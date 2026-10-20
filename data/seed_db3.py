#!/usr/bin/env python3
"""
seed_db3.py - Manufacturer Product Registry (DB3)
Seeded FIRST because all other DBs reference product_uid values.

Products:
  - 10 ASALI (genuine) - full metadata, valid CDSCO registrations
  - 5  NAKALI (fake)   - product_uid values that appear ONLY in DB1/DB2 (never in DB3)
  - 3  RECALLED        - genuine once, now recalled by CDSCO
  - 2  UNAUTHORIZED_DIST - genuine product but distributed by unauthorized party
"""

import sqlite3, os, hashlib, json
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(os.environ.get("ASALI_DB_DIR") or os.path.join(BASE, "databases"), "db3_manufacturer_registry.sqlite")

MANUFACTURERS = [
    ("MFG-001", "Cipla Ltd", "India", "Verna Industrial Estate, Goa", "MH/MFG/2018/001", date(2027, 12, 31), 1, "GMP-IN-001", date(2026, 6, 30), 1, "ISO9001-IN-001", 0, 1935, "Dr. Y. K. Hamied", "contact@cipla.com", "www.cipla.com"),
    ("MFG-002", "Sun Pharmaceutical Industries Ltd", "India", "Halol, Gujarat", "GJ/MFG/2015/002", date(2026, 8, 31), 1, "GMP-IN-002", date(2025, 12, 31), 1, "ISO9001-IN-002", 1, 1983, "Mr. Dilip Shanghvi", "reachus@sunpharma.com", "www.sunpharma.com"),
    ("MFG-003", "Dr. Reddy's Laboratories Ltd", "India", "Bolarum, Hyderabad", "TS/MFG/2019/003", date(2027, 3, 31), 1, "GMP-IN-003", date(2026, 9, 30), 0, None, 0, 1984, "Dr. K. Anji Reddy", "mail@drreddys.com", "www.drreddys.com"),
    ("MFG-004", "Biocon Biologics Ltd", "India", "Electronic City, Bengaluru", "KA/MFG/2017/004", date(2026, 12, 31), 1, "GMP-IN-004", date(2025, 6, 30), 0, None, 0, 1978, "Ms. Kiran Mazumdar-Shaw", "info@biocon.com", "www.biocon.com"),
]

PRODUCTS = [
    # --- ASALI (genuine, active) ---
    ("MED-ASALI-001", "Novamox 500mg", "Amoxycillin", "MFG-001", "antibiotic", "capsule", "500mg", "Strip of 10", "2025-01-15", "2027-01-14", "BATCH-A001", "CDSCO/MFG/001/2020", "J01CA04", "EAN-13", 15, 25, 0, 1, 0, None, None, None, 95.0, 115.0),
    ("MED-ASALI-002", "Pacimol 500mg", "Paracetamol", "MFG-002", "analgesic", "tablet", "500mg", "Strip of 15", "2025-02-10", "2027-02-09", "BATCH-A002", "CDSCO/MFG/002/2020", "N02BE01", "QR", 15, 25, 0, 0, 0, None, None, None, 25.0, 32.0),
    ("MED-ASALI-003", "Metsmall 850mg", "Metformin", "MFG-003", "antidiabetic", "tablet", "850mg", "Bottle of 30", "2025-03-05", "2027-03-04", "BATCH-A003", "CDSCO/MFG/003/2019", "A10BA02", "QR", 15, 25, 0, 1, 0, None, None, None, 110.0, 140.0),
    ("MED-ASALI-004", "Falcinil 80/480mg", "Artemether+Lumefantrine", "MFG-002", "antimalarial", "tablet", "80mg+480mg", "Pack of 24", "2025-01-20", "2026-07-19", "BATCH-A004", "CDSCO/MFG/004/2021", "P01BF01", "DataMatrix", 15, 25, 0, 1, 0, None, None, None, 220.0, 280.0),
    ("MED-ASALI-005", "Atorva 40mg", "Atorvastatin", "MFG-001", "cardiovascular", "tablet", "40mg", "Strip of 15", "2025-04-01", "2027-03-31", "BATCH-A005", "CDSCO/MFG/005/2020", "C10AA05", "QR", 15, 25, 0, 1, 0, None, None, None, 145.0, 180.0),
    ("MED-ASALI-006", "Electral ORS", "ORS Formula", "MFG-003", "rehydration", "powder", "WHO formula", "Sachet 21.8g", "2025-02-15", "2027-02-14", "BATCH-A006", "CDSCO/MFG/006/2022", "A07CA", "EAN-13", 15, 35, 0, 0, 0, None, None, None, 18.0, 22.0),
    ("MED-ASALI-007", "Ciplox 500mg", "Ciprofloxacin", "MFG-001", "antibiotic", "tablet", "500mg", "Strip of 10", "2025-05-10", "2027-05-09", "BATCH-A007", "CDSCO/MFG/007/2020", "J01MA02", "QR", 15, 25, 0, 1, 0, None, None, None, 75.0, 95.0),
    ("MED-ASALI-008", "Omez 20mg", "Omeprazole", "MFG-003", "antacid", "capsule", "20mg", "Strip of 15", "2025-03-20", "2027-03-19", "BATCH-A008", "CDSCO/MFG/008/2019", "A02BC01", "QR", 15, 25, 0, 0, 0, None, None, None, 68.0, 85.0),
    ("MED-ASALI-009", "Basalog 100 IU/ml", "Insulin glargine", "MFG-004", "antidiabetic", "injection", "100 IU/ml", "Pen 3ml", "2025-06-01", "2026-06-01", "BATCH-A009", "CDSCO/MFG/009/2021", "A10AE04", "DataMatrix", 2, 8, 1, 1, 0, None, None, None, 680.0, 850.0),
    ("MED-ASALI-010", "Calcirol 1000 IU", "Cholecalciferol", "MFG-003", "supplement", "tablet", "1000IU", "Bottle of 60", "2025-04-15", "2027-04-14", "BATCH-A010", "CDSCO/MFG/010/2022", "A11CC05", "EAN-13", 15, 25, 0, 0, 0, None, None, None, 275.0, 340.0),
    # --- RECALLED ---
    ("MED-RECALL-001", "Coughcure Syrup 100ml [RECALLED]", "Dextromethorphan Syrup", "MFG-002", "cough", "syrup", "10mg/5ml", "Bottle 100ml", "2024-08-01", "2026-07-31", "BATCH-R001", "CDSCO/MFG/011/2018", "R05DA09", "EAN-13", 15, 25, 0, 0, 1, "2025-05-20", "Diethylene glycol contamination above permissible limit", "Central Drugs Standard Control Organisation", 50.0, 65.0),
    ("MED-RECALL-002", "Amoxiclav 250mg Suspension [RECALLED]", "Amoxycillin+Clavulanate", "MFG-001", "antibiotic", "syrup", "250mg/5ml", "Bottle 60ml", "2024-06-01", "2026-05-31", "BATCH-R002", "CDSCO/MFG/012/2017", "J01CA04", "QR", 2, 8, 1, 0, 1, "2025-03-10", "Microbial contamination detected in reconstituted oral suspension", "Central Drugs Standard Control Organisation", 42.0, 55.0),
    ("MED-RECALL-003", "Metrogyl 400mg [RECALLED]", "Metronidazole", "MFG-003", "antiprotozoal", "tablet", "400mg", "Strip of 10", "2024-09-01", "2026-08-31", "BATCH-R003", "CDSCO/MFG/013/2019", "P01AB01", "EAN-13", 15, 25, 0, 1, 1, "2025-07-15", "Sub-potent active ingredient dissolution failure", "Central Drugs Standard Control Organisation", 35.0, 45.0),
    # --- UNAUTHORIZED DIST ---
    ("MED-UNAUTH-001", "Valium 5mg", "Diazepam", "MFG-002", "sedative", "tablet", "5mg", "Strip of 10", "2025-02-01", "2027-01-31", "BATCH-U001", "CDSCO/MFG/014/2020", "N05BA01", "QR", 15, 25, 0, 2, 0, None, None, None, 38.0, 48.0),
    ("MED-UNAUTH-002", "Corex Cough Syrup", "Codeine phosphate", "MFG-001", "analgesic", "syrup", "10mg/5ml", "Bottle 100ml", "2025-03-01", "2027-02-28", "BATCH-U002", "CDSCO/MFG/015/2018", "N02AA59", "EAN-13", 15, 25, 0, 2, 0, None, None, None, 40.0, 52.0),
]

AUTHORIZED_DISTRIBUTORS = [
    ("AUTH-001", "MFG-001", "DIST-001", date(2022, 1, 1), date(2027, 12, 31), "Maharashtra, Western India", "antibiotic,analgesic,antacid,cardiovascular", 1),
    ("AUTH-002", "MFG-001", "DIST-002", date(2021, 6, 1), date(2026, 6, 30), "South India Region", "antibiotic,analgesic", 1),
    ("AUTH-003", "MFG-002", "DIST-001", date(2023, 1, 1), date(2028, 12, 31), "Pan India", "antimalarial,antidiabetic,antibiotic,cough", 1),
    ("AUTH-004", "MFG-003", "DIST-003", date(2022, 3, 1), date(2027, 2, 28), "North India Depot", "antidiabetic,supplement,rehydration,antiprotozoal", 1),
    ("AUTH-005", "MFG-004", "DIST-001", date(2023, 1, 1), date(2028, 12, 31), "National Cold Chain", "antidiabetic,injection,biologics", 1),
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM authorized_distributors;")
    cur.execute("DELETE FROM products;")
    cur.execute("DELETE FROM manufacturers;")

    cur.executemany("""
        INSERT INTO manufacturers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, MANUFACTURERS)

    for p in PRODUCTS:
        cur.execute("""
            INSERT INTO products VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
        """, p)

    cur.executemany("""
        INSERT INTO authorized_distributors VALUES (?,?,?,?,?,?,?,?)
    """, AUTHORIZED_DISTRIBUTORS)

    conn.commit()
    conn.close()
    print("  db3_manufacturer_registry seeded successfully (India pharma entities).")

if __name__ == "__main__":
    seed()
