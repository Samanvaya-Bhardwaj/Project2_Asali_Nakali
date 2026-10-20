#!/usr/bin/env python3
"""
demo.py
-------
End-to-end demonstration of the Asali/Nakali Detection System.

Runs through all project phases:
  1. Creates all 4 heterogeneous SQLite databases
  2. Populates realistic seed data
  3. Demonstrates the integration engine on 6 test cases
  4. Shows audit chain statistics + integrity check
  5. Generates HTML reports for all cases
"""

import os, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# --- Colour helpers -----------------------------------------------------------
def bold(s):   return f"\033[1m{s}\033[0m"
def green(s):  return f"\033[92m{s}\033[0m"
def red(s):    return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def cyan(s):   return f"\033[96m{s}\033[0m"
def dim(s):    return f"\033[2m{s}\033[0m"

DIVIDER = "-" * 65
HEAVY   = "=" * 65

def header(title):
    print(f"\n{bold(HEAVY)}")
    print(f"  {bold(cyan(title))}")
    print(f"{bold(HEAVY)}")


# --- Phase 1: Create Databases ------------------------------------------------
def phase1_create_dbs():
    header("PHASE 1  -  Creating Heterogeneous Databases")
    print("""
  Creating 4 isolated SQLite databases, each owned by a different
  stakeholder and designed independently with different schemas.

  Key challenge: All 4 databases store the SAME item identifier
  under DIFFERENT column names (heterogeneous schema problem):

     DB1  purchase_events.scan_code
     DB2  distribution_batches.batch_serial
     DB3  products.product_uid
     DB4  complaints.complaint_item_ref
""")
    from create_databases import main as create_dbs
    create_dbs()


# --- Phase 2: Seed Data -------------------------------------------------------
def phase2_seed_data():
    header("PHASE 2  -  Populating Realistic Seed Data")
    print("""
  Seeding all 4 databases with realistic Kenya medicine market data.
  Item categories:
    * 10 ASALI  (genuine)  -  registered, authorized supply chain
    * 5  NAKALI (fake)     -  NOT in manufacturer DB (critical signal)
    * 3  RECALLED          -  genuine but recalled due to contamination
    * 2  UNAUTHORIZED      -  controlled substances via ghost distributor
""")
    # Seed in order: DB3 (authority) -> DB2 (distributor) -> DB1 (purchase) -> DB4 (ministry)
    print("  Seeding DB3 (Manufacturer Registry) ...")
    sys.path.insert(0, os.path.join(BASE, "data"))
    from data.seed_db3 import seed as seed3; seed3()
    print()
    print("  Seeding DB2 (Distributor Ledger) ...")
    from data.seed_db2 import seed as seed2; seed2()
    print()
    print("  Seeding DB1 (Purchase Registry) ...")
    from data.seed_db1 import seed as seed1; seed1()
    print()
    print("  Seeding DB4 (Ministry Reports) ...")
    from data.seed_db4 import seed as seed4; seed4()
    print()
    print(green("  All databases populated successfully."))


# --- Phase 3: Demonstrate Verification ---------------------------------------
def phase3_verify():
    header("PHASE 3  -  Intelligent Verification Demonstrations")

    from api.verify_item import verify

    demo_cases = [
        ("MED-ASALI-001",  "Genuine antibiotic  -  should pass all checks"),
        ("MED-ASALI-009",  "Genuine insulin  -  cold chain broken (suspicious)"),
        ("MED-NAKALI-001", "Counterfeit  -  absent from manufacturer DB"),
        ("MED-NAKALI-005", "Counterfeit  -  confirmed by lab testing"),
        ("MED-RECALL-001", "Recalled  -  heavy metal contamination"),
        ("MED-ASALI-002",  "Barcode cloning  -  5 simultaneous scan locations"),
    ]

    verdicts_seen = {"ASALI": 0, "SUSPICIOUS": 0, "NAKALI": 0}

    for code, description in demo_cases:
        print(f"\n{DIVIDER}")
        print(f"  {cyan('TEST:')} {description}")
        result = verify(code, generate_report=True)
        verdicts_seen[result["verdict"]] = verdicts_seen.get(result["verdict"], 0) + 1
        time.sleep(0.2)

    return verdicts_seen


# --- Phase 4: Audit Chain -----------------------------------------------------
def phase4_audit():
    header("PHASE 4  -  Audit Chain Integrity Verification")
    print("""
  The audit chain stores every verification query as a tamper-evident
  entry linked by SHA-256 hashes (blockchain-inspired architecture).
  Any modification to historical records is immediately detectable.
""")
    from integration.audit_chain import AuditChain
    chain  = AuditChain()
    result = chain.verify_chain()
    stats  = chain.stats()

    print(f"  Chain Status : {'INTACT  -  No tampering detected' if result['intact'] else red('COMPROMISED')}")
    print(f"  Total Entries: {result['entries_checked']}")
    print(f"  ASALI queries: {green(str(stats['asali']))}")
    print(f"  SUSPICIOUS   : {yellow(str(stats['suspicious']))}")
    print(f"  NAKALI flagged: {red(str(stats['nakali']))}")
    print(f"  Last Hash    : {dim(str(stats.get('last_hash',' - '))[:32]+'...')}")

    # Demo: Show item history for a NAKALI item
    history = chain.get_item_history("MED-NAKALI-001")
    if history:
        print(f"\n  Audit trail for MED-NAKALI-001:")
        for entry in history:
            print(f"    [{entry['entry_id']}] {entry['verdict']} | Score: {entry['trust_score']} | {entry['queried_at'][:16]}")
    return result


# --- Phase 5: Cross-DB Integration Summary -----------------------------------
def phase5_integration_summary():
    header("PHASE 5  -  Heterogeneous Integration Summary")
    print("""
  +-------------------------------------------------------------+
  |           INTEGRATION ENGINE KEY FEATURES                   |
  +-------------------------------------------------------------+
  |                                                             |
  |  Problem: 4 databases, 4 different column names for the     |
  |           same physical item barcode                        |
  |                                                             |
  |  Solution: JSON Ontology Bridge (schema_mapping.json)       |
  |            maps canonical "item_code" -> DB-specific aliases |
  |                                                             |
  |  Trust Engine: 10 weighted signals across all 4 DBs         |
  |    * Manufacturer registration (DB3)       -  40pt deduction  |
  |    * Ministry blacklist (DB4)              -  20pt deduction  |
  |    * Distributor authorization (DB2 x DB3)   -  20pt deduction  |
  |    * Multi-location anomaly (DB1)          -  25pt deduction  |
  |    * Supply chain gap (DB1 x DB2)            -  20pt deduction  |
  |    * Product recall (DB3)                  -  15pt deduction  |
  |    * Lab test fail (DB4)                   -  15pt deduction  |
  |    * Distributor unlicensed (DB2)          -  15pt deduction  |
  |    * Cold chain broken (DB2 x DB3)           -  10pt deduction  |
  |    * Open complaints (DB4)                 -  10pt deduction  |
  |                                                             |
  |  Innovation:                                                |
  |    Hash-chain audit trail (tamper-evident)                |
  |    Multi-signal anomaly detector                          |
  |    Auto-ministry reporting for NAKALI items               |
  |    Supply chain gap analysis (DB1 x DB2 cross-check)        |
  |    Temporal consistency verification                      |
  |    Price anomaly detection                                |
  |    Confidence interval calculation                        |
  |    Interactive HTML dashboard                             |
  +-------------------------------------------------------------+
""")


# --- Main ---------------------------------------------------------------------
def main():
    print("\n" + "#" * 65)
    print(bold(f"  ASALI / NAKALI MEDICINE VERIFICATION SYSTEM"))
    print(bold(f"  Project 2  -  Heterogeneous Data Integration"))
    print(bold(f"  Institute of Informatics & Analytics (IIA)"))
    print("#" * 65)

    start_time = time.time()

    phase1_create_dbs()
    print()
    phase2_seed_data()
    print()
    verdicts = phase3_verify()
    print()
    audit_result = phase4_audit()
    print()
    phase5_integration_summary()

    elapsed = time.time() - start_time

    header("DEMO COMPLETE")
    print(f"""
  Results Summary:
    {green('ASALI       ')}: {verdicts.get('ASALI', 0)} item(s) verified genuine
    {yellow('SUSPICIOUS  ')}: {verdicts.get('SUSPICIOUS', 0)} item(s) flagged for investigation
    {red('NAKALI      ')}: {verdicts.get('NAKALI', 0)} item(s) identified as counterfeit

  Audit Chain : {'Intact' if audit_result['intact'] else 'Compromised'}
  Elapsed     : {elapsed:.1f}s
  Reports     : {os.path.join(BASE, 'reports')}
  Dashboard   : Open  dashboard/index.html  in any browser

  {bold('To verify a specific item:')}
    python api/verify_item.py MED-NAKALI-001
    python api/verify_item.py --report MED-ASALI-004
    python api/verify_item.py --all
    python api/verify_item.py --stats
    python api/verify_item.py --audit
""")


if __name__ == "__main__":
    main()
