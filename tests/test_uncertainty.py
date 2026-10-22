"""
Phase 2 regression suite. Builds a fresh copy of every silo in a temporary
directory, so the demo databases are never touched, then checks the matcher and
the cleanser, including the insert / modify / delete checks an examiner would make.

    python -m unittest tests.test_uncertainty -v
"""

from __future__ import annotations
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

TMP = tempfile.mkdtemp(prefix="asali_dq_")
os.environ["ASALI_DB_DIR"] = os.path.join(TMP, "databases")
os.environ["ASALI_NOSQL_FILE"] = os.path.join(TMP, "db1_retail_pos.json")
os.environ["ASALI_GENERATED_DIR"] = os.path.join(TMP, "generated")

from integration.uncertainty import paths  # noqa: E402
from integration.uncertainty.confusion import ConfusionModel  # noqa: E402
from integration.uncertainty.similarity import damerau_osa, jaro_winkler, levenshtein, soundex  # noqa: E402
from integration.uncertainty.standardize import canonical_code, parse_datetime, parse_label  # noqa: E402


def build_silos():
    os.makedirs(paths.db_dir(), exist_ok=True)
    os.makedirs(paths.generated_dir(), exist_ok=True)
    real_model = os.path.join(BASE, "data", "generated", "linkage_model.json")
    if os.path.exists(real_model):
        shutil.copy(real_model, paths.model_file())
    import create_databases
    from data import generate_uncertain_data, seed_db1, seed_db2, seed_db3, seed_db4
    from data.seed_nosql_db1 import sync_collection
    create_databases.main()
    for seed in (seed_db3, seed_db2, seed_db1, seed_db4):
        seed.seed()
    generate_uncertain_data.main()
    sync_collection(paths.db_path("db1"), paths.nosql_file())


def sql(db, query, params=()):
    conn = sqlite3.connect(paths.db_path(db))
    try:
        cur = conn.execute(query, params)
        conn.commit()
        return cur.fetchall()
    finally:
        conn.close()


def match(**kw):
    from integration.uncertainty.cleanser import live_matcher
    rec = {"source": "db1", "key": "test", "channel": "manual"}
    rec.update(kw)
    return live_matcher().match(rec)


class Primitives(unittest.TestCase):
    def test_edit_distances(self):
        self.assertEqual(levenshtein("kitten", "sitting"), 3)
        self.assertEqual(damerau_osa("MED-AB-12", "MED-BA-12"), 1)       # a swap is one edit
        self.assertEqual(levenshtein("MED-AB-12", "MED-BA-12"), 2)       # but two for Levenshtein
        self.assertGreater(jaro_winkler("MARTHA", "MARHTA"), 0.96)

    def test_soundex(self):
        self.assertEqual(soundex("Robert"), "R163")
        self.assertEqual(soundex("Rupert"), "R163")
        self.assertEqual(soundex("Ashcraft"), "A261")

    def test_canonical_code_changes_format_only(self):
        for raw in ["med-asali-001", "MED_ASALI_001", " MED ASALI 001 ", "MEDASALI001", "IN-MED-ASALI-001"]:
            self.assertEqual(canonical_code(raw), "MED-ASALI-001", raw)
        self.assertEqual(canonical_code("MED-ASAL1-OO1"), "MED-ASAL1-OO1")   # never rewrites a character

    def test_confusable_glyph_is_cheaper_than_random(self):
        cm = ConfusionModel()
        self.assertLess(cm.distance("MED-ASALI-0O1", "MED-ASALI-001"), cm.distance("MED-ASALI-0X1", "MED-ASALI-001"))

    def test_ambiguous_date_reports_both_readings(self):
        p = parse_datetime("03/10/2025 11:20")
        self.assertTrue(p.ambiguous)
        self.assertEqual(p.iso(), "2025-10-03 11:20:00")
        self.assertEqual(p.alternatives[0].month, 3)

    def test_label_parsing(self):
        lab = parse_label("N0VAMOX 500MG | Amoxycillin | B.No. BATCH-A0O1 | EXP 0I/2027 | MRP Rs.115.00 | MED-ASALI-0O1")
        self.assertEqual(lab.strength, "500MG")
        self.assertEqual(lab.expiry, "2027-01")
        self.assertEqual(lab.mrp, 115.0)
        self.assertEqual(lab.code, "MED-ASALI-0O1")


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_silos()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP, ignore_errors=True)

    # -- rubric 1: approximate matching ------------------------------------------

    def test_noisy_code_with_context_links(self):
        r = match(code="MED-ASAL1-OO7", vendor_id="VND-005", price_paid=95, quantity=1, date="2025-06-02 11:20")
        self.assertEqual(r.decision, "AUTO_LINK")
        self.assertEqual(r.best_uid, "MED-ASALI-007")
        self.assertGreater(r.best_posterior, 0.95)

    def test_all_approximate_candidates_are_listed(self):
        r = match(code="MED-ASALI-0I1")
        uids = [c.uid for c in r.candidates]
        for expected in ("MED-ASALI-001", "MED-ASALI-010"):
            self.assertIn(expected, uids)

    def test_counterfeit_near_miss_is_not_linked(self):
        r = match(code="MED-ASALI-011", channel="scan", vendor_id="VND-007", price_paid=30, quantity=1,
                  date="2025-05-10")
        self.assertEqual(r.decision, "NO_MATCH")
        self.assertGreater(r.p_none, 0.8)

    def test_label_image_text_alone(self):
        r = match(code="", channel="ocr", vendor_id="VND-001",
                  label_text="N0VAMOX 500MG | Amoxycillin | B.No. BATCH-A0O1 | EXP 01/2027 | MRP Rs.115.00")
        self.assertEqual(r.best_uid, "MED-ASALI-001")

    def test_reverse_lookup_finds_damaged_records(self):
        from integration.uncertainty.cleanser import live_matcher
        r = live_matcher().reverse("MED-ASALI-001")
        stored = {x["stored_code"] for x in r["records"]}
        self.assertIn("MED-ASALI-0O1", stored)

    # -- rubric 2: cleansing --------------------------------------------------------

    def test_inserted_noisy_record_is_found_and_cleansed(self):
        from integration.uncertainty.cleanser import apply, scan, undo
        sql("db1", "INSERT INTO purchase_events (event_id, scan_code, scan_timestamp, vendor_id, quantity_bought, "
                   "price_paid, currency, scan_method) VALUES ('PE-T-INS','med asali 0O8','2025-04-20 10:15:00',"
                   "'VND-001',1,85,'INR','manual')")
        try:
            issue = next(i for i in scan()["issues"] if i["pk_val"] == "PE-T-INS" and i["column"] == "scan_code")
            self.assertEqual((issue["decision"], issue["proposed"]), ("AUTO", "MED-ASALI-008"))
            run = apply("auto")
            self.assertEqual(sql("db1", "SELECT scan_code FROM purchase_events WHERE event_id='PE-T-INS'")[0][0],
                             "MED-ASALI-008")
            self.assertEqual(run["after"]["auto"], 0)
            self.assertEqual(run["after"]["retain"], 0)
            undo(run["run_id"])
            self.assertEqual(sql("db1", "SELECT scan_code FROM purchase_events WHERE event_id='PE-T-INS'")[0][0],
                             "med asali 0O8")
        finally:
            sql("db1", "DELETE FROM purchase_events WHERE event_id='PE-T-INS'")

    def test_modified_registry_changes_the_answer(self):
        args = dict(code="MED-ASAL1-OO7", vendor_id="VND-005", price_paid=95, quantity=1, date="2025-06-02 11:20")
        self.assertEqual(match(**args).decision, "AUTO_LINK")
        sql("db3", "UPDATE products SET msrp_kes = 400 WHERE product_uid = 'MED-ASALI-007'")
        try:
            r = match(**args)
            self.assertNotEqual(r.decision, "AUTO_LINK")
        finally:
            sql("db3", "UPDATE products SET msrp_kes = 95 WHERE product_uid = 'MED-ASALI-007'")

    def test_deleted_product_is_no_longer_proposed(self):
        row = sql("db3", "SELECT * FROM products WHERE product_uid = 'MED-ASALI-008'")[0]
        sql("db3", "DELETE FROM products WHERE product_uid = 'MED-ASALI-008'")
        try:
            r = match(code="MED-ASALI-00B", vendor_id="VND-001", price_paid=170, quantity=2, date="2025-04-12")
            self.assertNotIn("MED-ASALI-008", [c.uid for c in r.candidates])
            self.assertNotEqual(r.decision, "AUTO_LINK")
        finally:
            sql("db3", f"INSERT INTO products VALUES ({','.join('?' * len(row))})", row)

    def test_inserted_duplicate_is_detected(self):
        from integration.uncertainty.cleanser import scan
        sql("db1", "INSERT INTO purchase_events SELECT 'PE-T-DUP', scan_code, datetime(scan_timestamp, '+12 seconds'), "
                   "vendor_id, customer_age_group, quantity_bought, price_paid, currency, payment_method, scan_method, "
                   "device_id, anomaly_flag, anomaly_reason, notes, label_text, label_image "
                   "FROM purchase_events WHERE event_id = 'PE-20250310-0001'")
        try:
            dup = [i for i in scan()["issues"] if i["pk_val"] == "PE-T-DUP" and i["category"] == "duplicate_record"]
            self.assertEqual(len(dup), 1)
            self.assertEqual(dup[0]["decision"], "AUTO")
        finally:
            sql("db1", "DELETE FROM purchase_events WHERE event_id='PE-T-DUP'")

    def test_automatic_fixes_agree_with_ground_truth(self):
        from integration.uncertainty.cleanser import scan
        acc = scan(include_issues=False)["accuracy_vs_ground_truth"]
        self.assertGreaterEqual(acc["auto"]["precision"], 0.99)
        self.assertGreaterEqual(acc["retain"]["precision"], 0.95)

    def test_blacklist_entry_is_canonicalised_not_relinked(self):
        from integration.uncertainty.cleanser import scan
        issues = [i for i in scan()["issues"] if i["pk_val"] == "BL-G02"]
        auto = [i for i in issues if i["decision"] == "AUTO"]
        self.assertEqual(len(auto), 1)
        self.assertEqual(auto[0]["category"], "format")
        registered = {r[0] for r in sql("db3", "SELECT product_uid FROM products")}
        self.assertNotIn(auto[0]["proposed"], registered)

    def test_curated_counterfeits_stay_unlinked(self):
        for code in ("MED-NAKALI-001", "MED-NAKALI-003"):
            self.assertEqual(match(code=code, channel="scan").decision, "NO_MATCH", code)

    def test_check_a_medicine_only_suggests_close_misses(self):
        # The Check a medicine page checks an unregistered code as typed and only
        # offers the closest product; far-off codes and registered ones get nothing.
        from types import SimpleNamespace as NS
        from api.verify_item import _suggestion
        missing = lambda code: NS(item_code=code, manufacturer=NS(found=False))
        sql("db3", "INSERT INTO products (product_uid, product_name, generic_name, manufacturer_id, category, "
                   "dosage_form, strength, manufacture_date, expiry_date, batch_number, registration_no) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("MED-SAM-001", "Samcillin 500mg", "Amoxicillin", "MFG-001", "Antibiotic", "Tablet", "500mg",
             "2025-01-01", "2027-01-01", "BATCH-SAM-01", "CDSCO/TEST/SAM-001"))
        try:
            s = _suggestion("MED-SAN-001", missing("MED-SAN-001"))
            self.assertIsNotNone(s)
            self.assertEqual(s["uid"], "MED-SAM-001")
            self.assertGreaterEqual(s["chance"], 0.5)
            self.assertIsNone(_suggestion("MED-TOTALLY-FAKE-9999", missing("MED-TOTALLY-FAKE-9999")))
            self.assertIsNone(_suggestion("MED-SAM-001", NS(item_code="MED-SAM-001", manufacturer=NS(found=True))))
        finally:
            sql("db3", "DELETE FROM products WHERE product_uid = 'MED-SAM-001'")

    def test_registry_codes_are_stored_in_standard_form(self):
        # A medicine registered as 'MED-sam-001' was stored that way, and every
        # lookup tidies to 'MED-SAM-001' first, so it was reported as fake.
        from integration.db_explorer import _registry_code
        self.assertEqual(_registry_code("MED-sam-001"), "MED-SAM-001")
        self.assertEqual(_registry_code("med_shagun 190"), "MED-SHAGUN-190")
        self.assertEqual(_registry_code("MED-FED-1234"), "MED-FED-1234")
        self.assertEqual(match(code="MED-asali-007").decision, "EXACT")

    def test_registered_code_with_details_that_do_not_fit_is_flagged(self):
        r = match(code="MED-ASALI-007", vendor_id="VND-007", price_paid=5, date="2020-01-01 10:00")
        self.assertEqual(r.decision, "EXACT")
        self.assertGreaterEqual(r.p_none, 0.8)
        self.assertTrue(any("do not fit" in n for n in r.notes))

    def test_code_typed_without_dashes_is_tidied_not_name_matched(self):
        from integration.uncertainty.standardize import canonical_code, looks_like_code
        self.assertTrue(looks_like_code("MEDASALI008"))
        self.assertEqual(canonical_code("MEDASALI008"), "MED-ASALI-008")
        self.assertFalse(looks_like_code("Novamox"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
