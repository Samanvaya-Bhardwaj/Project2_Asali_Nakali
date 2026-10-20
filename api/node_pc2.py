#!/usr/bin/env python3
"""
node_pc2.py
-----------
Distributed Server Node representing PC 2: Government & Regulatory Authority Cloud Node.

Hosted Services on this Node:
  - DB3: CDSCO Central Drug Registry (Master Data Management Relational Catalog)
  - DB4: Ministry INGRAM Grievance & Recall Microservice (Live Public Health REST API)

Can be run on:
  1. A separate physical laptop/PC on the local network (binds to 0.0.0.0:8012)
  2. An isolated Docker container (asali-pc2-authority)
  3. Local developer workstation on port 8012
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

SQL_DB3_FILE = os.path.join(BASE_DIR, "databases", "db3_manufacturer_registry.sqlite")
from api.ministry_service import MinistryDataStore


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


class NodePc2Handler(BaseHTTPRequestHandler):
    """HTTP Request Handler for PC 2 Services."""

    node_id = "PC2_REGULATORY_AUTHORITY_NODE"
    simulated_delay_sec = 0.0
    simulated_partition = False
    ministry_store = MinistryDataStore()

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("X-Node-ID", self.node_id)
        self.send_header("X-Node-Role", "Central_Statutory_Authority")
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
        elif path == "/api/v1/explorer/activity/clear":
            self._handle_activity_clear()
        elif path == "/api/v1/partition/toggle":
            NodePc2Handler.simulated_partition = not NodePc2Handler.simulated_partition
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "partition_active": NodePc2Handler.simulated_partition,
                "node": self.node_id
            }).encode("utf-8"))
        elif path == "/api/v1/explorer/operation":
            self._handle_explorer_operation()
        elif path == "/api/v1/explorer/reset":
            self._handle_explorer_reset()
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": f"Endpoint not found: {path}", "node": self.node_id}).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Allow health check, partition toggle, and explorer endpoints regardless of partition state
        if path in ["/health", "/api/v1/health"]:
            self._handle_health()
            return
        elif path.startswith(dq_api.PREFIX):
            self._handle_uncertainty("GET", parsed)
            return
        elif path == "/api/v1/partition/toggle":
            NodePc2Handler.simulated_partition = not NodePc2Handler.simulated_partition
            self._set_headers(200)
            self.wfile.write(json.dumps({
                "partition_active": NodePc2Handler.simulated_partition,
                "node": self.node_id
            }).encode("utf-8"))
            return
        elif path == "/api/v1/explorer/schema":
            self._handle_explorer_schema(params)
            return
        elif path == "/api/v1/explorer/entries":
            self._handle_explorer_entries(params)
            return
        elif path == "/api/v1/explorer/examples":
            self._handle_explorer_examples()
            return
        elif path == "/api/v1/explorer/validate_chain":
            self._handle_validate_chain()
            return
        elif path == "/api/v1/explorer/activity":
            self._handle_activity(params)
            return
        elif path == "/api/v1/explorer/conflict_scenarios":
            self._handle_conflict_scenarios()
            return

        if self.simulated_partition:
            # Simulate network partition or hardware downtime on PC 2
            self._set_headers(503)
            self.wfile.write(json.dumps({
                "error": "Simulated Network Partition / Host Unreachable",
                "node": self.node_id,
                "status": "PARTITIONED"
            }).encode("utf-8"))
            return

        if self.simulated_delay_sec > 0:
            time.sleep(self.simulated_delay_sec)

        if path == "/api/v1/cdsco/product":
            self._handle_cdsco_product(params)
        elif path == "/api/v1/dossier":
            self._handle_ministry_dossier(params)
        else:
            # Attempt to serve static dashboard files
            if not self._serve_static_file(path):
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": f"Endpoint not found: {path}", "node": self.node_id}).encode("utf-8"))

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
        db_id = params.get("db", ["db3"])[0]
        table = params.get("table", ["products"])[0]
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
            db_id = payload.get("db_id", "db3")
            op = payload.get("operation", "VIEW")
            table = payload.get("table", "products")
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

    def _handle_health(self):
        self._set_headers(200)
        resp = {
            "status": "ONLINE",
            "node_id": self.node_id,
            "role": "CDSCO Drug Master Registry & Ministry Grievance Authority",
            "hosted_services": [
                {
                    "service": "DB3_CDSCO_Manufacturer_Registry",
                    "paradigm": "Central MDM Golden Catalog (Relational SQLite)",
                    "file": "databases/db3_manufacturer_registry.sqlite",
                    "status": "READY"
                },
                {
                    "service": "DB4_Ministry_Recall_And_Lab_Service",
                    "paradigm": "HTTP RESTful Microservice (INGRAM Protocol)",
                    "status": "READY"
                }
            ],
            "partition_simulated": self.simulated_partition,
            "timestamp": time.time()
        }
        self.wfile.write(json.dumps(resp, indent=2).encode("ascii"))

    def _handle_cdsco_product(self, params: Dict[str, list]):
        """Queries CDSCO Central Master Catalog for registered product."""
        product_uid = params.get("product_uid", [""])[0].strip().upper()
        if not product_uid:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "Missing parameter: product_uid"}).encode("ascii"))
            return

        t0 = time.perf_counter()
        prod = None
        auth_dists = []
        batch_cert = None

        if os.path.exists(SQL_DB3_FILE):
            conn = sqlite3.connect(SQL_DB3_FILE)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.cursor()
                sql = """
                    SELECT p.*, m.company_name as mfg_name, m.gmp_certified,
                           m.license_no as cdsco_license_no, m.license_expiry as mfg_license_expiry
                    FROM products p
                    JOIN manufacturers m ON p.manufacturer_id = m.manufacturer_id
                    WHERE p.product_uid = ?
                """
                cur.execute(sql, (product_uid,))
                rows = [dict(r) for r in cur.fetchall()]
                prod = rows[0] if rows else None

                if prod:
                    mfg_id = prod.get("manufacturer_id")
                    cur.execute("SELECT * FROM authorized_distributors WHERE manufacturer_id = ? AND active = 1", (mfg_id,))
                    auth_dists = [dict(r) for r in cur.fetchall()]

                    cur.execute("SELECT * FROM batch_release_certs WHERE batch_number = ?", (prod.get("batch_number"),))
                    certs = [dict(r) for r in cur.fetchall()]
                    batch_cert = certs[0] if certs else None
            finally:
                conn.close()

        latency = (time.perf_counter() - t0) * 1000
        self._set_headers(200)
        resp = {
            "source_id": "db3_manufacturer_registry",
            "node": self.node_id,
            "paradigm": "Central MDM Golden Catalog",
            "product_uid": product_uid,
            "found": prod is not None,
            "product": prod,
            "manufacturer": {"company_name": prod.get("mfg_name"), "gmp_certified": prod.get("gmp_certified")} if prod else None,
            "authorized_distributors": auth_dists,
            "batch_cert": batch_cert,
            "execution_ms": round(latency, 2)
        }
        self.wfile.write(json.dumps(resp, indent=2).encode("ascii"))

    def _handle_ministry_dossier(self, params: Dict[str, list]):
        """Queries Ministry INGRAM store for regulatory dossier."""
        item_ref = params.get("item_ref", [""])[0].strip().upper()
        if not item_ref:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "Missing parameter: item_ref"}).encode("ascii"))
            return

        t0 = time.perf_counter()
        complaints = self.ministry_store.get_complaints(item_ref)
        blacklist = self.ministry_store.get_blacklist(item_ref)
        lab_reports = self.ministry_store.get_lab_reports(item_ref)
        alerts = self.ministry_store.get_alerts(item_ref)
        found = bool(complaints or blacklist or lab_reports or alerts)
        blacklist_entry = blacklist[0] if blacklist else None

        latency = (time.perf_counter() - t0) * 1000
        self._set_headers(200)
        resp = {
            "source_id": "db4_ministry_service",
            "node": self.node_id,
            "paradigm": "HTTP REST Microservice",
            "item_ref": item_ref,
            "found": found,
            "complaints": complaints,
            "blacklist_entry": blacklist_entry,
            "lab_reports": lab_reports,
            "alerts": alerts,
            "execution_ms": round(latency, 2)
        }
        self.wfile.write(json.dumps(resp, indent=2).encode("ascii"))

    def log_message(self, format, *args):
        pass


def run_node_pc2(host: str = "0.0.0.0", port: int = 8012, delay: float = 0.0):
    NodePc2Handler.simulated_delay_sec = delay
    server = HTTPServer((host, port), NodePc2Handler)
    print(f"[*] PC 2 Node Server started on http://{host}:{port}")
    print("    Hosted Services: DB3 (CDSCO Central MDM) & DB4 (Ministry Recall REST API)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Stopping PC 2 Node Server.")
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Start PC 2 Regulatory Authority Node Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (use 0.0.0.0 for LAN access)")
    parser.add_argument("--port", type=int, default=8012, help="Port to bind (default: 8012)")
    parser.add_argument("--delay", type=float, default=0.0, help="Simulate artificial network latency in seconds")
    args = parser.parse_args()
    run_node_pc2(args.host, args.port, args.delay)


if __name__ == "__main__":
    main()
