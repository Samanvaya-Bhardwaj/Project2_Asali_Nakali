"""
linkage.py
----------
Approximate matching of a noisy pack code against the national registry (DB3),
and the reverse: every noisy record across the silos that refers to a product.

Pipeline for one record
  1. canonicalise   format noise removed (standardize.canonical_code)
  2. block          products sharing enough folded bigrams with the code
  3. compare        for each candidate, a comparison vector gamma:
                      code     learned noisy-channel distance, by capture channel
                      custody  was this product ever shipped to this pharmacy (DB2)
                      price    unit price against the product's MRP (DB3)
                      date     sale between manufacture, arrival and expiry
                      label    brand, strength, batch, expiry and MRP read off the
                               photographed pack
                    (DB2 and DB4 records use the evidence they carry instead)
  4. weigh          Fellegi-Sunter: each agreement level contributes
                    log2( P(level | same product) / P(level | different product) )
  5. normalise      Bayesian posterior over the candidates *and* a null hypothesis,
                    "this code belongs to no registered product". The null is what
                    keeps a counterfeit serial one edit from a real one from being
                    rewritten into that real product.
  6. decide         EXACT, AUTO_LINK, REVIEW (a person decides), NO_MATCH, or
                    VALID_BUT_WRONG (the code exists but the evidence points at a
                    neighbour of it)
"""

from __future__ import annotations
import hashlib
import json
import math
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

from . import paths
from .confusion import ConfusionModel, code_level
from .context import LiveContext, bigrams, fold, get_context
from .similarity import (damerau_osa, edit_similarity, jaro_winkler, levenshtein,
                         qgram_jaccard, soundex_similarity)
from .standardize import (LabelReading, canonical_code, extract_codes, find_strength,
                          name_tokens, parse_datetime, parse_label)

CHANNEL_OF_SCAN = {"barcode": "scan", "qrcode": "scan", "nfc": "scan",
                   "manual": "manual", "ocr": "ocr"}

FEATURES: Dict[str, List[str]] = {
    "db1": ["code", "custody", "price", "date", "label_brand", "label_strength",
            "label_batch", "label_expiry", "label_mrp"],
    "db2": ["code", "mfr", "auth", "dest", "sold_at_dest", "date"],
    "db4": ["code", "brand_mention", "vendor_mention", "date"],
    "ref": ["code"],
}

# Starting values for m = P(level | match) and u = P(level | non-match, same block).
# Training replaces them with estimates from labelled data; these keep the matcher
# usable, and sensibly conservative, before any training has run.
DEFAULT_MU: Dict[str, Dict[str, Tuple[float, float]]] = {
    "code": {"L0_exact": (0.80, 0.002), "L1_confusable": (0.09, 0.004), "L2_one_edit": (0.07, 0.05),
             "L3_two_edits": (0.03, 0.25), "L4_far": (0.01, 0.70)},
    "custody": {"to_vendor": (0.95, 0.02), "same_city": (0.02, 0.10),
                "elsewhere": (0.02, 0.55), "never": (0.01, 0.33)},
    "price": {"match": (0.93, 0.35), "low": (0.05, 0.25), "dump": (0.005, 0.15),
              "high": (0.01, 0.15), "extreme": (0.005, 0.10)},
    "date": {"ok": (0.97, 0.70), "pre_arrival": (0.01, 0.10), "pre_mfg": (0.005, 0.10),
             "expired": (0.015, 0.10), "ok_fresh": (0.85, 0.45), "ok_aged": (0.13, 0.30),
             "ok_old": (0.02, 0.20)},
    "sold_at_dest": {"yes": (0.85, 0.05), "no": (0.15, 0.95)},
    "label_brand": {"agree": (0.85, 0.03), "close": (0.12, 0.05), "disagree": (0.03, 0.92)},
    "label_strength": {"agree": (0.97, 0.30), "disagree": (0.03, 0.70)},
    "label_batch": {"exact": (0.70, 0.001), "near": (0.25, 0.01), "far": (0.05, 0.989)},
    "label_expiry": {"agree": (0.90, 0.10), "disagree": (0.10, 0.90)},
    "label_mrp": {"agree": (0.95, 0.30), "disagree": (0.05, 0.70)},
    "mfr": {"agree": (0.95, 0.25), "disagree": (0.04, 0.70), "unknown_claim": (0.01, 0.05)},
    "auth": {"authorized": (0.97, 0.60), "not_authorized": (0.02, 0.30), "ghost": (0.01, 0.10)},
    "dest": {"licensed": (0.99, 0.93), "unlicensed": (0.01, 0.07)},
    "brand_mention": {"agree": (0.80, 0.03), "other_brand": (0.05, 0.40)},
    "vendor_mention": {"agree": (0.70, 0.05), "disagree": (0.30, 0.95)},
}
DEFAULT_PI0 = {"db1": 0.03, "db2": 0.03, "db4": 0.10, "ref": 0.30}
DEFAULT_THRESHOLDS = {"link": 0.90, "none": 0.80, "alt": 0.60}

# Channels where a person or a camera produced the code, so a real-but-wrong
# code is plausibly a slip. A scanner reading a valid code is never overruled.
CORRECTABLE_CHANNELS = ("manual", "ocr", "erp", "citizen")


def is_auto(res: "MatchResult", thresholds: Dict[str, float]) -> bool:
    """Whether a match result may be applied without a person looking at it."""
    if res.decision in ("EXACT", "AUTO_LINK"):
        return True
    if res.decision == "VALID_BUT_WRONG":
        return res.channel in CORRECTABLE_CHANNELS and res.best_posterior >= max(0.98, thresholds.get("link", 0.9))
    return False


def _num(v) -> Optional[float]:
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


class LinkageModel:
    """Fellegi-Sunter parameters plus the learned code distance."""

    def __init__(self, confusion: Optional[ConfusionModel] = None,
                 m: Optional[Dict] = None, u: Optional[Dict] = None,
                 pi0: Optional[Dict[str, float]] = None,
                 thresholds: Optional[Dict[str, float]] = None,
                 meta: Optional[Dict] = None):
        self.confusion = confusion or ConfusionModel()
        self.m = m or {}
        self.u = u or {}
        self.pi0 = dict(DEFAULT_PI0, **(pi0 or {}))
        self.thresholds = dict(DEFAULT_THRESHOLDS, **(thresholds or {}))
        self.meta = meta or {"source": "built-in defaults (no training run yet)"}

    def _mu(self, source: str, feature: str, value: str) -> Tuple[float, float]:
        m = self.m.get(source, {}).get(feature, {}).get(value)
        u = self.u.get(source, {}).get(feature, {}).get(value)
        if m is not None and u is not None:
            return m, u
        base = value.split(":", 1)[-1]
        return DEFAULT_MU.get(feature, {}).get(base, (0.5, 0.5))

    def weight(self, source: str, feature: str, value: str) -> float:
        m, u = self._mu(source, feature, value)
        return math.log2(max(m, 1e-6) / max(u, 1e-6))

    def to_dict(self) -> Dict:
        return {"confusion": self.confusion.to_dict(), "m": self.m, "u": self.u,
                "pi0": self.pi0, "thresholds": self.thresholds, "meta": self.meta}

    @classmethod
    def from_dict(cls, d: Dict) -> "LinkageModel":
        return cls(ConfusionModel.from_dict(d.get("confusion", {})), d.get("m"), d.get("u"),
                   d.get("pi0"), d.get("thresholds"), d.get("meta"))

    def save(self, path: Optional[str] = None) -> str:
        path = path or paths.model_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=1)
        return path


_MODEL = {"mtime": None, "model": None}


def load_model() -> LinkageModel:
    path = paths.model_file()
    try:
        mtime = os.stat(path).st_mtime_ns
    except OSError:
        mtime = None
    if _MODEL["model"] is None or _MODEL["mtime"] != mtime:
        model = LinkageModel()
        if mtime is not None:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    model = LinkageModel.from_dict(json.load(f))
            except (OSError, ValueError):
                model = LinkageModel()
        _MODEL.update(mtime=mtime, model=model)
    return _MODEL["model"]


@dataclass
class CandidateScore:
    uid: str
    product_name: str
    strength: str
    manufacturer: str
    batch_number: str
    mrp: Optional[float]
    code_distance: float
    code_similarity: float
    code_level: str
    features: Dict[str, str]
    weights: Dict[str, float]
    total_weight: float
    posterior: float = 0.0


@dataclass
class MatchResult:
    source: str
    key: str
    raw_code: str
    code: str
    channel: str
    decision: str
    best_uid: Optional[str]
    best_posterior: float
    p_none: float
    exact_uid: Optional[str]
    candidates: List[CandidateScore] = field(default_factory=list)
    explanation: str = ""
    notes: List[str] = field(default_factory=list)
    label: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        d = asdict(self)
        d["best_posterior"] = round(self.best_posterior, 4)
        d["p_none"] = round(self.p_none, 4)
        for c in d["candidates"]:
            c["posterior"] = round(c["posterior"], 4)
            c["total_weight"] = round(c["total_weight"], 2)
            c["code_distance"] = round(c["code_distance"], 3)
            c["code_similarity"] = round(c["code_similarity"], 3)
            c["weights"] = {k: round(v, 2) for k, v in c["weights"].items()}
        return d


class Matcher:
    def __init__(self, ctx: Optional[LiveContext] = None, model: Optional[LinkageModel] = None):
        self.ctx = ctx or get_context()
        self.model = model or load_model()
        self._dist: Dict[Tuple[str, str], float] = {}
        self._cache: Dict[str, MatchResult] = {}
        self._batch_index: Dict[str, List[str]] = {}
        for uid, p in self.ctx.products.items():
            if p.get("batch_key"):
                self._batch_index.setdefault(p["batch_key"], []).append(uid)

    # -- record adapters --------------------------------------------------------

    @staticmethod
    def record_from_db1(row: Dict[str, object]) -> Dict[str, object]:
        return {"source": "db1", "table": "purchase_events", "key": row.get("event_id"),
                "code": row.get("scan_code"),
                "channel": CHANNEL_OF_SCAN.get(str(row.get("scan_method") or "").lower(), "manual"),
                "vendor_id": row.get("vendor_id"), "price_paid": row.get("price_paid"),
                "quantity": row.get("quantity_bought"), "date": row.get("scan_timestamp"),
                "label_text": row.get("label_text")}

    @staticmethod
    def record_from_db2(row: Dict[str, object]) -> Dict[str, object]:
        return {"source": "db2", "table": "distribution_batches", "key": row.get("batch_id"),
                "code": row.get("batch_serial"), "channel": "erp",
                "manufacturer_ref": row.get("manufacturer_ref"),
                "distributor_id": row.get("distributor_id"),
                "vendor_id": row.get("destination_vendor_id"), "date": row.get("dispatch_date")}

    @staticmethod
    def record_from_db4(row: Dict[str, object]) -> Dict[str, object]:
        return {"source": "db4", "table": "complaints", "key": row.get("complaint_id"),
                "code": row.get("complaint_item_ref"), "channel": "citizen",
                "description": row.get("description"),
                "purchase_location": row.get("purchase_location"),
                "date": row.get("complaint_date")}

    @staticmethod
    def record_from_ref(table: str, key_col: str, row: Dict[str, object]) -> Dict[str, object]:
        return {"source": "ref", "table": table, "key": row.get(key_col),
                "code": row.get("item_ref"), "channel": "official"}

    # -- comparison -------------------------------------------------------------

    def distance(self, code: str, uid: str) -> float:
        key = (code, uid)
        d = self._dist.get(key)
        if d is None:
            d = self.model.confusion.distance(code, uid)
            self._dist[key] = d
        return d

    def _custody(self, rec, uid) -> Optional[str]:
        vid = self.ctx.vendor_id(rec.get("vendor_id"))
        if not vid:
            return None
        shipped = self.ctx.shipped_to(uid)
        if vid in shipped:
            return "to_vendor"
        city = self.ctx.city_of(vid)
        if city and city in self.ctx.custody_cities.get(uid, ()):
            return "same_city"
        return "elsewhere" if shipped else "never"

    def _price(self, rec, p) -> Optional[str]:
        price, mrp = _num(rec.get("price_paid")), _num(p.get("msrp_kes"))
        if price is None or not mrp:
            return None
        qty = max(1, int(_num(rec.get("quantity")) or 1))
        r = price / qty / mrp
        if r < 0.40:
            return "dump"
        if r < 0.80:
            return "low"
        if r <= 1.02:
            return "match"
        if r <= 1.50:
            return "high"
        return "extreme"

    def _date(self, rec, p, uid, mode: str) -> Optional[str]:
        parsed = rec.get("_parsed_date")
        if parsed is None:
            parsed = rec["_parsed_date"] = parse_datetime(rec.get("date"))
        readings = [d for d in [parsed.value] + parsed.alternatives if d is not None]
        if not readings:
            return None
        vid = self.ctx.vendor_id(rec.get("vendor_id")) if mode == "sale" else None
        arrived = self.ctx.shipped_to(uid).get(vid) if vid else None

        def classify(d):
            if p.get("mfg_dt") and d.date() < p["mfg_dt"].date():
                return "pre_mfg"
            if mode != "complaint" and p.get("exp_dt") and d.date() > p["exp_dt"].date():
                return "expired"
            if arrived is not None and d.date() < arrived.date():
                return "pre_arrival"
            if mode == "dispatch" and p.get("mfg_dt"):
                # Distributors ship a batch soon after release; an older sibling
                # batch would have been dispatched long after its manufacture.
                lag = (d.date() - p["mfg_dt"].date()).days
                return "ok_fresh" if lag <= 90 else "ok_aged" if lag <= 240 else "ok_old"
            return "ok"

        verdicts = [classify(d) for d in readings]
        good = [v for v in verdicts if v.startswith("ok")]
        return good[0] if good else verdicts[0]

    def _label(self, rec, p) -> Dict[str, Optional[str]]:
        lab: LabelReading = rec.get("_label")
        out: Dict[str, Optional[str]] = {}
        if lab is None or lab.empty:
            return out
        if lab.brand and p.get("brand"):
            jw = jaro_winkler(lab.brand, p["brand"])
            out["label_brand"] = "agree" if jw >= 0.92 else "close" if jw >= 0.80 else "disagree"
        ps = find_strength(p.get("strength"))
        if lab.strength and ps:
            out["label_strength"] = "agree" if lab.strength == ps else "disagree"
        if lab.batch and p.get("batch_key"):
            d = self.model.confusion.distance(canonical_code(lab.batch), p["batch_key"])
            out["label_batch"] = "exact" if d == 0 else "near" if d <= 1.2 else "far"
        if lab.expiry and p.get("exp_dt"):
            out["label_expiry"] = "agree" if lab.expiry == p["exp_dt"].strftime("%Y-%m") else "disagree"
        mrp = _num(p.get("msrp_kes"))
        if lab.mrp and mrp:
            out["label_mrp"] = "agree" if abs(lab.mrp - mrp) <= 0.02 * mrp else "disagree"
        return out

    def _db2(self, rec, p) -> Dict[str, Optional[str]]:
        out: Dict[str, Optional[str]] = {}
        vid = self.ctx.vendor_id(rec.get("vendor_id"))
        if vid:
            v = self.ctx.vendors.get(vid) or {}
            licensed = bool(v.get("active")) and v.get("vendor_type") != "kiosk"
            out["dest"] = "licensed" if licensed else "unlicensed"
            out["sold_at_dest"] = "yes" if vid in self.ctx.sold_at.get(p["product_uid"], ()) else "no"
        ref = str(rec.get("manufacturer_ref") or "").strip().upper()
        if ref:
            out["mfr"] = ("unknown_claim" if ref == "UNKNOWN"
                          else "agree" if ref == p.get("manufacturer_id") else "disagree")
        did = rec.get("distributor_id")
        if did:
            if did in self.ctx.authorized.get(p.get("manufacturer_id"), set()):
                out["auth"] = "authorized"
            else:
                d = self.ctx.distributors.get(did)
                out["auth"] = "ghost" if d is not None and not d.get("is_authorized") else "not_authorized"
        return out

    def _mentions(self, rec) -> None:
        if "_brands" in rec:
            return
        text = f"{rec.get('description') or ''} {rec.get('purchase_location') or ''}".upper()
        words = set(re.findall(r"[A-Z]{5,}", text))
        brands = set()
        for b in self.ctx.brands:
            if any(jaro_winkler(w, b) >= 0.92 for w in words if abs(len(w) - len(b)) <= 3):
                brands.add(b)
        rec["_brands"] = brands
        loc = str(rec.get("purchase_location") or "")
        loc_tokens = set(name_tokens(loc))
        vendors = set()
        if loc_tokens:
            for vid, v in self.ctx.vendors.items():
                shared = v["tokens"] & loc_tokens
                city = str(v.get("city") or "").upper()
                if shared and (not city or city.split()[0] in loc.upper()):
                    vendors.add(vid)
        rec["_vendors"] = vendors

    def _db4(self, rec, p, uid) -> Dict[str, Optional[str]]:
        self._mentions(rec)
        out: Dict[str, Optional[str]] = {}
        if rec["_brands"]:
            out["brand_mention"] = "agree" if p.get("brand") in rec["_brands"] else "other_brand"
        if rec["_vendors"]:
            shipped = set(self.ctx.shipped_to(uid))
            out["vendor_mention"] = "agree" if rec["_vendors"] & shipped else "disagree"
        return out

    def features(self, rec: Dict[str, object], uid: str, dist: float) -> Dict[str, Optional[str]]:
        p = self.ctx.products[uid]
        src = rec.get("source", "db1")
        feats: Dict[str, Optional[str]] = {}
        if rec.get("_code", True):      # no code at all is missing evidence, not disagreement
            feats["code"] = f"{rec.get('channel', 'manual')}:{code_level(dist)}"
        if src == "db1":
            feats["custody"] = self._custody(rec, uid)
            feats["price"] = self._price(rec, p)
            feats["date"] = self._date(rec, p, uid, "sale")
            feats.update(self._label(rec, p))
        elif src == "db2":
            feats.update(self._db2(rec, p))
            feats["date"] = self._date(rec, p, uid, "dispatch")
        elif src == "db4":
            feats.update(self._db4(rec, p, uid))
            feats["date"] = self._date(rec, p, uid, "complaint")
        return {k: v for k, v in feats.items() if v is not None}

    # -- matching ---------------------------------------------------------------

    def _posteriors(self, source: str, weights: List[float]) -> Tuple[List[float], float]:
        pi0 = min(max(self.model.pi0.get(source, 0.05), 1e-4), 0.999)
        n = max(len(self.ctx.products), 1)
        log_prior = math.log2((1 - pi0) / n)
        terms = [math.log2(pi0)] + [w + log_prior for w in weights]
        top = max(terms)
        z = top + math.log2(sum(2.0 ** (t - top) for t in terms))
        return [2.0 ** (t - z) for t in terms[1:]], 2.0 ** (terms[0] - z)

    def _cache_key(self, rec) -> str:
        plain = {k: v for k, v in rec.items() if not k.startswith("_")}
        return hashlib.sha1(json.dumps(plain, sort_keys=True, default=str).encode()).hexdigest()

    def match(self, rec: Dict[str, object], limit: int = 8) -> MatchResult:
        ck = self._cache_key(rec)
        hit = self._cache.get(ck)
        if hit is not None:
            return hit

        source = rec.get("source", "db1")
        model_source = source if source in FEATURES else "db1"
        notes: List[str] = []
        code = canonical_code(rec.get("code"))
        if source == "db4" and not code:
            found = extract_codes(rec.get("description"))
            if found:
                code = found[0]
                notes.append(f"Code field was empty; '{code}' was read from the complaint text.")
        lab = parse_label(rec.get("label_text")) if rec.get("label_text") else None
        rec["_label"] = lab
        if not code and lab and lab.code:
            code = lab.code
            notes.append(f"Code taken from the label image text: '{code}'.")

        rec["_code"] = code
        resolved = self.ctx.resolve_alias(code)
        exact = resolved if resolved in self.ctx.products else None
        if exact and exact != code:
            notes.append(f"'{code}' is a registered duplicate of '{exact}'.")

        uids = self.ctx.block(code) if code else []
        if exact and exact not in uids:
            uids.insert(0, exact)
        if lab and lab.batch:
            for uid in self._batch_index.get(canonical_code(lab.batch), []):
                if uid not in uids:
                    uids.append(uid)
        if lab and len(uids) < 3 and (lab.brand or lab.batch):
            # The code is missing or too damaged to block on: let the label propose
            # candidates by brand name and by (damaged) batch number instead.
            notes.append("Few candidates from the code; the label's brand and batch number proposed more.")
            batch = canonical_code(lab.batch) if lab.batch else ""
            for uid, p in self.ctx.products.items():
                if uid in uids:
                    continue
                if lab.brand and p.get("brand") and jaro_winkler(lab.brand, p["brand"]) >= 0.85:
                    uids.append(uid)
                elif batch and p.get("batch_key") and self.model.confusion.distance(batch, p["batch_key"]) <= 1.2:
                    uids.append(uid)

        scored: List[CandidateScore] = []
        for uid in uids:
            dist = 0.0 if uid == exact else self.distance(code, uid)
            feats = self.features(rec, uid, dist)
            weights = {f: self.model.weight(model_source, f, v) for f, v in feats.items()}
            p = self.ctx.products[uid]
            scored.append(CandidateScore(
                uid=uid, product_name=str(p.get("product_name") or ""),
                strength=str(p.get("strength") or ""),
                manufacturer=str(p.get("manufacturer_name") or p.get("manufacturer_id") or ""),
                batch_number=str(p.get("batch_number") or ""), mrp=_num(p.get("msrp_kes")),
                code_distance=dist,
                code_similarity=max(0.0, 1.0 - dist / max(len(code), len(uid), 1)),
                code_level=code_level(dist), features=feats, weights=weights,
                total_weight=sum(weights.values())))

        posts, p_none = self._posteriors(model_source, [c.total_weight for c in scored])
        for c, pst in zip(scored, posts):
            c.posterior = pst
        scored.sort(key=lambda c: (-c.posterior, c.code_distance, c.uid))
        best = scored[0] if scored else None
        th = self.model.thresholds

        if exact:
            # A registered code is overruled only when the evidence moves most of
            # the probability onto *other* registered products. Probability moving
            # to "no product" instead (a real code in a suspicious context) is a
            # fraud signal for the verification engine, not a typo to correct.
            others = [c for c in scored if c.uid != exact]
            p_exact = next((c.posterior for c in scored if c.uid == exact), 0.0)
            if others and sum(c.posterior for c in others) >= th["alt"] and others[0].posterior > p_exact:
                decision, best_uid = "VALID_BUT_WRONG", others[0].uid
            else:
                decision, best_uid = "EXACT", exact
                if p_none >= th["none"]:
                    notes.append("The code is registered, but the other details of this record (pharmacy, price, "
                                 "dates or label) do not fit that product: a real code used in a suspicious way.")
        elif best is not None and best.posterior >= th["link"]:
            decision, best_uid = "AUTO_LINK", best.uid
        elif not scored or p_none >= th["none"]:
            decision, best_uid = "NO_MATCH", None
        else:
            decision, best_uid = "REVIEW", best.uid if best else None

        best_post = next((c.posterior for c in scored if c.uid == best_uid), 0.0)
        result = MatchResult(
            source=source, key=str(rec.get("key") or ""), raw_code=str(rec.get("code") or ""),
            code=code, channel=str(rec.get("channel") or ""), decision=decision,
            best_uid=best_uid, best_posterior=best_post, p_none=p_none, exact_uid=exact,
            candidates=scored[:limit], notes=notes,
            label=lab.as_dict() if lab and not lab.empty else {})
        result.explanation = explain(result)
        self._cache[ck] = result
        return result

    # -- reverse ----------------------------------------------------------------

    def iter_records(self):
        for row in self.ctx.db1_events:
            yield "db1", "purchase_events", "event_id", "scan_code", row, self.record_from_db1(row)
        for row in self.ctx.db2_batches:
            yield "db2", "distribution_batches", "batch_id", "batch_serial", row, self.record_from_db2(row)
        for row in self.ctx.db4_complaints:
            yield "db4", "complaints", "complaint_id", "complaint_item_ref", row, self.record_from_db4(row)
        for table, key, rows in (("lab_reports", "lab_report_id", self.ctx.db4_lab),
                                 ("ministry_blacklist", "blacklist_id", self.ctx.db4_blacklist),
                                 ("public_alerts", "alert_id", self.ctx.db4_alerts)):
            for row in rows:
                yield "db4", table, key, "item_ref", row, self.record_from_ref(table, key, row)

    def reverse(self, uid: str, min_posterior: float = 0.05) -> Dict[str, object]:
        """Every record in DB1, DB2 and DB4 that approximately refers to this product."""
        target = self.ctx.resolve_alias(canonical_code(uid))
        p = self.ctx.products.get(target)
        if not p:
            return {"found": False, "uid": uid, "records": [],
                    "message": f"'{uid}' is not a registered product in DB3."}
        tgrams = bigrams(fold(target))
        floor = max(3, int(0.35 * len(tgrams)))
        out = []
        for db_id, table, key_col, code_col, row, rec in self.iter_records():
            stored = row.get(code_col)
            code = canonical_code(stored)
            if not code and db_id == "db4":
                found = extract_codes(row.get("description"))
                code = found[0] if found else ""
            if not code:
                continue
            if self.ctx.resolve_alias(code) != target and len(bigrams(fold(code)) & tgrams) < floor:
                continue
            res = self.match(rec)
            cand = next((c for c in res.candidates if c.uid == target), None)
            if cand is None or cand.posterior < min_posterior:
                continue
            out.append({
                "db_id": db_id, "table": table, "key": row.get(key_col), "stored_code": stored,
                "exact": stored == target, "posterior": round(cand.posterior, 4),
                "decision": res.decision, "best_uid": res.best_uid,
                "points_here": res.best_uid == target, "code_distance": round(cand.code_distance, 3),
                "features": cand.features, "channel": res.channel,
                "summary": _row_summary(db_id, table, row),
                "context": {k: rec.get(k) for k in ("vendor_id", "price_paid", "quantity", "date")
                            if rec.get(k) is not None},
            })
        out.sort(key=lambda r: (not r["exact"], -r["posterior"]))
        by_source: Dict[str, int] = {}
        for r in out:
            by_source[r["db_id"]] = by_source.get(r["db_id"], 0) + 1
        return {"found": True, "uid": target, "product": _public_product(p),
                "shipped_to": sorted(self.ctx.shipped_to(target)), "records": out,
                "counts": {"total": len(out), "exact": sum(r["exact"] for r in out),
                           "noisy": sum(not r["exact"] for r in out), "by_source": by_source}}


def _public_product(p: Dict[str, object]) -> Dict[str, object]:
    keep = ["product_uid", "product_name", "generic_name", "strength", "manufacturer_id",
            "manufacturer_name", "batch_number", "manufacture_date", "expiry_date", "msrp_kes",
            "category", "dosage_form", "is_recalled"]
    return {k: p.get(k) for k in keep}


def _row_summary(db_id: str, table: str, row: Dict[str, object]) -> str:
    if table == "purchase_events":
        return f"{row.get('vendor_id')} · {row.get('scan_timestamp')} · Rs {row.get('price_paid')} · {row.get('scan_method')}"
    if table == "distribution_batches":
        return f"{row.get('distributor_id')} → {row.get('destination_vendor_id')} · {row.get('dispatch_date')}"
    if table == "complaints":
        return f"{row.get('complaint_category')} · {row.get('complaint_date')} · {str(row.get('purchase_location') or '')[:40]}"
    return str(row.get("reason") or row.get("message") or row.get("findings_summary") or "")[:80]


_FEATURE_TEXT = {
    "custody": {"to_vendor": "shipped to this pharmacy", "same_city": "shipped only to other pharmacies in this city",
                "elsewhere": "shipped only to other cities", "never": "never shipped anywhere"},
    "price": {"match": "price fits MRP", "low": "priced 20-60% below MRP", "dump": "priced under 40% of MRP",
              "high": "priced above MRP", "extreme": "price far above MRP"},
    "date": {"ok": "dates consistent", "pre_arrival": "sold before it arrived", "pre_mfg": "dated before manufacture",
             "expired": "dated after expiry", "ok_fresh": "dispatched soon after manufacture",
             "ok_aged": "dispatched 3-8 months after manufacture", "ok_old": "dispatched long after manufacture"},
    "sold_at_dest": {"yes": "later scanned at the destination pharmacy", "no": "never scanned at the destination"},
    "dest": {"licensed": "shipped to a licensed pharmacy", "unlicensed": "shipped to an unlicensed outlet"},
    "auth": {"authorized": "carrier authorised by the maker", "not_authorized": "carrier not authorised by the maker",
             "ghost": "carrier with no valid licence"},
}


def explain(res: MatchResult) -> str:
    if not res.candidates:
        return f"No registered product is close enough to '{res.code}'."
    best = next((c for c in res.candidates if c.uid == res.best_uid), res.candidates[0])
    parts = []
    for f, v in best.features.items():
        if f == "code":
            continue
        text = _FEATURE_TEXT.get(f, {}).get(v, f"{f.replace('_', ' ')}: {v}")
        parts.append(f"{text} ({best.weights.get(f, 0):+.1f})")
    evidence = "; ".join(parts) if parts else "no other clues available"
    if res.decision in ("NO_MATCH", "REVIEW"):
        evidence = f"clues for {best.uid}: " + evidence
    what = f"'{res.code}'" if res.code else "The label"
    head = {
        "EXACT": f"{what} is a registered code.",
        "AUTO_LINK": f"{what} is {best.uid} ({best.posterior:.1%} sure).",
        "REVIEW": f"The closest product is {best.uid}, but only {best.posterior:.1%} sure, so a person should check.",
        "NO_MATCH": f"{res.p_none:.1%} chance that {what} is not a registered product.",
        "VALID_BUT_WRONG": f"{what} is a real code, but the other clues point to {best.uid} ({best.posterior:.1%} sure).",
    }[res.decision]
    if "code" in best.weights:
        level = _LEVEL_TEXT.get(best.code_level, best.code_level.split("_", 1)[1].replace("_", " "))
        code_part = f"Code difference {best.code_distance:.2f} ({level}, {best.weights['code']:+.1f})"
    else:
        code_part = "No code was readable, so the label alone is the evidence"
    return f"{head} {code_part}; {evidence}."


# -- algorithm comparison for a single query -------------------------------------

_LEVEL_TEXT = {"L0_exact": "exact", "L1_confusable": "look-alike letters", "L2_one_edit": "one letter off",
               "L3_two_edits": "two letters off", "L4_far": "very different"}


def compare_algorithms(code: str, ctx: Optional[LiveContext] = None,
                       model: Optional[LinkageModel] = None, top: int = 3) -> List[Dict[str, object]]:
    """Each string metric's own top candidates for one query, over the whole registry."""
    ctx = ctx or get_context()
    model = model or load_model()
    q = canonical_code(code)
    uids = list(ctx.products)
    metrics = {
        "Levenshtein": lambda a, b: edit_similarity(levenshtein(a, b), a, b),
        "Damerau-Levenshtein": lambda a, b: edit_similarity(damerau_osa(a, b), a, b),
        "Jaro-Winkler": jaro_winkler,
        "Bigram Jaccard": qgram_jaccard,
        "Soundex": soundex_similarity,
        "Learned OCR distance": model.confusion.similarity,
    }
    out = []
    for name, fn in metrics.items():
        scored = sorted(((fn(q, u), u) for u in uids), key=lambda t: (-t[0], t[1]))
        ties = sum(1 for s, _ in scored if s == scored[0][0]) if scored else 0
        out.append({"algorithm": name, "top": [{"uid": u, "score": round(s, 3)} for s, u in scored[:top]],
                    "ties_at_top": ties})
    return out


_MATCHER = {"key": None, "matcher": None}


def get_matcher(aliases: Optional[Dict[str, str]] = None,
                vendor_aliases: Optional[Dict[str, str]] = None) -> Matcher:
    """A matcher over the current silos, rebuilt when the data or the model changes."""
    ctx = get_context(aliases, vendor_aliases)
    model = load_model()
    key = (id(ctx), id(model))
    if _MATCHER["key"] != key:
        m = Matcher(ctx, model)
        ctx.complete_custody(m)
        m._cache.clear()
        _MATCHER.update(key=key, matcher=m)
    return _MATCHER["matcher"]
