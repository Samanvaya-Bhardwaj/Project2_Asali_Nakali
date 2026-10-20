#!/usr/bin/env python3
"""
seed_db4.py - Ministry of Consumer Affairs Report DB (DB4)
Uses complaint_item_ref as the integration key.
Pre-seeds Central Consumer Protection Authority (CCPA) and CDSCO regulatory records.
"""

import sqlite3, os
from datetime import date, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "databases", "db4_ministry_reports.sqlite")

MINISTRY_OFFICERS = [
    ("OFF-001", "Dr. Rajesh Sharma", "CDSCO Inspectorate", "Senior Drug Inspector", "rajesh.sharma@cdsco.gov.in", "+91-11-23230001", 1),
    ("OFF-002", "Mr. Amit Verma", "Central Consumer Protection Authority", "Joint Commissioner", "amit.verma@consumeraffairs.nic.in", "+91-11-23380002", 1),
    ("OFF-003", "Ms. Priya Nair", "National Consumer Commission", "Legal Registrar", "priya.nair@ncdrc.nic.in", "+91-11-24300003", 1),
    ("OFF-004", "Dr. Sunita Rao", "Central Drug Laboratory Kolkata", "Director of Chemistry", "sunita.rao@cdl.gov.in", "+91-33-22200004", 1),
    ("OFF-005", "Ms. Ananya Sen", "National Consumer Helpline", "Senior Grievance Officer", "ananya.sen@consumerhelpline.gov.in", "+91-11-23400005", 1),
]

COMPLAINTS = [
    # (complaint_id, item_ref, date, type, name, contact, location, category, description, severity, status, officer, date_assigned, resolution_date, resolution_notes, action_taken, auto_generated)
    ("MCA-2025-001", "MED-NAKALI-001", "2025-01-20 10:00:00", "consumer", "Rahul Deshmukh", "+91-9820111001", "Kurla West Kiosk, Mumbai", "counterfeit", "Patient reported severe nausea and no therapeutic effect after taking antibiotic purchased from street kiosk. Packaging fonts blurred.", "critical", "under_investigation", "OFF-002", "2025-01-22", None, None, None, 0),
    ("MCA-2025-002", "MED-NAKALI-002", "2025-02-05 14:30:00", "consumer", "Sneha Kulkarni", "+91-9821222002", "Janata Medicos, Mumbai", "substandard", "Fever did not subside after 3 days. Chemist confirmed batch sticker was paper-pasted over blank strip.", "high", "lab_testing", "OFF-001", "2025-02-07", None, None, None, 0),
    ("MCA-2025-003", "MED-NAKALI-003", "2025-03-15 09:00:00", "vendor", "Apollo Pharmacy Bandra", "+91-22-26401111", "Hill Road, Mumbai", "counterfeit", "Hospital pharmacy rejected incoming batch. Hologram did not fluoresce under UV lamp. Forged CDSCO license.", "critical", "escalated", "OFF-002", "2025-03-16", None, None, "criminal_referral", 0),
    ("MCA-2025-004", "MED-NAKALI-004", "2025-04-10 11:00:00", "consumer", "Vikram Malhotra", "+91-9811444004", "Chandni Chowk Kiosk, Delhi", "mislabeled", "Tablet weight is 200mg instead of 500mg labeled strength. Chalk powder texture.", "high", "open", "OFF-005", "2025-04-11", None, None, None, 0),
    ("MCA-2025-005", "MED-NAKALI-005", "2025-05-05 16:00:00", "consumer", "Meera Iyer", "+91-9844555005", "Suburban Chemist, Thane", "counterfeit", "Insulin cartridge liquid cloudy at room temperature. Patient blood glucose spiked dangerously. Counterfeit cartridge confirmed.", "critical", "under_investigation", "OFF-001", "2025-05-06", None, None, None, 0),
    # Resolved recalls
    ("MCA-2024-006", "MED-RECALL-001", "2024-10-01 08:00:00", "authority", "CDSCO Vigilance Cell", "vigilance@cdsco.gov.in", "National", "substandard", "Government analyst confirmed diethylene glycol solvent in pediatric cough syrup exceeding 0.1% limit.", "critical", "resolved", "OFF-004", "2024-10-03", "2025-05-25", "Nationwide recall gazetted. Manufacturer production halted pending GMP audit.", "product_recalled", 0),
    ("MCA-2024-007", "MED-RECALL-002", "2024-08-15 10:00:00", "authority", "FDA Maharashtra", "commissioner@fda.mh.gov.in", "Mumbai", "substandard", "Microbial contamination detected in reconstituted oral suspension bottles.", "critical", "resolved", "OFF-001", "2024-08-17", "2025-03-15", "Batch recalled from wholesale distributors. Remediation complete.", "product_recalled", 0),
    ("MCA-2024-008", "MED-RECALL-003", "2024-11-01 09:00:00", "manufacturer", "Dr. Reddy's QA", "qa@drreddys.com", "Internal Audit", "substandard", "Self-reported dissolution profile failure under accelerated stability testing.", "high", "resolved", "OFF-001", "2024-11-02", "2025-07-20", "Voluntary batch recall accepted by CDSCO.", "product_recalled", 0),
    # Unauthorized distribution
    ("MCA-2025-009", "MED-UNAUTH-001", "2025-04-08 15:00:00", "consumer", "Anonymous Consumer", "confidential@gov.in", "Kurla West", "counterfeit", "Schedule H1 sedative sold without medical prescription or bill.", "critical", "escalated", "OFF-003", "2025-04-09", None, None, "criminal_referral", 0),
    ("MCA-2025-010", "MED-UNAUTH-002", "2025-04-12 10:00:00", "authority", "Delhi Police Special Cell", "specialcell@delhipolice.gov.in", "Old Delhi", "counterfeit", "Codeine syrup seized from unlicensed wholesale godown without narcotics transport permits.", "critical", "under_investigation", "OFF-002", "2025-04-12", None, None, None, 0),
    # Velocity Anomaly
    ("MCA-2025-014", "MED-ASALI-002", "2025-05-02 08:30:00", "authority", "Central Consumer Protection Authority", "investigations@ccpa.nic.in", "Mumbai and Delhi", "counterfeit", "Same barcode MED-ASALI-002 scanned across 5 pharmacy locations in 28 minutes. Barcode cloning confirmed.", "critical", "under_investigation", "OFF-001", "2025-05-02", None, None, None, 0),
]

MINISTRY_BLACKLIST = [
    ("BL-001", "MED-NAKALI-001", "MCA-2025-001", "2025-03-20", "OFF-001", "Confirmed counterfeit - active ingredient absent. Not manufactured by Cipla.", "critical", "Acute health risk - severe infection treatment failure.", 1, "2025-03-21", 1, None, None),
    ("BL-002", "MED-NAKALI-002", "MCA-2025-002", "2025-04-15", "OFF-001", "Substandard - API under 30%. Chalk fillers and heavy metal binders.", "high", "Risk of toxicity and organ damage.", 1, "2025-04-16", 1, None, None),
    ("BL-003", "MED-NAKALI-003", "MCA-2025-003", "2025-04-01", "OFF-002", "Counterfeit antimalarial with forged licensing credentials.", "critical", "Fatal malaria complication risk.", 1, "2025-04-02", 1, None, None),
    ("BL-004", "MED-RECALL-001", "MCA-2024-006", "2025-05-25", "OFF-004", "Recalled - diethylene glycol solvent contamination.", "critical", "Acute kidney injury hazard.", 1, "2025-05-26", 1, None, None),
    ("BL-005", "MED-RECALL-002", "MCA-2024-007", "2025-03-15", "OFF-001", "Recalled - microbial contamination in pediatric formulation.", "high", "Risk of bacterial septicemia.", 1, "2025-03-16", 1, None, None),
    ("BL-006", "MED-RECALL-003", "MCA-2024-008", "2025-07-20", "OFF-001", "Recalled - sub-potent dissolution failure.", "high", "Therapeutic failure.", 1, "2025-07-21", 1, None, None),
]

LAB_TEST_REPORTS = [
    ("LAB-001", "MCA-2025-001", "MED-ASALI-001", "Central Drug Laboratory Kolkata", "NABL-ISO17025", "2025-01-25", "2025-01-28", "Assay, Dissolution, Related Substances", "pass", 1, "None detected", "Active ingredient Amoxycillin at 99.4% of label claim. Complies with Indian Pharmacopoeia standards.", "Batch certified fit for distribution"),
    ("LAB-002", "MCA-2025-001", "MED-NAKALI-001", "Central Drug Laboratory Kolkata", "NABL-ISO17025", "2025-02-01", "2025-02-04", "HPLC Assay, FTIR Spectroscopy", "fail", 0, "Chalk powder, talc binders", "Zero active pharmaceutical ingredient detected. Sample is composed entirely of inert excipients.", "Immediate seizure and criminal escalation recommended"),
    ("LAB-003", "MCA-2024-006", "MED-RECALL-001", "Central Drug Laboratory Kolkata", "NABL-ISO17025", "2024-10-15", "2024-10-18", "Gas Chromatography Diethylene Glycol Screen", "fail", 1, "Diethylene glycol 0.45% w/v", "Diethylene glycol detected at 0.45% w/v exceeding permissible statutory threshold of 0.1%. Toxic.", "Immediate nationwide product recall gazetted"),
]

PUBLIC_ALERTS = [
    ("ALERT-001", "MED-NAKALI-001", "2025-03-22 10:00:00", "public_portal", "Public Warning: Counterfeit Novamox 500mg capsules identified in unverified retail stalls. Look for missing CDSCO micro-text on blister foil.", "Central Drugs Standard Control Organisation", 1),
    ("ALERT-002", "MED-RECALL-001", "2025-05-26 12:00:00", "national_gazette", "Public Safety Notice: Recall of Coughcure Syrup Batch R-001. Halt all retail dispensation immediately.", "Ministry of Consumer Affairs", 1),
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM public_alerts;")
    cur.execute("DELETE FROM lab_reports;")
    cur.execute("DELETE FROM ministry_blacklist;")
    cur.execute("DELETE FROM complaints;")
    cur.execute("DELETE FROM ministry_officers;")

    cur.executemany("INSERT INTO ministry_officers VALUES (?,?,?,?,?,?,?)", MINISTRY_OFFICERS)
    cur.executemany("INSERT INTO complaints VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", COMPLAINTS)
    cur.executemany("INSERT INTO ministry_blacklist VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", MINISTRY_BLACKLIST)
    cur.executemany("INSERT INTO lab_reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", LAB_TEST_REPORTS)
    cur.executemany("INSERT INTO public_alerts VALUES (?,?,?,?,?,?,?)", PUBLIC_ALERTS)

    conn.commit()
    conn.close()
    print("  db4_ministry_reports seeded successfully (CDSCO & Ministry of Consumer Affairs).")

if __name__ == "__main__":
    seed()
