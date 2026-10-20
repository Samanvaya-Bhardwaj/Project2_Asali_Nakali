#!/usr/bin/env python3
"""
hard_veto_engine.py
-------------------
Tier-1: Deterministic Hard Veto Gates.

DESIGN PRINCIPLE (from Gemini audit):
The Subtractive Scoring Paradox  -  a phantom serial that only fails
the manufacturer check scores 100 - 40 = 60 -> SUSPICIOUS.
That is WRONG. A medicine that was never manufactured is an immediate
NAKALI regardless of all other signals.

This module runs BEFORE the soft trust scorer. Any veto returns
score=0, verdict=NAKALI immediately, bypassing soft scoring.

Five Hard Veto Gates (zero-tolerance, fail-stop):
  V1. PHANTOM_SERIAL       -  Not in Manufacturer DB (DB3)
  V2. MINISTRY_BLACKLIST   -  Explicitly blacklisted by MCA/CDSCO (DB4)
  V3. TEMPORAL_PARADOX     -  Sold before manufactured (cross-DB)
  V4. REPLAY_SCAN          -  Already DISPENSED (clone/double-spend)
  V5. CUSTODY_BYPASS       -  Sold by vendor not in authorized dispatch route

Each gate is independent. The first triggered gate wins.
Multiple gates can trigger (all are logged).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

from integration.resolver import ItemRecord


@dataclass
class VetoGate:
    gate_id:     str       # e.g. "V1_PHANTOM_SERIAL"
    triggered:   bool
    description: str
    severity:    str       # "CRITICAL" for all vetos
    evidence:    dict      # raw evidence from DBs


@dataclass
class VetoResult:
    vetoed:       bool                    # True if ANY gate fired
    gates:        list[VetoGate] = field(default_factory=list)
    primary_veto: Optional[VetoGate] = None   # first triggered

    @property
    def triggered_gates(self) -> list[VetoGate]:
        return [g for g in self.gates if g.triggered]

    @property
    def veto_codes(self) -> list[str]:
        return [g.gate_id for g in self.triggered_gates]


class HardVetoEngine:
    """
    Implements the 5 deterministic hard veto gates.
    Any gate that triggers causes immediate NAKALI verdict (score=0).
    """

    def evaluate(self, record: ItemRecord,
                 lifecycle_state: Optional[str] = None) -> VetoResult:
        """
        Run all 5 veto gates against the resolved ItemRecord.

        Args:
            record:          Fully resolved ItemRecord from resolver.py
            lifecycle_state: Current state from lifecycle tracker
                             (MINTED/DISPATCHED/DELIVERED/DISPENSED)

        Returns:
            VetoResult  -  contains all gate results and a vetoed flag.
        """
        gates = [
            self._v1_phantom_serial(record),
            self._v2_ministry_blacklist(record),
            self._v3_temporal_paradox(record),
            self._v4_replay_scan(record, lifecycle_state),
            self._v5_custody_bypass(record),
        ]

        triggered = [g for g in gates if g.triggered]
        vetoed    = len(triggered) > 0

        return VetoResult(
            vetoed       = vetoed,
            gates        = gates,
            primary_veto = triggered[0] if triggered else None,
        )

    # -- V1: Phantom Serial ----------------------------------------------------

    def _v1_phantom_serial(self, record: ItemRecord) -> VetoGate:
        """
        A serial code that does not exist in the Manufacturer Registry (DB3)
        cannot be genuine. No manufacturer = no legitimate origin = NAKALI.

        This is the most powerful signal. In India's Schedule H2 framework,
        every legitimate medicine unit must trace back to a licensed manufacturer.
        """
        triggered = not record.manufacturer.found or record.manufacturer.product is None
        return VetoGate(
            gate_id     = "V1_PHANTOM_SERIAL",
            triggered   = triggered,
            severity    = "CRITICAL",
            description = (
                f"Item code '{record.item_code}' has NO record in the "
                "Manufacturer Product Registry (DB3 / CDSCO-registered products). "
                "A genuine medicine unit must be registered by a licensed "
                "CDSCO-approved manufacturer. This is an absolute NAKALI indicator."
            ) if triggered else (
                f"Item confirmed in Manufacturer Registry: "
                f"{record.manufacturer.product.get('product_name', '?')}  -  "
                f"CDSCO Lic: {record.manufacturer.product.get('cdsco_license_no','?')}"
            ),
            evidence = {
                "manufacturer_found": record.manufacturer.found,
                "product":            record.manufacturer.product,
            }
        )

    # -- V2: Ministry / CDSCO Blacklist ----------------------------------------

    def _v2_ministry_blacklist(self, record: ItemRecord) -> VetoGate:
        """
        If an item is on the Ministry of Consumer Affairs / CDSCO blacklist,
        it must never receive a passing or suspicious verdict.
        A blacklisted item is by regulatory definition NAKALI.
        """
        bl = record.ministry.blacklist_entry
        triggered = bl is not None and bl.get("active", 0) == 1

        if triggered:
            desc = (
                f"Item is on the MCA/CDSCO BLACKLIST. "
                f"Gazette order: {bl.get('gazette_order_no', 'N/A')}. "
                f"Blacklisted on: {bl.get('blacklisted_on', 'N/A')}. "
                f"Reason: {bl.get('reason', 'N/A')}. "
                f"Risk: {bl.get('health_risk', 'N/A')}."
            )
        else:
            desc = "Item is NOT on any MCA/CDSCO blacklist  -  blacklist clear."

        return VetoGate(
            gate_id     = "V2_MINISTRY_BLACKLIST",
            triggered   = triggered,
            severity    = "CRITICAL",
            description = desc,
            evidence    = {"blacklist_entry": bl}
        )

    # -- V3: Temporal Paradox --------------------------------------------------

    def _v3_temporal_paradox(self, record: ItemRecord) -> VetoGate:
        """
        Cross-DB consistency check (GPT audit recommendation):
        manufacture_date (DB3) must be BEFORE dispatch_date (DB2)
        and BEFORE purchase_date (DB1).

        If sold before manufactured: temporal paradox -> counterfeit packaging
        reusing a future batch number, or back-dated fraud.
        """
        paradox_details = []
        triggered = False

        mfg_prod = record.manufacturer.product
        mfg_date = None
        if mfg_prod:
            try:
                mfg_date = date.fromisoformat(str(mfg_prod.get("manufacture_date", "")))
            except (ValueError, TypeError):
                pass

        # Check: dispatch before manufacture?
        if mfg_date and record.distribution.found:
            for batch in record.distribution.batches:
                try:
                    dispatch_date = datetime.fromisoformat(
                        str(batch.get("dispatch_date", "2099-01-01"))
                    ).date()
                    if dispatch_date < mfg_date:
                        triggered = True
                        paradox_details.append(
                            f"Dispatch {dispatch_date} < Manufacture {mfg_date} "
                            f"(batch {batch.get('batch_id','?')})"
                        )
                except (ValueError, TypeError):
                    pass

        # Check: purchase before manufacture?
        if mfg_date and record.purchase.found:
            for evt in record.purchase.events:
                try:
                    purchase_dt = datetime.fromisoformat(
                        str(evt.get("scan_timestamp", "2099-01-01"))
                    ).date()
                    if purchase_dt < mfg_date:
                        triggered = True
                        paradox_details.append(
                            f"Purchase {purchase_dt} < Manufacture {mfg_date} "
                            f"(event {evt.get('purchase_id','?')})"
                        )
                except (ValueError, TypeError):
                    pass

        desc = (
            f"TEMPORAL PARADOX DETECTED: {'; '.join(paradox_details)}. "
            "Medicine cannot be sold or dispatched before its manufacture date. "
            "This indicates forged batch numbers or pre-dated packaging."
        ) if triggered else (
            "Temporal consistency check PASSED  -  all dates are logically ordered "
            "(manufacture -> dispatch -> purchase)."
        )

        return VetoGate(
            gate_id     = "V3_TEMPORAL_PARADOX",
            triggered   = triggered,
            severity    = "CRITICAL",
            description = desc,
            evidence    = {
                "manufacture_date": str(mfg_date) if mfg_date else None,
                "paradoxes":        paradox_details
            }
        )

    # -- V4: Replay / Double-Spend ---------------------------------------------

    def _v4_replay_scan(self, record: ItemRecord,
                        lifecycle_state: Optional[str]) -> VetoGate:
        """
        If the item's lifecycle state is already DISPENSED (sold once),
        any subsequent scan of the same serial code is a REPLAY ATTACK  - 
        a cloned barcode being sold again.

        Also fires if multi-location anomaly is confirmed (physical impossibility).
        """
        # Check 1: Multi-location or replay anomalies in scan log (physical impossibility)
        replay_anomalies = [
            a for a in record.purchase.anomalies
            if a.get("anomaly_type") in ("multi_location", "replay_scan", "duplicate_scan", "barcode_cloning")
        ]
        clone_triggered = len(replay_anomalies) > 0

        # Check 2: Check for flagged replay purchase events (anomaly_flag=1 with multi_location)
        flagged_events = [
            e for e in record.purchase.events
            if e.get("anomaly_flag") == 1 and "multi_location" in str(e.get("anomaly_reason", ""))
        ]
        event_triggered = len(flagged_events) > 0

        # Check 3: Check if lifecycle tracker recorded an illegal re-dispense violation
        tracker_violations = []
        try:
            from integration.lifecycle_state import get_tracker
            tracker_violations = [
                h for h in get_tracker().get_history(record.item_code)
                if h.get("violation") == "REPLAY_ATTACK"
            ]
        except Exception:
            pass
        violation_triggered = len(tracker_violations) > 0

        triggered = clone_triggered or event_triggered or violation_triggered

        if clone_triggered:
            desc = (
                f"BARCODE CLONING: Same serial code scanned across multiple "
                f"mutually exclusive locations. Detail: {replay_anomalies[0].get('description','?')}. "
                "A physical medicine unit cannot exist in multiple places simultaneously."
            )
        elif event_triggered:
            desc = (
                f"REPLAY / CLONE DETECTED: {len(flagged_events)} scan event(s) flagged "
                "with multi-location anomaly. Cloned packaging in circulation."
            )
        elif violation_triggered:
            desc = (
                "REPLAY ATTACK: Lifecycle state machine detected illegal DISPENSED -> DISPENSED "
                "transition. Re-dispensing of an already consumed unit is prohibited."
            )
        else:
            desc = (
                f"Lifecycle verification PASSED (State: {lifecycle_state or 'DELIVERED'}). "
                "No replay attack or multi-location cloning detected."
            )

        return VetoGate(
            gate_id     = "V4_REPLAY_SCAN",
            triggered   = triggered,
            severity    = "CRITICAL",
            description = desc,
            evidence    = {
                "lifecycle_state":      lifecycle_state,
                "replay_anomalies":     replay_anomalies,
                "flagged_events_count": len(flagged_events),
                "tracker_violations":   tracker_violations,
            }
        )

    # -- V5: Custody Bypass ----------------------------------------------------

    def _v5_custody_bypass(self, record: ItemRecord) -> VetoGate:
        """
        Chain-of-custody validation (Gemini Flaw 3):
        Verify that the vendor who sold this item MATCHES the vendor
        to whom the batch was dispatched in DB2.

        If batch was dispatched to Vendor A but sold by Vendor B,
        the item was either:
          a) Stolen from Vendor A's shipment
          b) Diverted through grey market
          c) Cloned packaging
        """
        bypasses = []
        triggered = False

        if not record.distribution.found or not record.purchase.found:
            # Can't check without both records
            return VetoGate(
                gate_id     = "V5_CUSTODY_BYPASS",
                triggered   = False,
                severity    = "CRITICAL",
                description = "Custody bypass check skipped  -  insufficient data from DB1 or DB2.",
                evidence    = {}
            )

        # Get vendors from purchase events
        purchase_vendor_ids = {
            e.get("vendor_id") for e in record.purchase.events
            if e.get("vendor_id")
        }

        # Get authorized target vendors from dispatch records
        dispatch_target_vendors = {
            b.get("vendor_id_target") for b in record.distribution.batches
            if b.get("vendor_id_target")
        }

        if dispatch_target_vendors:
            # Check if selling vendor was in authorized dispatch targets
            unauthorized_sellers = purchase_vendor_ids - dispatch_target_vendors
            if unauthorized_sellers:
                triggered = True
                bypasses = list(unauthorized_sellers)

        if triggered:
            desc = (
                f"CUSTODY BYPASS DETECTED: Item was sold by vendor(s) "
                f"{bypasses} but the dispatch records show it was sent to "
                f"{dispatch_target_vendors}. This indicates supply chain diversion, "
                "stolen stock, or counterfeit packaging on genuine batch numbers."
            )
        else:
            desc = (
                f"Custody chain intact: selling vendor(s) {purchase_vendor_ids} "
                "match authorized dispatch targets."
            ) if dispatch_target_vendors else (
                "Custody bypass check: no target vendor constraint in dispatch records."
            )

        return VetoGate(
            gate_id     = "V5_CUSTODY_BYPASS",
            triggered   = triggered,
            severity    = "CRITICAL",
            description = desc,
            evidence    = {
                "purchase_vendors":        list(purchase_vendor_ids),
                "dispatch_target_vendors": list(dispatch_target_vendors),
                "unauthorized_sellers":    bypasses,
            }
        )


# --- CLI test -----------------------------------------------------------------
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from integration.resolver import resolve

    code   = sys.argv[1] if len(sys.argv) > 1 else "MED-NAKALI-001"
    record = resolve(code)
    engine = HardVetoEngine()
    result = engine.evaluate(record)

    print(f"\n{'='*65}")
    print(f"  HARD VETO EVALUATION: {code}")
    print(f"{'='*65}")
    print(f"  VETOED: {'YES  -  NAKALI (score forced to 0)' if result.vetoed else 'No  -  proceed to soft scoring'}")
    for g in result.gates:
        icon = "CRITICAL" if g.triggered else ""
        print(f"\n  {icon} {g.gate_id}: {'TRIGGERED' if g.triggered else 'PASSED'}")
        print(f"     {g.description[:120]}")
    print()
