#!/usr/bin/env python3
"""
seed_db1.py - Purchase / Scan Registry (DB1)
Uses scan_code as the integration key (same value as product_uid / batch_serial).

Vendors:
  VND-001..006 - licensed, active Indian pharmacies/hospitals
  VND-007..009 - unlicensed / suspicious kiosks
"""

import sqlite3, os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "databases", "db1_purchase_registry.sqlite")

VENDORS = [
    ("VND-001", "Apollo Pharmacy", "pharmacy", "Mumbai", "Hill Road, Bandra West", "FDA/MH/PH/001/2019", "2028-06-30", "+91-22-26401111", "bandra@apollopharmacy.org", 1, "2019-06-01"),
    ("VND-002", "MedPlus Pharmacy", "pharmacy", "Bengaluru", "100ft Road, Indiranagar", "FDA/KA/PH/002/2020", "2027-12-31", "+91-80-25202222", "indiranagar@medplusindia.com", 1, "2020-01-15"),
    ("VND-003", "AIIMS Hospital Dispensary", "hospital", "New Delhi", "Ansari Nagar", "FDA/DL/PH/003/2018", "2029-03-31", "+91-11-26593333", "dispensary@aiims.edu", 1, "2018-03-01"),
    ("VND-004", "Wellness Forever Chemist", "pharmacy", "New Delhi", "Connaught Place", "FDA/DL/PH/004/2021", "2027-06-30", "+91-11-23304444", "cp@wellnessforever.in", 1, "2021-06-01"),
    ("VND-005", "Noble Chemist", "pharmacy", "Mumbai", "Dadar TT Circle", "FDA/MH/PH/005/2019", "2028-09-30", "+91-22-24105555", "dadar@noblechemist.com", 1, "2019-09-01"),
    ("VND-006", "Fortis Healthworld Pharmacy", "clinic", "Gurugram", "Sector 44", "FDA/HR/PH/006/2022", "2027-08-31", "+91-124-4906666", "pharmacy@fortishealthcare.com", 1, "2022-08-01"),
    # Suspect / unlicensed vendors
    ("VND-007", "Janata Medicos (Unlicensed Kiosk)", "kiosk", "Mumbai", "Kurla Station Road", None, "2020-01-01", "+91-9820999007", "janata@nomail.com", 0, "2019-01-01"),
    ("VND-008", "QuickRelief Kiosk", "kiosk", "New Delhi", "Chandni Chowk Market", None, "2020-01-01", "+91-9810999008", "quickrelief@nomail.com", 0, "2019-01-01"),
    ("VND-009", "Suburban Chemist Stall", "kiosk", "Thane", "Thane West Station", None, "2020-01-01", "+91-9833999009", "suburban@nomail.com", 0, "2019-01-01"),
]

PURCHASE_EVENTS = [
    # ---- ASALI purchases (normal) ----
    ("PE-20250310-0001", "MED-ASALI-001", "2025-03-10 09:15:00", "VND-001", "adult", 2, 230.0, "INR", "upi", "barcode", "POS-001-A", 0, None, None),
    ("PE-20250310-0002", "MED-ASALI-002", "2025-03-10 10:30:00", "VND-001", "adult", 1, 32.0, "INR", "cash", "barcode", "POS-001-A", 0, None, None),
    ("PE-20250322-0003", "MED-ASALI-003", "2025-03-22 14:00:00", "VND-003", "senior", 1, 140.0, "INR", "insurance", "qrcode", "POS-003-B", 0, None, None),
    ("PE-20250312-0004", "MED-ASALI-004", "2025-03-12 11:30:00", "VND-004", "adult", 3, 840.0, "INR", "upi", "qrcode", "POS-004-C", 0, None, None),
    ("PE-20250418-0005", "MED-ASALI-005", "2025-04-18 16:45:00", "VND-002", "senior", 1, 180.0, "INR", "card", "barcode", "POS-002-A", 0, None, None),
    ("PE-20250315-0006", "MED-ASALI-006", "2025-03-15 08:00:00", "VND-006", "child", 2, 44.0, "INR", "cash", "barcode", "POS-006-A", 0, None, None),
    ("PE-20250528-0007", "MED-ASALI-007", "2025-05-28 12:15:00", "VND-005", "adult", 1, 95.0, "INR", "upi", "qrcode", "POS-005-B", 0, None, None),
    ("PE-20250412-0008", "MED-ASALI-008", "2025-04-12 09:00:00", "VND-001", "adult", 2, 170.0, "INR", "cash", "barcode", "POS-001-A", 0, None, None),
    ("PE-20250615-0009", "MED-ASALI-009", "2025-06-15 10:00:00", "VND-003", "senior", 1, 850.0, "INR", "insurance", "nfc", "POS-003-B", 0, None, "Insulin dispensed via hospital cold storage"),
    ("PE-20250428-0010", "MED-ASALI-010", "2025-04-28 11:30:00", "VND-006", "adult", 1, 340.0, "INR", "upi", "barcode", "POS-006-A", 0, None, None),
    # ---- NAKALI purchases ----
    ("PE-20250310-0011", "MED-NAKALI-001", "2025-03-10 09:30:00", "VND-007", "adult", 5, 45.0, "INR", "cash", "manual", "POS-007-X", 1, "unregistered_vendor", "Suspicious low price for antibiotic"),
    ("PE-20250311-0012", "MED-NAKALI-002", "2025-03-11 14:30:00", "VND-007", "youth", 3, 15.0, "INR", "cash", "manual", "POS-007-X", 1, "unregistered_vendor", "Handwritten batch sticker"),
    ("PE-20250312-0013", "MED-NAKALI-003", "2025-03-12 10:00:00", "VND-008", "adult", 2, 90.0, "INR", "cash", "qrcode", "POS-008-X", 1, "unregistered_vendor", None),
    ("PE-20250315-0014", "MED-NAKALI-004", "2025-03-15 15:45:00", "VND-008", "adult", 4, 40.0, "INR", "cash", "barcode", "POS-008-X", 0, None, "Counterfeit packaging mimicking Ciplox"),
    ("PE-20250318-0015", "MED-NAKALI-005", "2025-03-18 11:00:00", "VND-009", "senior", 1, 250.0, "INR", "cash", "qrcode", "POS-009-X", 0, None, "Fake insulin pen sold at street stall"),
    # ---- RECALLED items still being sold ----
    ("PE-20250520-0016", "MED-RECALL-001", "2025-05-20 09:00:00", "VND-001", "adult", 1, 65.0, "INR", "upi", "barcode", "POS-001-A", 0, None, "Vendor unaware of CDSCO recall notice"),
    ("PE-20250325-0017", "MED-RECALL-002", "2025-03-25 14:00:00", "VND-005", "child", 1, 55.0, "INR", "insurance", "barcode", "POS-005-B", 0, None, None),
    ("PE-20250610-0018", "MED-RECALL-003", "2025-06-10 10:30:00", "VND-006", "adult", 2, 90.0, "INR", "cash", "barcode", "POS-006-A", 0, None, None),
    # ---- UNAUTHORIZED DIST items ----
    ("PE-20250405-0019", "MED-UNAUTH-001", "2025-04-05 21:00:00", "VND-007", "adult", 1, 48.0, "INR", "cash", "manual", "POS-007-X", 1, "unauthorized_distributor", "Schedule H1 sold without prescription"),
    ("PE-20250410-0020", "MED-UNAUTH-002", "2025-04-10 22:30:00", "VND-008", "youth", 2, 104.0, "INR", "cash", "manual", "POS-008-X", 1, "unauthorized_distributor", "Codeine syrup sold OTC"),
    # ---- ANOMALY: MED-ASALI-002 scanned at 5 different locations within 28 minutes ----
    ("PE-20250502-0021", "MED-ASALI-002", "2025-05-02 08:00:00", "VND-001", "adult", 1, 32.0, "INR", "cash", "barcode", "POS-001-A", 0, None, "Scan 1 of clone cluster (Bandra)"),
    ("PE-20250502-0022", "MED-ASALI-002", "2025-05-02 08:07:00", "VND-002", "adult", 1, 32.0, "INR", "card", "barcode", "POS-002-A", 1, "velocity_anomaly", "Scan 2 in Bengaluru (7 min later - physically impossible)"),
    ("PE-20250502-0023", "MED-ASALI-002", "2025-05-02 08:14:00", "VND-003", "adult", 1, 32.0, "INR", "cash", "barcode", "POS-003-B", 1, "velocity_anomaly", "Scan 3 in Delhi (14 min later)"),
    ("PE-20250502-0024", "MED-ASALI-002", "2025-05-02 08:21:00", "VND-004", "adult", 1, 32.0, "INR", "upi", "barcode", "POS-004-C", 1, "velocity_anomaly", "Scan 4 in Connaught Place (21 min later)"),
    ("PE-20250502-0025", "MED-ASALI-002", "2025-05-02 08:28:00", "VND-005", "adult", 1, 32.0, "INR", "cash", "barcode", "POS-005-B", 1, "velocity_anomaly", "Scan 5 in Dadar (28 min later - clone confirmed)"),
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM purchase_events;")
    cur.execute("DELETE FROM vendors;")

    cur.executemany("INSERT INTO vendors VALUES (?,?,?,?,?,?,?,?,?,?,?)", VENDORS)
    cur.executemany("INSERT INTO purchase_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", PURCHASE_EVENTS)

    conn.commit()
    conn.close()
    print("  db1_purchase_registry seeded successfully (India retail POS).")

if __name__ == "__main__":
    seed()
