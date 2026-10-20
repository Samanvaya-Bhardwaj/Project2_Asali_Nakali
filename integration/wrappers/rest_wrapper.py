#!/usr/bin/env python3
"""
rest_wrapper.py
---------------
HTTP RESTful Client Wrapper for DB4: Ministry of Consumer Affairs & CDSCO Grievance Portal.

Communicates with the government regulatory microservice via HTTP REST API.
Demonstrates:
  - Network-based data integration over HTTP
  - Bearer token authentication
  - Handling of REST envelope structures: { "meta": {...}, "data": [...] }
  - Graceful failover to in-process datastore if microservice daemon is offline
"""

from __future__ import annotations
import os, json, time, urllib.request, urllib.error
from urllib.parse import quote_plus
from typing import Any, Dict, List, Optional
from .base_wrapper import BaseWrapper, SourceMetadata

DEFAULT_BASE_URL = "http://127.0.0.1:8001/api/v1"
AUTH_TOKEN = "CDSCO-MCA-2026-KEY"


class RestApiMicroserviceWrapper(BaseWrapper):
    """Wrapper querying the external Ministry RESTful API over HTTP."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout_sec: float = 1.5):
        super().__init__("db4_ministry")
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def _http_get(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Makes an HTTP GET request with Authorization header."""
        query_str = ""
        if params:
            query_str = "?" + "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items() if v is not None)
        url = f"{self.base_url}/{endpoint.lstrip('/')}{query_str}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Accept": "application/json",
            "User-Agent": "Asali-Federated-Mediator/2.0"
        })
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                if resp.status == 200:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw)
        except Exception:
            return None
        return None

    def get_metadata(self) -> SourceMetadata:
        online = self.health_check()
        return SourceMetadata(
            source_id="db4_ministry",
            source_name="Ministry of Consumer Affairs & CDSCO (INGRAM)",
            source_type="HTTP RESTful Web Service",
            paradigm="Web Microservice",
            protocol="HTTP 1.1 / JSON REST API",
            native_key="complaint_item_ref",
            status="ONLINE (HTTP :8001)" if online else "IN_PROCESS_FALLBACK",
            latency_ms=4.8 if online else 0.5
        )

    def health_check(self) -> bool:
        res = self._http_get("health")
        return bool(res and res.get("status") == "online")

    def query(self, canonical_key: str, native_filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        start = time.perf_counter()
        used_http = False

        # Attempt live HTTP query to the microservice
        complaints_res = self._http_get("complaints", {"item_ref": canonical_key})
        blacklist_res = self._http_get("blacklist", {"item_ref": canonical_key})
        lab_res = self._http_get("lab_reports", {"item_ref": canonical_key})
        alerts_res = self._http_get("alerts", {"item_ref": canonical_key})

        if complaints_res is not None:
            used_http = True
            complaints = complaints_res.get("data", [])
            blacklist = blacklist_res.get("data", []) if blacklist_res else []
            lab_reports = lab_res.get("data", []) if lab_res else []
            alerts = alerts_res.get("data", []) if alerts_res else []
        else:
            # In-process fallback datastore to guarantee resilience
            from api.ministry_service import GLOBAL_DATASTORE
            complaints = GLOBAL_DATASTORE.get_complaints(canonical_key)
            blacklist = GLOBAL_DATASTORE.get_blacklist(canonical_key)
            lab_reports = GLOBAL_DATASTORE.get_lab_reports(canonical_key)
            alerts = GLOBAL_DATASTORE.get_alerts(canonical_key)

        latency = (time.perf_counter() - start) * 1000
        found = bool(complaints or blacklist or lab_reports or alerts)

        endpoint_url = f"{self.base_url}/complaints?item_ref={canonical_key}"
        return {
            "source_id": "db4_ministry",
            "native_query": f"HTTP GET {endpoint_url}" if used_http else f"IN_PROCESS_REST_PROXY GET /complaints?item_ref={canonical_key}",
            "paradigm": "HTTP REST Microservice (Live)" if used_http else "RESTful Service (Embedded Proxy)",
            "protocol": "HTTP/1.1 REST" if used_http else "Internal REST Proxy",
            "found": found,
            "complaints": complaints,
            "blacklist_entry": blacklist[0] if blacklist else None,
            "lab_reports": lab_reports,
            "alerts": alerts,
            "count": len(complaints),
            "execution_time_ms": round(latency, 2),
            "used_live_http": used_http
        }
