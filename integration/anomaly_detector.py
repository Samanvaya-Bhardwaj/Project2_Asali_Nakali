#!/usr/bin/env python3
"""
anomaly_detector.py
-------------------
Advanced Anomaly Detection Engine for the Asali/Nakali system.

Detects suspicious patterns that individual DB checks cannot catch:
  1. Multi-location scan (barcode cloning)
  2. Temporal inconsistency (manufacture > dispatch > purchase order violated)
  3. Price anomaly (price far below MSRP -> suspected counterfeit)
  4. Velocity anomaly (too many units sold too fast for a single batch)
  5. Unlicensed vendor sales
  6. Supply chain gap (sold but never distributed)
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from integration.resolver import ItemRecord


@dataclass
class AnomalyFlag:
    anomaly_type: str
    severity:     str          # low / medium / high / critical
    description:  str
    evidence:     str
    score_impact: int          # additional score deduction

@dataclass
class AnomalyReport:
    item_code:    str
    flags:        list[AnomalyFlag] = field(default_factory=list)
    total_impact: int = 0
    clean:        bool = True


class AnomalyDetector:
    """
    Stateless anomaly detector  -  takes a resolved ItemRecord and
    returns an AnomalyReport with all detected suspicious patterns.
    """

    def detect(self, record: ItemRecord) -> AnomalyReport:
        report = AnomalyReport(item_code=record.item_code)
        flags  = []

        flags += self._check_multi_location(record)
        flags += self._check_temporal_consistency(record)
        flags += self._check_price_anomaly(record)
        flags += self._check_velocity(record)
        flags += self._check_unlicensed_vendor(record)
        flags += self._check_supply_chain_gap(record)
        flags += self._check_cold_chain_risk(record)

        report.flags        = flags
        report.total_impact = sum(f.score_impact for f in flags)
        report.clean        = len(flags) == 0
        return report

    # -- 1. Multi-location (barcode cloning) ----------------------------------
    def _check_multi_location(self, record: ItemRecord) -> list[AnomalyFlag]:
        flags = []
        events = record.purchase.events
        if len(events) < 2:
            return flags

        # Group events by date-hour window
        TIME_WINDOW_MINUTES = 60
        for i, e1 in enumerate(events):
            t1 = self._parse_dt(e1.get("scan_timestamp"))
            if not t1:
                continue
            nearby = []
            for e2 in events[i+1:]:
                t2 = self._parse_dt(e2.get("scan_timestamp"))
                if not t2:
                    continue
                diff_mins = abs((t2 - t1).total_seconds()) / 60
                if diff_mins <= TIME_WINDOW_MINUTES and e1.get("vendor_id") != e2.get("vendor_id"):
                    nearby.append((e2, diff_mins))

            if len(nearby) >= 2:
                vendor_list = [e1.get("vendor_id")] + [n[0].get("vendor_id") for n in nearby]
                flags.append(AnomalyFlag(
                    anomaly_type = "MULTI_LOCATION_SCAN",
                    severity     = "critical",
                    description  = "Barcode cloning detected",
                    evidence     = (
                        f"Item code '{record.item_code}' scanned at "
                        f"{len(vendor_list)} different vendor locations "
                        f"within {TIME_WINDOW_MINUTES} minutes. "
                        f"Locations: {', '.join(vendor_list)}. "
                        "A single physical unit cannot be at multiple locations simultaneously."
                    ),
                    score_impact = -25
                ))
                break   # one flag per item is sufficient
        return flags

    # -- 2. Temporal consistency -----------------------------------------------
    def _check_temporal_consistency(self, record: ItemRecord) -> list[AnomalyFlag]:
        flags = []
        prod  = record.manufacturer.product
        if not prod:
            return flags

        mfg_date = self._parse_date(prod.get("manufacture_date"))
        if not mfg_date:
            return flags

        for batch in record.distribution.batches:
            disp_date = self._parse_date(batch.get("dispatch_date"))
            if disp_date and disp_date < mfg_date:
                flags.append(AnomalyFlag(
                    anomaly_type = "TEMPORAL_INCONSISTENCY",
                    severity     = "critical",
                    description  = "Dispatch date before manufacture date",
                    evidence     = (
                        f"Distribution batch '{batch.get('batch_id')}' dispatched on {disp_date} "
                        f"but product was only manufactured on {mfg_date}. "
                        "Impossible  -  this is a physical impossibility indicating a forged timestamp."
                    ),
                    score_impact = -20
                ))

        for event in record.purchase.events:
            sale_date = self._parse_date(event.get("scan_timestamp","")[:10])
            if sale_date and mfg_date and sale_date < mfg_date:
                flags.append(AnomalyFlag(
                    anomaly_type = "TEMPORAL_INCONSISTENCY",
                    severity     = "high",
                    description  = "Sale date before manufacture date",
                    evidence     = (
                        f"Item sold on {sale_date} but manufactured on {mfg_date}. "
                        "Cannot sell something before it is manufactured  -  forged date or wrong code."
                    ),
                    score_impact = -15
                ))
        return flags

    # -- 3. Price anomaly ------------------------------------------------------
    def _check_price_anomaly(self, record: ItemRecord) -> list[AnomalyFlag]:
        flags = []
        prod  = record.manufacturer.product
        if not prod or not prod.get("msrp_kes"):
            return flags

        msrp = float(prod["msrp_kes"])
        for event in record.purchase.events:
            price = event.get("price_paid")
            if price is None:
                continue
            price = float(price)
            qty   = max(int(event.get("quantity_bought", 1)), 1)
            unit_price = price / qty

            # Too cheap: < 40% of MSRP -> strongly suspicious
            if msrp > 0 and unit_price < (msrp * 0.4):
                flags.append(AnomalyFlag(
                    anomaly_type = "PRICE_ANOMALY_LOW",
                    severity     = "high",
                    description  = "Price far below manufacturer's suggested retail price",
                    evidence     = (
                        f"Unit price paid: KES {unit_price:.2f}. "
                        f"Manufacturer MSRP: KES {msrp:.2f}. "
                        f"Price is {(unit_price/msrp*100):.1f}% of MSRP. "
                        "Extremely low prices are a hallmark of counterfeit medicines "
                        "where production costs are negligible (no real API used)."
                    ),
                    score_impact = -10
                ))
            # Too expensive: > 300% of MSRP -> price gouging
            elif msrp > 0 and unit_price > (msrp * 3):
                flags.append(AnomalyFlag(
                    anomaly_type = "PRICE_ANOMALY_HIGH",
                    severity     = "medium",
                    description  = "Price far above MSRP (price gouging)",
                    evidence     = (
                        f"Unit price: KES {unit_price:.2f}. MSRP: KES {msrp:.2f}. "
                        f"Marked up {(unit_price/msrp*100):.1f}% above MSRP."
                    ),
                    score_impact = -5
                ))
        return flags

    # -- 4. Velocity anomaly ---------------------------------------------------
    def _check_velocity(self, record: ItemRecord) -> list[AnomalyFlag]:
        flags = []
        total_sold = sum(e.get("quantity_bought", 0) for e in record.purchase.events)
        total_dist = sum(b.get("quantity_received", 0) or 0 for b in record.distribution.batches)

        if total_dist > 0 and total_sold > total_dist * 1.2:
            flags.append(AnomalyFlag(
                anomaly_type = "VELOCITY_ANOMALY",
                severity     = "high",
                description  = "Units sold exceed units distributed",
                evidence     = (
                    f"Total units sold (DB1): {total_sold}. "
                    f"Total units distributed (DB2): {total_dist}. "
                    f"Sales exceed distribution by {total_sold - total_dist} units ({((total_sold/total_dist-1)*100):.1f}%). "
                    "This suggests additional counterfeit units in circulation beyond the legitimate batch."
                ),
                score_impact = -15
            ))
        return flags

    # -- 5. Unlicensed vendor --------------------------------------------------
    def _check_unlicensed_vendor(self, record: ItemRecord) -> list[AnomalyFlag]:
        flags = []
        unlicensed_sales = [
            e for e in record.purchase.events
            if e.get("vendor_active") == 0 or e.get("vendor_license") == "NONE"
        ]
        if unlicensed_sales:
            vendor_ids = list(set(e.get("vendor_id") for e in unlicensed_sales))
            flags.append(AnomalyFlag(
                anomaly_type = "UNLICENSED_VENDOR_SALE",
                severity     = "high",
                description  = "Item sold at unlicensed vendor",
                evidence     = (
                    f"Item found being sold at {len(unlicensed_sales)} event(s) "
                    f"at unlicensed vendor(s): {', '.join(vendor_ids)}. "
                    "Only licensed pharmacies and medical outlets may legally sell medicines."
                ),
                score_impact = -10
            ))
        return flags

    # -- 6. Supply chain gap ---------------------------------------------------
    def _check_supply_chain_gap(self, record: ItemRecord) -> list[AnomalyFlag]:
        flags = []
        if record.purchase.found and not record.distribution.found:
            flags.append(AnomalyFlag(
                anomaly_type = "SUPPLY_CHAIN_GAP",
                severity     = "critical",
                description  = "Item at retail with no distribution record",
                evidence     = (
                    f"Item '{record.item_code}' appears in {len(record.purchase.events)} "
                    "purchase event(s) in DB1 but has ZERO records in the distributor ledger (DB2). "
                    "Every legitimate medicine must be traceable through at least one licensed distributor. "
                    "This item appears to have bypassed the entire regulated supply chain."
                ),
                score_impact = -20
            ))
        return flags

    # -- 7. Cold chain risk ----------------------------------------------------
    def _check_cold_chain_risk(self, record: ItemRecord) -> list[AnomalyFlag]:
        flags = []
        prod = record.manufacturer.product
        if not prod or not prod.get("requires_cold_chain"):
            return flags
        broken = [b for b in record.distribution.batches if b.get("cold_chain_maintained") == 0]
        if broken:
            flags.append(AnomalyFlag(
                anomaly_type = "COLD_CHAIN_VIOLATION",
                severity     = "high",
                description  = "Cold chain broken for temperature-sensitive medicine",
                evidence     = (
                    f"Product requires cold storage ({prod.get('storage_temp_min')} degC - "
                    f"{prod.get('storage_temp_max')} degC). "
                    f"{len(broken)} distribution batch(es) did not maintain cold chain. "
                    "Potency and safety may be compromised even if the item is technically 'genuine'."
                ),
                score_impact = -10
            ))
        return flags

    # -- Helpers ---------------------------------------------------------------
    @staticmethod
    def _parse_dt(s) -> Optional[datetime]:
        if not s:
            return None
        try:
            return datetime.fromisoformat(str(s)[:19])
        except:
            return None

    @staticmethod
    def _parse_date(s) -> Optional[date]:
        if not s:
            return None
        try:
            return date.fromisoformat(str(s)[:10])
        except:
            return None


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from integration.resolver import resolve

    code   = sys.argv[1] if len(sys.argv) > 1 else "MED-NAKALI-001"
    record = resolve(code)
    det    = AnomalyDetector()
    report = det.detect(record)

    print(f"\n  Anomaly Report for {code}:")
    print(f"  Clean: {report.clean}  |  Total score impact: {report.total_impact}")
    for flag in report.flags:
        print(f"    [{flag.severity.upper()}] {flag.anomaly_type}: {flag.description}")
        print(f"      {flag.evidence[:100]}...")
