"""
cleanser.py
-----------
Finds every kind of data anomaly across the silos, proposes a fix for each with
a confidence and a reason, applies the ones that are safe, and keeps a lineage
log so any run can be undone.

Categories of uncertainty handled
  format             representation differs, meaning does not (dates, currency,
                     separators, vendor-id spelling). Deterministic.
  noisy_identifier   the code is damaged; linked by the probabilistic matcher.
  valid_but_wrong    the code exists, but every other piece of evidence says the
                     record is about a neighbouring product.
  duplicate_record   the same event recorded more than once (POS retry,
                     re-imported ERP file, a complaint filed twice).
  master_duplicate   one real-world product or pharmacy registered twice in a
                     master table, under two identifiers.
  conflict           two silos disagree on the same fact; resolved by source
                     authority, or annotated when no source can be trusted over
                     the other.
  missing_value      a value absent but determined by other silos.
  outlier            a value that cannot be right as recorded (a unit error).
  counterfeit_signal a code that belongs to no registered product. It is *not*
                     cleansed: rewriting it into the nearest real product would
                     destroy the evidence of a fake. It is quarantined instead.

Decisions
  AUTO     safe to apply without a person (deterministic, or posterior above the
           link threshold)
  REVIEW   a person decides; the candidates and their evidence are shown
  RETAIN   evidence of fraud; quarantined by annotation, values left alone
  DISMISSED a reviewer has already looked and kept the record as it is
"""

from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from . import paths
from .context import LiveContext, get_context
from .linkage import Matcher, MatchResult, get_matcher, is_auto
from .similarity import jaro_winkler
from .standardize import (canonical_code, is_canonical_datetime, license_key,
                          normalize_currency, parse_datetime)

CATEGORY_INFO = {
    "format": ("Representation mismatch", "Same value, written differently by different systems."),
    "noisy_identifier": ("Noisy identifier", "Damaged code linked to the registry by the probabilistic matcher."),
    "valid_but_wrong": ("Valid but wrong identifier", "A real code, but the evidence points at a neighbouring product."),
    "duplicate_record": ("Duplicate record", "The same event stored more than once."),
    "master_duplicate": ("Duplicate master record", "One product or pharmacy registered under two identifiers."),
    "conflict": ("Cross-source conflict", "Two silos disagree on the same fact."),
    "missing_value": ("Missing value", "Absent, but determined by another silo."),
    "outlier": ("Implausible value", "Cannot be right as recorded."),
    "counterfeit_signal": ("Counterfeit signal (kept)", "Belongs to no registered product; quarantined, not rewritten."),
}

DQ_FLAG = "DQ:"
QUARANTINE = "DQ: quarantined"


@dataclass
class Change:
    db_id: str
    table: str
    pk_col: str
    pk_val: str
    action: str                     # UPDATE or DELETE
    column: Optional[str] = None
    old: object = None
    new: object = None


@dataclass
class Issue:
    issue_id: str
    category: str
    decision: str
    confidence: float
    db_id: str
    table: str
    pk_col: str
    pk_val: str
    column: str
    current: object
    proposed: object
    method: str
    explanation: str
    changes: List[Change] = field(default_factory=list)
    candidates: List[Dict[str, object]] = field(default_factory=list)
    truth: Optional[str] = None
    quarantine_changes: List[Change] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        d = asdict(self)
        d["category_label"] = CATEGORY_INFO[self.category][0]
        d["confidence"] = round(self.confidence, 4)
        d["can_quarantine"] = bool(self.quarantine_changes)
        d.pop("quarantine_changes", None)
        return d


def _append_note(existing, note: str) -> str:
    """Annotations are added to what a record already says, never written over it."""
    existing = str(existing or "").strip()
    return f"{existing}; {note}" if existing else note


def _issue_id(category: str, db_id: str, table: str, pk: str, column: str, proposed) -> str:
    raw = f"{category}|{db_id}|{table}|{pk}|{column}|{proposed}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


# -- lineage store --------------------------------------------------------------

def _dq_conn() -> sqlite3.Connection:
    os.makedirs(paths.db_dir(), exist_ok=True)
    conn = sqlite3.connect(paths.db_path("dq"))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS dq_runs (
            run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, mode TEXT, actor TEXT,
            issues_applied INTEGER, changes_applied INTEGER, summary_json TEXT, undone_at TEXT);
        CREATE TABLE IF NOT EXISTS dq_actions (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, seq INTEGER NOT NULL,
            issue_id TEXT, category TEXT, decision TEXT, db_id TEXT, table_name TEXT, pk_col TEXT,
            pk_val TEXT, action TEXT, column_name TEXT, old_value TEXT, new_value TEXT,
            row_snapshot TEXT, confidence REAL, method TEXT, explanation TEXT, applied_at TEXT);
        CREATE TABLE IF NOT EXISTS dq_decisions (
            issue_id TEXT PRIMARY KEY, decision TEXT NOT NULL, chosen_value TEXT,
            decided_at TEXT NOT NULL, note TEXT);
        CREATE INDEX IF NOT EXISTS idx_dq_actions_run ON dq_actions(run_id);
    """)
    return conn


def _dismissed() -> Dict[str, Dict[str, object]]:
    if not os.path.exists(paths.db_path("dq")):
        return {}
    conn = _dq_conn()
    try:
        return {r["issue_id"]: dict(r) for r in conn.execute("SELECT * FROM dq_decisions")}
    finally:
        conn.close()


def _load_truth() -> Dict[str, Dict[str, object]]:
    try:
        with open(paths.ground_truth_file(), "r", encoding="utf-8") as f:
            return json.load(f).get("records", {})
    except (OSError, ValueError):
        return {}


# -- the scanner ----------------------------------------------------------------

class Scanner:
    def __init__(self):
        base = get_context()
        self.product_aliases, master = Scanner.product_duplicates(base)
        self.vendor_aliases, vendor = Scanner.vendor_duplicates(base)
        self.matcher: Matcher = get_matcher(self.product_aliases, self.vendor_aliases)
        self.ctx: LiveContext = self.matcher.ctx
        self.issues: List[Issue] = master + vendor
        self.links: Dict[Tuple[str, str], Optional[str]] = {}     # (table, pk) -> effective uid
        self.evidence: List[Dict[str, object]] = []

    # -- helpers ------------------------------------------------------------------

    def add(self, category, decision, confidence, db_id, table, pk_col, pk_val, column,
            current, proposed, method, explanation, changes=None, candidates=None) -> Issue:
        issue = Issue(_issue_id(category, db_id, table, str(pk_val), column, proposed), category,
                      decision, float(confidence), db_id, table, pk_col, str(pk_val), column,
                      current, proposed, method, explanation, list(changes or []), list(candidates or []))
        self.issues.append(issue)
        return issue

    @staticmethod
    def _candidate_list(res: MatchResult, n: int = 4) -> List[Dict[str, object]]:
        return [{"uid": c.uid, "product_name": c.product_name, "strength": c.strength,
                 "posterior": round(c.posterior, 4), "code_distance": round(c.code_distance, 3),
                 "features": c.features} for c in res.candidates[:n]]

    # -- master duplicates ----------------------------------------------------------

    @staticmethod
    def _references(ctx: LiveContext) -> Counter:
        refs: Counter = Counter()
        for r in ctx.db1_events:
            refs[canonical_code(r.get("scan_code"))] += 1
        for r in ctx.db2_batches:
            refs[canonical_code(r.get("batch_serial"))] += 1
        for r in ctx.db4_complaints:
            refs[canonical_code(r.get("complaint_item_ref"))] += 1
        return refs

    @staticmethod
    def product_duplicates(ctx: LiveContext) -> Tuple[Dict[str, str], List[Issue]]:
        groups: Dict[tuple, List[Dict[str, object]]] = defaultdict(list)
        for p in ctx.all_products.values():
            if p.get("batch_key"):
                groups[(p["batch_key"], p.get("strength_key"), p.get("manufacturer_id"))].append(p)
        refs = Scanner._references(ctx)
        aliases: Dict[str, str] = {}
        issues: List[Issue] = []
        for members in groups.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda p: (-refs[p["product_uid"]], str(p.get("registration_no")), p["product_uid"]))
            survivor = members[0]
            for dup in members[1:]:
                jw = jaro_winkler(dup.get("brand") or "", survivor.get("brand") or "")
                if jw < 0.85:
                    continue
                same_reg = license_key(dup.get("registration_no")) == license_key(survivor.get("registration_no"))
                decision = "AUTO" if same_reg or jw >= 0.95 else "REVIEW"
                aliases[dup["product_uid"]] = survivor["product_uid"]
                changes = Scanner._repoint_product(ctx, dup["product_uid"], survivor["product_uid"])
                changes.append(Change("db3", "products", "product_uid", dup["product_uid"], "DELETE"))
                issues.append(Issue(
                    _issue_id("master_duplicate", "db3", "products", dup["product_uid"], "product_uid",
                              survivor["product_uid"]),
                    "master_duplicate", decision, 0.99 if same_reg else round(jw, 3), "db3", "products",
                    "product_uid", dup["product_uid"], "product_uid", dup["product_uid"], survivor["product_uid"],
                    "MDM survivorship: same batch, strength and manufacturer; brand Jaro-Winkler "
                    f"{jw:.2f}; registration numbers {'identical once normalised' if same_reg else 'differ'}",
                    f"'{dup.get('product_name')}' ({dup['product_uid']}) duplicates '{survivor.get('product_name')}' "
                    f"({survivor['product_uid']}). The survivor is the record more silos already reference "
                    f"({refs[survivor['product_uid']]} vs {refs[dup['product_uid']]}); "
                    f"{len(changes) - 1} reference(s) will be re-pointed before the duplicate is removed.",
                    changes))
        return aliases, issues

    @staticmethod
    def _repoint_product(ctx: LiveContext, dup: str, survivor: str) -> List[Change]:
        out = []
        for r in ctx.db1_events:
            if r.get("scan_code") == dup:
                out.append(Change("db1", "purchase_events", "event_id", r["event_id"], "UPDATE",
                                  "scan_code", dup, survivor))
        for r in ctx.db2_batches:
            if r.get("batch_serial") == dup:
                out.append(Change("db2", "distribution_batches", "batch_id", r["batch_id"], "UPDATE",
                                  "batch_serial", dup, survivor))
        for r in ctx.db4_complaints:
            if r.get("complaint_item_ref") == dup:
                out.append(Change("db4", "complaints", "complaint_id", r["complaint_id"], "UPDATE",
                                  "complaint_item_ref", dup, survivor))
        return out

    @staticmethod
    def vendor_duplicates(ctx: LiveContext) -> Tuple[Dict[str, str], List[Issue]]:
        by_license: Dict[str, List[Dict[str, object]]] = defaultdict(list)
        for v in ctx.vendors.values():
            if v.get("license_key"):
                by_license[v["license_key"]].append(v)
        aliases: Dict[str, str] = {}
        issues: List[Issue] = []
        for members in by_license.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda v: (str(v.get("registered_on") or "9999"), v["vendor_id"]))
            survivor = members[0]
            for dup in members[1:]:
                aliases[dup["vendor_id"]] = survivor["vendor_id"]
                changes = []
                for r in ctx.db1_events:
                    if r.get("vendor_id") == dup["vendor_id"]:
                        changes.append(Change("db1", "purchase_events", "event_id", r["event_id"], "UPDATE",
                                              "vendor_id", dup["vendor_id"], survivor["vendor_id"]))
                for r in ctx.db2_batches:
                    if r.get("destination_vendor_id") == dup["vendor_id"]:
                        changes.append(Change("db2", "distribution_batches", "batch_id", r["batch_id"], "UPDATE",
                                              "destination_vendor_id", dup["vendor_id"], survivor["vendor_id"]))
                changes.append(Change("db1", "vendors", "vendor_id", dup["vendor_id"], "DELETE"))
                issues.append(Issue(
                    _issue_id("master_duplicate", "db1", "vendors", dup["vendor_id"], "vendor_id", survivor["vendor_id"]),
                    "master_duplicate", "AUTO", 0.98, "db1", "vendors", "vendor_id", dup["vendor_id"], "vendor_id",
                    dup["vendor_id"], survivor["vendor_id"],
                    "Licence number identical once punctuation and case are removed",
                    f"'{dup.get('vendor_name')}' ({dup['vendor_id']}, licence {dup.get('license_no')}) is "
                    f"'{survivor.get('vendor_name')}' ({survivor['vendor_id']}, licence {survivor.get('license_no')}) "
                    f"registered a second time. {len(changes) - 1} reference(s) re-pointed, then the copy removed.",
                    changes))
        return aliases, issues

    # -- identifiers ----------------------------------------------------------------

    def _regulatory_ref(self, db_id, table, pk_col, pk_val, column, stored, rec):
        """
        Blacklist, alert and lab-report references are held to a different rule.
        Their codes are usually counterfeit codes, which are unregistered by
        definition, so "close to a registered product" is not evidence of a typo
        here. Linking one to the nearest real product would blacklist a genuine
        medicine and leave the fake un-vetoed. So: always fix formatting (that is
        what lets the blacklist veto find the code), and suggest a registered
        product only when the evidence for it is strong, and only for review.
        """
        res = self.matcher.match(rec)
        canon = canonical_code(stored)
        if stored and canon and stored != canon and not (res.exact_uid and res.exact_uid != canon):
            self.add("format", "AUTO", 1.0, db_id, table, pk_col, pk_val, column, stored, canon,
                     "Deterministic canonicalisation (case, spacing, separators)",
                     f"'{stored}' becomes '{canon}'. Only the formatting changes, so the blacklist veto and "
                     "alert lookups can find the code; no character is altered.",
                     [Change(db_id, table, pk_col, pk_val, "UPDATE", column, stored, canon)])
        if res.decision in ("AUTO_LINK", "VALID_BUT_WRONG") and res.best_uid and res.best_uid != canon:
            self.add("noisy_identifier", "REVIEW", res.best_posterior, db_id, table, pk_col, pk_val, column,
                     stored, res.best_uid, "Fellegi-Sunter linkage (regulatory reference: review only)",
                     res.explanation + " A regulatory reference is never re-pointed at a registered product "
                     "without a person confirming it.",
                     [Change(db_id, table, pk_col, pk_val, "UPDATE", column, stored, res.best_uid)],
                     self._candidate_list(res))
        elif res.decision != "EXACT":
            self.evidence.append({"db_id": db_id, "table": table, "key": pk_val, "code": stored,
                                  "p_none": round(res.p_none, 4)})
        self.links[(table, str(pk_val))] = res.exact_uid
        return res, res.exact_uid

    def _identifier(self, db_id, table, pk_col, pk_val, column, stored, rec, flag_change=None):
        res = self.matcher.match(rec)
        effective = None
        if res.decision == "EXACT":
            effective = res.exact_uid
            canon = canonical_code(stored)
            if stored != effective and canon == effective:
                self.add("format", "AUTO", 1.0, db_id, table, pk_col, pk_val, column, stored, effective,
                         "Deterministic canonicalisation (case, spacing, separators)",
                         f"'{stored}' and '{effective}' differ only in formatting.",
                         [Change(db_id, table, pk_col, pk_val, "UPDATE", column, stored, effective)])
        elif res.decision in ("AUTO_LINK", "REVIEW", "VALID_BUT_WRONG"):
            category = "valid_but_wrong" if res.decision == "VALID_BUT_WRONG" else "noisy_identifier"
            decision = "AUTO" if is_auto(res, self.matcher.model.thresholds) else "REVIEW"
            proposed = res.best_uid
            effective = proposed if decision == "AUTO" else res.exact_uid
            issue = self.add(category, decision, res.best_posterior, db_id, table, pk_col, pk_val, column, stored,
                             proposed, "Fellegi-Sunter linkage over learned code distance and context evidence",
                             res.explanation,
                             [Change(db_id, table, pk_col, pk_val, "UPDATE", column, stored, proposed)] if proposed else [],
                             self._candidate_list(res))
            if decision == "REVIEW" and flag_change is not None:
                issue.quarantine_changes = flag_change(res)    # the reviewer's third option
        elif res.decision == "NO_MATCH":
            canon = canonical_code(stored)
            if flag_change is not None:
                self.add("counterfeit_signal", "RETAIN", res.p_none, db_id, table, pk_col, pk_val, column,
                         stored, None, "Null hypothesis of the linkage model",
                         res.explanation + " Quarantined as evidence; the code itself is left untouched.",
                         flag_change(res), self._candidate_list(res))
            elif stored and canon and stored != canon:
                self.add("format", "AUTO", 1.0, db_id, table, pk_col, pk_val, column, stored, canon,
                         "Deterministic canonicalisation (case, spacing, separators)",
                         f"Unregistered code, but its formatting still differs from the canonical '{canon}'. "
                         "Only the formatting is changed, so lookups such as the blacklist veto can find it.",
                         [Change(db_id, table, pk_col, pk_val, "UPDATE", column, stored, canon)])
            self.evidence.append({"db_id": db_id, "table": table, "key": pk_val, "code": stored,
                                  "p_none": round(res.p_none, 4)})
        self.links[(table, str(pk_val))] = effective
        return res, effective

    # -- per-silo checks --------------------------------------------------------

    def _date_fix(self, db_id, table, pk_col, pk_val, column, raw, with_time, uid, mode):
        if raw is None or raw == "" or is_canonical_datetime(raw, with_time):
            return
        parsed = parse_datetime(raw)
        if parsed.value is None:
            self.add("format", "REVIEW", 0.0, db_id, table, pk_col, pk_val, column, raw, None,
                     "Date parser", f"'{raw}' is not a date format this system recognises.")
            return
        chosen, confidence, how = parsed.value, 1.0, f"Reformatted from {parsed.fmt}"
        if parsed.ambiguous:
            options = [parsed.value] + parsed.alternatives
            fits = [d for d in options if self._date_fits(d, uid, mode)] if uid else []
            if len(fits) == 1:
                chosen, confidence = fits[0], 0.97
                how = (f"'{raw}' reads as {options[0]:%d %b %Y} or {options[1]:%d %b %Y}; only "
                       f"{fits[0]:%d %b %Y} fits the product's manufacture/arrival/expiry timeline")
            else:
                confidence = 0.85
                how = (f"'{raw}' is ambiguous and both readings fit the timeline; day-first chosen "
                       "(Indian locale convention)")
        new = parsed.iso(with_time=with_time, value=chosen)
        if new != raw:
            self.add("format", "AUTO" if confidence >= 0.85 else "REVIEW", confidence, db_id, table, pk_col,
                     pk_val, column, raw, new, "Date canonicalisation", how,
                     [Change(db_id, table, pk_col, pk_val, "UPDATE", column, raw, new)])

    def _date_fits(self, d: datetime, uid: str, mode: str) -> bool:
        p = self.ctx.products.get(uid)
        if not p:
            return True
        if p.get("mfg_dt") and d.date() < p["mfg_dt"].date():
            return False
        if mode != "complaint" and p.get("exp_dt") and d.date() > p["exp_dt"].date():
            return False
        if d > datetime.now():
            return False
        return True

    def _vendor_fix(self, db_id, table, pk_col, pk_val, column, raw):
        if raw in self.ctx.vendors or raw in self.vendor_aliases:
            return
        fixed = self.ctx.vendor_id(raw)
        if fixed:
            self.add("format", "AUTO", 1.0, db_id, table, pk_col, pk_val, column, raw, fixed,
                     "Vendor id canonicalisation", f"'{raw}' is '{fixed}' written differently.",
                     [Change(db_id, table, pk_col, pk_val, "UPDATE", column, raw, fixed)])
        else:
            self.add("conflict", "REVIEW", 0.0, db_id, table, pk_col, pk_val, column, raw, None,
                     "Referential integrity", f"Vendor '{raw}' does not exist in the DB1 vendor register.")

    def check_db1(self) -> None:
        for r in self.ctx.db1_events:
            pk = r["event_id"]
            already = int(r.get("anomaly_flag") or 0) == 1
            quarantined = QUARANTINE in str(r.get("anomaly_reason") or "")

            def flag(res, pk=pk, r=r):
                return [Change("db1", "purchase_events", "event_id", pk, "UPDATE", "anomaly_flag",
                               r.get("anomaly_flag"), 1),
                        Change("db1", "purchase_events", "event_id", pk, "UPDATE", "anomaly_reason",
                               r.get("anomaly_reason"),
                               f"{QUARANTINE}: code matches no registered product (p={res.p_none:.2f})")]

            if quarantined:                 # already decided: kept as counterfeit evidence
                uid = None
                self.links[("purchase_events", pk)] = None
            else:
                _, uid = self._identifier("db1", "purchase_events", "event_id", pk, "scan_code", r.get("scan_code"),
                                          self.matcher.record_from_db1(r), None if already else flag)
            self._date_fix("db1", "purchase_events", "event_id", pk, "scan_timestamp", r.get("scan_timestamp"),
                           True, uid, "sale")
            self._vendor_fix("db1", "purchase_events", "event_id", pk, "vendor_id", r.get("vendor_id"))
            cur = r.get("currency")
            norm = normalize_currency(cur)
            if norm != cur:
                cat = "missing_value" if not str(cur or "").strip() else "format"
                self.add(cat, "AUTO", 1.0, "db1", "purchase_events", "event_id", pk, "currency", cur, norm,
                         "Currency canonicalisation", f"'{cur}' is the Indian rupee; every vendor is in India.",
                         [Change("db1", "purchase_events", "event_id", pk, "UPDATE", "currency", cur, norm)])
            self._price_check(r, uid)

    def _price_check(self, r, uid) -> None:
        p = self.ctx.products.get(uid or "")
        try:
            price, qty = float(r.get("price_paid")), max(1, int(r.get("quantity_bought") or 1))
            mrp = float(p.get("msrp_kes")) if p and p.get("msrp_kes") else None
        except (TypeError, ValueError):
            return
        if not mrp:
            return
        ratio = price / qty / mrp
        for factor, what in ((100, "paise keyed as rupees"), (10, "an extra zero")):
            fixed_ratio = ratio / factor
            if 0.80 <= fixed_ratio <= 1.02:
                new = round(price / factor, 2)
                self.add("outlier", "AUTO", 0.92, "db1", "purchase_events", "event_id", r["event_id"],
                         "price_paid", price, new, f"Unit-error detection (x{factor})",
                         f"Unit price is {ratio:.1f}x the MRP of {uid} (Rs {mrp}); dividing by {factor} "
                         f"lands exactly within the MRP band, which is what {what} looks like.",
                         [Change("db1", "purchase_events", "event_id", r["event_id"], "UPDATE", "price_paid",
                                 r.get("price_paid"), new)])
                return

    def check_db2(self) -> None:
        for r in self.ctx.db2_batches:
            pk = r["batch_id"]
            quarantined = QUARANTINE in str(r.get("discrepancy_details") or "")

            def flag(res, pk=pk, r=r):
                return [Change("db2", "distribution_batches", "batch_id", pk, "UPDATE", "discrepancy_noted",
                               r.get("discrepancy_noted"), 1),
                        Change("db2", "distribution_batches", "batch_id", pk, "UPDATE", "discrepancy_details",
                               r.get("discrepancy_details"),
                               _append_note(r.get("discrepancy_details"),
                                            f"{QUARANTINE}: serial matches no registered product (p={res.p_none:.2f})"))]

            if quarantined:
                uid = None
                self.links[("distribution_batches", pk)] = None
            else:
                _, uid = self._identifier("db2", "distribution_batches", "batch_id", pk, "batch_serial",
                                          r.get("batch_serial"), self.matcher.record_from_db2(r), flag)
            for col in ("dispatch_date", "expected_arrival_date", "actual_arrival_date"):
                self._date_fix("db2", "distribution_batches", "batch_id", pk, col, r.get(col), False, uid, "dispatch")
            self._vendor_fix("db2", "distribution_batches", "batch_id", pk, "destination_vendor_id",
                             r.get("destination_vendor_id"))
            p = self.ctx.products.get(uid or "")
            ref = str(r.get("manufacturer_ref") or "").strip()
            if p:
                truth = p.get("manufacturer_id")
                if not ref:
                    self.add("missing_value", "AUTO", 0.99, "db2", "distribution_batches", "batch_id", pk,
                             "manufacturer_ref", r.get("manufacturer_ref"), truth, "Imputed from DB3 via the linked product",
                             f"Manufacturer missing; the shipped product {uid} is registered to {truth} in DB3.",
                             [Change("db2", "distribution_batches", "batch_id", pk, "UPDATE", "manufacturer_ref",
                                     r.get("manufacturer_ref"), truth)])
                elif ref.upper() != "UNKNOWN" and ref != truth:
                    self.add("conflict", "AUTO", 0.95, "db2", "distribution_batches", "batch_id", pk,
                             "manufacturer_ref", ref, truth, "Source authority: DB3 is the statutory registry",
                             f"DB2 says {ref}, DB3 says {uid} is made by {truth}. Who manufactured a product is a "
                             "registry fact, so DB3 wins and DB2 is corrected.",
                             [Change("db2", "distribution_batches", "batch_id", pk, "UPDATE", "manufacturer_ref",
                                     ref, truth)])
            shipped, received = r.get("quantity_shipped"), r.get("quantity_received")
            if (isinstance(shipped, int) and isinstance(received, int) and received > shipped
                    and DQ_FLAG not in str(r.get("discrepancy_details") or "")):
                note = f"{DQ_FLAG} received {received} exceeds shipped {shipped}; neither count can be trusted over the other"
                self.add("conflict", "AUTO", 1.0, "db2", "distribution_batches", "batch_id", pk,
                         "quantity_received", received, received, "Annotate, do not guess",
                         "More units received than were sent is impossible. Neither the dispatch count nor the "
                         "dock count outranks the other, so the record is flagged as a discrepancy rather than "
                         "silently overwritten.",
                         [Change("db2", "distribution_batches", "batch_id", pk, "UPDATE", "discrepancy_noted",
                                 r.get("discrepancy_noted"), 1),
                          Change("db2", "distribution_batches", "batch_id", pk, "UPDATE", "discrepancy_details",
                                 r.get("discrepancy_details"), _append_note(r.get("discrepancy_details"), note))])

    def check_db4(self) -> None:
        for r in self.ctx.db4_complaints:
            pk = r["complaint_id"]
            stored = r.get("complaint_item_ref")
            res, uid = self._identifier("db4", "complaints", "complaint_id", pk, "complaint_item_ref", stored,
                                        self.matcher.record_from_db4(r), None)
            if not str(stored or "").strip() and res.best_uid and res.decision in ("AUTO_LINK", "EXACT"):
                self.issues[-1:] = [i for i in self.issues[-1:] if i.pk_val != pk]
                self.add("missing_value", "AUTO", res.best_posterior or 1.0, "db4", "complaints", "complaint_id",
                         pk, "complaint_item_ref", stored, res.best_uid, "Extracted from complaint text, then linked",
                         " ".join(res.notes) + " " + res.explanation,
                         [Change("db4", "complaints", "complaint_id", pk, "UPDATE", "complaint_item_ref",
                                 stored, res.best_uid)], self._candidate_list(res))
                self.links[("complaints", pk)] = res.best_uid
                uid = res.best_uid
            self._date_fix("db4", "complaints", "complaint_id", pk, "complaint_date", r.get("complaint_date"),
                           True, uid, "complaint")
        for table, key, rows in (("lab_reports", "lab_report_id", self.ctx.db4_lab),
                                 ("ministry_blacklist", "blacklist_id", self.ctx.db4_blacklist),
                                 ("public_alerts", "alert_id", self.ctx.db4_alerts)):
            for r in rows:
                self._regulatory_ref("db4", table, key, r[key], "item_ref", r.get("item_ref"),
                                     self.matcher.record_from_ref(table, key, r))

    # -- duplicates -----------------------------------------------------------------

    def _uid(self, table: str, pk, raw) -> str:
        uid = self.links.get((table, str(pk)))
        return uid or self.ctx.resolve_alias(canonical_code(raw)) or ""

    def check_duplicates(self) -> None:
        groups: Dict[tuple, List[Dict[str, object]]] = defaultdict(list)
        for r in self.ctx.db1_events:
            vid = self.ctx.vendor_id(r.get("vendor_id")) or r.get("vendor_id")
            key = (self._uid("purchase_events", r["event_id"], r.get("scan_code")), vid,
                   round(float(r.get("price_paid") or 0), 2), r.get("quantity_bought"), r.get("device_id"))
            groups[key].append(r)
        for members in groups.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda r: (parse_datetime(r.get("scan_timestamp")).value or datetime.max, r["event_id"]))
            keep = members[0]
            for other in members[1:]:
                a = parse_datetime(keep.get("scan_timestamp")).value
                b = parse_datetime(other.get("scan_timestamp")).value
                if not a or not b:
                    continue
                gap = abs((b - a).total_seconds())
                if gap > 120:
                    keep = other
                    continue
                same = all(keep.get(c) == other.get(c) for c in ("payment_method", "customer_age_group"))
                self.add("duplicate_record", "AUTO" if gap <= 60 and same else "REVIEW",
                         0.97 if same else 0.75, "db1", "purchase_events", "event_id", other["event_id"],
                         "*", other.get("scan_code"), f"duplicate of {keep['event_id']}",
                         "Same product, terminal, price and quantity within two minutes",
                         f"{other['event_id']} repeats {keep['event_id']} {int(gap)} s later at the same till; "
                         "a POS retry, not a second sale.",
                         [Change("db1", "purchase_events", "event_id", other["event_id"], "DELETE")])

        self._near_duplicates(seen={i.pk_val for i in self.issues if i.category == "duplicate_record"})

        groups = defaultdict(list)
        for r in self.ctx.db2_batches:
            key = (self._uid("distribution_batches", r["batch_id"], r.get("batch_serial")), r.get("distributor_id"),
                   self.ctx.vendor_id(r.get("destination_vendor_id")) or r.get("destination_vendor_id"),
                   parse_datetime(r.get("dispatch_date")).iso(with_time=False), r.get("quantity_shipped"),
                   r.get("vehicle_reg"))
            groups[key].append(r)
        for members in groups.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda r: r["batch_id"])
            for other in members[1:]:
                self.add("duplicate_record", "AUTO", 0.98, "db2", "distribution_batches", "batch_id",
                         other["batch_id"], "*", other.get("batch_serial"), f"duplicate of {members[0]['batch_id']}",
                         "Same serial, carrier, destination, date, quantity and vehicle",
                         f"{other['batch_id']} is {members[0]['batch_id']} imported twice.",
                         [Change("db2", "distribution_batches", "batch_id", other["batch_id"], "DELETE")])

        # Complaints: same complainant within three days, and either the same product,
        # codes a small learned distance apart, or a later report that repeats the
        # earlier one's text. The last two catch a refiling whose code is too damaged
        # to resolve on its own.
        conf = self.matcher.model.confusion
        by_contact: Dict[str, List[Dict[str, object]]] = defaultdict(list)
        for r in self.ctx.db4_complaints:
            contact = "".join(ch for ch in str(r.get("complainant_contact") or "").lower() if ch.isalnum())
            if contact and r.get("complainant_type") != "auto_system":
                by_contact[contact].append(r)
        for members in by_contact.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda r: (parse_datetime(r.get("complaint_date")).value or datetime.max, r["complaint_id"]))
            closed = set()
            for i, keep in enumerate(members):
                if keep["complaint_id"] in closed:
                    continue
                for other in members[i + 1:]:
                    if other["complaint_id"] in closed or DQ_FLAG in str(other.get("resolution_notes") or ""):
                        continue
                    a = parse_datetime(keep.get("complaint_date")).value
                    b = parse_datetime(other.get("complaint_date")).value
                    if not (a and b and abs((b - a).days) <= 3):
                        continue
                    ua = self._uid("complaints", keep["complaint_id"], keep.get("complaint_item_ref"))
                    ub = self._uid("complaints", other["complaint_id"], other.get("complaint_item_ref"))
                    ca = canonical_code(keep.get("complaint_item_ref"))
                    cb = canonical_code(other.get("complaint_item_ref"))
                    earlier = str(keep.get("description") or "").strip()
                    if ua and ua == ub:
                        why = "the same product"
                    elif ca and cb and conf.distance(cb, ca) <= 2.2:
                        why = f"nearly the same code ('{keep.get('complaint_item_ref')}' / '{other.get('complaint_item_ref')}')"
                    elif len(earlier) > 30 and earlier in str(other.get("description") or ""):
                        why = "a repeat of the earlier report's own words"
                    else:
                        continue
                    closed.add(other["complaint_id"])
                    note = f"{DQ_FLAG} duplicate of {keep['complaint_id']}"
                    self.add("duplicate_record", "AUTO", 0.93, "db4", "complaints", "complaint_id",
                             other["complaint_id"], "status", other.get("status"), "closed",
                             "Same complainant within three days, about the same product",
                             f"{other['complaint_id']} is the same person filing again about {why} as "
                             f"{keep['complaint_id']}. Closed as a duplicate rather than deleted: a citizen's "
                             "report is never erased.",
                             [Change("db4", "complaints", "complaint_id", other["complaint_id"], "UPDATE", "status",
                                     other.get("status"), "closed"),
                              Change("db4", "complaints", "complaint_id", other["complaint_id"], "UPDATE",
                                     "resolution_notes", other.get("resolution_notes"), note),
                              Change("db4", "complaints", "complaint_id", other["complaint_id"], "UPDATE",
                                     "action_taken", other.get("action_taken"), "case_dismissed")])

    def _near_duplicates(self, seen: set) -> None:
        """
        A POS retry that was re-keyed by hand carries a typo, so its code may not
        resolve and the exact grouping above never pairs it with the original. The
        neighbouring record is itself the evidence: same till, same price and
        quantity, seconds apart, and a code a small learned distance from the
        original's. Such a row is a duplicate whatever its typo resolves to.
        """
        conf = self.matcher.model.confusion
        groups: Dict[tuple, List[Dict[str, object]]] = defaultdict(list)
        for r in self.ctx.db1_events:
            vid = self.ctx.vendor_id(r.get("vendor_id")) or r.get("vendor_id")
            groups[(vid, r.get("device_id"), round(float(r.get("price_paid") or 0), 2),
                    r.get("quantity_bought"))].append(r)
        for members in groups.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda r: (parse_datetime(r.get("scan_timestamp")).value or datetime.max, r["event_id"]))
            for a, b in zip(members, members[1:]):
                if b["event_id"] in seen or a["event_id"] in seen:
                    continue
                ta = parse_datetime(a.get("scan_timestamp")).value
                tb = parse_datetime(b.get("scan_timestamp")).value
                if not ta or not tb or abs((tb - ta).total_seconds()) > 60:
                    continue
                ca, cb = canonical_code(a.get("scan_code")), canonical_code(b.get("scan_code"))
                if ca == cb:
                    continue
                d = conf.distance(cb, ca)
                if d > 2.2:
                    continue
                # keep the record whose code is registered; drop the damaged copy
                keep, drop = (a, b) if self.ctx.resolve_alias(ca) in self.ctx.products else (b, a)
                gap = int(abs((tb - ta).total_seconds()))
                same = all(a.get(c) == b.get(c) for c in ("payment_method", "customer_age_group"))
                self.add("duplicate_record", "AUTO" if same and d <= 1.2 else "REVIEW", 0.95 if same else 0.7,
                         "db1", "purchase_events", "event_id", drop["event_id"], "*", drop.get("scan_code"),
                         f"duplicate of {keep['event_id']}",
                         "Same till, price and quantity within a minute; code a small learned distance apart",
                         f"{drop['event_id']} ('{drop.get('scan_code')}') repeats {keep['event_id']} "
                         f"('{keep.get('scan_code')}') {gap} s later at the same till. The second code is a damaged "
                         f"copy of the first (distance {d:.2f}), so this is a re-keyed retry, not a second sale.",
                         [Change("db1", "purchase_events", "event_id", drop["event_id"], "DELETE")])
                seen.add(drop["event_id"])

    # -- run ------------------------------------------------------------------------

    def run(self) -> List[Issue]:
        self.check_db2()
        self.check_db1()
        self.check_db4()
        self.check_duplicates()
        dismissed = _dismissed()
        truth = _load_truth()
        seen = set()
        unique = []
        for i in self.issues:
            if i.issue_id in seen:
                continue
            seen.add(i.issue_id)
            if i.issue_id in dismissed and dismissed[i.issue_id].get("decision") == "REJECTED":
                i.decision = "DISMISSED"
            t = truth.get(f"{i.db_id}:{i.table}:{i.pk_val}")
            if t:
                i.truth = t.get("true_uid") or t.get("label")
            unique.append(i)
        self.issues = unique
        return unique


def duplicate_aliases(ctx: LiveContext) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Product and vendor alias maps (duplicate -> survivor), as a scan would compute them."""
    return Scanner.product_duplicates(ctx)[0], Scanner.vendor_duplicates(ctx)[0]


_ALIAS_CACHE: Dict[str, object] = {"stamp": None, "aliases": ({}, {})}


def live_matcher() -> Matcher:
    """
    The matcher the endpoints use: duplicate products and pharmacies resolve to
    their survivor, so a single query sees the registry the way a scan does.
    """
    base = get_context()
    if _ALIAS_CACHE["stamp"] != base.stamp:
        _ALIAS_CACHE.update(stamp=base.stamp, aliases=duplicate_aliases(base))
    products, vendors = _ALIAS_CACHE["aliases"]
    return get_matcher(products, vendors)


def _summary(issues: List[Issue]) -> Dict[str, object]:
    by_cat: Dict[str, Dict[str, int]] = {}
    for c in CATEGORY_INFO:
        by_cat[c] = {"AUTO": 0, "REVIEW": 0, "RETAIN": 0, "DISMISSED": 0}
    for i in issues:
        by_cat[i.category][i.decision] += 1
    open_count = sum(1 for i in issues if i.decision in ("AUTO", "REVIEW", "RETAIN"))
    return {"total_open": open_count,
            "auto": sum(1 for i in issues if i.decision == "AUTO"),
            "review": sum(1 for i in issues if i.decision == "REVIEW"),
            "retain": sum(1 for i in issues if i.decision == "RETAIN"),
            "dismissed": sum(1 for i in issues if i.decision == "DISMISSED"),
            "by_category": by_cat,
            "categories": {k: {"label": v[0], "description": v[1]} for k, v in CATEGORY_INFO.items()}}


def _accuracy(issues: List[Issue]) -> Dict[str, object]:
    """How the proposed identifier fixes compare with the generator's ground truth."""
    rows = [i for i in issues if i.truth is not None and i.category in
            ("noisy_identifier", "valid_but_wrong", "counterfeit_signal")]
    if not rows:
        return {"available": False}
    out = {"available": True}
    for decision in ("AUTO", "REVIEW", "RETAIN"):
        sel = [i for i in rows if i.decision == decision]
        if decision == "RETAIN":
            correct = sum(1 for i in sel if i.truth == "COUNTERFEIT")
        else:
            correct = sum(1 for i in sel if i.proposed == i.truth)
        out[decision.lower()] = {"n": len(sel), "correct": correct,
                                 "precision": round(correct / len(sel), 4) if sel else None}
    return out


def scan(include_issues: bool = True) -> Dict[str, object]:
    t0 = time.perf_counter()
    scanner = Scanner()
    issues = scanner.run()
    res = {"scanned_at": datetime.now().isoformat(timespec="seconds"),
           "records_scanned": {"db1_purchase_events": len(scanner.ctx.db1_events),
                               "db2_distribution_batches": len(scanner.ctx.db2_batches),
                               "db3_products": len(scanner.ctx.all_products),
                               "db4_complaints": len(scanner.ctx.db4_complaints),
                               "db1_vendors": len(scanner.ctx.vendors)},
           "summary": _summary(issues),
           "accuracy_vs_ground_truth": _accuracy(issues),
           "evidence_retained": len(scanner.evidence),
           "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}
    if include_issues:
        res["issues"] = [i.to_dict() for i in issues]
    return res


# -- apply / undo ---------------------------------------------------------------

_ORDER = {"master_duplicate": 0, "format": 1, "noisy_identifier": 2, "valid_but_wrong": 2,
          "missing_value": 3, "conflict": 3, "outlier": 3, "counterfeit_signal": 4, "duplicate_record": 5}


def _connections() -> Dict[str, sqlite3.Connection]:
    conns = {}
    for d in ("db1", "db2", "db3", "db4"):
        if os.path.exists(paths.db_path(d)):
            conns[d] = sqlite3.connect(paths.db_path(d))
            conns[d].row_factory = sqlite3.Row
    return conns


def _apply_change(conns, dq, run_id, seq, issue: Issue, ch: Change) -> bool:
    conn = conns.get(ch.db_id)
    if conn is None:
        return False
    now = datetime.now().isoformat(timespec="seconds")
    snapshot = None
    if ch.action == "UPDATE":
        cur = conn.execute(f"SELECT {ch.column} FROM {ch.table} WHERE {ch.pk_col} = ?", (ch.pk_val,)).fetchone()
        if cur is None:
            return False
        old = cur[0]
        conn.execute(f"UPDATE {ch.table} SET {ch.column} = ? WHERE {ch.pk_col} = ?", (ch.new, ch.pk_val))
        old_value, new_value = old, ch.new
    elif ch.action == "DELETE":
        row = conn.execute(f"SELECT * FROM {ch.table} WHERE {ch.pk_col} = ?", (ch.pk_val,)).fetchone()
        if row is None:
            return False
        snapshot = json.dumps(dict(row), default=str)
        conn.execute(f"DELETE FROM {ch.table} WHERE {ch.pk_col} = ?", (ch.pk_val,))
        old_value, new_value = None, None
    else:
        return False
    dq.execute("""INSERT INTO dq_actions (run_id, seq, issue_id, category, decision, db_id, table_name, pk_col,
                  pk_val, action, column_name, old_value, new_value, row_snapshot, confidence, method,
                  explanation, applied_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (run_id, seq, issue.issue_id, issue.category, issue.decision, ch.db_id, ch.table, ch.pk_col,
                ch.pk_val, ch.action, ch.column, None if old_value is None else json.dumps(old_value),
                None if new_value is None else json.dumps(new_value), snapshot, issue.confidence,
                issue.method, issue.explanation[:500], now))
    return True


def apply(mode: str = "auto", issue_ids: Optional[Iterable[str]] = None,
          overrides: Optional[Dict[str, str]] = None, actor: str = "dashboard",
          quarantine_ids: Optional[Iterable[str]] = None, max_passes: int = 3,
          run_id: Optional[str] = None) -> Dict[str, object]:
    """
    mode='auto'      apply every AUTO and RETAIN issue, rescanning until nothing
                     automatic is left (a fixed code can reveal a duplicate, a
                     linked shipment can reveal a manufacturer conflict)
    mode='selected'  apply only the given issue ids (a reviewer accepting items)
    overrides        {issue_id: uid} lets a reviewer pick a different candidate
    quarantine_ids   review items the reviewer judged counterfeit: flagged, not relinked
    run_id           given when the other node replays this run on its copy, so
                     both copies carry the same id and either can undo it
    """
    t0 = time.perf_counter()
    run_id = run_id or "DQ-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:22]
    totals = {"issues": 0, "changes": 0, "skipped": 0, "passes": 0}
    by_cat: Counter = Counter()
    touched: set = set()
    first_issues: List[Issue] = []
    seq = [0]
    for _ in range(max_passes if mode == "auto" else 1):
        issues = Scanner().run()
        if not first_issues:
            first_issues = issues
        chosen = _select(issues, mode, issue_ids, overrides, quarantine_ids)
        if not chosen:
            break
        totals["passes"] += 1
        _apply_issues(run_id, chosen, mode, actor, totals, by_cat, touched, seq)
        if mode != "auto":
            break
    if totals["issues"]:
        dq = _dq_conn()
        dq.execute("INSERT INTO dq_runs VALUES (?,?,?,?,?,?,?,NULL)",
                   (run_id, datetime.now().isoformat(timespec="seconds"), mode, actor, totals["issues"],
                    totals["changes"], json.dumps({"by_category": dict(by_cat), "touched": sorted(touched),
                                                   "passes": totals["passes"]})))
        dq.commit()
        dq.close()
    if "db1" in touched:
        sync_nosql_mirror()
    after = scan(include_issues=False)
    return {"success": True, "run_id": run_id if totals["issues"] else None, "mode": mode,
            "issues_applied": totals["issues"], "changes_applied": totals["changes"],
            "changes_skipped": totals["skipped"], "passes": totals["passes"], "by_category": dict(by_cat),
            "after": after["summary"], "accuracy_before_apply": _accuracy(first_issues),
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}


def _select(issues: List[Issue], mode: str, issue_ids, overrides, quarantine_ids) -> List[Issue]:
    wanted = set(issue_ids or [])
    quarantine = set(quarantine_ids or [])
    overrides = overrides or {}
    if mode == "auto":
        chosen = [i for i in issues if i.decision in ("AUTO", "RETAIN")]
    else:
        chosen = [i for i in issues
                  if (i.issue_id in wanted or i.issue_id in quarantine) and i.decision != "DISMISSED"]
    for i in chosen:
        if i.issue_id in quarantine and i.quarantine_changes:
            i.changes = i.quarantine_changes
            i.category, i.proposed = "counterfeit_signal", None
            i.method += " (reviewer judged counterfeit)"
            continue
        uid = overrides.get(i.issue_id)
        if uid and i.category in ("noisy_identifier", "valid_but_wrong", "format"):
            i.proposed = uid
            i.changes = [Change(i.db_id, i.table, i.pk_col, i.pk_val, "UPDATE", i.column, i.current, uid)]
            i.method += " (reviewer chose candidate)"
            i.confidence = 1.0
    chosen.sort(key=lambda i: _ORDER.get(i.category, 9))
    return chosen


def _apply_issues(run_id, chosen, mode, actor, totals, by_cat, touched, seq_box) -> None:
    conns = _connections()
    dq = _dq_conn()
    deleted = set()
    try:
        for issue in chosen:
            ok_any = False
            for ch in issue.changes:
                if (ch.db_id, ch.table, ch.pk_val) in deleted:
                    continue
                seq_box[0] += 1
                if _apply_change(conns, dq, run_id, seq_box[0], issue, ch):
                    ok_any = True
                    totals["changes"] += 1
                    touched.add(ch.db_id)
                    if ch.action == "DELETE":
                        deleted.add((ch.db_id, ch.table, ch.pk_val))
                else:
                    totals["skipped"] += 1
            if ok_any:
                totals["issues"] += 1
                by_cat[issue.category] += 1
            if mode != "auto":
                verdict = "QUARANTINED" if issue.category == "counterfeit_signal" else "ACCEPTED"
                dq.execute("INSERT OR REPLACE INTO dq_decisions VALUES (?,?,?,?,?)",
                           (issue.issue_id, verdict, str(issue.proposed), datetime.now().isoformat(), actor))
        for c in conns.values():
            c.commit()
        dq.commit()
    except Exception:
        for c in conns.values():
            c.rollback()
        dq.rollback()
        raise
    finally:
        for c in conns.values():
            c.close()
        dq.close()


def undo(run_id: str) -> Dict[str, object]:
    dq = _dq_conn()
    run = dq.execute("SELECT * FROM dq_runs WHERE run_id = ?", (run_id,)).fetchone()
    if run is None:
        dq.close()
        return {"success": False, "error": f"No cleansing run '{run_id}'."}
    if run["undone_at"]:
        dq.close()
        return {"success": False, "error": f"Run '{run_id}' was already undone at {run['undone_at']}."}
    actions = dq.execute("SELECT * FROM dq_actions WHERE run_id = ? ORDER BY seq DESC", (run_id,)).fetchall()
    # Reverting a run under a later one that changed the same rows would silently
    # overwrite the later change, so the later run has to be undone first.
    rows = {(a["db_id"], a["table_name"], a["pk_val"]) for a in actions}
    for later in dq.execute("SELECT run_id FROM dq_runs WHERE started_at >= ? AND run_id != ? AND undone_at IS NULL",
                            (run["started_at"], run_id)).fetchall():
        hit = dq.execute("SELECT db_id, table_name, pk_val FROM dq_actions WHERE run_id = ?", (later["run_id"],)).fetchall()
        if any((h["db_id"], h["table_name"], h["pk_val"]) in rows for h in hit):
            dq.close()
            return {"success": False, "error": f"Run '{later['run_id']}' changed some of the same rows after "
                                               f"'{run_id}'. Undo it first."}
    conns = _connections()
    restored = 0
    touched = set()
    try:
        for a in actions:
            conn = conns.get(a["db_id"])
            if conn is None:
                continue
            if a["action"] == "UPDATE":
                old = None if a["old_value"] is None else json.loads(a["old_value"])
                conn.execute(f"UPDATE {a['table_name']} SET {a['column_name']} = ? WHERE {a['pk_col']} = ?",
                             (old, a["pk_val"]))
            elif a["action"] == "DELETE" and a["row_snapshot"]:
                row = json.loads(a["row_snapshot"])
                cols = list(row)
                conn.execute(f"INSERT OR REPLACE INTO {a['table_name']} ({', '.join(cols)}) "
                             f"VALUES ({', '.join('?' * len(cols))})", [row[c] for c in cols])
            restored += 1
            touched.add(a["db_id"])
        for c in conns.values():
            c.commit()
        dq.execute("UPDATE dq_runs SET undone_at = ? WHERE run_id = ?",
                   (datetime.now().isoformat(timespec="seconds"), run_id))
        dq.execute("DELETE FROM dq_decisions WHERE issue_id IN (SELECT issue_id FROM dq_actions WHERE run_id = ?)",
                   (run_id,))
        dq.commit()
    finally:
        for c in conns.values():
            c.close()
        dq.close()
    if "db1" in touched:
        sync_nosql_mirror()
    return {"success": True, "run_id": run_id, "actions_reverted": restored}


def decide(issue_id: str, decision: str, uid: Optional[str] = None, note: str = "",
           run_id: Optional[str] = None) -> Dict[str, object]:
    """A reviewer's verdict on one REVIEW item: accept (optionally another candidate), quarantine
    it as counterfeit evidence, or reject the suggestion and keep the record as it is."""
    decision = decision.upper()
    if decision in ("ACCEPT", "ACCEPTED"):
        return apply(mode="selected", issue_ids=[issue_id], overrides={issue_id: uid} if uid else None,
                     actor="reviewer", run_id=run_id)
    if decision in ("QUARANTINE", "COUNTERFEIT"):
        return apply(mode="selected", quarantine_ids=[issue_id], actor="reviewer", run_id=run_id)
    if decision in ("REJECT", "REJECTED", "KEEP"):
        dq = _dq_conn()
        dq.execute("INSERT OR REPLACE INTO dq_decisions VALUES (?,?,?,?,?)",
                   (issue_id, "REJECTED", None, datetime.now().isoformat(), note or "kept as recorded"))
        dq.commit()
        dq.close()
        return {"success": True, "issue_id": issue_id, "decision": "REJECTED"}
    return {"success": False, "error": f"Unknown decision '{decision}'."}


def lineage(limit: int = 50) -> Dict[str, object]:
    if not os.path.exists(paths.db_path("dq")):
        return {"runs": [], "actions": []}
    dq = _dq_conn()
    try:
        runs = [dict(r) for r in dq.execute("SELECT * FROM dq_runs ORDER BY started_at DESC LIMIT 20")]
        for r in runs:
            r["summary"] = json.loads(r.pop("summary_json") or "{}")
        actions = [dict(r) for r in dq.execute(
            "SELECT action_id, run_id, category, decision, db_id, table_name, pk_val, action, column_name, "
            "old_value, new_value, confidence, method, applied_at FROM dq_actions ORDER BY action_id DESC LIMIT ?",
            (limit,))]
        return {"runs": runs, "actions": actions}
    finally:
        dq.close()


def sync_nosql_mirror() -> int:
    """Rebuild the DB1 document collection from the SQLite rows it mirrors."""
    try:
        from data.seed_nosql_db1 import sync_collection
    except ImportError:
        return 0
    return sync_collection(paths.db_path("db1"), paths.nosql_file())


def assess_row(db_id: str, table: str, row: Dict[str, object]) -> Optional[Dict[str, object]]:
    """Inline quality gate for a single written row: how would the matcher read it?"""
    m = live_matcher()
    if db_id == "db1" and table == "purchase_events":
        rec = m.record_from_db1(row)
    elif db_id == "db2" and table == "distribution_batches":
        rec = m.record_from_db2(row)
    elif db_id == "db4" and table == "complaints":
        rec = m.record_from_db4(row)
    else:
        return None
    if not rec.get("code") and db_id != "db4":
        return None
    res = m.match(rec, limit=4)
    return {"decision": res.decision, "code": res.code, "best_uid": res.best_uid,
            "posterior": round(res.best_posterior, 4), "p_none": round(res.p_none, 4),
            "explanation": res.explanation,
            "candidates": [{"uid": c.uid, "posterior": round(c.posterior, 4),
                            "product_name": c.product_name} for c in res.candidates[:3]],
            "next_step": "Open Uncertainty → Cleansing and run a scan to apply or review this record."}
