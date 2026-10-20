#!/usr/bin/env python3
"""
rebuild_data.py
---------------
Rebuilds every silo from scratch, in order:

  1. create the four SQLite databases from schema/
  2. curated phase-1 seeds (the 20 benchmark items)
  3. the phase-2 uncertain dataset and its ground truth
  4. label images for the records captured by camera (needs Pillow; optional)
  5. the DB1 NoSQL document mirror
  6. fit the linkage model and benchmark every algorithm

The audit chain and the activity log are left alone. The cleansing lineage store
is reset, because its entries describe rows that no longer exist.

    python scripts/rebuild_data.py
    python scripts/rebuild_data.py --no-train --no-images
"""

from __future__ import annotations
import argparse
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)


def main():
    ap = argparse.ArgumentParser(description="Rebuild all silos and the trained model")
    ap.add_argument("--no-train", action="store_true", help="skip fitting / benchmarking")
    ap.add_argument("--no-images", action="store_true", help="skip rendering label images")
    ap.add_argument("--quick", action="store_true", help="faster, smaller benchmark")
    args = ap.parse_args()
    t0 = time.time()

    import create_databases
    from data import seed_db1, seed_db2, seed_db3, seed_db4, seed_nosql_db1
    from data import generate_uncertain_data, render_label_images
    from integration.uncertainty import paths

    print("[1/6] Creating databases")
    create_databases.main()
    print("[2/6] Curated seeds")
    seed_db3.seed()
    seed_db2.seed()
    seed_db1.seed()
    seed_db4.seed()
    print("[3/6] Uncertain dataset")
    generate_uncertain_data.main()
    print("[4/6] Label images")
    if args.no_images:
        print("  skipped")
    else:
        render_label_images.main()
    print("[5/6] NoSQL mirror")
    seed_nosql_db1.generate_nosql_collection()
    dq = paths.db_path("dq")
    if os.path.exists(dq):
        os.remove(dq)
        print("  cleansing lineage reset")
    print("[6/6] Linkage model")
    if args.no_train:
        print("  skipped")
    else:
        from integration.uncertainty import train
        train.print_table(train.run(quick=args.quick))
    print(f"\nDone in {time.time() - t0:.1f} s.")


if __name__ == "__main__":
    main()
