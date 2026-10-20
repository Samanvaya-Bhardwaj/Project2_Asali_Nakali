#!/usr/bin/env python3
"""
trust_engine.py  (v2  -  Two-Tier Hybrid Architecture)
------------------------------------------------------
TIER-1: Hard Veto (deterministic, zero-tolerance)  -  see hard_veto_engine.py
TIER-2: Soft Compliance Score (probabilistic, weighted deductions)

Fixes from multi-LLM audit:
  Subtractive Scoring Paradox fixed  -  Tier-1 forces score=0 for phantom serials
  Vendor cross-check signal added (Gemini Flaw 3)
  Price-below-MRP signal added (Claude audit)
  Temporal contradiction signal from canonical_model
  Evidence Completeness renamed and formally defined (Claude)
  Verdict thresholds adjusted: ASALI >=80 (was >=85)

Tier-2 Soft Signals (when Tier-1 passes):
  Start: 100 points
  1. Cold chain breach for temperature-sensitive medicine:  -25
  2. Unauthorized distributor route:                       -20
  3. Price below 40% of MRP:                               -15
  4. Open MCA complaints:                                  -10
  5. Near expiry (within 30 days):                         -10
  6. Supply chain gap (no distributor record):             -20
  7. Distributor license expired/revoked:                  -15
  8. Lab test failed:                                      -15
  9. Product recalled:                                     -15
 10. Price suspiciously low (40-60% of MRP):               -8  (mild signal)
Bonus:
  +5  Lab test passed
  +5  All checks clean (perfect score)
"""

from __future__ import annotations
import json, os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from integration.resolver import ItemRecord

if TYPE_CHECKING:
    from integration.canonical_model import GlobalItemHistory

MAPPING_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "integration", "schema_mapping.json"
)
with open(MAPPING_PATH) as f:
    MAPPING = json.load(f)

WEIGHTS    = MAPPING.get("trust_score_weights", {})
THRESHOLDS = MAPPING.get("verdict_thresholds", {"ASALI": 80, "SUSPICIOUS": 50})


# --- Result dataclasses -------------------------------------------------------

@dataclass
class EvidenceItem:
    signal:      str
    value:       int      # positive = bonus, negative = deduction
    description: str
    db_source:   str
    tier:        str = "SOFT"   # "HARD_VETO" or "SOFT"


@dataclass
class TrustResult:
    item_code:       str
    trust_score:     int
    verdict:         str           # ASALI / SUSPICIOUS / NAKALI
    verdict_emoji:   str
    # Evidence completeness (renamed from "confidence interval" per Claude audit)
    evidence_completeness: int     # 0-100  -  how much data was available
    db_coverage:     int           # 0-4 DBs with data
    evidence:        list[EvidenceItem] = field(default_factory=list)
    veto_gates:      list = field(default_factory=list)    # VetoGate objects
    summary:         str = ""
    recommendations: list[str] = field(default_factory=list)
    auto_report:     bool = False
    lifecycle_state: Optional[str] = None
    # Backward compat alias
    @property
    def confidence_pct(self) -> int:
        return self.evidence_completeness


# --- Two-Tier Engine ----------------------------------------------------------

class TrustEngine:
    """
    Two-Tier Hybrid Verification Engine.

    Tier 1 (hard_veto_engine.py) is called FIRST by verify_item.py.
    This class only implements Tier 2 (soft scoring).
    The orchestrator (verify_item.py) wires them together.
    """

    def calculate(self, record: ItemRecord,
                  veto_result=None,
                  global_view=None) -> TrustResult:
        """
        Calculate the Tier-2 soft compliance score.

        Args:
            record:      Resolved ItemRecord
            veto_result: VetoResult from HardVetoEngine (if None, skips Tier-1)
            global_view: GlobalItemHistory (for contradiction signals)
        """
        # -- Tier-1 Short-circuit -----------------------------------------------
        if veto_result is not None and veto_result.vetoed:
            veto_evidence = [
                EvidenceItem(
                    signal      = gate.gate_id,
                    value       = -100,
                    description = gate.description,
                    db_source   = "Tier-1 Hard Veto Gate",
                    tier        = "HARD_VETO",
                )
                for gate in veto_result.triggered_gates
            ]
            recs = self._veto_recommendations(veto_result)
            db_cov = sum([record.purchase.found, record.distribution.found,
                          record.manufacturer.found, record.ministry.found])
            return TrustResult(
                item_code            = record.item_code,
                trust_score          = 0,
                verdict              = "NAKALI",
                verdict_emoji        = "FAIL",
                evidence_completeness= self._evidence_completeness(record),
                db_coverage          = db_cov,
                evidence             = veto_evidence,
                veto_gates           = veto_result.triggered_gates,
                summary              = self._veto_summary(record, veto_result),
                recommendations      = recs,
                auto_report          = True,
                lifecycle_state      = None,
            )

        # -- Tier-2 Soft Scoring ------------------------------------------------
        score    = 100
        evidence = []
        recs     = []

        p   = record.purchase
        d   = record.distribution
        m   = record.manufacturer
        reg = record.ministry

        # 2a. Product recall (DB3)
        if m.found and m.product:
            prod = m.product
            if prod.get("is_recalled"):
                adj = WEIGHTS.get("product_recalled", -15)
                score += adj
                evidence.append(EvidenceItem(
                    "PRODUCT_RECALLED", adj,
                    f"Product recalled on {prod.get('recall_date')}. "
                    f"Reason: {prod.get('recall_reason')}. "
                    f"Authority: {prod.get('recall_authority')}.",
                    "DB3  -  Manufacturer Registry"))
                recs.append(" This product has been officially RECALLED. Return to vendor.")

            # 2b. Expiry check  -  near expiry within 30 days
            try:
                exp = date.fromisoformat(str(prod.get("expiry_date", "2099-01-01")))
                today = date.today()
                if exp < today:
                    adj = WEIGHTS.get("product_expired", -10)
                    score += adj
                    evidence.append(EvidenceItem(
                        "PRODUCT_EXPIRED", adj,
                        f"Product expired on {exp}. Selling expired medicine is illegal.",
                        "DB3  -  Manufacturer Registry"))
                    recs.append(f" Product expired on {exp}. Do not consume.")
                elif (exp - today).days <= 30:
                    adj = WEIGHTS.get("near_expiry", -10)
                    score += adj
                    evidence.append(EvidenceItem(
                        "NEAR_EXPIRY", adj,
                        f"Product expires in {(exp-today).days} day(s) (on {exp}). "
                        "Verify with vendor before purchasing.",
                        "DB3  -  Manufacturer Registry"))
                    recs.append(f" Product expires in {(exp-today).days} days.")
            except (ValueError, TypeError):
                pass

        # 2c. Open MCA complaints (DB4)
        open_complaints = [
            c for c in reg.complaints
            if c.get("status") in ("open","under_investigation","lab_testing","escalated")
        ]
        if open_complaints:
            adj = WEIGHTS.get("open_complaints", -10)
            score += adj
            cats = ", ".join(set(c.get("complaint_category","?") for c in open_complaints))
            evidence.append(EvidenceItem(
                "OPEN_COMPLAINTS", adj,
                f"{len(open_complaints)} active MCA complaint(s). Categories: {cats}.",
                "DB4  -  Ministry of Consumer Affairs"))
            recs.append(f" {len(open_complaints)} unresolved complaint(s) with MCA.")

        # 2d. Distributor signals (DB2)
        if d.found:
            # Unauthorized route
            unauth = [b for b in d.batches if not b.get("is_authorized")]
            ghost  = [b for b in d.batches if b.get("distributor_id") == "DIST-004"]
            if unauth or ghost:
                adj = WEIGHTS.get("distributor_unauthorized", -20)
                score += adj
                names = ", ".join(set(b.get("dist_name","?") for b in (unauth or ghost)))
                evidence.append(EvidenceItem(
                    "DISTRIBUTOR_UNAUTHORIZED", adj,
                    f"Distributed by UNAUTHORIZED entity: {names}. "
                    "Not on CDSCO-approved list for this manufacturer.",
                    "DB2  x  DB3"))
                recs.append("Unauthorized distributor. Procurement chain is compromised.")

                # Expired license
                exp_lic = [
                    b for b in d.distributors
                    if b.get("is_authorized") == 0 or
                    (b.get("license_expiry") and
                     date.fromisoformat(str(b["license_expiry"])) < date.today())
                ]
                if exp_lic:
                    adj2 = WEIGHTS.get("distributor_unlicensed", -15)
                    score += adj2
                    evidence.append(EvidenceItem(
                        "DISTRIBUTOR_UNLICENSED", adj2,
                        f"Distributor license expired/revoked. "
                        f"Reason: {exp_lic[0].get('revocation_reason','Unknown')}.",
                        "DB2  -  Distributor Ledger"))

            # Cold chain (signal adjusted to -25 per Gemini architecture)
            cold_breaks = [b for b in d.batches if b.get("cold_chain_maintained") == 0]
            req_cc = m.product.get("requires_cold_chain") if m.product else False
            if cold_breaks and req_cc:
                adj = WEIGHTS.get("cold_chain_broken", -25)
                score += adj
                evidence.append(EvidenceItem(
                    "COLD_CHAIN_BROKEN", adj,
                    f"TEMPERATURE-SENSITIVE MEDICINE: Cold chain broken in "
                    f"{len(cold_breaks)} batch(es). Efficacy is compromised.",
                    "DB2  -  Distributor Ledger"))
                recs.append(" Cold chain broken. Product potency may be compromised.")

            # 2e. Vendor custody cross-check (Gemini Flaw 3  -  NEW)
            purchase_vendors  = {e.get("vendor_id") for e in p.events if e.get("vendor_id")}
            dispatch_targets  = {b.get("vendor_id_target") for b in d.batches if b.get("vendor_id_target")}
            if dispatch_targets:
                wrong_vendors = purchase_vendors - dispatch_targets
                if wrong_vendors:
                    adj = WEIGHTS.get("vendor_custody_bypass", -20)
                    score += adj
                    evidence.append(EvidenceItem(
                        "VENDOR_CUSTODY_BYPASS", adj,
                        f"SUPPLY CHAIN DIVERSION: Item sold by vendor(s) {wrong_vendors} "
                        f"but dispatched exclusively to {dispatch_targets}. "
                        "Indicates stolen stock, grey market, or diverted shipment.",
                        "DB1  x  DB2  -  Cross-DB custody check"))
                    recs.append("Supply chain diversion detected  -  wrong vendor sold this item.")

        else:
            # No distributor record but item was sold  -  gap
            if p.found:
                adj = WEIGHTS.get("supply_chain_gap", -20)
                score += adj
                evidence.append(EvidenceItem(
                    "SUPPLY_CHAIN_GAP", adj,
                    "Item in purchase records (DB1) but NO distributor record in DB2. "
                    "Genuine medicine must pass through licensed distributor. "
                    "This item bypassed the entire supply chain.",
                    "DB1  x  DB2  -  Supply chain gap"))
                recs.append("Supply chain gap: Item reached vendor with no distribution record.")

        # 2f. Multi-location / barcode cloning (DB1)
        if p.anomalies:
            multi_loc = [a for a in p.anomalies if a.get("anomaly_type") in ("multi_location", "velocity_anomaly")]
            if multi_loc:
                adj = WEIGHTS.get("multi_location_anomaly", -35)
                score += adj
                evidence.append(EvidenceItem(
                    "MULTI_LOCATION_ANOMALY", adj,
                    f"BARCODE CLONING: Same code scanned at multiple locations simultaneously. "
                    f"Detail: {multi_loc[0].get('description','N/A')}. "
                    "Physical impossibility  -  counterfeit copies in circulation.",
                    "DB1  -  Purchase Registry"))
                recs.append("Barcode cloning  -  multiple counterfeit copies in circulation.")

        # 2g. Lab result (DB4)
        failed_labs = [lr for lr in reg.lab_reports if lr.get("result") == "fail"]
        passed_labs = [lr for lr in reg.lab_reports if lr.get("result") == "pass"]
        if failed_labs:
            adj = WEIGHTS.get("lab_test_fail", -15)
            score += adj
            evidence.append(EvidenceItem(
                "LAB_TEST_FAILED", adj,
                f"MCA Lab FAILED. Lab: {failed_labs[0].get('lab_name')}. "
                f"Findings: {failed_labs[0].get('findings_summary','N/A')}.",
                "DB4  -  Ministry Lab Reports"))
        elif passed_labs:
            adj = WEIGHTS.get("lab_test_pass_bonus", 5)
            score += adj
            evidence.append(EvidenceItem(
                "LAB_TEST_PASSED", adj,
                f"MCA Lab PASSED ({passed_labs[0].get('lab_name')}). "
                "Product quality verified by accredited lab.",
                "DB4  -  Ministry Lab Reports"))

        # 2h. Price-below-MRP signal (Claude audit  -  NEW)
        if m.product and p.found and p.events:
            mrp  = m.product.get("msrp_kes") or m.product.get("mrp_inr")
            paid = p.events[0].get("price_paid")
            if mrp and paid:
                try:
                    mrp_f, paid_f = float(mrp), float(paid)
                    ratio = paid_f / mrp_f if mrp_f > 0 else 1.0
                    if ratio < 0.40:
                        adj = WEIGHTS.get("price_below_mrp", -15)
                        score += adj
                        evidence.append(EvidenceItem(
                            "PRICE_BELOW_MRP", adj,
                            f"Price paid (INR {paid_f:.0f}) is only {ratio:.0%} of MRP (INR {mrp_f:.0f}). "
                            "Prices < 40% of MRP are a hallmark of counterfeits "
                            "(no genuine API manufacturing cost).",
                            "DB1  x  DB3  -  Price cross-check"))
                        recs.append(f" Price (INR {paid_f:.0f}) suspiciously below MRP (INR {mrp_f:.0f}).")
                    elif ratio < 0.60:
                        adj = WEIGHTS.get("price_suspicious", -8)
                        score += adj
                        evidence.append(EvidenceItem(
                            "PRICE_SUSPICIOUS", adj,
                            f"Price (INR {paid_f:.0f}) is {ratio:.0%} of MRP  -  below normal range.",
                            "DB1  x  DB3  -  Price cross-check"))
                except (TypeError, ValueError):
                    pass

        # 2i. Contradictions from canonical model (GPT audit  -  NEW)
        if global_view and global_view.contradictions:
            for contra in global_view.contradictions:
                if contra.contradiction_type == "TEMPORAL" and contra.severity == "HIGH":
                    adj = -15
                    score += adj
                    evidence.append(EvidenceItem(
                        "TEMPORAL_CONTRADICTION", adj,
                        contra.description,
                        f"{contra.source_a}  x  {contra.source_b}"))
                elif contra.contradiction_type == "CUSTODY" and contra.severity == "HIGH":
                    pass   # already handled by V5 / vendor bypass above

        # -- All-clean bonus ----------------------------------------------------
        deductions = sum(e.value for e in evidence if e.value < 0)
        if deductions == 0 and m.found:
            adj = WEIGHTS.get("all_checks_clean_bonus", 5)
            score += adj
            evidence.append(EvidenceItem(
                "ALL_CHECKS_CLEAN", adj,
                "All Tier-2 compliance checks passed. Full supply chain verified. "
                "No complaints, no cold chain issues, no price anomalies.",
                "All 4 DBs"))
            recs.append("All checks passed. Medicine appears genuine and safe.")

        # -- Clamp -------------------------------------------------------------
        score = max(0, min(100, score))

        # -- Verdict (adjusted thresholds per plan) -----------------------------
        if score >= THRESHOLDS.get("ASALI", 80):
            verdict, emoji = "ASALI", "PASS"
        elif score >= THRESHOLDS.get("SUSPICIOUS", 50):
            verdict, emoji = "SUSPICIOUS", ""
        else:
            verdict, emoji = "NAKALI", "FAIL"

        # -- Evidence completeness (formally defined  -  Claude audit) ------------
        ec   = self._evidence_completeness(record)
        db_c = sum([p.found, d.found, m.found, reg.found])

        # -- Auto-report --------------------------------------------------------
        auto_report = verdict == "NAKALI" or any(
            e.signal in (
                "MINISTRY_BLACKLISTED","MULTI_LOCATION_ANOMALY",
                "SUPPLY_CHAIN_GAP","VENDOR_CUSTODY_BYPASS",
            )
            for e in evidence)

        summary = self._build_summary(record, verdict, score, evidence, m)

        return TrustResult(
            item_code            = record.item_code,
            trust_score          = score,
            verdict              = verdict,
            verdict_emoji        = emoji,
            evidence_completeness= ec,
            db_coverage          = db_c,
            evidence             = evidence,
            veto_gates           = [],
            summary              = summary,
            recommendations      = recs,
            auto_report          = auto_report,
        )

    def _evidence_completeness(self, record: ItemRecord) -> int:
        """
        Evidence Completeness Score (0-100).
        Formally defined: what fraction of verification signals had data to evaluate.

        DB coverage:       4  x  20 pts = up to 80 pts
        Signal richness:   bonus pts for additional sub-signals
        """
        pts = 0
        if record.manufacturer.found:  pts += 20
        if record.distribution.found:  pts += 20
        if record.purchase.found:      pts += 20
        if record.ministry.found:      pts += 20
        # Bonus for richer data
        if record.ministry.lab_reports:                    pts += 5
        if record.manufacturer.found and record.manufacturer.product:
            if record.manufacturer.product.get("batch_number"): pts += 5
        if record.purchase.found and record.purchase.anomalies: pts += 5
        # Penalty for missing critical DB
        if not record.manufacturer.found: pts -= 10
        return min(99, max(10, pts))

    def _veto_recommendations(self, veto_result) -> list[str]:
        recs = []
        for gate in veto_result.triggered_gates:
            if gate.gate_id == "V1_PHANTOM_SERIAL":
                recs.append("Do NOT purchase. No CDSCO manufacturer registration found.")
            elif gate.gate_id == "V2_MINISTRY_BLACKLIST":
                recs.append("Item is on MCA/CDSCO BLACKLIST. Report to authorities.")
            elif gate.gate_id == "V3_TEMPORAL_PARADOX":
                recs.append("Temporal paradox detected. Forged batch numbers suspected.")
            elif gate.gate_id == "V4_REPLAY_SCAN":
                recs.append("Barcode cloning or replay attack. Multiple copies in circulation.")
            elif gate.gate_id == "V5_CUSTODY_BYPASS":
                recs.append("Supply chain custody bypass. Item reached wrong vendor.")
        return recs

    def _veto_summary(self, record: ItemRecord, veto_result) -> str:
        codes = ", ".join(veto_result.veto_codes)
        return (
            f"Item '{record.item_code}' VETOED by Tier-1 Hard Veto Gate(s): {codes}. "
            f"Score forced to 0. Verdict: NAKALI."
        )

    def _build_summary(self, record, verdict, score, evidence, m) -> str:
        name    = m.product.get("product_name", record.item_code) if m.product else record.item_code
        signals = ", ".join(e.signal for e in evidence if e.value < 0) or "NONE"
        return (
            f"Item '{record.item_code}' ({name})  -  Tier-2 score: {score}/100. "
            f"Verdict: {verdict}. Negative signals: {signals}."
        )


# --- CLI test -----------------------------------------------------------------
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from integration.resolver import resolve
    from integration.hard_veto_engine import HardVetoEngine
    from integration.lifecycle_state import get_tracker
    from integration.canonical_model import build_global_view

    code   = sys.argv[1] if len(sys.argv) > 1 else "MED-NAKALI-001"
    record = resolve(code)

    tracker  = get_tracker()
    lc_state = tracker.infer_and_sync(record)

    veto   = HardVetoEngine().evaluate(record, lifecycle_state=lc_state)
    gv     = build_global_view(record, lc_state)
    engine = TrustEngine()
    result = engine.calculate(record, veto_result=veto, global_view=gv)

    print(f"\n{'='*65}")
    print(f"  TRUST RESULT (v2): {code}")
    print(f"{'='*65}")
    print(f"  Score        : {result.trust_score}/100")
    print(f"  Verdict      : {result.verdict_emoji} {result.verdict}")
    print(f"  Evidence     : {result.evidence_completeness}%")
    print(f"  DB Coverage  : {result.db_coverage}/4")
    print(f"  Lifecycle    : {lc_state}")
    print(f"\n  Evidence:")
    for ev in result.evidence:
        sign = "+" if ev.value >= 0 else ""
        tier = " [VETO]" if ev.tier == "HARD_VETO" else ""
        print(f"    [{sign}{ev.value:+d}]{tier} {ev.signal}")
    print(f"\n  Recommendations:")
    for r in result.recommendations:
        print(f"    {r}")
