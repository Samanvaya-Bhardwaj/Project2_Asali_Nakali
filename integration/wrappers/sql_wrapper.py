#!/usr/bin/env python3
"""
sql_wrapper.py
--------------
Relational SQL Wrapper for DB2 (Distributor Logistics ERP) and DB3 (CDSCO Master Registry).

Translates canonical query requests into relational SQL with foreign key JOINs,
measures execution latency, and preserves SQL query provenance.
"""

from __future__ import annotations
import os, sqlite3, time
from typing import Any, Dict, List, Optional
from .base_wrapper import BaseWrapper, SourceMetadata

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_DIR = os.path.join(BASE, "databases")


class SqliteRelationalWrapper(BaseWrapper):
    """Wrapper querying relational SQLite / SQL databases with foreign key JOINs."""

    def __init__(self, source_id: str, db_filename: str, source_name: str, native_key: str):
        super().__init__(source_id)
        self.db_filename = db_filename
        self.db_path = os.path.join(DB_DIR, db_filename)
        self.source_name = source_name
        self.native_key = native_key

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_metadata(self) -> SourceMetadata:
        exists = os.path.exists(self.db_path)
        return SourceMetadata(
            source_id=self.source_id,
            source_name=self.source_name,
            source_type="Relational SQL Database",
            paradigm="Relational",
            protocol="SQL Engine / Multi-Table Joins",
            native_key=self.native_key,
            status="ONLINE" if exists else "NOT_FOUND",
            latency_ms=0.8
        )

    def query(self, canonical_key: str, native_filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        start = time.perf_counter()
        if not os.path.exists(self.db_path):
            return {
                "source_id": self.source_id,
                "found": False,
                "error": "Database file not found",
                "execution_time_ms": 0.0
            }

        conn = self._get_conn()
        try:
            cur = conn.cursor()
            if self.source_id == "db2_distributor":
                sql = """
                    SELECT db.*, d.company_name as dist_name, d.is_authorized,
                           d.license_no as dist_license, d.license_expiry as dist_license_expiry
                    FROM distribution_batches db
                    LEFT JOIN distributors d ON db.distributor_id = d.distributor_id
                    WHERE db.batch_serial = ? OR db.batch_id = ?
                    ORDER BY db.dispatch_date DESC
                """
                cur.execute(sql, (canonical_key, canonical_key))
                batches = [dict(r) for r in cur.fetchall()]

                # Return log check
                cur.execute("SELECT * FROM return_log WHERE batch_serial = ? OR batch_serial = (SELECT batch_serial FROM distribution_batches WHERE batch_id = ? LIMIT 1)", (canonical_key, canonical_key))
                returns = [dict(r) for r in cur.fetchall()]

                # Distributors list
                dist_ids = list({b.get("distributor_id") for b in batches if b.get("distributor_id")})
                dists = []
                if dist_ids:
                    placeholders = ",".join("?" * len(dist_ids))
                    cur.execute(f"SELECT * FROM distributors WHERE distributor_id IN ({placeholders})", dist_ids)
                    dists = [dict(r) for r in cur.fetchall()]

                latency = (time.perf_counter() - start) * 1000
                return {
                    "source_id": self.source_id,
                    "native_query": sql.strip().replace("\n", " ").replace("  ", " "),
                    "paradigm": "Relational SQL",
                    "found": len(batches) > 0,
                    "count": len(batches),
                    "batches": batches,
                    "distributors": dists,
                    "returns": returns,
                    "execution_time_ms": round(latency, 2)
                }

            elif self.source_id == "db3_manufacturer":
                sql = """
                    SELECT p.*, m.company_name as mfg_name, m.gmp_certified,
                           m.license_no as cdsco_license_no, m.license_expiry as mfg_license_expiry
                    FROM products p
                    JOIN manufacturers m ON p.manufacturer_id = m.manufacturer_id
                    WHERE p.product_uid = ? OR p.batch_number = ?
                """
                cur.execute(sql, (canonical_key, canonical_key))
                rows = [dict(r) for r in cur.fetchall()]
                prod = rows[0] if rows else None

                auth_dists = []
                batch_cert = None
                if prod:
                    mfg_id = prod.get("manufacturer_id")
                    cur.execute("SELECT * FROM authorized_distributors WHERE manufacturer_id = ? AND active = 1", (mfg_id,))
                    auth_dists = [dict(r) for r in cur.fetchall()]

                    cur.execute("SELECT * FROM batch_release_certs WHERE batch_number = ?", (prod.get("batch_number"),))
                    certs = [dict(r) for r in cur.fetchall()]
                    batch_cert = certs[0] if certs else None

                latency = (time.perf_counter() - start) * 1000
                return {
                    "source_id": self.source_id,
                    "native_query": sql.strip().replace("\n", " ").replace("  ", " "),
                    "paradigm": "Central MDM Relational Catalog",
                    "found": prod is not None,
                    "product": prod,
                    "manufacturer": {"company_name": prod.get("mfg_name"), "gmp_certified": prod.get("gmp_certified")} if prod else None,
                    "authorized_distributors": auth_dists,
                    "batch_cert": batch_cert,
                    "execution_time_ms": round(latency, 2)
                }

            else:
                return {"source_id": self.source_id, "found": False, "error": "Unknown SQL source"}

        finally:
            conn.close()

    def health_check(self) -> bool:
        return os.path.exists(self.db_path)
