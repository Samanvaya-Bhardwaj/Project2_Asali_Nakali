#!/usr/bin/env python3
"""
seed_db2.py - Distributor / Supplier Ledger (DB2)
Uses batch_serial as the integration key (same value as product_uid in DB3).

Distributors:
  DIST-001  Apollo Supply Chain Solutions Ltd   - authorized, national cold chain
  DIST-002  MedPlus Distribution Pvt Ltd        - authorized, South India
  DIST-003  Entero Healthcare Solutions Ltd     - authorized, North India
  DIST-004  QuickMed Traders                    - NOT authorized (unlicensed ghost distributor)
"""

import sqlite3, os
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "databases", "db2_distributor_ledger.sqlite")

DISTRIBUTORS = [
    ("DIST-001", "Apollo Supply Chain Solutions Ltd", "DL/MH/001/2018", date(2027, 12, 31), date(2018, 3, 15), "Western India", "Bhiwandi Central DC, Mumbai", "Mr. Rajesh Nair", "+91-22-26500001", "logistics@apollosupplychain.com", 1, 1, None),
    ("DIST-002", "MedPlus Distribution Pvt Ltd", "DL/TS/002/2016", date(2026, 10, 31), date(2016, 7, 1), "South India", "Kukatpally Logistics Hub, Hyderabad", "Mr. Venkat Rao", "+91-40-23000002", "dispatch@medplusindia.com", 0, 1, None),
    ("DIST-003", "Entero Healthcare Solutions Ltd", "DL/DL/003/2020", date(2027, 2, 28), date(2020, 1, 10), "North India", "Okhla Phase III Depot, New Delhi", "Ms. Shweta Gupta", "+91-11-26800003", "operations@enterohealthcare.com", 0, 1, None),
    ("DIST-004", "QuickMed Traders", "DL/INVALID/TEMP", date(2020, 1, 1), date(2019, 6, 1), "Unknown", "Unknown Premises, Kurla", "Unknown", "+91-9820000000", "quickmed@temporary.in", 0, 0, "Unlicensed wholesale broker blacklisted for illegal diversion"),
]

DISTRIBUTOR_VENDOR_CONTRACTS = [
    ("DVC-001", "DIST-001", "VND-001", date(2023, 1, 1), date(2027, 12, 31), "all", 1),
    ("DVC-002", "DIST-001", "VND-002", date(2022, 6, 1), date(2026, 5, 31), "antibiotic,analgesic", 1),
    ("DVC-003", "DIST-001", "VND-003", date(2023, 3, 1), date(2027, 2, 28), "all", 1),
    ("DVC-004", "DIST-002", "VND-004", date(2021, 1, 1), date(2026, 12, 31), "antimalarial,antibiotic", 1),
    ("DVC-005", "DIST-002", "VND-005", date(2022, 1, 1), date(2027, 12, 31), "all", 1),
    ("DVC-006", "DIST-003", "VND-006", date(2023, 6, 1), date(2027, 5, 31), "rehydration,supplement", 1),
]

DISTRIBUTION_BATCHES = [
    # ---- ASALI items via authorized distributors ----
    ("DBATCH-001", "MED-ASALI-001", "DIST-001", "MFG-001", "Mumbai Central DC", "VND-001", 200, 198, "2025-02-01", "2025-02-05", "2025-02-05", 1, None, "road", "MH-04-AB-1234", "delivered", 0, None),
    ("DBATCH-002", "MED-ASALI-001", "DIST-001", "MFG-001", "Mumbai Central DC", "VND-002", 150, 150, "2025-02-10", "2025-02-14", "2025-02-14", 1, None, "road", "MH-04-AB-1234", "delivered", 0, None),
    ("DBATCH-003", "MED-ASALI-002", "DIST-001", "MFG-002", "Mumbai Central DC", "VND-001", 300, 300, "2025-02-12", "2025-02-15", "2025-02-15", 1, None, "road", "MH-12-CD-5678", "delivered", 0, None),
    ("DBATCH-004", "MED-ASALI-003", "DIST-001", "MFG-003", "Mumbai Central DC", "VND-003", 100, 100, "2025-03-15", "2025-03-20", "2025-03-20", 1, None, "road", "MH-04-AB-1234", "delivered", 0, None),
    ("DBATCH-005", "MED-ASALI-004", "DIST-002", "MFG-002", "Hyderabad Hub", "VND-004", 250, 245, "2025-02-05", "2025-02-10", "2025-02-11", 1, None, "road", "TS-09-EF-9012", "delivered", 1, "5 units damaged in transit - credited"),
    ("DBATCH-006", "MED-ASALI-005", "DIST-001", "MFG-001", "Mumbai Central DC", "VND-002", 80, 80, "2025-04-10", "2025-04-14", "2025-04-14", 1, None, "road", "MH-12-CD-5678", "delivered", 0, None),
    ("DBATCH-007", "MED-ASALI-006", "DIST-003", "MFG-003", "Delhi NCR Depot", "VND-006", 400, 400, "2025-03-01", "2025-03-05", "2025-03-05", 1, None, "road", "DL-01-GH-3456", "delivered", 0, None),
    ("DBATCH-008", "MED-ASALI-007", "DIST-002", "MFG-001", "Hyderabad Hub", "VND-005", 120, 120, "2025-05-20", "2025-05-25", "2025-05-25", 1, None, "courier", "BlueDart Express", "delivered", 0, None),
    ("DBATCH-009", "MED-ASALI-008", "DIST-001", "MFG-003", "Mumbai Central DC", "VND-001", 180, 178, "2025-04-05", "2025-04-08", "2025-04-08", 1, None, "road", "MH-12-CD-5678", "delivered", 1, "2 units packaging crushed"),
    ("DBATCH-010", "MED-ASALI-009", "DIST-001", "MFG-004", "Mumbai Central DC", "VND-003", 50, 50, "2025-06-05", "2025-06-07", "2025-06-07", 0, "url://temp_telemetry_009", "air", "AI-864", "delivered", 1, "Thermal excursion to 14.2C logged in transit (exceeded 8C threshold)"),
    ("DBATCH-011", "MED-ASALI-010", "DIST-003", "MFG-003", "Delhi NCR Depot", "VND-006", 200, 200, "2025-04-20", "2025-04-24", "2025-04-24", 1, None, "road", "DL-01-GH-3456", "delivered", 0, None),
    # ---- NAKALI items via ghost distributor DIST-004 ----
    ("DBATCH-012", "MED-NAKALI-001", "DIST-004", "UNKNOWN", "?", "VND-007", 500, 500, "2025-01-10", "2025-01-15", "2025-01-15", 0, None, "road", "Unmarked Van", "delivered", 0, None),
    ("DBATCH-013", "MED-NAKALI-002", "DIST-004", "UNKNOWN", "?", "VND-007", 300, 300, "2025-02-01", "2025-02-06", "2025-02-06", 0, None, "road", "Unmarked Van", "delivered", 0, None),
    ("DBATCH-014", "MED-NAKALI-003", "DIST-004", "UNKNOWN", "?", "VND-008", 400, 400, "2025-03-01", "2025-03-06", "2025-03-06", 0, None, "road", "Unmarked Van", "delivered", 0, None),
    ("DBATCH-015", "MED-NAKALI-004", "DIST-004", "UNKNOWN", "?", "VND-008", 250, 250, "2025-04-01", "2025-04-06", "2025-04-06", 0, None, "road", "Unmarked Van", "delivered", 0, None),
    ("DBATCH-016", "MED-NAKALI-005", "DIST-004", "UNKNOWN", "?", "VND-009", 150, 150, "2025-05-01", "2025-05-06", "2025-05-06", 0, None, "road", "Unmarked Van", "delivered", 0, None),
    # ---- RECALLED items via authorized distributor ----
    ("DBATCH-017", "MED-RECALL-001", "DIST-001", "MFG-002", "Mumbai Central DC", "VND-001", 100, 100, "2024-09-01", "2024-09-05", "2024-09-05", 1, None, "road", "MH-04-AB-1234", "delivered", 0, None),
    ("DBATCH-018", "MED-RECALL-002", "DIST-002", "MFG-001", "Hyderabad Hub", "VND-005", 80, 80, "2024-07-10", "2024-07-14", "2024-07-14", 1, None, "road", "TS-09-EF-9012", "delivered", 0, None),
    ("DBATCH-019", "MED-RECALL-003", "DIST-003", "MFG-003", "Delhi NCR Depot", "VND-006", 150, 150, "2024-10-01", "2024-10-05", "2024-10-05", 1, None, "road", "DL-01-GH-3456", "delivered", 0, None),
    # ---- UNAUTHORIZED DIST items ----
    ("DBATCH-020", "MED-UNAUTH-001", "DIST-004", "MFG-002", "Unknown", "VND-007", 60, 60, "2025-03-01", "2025-03-05", "2025-03-05", 0, None, "road", "Unmarked Auto", "delivered", 0, "No Form 20B/21B narcotics transport permit on file"),
    ("DBATCH-021", "MED-UNAUTH-002", "DIST-004", "MFG-001", "Unknown", "VND-008", 40, 40, "2025-04-01", "2025-04-04", "2025-04-04", 0, None, "road", "Unmarked Auto", "delivered", 0, "Schedule H1 codeine diverted from licensed chain"),
]

RETURN_LOG = [
    ("RET-001", "MED-NAKALI-001", "VND-001", "2025-02-15", "suspected_fake", 50, 1, "Dispensary rejected suspect batch packaging"),
    ("RET-002", "MED-RECALL-001", "VND-001", "2025-05-22", "quality_issue", 20, 1, "Returned following CDSCO nationwide recall notice"),
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM return_log;")
    cur.execute("DELETE FROM distribution_batches;")
    cur.execute("DELETE FROM distributor_vendor_contracts;")
    cur.execute("DELETE FROM distributors;")

    cur.executemany("INSERT INTO distributors VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", DISTRIBUTORS)
    cur.executemany("INSERT INTO distributor_vendor_contracts VALUES (?,?,?,?,?,?,?)", DISTRIBUTOR_VENDOR_CONTRACTS)
    cur.executemany("INSERT INTO distribution_batches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", DISTRIBUTION_BATCHES)
    cur.executemany("INSERT INTO return_log VALUES (?,?,?,?,?,?,?,?)", RETURN_LOG)

    conn.commit()
    conn.close()
    print("  db2_distributor_ledger seeded successfully (India supply chain).")

if __name__ == "__main__":
    seed()
