#!/usr/bin/env python3
"""
nosql_wrapper.py
----------------
Wrapper for DB1: Retail Pharmacy POS System (NoSQL Document Store).

Translates canonical query requests into native NoSQL document queries.
Handles nested JSON document navigation:
  doc["dispensary"]["vendor_name"]
  doc["transaction"]["timestamp_iso"]
  doc["pos_terminal"]["device_id"]
"""

from __future__ import annotations
import os, json, time
from typing import Any, Dict, List, Optional
from .base_wrapper import BaseWrapper, SourceMetadata

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOSQL_FILE = os.path.join(BASE, "data", "nosql_store", "db1_retail_pos.json")


class NoSqlDocumentWrapper(BaseWrapper):
    """Wrapper querying the native NoSQL JSON document collection for DB1."""

    def __init__(self, doc_path: str = NOSQL_FILE):
        super().__init__("db1_purchase")
        self.doc_path = doc_path
        self._ensure_data()

    def _ensure_data(self):
        if not os.path.exists(self.doc_path):
            from data.seed_nosql_db1 import generate_nosql_collection
            generate_nosql_collection()

    def _load_documents(self) -> List[Dict[str, Any]]:
        self._ensure_data()
        try:
            with open(self.doc_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def get_metadata(self) -> SourceMetadata:
        exists = os.path.exists(self.doc_path)
        return SourceMetadata(
            source_id="db1_purchase",
            source_name="Retail Pharmacy POS Network",
            source_type="NoSQL Document Store",
            paradigm="Document-Oriented",
            protocol="JSON Document Store / Filter API",
            native_key="scan_code",
            status="ONLINE" if exists else "INITIALIZING",
            latency_ms=1.2
        )

    def query(self, canonical_key: str, native_filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes document query:
        filter: {"scan_code": canonical_key}
        """
        start = time.perf_counter()
        docs = self._load_documents()

        keys_to_match = {canonical_key.upper()}
        if native_filter and "aliases" in native_filter:
            for a in native_filter["aliases"]:
                if a:
                    keys_to_match.add(str(a).upper())

        # Native Document Query Filter
        matched_docs = [
            d for d in docs
            if d.get("scan_code", "").upper() in keys_to_match
            or d.get("item_identifier", "").upper() in keys_to_match
        ]

        latency = (time.perf_counter() - start) * 1000

        # Unpack / Project nested fields into canonical format
        events = []
        vendors = []
        anomalies = []

        for d in matched_docs:
            disp = d.get("dispensary", {})
            tx = d.get("transaction", {})
            pos = d.get("pos_terminal", {})
            telemetry = d.get("anomaly_telemetry", {})

            event_dict = {
                "event_id": d.get("_id"),
                "scan_code": d.get("scan_code"),
                "scan_timestamp": tx.get("timestamp_iso"),
                "vendor_id": disp.get("vendor_id"),
                "vendor_name": disp.get("vendor_name"),
                "vendor_type": disp.get("vendor_type"),
                "location_county": disp.get("location", {}).get("city"),
                "vendor_active": disp.get("license", {}).get("is_active", True),
                "vendor_license": disp.get("license", {}).get("number"),
                "price_paid": tx.get("price", {}).get("amount", 0.0),
                "currency": tx.get("price", {}).get("currency", "INR"),
                "quantity_bought": tx.get("quantity", 1),
                "payment_method": tx.get("payment_method"),
                "scan_method": pos.get("scan_method"),
                "device_id": pos.get("device_id"),
                "anomaly_flag": 1 if telemetry.get("flagged") else 0,
                "anomaly_reason": telemetry.get("reason"),
                "notes": telemetry.get("notes")
            }
            events.append(event_dict)

            # Vendor summary
            v_summary = {
                "vendor_id": disp.get("vendor_id"),
                "vendor_name": disp.get("vendor_name"),
                "vendor_type": disp.get("vendor_type"),
                "city": disp.get("location", {}).get("city"),
                "license_no": disp.get("license", {}).get("number")
            }
            if not any(v.get("vendor_id") == v_summary["vendor_id"] for v in vendors):
                vendors.append(v_summary)

            if telemetry.get("flagged"):
                anomalies.append({
                    "event_id": d.get("_id"),
                    "scan_code": d.get("scan_code"),
                    "vendor_id": disp.get("vendor_id"),
                    "anomaly_type": telemetry.get("reason") or "SCAN_ANOMALY",
                    "flagged_at": tx.get("timestamp_iso"),
                    "resolved": 0
                })

        return {
            "source_id": "db1_purchase",
            "native_query": f"db.retail_pos_scans.find({{'scan_code': '{canonical_key}'}})",
            "paradigm": "NoSQL Document Store",
            "found": len(events) > 0,
            "count": len(events),
            "events": events,
            "vendors": vendors,
            "anomalies": anomalies,
            "raw_documents": matched_docs,
            "execution_time_ms": round(latency, 2)
        }

    def health_check(self) -> bool:
        return os.path.exists(self.doc_path)
