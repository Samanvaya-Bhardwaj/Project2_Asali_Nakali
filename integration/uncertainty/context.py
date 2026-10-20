"""
context.py
----------
A read-only snapshot of the four silos, shaped for matching.

A noisy code on its own says little. What makes one candidate more believable
than another is everything else the silos know: whether that product was ever
shipped to the pharmacy that sold it, whether the price fits its MRP, whether
the sale falls between its manufacture and expiry dates, whether the label on
the pack names the same brand. This module gathers that evidence once.

The snapshot is cached and rebuilt automatically whenever any silo file changes,
so a row inserted, edited or deleted through the explorer is visible to the very
next match.
"""

from __future__ import annotations
import os
import sqlite3
import threading
from collections import defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set

from . import paths
from .standardize import (brand_key, canonical_code, license_key, name_tokens,
                          normalize_vendor_id, strength_key, to_date)

# Characters a reader confuses are folded together for blocking only.
_FOLD = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1",
                       "S": "5", "B": "8", "Z": "2", "G": "6"})


def fold(code: str) -> str:
    return (code or "").translate(_FOLD)


def bigrams(s: str) -> Set[str]:
    p = f"#{s}#"
    return {p[i:i + 2] for i in range(len(p) - 1)}


def _rows(db_id: str, sql: str, params: Iterable = ()) -> List[Dict[str, object]]:
    path = paths.db_path(db_id)
    if not os.path.exists(path):
        return []
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


class LiveContext:
    """Everything the matcher may use as evidence, read from the live silos."""

    def __init__(self, aliases: Optional[Dict[str, str]] = None,
                 vendor_aliases: Optional[Dict[str, str]] = None):
        self.stamp = paths.stamp("db1", "db2", "db3", "db4")
        self.built_at = datetime.now().isoformat(timespec="seconds")
        self.aliases: Dict[str, str] = dict(aliases or {})
        self.vendor_aliases: Dict[str, str] = dict(vendor_aliases or {})
        self._load_products()
        self._load_parties()
        self._load_records()
        self._build_blocking_index()
        self._build_sales_index()
        self._build_custody(exact_only=True)
        self.db2_links: Dict[str, Dict[str, object]] = {}
        self.custody_complete = False

    # -- products ---------------------------------------------------------------

    def _load_products(self) -> None:
        rows = _rows("db3", """
            SELECT p.*, m.company_name AS manufacturer_name
            FROM products p LEFT JOIN manufacturers m ON p.manufacturer_id = m.manufacturer_id
        """)
        self.all_products: Dict[str, Dict[str, object]] = {}
        for r in rows:
            r["brand"] = brand_key(r.get("product_name"))
            r["strength_key"] = strength_key(r.get("strength"))
            r["mfg_dt"] = to_date(r.get("manufacture_date"))
            r["exp_dt"] = to_date(r.get("expiry_date"))
            r["batch_key"] = canonical_code(r.get("batch_number"))
            self.all_products[r["product_uid"]] = r
        # Aliased duplicates resolve to their survivor and drop out as candidates.
        self.products = {u: p for u, p in self.all_products.items() if u not in self.aliases}
        self.brands = sorted({p["brand"] for p in self.products.values() if p["brand"]})

    def resolve_alias(self, uid: Optional[str]) -> Optional[str]:
        seen = set()
        while uid in self.aliases and uid not in seen:
            seen.add(uid)
            uid = self.aliases[uid]
        return uid

    def product(self, uid: Optional[str]) -> Optional[Dict[str, object]]:
        uid = self.resolve_alias(uid)
        return self.products.get(uid) if uid else None

    # -- vendors, distributors, authorisations -----------------------------------

    def _load_parties(self) -> None:
        self.vendors = {r["vendor_id"]: r for r in _rows("db1", "SELECT * FROM vendors")}
        for v in self.vendors.values():
            v["city"] = v.get("location_county")
            v["license_key"] = license_key(v.get("license_no"))
            v["tokens"] = set(name_tokens(v.get("vendor_name")))
        self.distributors = {r["distributor_id"]: r for r in _rows("db2", "SELECT * FROM distributors")}
        self.authorized: Dict[str, Set[str]] = defaultdict(set)
        for r in _rows("db3", "SELECT * FROM authorized_distributors"):
            if r.get("active", 1):
                self.authorized[r["manufacturer_id"]].add(r["distributor_ref"])
        self.manufacturers = {r["manufacturer_id"]: r for r in _rows("db3", "SELECT * FROM manufacturers")}

    def vendor_id(self, raw) -> Optional[str]:
        vid = normalize_vendor_id(raw, self.vendors.keys())
        return self.vendor_aliases.get(vid, vid) if vid else None

    def city_of(self, vendor_id: Optional[str]) -> Optional[str]:
        v = self.vendors.get(vendor_id or "")
        return v.get("city") if v else None

    # -- the noisy records --------------------------------------------------------

    def _load_records(self) -> None:
        self.db1_events = _rows("db1", "SELECT * FROM purchase_events ORDER BY event_id")
        self.db2_batches = _rows("db2", "SELECT * FROM distribution_batches ORDER BY batch_id")
        self.db4_complaints = _rows("db4", "SELECT * FROM complaints ORDER BY complaint_id")
        self.db4_lab = _rows("db4", "SELECT * FROM lab_reports ORDER BY lab_report_id")
        self.db4_blacklist = _rows("db4", "SELECT * FROM ministry_blacklist ORDER BY blacklist_id")
        self.db4_alerts = _rows("db4", "SELECT * FROM public_alerts ORDER BY alert_id")

    # -- blocking -----------------------------------------------------------------

    def _build_blocking_index(self) -> None:
        self.index: Dict[str, Set[str]] = defaultdict(set)
        self.grams: Dict[str, Set[str]] = {}
        for uid in self.products:
            g = bigrams(fold(uid))
            self.grams[uid] = g
            for gram in g:
                self.index[gram].add(uid)

    def block(self, code: str, limit: int = 30) -> List[str]:
        """
        Candidate generation. Comparing every record with every product is
        quadratic; instead keep the products that share enough folded bigrams with
        the query. Folding first means an O/0 or B/8 misread does not cost the
        true product its place in the block.
        """
        if not code:
            return []
        q = bigrams(fold(code))
        counts: Dict[str, int] = defaultdict(int)
        for gram in q:
            for uid in self.index.get(gram, ()):
                counts[uid] += 1
        if not counts:
            return []
        floor = max(3, int(0.35 * len(q)))
        ranked = sorted((u for u, c in counts.items() if c >= floor),
                        key=lambda u: (-counts[u], u))
        return ranked[:limit]

    # -- where each product was later sold (DB1 -> evidence for DB2) -----------------

    def _build_sales_index(self) -> None:
        """
        Pharmacies at which each product was scanned by barcode or QR with an
        exactly registered code. A shipment record with a damaged serial is most
        likely the batch that was later sold at its destination. Only scanner reads
        are used, so this evidence never depends on another fuzzy link.
        """
        self.sold_at: Dict[str, Set[str]] = defaultdict(set)
        for e in self.db1_events:
            if str(e.get("scan_method") or "").lower() not in ("barcode", "qrcode", "nfc"):
                continue
            uid = self.resolve_alias(canonical_code(e.get("scan_code")))
            vid = self.vendor_id(e.get("vendor_id"))
            if uid in self.products and vid:
                self.sold_at[uid].add(vid)

    # -- custody: which product reached which pharmacy -----------------------------

    def _build_custody(self, exact_only: bool) -> None:
        self.custody: Dict[str, Dict[str, datetime]] = defaultdict(dict)
        self.custody_cities: Dict[str, Set[str]] = defaultdict(set)
        for b in self.db2_batches:
            uid = self._db2_uid(b, exact_only)
            if not uid:
                continue
            vid = self.vendor_id(b.get("destination_vendor_id")) or b.get("destination_vendor_id")
            arrived = to_date(b.get("actual_arrival_date")) or to_date(b.get("dispatch_date"))
            if vid:
                prior = self.custody[uid].get(vid)
                if prior is None or (arrived and arrived < prior):
                    self.custody[uid][vid] = arrived or datetime(1970, 1, 1)
                city = self.city_of(vid)
                if city:
                    self.custody_cities[uid].add(city)

    def _db2_uid(self, batch: Dict[str, object], exact_only: bool) -> Optional[str]:
        code = self.resolve_alias(canonical_code(batch.get("batch_serial")))
        if code in self.products:
            return code
        if exact_only:
            return None
        link = self.db2_links.get(batch.get("batch_id"))
        if link and link.get("decision") in ("AUTO_LINK", "EXACT"):
            return link.get("uid")
        return None

    def complete_custody(self, matcher) -> None:
        """
        Second pass: noisy DB2 serials are linked with DB2's own evidence
        (manufacturer, distributor authorisation, dates), and only confident links
        are allowed to contribute custody evidence for DB1.
        """
        if self.custody_complete:
            return
        for b in self.db2_batches:
            code = self.resolve_alias(canonical_code(b.get("batch_serial")))
            if code in self.products:
                continue
            res = matcher.match(matcher.record_from_db2(b))
            self.db2_links[b["batch_id"]] = {"uid": res.best_uid, "decision": res.decision,
                                             "posterior": res.best_posterior}
        self._build_custody(exact_only=False)
        self.custody_complete = True

    def shipped_to(self, uid: str) -> Dict[str, datetime]:
        return self.custody.get(uid, {})


_LOCK = threading.Lock()
_CACHE: Dict[str, LiveContext] = {}


def get_context(aliases: Optional[Dict[str, str]] = None,
                vendor_aliases: Optional[Dict[str, str]] = None,
                force: bool = False) -> LiveContext:
    """Cached snapshot, rebuilt when any silo file has changed since it was taken."""
    key = repr((sorted((aliases or {}).items()), sorted((vendor_aliases or {}).items())))
    with _LOCK:
        ctx = _CACHE.get(key)
        if force or ctx is None or ctx.stamp != paths.stamp("db1", "db2", "db3", "db4"):
            if len(_CACHE) > 4:
                _CACHE.clear()
            ctx = LiveContext(aliases, vendor_aliases)
            _CACHE[key] = ctx
        return ctx
