#!/usr/bin/env python3
"""
create_databases.py
-------------------
Creates all four heterogeneous SQLite databases from their SQL schema files.
Run this FIRST before any seed scripts.
"""

import sqlite3
import os
import sys

BASE  = os.path.dirname(os.path.abspath(__file__))
# ASALI_DB_DIR lets the test suite build into a throwaway directory
DB_DIR     = os.environ.get("ASALI_DB_DIR") or os.path.join(BASE, "databases")
SCHEMA_DIR = os.path.join(BASE, "schema")

DATABASES = {
    "db1_purchase_registry.sqlite":    "schema_db1.sql",
    "db2_distributor_ledger.sqlite":   "schema_db2.sql",
    "db3_manufacturer_registry.sqlite":"schema_db3.sql",
    "db4_ministry_reports.sqlite":     "schema_db4.sql",
}

def create_db(db_filename: str, schema_filename: str) -> None:
    db_path     = os.path.join(DB_DIR, db_filename)
    schema_path = os.path.join(SCHEMA_DIR, schema_filename)

    if os.path.exists(db_path):
        os.remove(db_path)

    if not os.path.exists(schema_path):
        print(f"  [ERROR] Schema file not found: {schema_path}")
        sys.exit(1)

    with open(schema_path, "r") as f:
        sql = f.read()

    conn = sqlite3.connect(db_path)
    conn.executescript(sql)
    conn.commit()
    conn.close()
    print(f"  {db_filename}")

def main():
    os.makedirs(DB_DIR, exist_ok=True)
    print("=" * 60)
    print("  Creating Asali/Nakali Heterogeneous Databases")
    print("=" * 60)
    for db_file, schema_file in DATABASES.items():
        create_db(db_file, schema_file)
    print("=" * 60)
    print("  All 4 databases created successfully.")
    print(f"  Location: {DB_DIR}")

if __name__ == "__main__":
    main()
