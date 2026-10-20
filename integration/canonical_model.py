#!/usr/bin/env python3
"""
canonical_model.py
------------------
Unified Item View  -  GlobalItemHistory (GPT audit recommendation).

The assignment requires a "complete history (view) of this item."
This module implements the formal canonical object that represents
a complete federated view of all 4 database records merged into
a single, provenance-aware structure.

In GAV (Global-as-View) integration theory, this is the "global schema"
that the mediator exposes  -  a virtual view that users query without
knowing anything about the 4 underlying heterogeneous sources.

Structure of GlobalItemHistory:
  +-------------------------------------------------+
  |           GlobalItemHistory                     |
  |  +-------------+  +--------------------------+  |
  |  |  Identity   |  |   Supply Chain Trail     |  |
  |  |  (DB3)      |  |   (DB2 -> DB1)            |  |
  |  +-------------+  +--------------------------+  |
  |  +-------------+  +--------------------------+  |
  |  |  Regulatory |  |   Provenance Log          |  |
  |  |  (DB4)      |  |   (source-tagged items)  |  |
  |  +-------------+  +--------------------------+  |
  +-------------------------------------------------+

Key design: every field is tagged with its source DB and the
original column name used to fetch it. This enables full provenance.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Any

from integration.resolver import ItemRecord


# --- Provenance-tagged field --------------------------------------------------

@dataclass
class ProvenanceField:
    """A data value tagged with its source for full auditability."""
    value:       Any
    source_db:   str   # e.g. "DB3  -  Manufacturer Registry"
    column_name: str   # original column name in that DB
    table_name:  str   # original table name


# --- Timeline event -----------------------------------------------------------

@dataclass
class SupplyChainEvent:
    """One node in the supply chain provenance timeline."""
    stage:      str        # MANUFACTURED / DISPATCHED / DELIVERED / SOLD / FLAGGED
    timestamp:  Optional[str]
    actor:      str        # company/vendor name
    actor_id:   str        # DB-specific ID
    location:   str
    status:     str        # OK / WARNING / BREAK
    source_db:  str
    details:    dict = field(default_factory=dict)


# --- Contradiction ------------------------------------------------------------

@dataclass
class DataContradiction:
    """A logical inconsistency detected across two or more DBs."""
    contradiction_type:  str    # TEMPORAL / IDENTITY / QUANTITY / STATUS
    description:         str
    source_a:            str    # first DB making a claim
    value_a:             Any
    source_b:            str    # second DB making conflicting claim
    value_b:             Any
    severity:            str    # HIGH / MEDIUM / LOW


# --- Canonical Global Item History --------------------------------------------

@dataclass
class GlobalItemHistory:
    """
    The unified virtual view of a medicine item across all 4 databases.
    This is the canonical model that the decision engine operates on.
    """
    # -- Identity (primarily from DB3) -------------------------------------
    item_code:           str
    product_name:        Optional[ProvenanceField] = None
    generic_name:        Optional[ProvenanceField] = None
    manufacturer_name:   Optional[ProvenanceField] = None
    cdsco_license_no:    Optional[ProvenanceField] = None
    batch_no:            Optional[ProvenanceField] = None
    manufacture_date:    Optional[ProvenanceField] = None
    expiry_date:         Optional[ProvenanceField] = None
    strength:            Optional[ProvenanceField] = None
    dosage_form:         Optional[ProvenanceField] = None
    mrp_inr:             Optional[ProvenanceField] = None  # Max Retail Price
    is_recalled:         Optional[ProvenanceField] = None
    requires_cold_chain: Optional[ProvenanceField] = None

    # -- Supply Chain (from DB2) -------------------------------------------
    distributor_name:    Optional[ProvenanceField] = None
    distributor_license: Optional[ProvenanceField] = None
    authorized_route:    Optional[ProvenanceField] = None
    dispatch_date:       Optional[ProvenanceField] = None
    delivery_date:       Optional[ProvenanceField] = None
    cold_chain_ok:       Optional[ProvenanceField] = None
    target_vendor_id:    Optional[ProvenanceField] = None

    # -- Retail (from DB1) -------------------------------------------------
    vendor_name:         Optional[ProvenanceField] = None
    vendor_license:      Optional[ProvenanceField] = None
    purchase_date:       Optional[ProvenanceField] = None
    price_paid_inr:      Optional[ProvenanceField] = None
    vendor_location:     Optional[ProvenanceField] = None

    # -- Regulatory (from DB4) ---------------------------------------------
    blacklisted:         Optional[ProvenanceField] = None
    complaint_count:     Optional[ProvenanceField] = None
    lab_result:          Optional[ProvenanceField] = None
    gazette_order:       Optional[ProvenanceField] = None

    # -- Cross-cutting -----------------------------------------------------
    lifecycle_state:     Optional[str] = None
    db_coverage:         int = 0       # How many of 4 DBs had data
    evidence_completeness: float = 0.0  # 0.0-1.0

    # -- Provenance artifacts ----------------------------------------------
    supply_chain_timeline: list[SupplyChainEvent] = field(default_factory=list)
    contradictions:        list[DataContradiction] = field(default_factory=list)

    # -- Normalization metadata --------------------------------------------
    normalized_from:     Optional[str] = None   # original raw code if different
    resolution_time_ms:  float = 0.0

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON output / dashboard."""
        def pf_to_val(pf: Optional[ProvenanceField]) -> Any:
            return pf.value if pf else None

        return {
            "item_code":           self.item_code,
            "product_name":        pf_to_val(self.product_name),
            "generic_name":        pf_to_val(self.generic_name),
            "manufacturer_name":   pf_to_val(self.manufacturer_name),
            "cdsco_license_no":    pf_to_val(self.cdsco_license_no),
            "batch_no":            pf_to_val(self.batch_no),
            "manufacture_date":    pf_to_val(self.manufacture_date),
            "expiry_date":         pf_to_val(self.expiry_date),
            "strength":            pf_to_val(self.strength),
            "dosage_form":         pf_to_val(self.dosage_form),
            "mrp_inr":             pf_to_val(self.mrp_inr),
            "is_recalled":         pf_to_val(self.is_recalled),
            "requires_cold_chain": pf_to_val(self.requires_cold_chain),
            "distributor_name":    pf_to_val(self.distributor_name),
            "distributor_license": pf_to_val(self.distributor_license),
            "authorized_route":    pf_to_val(self.authorized_route),
            "dispatch_date":       pf_to_val(self.dispatch_date),
            "delivery_date":       pf_to_val(self.delivery_date),
            "cold_chain_ok":       pf_to_val(self.cold_chain_ok),
            "target_vendor_id":    pf_to_val(self.target_vendor_id),
            "vendor_name":         pf_to_val(self.vendor_name),
            "vendor_license":      pf_to_val(self.vendor_license),
            "purchase_date":       pf_to_val(self.purchase_date),
            "price_paid_inr":      pf_to_val(self.price_paid_inr),
            "vendor_location":     pf_to_val(self.vendor_location),
            "blacklisted":         pf_to_val(self.blacklisted),
            "complaint_count":     pf_to_val(self.complaint_count),
            "lab_result":          pf_to_val(self.lab_result),
            "gazette_order":       pf_to_val(self.gazette_order),
            "lifecycle_state":     self.lifecycle_state,
            "db_coverage":         self.db_coverage,
            "evidence_completeness": self.evidence_completeness,
            "supply_chain_timeline": [
                {
                    "stage":     e.stage, "timestamp": e.timestamp,
                    "actor":     e.actor, "location":  e.location,
                    "status":    e.status, "source_db": e.source_db,
                    "details":   e.details,
                }
                for e in self.supply_chain_timeline
            ],
            "contradictions": [
                {
                    "type":        c.contradiction_type,
                    "description": c.description,
                    "source_a":    c.source_a, "value_a": str(c.value_a),
                    "source_b":    c.source_b, "value_b": str(c.value_b),
                    "severity":    c.severity,
                }
                for c in self.contradictions
            ],
        }


# --- Builder ------------------------------------------------------------------

def build_global_view(record: ItemRecord,
                      lifecycle_state: Optional[str] = None,
                      normalized_from: Optional[str] = None) -> GlobalItemHistory:
    """
    Build a GlobalItemHistory from a resolved ItemRecord.
    This is the GAV materialization step.
    """
    import time
    t0 = time.perf_counter()

    gv = GlobalItemHistory(item_code=record.item_code)
    gv.normalized_from = normalized_from
    gv.lifecycle_state = lifecycle_state

    db_coverage = 0

    # -- DB3: Manufacturer -----------------------------------------------------
    if record.manufacturer.found and record.manufacturer.product:
        db_coverage += 1
        p = record.manufacturer.product

        def pf3(val, col):
            return ProvenanceField(val, "DB3  -  Manufacturer Registry", col, "products")

        gv.product_name        = pf3(p.get("product_name"),       "product_name")
        gv.generic_name        = pf3(p.get("generic_name"),        "generic_name")
        gv.manufacturer_name   = pf3(p.get("mfg_name"),           "company_name")
        gv.cdsco_license_no    = pf3(p.get("cdsco_license_no") or p.get("registration_no"), "cdsco_license_no")
        gv.batch_no            = pf3(p.get("batch_number"),        "batch_number")
        gv.manufacture_date    = pf3(p.get("manufacture_date"),    "manufacture_date")
        gv.expiry_date         = pf3(p.get("expiry_date"),         "expiry_date")
        gv.strength            = pf3(p.get("strength"),            "strength")
        gv.dosage_form         = pf3(p.get("dosage_form"),         "dosage_form")
        gv.mrp_inr             = pf3(p.get("msrp_kes") or p.get("mrp_inr"), "msrp_kes")
        gv.is_recalled         = pf3(bool(p.get("is_recalled")),   "is_recalled")
        gv.requires_cold_chain = pf3(bool(p.get("requires_cold_chain")), "requires_cold_chain")

        # Supply chain event: MANUFACTURED
        gv.supply_chain_timeline.append(SupplyChainEvent(
            stage      = "MANUFACTURED",
            timestamp  = str(p.get("manufacture_date", "")),
            actor      = p.get("mfg_name", "Unknown Manufacturer"),
            actor_id   = p.get("manufacturer_id", "?"),
            location   = p.get("mfg_country", "India"),
            status     = "OK",
            source_db  = "DB3  -  Manufacturer Registry",
            details    = {
                "product_uid": record.item_code,
                "batch":       p.get("batch_number"),
                "cdsco_lic":   p.get("cdsco_license_no") or p.get("registration_no"),
                "expiry":      p.get("expiry_date"),
            }
        ))

        if p.get("is_recalled"):
            gv.supply_chain_timeline.append(SupplyChainEvent(
                stage      = "RECALLED",
                timestamp  = str(p.get("recall_date", "")),
                actor      = "CDSCO / Manufacturer",
                actor_id   = p.get("manufacturer_id", "?"),
                location   = "National",
                status     = "WARNING",
                source_db  = "DB3  -  Manufacturer Registry",
                details    = {
                    "reason":    p.get("recall_reason"),
                    "authority": p.get("recall_authority"),
                }
            ))

    # -- DB2: Distributor ------------------------------------------------------
    if record.distribution.found and record.distribution.batches:
        db_coverage += 1
        b = record.distribution.batches[0]  # most recent batch

        def pf2(val, col):
            return ProvenanceField(val, "DB2  -  Distributor Ledger", col, "distribution_batches")

        gv.distributor_name   = pf2(b.get("dist_name"),            "company_name")
        gv.distributor_license= pf2(b.get("dist_license"),         "license_no")
        gv.authorized_route   = pf2(b.get("is_authorized"),        "is_authorized")
        gv.dispatch_date      = pf2(b.get("dispatch_date"),        "dispatch_date")
        gv.delivery_date      = pf2(b.get("delivery_date"),        "delivery_date")
        gv.cold_chain_ok      = pf2(b.get("cold_chain_maintained"), "cold_chain_maintained")
        gv.target_vendor_id   = pf2(b.get("vendor_id_target"),     "vendor_id_target")

        dispatch_ok = b.get("is_authorized", False)
        gv.supply_chain_timeline.append(SupplyChainEvent(
            stage      = "DISPATCHED",
            timestamp  = str(b.get("dispatch_date", "")),
            actor      = b.get("dist_name", "Unknown Distributor"),
            actor_id   = b.get("distributor_id", "?"),
            location   = b.get("dispatch_location", "India"),
            status     = "OK" if dispatch_ok else "BREAK",
            source_db  = "DB2  -  Distributor Ledger",
            details    = {
                "batch_serial":     record.item_code,
                "authorized":       dispatch_ok,
                "cold_chain":       b.get("cold_chain_maintained"),
                "vendor_target":    b.get("vendor_id_target"),
            }
        ))

        if b.get("delivery_date"):
            gv.supply_chain_timeline.append(SupplyChainEvent(
                stage      = "DELIVERED",
                timestamp  = str(b.get("delivery_date", "")),
                actor      = b.get("dist_name", "Unknown Distributor"),
                actor_id   = b.get("distributor_id", "?"),
                location   = "Vendor Location",
                status     = "OK" if b.get("delivery_status") not in ("INTERCEPTED",) else "BREAK",
                source_db  = "DB2  -  Distributor Ledger",
                details    = {
                    "delivery_status":  b.get("delivery_status"),
                    "vendor_target":    b.get("vendor_id_target"),
                }
            ))

    # -- DB1: Purchase ---------------------------------------------------------
    if record.purchase.found and record.purchase.events:
        db_coverage += 1
        e = record.purchase.events[0]   # most recent purchase

        def pf1(val, col):
            return ProvenanceField(val, "DB1  -  Purchase Registry", col, "purchase_events")

        gv.vendor_name    = pf1(e.get("vendor_name"),            "vendor_name")
        gv.vendor_license = pf1(e.get("vendor_license"),         "license_no")
        gv.purchase_date  = pf1(e.get("scan_timestamp"),         "scan_timestamp")
        gv.price_paid_inr = pf1(e.get("price_paid"),             "price_paid")
        gv.vendor_location= pf1(e.get("location_county"),        "location_county")

        gv.supply_chain_timeline.append(SupplyChainEvent(
            stage      = "DISPENSED",
            timestamp  = str(e.get("scan_timestamp", "")),
            actor      = e.get("vendor_name", "Unknown Vendor"),
            actor_id   = e.get("vendor_id", "?"),
            location   = e.get("location_county", "Unknown"),
            status     = "OK",
            source_db  = "DB1  -  Purchase Registry",
            details    = {
                "scan_code":   record.item_code,
                "price_paid":  e.get("price_paid"),
                "vendor_lic":  e.get("vendor_license"),
            }
        ))

    # -- DB4: Ministry ---------------------------------------------------------
    if record.ministry.found or record.ministry.blacklist_entry:
        db_coverage += 1
        bl = record.ministry.blacklist_entry

        def pf4(val, col):
            return ProvenanceField(val, "DB4  -  Ministry of Consumer Affairs", col, "ministry_blacklist")

        gv.blacklisted    = pf4(bl is not None and bl.get("active", 0) == 1, "active")
        gv.complaint_count= ProvenanceField(
            len(record.ministry.complaints),
            "DB4  -  Ministry of Consumer Affairs", "complaint_id", "complaints")
        gv.gazette_order  = pf4(bl.get("gazette_order_no") if bl else None, "gazette_order_no")

        # Lab result
        if record.ministry.lab_reports:
            lr = record.ministry.lab_reports[0]
            gv.lab_result = ProvenanceField(
                lr.get("result"), "DB4  -  Ministry Lab Reports", "result", "lab_reports")

        if bl and bl.get("active"):
            gv.supply_chain_timeline.append(SupplyChainEvent(
                stage      = "FLAGGED",
                timestamp  = str(bl.get("blacklisted_on", "")),
                actor      = "Ministry of Consumer Affairs / CDSCO",
                actor_id   = "MCA-GOI",
                location   = "National",
                status     = "BREAK",
                source_db  = "DB4  -  Ministry of Consumer Affairs",
                details    = {
                    "reason":        bl.get("reason"),
                    "health_risk":   bl.get("health_risk"),
                    "gazette_order": bl.get("gazette_order_no"),
                }
            ))

    # -- Sort timeline chronologically -----------------------------------------
    def _ts(e: SupplyChainEvent) -> str:
        return e.timestamp or "0000-00-00"
    gv.supply_chain_timeline.sort(key=_ts)

    # -- Detect contradictions -------------------------------------------------
    gv.contradictions = _detect_contradictions(record, gv)

    # -- Evidence completeness (Claude audit) ----------------------------------
    gv.db_coverage            = db_coverage
    gv.evidence_completeness  = round(db_coverage / 4.0, 2)

    gv.resolution_time_ms = round((time.perf_counter() - t0) * 1000, 2)
    return gv


def _detect_contradictions(record: ItemRecord,
                            gv: GlobalItemHistory) -> list[DataContradiction]:
    """
    Systematic cross-DB contradiction detection (GPT audit).
    Checks for logical inconsistencies between records.
    """
    contras = []

    # C1: Temporal  -  manufacture_date vs dispatch_date
    mfg_date = gv.manufacture_date.value if gv.manufacture_date else None
    disp_date = gv.dispatch_date.value if gv.dispatch_date else None
    if mfg_date and disp_date:
        try:
            from datetime import date
            md = date.fromisoformat(str(mfg_date))
            dd = date.fromisoformat(str(disp_date)[:10])
            if dd < md:
                contras.append(DataContradiction(
                    contradiction_type = "TEMPORAL",
                    description        = f"Item dispatched ({dd}) BEFORE manufactured ({md})",
                    source_a           = "DB3  -  Manufacturer Registry",
                    value_a            = md,
                    source_b           = "DB2  -  Distributor Ledger",
                    value_b            = dd,
                    severity           = "HIGH",
                ))
        except (ValueError, TypeError):
            pass

    # C2: Temporal  -  manufacture_date vs purchase_date
    purch_date = gv.purchase_date.value if gv.purchase_date else None
    if mfg_date and purch_date:
        try:
            from datetime import date
            md = date.fromisoformat(str(mfg_date))
            pd = date.fromisoformat(str(purch_date)[:10])
            if pd < md:
                contras.append(DataContradiction(
                    contradiction_type = "TEMPORAL",
                    description        = f"Item purchased ({pd}) BEFORE manufactured ({md})",
                    source_a           = "DB3  -  Manufacturer Registry",
                    value_a            = md,
                    source_b           = "DB1  -  Purchase Registry",
                    value_b            = pd,
                    severity           = "HIGH",
                ))
        except (ValueError, TypeError):
            pass

    # C3: Status  -  recalled but still being sold
    if gv.is_recalled and gv.is_recalled.value and record.purchase.found:
        if gv.purchase_date and gv.manufacture_date:
            try:
                from datetime import date
                recall_d = record.manufacturer.product.get("recall_date","")
                pd       = date.fromisoformat(str(gv.purchase_date.value)[:10])
                rd       = date.fromisoformat(str(recall_d)[:10]) if recall_d else None
                if rd and pd > rd:
                    contras.append(DataContradiction(
                        contradiction_type = "STATUS",
                        description        = f"Item sold ({pd}) AFTER recall date ({rd})",
                        source_a           = "DB3  -  Manufacturer Registry",
                        value_a            = f"Recalled on {rd}",
                        source_b           = "DB1  -  Purchase Registry",
                        value_b            = f"Sold on {pd}",
                        severity           = "HIGH",
                    ))
            except (ValueError, TypeError):
                pass

    # C4: Identity  -  vendor who sold vs vendor dispatch target
    if gv.target_vendor_id and gv.vendor_name:
        purch_vendors = {e.get("vendor_id") for e in record.purchase.events}
        target        = gv.target_vendor_id.value
        if target and purch_vendors and target not in purch_vendors:
            contras.append(DataContradiction(
                contradiction_type = "CUSTODY",
                description        = f"Dispatched to vendor '{target}' but sold by {purch_vendors}",
                source_a           = "DB2  -  Distributor Ledger",
                value_a            = f"Target vendor: {target}",
                source_b           = "DB1  -  Purchase Registry",
                value_b            = f"Selling vendor: {purch_vendors}",
                severity           = "HIGH",
            ))

    # C5: Price  -  price paid vs MRP (Claude audit)
    mrp  = gv.mrp_inr.value if gv.mrp_inr else None
    paid = gv.price_paid_inr.value if gv.price_paid_inr else None
    if mrp and paid:
        try:
            mrp_f  = float(mrp)
            paid_f = float(paid)
            if mrp_f > 0 and paid_f < mrp_f * 0.40:
                contras.append(DataContradiction(
                    contradiction_type = "PRICE",
                    description        = f"Price paid (INR {paid_f:.0f}) is {paid_f/mrp_f:.0%} of MRP (INR {mrp_f:.0f})  -  hallmark of counterfeit",
                    source_a           = "DB3  -  Manufacturer Registry",
                    value_a            = f"MRP: INR {mrp_f:.0f}",
                    source_b           = "DB1  -  Purchase Registry",
                    value_b            = f"Paid: INR {paid_f:.0f}",
                    severity           = "MEDIUM",
                ))
        except (TypeError, ValueError):
            pass

    return contras
