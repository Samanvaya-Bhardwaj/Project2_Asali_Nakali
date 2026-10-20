#!/usr/bin/env python3
"""
seed_nosql_db1.py
-----------------
Generates and populates the native NoSQL Document Collection for DB1 (Retail Pharmacy POS).
In real-world retail networks, thousands of distributed POS terminals stream semi-structured
JSON documents into a central NoSQL / Document store (e.g. MongoDB, DocumentDB) with nested
vendor, location, and payment metadata.

This script creates 'data/nosql_store/db1_retail_pos.json' representing the native NoSQL document
collection for DB1, introducing true syntactic and structural heterogeneity into the architecture.

Phase 2: the collection is a mirror of the SQLite rows, so it is re-synced whenever those rows
change (an explorer write, a cleansing run, an undo). Documents that were inserted straight into
the collection, and so never came from SQLite, are preserved across a sync.
"""

from __future__ import annotations
import os, json, sqlite3

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOSQL_DIR = os.path.join(BASE, "data", "nosql_store")
SQLITE_DB1 = os.path.join(BASE, "databases", "db1_purchase_registry.sqlite")
OUTPUT_JSON = os.path.join(NOSQL_DIR, "db1_retail_pos.json")

MIRROR_ORIGIN = "sqlite_mirror"

# City coordinates mapping for real-world geospatial simulation
CITY_COORDS = {
    "Mumbai": {"lat": 19.0760, "lon": 72.8777, "state": "Maharashtra"},
    "Thane": {"lat": 19.2183, "lon": 72.9781, "state": "Maharashtra"},
    "Pune": {"lat": 18.5204, "lon": 73.8567, "state": "Maharashtra"},
    "Bengaluru": {"lat": 12.9716, "lon": 77.5946, "state": "Karnataka"},
    "New Delhi": {"lat": 28.6139, "lon": 77.2090, "state": "Delhi"},
    "Gurugram": {"lat": 28.4595, "lon": 77.0266, "state": "Haryana"},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867, "state": "Telangana"},
    "Chennai": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu"},
    "Kolkata": {"lat": 22.5726, "lon": 88.3639, "state": "West Bengal"},
}


def build_documents(db_path: str = SQLITE_DB1) -> list:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Fetch all vendors
    cur.execute("SELECT * FROM vendors")
    vendors_by_id = {r["vendor_id"]: dict(r) for r in cur.fetchall()}

    # Fetch all purchase events
    cur.execute("SELECT * FROM purchase_events ORDER BY scan_timestamp ASC")
    events = cur.fetchall()

    documents = []
    for ev in events:
        ev_dict = dict(ev)
        v = vendors_by_id.get(ev_dict["vendor_id"], {})
        city = v.get("location_county", "Unknown")
        coords = CITY_COORDS.get(city, {"lat": 20.5937, "lon": 78.9629, "state": "India"})

        # Build nested NoSQL Document Structure
        doc = {
            "_id": ev_dict["event_id"],
            "origin": MIRROR_ORIGIN,
            "scan_code": ev_dict["scan_code"],
            "item_identifier": ev_dict["scan_code"],
            "document_type": "retail_pos_scan",
            "pos_terminal": {
                "device_id": ev_dict.get("device_id") or "POS-DEFAULT-01",
                "scan_method": ev_dict.get("scan_method") or "barcode",
                "firmware_version": "v4.1.2-pos"
            },
            "dispensary": {
                "vendor_id": v.get("vendor_id") or ev_dict.get("vendor_id"),
                "vendor_name": v.get("vendor_name"),
                "vendor_type": v.get("vendor_type"),
                "license": {
                    "number": v.get("license_no"),
                    "expiry": v.get("license_expiry"),
                    "is_active": bool(v.get("active", 1))
                },
                "location": {
                    "city": city,
                    "street": v.get("location_street"),
                    "state": coords["state"],
                    "geo": {"lat": coords["lat"], "lon": coords["lon"]}
                },
                "contact": {
                    "phone": v.get("phone"),
                    "email": v.get("email")
                }
            },
            "transaction": {
                "timestamp_iso": ev_dict["scan_timestamp"],
                "price": {
                    "amount": float(ev_dict.get("price_paid") or 0.0),
                    "currency": ev_dict.get("currency") or "INR"
                },
                "quantity": int(ev_dict.get("quantity_bought") or 1),
                "payment_method": ev_dict.get("payment_method") or "cash",
                "customer_category": ev_dict.get("customer_age_group") or "adult"
            },
            "anomaly_telemetry": {
                "flagged": bool(ev_dict.get("anomaly_flag", 0)),
                "reason": ev_dict.get("anomaly_reason"),
                "notes": ev_dict.get("notes")
            }
        }
        if ev_dict.get("label_text") or ev_dict.get("label_image"):
            doc["label_capture"] = {"ocr_text": ev_dict.get("label_text"), "image": ev_dict.get("label_image")}
        documents.append(doc)

    conn.close()
    return documents


def sync_collection(db_path: str = SQLITE_DB1, out_path: str = OUTPUT_JSON) -> int:
    """Rebuild the mirror from SQLite, keeping documents that only ever lived in the collection."""
    docs = build_documents(db_path)
    mirrored = {d["_id"] for d in docs}
    native = []
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                native = [d for d in json.load(f)
                          if d.get("origin") != MIRROR_ORIGIN and d.get("_id") not in mirrored
                          and not str(d.get("_id", "")).startswith("PE-")]
        except (OSError, ValueError):
            native = []
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(docs + native, f, indent=2)
    return len(docs) + len(native)


def generate_nosql_collection():
    print("  Converting DB1 to Native NoSQL Document Collection...")
    n = sync_collection(SQLITE_DB1, OUTPUT_JSON)
    print(f"  [OK] Exported {n} NoSQL documents to: {OUTPUT_JSON}")


if __name__ == "__main__":
    generate_nosql_collection()
