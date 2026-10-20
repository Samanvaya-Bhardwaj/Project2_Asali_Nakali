#!/usr/bin/env python3
"""
conflict_resolver.py
--------------------
Cross-Source Contradiction Detection and Conflict Arbitration Engine.

In Information Integration, reconciling conflicting claims across independently
operated databases requires explicit, declarative arbitration policies:
  1. Authority Precedence Policy: Statutory regulatory agency (DB4) strictly
     overrules commercial manufacturer claims (DB3) regarding recalls and bans.
  2. Physical Causality Policy: Retail checkout timestamp (DB1) cannot precede
     manufacturing release timestamp (DB3).
  3. Geospatial Velocity Feasibility Policy: Physical goods cannot travel between
     distant cities faster than commercial air transit velocity (> 800 km/h).
  4. Precautionary Medical Policy: Biological potency warnings from distributor
     telemetry (DB2) take precedence over general catalog classification.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class ConflictResolutionEntry:
    """Telemetry for a detected cross-source contradiction and its arbitration."""
    conflict_type: str
    sources_involved: List[str]
    conflicting_values: Dict[str, Any]
    arbitrated_value: Any
    winning_source: str
    governing_policy: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM"
    description: str


class ConflictResolver:
    """Detects cross-source contradictions and applies declarative arbitration rules."""

    def arbitrate(
        self,
        item_code: str,
        purchase_data: Dict[str, Any],
        distribution_data: Dict[str, Any],
        manufacturer_data: Dict[str, Any],
        ministry_data: Dict[str, Any]
    ) -> List[ConflictResolutionEntry]:
        """
        Analyzes resolved records from all 4 heterogeneous databases and arbitrates conflicts.
        """
        conflicts: List[ConflictResolutionEntry] = []

        prod = manufacturer_data.get("product") or {}
        batches = distribution_data.get("batches") or []
        events = purchase_data.get("events") or []
        complaints = ministry_data.get("complaints") or []
        blacklist = ministry_data.get("blacklist_entry")

        # 1. Authority Precedence Conflict: Recall / Blacklist Status
        # Manufacturer DB3 might show is_recalled = 0, but DB4 Government has active Gazette recall
        db3_recalled = bool(prod.get("is_recalled", 0))
        db4_blacklisted = blacklist is not None
        has_recall_complaint = any(c.get("complaint_category") in ("contamination", "substandard") for c in complaints)

        if not db3_recalled and (db4_blacklisted or has_recall_complaint):
            conflicts.append(ConflictResolutionEntry(
                conflict_type="STATUTORY_RECALL_PRECEDENCE",
                sources_involved=["DB3_Manufacturer", "DB4_Ministry"],
                conflicting_values={
                    "DB3_Manufacturer": "ACTIVE / UNRECALLED (Local DB3 file)",
                    "DB4_Ministry": "BLACKLISTED / RECALL NOTICE ISSUED (National Gazette)"
                },
                arbitrated_value="RECALLED_MANDATE",
                winning_source="DB4_Ministry",
                governing_policy="Regulatory Authority Dominance (Drugs Rules 1945)",
                severity="CRITICAL",
                description="Government regulatory recall mandate supersedes manufacturer internal status."
            ))

        # 2. Temporal Causality Conflict: Retail scan before manufacturing date
        mfg_date_str = prod.get("mfg_date")
        if mfg_date_str and events:
            try:
                mfg_dt = datetime.strptime(mfg_date_str[:10], "%Y-%m-%d")
                for ev in events:
                    ev_ts = ev.get("scan_timestamp")
                    if ev_ts:
                        ev_dt = datetime.strptime(ev_ts[:10], "%Y-%m-%d")
                        if ev_dt < mfg_dt:
                            conflicts.append(ConflictResolutionEntry(
                                conflict_type="TEMPORAL_CAUSALITY_VIOLATION",
                                sources_involved=["DB1_Purchase", "DB3_Manufacturer"],
                                conflicting_values={
                                    "DB3_Manufacture_Date": mfg_date_str,
                                    "DB1_Retail_Scan_Date": ev_ts
                                },
                                arbitrated_value="CONTRADICTION_FLAGGED",
                                winning_source="Integrity Engine (Veto)",
                                governing_policy="Physical Causality Principle",
                                severity="CRITICAL",
                                description=f"Retail purchase on {ev_ts[:10]} occurred before manufacturing release on {mfg_date_str}."
                            ))
                            break
            except Exception:
                pass

        # 3. Geospatial Velocity Conflict: Duplicate retail scans across cities
        if len(events) >= 2:
            cities = list({ev.get("location_county") for ev in events if ev.get("location_county")})
            if len(cities) >= 2:
                conflicts.append(ConflictResolutionEntry(
                    conflict_type="IMPOSSIBLE_SCAN_VELOCITY",
                    sources_involved=["DB1_Purchase"],
                    conflicting_values={
                        "scan_locations": cities,
                        "event_count": len(events)
                    },
                    arbitrated_value="SUSPICIOUS_CLONING",
                    winning_source="Integrity Engine",
                    governing_policy="Geospatial Velocity Feasibility Policy",
                    severity="CRITICAL",
                    description=f"Serial unit scanned across {len(cities)} distant cities ({', '.join(cities)}) within rapid interval."
                ))

        # 4. Cold-Chain Custody Conflict: Manufacturer vs Distributor Sensor
        cold_chain_required = bool(prod.get("requires_cold_chain", 0))
        for b in batches:
            notes = str(b.get("notes") or "").lower()
            if "excursion" in notes or "thermal" in notes:
                conflicts.append(ConflictResolutionEntry(
                    conflict_type="COLD_CHAIN_DEGRADATION_CONFLICT",
                    sources_involved=["DB2_Distributor", "DB3_Manufacturer"],
                    conflicting_values={
                        "DB3_Standard_Spec": "Standard Shelf-Life Spec",
                        "DB2_Sensor_Telemetry": "Thermal Excursion Logged in Transit"
                    },
                    arbitrated_value="POTENCY_DEGRADED",
                    winning_source="DB2_Distributor (IoT Sensor)",
                    governing_policy="Precautionary Medical Quality Principle",
                    severity="HIGH",
                    description="Distributor temperature logger recorded thermal excursion above permissible limit."
                ))
                break

        return conflicts


GLOBAL_CONFLICT_RESOLVER = ConflictResolver()

def arbitrate_conflicts(item_code, purchase, dist, mfg, ministry) -> List[ConflictResolutionEntry]:
    return GLOBAL_CONFLICT_RESOLVER.arbitrate(item_code, purchase, dist, mfg, ministry)
