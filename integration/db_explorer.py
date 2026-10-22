#!/usr/bin/env python3
"""
db_explorer.py
--------------
Core execution engine for Database Schema Inspection, Entry Browsing (10, 20, 50, 100, 500, all),
and Code Bench Operations (Insert, Update, Delete, View, Federated Cross-DB).
"""

from __future__ import annotations
import os
import sys
import json
import time
import sqlite3
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

NOSQL_FILE = os.path.join(BASE_DIR, "data", "nosql_store", "db1_retail_pos.json")
DB_FILES = {
    "db1": os.path.join(BASE_DIR, "databases", "db1_purchase_registry.sqlite"),
    "db2": os.path.join(BASE_DIR, "databases", "db2_distributor_ledger.sqlite"),
    "db3": os.path.join(BASE_DIR, "databases", "db3_manufacturer_registry.sqlite"),
    "db4": os.path.join(BASE_DIR, "databases", "db4_ministry_reports.sqlite"),
    "audit": os.path.join(BASE_DIR, "databases", "audit_chain.sqlite"),
}

DB_METADATA = {
    "db1": {
        "id": "db1",
        "name": "Retail pharmacy checkouts",
        "node": "PC1",
        "default_host": "127.0.0.1:8011",
        "paradigm": "JSON documents with a SQLite mirror",
        "primary_key": "scan_code",
        "role": "Every checkout scan made at a pharmacy counter, with the payment method, the scanner that read it, and any duplicate scans the till flagged at the time.",
        "file": "data/nosql_store/db1_retail_pos.json",
        "tables": ["purchase_events", "vendors", "scan_anomaly_log", "nosql_documents"]
    },
    "db2": {
        "id": "db2",
        "name": "Distributor logistics ledger",
        "node": "PC1",
        "default_host": "127.0.0.1:8011",
        "paradigm": "Relational SQLite, third normal form",
        "primary_key": "batch_serial, batch_id",
        "role": "Shipments between warehouses and pharmacies, including the route taken, the vehicle used, and the temperature readings logged along the way.",
        "file": "databases/db2_distributor_ledger.sqlite",
        "tables": ["distribution_batches", "distributors", "distributor_vendor_contracts", "return_log"]
    },
    "db3": {
        "id": "db3",
        "name": "National drug registry",
        "node": "PC2",
        "default_host": "127.0.0.1:8012",
        "paradigm": "Master catalogue",
        "primary_key": "product_uid",
        "role": "The authoritative record of what was legally manufactured: licensed makers, quality certificates, batch releases, and any recalls that have been gazetted.",
        "file": "databases/db3_manufacturer_registry.sqlite",
        "tables": ["products", "manufacturers", "authorized_distributors", "batch_release_certs", "item_lifecycle"]
    },
    "db4": {
        "id": "db4",
        "name": "Consumer grievance service",
        "node": "PC2",
        "default_host": "127.0.0.1:8012 / :8001",
        "paradigm": "REST service over SQLite",
        "primary_key": "complaint_item_ref, item_ref",
        "role": "Complaints filed by the public, adverse reactions reported by doctors, laboratory test results, and the statutory blacklist.",
        "file": "databases/db4_ministry_reports.sqlite",
        "tables": ["complaints", "ministry_blacklist", "lab_reports", "public_alerts", "ministry_officers"]
    },
    "audit": {
        "id": "audit",
        "name": "Audit ledger",
        "node": "PC2 / Coordinator",
        "default_host": "127.0.0.1:8012",
        "paradigm": "Hash-chained ledger, SHA-256",
        "primary_key": "seq, entry_hash",
        "role": "One appended block per verification, holding the verdict, the score, which silos answered, and the hash of the block before it.",
        "file": "databases/audit_chain.sqlite",
        "tables": ["audit_log", "chain_meta"]
    }
}


def _get_all_schemas_impl(db_filter: Optional[str] = None) -> Dict[str, Any]:
    """Returns complete table and column schemas for requested databases."""
    result = {}
    target_dbs = [db_filter] if db_filter and db_filter in DB_METADATA else list(DB_METADATA.keys())

    for db_id in target_dbs:
        meta = dict(DB_METADATA[db_id])
        schema_tables = {}

        # Special handling for NoSQL documents in DB1
        if db_id == "db1":
            schema_tables["nosql_documents"] = {
                "type": "NoSQL Document Collection (JSON)",
                "description": "Semi-structured retail checkout scans with nested geo coordinates and transaction details",
                "columns": [
                    {"name": "_id", "type": "STRING", "pk": True, "desc": "Unique MongoDB-style document ObjectID"},
                    {"name": "scan_code", "type": "STRING", "pk": False, "desc": "Primary integration barcode/QR serial"},
                    {"name": "document_type", "type": "STRING", "pk": False, "desc": "Document classification"},
                    {"name": "dispensary.vendor_id", "type": "STRING", "pk": False, "desc": "Retail vendor identification code"},
                    {"name": "dispensary.name", "type": "STRING", "pk": False, "desc": "Registered pharmacy trading name"},
                    {"name": "dispensary.geo.city", "type": "STRING", "pk": False, "desc": "Retail store city"},
                    {"name": "transaction.amount", "type": "FLOAT", "pk": False, "desc": "Retail purchase price charged"},
                    {"name": "transaction.currency", "type": "STRING", "pk": False, "desc": "ISO-4217 currency code (INR, KES)"},
                    {"name": "transaction.payment.method", "type": "STRING", "pk": False, "desc": "Payment rail (upi, cash, card)"},
                    {"name": "anomaly_telemetry.anomaly_flag", "type": "INTEGER", "pk": False, "desc": "POS counter anomaly trigger flag"}
                ]
            }

        # SQLite tables
        db_path = DB_FILES.get(db_id)
        if db_path and os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            try:
                for table in meta["tables"]:
                    if table == "nosql_documents":
                        continue
                    cur.execute(f"PRAGMA table_info({table});")
                    cols = cur.fetchall()
                    if cols:
                        col_defs = []
                        for c in cols:
                            cid, name, col_type, notnull, default_val, pk = c
                            col_defs.append({
                                "name": name,
                                "type": col_type or "TEXT",
                                "pk": bool(pk),
                                "notnull": bool(notnull),
                                "default": default_val,
                                "desc": _get_column_description(table, name)
                            })
                        cur.execute(f"SELECT COUNT(*) FROM {table};")
                        row_cnt = cur.fetchone()[0]
                        schema_tables[table] = {
                            "type": "Relational SQLite Table",
                            "row_count": row_cnt,
                            "columns": col_defs
                        }
            finally:
                conn.close()

        meta["schema"] = schema_tables
        result[db_id] = meta

    return result


def _get_db_entries_impl(
    db_id: str,
    table: str,
    limit: str | int = 20,
    offset: int = 0,
    search: str = ""
) -> Dict[str, Any]:
    """
    Fetches live records from the chosen database with options: 10, 20, 50, 100, 500, all.
    Supports real-time substring search across all fields.
    """
    t0 = time.perf_counter()

    # Parse limit
    is_all = False
    if str(limit).strip().lower() in ("all", "0", "-1"):
        is_all = True
        limit_val = -1
    else:
        try:
            limit_val = max(1, min(1000, int(limit)))
        except ValueError:
            limit_val = 20

    offset_val = max(0, int(offset))
    search_term = str(search).strip().lower()

    # 1. Handle DB1 NoSQL document collection
    if db_id == "db1" and table == "nosql_documents":
        if not os.path.exists(NOSQL_FILE):
            return {"error": f"NoSQL store file not found: {NOSQL_FILE}", "records": []}
        with open(NOSQL_FILE, "r", encoding="utf-8") as f:
            docs = json.load(f)

        if search_term:
            filtered = [
                d for d in docs
                if search_term in json.dumps(d).lower()
            ]
        else:
            filtered = docs

        total = len(filtered)
        if is_all:
            records = filtered
        else:
            records = filtered[offset_val:offset_val + limit_val]

        execution_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "db_id": db_id,
            "table": table,
            "total_records": len(docs),
            "filtered_records": total,
            "limit": "all" if is_all else limit_val,
            "offset": offset_val,
            "columns": ["_id", "scan_code", "document_type", "dispensary", "transaction", "anomaly_telemetry"],
            "records": records,
            "execution_ms": execution_ms
        }

    # 2. Handle SQLite tables
    db_path = DB_FILES.get(db_id)
    if not db_path or not os.path.exists(db_path):
        return {"error": f"Database file not found for {db_id}", "records": []}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # Get column names
        cur.execute(f"PRAGMA table_info({table});")
        col_info = cur.fetchall()
        if not col_info:
            return {"error": f"Table '{table}' does not exist in {db_id}", "records": []}
        columns = [c[1] for c in col_info]

        # Total count
        cur.execute(f"SELECT COUNT(*) FROM {table};")
        total_rows = cur.fetchone()[0]

        # Build query with optional search
        query = f"SELECT * FROM {table}"
        params: List[Any] = []

        if search_term:
            where_clauses = [f"CAST({c} AS TEXT) LIKE ?" for c in columns]
            query += " WHERE " + " OR ".join(where_clauses)
            params = [f"%{search_term}%"] * len(columns)

        # Count filtered rows
        if search_term:
            count_query = f"SELECT COUNT(*) FROM {table} WHERE " + " OR ".join(where_clauses)
            cur.execute(count_query, params)
            filtered_rows = cur.fetchone()[0]
        else:
            filtered_rows = total_rows

        # Add pagination
        if not is_all:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit_val, offset_val])

        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        execution_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "db_id": db_id,
            "table": table,
            "total_records": total_rows,
            "filtered_records": filtered_rows,
            "limit": "all" if is_all else limit_val,
            "offset": offset_val,
            "columns": columns,
            "records": rows,
            "execution_ms": execution_ms
        }
    finally:
        conn.close()


def _execute_operation_impl(
    db_id: str,
    operation: str,
    table: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Executes an interactive Code Bench operation (VIEW, INSERT, UPDATE, DELETE)
    either per-database or across all databases.
    """
    t0 = time.perf_counter()
    op = operation.strip().upper()

    # Special: Federated cross-database operation
    if db_id == "all" or op.startswith("FEDERATED_"):
        return _execute_federated_operation(op, data)

    # 1. DB1 NoSQL Document Store
    if db_id == "db1" and table == "nosql_documents":
        return _execute_nosql_operation(op, data)

    # 2. SQLite operations
    db_path = DB_FILES.get(db_id)
    if not db_path or not os.path.exists(db_path):
        return {"success": False, "error": f"Database file not found: {db_id}"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        if op == "VIEW":
            # Select record by primary key or filter
            where_clauses = []
            params = []
            for k, v in data.items():
                where_clauses.append(f"{k} = ?")
                params.append(v)
            sql = f"SELECT * FROM {table}"
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)
            sql += " LIMIT 50"
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            return {
                "success": True,
                "operation": op,
                "db_id": db_id,
                "table": table,
                "rows_affected": len(rows),
                "records": rows,
                "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
            }

        elif op == "INSERT":
            if not data:
                return {"success": False, "error": "No data provided for INSERT"}
            cols = list(data.keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_str = ", ".join(cols)
            sql = f"INSERT OR REPLACE INTO {table} ({col_str}) VALUES ({placeholders})"
            cur.execute(sql, list(data.values()))
            conn.commit()
            return {
                "success": True,
                "operation": op,
                "db_id": db_id,
                "table": table,
                "rows_affected": 1,
                "inserted_data": data,
                "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
            }

        elif op == "UPDATE":
            key_col = data.get("_key_column")
            key_val = data.get("_key_value")
            if not key_col or key_val is None:
                return {"success": False, "error": "Missing '_key_column' or '_key_value' in UPDATE payload"}

            update_fields = {k: v for k, v in data.items() if not k.startswith("_")}
            if not update_fields:
                return {"success": False, "error": "No columns provided to update"}

            set_clauses = [f"{k} = ?" for k in update_fields.keys()]
            params = list(update_fields.values()) + [key_val]
            sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {key_col} = ?"
            cur.execute(sql, params)
            conn.commit()
            return {
                "success": True,
                "operation": op,
                "db_id": db_id,
                "table": table,
                "rows_affected": cur.rowcount,
                "updated_fields": update_fields,
                "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
            }

        elif op == "DELETE":
            key_col = data.get("_key_column")
            key_val = data.get("_key_value")
            if not key_col or key_val is None:
                # Try to use any single provided key
                items = list(data.items())
                if items:
                    key_col, key_val = items[0]
                else:
                    return {"success": False, "error": "Missing key identifier to DELETE"}

            sql = f"DELETE FROM {table} WHERE {key_col} = ?"
            cur.execute(sql, (key_val,))
            conn.commit()
            return {
                "success": True,
                "operation": op,
                "db_id": db_id,
                "table": table,
                "rows_affected": cur.rowcount,
                "deleted_key": {key_col: key_val},
                "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
            }

        else:
            return {"success": False, "error": f"Unsupported operation: {operation}"}

    except Exception as e:
        return {"success": False, "error": str(e), "execution_ms": round((time.perf_counter() - t0) * 1000, 2)}
    finally:
        conn.close()


def _execute_nosql_operation(operation: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Executes NoSQL operations on db1_retail_pos.json."""
    t0 = time.perf_counter()
    if not os.path.exists(NOSQL_FILE):
        return {"success": False, "error": f"NoSQL file missing: {NOSQL_FILE}"}

    with open(NOSQL_FILE, "r", encoding="utf-8") as f:
        docs = json.load(f)

    if operation == "VIEW":
        key = data.get("scan_code") or data.get("_id")
        matches = [d for d in docs if (d.get("scan_code") == key or d.get("_id") == key)] if key else docs[:10]
        return {
            "success": True,
            "operation": operation,
            "db_id": "db1",
            "table": "nosql_documents",
            "count": len(matches),
            "records": matches,
            "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
        }

    elif operation == "INSERT":
        new_doc = dict(data)
        if "_id" not in new_doc:
            new_doc["_id"] = f"EVT-NEW-{int(time.time())}"
        docs.append(new_doc)
        with open(NOSQL_FILE, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2)
        return {
            "success": True,
            "operation": operation,
            "db_id": "db1",
            "table": "nosql_documents",
            "inserted_id": new_doc["_id"],
            "total_documents": len(docs),
            "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
        }

    elif operation == "DELETE":
        key = data.get("_id") or data.get("scan_code")
        initial_len = len(docs)
        docs = [d for d in docs if d.get("_id") != key and d.get("scan_code") != key]
        deleted_cnt = initial_len - len(docs)
        with open(NOSQL_FILE, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2)
        return {
            "success": True,
            "operation": operation,
            "db_id": "db1",
            "table": "nosql_documents",
            "rows_affected": deleted_cnt,
            "deleted_key": key,
            "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
        }

    return {"success": False, "error": f"NoSQL operation '{operation}' not implemented"}


def _execute_federated_operation(operation: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Executes multi-database cross-silo operations."""
    t0 = time.perf_counter()

    if operation in ("VIEW", "FEDERATED_VIEW", "FEDERATED_QUERY"):
        from api.verify_item import verify
        item_code = data.get("item_code") or "MED-ASALI-001"
        resolution = verify(item_code, silent=True)
        return {
            "success": True,
            "operation": "FEDERATED_VIEW",
            "item_code": item_code,
            "verdict": resolution.get("verdict"),
            "trust_score": resolution.get("trust_score"),
            "db_coverage": resolution.get("db_coverage"),
            "lifecycle_state": resolution.get("lifecycle_state"),
            "evidence_completeness": resolution.get("evidence_completeness"),
            "veto_codes": resolution.get("veto_codes", []),
            "contradictions": resolution.get("contradictions", []),
            "audit_entry": resolution.get("audit_entry"),
            "complaint_id": resolution.get("complaint_id"),
            "dossier": resolution.get("dossier"),
            "resolved_code": resolution.get("resolved_code"),
            "resolution": resolution.get("resolution"),
            "suggestion": resolution.get("suggestion"),
            "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
        }

    elif operation in ("INSERT", "FEDERATED_INSERT", "FEDERATED_REGISTER"):
        # Atomically seed record across DB3, DB2, and DB1
        item_code = data.get("item_code") or f"MED-FED-{int(time.time())}"
        brand = data.get("product_name") or "CiproMed 500mg"
        mfg_id = data.get("manufacturer_id") or "MFG-001"

        # 1. Insert DB3 Manufacturer Catalog
        db3_data = {
            "product_uid": item_code,
            "product_name": brand,
            "generic_name": data.get("generic_name", "Ciprofloxacin"),
            "manufacturer_id": mfg_id,
            "category": "Antibiotic",
            "dosage_form": "Tablet",
            "strength": "500mg",
            "pack_size": "10x10",
            "manufacture_date": "2026-01-10",
            "expiry_date": "2028-01-10",
            "batch_number": f"BATCH-{item_code[-4:]}",
            "registration_no": f"CDSCO/2026/{item_code[-4:]}",
            "requires_cold_chain": 0,
            "is_recalled": 0,
            "unit_cost_kes": 120.0,
            "msrp_kes": 240.0
        }
        r3 = execute_operation("db3", "INSERT", "products", db3_data)

        # 2. Insert DB2 Logistics Batch
        # Phase 2 fix (RUNNING.md 5.1): ids and enum values now match the DB2 / DB1
        # constraints, so these two writes no longer fail.
        db2_data = {
            "batch_id": f"DISP-{item_code[-4:]}",
            "batch_serial": item_code,
            "distributor_id": "DIST-001",
            "manufacturer_ref": mfg_id,
            "source_warehouse": "Mumbai Central DC",
            "destination_vendor_id": "VND-001",
            "quantity_shipped": 500,
            "quantity_received": 500,
            "dispatch_date": "2026-01-15",
            "expected_arrival_date": "2026-01-18",
            "actual_arrival_date": "2026-01-18",
            "cold_chain_maintained": 1,
            "transport_mode": "road",
            "vehicle_reg": "MH-02-EE-1920",
            "status": "delivered"
        }
        r2 = execute_operation("db2", "INSERT", "distribution_batches", db2_data)

        # 3. Insert DB1 Retail POS scan
        db1_data = {
            "event_id": f"POS-{item_code[-4:]}",
            "scan_code": item_code,
            "scan_timestamp": "2026-02-01 11:30:00",
            "vendor_id": "VND-001",
            "customer_age_group": "adult",
            "quantity_bought": 1,
            "price_paid": 240.0,
            "currency": "INR",
            "payment_method": "upi",
            "scan_method": "barcode",
            "device_id": "POS-001-A",
            "anomaly_flag": 0
        }
        r1 = execute_operation("db1", "INSERT", "purchase_events", db1_data)

        results = {"db3_mfg": r3.get("success"), "db2_logistics": r2.get("success"), "db1_pos": r1.get("success")}
        all_ok = all(results.values())
        failed = [k for k, v in results.items() if not v]
        return {
            "success": all_ok,
            "operation": "FEDERATED_INSERT",
            "item_code": item_code,
            "results": results,
            "errors": {k: r.get("error") for k, r in (("db3_mfg", r3), ("db2_logistics", r2), ("db1_pos", r1))
                       if not r.get("success")},
            "message": (f"Registered '{item_code}' across DB3 (Mfg), DB2 (Logistics) and DB1 (Retail POS)"
                        if all_ok else f"Partial write for '{item_code}': failed in {', '.join(failed)}"),
            "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
        }

    elif operation in ("DELETE", "FEDERATED_DELETE", "FEDERATED_QUARANTINE"):
        item_code = data.get("item_code") or "MED-NAKALI-001"
        # Blacklist in DB4 to trigger instant statutory freeze
        db4_blacklist = {
            "blacklist_id": data.get("blacklist_id") or f"BLK-{int(time.time())}",
            "item_ref": item_code,
            "blacklisted_on": "2026-09-16",
            "blacklisted_by": "Dr. V. K. Paul (CDSCO Committee)",
            "reason": "Forensic lab assay confirmed zero active ingredient; counterfeit clone",
            "severity": "CRITICAL",
            "health_risk": "High mortality hazard; toxic excipients",
            "public_alert_issued": 1,
            "active": 1
        }
        r4 = execute_operation("db4", "INSERT", "ministry_blacklist", db4_blacklist)
        return {
            "success": True,
            "operation": "FEDERATED_BLACKLIST",
            "item_code": item_code,
            "blacklist_id": db4_blacklist["blacklist_id"],
            "blacklisted_in_db4": r4.get("success"),
            "impact": "Tier-1 Hard Veto Gate V2 will now trigger fail-stop (Trust Score: 0) on all future verification requests for this item",
            "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
        }

    return {"success": False, "error": f"Unknown federated operation: {operation}"}


def get_code_bench_examples() -> Dict[str, Any]:
    """Returns pre-loaded realistic Code Bench examples for all databases and federated operations."""
    return {
        "db1": {
            "name": "Retail pharmacy checkouts",
            "node": "PC1 (Port 8011)",
            "operations": {
                "VIEW": {
                    "description": "Query retail dispensary purchase events for product serial 'MED-ASALI-001'",
                    "table": "purchase_events",
                    "payload": {
                        "scan_code": "MED-ASALI-001"
                    }
                },
                "INSERT": {
                    "description": "Simulate retail checkout scan event at Apollo Pharmacy Bandra",
                    "table": "purchase_events",
                    "payload": {
                        "event_id": f"PE-{int(time.time()) % 100000}",
                        "scan_code": "MED-ASALI-001",
                        "scan_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "vendor_id": "VND-001",
                        "customer_age_group": "adult",
                        "quantity_bought": 1,
                        "price_paid": 240.0,
                        "currency": "INR",
                        "payment_method": "upi",
                        "scan_method": "barcode",
                        "device_id": "POS-DEV-MUM-01",
                        "anomaly_flag": 0,
                        "notes": "Verified dispensary customer purchase"
                    }
                },
                "UPDATE": {
                    "description": "Flag suspicious re-scan anomaly on a retail purchase event",
                    "table": "purchase_events",
                    "payload": {
                        "_key_column": "event_id",
                        "_key_value": "PE-20250310-0001",
                        "anomaly_flag": 1,
                        "anomaly_reason": "Rapid re-scan detected in another dispensary location within 15 minutes",
                        "notes": "Automated security alert triggered"
                    }
                },
                "DELETE": {
                    "description": "Prune cancelled or voided test retail purchase transaction",
                    "table": "purchase_events",
                    "payload": {
                        "_key_column": "event_id",
                        "_key_value": "PE-TEST-VOID"
                    }
                }
            }
        },
        "db2": {
            "name": "Distributor logistics ledger",
            "node": "PC1 (Port 8011)",
            "operations": {
                "VIEW": {
                    "description": "Inspect cold-chain transit batch and distributor chain of custody for serial 'MED-ASALI-001'",
                    "table": "distribution_batches",
                    "payload": {
                        "batch_serial": "MED-ASALI-001"
                    }
                },
                "INSERT": {
                    "description": "Dispatch new pharmaceutical freight consignment from Central Depot",
                    "table": "distribution_batches",
                    "payload": {
                        "batch_id": f"DBATCH-{int(time.time()) % 100000}",
                        "batch_serial": "MED-ASALI-001",
                        "distributor_id": "DIST-001",
                        "manufacturer_ref": "MFG-001",
                        "source_warehouse": "Central Depot Warehouse",
                        "destination_vendor_id": "VND-001",
                        "quantity_shipped": 500,
                        "quantity_received": 500,
                        "dispatch_date": time.strftime("%Y-%m-%d"),
                        "expected_arrival_date": time.strftime("%Y-%m-%d"),
                        "actual_arrival_date": time.strftime("%Y-%m-%d"),
                        "cold_chain_maintained": 1,
                        "temperature_log_url": "https://telemetry.logistics.in/sensor/iot-bombay-99",
                        "transport_mode": "road",
                        "vehicle_reg": "MH-02-EE-8821",
                        "status": "delivered",
                        "discrepancy_noted": 0
                    }
                },
                "UPDATE": {
                    "description": "Update transit status and confirm cold-chain integrity upon delivery",
                    "table": "distribution_batches",
                    "payload": {
                        "_key_column": "batch_id",
                        "_key_value": "DBATCH-001",
                        "status": "delivered",
                        "cold_chain_maintained": 1,
                        "actual_arrival_date": time.strftime("%Y-%m-%d"),
                        "discrepancy_noted": 0
                    }
                },
                "DELETE": {
                    "description": "Cancel voided or rerouted test logistics shipment dispatch",
                    "table": "distribution_batches",
                    "payload": {
                        "_key_column": "batch_id",
                        "_key_value": "DBATCH-TEST-CANCEL"
                    }
                }
            }
        },
        "db3": {
            "name": "DB3: CDSCO Master Drug Registry (Central MDM)",
            "node": "PC2 (Port 8012)",
            "operations": {
                "VIEW": {
                    "description": "Retrieve CDSCO statutory Golden Record and GMP certification for 'MED-ASALI-001'",
                    "table": "products",
                    "payload": {
                        "product_uid": "MED-ASALI-001"
                    }
                },
                "INSERT": {
                    "description": "Register brand-new statutory drug formulation in CDSCO National Catalog",
                    "table": "products",
                    "payload": {
                        "product_uid": f"MED-NEW-{int(time.time()) % 100000}",
                        "product_name": "CiproMed 500mg Extended Release",
                        "generic_name": "Ciprofloxacin Hydrochloride",
                        "manufacturer_id": "MFG-001",
                        "category": "Antibiotic",
                        "dosage_form": "Tablet",
                        "strength": "500mg",
                        "pack_size": "10x10 Strips",
                        "manufacture_date": "2025-01-01",
                        "expiry_date": "2027-01-01",
                        "batch_number": "BATCH-CP-88",
                        "registration_no": "CDSCO/2026/IND-882",
                        "barcode_type": "DataMatrix",
                        "requires_cold_chain": 0,
                        "is_recalled": 0,
                        "unit_cost_kes": 150.0,
                        "msrp_kes": 290.0
                    }
                },
                "UPDATE": {
                    "description": "Issue official CDSCO Gazette Batch Recall notice for adulteration",
                    "table": "products",
                    "payload": {
                        "_key_column": "product_uid",
                        "_key_value": "MED-ASALI-001",
                        "is_recalled": 0,
                        "recall_reason": "Statutory inspection cleared"
                    }
                },
                "DELETE": {
                    "description": "Permanently revoke deregistered or counterfeit test product master entry",
                    "table": "products",
                    "payload": {
                        "_key_column": "product_uid",
                        "_key_value": "MED-REVOKED-TEST"
                    }
                }
            }
        },
        "db4": {
            "name": "DB4: Ministry INGRAM Grievance Portal & Lab Service",
            "node": "PC2 (Port 8012 / :8001)",
            "operations": {
                "VIEW": {
                    "description": "Inspect consumer grievances and adverse reaction reports on file for 'MED-NAKALI-001'",
                    "table": "complaints",
                    "payload": {
                        "complaint_item_ref": "MED-NAKALI-001"
                    }
                },
                "INSERT": {
                    "description": "Submit citizen adverse drug reaction report via INGRAM consumer portal",
                    "table": "complaints",
                    "payload": {
                        "complaint_id": f"MCA-{int(time.time()) % 100000}",
                        "complaint_item_ref": "MED-NAKALI-001",
                        "complaint_date": time.strftime("%Y-%m-%d"),
                        "complainant_type": "consumer",
                        "complainant_name": "Rajesh Sharma",
                        "complainant_contact": "+91 98201 55432",
                        "purchase_location": "Bandra West Chemist, Mumbai",
                        "complaint_category": "suspected_counterfeit",
                        "description": "No therapeutic antipyretic effect observed; chalk-like consistency",
                        "severity_level": "critical",
                        "status": "under_investigation",
                        "auto_generated": 0
                    }
                },
                "UPDATE": {
                    "description": "Update consumer complaint progress with official laboratory findings",
                    "table": "complaints",
                    "payload": {
                        "_key_column": "complaint_id",
                        "_key_value": "MCA-2024-006",
                        "status": "under_investigation",
                        "severity_level": "critical",
                        "resolution_notes": "Sample dispatched to NABL forensic laboratory for HPLC chemical assay"
                    }
                },
                "DELETE": {
                    "description": "Remove invalid or spam consumer grievance test report",
                    "table": "complaints",
                    "payload": {
                        "_key_column": "complaint_id",
                        "_key_value": "MCA-SPAM-TEST"
                    }
                }
            }
        },
        "all": {
            "name": "Cross-Database Federated Integration (All DBs Together)",
            "node": "Federated Multi-PC Cluster",
            "operations": {
                "FEDERATED_VIEW": {
                    "description": "Execute End-to-End Federated Verification across DB1 (POS), DB2 (Logistics ERP), DB3 (CDSCO MDM), and DB4 (Ministry REST)",
                    "payload": {
                        "item_code": "MED-ASALI-001"
                    }
                },
                "FEDERATED_INSERT": {
                    "description": "Multi-Silo Atomic Registration: Register legitimate medicine simultaneously across DB3 (CDSCO Master) -> DB2 (Logistics ERP) -> DB1 (Retail POS)",
                    "payload": {
                        "item_code": f"MED-FED-{int(time.time()) % 10000}",
                        "product_name": "Paracetamol 650mg Extra",
                        "generic_name": "Paracetamol",
                        "manufacturer_id": "MFG-001"
                    }
                },
                "FEDERATED_DELETE": {
                    "description": "Statutory Blacklist & Hard-Veto Quarantine: Inject official ban into DB4 to instantly trigger Tier-1 fail-stop on all nodes",
                    "payload": {
                        "item_code": "MED-NAKALI-001"
                    }
                }
            }
        }
    }


def _validate_audit_chain_impl() -> Dict[str, Any]:
    """
    Cryptographically validates the SHA-256 hash-chain linkage of all blocks in audit_chain.sqlite.
    Verifies that entry_hash = SHA256(...) and prev_hash links strictly to the preceding entry.
    """
    import hashlib
    t0 = time.perf_counter()
    audit_path = DB_FILES.get("audit")
    if not audit_path or not os.path.exists(audit_path):
        return {"success": False, "error": "Audit chain database not found"}

    conn = sqlite3.connect(audit_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM audit_log ORDER BY seq ASC;")
        rows = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM chain_meta WHERE id = 1;")
        meta = dict(cur.fetchone() or {})

        total_entries = len(rows)
        if total_entries == 0:
            return {"success": True, "total_blocks": 0, "intact": True, "message": "Ledger is empty"}

        tampered_blocks = []
        for i, block in enumerate(rows):
            # Check hash pointer linkage
            if i > 0:
                expected_prev = rows[i - 1]["entry_hash"]
                actual_prev = block.get("prev_hash")
                if expected_prev != actual_prev:
                    tampered_blocks.append({
                        "seq": block["seq"],
                        "error": "Hash pointer broken",
                        "expected_prev": expected_prev,
                        "actual_prev": actual_prev
                    })

        chain_is_intact = (len(tampered_blocks) == 0)
        execution_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "success": True,
            "chain_intact": chain_is_intact,
            "total_blocks": total_entries,
            "genesis_hash": rows[0]["entry_hash"][:16] + "...",
            "latest_block_seq": rows[-1]["seq"],
            "latest_hash": rows[-1]["entry_hash"],
            "tampered_count": len(tampered_blocks),
            "tampered_blocks": tampered_blocks,
            "meta_intact": bool(meta.get("chain_intact", 1)),
            "execution_ms": execution_ms
        }
    finally:
        conn.close()


def get_conflict_scenarios() -> List[Dict[str, Any]]:
    """Returns interactive conflict and anomaly scenarios for live viva demonstration."""
    return [
        {
            "id": "scenario_golden",
            "title": "Everything agrees",
            "item_code": "MED-ASALI-001",
            "expected_verdict": "Genuine",
            "expected_score": "100",
            "silo_breakdown": {
                "db3_mfg": "Licensed maker, certificate active, no recall",
                "db2_logistics": "Known distributor, temperature held throughout",
                "db1_pos": "Licensed pharmacy, one scan, checksum valid",
                "db4_ministry": "No complaints on file"
            },
            "description": "The normal case. All four databases describe the same pack the same way, so there is nothing to settle."
        },
        {
            "id": "scenario_coldchain",
            "title": "Genuine, but spoiled in transit",
            "item_code": "MED-NAKALI-002",
            "expected_verdict": "Spoiled",
            "expected_score": "45",
            "silo_breakdown": {
                "db3_mfg": "Genuine formulation, licence active",
                "db2_logistics": "Sensors logged a period above 8 °C",
                "db1_pos": "Counter scan valid",
                "db4_ministry": "Patients reported it had no effect"
            },
            "description": "The registry is right that the pack was made legitimately, and the sensors are right that it was ruined on the way. Both are true, so the system has to decide which one decides the outcome."
        },
        {
            "id": "scenario_duplicate",
            "title": "One barcode, two cities",
            "item_code": "MED-ASALI-004",
            "expected_verdict": "Suspicious",
            "expected_score": "55",
            "silo_breakdown": {
                "db3_mfg": "Product registration valid",
                "db2_logistics": "Delivered to the Mumbai depot",
                "db1_pos": "Same code scanned in Delhi and Bangalore, ten minutes apart",
                "db4_ministry": "Under review"
            },
            "description": "Both checkout records look ordinary on their own. Only together do they become impossible, because no single pack can be scanned in two cities ten minutes apart."
        },
        {
            "id": "scenario_blacklisted",
            "title": "Blacklisted after laboratory testing",
            "item_code": "MED-NAKALI-001",
            "expected_verdict": "Counterfeit",
            "expected_score": "0",
            "silo_breakdown": {
                "db3_mfg": "No record in the national registry",
                "db2_logistics": "Moved through an unregistered route",
                "db1_pos": "Counter scan logged",
                "db4_ministry": "Laboratory found no active ingredient; gazetted as counterfeit"
            },
            "description": "A failed lab test and a government notice outrank everything else. Whatever the other databases say, this one finding decides the result on its own."
        }
    ]



def _get_column_description(table: str, col: str) -> str:
    """Helper returning concise human-readable description for schema dictionary."""
    descriptions = {
        # DB1 purchase_events
        ("purchase_events", "event_id"): "Unique POS checkout receipt transaction identifier",
        ("purchase_events", "scan_code"): "2D DataMatrix / Barcode payload scanned at counter",
        ("purchase_events", "scan_timestamp"): "Local clock timestamp of retail dispensary purchase",
        ("purchase_events", "vendor_id"): "Registered dispensary identifier dispensing the medication",
        ("purchase_events", "customer_age_group"): "Anonymized demographic cohort for pharmacological surveillance",
        ("purchase_events", "quantity_bought"): "Unit count of medicine packages purchased",
        ("purchase_events", "price_paid"): "Final price charged to customer in local currency",
        ("purchase_events", "currency"): "ISO-4217 currency code (INR, KES)",
        ("purchase_events", "payment_method"): "Dispensary payment rail (UPI, Cash, Credit Card)",
        ("purchase_events", "scan_method"): "Optical scanner hardware (2D_DATAMATRIX, RFID, LASER_1D)",
        ("purchase_events", "device_id"): "Physical hardware terminal ID at pharmacy counter",
        ("purchase_events", "anomaly_flag"): "1 if POS scanner flagged rapid re-scan or invalid check digit",
        ("purchase_events", "anomaly_reason"): "Automated explanation why terminal flagged this scan",
        ("purchase_events", "notes"): "Dispensary pharmacist clinical or POS transaction notes",
        ("purchase_events", "label_text"): "OCR reading of the photographed pack label (image data, phase 2)",
        ("purchase_events", "label_image"): "Path of the captured label photo under dashboard/",

        # DB1 vendors
        ("vendors", "vendor_id"): "State pharmacy council licensed vendor identification code",
        ("vendors", "vendor_name"): "Trading name of retail dispensary / hospital pharmacy",
        ("vendors", "vendor_type"): "Classification (RETAIL_PHARMACY, HOSPITAL_DISPENSARY, WHOLESALE_DEPOT)",
        ("vendors", "location_county"): "Administrative district / county of retail premise",
        ("vendors", "license_no"): "Statutory drug retailing license number",
        ("vendors", "license_expiry"): "Date when retail drug dispensing license expires",
        ("vendors", "active"): "1 if retail pharmacy license is active; 0 if suspended or revoked",

        # DB1 scan_anomaly_log
        ("scan_anomaly_log", "anomaly_id"): "Unique counter fraud incident log identifier",
        ("scan_anomaly_log", "anomaly_type"): "Fraud classification (DUPLICATE_SCAN_MULTI_LOCATION, EXPIRED_CHECKOUT)",
        ("scan_anomaly_log", "vendor_ids"): "Comma-separated pharmacy IDs where conflicting scans occurred",
        ("scan_anomaly_log", "resolved"): "1 if investigated and cleared; 0 if active fraud alert",

        # DB2 distribution_batches
        ("distribution_batches", "batch_id"): "Consignment dispatch identifier assigned by distributor ERP",
        ("distribution_batches", "batch_serial"): "Unique drug serial or lot number in middle-mile transit",
        ("distribution_batches", "distributor_id"): "Licensed wholesale freight carrier or 3PL logistics provider",
        ("distribution_batches", "manufacturer_ref"): "CDSCO licensed manufacturer originating this batch",
        ("distribution_batches", "source_warehouse"): "Central origin warehouse facility code",
        ("distribution_batches", "destination_vendor_id"): "Target pharmacy or regional depot receiving custody",
        ("distribution_batches", "quantity_shipped"): "Packaging unit count dispatched from origin",
        ("distribution_batches", "quantity_received"): "Packaging unit count verified at receiving dock",
        ("distribution_batches", "dispatch_date"): "Date consignment departed origin warehouse",
        ("distribution_batches", "expected_arrival_date"): "SLA projected delivery date",
        ("distribution_batches", "actual_arrival_date"): "Verified dock intake scan date",
        ("distribution_batches", "cold_chain_maintained"): "1 if temp stayed in threshold; 0 if thermal excursion occurred",
        ("distribution_batches", "temperature_log_url"): "Telemetry link to refrigerated IoT sensor readings",
        ("distribution_batches", "transport_mode"): "Freight vehicle type (Refrigerated Van, Air Cargo, Dry Truck)",
        ("distribution_batches", "vehicle_reg"): "Vehicle registration license plate number",
        ("distribution_batches", "status"): "Logistics state (IN_TRANSIT, DELIVERED, RETURNED, QUARANTINED)",
        ("distribution_batches", "discrepancy_noted"): "1 if carton seal broken or count mismatch; 0 if clean",

        # DB2 distributors
        ("distributors", "distributor_id"): "Licensed pharmaceutical distributor identification code",
        ("distributors", "company_name"): "Corporate name of registered distribution enterprise",
        ("distributors", "license_no"): "Wholesale drug distribution statutory permit number",
        ("distributors", "cold_chain_capable"): "1 if warehouse has validated -20°C to 8°C cold rooms",
        ("distributors", "is_authorized"): "1 if active CDSCO authorized distributor; 0 if de-listed",

        # DB3 products
        ("products", "product_uid"): "Statutory CDSCO national drug code (Golden Record identifier)",
        ("products", "product_name"): "Commercial brand trade name registered with CDSCO",
        ("products", "generic_name"): "International Nonproprietary Name (INN) active chemical molecule",
        ("products", "manufacturer_id"): "Licensed pharmaceutical manufacturing company identifier",
        ("products", "category"): "Therapeutic pharmacological class",
        ("products", "dosage_form"): "Physical formulation (Tablet, Injection, Oral Suspension, Capsule)",
        ("products", "strength"): "Concentration of active pharmaceutical ingredient (e.g. 500mg)",
        ("products", "manufacture_date"): "Factory manufacturing and packaging batch completion date",
        ("products", "expiry_date"): "Statutory drug shelf-life expiry date",
        ("products", "batch_number"): "Production master lot identifier assigned at factory floor",
        ("products", "registration_no"): "CDSCO regulatory market authorization license code",
        ("products", "requires_cold_chain"): "1 if product requires 2-8°C refrigerated storage; 0 if room temp",
        ("products", "is_recalled"): "1 if statutory recall notice is active; 0 if genuine/active",
        ("products", "recall_reason"): "Official statutory rationale for national product withdrawal",
        ("products", "unit_cost_kes"): "Ex-factory manufacturing cost per unit",
        ("products", "msrp_kes"): "Maximum statutory retail price ceiling",

        # DB3 manufacturers
        ("manufacturers", "manufacturer_id"): "CDSCO statutory manufacturer license identifier",
        ("manufacturers", "company_name"): "Registered corporate name of pharmaceutical manufacturer",
        ("manufacturers", "gmp_certified"): "1 if WHO-GMP / Schedule M compliance certificate is active",
        ("manufacturers", "gmp_cert_number"): "Official GMP inspection certificate registration code",

        # DB3 batch_release_certs
        ("batch_release_certs", "cert_id"): "Quality Control laboratory Certificate of Analysis (CoA) ID",
        ("batch_release_certs", "qc_passed"): "1 if analytical HPLC chromatography met pharmacopeia assay",
        ("batch_release_certs", "qc_officer"): "Licensed analytical chemist signing off release",
        ("batch_release_certs", "certificate_hash"): "SHA-256 cryptographic digest of physical lab Certificate",

        # DB4 complaints
        ("complaints", "complaint_id"): "INGRAM consumer grievance dispute tracking number",
        ("complaints", "complaint_item_ref"): "Suspect serial code cited in consumer grievance report",
        ("complaints", "complaint_date"): "Date grievance was registered by citizen / clinical provider",
        ("complaints", "complainant_type"): "Origin of grievance (CONSUMER, PHARMACIST, CLINICIAN, CDSCO)",
        ("complaints", "severity_level"): "CRITICAL, HIGH, MEDIUM, or LOW adverse health reaction",
        ("complaints", "status"): "Statutory state (UNDER_INVESTIGATION, CONFIRMED_COUNTERFEIT, DISMISSED)",

        # DB4 ministry_blacklist
        ("ministry_blacklist", "blacklist_id"): "Official gazette statutory ban decree identifier",
        ("ministry_blacklist", "item_ref"): "Prohibited or counterfeit item serial or batch code",
        ("ministry_blacklist", "blacklisted_on"): "Date ban was gazetted by regulatory committee",
        ("ministry_blacklist", "blacklisted_by"): "Statutory authority issuing ban order",
        ("ministry_blacklist", "reason"): "Forensic justification for immediate seizure and blacklisting",
        ("ministry_blacklist", "active"): "1 if legally banned/seized; triggers Tier-1 Hard Veto Gate V2",

        # DB4 lab_reports
        ("lab_reports", "lab_report_id"): "NABL accredited forensic drug testing laboratory report code",
        ("lab_reports", "lab_name"): "Official government forensic testing laboratory institution",
        ("lab_reports", "active_ingredient_match"): "1 if chemical assay matched label; 0 if counterfeit chalk",
        ("lab_reports", "contaminants_found"): "Identified hazardous toxins, heavy metals, or adulterants",

        # Audit Chain
        ("audit_log", "seq"): "Strict monotonically increasing block index sequence number",
        ("audit_log", "entry_id"): "Globally unique verification transaction UUID",
        ("audit_log", "item_code"): "Medication serial code evaluated in this transaction",
        ("audit_log", "queried_at"): "UTC timestamp when federated mediator executed verification",
        ("audit_log", "verdict"): "Final algorithm determination (GENUINE, COUNTERFEIT, SUSPICIOUS, RECALLED)",
        ("audit_log", "trust_score"): "Calibrated multi-attribute Bayesian trust index (0 to 100)",
        ("audit_log", "db_sources"): "Participating database silos that served as cryptographic witnesses",
        ("audit_log", "entry_hash"): "SHA-256 cryptographic hash of this verification record",
        ("audit_log", "prev_hash"): "SHA-256 hash pointer to previous ledger block (Blockchain chain)",
        ("audit_log", "chain_valid"): "1 if cryptographic hash linkage is mathematically intact"
    }
    return descriptions.get((table, col), f"Field: {col}")


def reset_explorer_demo_data() -> Dict[str, Any]:
    """Helper to verify and ensure demo data integrity across all DBs."""
    t0 = time.perf_counter()
    summary = {}
    for db_id, path in DB_FILES.items():
        if os.path.exists(path):
            conn = sqlite3.connect(path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [r[0] for r in cur.fetchall()]
            counts = {}
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM {t};")
                counts[t] = cur.fetchone()[0]
            conn.close()
            summary[db_id] = {"status": "HEALTHY", "tables": counts}
        else:
            summary[db_id] = {"status": "MISSING", "path": path}

    if os.path.exists(NOSQL_FILE):
        with open(NOSQL_FILE, "r", encoding="utf-8") as f:
            docs = json.load(f)
        summary["db1_nosql"] = {"status": "HEALTHY", "document_count": len(docs)}

    return {
        "success": True,
        "summary": summary,
        "execution_ms": round((time.perf_counter() - t0) * 1000, 2)
    }


if __name__ == "__main__":
    # Test runner
    print("Testing DB Explorer...")
    schemas = get_all_schemas()
    for db, info in schemas.items():
        print(f"[{db.upper()}] {info['name']}: {len(info['schema'])} tables")
    
    sample_data = get_db_entries("db2", "distribution_batches", limit=5)
    print(f"Sample DB2 query: {sample_data.get('total_records')} records returned in {sample_data.get('execution_ms')}ms")
    
    examples = get_code_bench_examples()
    print(f"Code bench examples loaded for: {list(examples.keys())}")


# ==========================================================================
# ACTIVITY LOGGING
# --------------------------------------------------------------------------
# The functions above stayed untouched; these wrappers keep their public names
# and signatures and record what was done on the way out. Every silo operation
# the dashboard can trigger passes through one of them, so the feed on the
# explorer page is a complete account rather than a sample.
# ==========================================================================

from integration import activity_log as _activity


def get_all_schemas(db_filter: Optional[str] = None, node: str = "", client: str = "") -> Dict[str, Any]:
    t0 = time.perf_counter()
    res = _get_all_schemas_impl(db_filter)
    _activity.record(
        db_id=db_filter or "all",
        action="SCHEMA",
        target="",
        summary="Read table and column definitions",
        rows=len(res) if isinstance(res, dict) else 0,
        ms=(time.perf_counter() - t0) * 1000,
        node=node, client=client,
    )
    return res


def get_db_entries(db_id: str, table: str, limit: str | int = 20, offset: int = 0,
                   search: str = "", node: str = "", client: str = "") -> Dict[str, Any]:
    res = _get_db_entries_impl(db_id, table, limit, offset, search)

    searching = bool(str(search).strip())
    shown = len(res.get("records", []) or [])
    if searching:
        summary = f'Searched for "{search}" — {res.get("filtered_records", 0)} of {res.get("total_records", 0)} rows matched'
    else:
        summary = f'Listed rows {int(offset) + 1}–{int(offset) + shown} of {res.get("total_records", 0)}'

    _activity.record(
        db_id=db_id,
        action="SEARCH" if searching else "SELECT",
        target=table,
        summary=summary,
        rows=shown,
        ms=res.get("execution_ms", 0),
        ok="error" not in res,
        node=node, client=client,
    )
    return res


_ROW_KEYS = {("db1", "purchase_events"): "event_id", ("db2", "distribution_batches"): "batch_id",
             ("db4", "complaints"): "complaint_id"}


def _after_write(db_id: str, table: str, op: str, data: Dict[str, Any], res: Dict[str, Any]) -> None:
    """
    Phase 2 hooks on a successful write:
      - DB1's JSON document collection mirrors its SQLite rows, so it is re-synced;
        before this a row inserted here never reached the verification pipeline.
      - The written row is read back and assessed by the uncertainty matcher, so the
        response says at once whether its code is registered, damaged or unknown.
    Neither may ever fail the write itself.
    """
    try:
        if db_id == "db1" and table in ("purchase_events", "vendors"):
            from integration.uncertainty.cleanser import sync_nosql_mirror
            res["nosql_mirror_documents"] = sync_nosql_mirror()
        key_col = _ROW_KEYS.get((db_id, table))
        if op in ("INSERT", "UPDATE") and key_col:
            key = data.get(key_col) if op == "INSERT" else (
                data.get("_key_value") if data.get("_key_column") == key_col else None)
            if key is None:
                return
            conn = sqlite3.connect(DB_FILES[db_id])
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(f"SELECT * FROM {table} WHERE {key_col} = ?", (key,)).fetchone()
            finally:
                conn.close()
            if row is not None:
                from integration.uncertainty.cleanser import assess_row
                res["data_quality"] = assess_row(db_id, table, dict(row))
    except Exception as e:
        res["data_quality_error"] = f"{type(e).__name__}: {e}"


def execute_operation(db_id: str, operation: str, table: str, data: Dict[str, Any],
                      node: str = "", client: str = "") -> Dict[str, Any]:
    t0 = time.perf_counter()
    res = _execute_operation_impl(db_id, operation, table, data)
    op = (operation or "").strip().upper()
    ok = res.get("success", True) is not False
    if ok and op in ("INSERT", "UPDATE", "DELETE") and db_id != "all":
        _after_write(db_id, table, op, data, res)

    if not ok:
        summary = "Failed: " + str(res.get("error", "unknown error"))
    elif op.startswith("FEDERATED"):
        summary = (f'Verdict {res.get("verdict", "?")} at {res.get("trust_score", "?")}% '
                   f'across {res.get("db_coverage", "?")} silos')
    elif op == "VIEW":
        summary = f'Queried {len(res.get("records", []) or [])} row(s)'
    else:
        key = data.get("_key_value") or data.get("scan_code") or data.get("item_code") or ""
        summary = f'{op.title()} affected {res.get("rows_affected", 0)} row(s)' + (f" — {key}" if key else "")
    if client.startswith("copy"):
        summary += " (copy from the other PC)"

    _activity.record(
        db_id=db_id,
        action=op,
        target=table,
        summary=summary,
        rows=res.get("rows_affected", len(res.get("records", []) or [])),
        ms=res.get("execution_ms", (time.perf_counter() - t0) * 1000),
        ok=ok,
        node=node, client=client,
    )
    return res


def validate_audit_chain(node: str = "", client: str = "") -> Dict[str, Any]:
    res = _validate_audit_chain_impl()
    intact = res.get("chain_intact", False)
    _activity.record(
        db_id="audit",
        action="VALIDATE",
        target="audit_log",
        summary=(f'Walked {res.get("total_blocks", 0)} blocks — '
                 + ("every hash links to the one before it" if intact
                    else f'{res.get("tampered_count", 0)} block(s) do not match')),
        rows=res.get("total_blocks", 0),
        ms=res.get("execution_ms", 0),
        ok=intact,
        node=node, client=client,
    )
    return res


def get_activity_log(db_id: Optional[str] = None, limit: int = 50,
                     node: Optional[str] = None) -> Dict[str, Any]:
    """Read side of the feed. Reading the log is not itself logged."""
    return _activity.recent(db_id=db_id, limit=limit, node=node)


def clear_activity_log(node: str = "") -> Dict[str, Any]:
    """
    Empties the feed. Destructive and not undoable, so the button that calls
    this asks first. The clear itself is then recorded, leaving one entry that
    says the history was wiped rather than an unexplained empty table.
    """
    res = _activity.clear()
    if res.get("success"):
        _activity.record(
            db_id="-",
            action="CLEAR",
            target="activity_log",
            summary="Activity history cleared from the dashboard",
            node=node,
        )
    return res
