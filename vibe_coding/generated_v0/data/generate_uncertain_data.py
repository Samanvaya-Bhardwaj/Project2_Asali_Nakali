#!/usr/bin/env python3
"""
generate_uncertain_data.py
--------------------------
Phase 2 dataset: enough data, damaged in enough ways, to defend integration under
uncertainty.

Run after the curated seeds (seed_db1..4). It appends to the same four silos:

  DB3  6 more manufacturers, ~180 registered batches of 38 invented brands, and a
       handful of master-data duplicates (one batch registered twice)
  DB2  5 more distributors, ~350 shipments (some keyed in by hand, some
       re-imported twice, some with the wrong manufacturer), plus shipments of
       counterfeit stock by unlicensed traders
  DB1  29 more pharmacies (three registered twice), ~1,500 checkout scans captured
       by barcode, QR, hand entry or a phone camera reading the label, each
       channel failing in its own way; plus sales of counterfeit packs
  DB4  ~150 citizen complaints typed by hand, some filed twice, some with the code
       only in the free text; blacklist and alert entries for counterfeits

Every injected defect is recorded in data/generated/ground_truth.json, which the
matcher never reads. It exists so the benchmark and the cleanser can be scored.

Deterministic: the same seed always produces the same data.
"""

from __future__ import annotations
import json
import os
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from integration.uncertainty import paths
from integration.uncertainty.context import fold
from integration.uncertainty.noise import corrupt, corrupt_for_channel, ocr as ocr_noise, phonetic
from integration.uncertainty.standardize import canonical_code, label_text_for

SEED = 2026
LAST_SALE = date(2026, 10, 15)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

NEW_MANUFACTURERS = [
    ("MFG-005", "Lupin Ltd", "Andheri East, Mumbai", "MH/MFG/2016/005", "GMP-IN-005"),
    ("MFG-006", "Zydus Lifesciences Ltd", "SG Highway, Ahmedabad", "GJ/MFG/2014/006", "GMP-IN-006"),
    ("MFG-007", "Mankind Pharma Ltd", "Okhla Phase III, New Delhi", "DL/MFG/2017/007", "GMP-IN-007"),
    ("MFG-008", "Alkem Laboratories Ltd", "Lower Parel, Mumbai", "MH/MFG/2015/008", "GMP-IN-008"),
    ("MFG-009", "Torrent Pharmaceuticals Ltd", "Ashram Road, Ahmedabad", "GJ/MFG/2018/009", "GMP-IN-009"),
    ("MFG-010", "Glenmark Pharmaceuticals Ltd", "Mahakali Caves Road, Mumbai", "MH/MFG/2019/010", "GMP-IN-010"),
]

# generic, category, form, ATC, cold chain, shelf months, [(strength, MRP)], [(brand, manufacturer)]
MOLECULES = [
    ("Amoxycillin", "antibiotic", "capsule", "J01CA04", 0, 24, [("250mg", 62), ("500mg", 118)],
     [("Amoxilan", "MFG-005"), ("Moxivera", "MFG-008")]),
    ("Azithromycin", "antibiotic", "tablet", "J01FA10", 0, 36, [("250mg", 78), ("500mg", 132)],
     [("Azivista", "MFG-008"), ("Zithrolane", "MFG-007")]),
    ("Cefixime", "antibiotic", "tablet", "J01DD08", 0, 24, [("200mg", 109)], [("Cefirana", "MFG-005")]),
    ("Ciprofloxacin", "antibiotic", "tablet", "J01MA02", 0, 36, [("250mg", 48), ("500mg", 89)],
     [("Ciprovane", "MFG-009")]),
    ("Doxycycline", "antibiotic", "capsule", "J01AA02", 0, 24, [("100mg", 71)], [("Doxalyn", "MFG-010")]),
    ("Paracetamol", "analgesic", "tablet", "N02BE01", 0, 36, [("500mg", 24), ("650mg", 33)],
     [("Feverol", "MFG-007"), ("Paranova", "MFG-006")]),
    ("Ibuprofen", "analgesic", "tablet", "M01AE01", 0, 36, [("400mg", 38)], [("Ibunova", "MFG-006")]),
    ("Diclofenac", "analgesic", "tablet", "M01AB05", 0, 36, [("50mg", 42)], [("Diclotane", "MFG-009")]),
    ("Metformin", "antidiabetic", "tablet", "A10BA02", 0, 36, [("500mg", 36), ("1000mg", 64)],
     [("Glucovane", "MFG-009"), ("Metorin", "MFG-005")]),
    ("Glimepiride", "antidiabetic", "tablet", "A10BB12", 0, 24, [("1mg", 58), ("2mg", 96)], [("Glimora", "MFG-010")]),
    ("Sitagliptin", "antidiabetic", "tablet", "A10BH01", 0, 24, [("50mg", 212), ("100mg", 348)],
     [("Sitavia", "MFG-006")]),
    ("Insulin glargine", "antidiabetic", "injection", "A10AE04", 1, 18, [("100IU/ml", 812)], [("Glarvia", "MFG-004")]),
    ("Insulin aspart", "antidiabetic", "injection", "A10AB05", 1, 18, [("100IU/ml", 744)], [("Aspira", "MFG-006")]),
    ("Atorvastatin", "cardiovascular", "tablet", "C10AA05", 0, 36, [("10mg", 74), ("20mg", 128), ("40mg", 196)],
     [("Atorlane", "MFG-008")]),
    ("Rosuvastatin", "cardiovascular", "tablet", "C10AA07", 0, 36, [("10mg", 142), ("20mg", 236)],
     [("Rosuvane", "MFG-009")]),
    ("Amlodipine", "cardiovascular", "tablet", "C08CA01", 0, 36, [("5mg", 36), ("10mg", 62)], [("Amlovia", "MFG-005")]),
    ("Telmisartan", "cardiovascular", "tablet", "C09CA07", 0, 24, [("40mg", 96), ("80mg", 158)],
     [("Telmora", "MFG-010")]),
    ("Losartan", "cardiovascular", "tablet", "C09CA01", 0, 36, [("50mg", 68)], [("Losavane", "MFG-007")]),
    ("Metoprolol", "cardiovascular", "tablet", "C07AB02", 0, 36, [("25mg", 46), ("50mg", 79)], [("Metopra", "MFG-009")]),
    ("Clopidogrel", "cardiovascular", "tablet", "B01AC04", 0, 24, [("75mg", 118)], [("Clopivane", "MFG-008")]),
    ("Pantoprazole", "antacid", "tablet", "A02BC02", 0, 24, [("40mg", 112)],
     [("Pantora", "MFG-007"), ("Pantovia", "MFG-010")]),
    ("Omeprazole", "antacid", "capsule", "A02BC01", 0, 24, [("20mg", 54)], [("Omevane", "MFG-005")]),
    ("Famotidine", "antacid", "tablet", "A02BA03", 0, 36, [("20mg", 28), ("40mg", 44)], [("Famora", "MFG-006")]),
    ("Montelukast", "respiratory", "tablet", "R03DC03", 0, 24, [("10mg", 176)], [("Montelane", "MFG-010")]),
    ("Cetirizine", "antihistamine", "tablet", "R06AE07", 0, 36, [("10mg", 22)], [("Cetrova", "MFG-007")]),
    ("Levocetirizine", "antihistamine", "tablet", "R06AE09", 0, 36, [("5mg", 64)], [("Levocera", "MFG-008")]),
    ("Salbutamol", "respiratory", "inhaler", "R03AC02", 0, 24, [("100mcg", 158)], [("Salbuvane", "MFG-005")]),
    ("Hydroxychloroquine", "antimalarial", "tablet", "P01BA02", 0, 36, [("200mg", 92)], [("Hydrova", "MFG-006")]),
    ("Albendazole", "anthelmintic", "tablet", "P02CA03", 0, 36, [("400mg", 18)], [("Albenzo", "MFG-008")]),
    ("Ondansetron", "antiemetic", "tablet", "A04AA01", 0, 24, [("4mg", 54), ("8mg", 86)], [("Ondavia", "MFG-009")]),
    ("Cholecalciferol", "supplement", "capsule", "A11CC05", 0, 24, [("60000IU", 46)], [("Calcivane", "MFG-007")]),
    ("Levothyroxine", "thyroid", "tablet", "H03AA01", 0, 24, [("25mcg", 128), ("50mcg", 152), ("100mcg", 186)],
     [("Thyrova", "MFG-010")]),
    ("Prednisolone", "corticosteroid", "tablet", "H02AB06", 0, 36, [("5mg", 16), ("10mg", 27)], [("Predavia", "MFG-005")]),
    ("Hepatitis B vaccine", "vaccine", "injection", "J07BC01", 1, 18, [("20mcg/ml", 286)], [("Hepashield", "MFG-006")]),
    ("Erythropoietin", "biologic", "injection", "B03XA01", 1, 18, [("4000IU", 1490)], [("Epovia", "MFG-004")]),
]

PACK = {"tablet": "Strip of 10", "capsule": "Strip of 10", "injection": "Vial 1 x 3ml", "inhaler": "200 metered doses"}

NEW_VENDORS = [
    # id, name, type, city, street, licence
    ("VND-010", "HealthFirst Pharmacy", "pharmacy", "Mumbai", "Andheri East", "FDA/MH/PH/010/2021"),
    ("VND-011", "Sai Krupa Medical", "pharmacy", "Mumbai", "Ghatkopar West", "FDA/MH/PH/011/2020"),
    ("VND-012", "Lifeline Chemists", "pharmacy", "Mumbai", "Powai", "FDA/MH/PH/012/2022"),
    ("VND-013", "Pune Medico", "pharmacy", "Pune", "Kothrud", "FDA/MH/PH/013/2019"),
    ("VND-014", "Deccan Pharmacy", "pharmacy", "Pune", "FC Road", "FDA/MH/PH/014/2021"),
    ("VND-015", "Sahyadri Hospital Pharmacy", "hospital", "Pune", "Karve Road", "FDA/MH/PH/015/2018"),
    ("VND-016", "Nightingale Pharmacy", "pharmacy", "Bengaluru", "Koramangala", "FDA/KA/PH/016/2020"),
    ("VND-017", "HAL Road Hospital Dispensary", "hospital", "Bengaluru", "HAL Airport Road", "FDA/KA/PH/017/2019"),
    ("VND-018", "Sri Venkateshwara Medicals", "pharmacy", "Bengaluru", "Jayanagar", "FDA/KA/PH/018/2022"),
    ("VND-019", "Lajpat Medicos", "pharmacy", "New Delhi", "Lajpat Nagar", "FDA/DL/PH/019/2020"),
    ("VND-020", "Saket City Hospital Pharmacy", "hospital", "New Delhi", "Saket", "FDA/DL/PH/020/2019"),
    ("VND-021", "Karol Bagh Guardian Chemist", "pharmacy", "New Delhi", "Karol Bagh", "FDA/DL/PH/021/2021"),
    ("VND-022", "Charminar Medical Hall", "pharmacy", "Hyderabad", "Old City", "FDA/TS/PH/022/2020"),
    ("VND-023", "Banjara Care Pharmacy", "hospital", "Hyderabad", "Banjara Hills", "FDA/TS/PH/023/2018"),
    ("VND-024", "Jubilee Chemists", "pharmacy", "Hyderabad", "Jubilee Hills", "FDA/TS/PH/024/2022"),
    ("VND-025", "Marina Pharmacy", "pharmacy", "Chennai", "T Nagar", "FDA/TN/PH/025/2021"),
    ("VND-026", "Greams Road Hospital Dispensary", "hospital", "Chennai", "Greams Road", "FDA/TN/PH/026/2019"),
    ("VND-027", "Kapaleeshwarar Medicals", "pharmacy", "Chennai", "Mylapore", "FDA/TN/PH/027/2020"),
    ("VND-028", "Esplanade Medical Stores", "pharmacy", "Kolkata", "Esplanade", "FDA/WB/PH/028/2020"),
    ("VND-029", "Salt Lake City Pharmacy", "pharmacy", "Kolkata", "Salt Lake Sector V", "FDA/WB/PH/029/2021"),
    ("VND-030", "Howrah Chemists", "pharmacy", "Kolkata", "Howrah Maidan", "FDA/WB/PH/030/2019"),
    ("VND-031", "Cyber City Pharmacy", "pharmacy", "Gurugram", "DLF Cyber City", "FDA/HR/PH/031/2022"),
]
KIOSKS = [
    ("VND-032", "Footpath Medical Stall", "Kolkata", "Sealdah Station Road"),
    ("VND-033", "Night Bazaar Medicines", "Hyderabad", "Begum Bazaar"),
    ("VND-034", "Railway Kiosk Chemist", "Pune", "Pune Station"),
    ("VND-035", "Cheap Medicine Corner", "Chennai", "Parrys Corner"),
]
# The same pharmacy registered a second time with its licence typed differently.
VENDOR_DUPLICATES = [
    ("VND-036", "APOLLO PHARMACY - BANDRA W", "VND-001", "FDA-MH-PH-001-2019"),
    ("VND-037", "Medplus Pharmacy Indiranagar", "VND-002", "fda/ka/ph/002/2020"),
    ("VND-038", "Lifeline Chemist", "VND-012", "FDA MH PH 012 2022"),
]

NEW_DISTRIBUTORS = [
    ("DIST-005", "Shree Sai Pharma Distributors", "DL/MH/005/2017", "Western India", "Bhiwandi, Thane", 0, 1),
    ("DIST-006", "Southern Medilinks Pvt Ltd", "DL/KA/006/2018", "South India", "Hosur Road, Bengaluru", 1, 1),
    ("DIST-007", "Eastern Health Logistics", "DL/WB/007/2019", "East India", "Dankuni, Kolkata", 1, 1),
    ("DIST-008", "Capital Pharma Movers", "DL/DL/008/2016", "North India", "Narela, New Delhi", 1, 1),
    ("DIST-009", "Rapid Generic Traders", "DL/TEMP/UNVERIFIED", "Unknown", "Unknown premises", 0, 0),
]
CITY_DISTRIBUTORS = {
    "Mumbai": ["DIST-001", "DIST-005"], "Pune": ["DIST-005", "DIST-001"], "Thane": ["DIST-005"],
    "Bengaluru": ["DIST-002", "DIST-006"], "Hyderabad": ["DIST-006", "DIST-002"], "Chennai": ["DIST-006"],
    "New Delhi": ["DIST-003", "DIST-008"], "Gurugram": ["DIST-008", "DIST-003"], "Kolkata": ["DIST-007"],
}
COLD_DISTRIBUTOR = {"Mumbai": "DIST-001", "Pune": "DIST-001", "Thane": "DIST-001", "Bengaluru": "DIST-006",
                    "Hyderabad": "DIST-006", "Chennai": "DIST-006", "New Delhi": "DIST-008",
                    "Gurugram": "DIST-008", "Kolkata": "DIST-007"}
PLATE_STATE = {"Mumbai": "MH-01", "Pune": "MH-12", "Thane": "MH-04", "Bengaluru": "KA-03", "Hyderabad": "TS-09",
               "Chennai": "TN-07", "New Delhi": "DL-01", "Gurugram": "HR-26", "Kolkata": "WB-02"}

FIRST = ["Aarav", "Vivaan", "Aditya", "Ananya", "Diya", "Ishaan", "Kavya", "Rohan", "Priya", "Arjun", "Meera",
         "Sanjay", "Neha", "Rahul", "Pooja", "Vikram", "Sneha", "Karthik", "Lakshmi", "Imran", "Fatima", "Joseph",
         "Gurpreet", "Suresh", "Deepa", "Arnab", "Moumita", "Venkat", "Divya", "Farhan"]
LAST = ["Sharma", "Verma", "Iyer", "Nair", "Reddy", "Rao", "Patel", "Shah", "Desai", "Kulkarni", "Banerjee",
        "Chatterjee", "Das", "Singh", "Gill", "Khan", "Fernandes", "Menon", "Pillai", "Joshi", "Mehta", "Gupta"]
SYMPTOMS = ["a skin rash", "nausea", "dizziness", "stomach pain", "a headache", "severe itching"]


class Truth:
    def __init__(self):
        self.records = {}
        self.format = []
        self.duplicates = []
        self.conflicts = []
        self.missing = []
        self.outliers = []
        self.master_duplicates = []
        self.vendor_duplicates = []

    def rec(self, db, table, pk, true_uid, noise, field, stored):
        self.records[f"{db}:{table}:{pk}"] = {
            "true_uid": true_uid, "label": "GENUINE" if true_uid else "COUNTERFEIT",
            "noise": noise, "field": field, "stored": stored}

    def dump(self):
        kinds = Counter(r["noise"] for r in self.records.values())
        return {"seed": SEED, "generated_at": datetime.now().isoformat(timespec="seconds"),
                "note": "Evaluation only. The matcher and cleanser never read this file to make decisions.",
                "summary": {"records": len(self.records), "noise_kinds": dict(kinds),
                            "counterfeit_records": sum(1 for r in self.records.values() if not r["true_uid"]),
                            "format_defects": len(self.format), "duplicates": len(self.duplicates),
                            "conflicts": len(self.conflicts), "missing": len(self.missing),
                            "outliers": len(self.outliers), "master_duplicates": len(self.master_duplicates),
                            "vendor_duplicates": len(self.vendor_duplicates)},
                "records": self.records, "format": self.format, "duplicates": self.duplicates,
                "conflicts": self.conflicts, "missing": self.missing, "outliers": self.outliers,
                "master_duplicates": self.master_duplicates, "vendor_duplicates": self.vendor_duplicates}


def family_code(brand: str, taken: set) -> str:
    up = brand.upper()
    cons = up[0] + "".join(c for c in up[1:] if c not in "AEIOU")
    code = (cons + "".join(c for c in up[1:] if c in "AEIOU"))[:5]
    while code in taken or code in ("ASALI", "NAKAL", "RECAL", "UNAUT"):
        code = code[:4] + chr((ord(code[4]) - 65 + 1) % 26 + 65)
    taken.add(code)
    return code


def fmt_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def messy_datetime(dt: datetime, rng: random.Random, with_time: bool) -> str:
    style = rng.choice(["dmy", "dmy", "iso_t", "mon"])
    if style == "dmy":
        return dt.strftime("%d/%m/%Y %H:%M") if with_time else dt.strftime("%d/%m/%Y")
    if style == "iso_t":
        return dt.strftime("%Y-%m-%dT%H:%M:%S") if with_time else dt.strftime("%Y/%m/%d")
    return dt.strftime("%d-%b-%Y %H:%M") if with_time else dt.strftime("%d-%b-%Y")


def plate(city: str, rng: random.Random) -> str:
    return f"{PLATE_STATE[city]}-{rng.choice('ABCDEFGHJKMNPRSTUVWXYZ')}{rng.choice('ABCDEFGHJKMNPRSTUVWXYZ')}-{rng.randint(1000, 9999)}"


# ---------------------------------------------------------------------------

def main():
    rng = random.Random(SEED)
    truth = Truth()
    conns = {d: sqlite3.connect(paths.db_path(d)) for d in ("db1", "db2", "db3", "db4")}
    for c in conns.values():
        c.row_factory = sqlite3.Row
    c1, c2, c3, c4 = conns["db1"], conns["db2"], conns["db3"], conns["db4"]

    if c3.execute("SELECT 1 FROM manufacturers WHERE manufacturer_id = 'MFG-005'").fetchone():
        print("  Uncertain dataset already present. Rebuild with: python scripts/rebuild_data.py")
        return

    # --- curated rows get ground truth too ----------------------------------
    curated = {r["product_uid"] for r in c3.execute("SELECT product_uid FROM products")}
    for r in c1.execute("SELECT event_id, scan_code FROM purchase_events"):
        truth.rec("db1", "purchase_events", r["event_id"], r["scan_code"] if r["scan_code"] in curated else None,
                  "clean" if r["scan_code"] in curated else "counterfeit", "scan_code", r["scan_code"])
    for r in c2.execute("SELECT batch_id, batch_serial FROM distribution_batches"):
        truth.rec("db2", "distribution_batches", r["batch_id"], r["batch_serial"] if r["batch_serial"] in curated else None,
                  "clean" if r["batch_serial"] in curated else "counterfeit", "batch_serial", r["batch_serial"])
    for r in c4.execute("SELECT complaint_id, complaint_item_ref FROM complaints"):
        ref = r["complaint_item_ref"]
        truth.rec("db4", "complaints", r["complaint_id"], ref if ref in curated else None,
                  "clean" if ref in curated else "counterfeit", "complaint_item_ref", ref)

    # --- DB3: manufacturers, products ------------------------------------------
    for mid, name, addr, lic, gmp in NEW_MANUFACTURERS:
        c3.execute("""INSERT INTO manufacturers (manufacturer_id, company_name, country, physical_address, license_no,
                      license_expiry, gmp_certified, gmp_cert_number, gmp_cert_expiry, iso_certified, iso_cert_number,
                      founded_year, contact_email, website) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (mid, name, "India", addr, lic, "2029-03-31", 1, gmp, "2028-06-30", 1, f"ISO9001-IN-{mid[-3:]}",
                    rng.randint(1960, 2000), f"regulatory@{name.split()[0].lower()}.example.in",
                    f"www.{name.split()[0].lower()}.example.in"))

    products = []                     # dicts with every column plus helpers
    skus = []
    taken = set()
    reg_counter = 100
    for generic, cat, form, atc, cold, shelf, strengths, brands in MOLECULES:
        for brand, mfg in brands:
            fam = family_code(brand, taken)
            used_numbers = set()
            for strength, mrp in strengths:
                n_batches = rng.choice([2, 3, 3, 4])
                while True:
                    base = rng.randint(101, 880)
                    if all(abs(base - u) > 12 for u in used_numbers):
                        break
                used_numbers.add(base)
                mfg_date = date(2025, 1, 5) + timedelta(days=rng.randint(0, 330))
                sku = {"brand": brand, "strength": strength, "uids": []}
                for k in range(n_batches):
                    number = base + k
                    uid = f"MED-{fam}-{number:03d}"
                    exp = mfg_date + timedelta(days=int(shelf * 30.4))
                    if exp < date(2027, 1, 31):
                        exp = date(2027, 1, 31) + timedelta(days=rng.randint(0, 120))
                    reg_counter += 1
                    p = {
                        "product_uid": uid, "product_name": f"{brand} {strength}", "generic_name": generic,
                        "manufacturer_id": mfg, "category": cat, "dosage_form": form, "strength": strength,
                        "pack_size": PACK[form], "manufacture_date": mfg_date.isoformat(),
                        "expiry_date": exp.isoformat(),
                        "batch_number": f"{fam[:3]}{mfg_date.year % 100:02d}{number:03d}",
                        "registration_no": f"CDSCO/MFG/{reg_counter:04d}/{2018 + reg_counter % 7}",
                        "atc_code": atc, "barcode_type": rng.choice(["QR", "DataMatrix", "GS1-128", "EAN-13"]),
                        "storage_temp_min": 2 if cold else 15, "storage_temp_max": 8 if cold else 25,
                        "requires_cold_chain": cold, "controlled_substance": 0, "is_recalled": 0,
                        "unit_cost_kes": round(mrp * 0.78, 2), "msrp_kes": float(mrp),
                    }
                    products.append(p)
                    sku["uids"].append(uid)
                    mfg_date = mfg_date + timedelta(days=rng.randint(40, 90))
                    if mfg_date > date(2026, 6, 30):
                        break
                skus.append(sku)

    folded = {fold(u) for u in curated}
    for p in products:
        assert fold(p["product_uid"]) not in folded, f"fold collision {p['product_uid']}"
        folded.add(fold(p["product_uid"]))

    cols = list(products[0].keys())
    for p in products:
        c3.execute(f"INSERT INTO products ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                   [p[c] for c in cols])
    by_uid = {p["product_uid"]: p for p in products}
    sibling = {}
    for sku in skus:
        for i, u in enumerate(sku["uids"]):
            sibling[u] = [x for x in sku["uids"] if x != u]

    # Master-data duplicates: the same batch registered again under another code.
    dup_of = {}
    for p in rng.sample(products, 6):
        brand = p["product_name"].split()[0]
        alt_fam = brand.upper()[:5]
        dup_uid = f"MED-{alt_fam}-{p['product_uid'][-3:]}"
        if dup_uid in by_uid or dup_uid in curated or fold(dup_uid) in folded:
            continue
        folded.add(fold(dup_uid))
        d = dict(p)
        d["product_uid"] = dup_uid
        d["product_name"] = f"{brand.upper()} {p['strength'].replace('mg', ' MG').replace('mcg', ' MCG')}"
        d["strength"] = p["strength"].replace("mg", " mg")
        d["registration_no"] = p["registration_no"].replace("/", "-")
        c3.execute(f"INSERT INTO products ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                   [d[c] for c in cols])
        dup_of[dup_uid] = p["product_uid"]
        truth.master_duplicates.append({"dup": dup_uid, "survivor": p["product_uid"]})

    auth_id = 100
    for mid in [m[0] for m in NEW_MANUFACTURERS] + ["MFG-004"]:
        for did in ["DIST-001", "DIST-002", "DIST-003", "DIST-005", "DIST-006", "DIST-007", "DIST-008"]:
            auth_id += 1
            c3.execute("INSERT INTO authorized_distributors VALUES (?,?,?,?,?,?,?,?)",
                       (f"AUTH-{auth_id}", mid, did, "2023-01-01", "2028-12-31", "India", "all", 1))

    # --- DB1 vendors, DB2 distributors -----------------------------------------
    for vid, name, vtype, city, street, lic in NEW_VENDORS:
        c1.execute("INSERT INTO vendors VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (vid, name, vtype, city, street, lic, "2028-12-31", f"+91-{rng.randint(7000000000, 9999999999)}",
                    f"{name.split()[0].lower()}@example.in", 1, f"20{rng.randint(15, 22)}-0{rng.randint(1, 9)}-01"))
    for vid, name, city, street in KIOSKS:
        c1.execute("INSERT INTO vendors VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (vid, name, "kiosk", city, street, None, "2020-01-01", f"+91-{rng.randint(7000000000, 9999999999)}",
                    None, 0, "2021-01-01"))
    vendors = {r["vendor_id"]: dict(r) for r in c1.execute("SELECT * FROM vendors")}
    for vid, name, orig, lic in VENDOR_DUPLICATES:
        o = vendors[orig]
        c1.execute("INSERT INTO vendors VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (vid, name, o["vendor_type"], o["location_county"], o["location_street"], lic, o["license_expiry"],
                    o["phone"], o["email"], 1, "2024-11-15"))
        truth.vendor_duplicates.append({"dup": vid, "survivor": orig})
    licensed_by_city = defaultdict(list)
    for vid, v in vendors.items():
        if v["active"] and v["vendor_type"] != "kiosk" and vid >= "VND-010":
            licensed_by_city[v["location_county"]].append(vid)

    for did, name, lic, region, hq, cold_ok, authorised in NEW_DISTRIBUTORS:
        c2.execute("INSERT INTO distributors VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (did, name, lic, "2028-12-31" if authorised else "2021-01-01", "2016-04-01", region, hq,
                    "Operations desk", f"+91-{rng.randint(7000000000, 9999999999)}", f"ops@{did.lower()}.example.in",
                    cold_ok, authorised, None if authorised else "Licence never verified; diversion suspected"))
    dvc = 100
    for city, vids in licensed_by_city.items():
        for vid in vids:
            for did in CITY_DISTRIBUTORS.get(city, []):
                dvc += 1
                c2.execute("INSERT INTO distributor_vendor_contracts VALUES (?,?,?,?,?,?,?)",
                           (f"DVC-{dvc}", did, vid, "2024-01-01", "2028-12-31", "all", 1))

    # --- DB2 shipments ------------------------------------------------------------
    batch_cols = ["batch_id", "batch_serial", "distributor_id", "manufacturer_ref", "source_warehouse",
                  "destination_vendor_id", "quantity_shipped", "quantity_received", "dispatch_date",
                  "expected_arrival_date", "actual_arrival_date", "cold_chain_maintained", "temperature_log_url",
                  "transport_mode", "vehicle_reg", "status", "discrepancy_noted", "discrepancy_details"]
    shipments = []
    ship_n = 0
    cities = [c for c in licensed_by_city if licensed_by_city[c]]
    weights = [4 if c in ("Mumbai", "Bengaluru", "New Delhi") else 2 for c in cities]
    rev_dup = {v: k for k, v in dup_of.items()}
    for p in products:
        city = rng.choices(cities, weights)[0]
        dests = rng.sample(licensed_by_city[city], min(len(licensed_by_city[city]), rng.choice([1, 2, 2, 3])))
        for vid in dests:
            ship_n += 1
            mfg = date.fromisoformat(p["manufacture_date"])
            dispatch = mfg + timedelta(days=rng.randint(10, 75))
            if dispatch > date(2026, 9, 1):
                dispatch = date(2026, 9, 1) - timedelta(days=rng.randint(0, 30))
            arrive = dispatch + timedelta(days=rng.randint(1, 5))
            qty = rng.choice([60, 80, 100, 120, 150, 200, 250, 300])
            cold = p["requires_cold_chain"]
            did = COLD_DISTRIBUTOR[city] if cold else rng.choice(CITY_DISTRIBUTORS[city])
            damaged = rng.randint(1, 5) if rng.random() < 0.06 else 0
            s = {"batch_id": f"DBATCH-G{ship_n:04d}", "batch_serial": p["product_uid"], "distributor_id": did,
                 "manufacturer_ref": p["manufacturer_id"], "source_warehouse": f"{city} DC",
                 "destination_vendor_id": vid, "quantity_shipped": qty,
                 "quantity_received": qty - damaged,
                 "dispatch_date": dispatch.isoformat(), "expected_arrival_date": arrive.isoformat(),
                 "actual_arrival_date": arrive.isoformat(), "cold_chain_maintained": 1,
                 "temperature_log_url": f"https://telemetry.example.in/{ship_n:04d}" if cold else None,
                 "transport_mode": ("air" if rng.random() < 0.3 else "road") if cold else
                 rng.choices(["road", "rail", "courier"], [85, 5, 10])[0],
                 "vehicle_reg": plate(city, rng), "status": "delivered", "discrepancy_noted": 1 if damaged else 0,
                 "discrepancy_details": f"{damaged} unit(s) damaged in transit - credited" if damaged else None,
                 "_true": p["product_uid"], "_arrive": arrive, "_city": city}
            if p["product_uid"] in rev_dup and rng.random() < 0.5:
                s["batch_serial"] = rev_dup[p["product_uid"]]       # clerk picked the duplicate master record
            shipments.append(s)

    # Noise on the legitimate shipments, recorded as it is injected.
    final_ship = []
    for s in shipments:
        stored = dict(s)
        noise = "clean" if s["batch_serial"] == s["_true"] else "master_duplicate_ref"
        roll = rng.random()
        if noise == "clean" and roll < 0.09:
            stored["batch_serial"], noise = corrupt_for_channel(s["_true"], "erp", rng)
        elif noise == "clean" and roll < 0.105 and sibling.get(s["_true"]):
            stored["batch_serial"], noise = rng.choice(sibling[s["_true"]]), "valid_but_wrong"
        key = stored["batch_id"]
        truth.rec("db2", "distribution_batches", key, s["_true"], noise, "batch_serial", stored["batch_serial"])
        r = rng.random()
        if r < 0.03:
            wrong = rng.choice([m[0] for m in NEW_MANUFACTURERS if m[0] != s["manufacturer_ref"]])
            truth.conflicts.append({"key": f"db2:distribution_batches:{key}", "column": "manufacturer_ref",
                                    "stored": wrong, "correct": s["manufacturer_ref"]})
            stored["manufacturer_ref"] = wrong
        elif r < 0.05:
            truth.missing.append({"key": f"db2:distribution_batches:{key}", "column": "manufacturer_ref",
                                  "correct": s["manufacturer_ref"]})
            stored["manufacturer_ref"] = ""
        if rng.random() < 0.06:
            raw = messy_datetime(datetime.combine(date.fromisoformat(s["dispatch_date"]), datetime.min.time()), rng, False)
            truth.format.append({"key": f"db2:distribution_batches:{key}", "column": "dispatch_date",
                                 "stored": raw, "correct": s["dispatch_date"]})
            stored["dispatch_date"] = raw
        if rng.random() < 0.03:
            num = int(s["destination_vendor_id"][-3:])
            raw = rng.choice([f"vnd-{num}", f"VND{num:03d}", f"VND {num:03d}"])
            truth.format.append({"key": f"db2:distribution_batches:{key}", "column": "destination_vendor_id",
                                 "stored": raw, "correct": s["destination_vendor_id"]})
            stored["destination_vendor_id"] = raw
        if rng.random() < 0.012:
            stored["quantity_received"] = s["quantity_shipped"] + rng.randint(5, 40)
            truth.conflicts.append({"key": f"db2:distribution_batches:{key}", "column": "quantity_received",
                                    "stored": stored["quantity_received"], "correct": "flag as discrepancy"})
        final_ship.append(stored)
        if rng.random() < 0.03:
            ship_n += 1
            dup = dict(stored)
            dup["batch_id"] = f"DBATCH-G{ship_n:04d}"
            final_ship.append(dup)
            truth.rec("db2", "distribution_batches", dup["batch_id"], s["_true"], noise, "batch_serial",
                      dup["batch_serial"])
            truth.duplicates.append({"table": "distribution_batches", "keep": key, "dup": dup["batch_id"]})

    # --- counterfeits: near-miss and fabricated codes ----------------------------
    all_codes = set(by_uid) | curated | set(dup_of)
    fakes = []
    targets = rng.sample(products, 24)
    for p in targets:
        fam, num = p["product_uid"].split("-")[1], int(p["product_uid"][-3:])
        for _ in range(20):
            if rng.random() < 0.6:
                fake = f"MED-{fam}-{num + rng.choice([5, 6, 7, 8, 9, 11, 13]):03d}"
            else:
                i = rng.randrange(len(fam))
                fake = f"MED-{fam[:i]}{rng.choice('ABCDEFGHJKMNPRTVWXY')}{fam[i + 1:]}-{num:03d}"
            if fake not in all_codes and fold(fake) not in folded:
                break
        all_codes.add(fake)
        folded.add(fold(fake))
        fakes.append({"code": fake, "imitates": p})
    for _ in range(6):
        fake = f"MED-{''.join(rng.choice('BCDFGHJKLMNPRSTVWXZ') for _ in range(5))}-{rng.randint(100, 999)}"
        fakes.append({"code": fake, "imitates": rng.choice(products)})

    kiosks = [k[0] for k in KIOSKS] + ["VND-007", "VND-008", "VND-009"]
    fake_ship_n = 0
    fake_sales_at = defaultdict(list)
    for f in fakes:
        p = f["imitates"]
        dests = [rng.choice(kiosks)]
        if rng.random() < 0.3:
            # Infiltration: the fake reaches a licensed pharmacy that stocks the real product.
            real_dests = [s["destination_vendor_id"] for s in shipments if s["_true"] == p["product_uid"]]
            if real_dests:
                dests.append(real_dests[0])
        for vid in dests:
            fake_ship_n += 1
            dispatch = date(2025, 6, 1) + timedelta(days=rng.randint(0, 420))
            row = {"batch_id": f"DBATCH-X{fake_ship_n:03d}", "batch_serial": f["code"],
                   "distributor_id": rng.choice(["DIST-004", "DIST-009"]),
                   "manufacturer_ref": rng.choice(["UNKNOWN", p["manufacturer_id"]]),
                   "source_warehouse": "Unregistered godown", "destination_vendor_id": vid,
                   "quantity_shipped": rng.choice([100, 200, 300]), "quantity_received": None,
                   "dispatch_date": dispatch.isoformat(), "expected_arrival_date": None,
                   "actual_arrival_date": (dispatch + timedelta(days=2)).isoformat(), "cold_chain_maintained": 0,
                   "temperature_log_url": None, "transport_mode": "road", "vehicle_reg": "Unmarked van",
                   "status": "delivered", "discrepancy_noted": 0, "discrepancy_details": None}
            row["quantity_received"] = row["quantity_shipped"]
            if vid.startswith("VND-0") and vid in vendors and vendors[vid]["active"] and vid not in kiosks:
                row["distributor_id"] = "DIST-009"
            final_ship.append(row)
            truth.rec("db2", "distribution_batches", row["batch_id"], None, "counterfeit", "batch_serial", f["code"])
            fake_sales_at[f["code"]].append((vid, dispatch + timedelta(days=2)))

    for s in final_ship:
        c2.execute(f"INSERT INTO distribution_batches ({', '.join(batch_cols)}) VALUES ({', '.join('?' * len(batch_cols))})",
                   [s.get(c) for c in batch_cols])

    # --- DB1 checkout scans ---------------------------------------------------------
    ev_cols = ["event_id", "scan_code", "scan_timestamp", "vendor_id", "customer_age_group", "quantity_bought",
               "price_paid", "currency", "payment_method", "scan_method", "device_id", "anomaly_flag",
               "anomaly_reason", "notes", "label_text", "label_image"]
    events = []
    ev_n = 0
    images_left = 30
    for s in shipments:
        p = by_uid[s["_true"]]
        vid = s["destination_vendor_id"]
        exp = date.fromisoformat(p["expiry_date"])
        start = s["_arrive"] + timedelta(days=1)
        end = min(exp - timedelta(days=1), LAST_SALE)
        if end <= start:
            continue
        budget = int(s["quantity_received"] * 0.5)
        for _ in range(rng.randint(2, 6)):
            qty = rng.choice([1, 1, 1, 2, 2, 3])
            if qty > budget:
                break
            budget -= qty
            ev_n += 1
            day = start + timedelta(days=rng.randint(0, (end - start).days))
            when = datetime.combine(day, datetime.min.time()) + timedelta(minutes=rng.randint(8 * 60, 22 * 60))
            unit = round(p["msrp_kes"] * rng.choice([1.0, 1.0, 0.95, 0.9, 0.85]), 2)
            vtype = vendors[vid]["vendor_type"]
            method = rng.choices(["barcode", "qrcode", "manual", "ocr"],
                                 [60, 25, 8, 7] if vtype == "hospital" else [50, 25, 13, 12])[0]
            e = {"event_id": f"PE-G-{ev_n:05d}", "scan_code": p["product_uid"], "scan_timestamp": fmt_ts(when),
                 "vendor_id": vid, "customer_age_group": rng.choice(["child", "youth", "adult", "adult", "senior"]),
                 "quantity_bought": qty, "price_paid": round(unit * qty, 2), "currency": "INR",
                 "payment_method": rng.choices(["upi", "cash", "card", "insurance"], [45, 30, 15, 10])[0],
                 "scan_method": method, "device_id": f"POS-{vid[-3:]}-{rng.choice('AB')}", "anomaly_flag": 0,
                 "anomaly_reason": None, "notes": None, "label_text": None, "label_image": None,
                 "_true": p["product_uid"]}
            events.append(e)

    # demo records next to curated products (documented in UNCERTAINTY.md)
    curated_rows = {r["product_uid"]: dict(r) for r in c3.execute("SELECT * FROM products")}
    events.append({"event_id": "PE-G-DEMO-01", "scan_code": "MED-ASAL1-OO7", "scan_timestamp": "2025-06-02 11:20:00",
                   "vendor_id": "VND-005", "customer_age_group": "adult", "quantity_bought": 1, "price_paid": 95.0,
                   "currency": "INR", "payment_method": "cash", "scan_method": "manual", "device_id": "POS-005-B",
                   "anomaly_flag": 0, "anomaly_reason": None, "notes": "Barcode smudged; typed by pharmacist",
                   "label_text": None, "label_image": None, "_true": "MED-ASALI-007", "_noise": "manual_demo"})
    demo_label = label_text_for(curated_rows["MED-ASALI-001"]).replace("MED-ASALI-001", "MED-ASALI-0O1").replace("NOVAMOX", "N0VAMOX")
    events.append({"event_id": "PE-G-DEMO-02", "scan_code": "MED-ASALI-0O1", "scan_timestamp": "2025-03-14 18:05:00",
                   "vendor_id": "VND-001", "customer_age_group": "senior", "quantity_bought": 1, "price_paid": 115.0,
                   "currency": "INR", "payment_method": "upi", "scan_method": "ocr", "device_id": "POS-001-A",
                   "anomaly_flag": 0, "anomaly_reason": None, "notes": "Read from the pack by the phone camera",
                   "label_text": demo_label, "label_image": "samples/labels/PE-G-DEMO-02.jpg",
                   "_true": "MED-ASALI-001", "_noise": "ocr_demo"})

    final_events = []
    for e in events:
        stored = dict(e)
        noise = e.get("_noise", "clean")
        true_uid = e["_true"]
        channel = {"barcode": "scan", "qrcode": "scan", "manual": "manual", "ocr": "ocr"}[e["scan_method"]]
        if noise == "clean":
            rate = {"scan": 0.004, "manual": 0.35, "ocr": 0.50}[channel]
            roll = rng.random()
            if roll < rate:
                stored["scan_code"], noise = corrupt_for_channel(true_uid, channel, rng)
            elif channel in ("manual", "ocr") and roll < rate + 0.04 and sibling.get(true_uid):
                stored["scan_code"], noise = rng.choice(sibling[true_uid]), "valid_but_wrong"
        if e["scan_method"] == "ocr" and e["event_id"] != "PE-G-DEMO-02":
            p = by_uid[true_uid]
            parts = label_text_for(p).split(" | ")
            if rng.random() < 0.3:
                parts[0] = ocr_noise(parts[0], rng, 1)
            if rng.random() < 0.35:
                parts[2] = "B.No. " + ocr_noise(parts[2][6:], rng, 1)
            if rng.random() < 0.1:
                parts[4] = "EXP " + ocr_noise(parts[4][4:], rng, 1)
            parts[-1] = stored["scan_code"]
            stored["label_text"] = " | ".join(parts)
            if images_left > 0 and rng.random() < 0.25:
                stored["label_image"] = f"samples/labels/{e['event_id']}.jpg"
                images_left -= 1
        key = stored["event_id"]
        truth.rec("db1", "purchase_events", key, true_uid, noise, "scan_code", stored["scan_code"])
        if rng.random() < 0.05:
            raw = messy_datetime(datetime.fromisoformat(e["scan_timestamp"]), rng, True)
            truth.format.append({"key": f"db1:purchase_events:{key}", "column": "scan_timestamp",
                                 "stored": raw, "correct": e["scan_timestamp"][:16]})
            stored["scan_timestamp"] = raw
        r = rng.random()
        if r < 0.04:
            stored["currency"] = rng.choice(["Rs", "Rs.", "inr", "INR ", "rupees"])
            truth.format.append({"key": f"db1:purchase_events:{key}", "column": "currency",
                                 "stored": stored["currency"], "correct": "INR"})
        elif r < 0.05:
            stored["currency"] = ""
            truth.missing.append({"key": f"db1:purchase_events:{key}", "column": "currency", "correct": "INR"})
        if rng.random() < 0.02:
            num = int(e["vendor_id"][-3:])
            stored["vendor_id"] = rng.choice([f"vnd-{num:03d}", f"VND{num:03d}", f"VND {num}"])
            truth.format.append({"key": f"db1:purchase_events:{key}", "column": "vendor_id",
                                 "stored": stored["vendor_id"], "correct": e["vendor_id"]})
        if rng.random() < 0.008:
            factor = rng.choice([10, 100])
            stored["price_paid"] = round(e["price_paid"] * factor, 2)
            truth.outliers.append({"key": f"db1:purchase_events:{key}", "column": "price_paid",
                                   "stored": stored["price_paid"], "correct": e["price_paid"]})
        if rng.random() < 0.3 and e["vendor_id"] in ("VND-001", "VND-002", "VND-012"):
            dup_vid = {"VND-001": "VND-036", "VND-002": "VND-037", "VND-012": "VND-038"}[e["vendor_id"]]
            stored["vendor_id"] = dup_vid                 # sale booked under the duplicate pharmacy record
        final_events.append(stored)
        dup_roll = rng.random()
        if dup_roll < 0.03 and stored["scan_timestamp"] == e["scan_timestamp"]:
            ev_n += 1
            dup = dict(stored)
            dup["event_id"] = f"PE-G-{ev_n:05d}"
            dup["scan_timestamp"] = fmt_ts(datetime.fromisoformat(e["scan_timestamp"]) + timedelta(seconds=rng.randint(3, 40)))
            if dup_roll < 0.006:
                dup["scan_code"], _ = corrupt_for_channel(true_uid, "manual", rng)
            final_events.append(dup)
            truth.rec("db1", "purchase_events", dup["event_id"], true_uid,
                      "clean" if dup["scan_code"] == true_uid else "keyboard", "scan_code", dup["scan_code"])
            truth.duplicates.append({"table": "purchase_events", "keep": key, "dup": dup["event_id"]})

    for f in fakes:
        p = f["imitates"]
        for vid, arrived in fake_sales_at.get(f["code"], []):
            for _ in range(rng.randint(2, 4)):
                ev_n += 1
                when = datetime.combine(min(arrived + timedelta(days=rng.randint(1, 120)), LAST_SALE),
                                        datetime.min.time()) + timedelta(minutes=rng.randint(9 * 60, 23 * 60))
                method = rng.choices(["barcode", "qrcode", "manual"], [50, 20, 30])[0]
                code = f["code"]
                noise = "counterfeit"
                if method == "manual" and rng.random() < 0.3:
                    code, _ = corrupt_for_channel(code, "manual", rng)
                qty = rng.choice([1, 2, 3])
                e = {"event_id": f"PE-G-{ev_n:05d}", "scan_code": code, "scan_timestamp": fmt_ts(when),
                     "vendor_id": vid, "customer_age_group": rng.choice(["youth", "adult", "senior"]),
                     "quantity_bought": qty,
                     "price_paid": round(p["msrp_kes"] * rng.uniform(0.3, 0.6) * qty, 2), "currency": "INR",
                     "payment_method": "cash", "scan_method": method, "device_id": f"POS-{vid[-3:]}-X",
                     "anomaly_flag": 0, "anomaly_reason": None, "notes": None, "label_text": None, "label_image": None}
                final_events.append(e)
                truth.rec("db1", "purchase_events", e["event_id"], None, noise, "scan_code", code)

    for e in final_events:
        c1.execute(f"INSERT INTO purchase_events ({', '.join(ev_cols)}) VALUES ({', '.join('?' * len(ev_cols))})",
                   [e.get(c) for c in ev_cols])

    # --- DB4 complaints ------------------------------------------------------------
    comp_cols = ["complaint_id", "complaint_item_ref", "complaint_date", "complainant_type", "complainant_name",
                 "complainant_contact", "purchase_location", "complaint_category", "description", "severity_level",
                 "status", "assigned_officer_id", "date_assigned", "resolution_date", "resolution_notes",
                 "action_taken", "auto_generated"]
    comps = []
    cn = 0
    legit_sales = [e for e in events if not e["event_id"].startswith("PE-G-DEMO")]

    def brand_as_typed(brand):
        r = rng.random()
        if r < 0.15:
            return phonetic(brand, rng).title()
        if r < 0.25:
            return corrupt(brand, "keyboard", rng).title()
        return brand

    for e in rng.sample(legit_sales, 115):
        p = by_uid[e["_true"]]
        v = vendors[e["vendor_id"]]
        cn += 1
        brand = p["product_name"].split()[0]
        sale = datetime.fromisoformat(e["scan_timestamp"])
        when = min(sale + timedelta(days=rng.randint(1, 20), hours=rng.randint(0, 9)), datetime(2026, 10, 18, 17))
        cat = rng.choices(["adverse_reaction", "substandard", "price_gouging", "mislabeled", "other"],
                          [30, 20, 15, 10, 25])[0]
        typed = brand_as_typed(brand)
        desc = {
            "adverse_reaction": f"Developed {rng.choice(SYMPTOMS)} after taking {typed} {p['strength']} bought on {sale:%d %b}.",
            "substandard": f"{typed} {p['strength']} tablets crumble in the strip and had no effect after {rng.randint(2, 6)} days.",
            "price_gouging": f"Charged more than the printed MRP for {typed} {p['strength']}.",
            "mislabeled": f"Strength printed on the {typed} box does not match the strip inside.",
            "other": f"Pharmacist could not confirm the batch of {typed} {p['strength']}.",
        }[cat]
        ref, noise = p["product_uid"], "clean"
        roll = rng.random()
        if roll < 0.30:
            ref, noise = corrupt_for_channel(p["product_uid"], "citizen", rng)
        elif roll < 0.38:
            desc += f" Code on the strip: {p['product_uid'].lower().replace('-', ' ')}."
            ref, noise = "", "missing_code"
        elif rng.random() < 0.3:
            desc += f" Code on the strip: {p['product_uid']}."
        first, last = rng.choice(FIRST), rng.choice(LAST)
        loc = f"{v['vendor_name']}, {v['location_county']}"
        if rng.random() < 0.25:
            loc = loc.lower()
        c = {"complaint_id": f"MCA-2026-G{cn:04d}", "complaint_item_ref": ref, "complaint_date": fmt_ts(when),
             "complainant_type": rng.choices(["consumer", "vendor", "ngo"], [85, 10, 5])[0],
             "complainant_name": f"{first} {last}", "complainant_contact": f"+91-9{rng.randint(100000000, 999999999)}",
             "purchase_location": loc, "complaint_category": cat, "description": desc,
             "severity_level": rng.choice(["low", "medium", "medium", "high"]),
             "status": rng.choice(["open", "open", "under_investigation", "resolved"]),
             "assigned_officer_id": rng.choice(["OFF-001", "OFF-002", "OFF-005"]),
             "date_assigned": (when + timedelta(days=1)).date().isoformat(), "resolution_date": None,
             "resolution_notes": None, "action_taken": None, "auto_generated": 0, "_true": p["product_uid"]}
        if rng.random() < 0.08:
            raw = messy_datetime(when, rng, True)
            truth.format.append({"key": f"db4:complaints:{c['complaint_id']}", "column": "complaint_date",
                                 "stored": raw, "correct": c["complaint_date"][:16]})
            c["complaint_date"] = raw
        comps.append(c)
        truth.rec("db4", "complaints", c["complaint_id"], p["product_uid"], noise, "complaint_item_ref", ref)
        if rng.random() < 0.08:
            cn += 1
            d = dict(c)
            d["complaint_id"] = f"MCA-2026-G{cn:04d}"
            d["complaint_date"] = fmt_ts(when + timedelta(days=rng.randint(1, 2)))
            d["description"] = "Filing again, no response yet. " + desc
            d["complaint_item_ref"], dn = (corrupt_for_channel(p["product_uid"], "citizen", rng)
                                           if rng.random() < 0.4 else (p["product_uid"], "clean"))
            comps.append(d)
            truth.rec("db4", "complaints", d["complaint_id"], p["product_uid"], dn, "complaint_item_ref",
                      d["complaint_item_ref"])
            truth.duplicates.append({"table": "complaints", "keep": c["complaint_id"], "dup": d["complaint_id"]})

    for f in rng.sample(fakes, 14):
        p = f["imitates"]
        vid = fake_sales_at.get(f["code"], [(rng.choice(kiosks), None)])[0][0]
        v = vendors[vid]
        cn += 1
        brand = p["product_name"].split()[0]
        ref = f["code"] if rng.random() < 0.7 else corrupt_for_channel(f["code"], "citizen", rng)[0]
        c = {"complaint_id": f"MCA-2026-G{cn:04d}", "complaint_item_ref": ref,
             "complaint_date": fmt_ts(datetime(2025, 9, 1) + timedelta(days=rng.randint(0, 400), hours=rng.randint(9, 19))),
             "complainant_type": "consumer", "complainant_name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
             "complainant_contact": f"+91-9{rng.randint(100000000, 999999999)}",
             "purchase_location": f"{v['vendor_name']}, {v['location_county']}", "complaint_category": "counterfeit",
             "description": f"{brand} {p['strength']} looked fake: blurred print, no hologram, sold very cheap.",
             "severity_level": "critical", "status": "under_investigation", "assigned_officer_id": "OFF-002",
             "date_assigned": None, "resolution_date": None, "resolution_notes": None, "action_taken": None,
             "auto_generated": 0}
        comps.append(c)
        truth.rec("db4", "complaints", c["complaint_id"], None, "counterfeit", "complaint_item_ref", ref)

    for c in comps:
        c4.execute(f"INSERT INTO complaints ({', '.join(comp_cols)}) VALUES ({', '.join('?' * len(comp_cols))})",
                   [c.get(k) for k in comp_cols])

    bl = rng.sample(fakes[:24], 3)
    for i, f in enumerate(bl, 1):
        ref = f["code"] if i != 2 else f["code"].lower().replace("-", " ")
        if i == 2:
            truth.format.append({"key": f"db4:ministry_blacklist:BL-G{i:02d}", "column": "item_ref",
                                 "stored": ref, "correct": f["code"]})
        c4.execute("INSERT INTO ministry_blacklist VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (f"BL-G{i:02d}", ref, None, "2026-08-1" + str(i), "OFF-001",
                    f"Counterfeit imitation of {f['imitates']['product_name']}; code never issued by the manufacturer.",
                    "critical", "Therapeutic failure", 1, "2026-08-20", 1, None, None))
    f = bl[0]
    c4.execute("INSERT INTO public_alerts VALUES (?,?,?,?,?,?,?)",
               ("ALERT-G01", f["code"].replace("-", "_"), "2026-08-21 10:00:00", "public_portal",
                f"Do not buy packs coded {f['code']}: counterfeit {f['imitates']['product_name']}.",
                "Central Drugs Standard Control Organisation", 1))
    truth.format.append({"key": "db4:public_alerts:ALERT-G01", "column": "item_ref",
                         "stored": f["code"].replace("-", "_"), "correct": f["code"]})

    for c in conns.values():
        c.commit()
        c.close()

    os.makedirs(paths.generated_dir(), exist_ok=True)
    data = truth.dump()
    with open(paths.ground_truth_file(), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    s = data["summary"]
    print(f"  generated: {len(products)} products (+{len(dup_of)} duplicate registrations), "
          f"{len(final_ship)} shipments, {len(final_events)} checkout scans, {len(comps)} complaints, "
          f"{len(fakes)} counterfeit codes")
    print(f"  noise kinds: {s['noise_kinds']}")
    print(f"  ground truth -> {paths.ground_truth_file()}")


if __name__ == "__main__":
    main()
