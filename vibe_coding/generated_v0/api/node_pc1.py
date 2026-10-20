#!/usr/bin/env python3
"""
node_pc1.py
-----------
Distributed Server Node representing PC 1: Retail Pharmacy POS & Distributor Logistics Node.

Hosted Services on this Node:
  - DB1: Retail POS NoSQL Document Collection
  - DB2: Wholesale Distributor Logistics Relational SQL ERP

Can be run on:
  1. A separate physical laptop/PC on the local network (binds to 0.0.0.0:8011)
  2. An isolated Docker container (asali-pc1-retail)
  3. Local developer workstation on port 8011
"""

from __future__ import annotations
import sys
import os
import time
import json
import sqlite3
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

NOSQL_FILE = os.path.join(BASE_DIR, "data", "nosql_store", "db1_retail_pos.json")
SQL_DB2_FILE = os.path.join(BASE_DIR, "databases", "db2_distributor_ledger.sqlite")


from integration import db_explorer as dbe
from integration.uncertainty import http_api as dq_api

DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")
MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".pdf": "application/pdf",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".txt": "text/plain; charset=utf-8",
}


class NodePc1Handler(BaseHTTPRequestHandler):
    """HTTP Request Handler for PC 1 Services."""

    node_id = "PC1_RETAIL_LOGISTICS_NODE"
    simulated_delay_sec = 0.0

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("X-Node-ID", self.node_id)
        self.send_header("X-Node-Role", "Edge_Retail_And_Supply_Chain")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_HEAD(self):
        self.do_GET()

    def _handle_uncertainty(self, method: str, parsed) -> None:
        """Phase 2: /api/v1/uncertainty/* is answered by the shared module."""
        body = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            body = json.loads(raw) if raw else {}
        status, payload = dq_api.handle(method, parsed.path, parse_qs(parsed.query), body, node=self.node_id)
        self._set_headers(status)
        self.wfile.write(json.dumps(payload, default=str).encode("utf-8"))

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith(dq_api.PREFIX):
            self._handle_uncertainty("POST", parsed)
        elif path == "/api/v1/explorer/operation":
            self._handle_explorer_operation()
        elif path == "/api/v1/explorer/activity/clear":
            self._handle_activity_clear()
        elif path == "/api/v1/explorer/reset":
            self._handle_explorer_reset()
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": f"Endpoint not found: {path}", "node": self.node_id}).encode("utf-8"))

    def do_GET(self):
        if self.simulated_delay_sec > 0:
            time.sleep(self.simulated_delay_sec)

        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path in ["/health", "/api/v1/health"]:
            self._handle_health()
        elif path.startswith(dq_api.PREFIX):
            self._handle_uncertainty("GET", parsed)
        elif path == "/api/v1/pos/scans":
            self._handle_pos_scans(params)
        elif path == "/api/v1/distributor/batches":
            self._handle_distributor_batches(params)
        elif path == "/api/v1/explorer/schema":
            self._handle_explorer_schema(params)
        elif path == "/api/v1/explorer/entries":
            self._handle_explorer_entries(params)
        elif path == "/api/v1/explorer/examples":
            self._handle_explorer_examples()
        elif path == "/api/v1/explorer/validate_chain":
            self._handle_validate_chain()
        elif path == "/api/v1/explorer/activity":
            self._handle_activity(params)
        elif path == "/api/v1/explorer/conflict_scenarios":
            self._handle_conflict_scenarios()
        else:
            # Attempt to serve static dashboard files
            if not self._serve_static_file(path):
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": f"Endpoint not found: {path}", "node": self.node_id}).encode("utf-8"))

    def _handle_activity_clear(self):
        res = dbe.clear_activity_log(node=self.node_id)
        self._set_headers(200)
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def _handle_activity(self, params):
        """Operation feed for this node. Reads are served, never logged."""
        db = params.get("db", ["all"])[0]
        try:
            limit = int(params.get("limit", ["60"])[0])
        except (TypeError, ValueError):
            limit = 60
        res = dbe.get_activity_log(db_id=db, limit=limit, node=self.node_id)
        self._set_headers(200)
        self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))

    def _handle_validate_chain(self):
        res = dbe.validate_audit_chain(node=self.node_id)
        self._set_headers(200)
        self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))

    def _handle_conflict_scenarios(self):
        scenarios = dbe.get_conflict_scenarios()
        self._set_headers(200)
        self.wfile.write(json.dumps(scenarios, indent=2).encode("utf-8"))

    def _serve_static_file(self, req_path: str) -> bool:
        """Serves static dashboard files (HTML, JS, CSS, assets) directly from node."""
        if req_path == "/" or req_path == "":
            rel_path = "index.html"
        else:
            rel_path = req_path.lstrip("/")
        
        target_path = os.path.normpath(os.path.join(DASHBOARD_DIR, rel_path))
        if not target_path.startswith(DASHBOARD_DIR):
            return False
        
        if os.path.exists(target_path) and os.path.isfile(target_path):
            ext = os.path.splitext(target_path)[1].lower()
            content_type = MIME_TYPES.get(ext, "application/octet-stream")
            try:
                with open(target_path, "rb") as f:
                    content = f.read()
                self._set_headers(200, content_type=content_type)
                self.wfile.write(content)
                return True
            except Exception:
                return False
        return False

    def _handle_explorer_schema(self, params: Dict[str, list]):
        db_id = params.get("db", [None])[0]
        schema = dbe.get_all_schemas(db_id, node=self.node_id)
        self._set_headers(200)
        self.wfile.write(json.dumps(schema, indent=2).encode("utf-8"))

    def _handle_explorer_entries(self, params: Dict[str, list]):
        db_id = params.get("db", ["db1"])[0]
        table = params.get("table", ["purchase_events"])[0]
        limit = params.get("limit", ["20"])[0]
        offset = int(params.get("offset", ["0"])[0])
        search = params.get("search", [""])[0]
        res = dbe.get_db_entries(db_id, table, limit=limit, offset=offset, search=search, node=self.node_id)
        self._set_headers(200)
        self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))

    def _handle_explorer_examples(self):
        examples = dbe.get_code_bench_examples()
        self._set_headers(200)
        self.wfile.write(json.dumps(examples, indent=2).encode("utf-8"))

    def _handle_explorer_operation(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body) if body else {}
            db_id = payload.get("db_id", "db1")
            op = payload.get("operation", "VIEW")
            table = payload.get("table", "purchase_events")
            data = payload.get("data", {})

            res = dbe.execute_operation(db_id, op, table, data, node=self.node_id)
            self._set_headers(200)
            self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))

    def _handle_explorer_reset(self):
        res = dbe.reset_explorer_demo_data()
        self._set_headers(200)
        self.wfile.write(json.dumps(res, indent=2).encode("utf-8"))

    def _handle_health(self):
        self._set_headers(200)
        resp = {
            "status": "ONLINE",
            "node_id": self.node_id,
            "role": "Edge Retail POS & Wholesale Distributor ERP",
            "hosted_services": [
                {
                    "service": "DB1_Retail_POS",
                    "paradigm": "NoSQL Document Store (JSON Documents)",
                    "file": "data/nosql_store/db1_retail_pos.json",
                    "status": "READY"
                },
                {
                    "service": "DB2_Distributor_Logistics",
                    "paradigm": "Relational SQL (3NF SQLite)",
                    "file": "databases/db2_distributor_ledger.sqlite",
                    "status": "READY"
                }
            ],
            "timestamp": time.time()
        }
        self.wfile.write(json.dumps(resp, indent=2).encode("ascii"))

    def _handle_pos_scans(self, params: Dict[str, list]):
        """Queries native NoSQL document collection for scan events."""
        scan_code = params.get("scan_code", [""])[0].strip().upper()
        if not scan_code:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "Missing parameter: scan_code"}).encode("ascii"))
            return

        t0 = time.perf_counter()
        matches = []
        if os.path.exists(NOSQL_FILE):
            with open(NOSQL_FILE, "r", encoding="ascii") as f:
                docs = json.load(f)
                for doc in docs:
                    if doc.get("scan_code") == scan_code:
                        matches.append(doc)

        latency = (time.perf_counter() - t0) * 1000
        self._set_headers(200)
        resp = {
            "source_id": "db1_retail_pos",
            "node": self.node_id,
            "paradigm": "NoSQL Document Store",
            "scan_code": scan_code,
            "found": len(matches) > 0,
            "count": len(matches),
            "documents": matches,
            "execution_ms": round(latency, 2)
        }
        self.wfile.write(json.dumps(resp, indent=2).encode("ascii"))

    def _handle_distributor_batches(self, params: Dict[str, list]):
        """Queries relational SQL ledger for batch serial numbers."""
        batch_serial = params.get("batch_serial", [""])[0].strip().upper()
        if not batch_serial:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "Missing parameter: batch_serial"}).encode("ascii"))
            return

        t0 = time.perf_counter()
        batches = []
        distributors = []
        returns = []

        if os.path.exists(SQL_DB2_FILE):
            conn = sqlite3.connect(SQL_DB2_FILE)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.cursor()
                sql = """
                    SELECT db.*, d.company_name as dist_name, d.is_authorized,
                           d.license_no as dist_license, d.license_expiry as dist_license_expiry
                    FROM distribution_batches db
                    LEFT JOIN distributors d ON db.distributor_id = d.distributor_id
                    WHERE db.batch_serial = ?
                    ORDER BY db.dispatch_date DESC
                """
                cur.execute(sql, (batch_serial,))
                batches = [dict(r) for r in cur.fetchall()]

                dist_ids = list(set(b["distributor_id"] for b in batches if b.get("distributor_id")))
                if dist_ids:
                    placeholders = ",".join("?" * len(dist_ids))
                    cur.execute(f"SELECT * FROM distributors WHERE distributor_id IN ({placeholders})", dist_ids)
                    distributors = [dict(r) for r in cur.fetchall()]

                cur.execute("SELECT * FROM return_log WHERE batch_serial = ?", (batch_serial,))
                returns = [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()

        latency = (time.perf_counter() - t0) * 1000
        self._set_headers(200)
        resp = {
            "source_id": "db2_distributor_ledger",
            "node": self.node_id,
            "paradigm": "Relational SQL RDBMS",
            "batch_serial": batch_serial,
            "found": len(batches) > 0,
            "count": len(batches),
            "batches": batches,
            "distributors": distributors,
            "returns": returns,
            "execution_ms": round(latency, 2)
        }
        self.wfile.write(json.dumps(resp, indent=2).encode("ascii"))

    def log_message(self, format, *args):
        # Clean logging
        pass


def run_node_pc1(host: str = "0.0.0.0", port: int = 8011, delay: float = 0.0):
    NodePc1Handler.simulated_delay_sec = delay
    server = HTTPServer((host, port), NodePc1Handler)
    print(f"[*] PC 1 Node Server started on http://{host}:{port}")
    print("    Hosted Services: DB1 (NoSQL Document Store) & DB2 (Relational SQL ERP)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Stopping PC 1 Node Server.")
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Start PC 1 Retail & Supply Chain Node Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (use 0.0.0.0 for LAN access)")
    parser.add_argument("--port", type=int, default=8011, help="Port to bind (default: 8011)")
    parser.add_argument("--delay", type=float, default=0.0, help="Simulate artificial network latency in seconds")
    args = parser.parse_args()
    run_node_pc1(args.host, args.port, args.delay)


if __name__ == "__main__":
    main()
