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
"""

from __future__ import annotations
import os, json, sqlite3

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOSQL_DIR = os.path.join(BASE, "data", "nosql_store")
SQLITE_DB1 = os.path.join(BASE, "databases", "db1_purchase_registry.sqlite")
OUTPUT_JSON = os.path.join(NOSQL_DIR, "db1_retail_pos.json")

os.makedirs(NOSQL_DIR, exist_ok=True)

def generate_nosql_collection():
    print("  Converting DB1 to Native NoSQL Document Collection...")
    
    conn = sqlite3.connect(SQLITE_DB1)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Fetch all vendors
    cur.execute("SELECT * FROM vendors")
    vendors_by_id = {r["vendor_id"]: dict(r) for r in cur.fetchall()}
    
    # City coordinates mapping for real-world geospatial simulation
    CITY_COORDS = {
        "Mumbai": {"lat": 19.0760, "lon": 72.8777, "state": "Maharashtra"},
        "Bengaluru": {"lat": 12.9716, "lon": 77.5946, "state": "Karnataka"},
        "New Delhi": {"lat": 28.6139, "lon": 77.2090, "state": "Delhi"},
        "Hyderabad": {"lat": 17.3850, "lon": 78.4867, "state": "Telangana"},
        "Chennai": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu"}
    }
    
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
            "scan_code": ev_dict["scan_code"],
            "item_identifier": ev_dict["scan_code"],
            "document_type": "retail_pos_scan",
            "pos_terminal": {
                "device_id": ev_dict.get("device_id") or "POS-DEFAULT-01",
                "scan_method": ev_dict.get("scan_method") or "barcode",
                "firmware_version": "v4.1.2-pos"
            },
            "dispensary": {
                "vendor_id": v.get("vendor_id"),
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
        documents.append(doc)
    
    conn.close()
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump(documents, f, indent=2)
        
    print(f"  [OK] Exported {len(documents)} NoSQL documents to: {OUTPUT_JSON}")

if __name__ == "__main__":
    generate_nosql_collection()
