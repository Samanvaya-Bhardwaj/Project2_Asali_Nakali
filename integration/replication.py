#!/usr/bin/env python3
"""
replication.py
--------------
Keeps the copies of the databases on the two PCs the same.

Both nodes hold all four databases, and each page reads from one node only:
the Uncertainty page asks PC1, the Verify page asks PC2, the Explorer asks the
node that owns the database. So a write accepted by one node is sent on to the
other node, which applies the same request to its own copy. A product
registered on PC2 through the Explorer is then also in PC1's registry, where
the Uncertainty page looks for it, and a cleansing run made on PC1 is also
seen by the Verify page on PC2.

How a node finds the other one:
  1. the dashboard sends the other node's address with every write
     (header X-Asali-Peer), and the node remembers it;
  2. otherwise PC1_HOST / PC2_HOST from integration/distributed_config.py.

When both nodes run from the same folder (one laptop) they share the files, so
nothing needs copying: every node has a storage id, and a node that receives a
copy from its own storage answers "same_storage" without applying it.

Copies are sent by one background thread per node, in the order the writes
were made. The node waits a few seconds for the copy so the page can say
"also saved on the other PC"; a slow copy (a full cleansing run) finishes in
the background.
"""

from __future__ import annotations
import hashlib
import json
import os
import queue
import socket
import threading
import urllib.request
from typing import Any, Dict, Mapping, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STORAGE_ID = hashlib.sha1(
    (socket.gethostname() + "|" + os.path.realpath(os.path.join(BASE_DIR, "databases"))).lower().encode("utf-8")
).hexdigest()[:12]

HDR_PEER = "X-Asali-Peer"
HDR_REPLICA = "X-Asali-Replica"
CORS_HEADERS = "Content-Type, Authorization, " + HDR_PEER + ", " + HDR_REPLICA

EXPLORER_PATH = "/api/v1/explorer/operation"
WRITE_OPS = {"INSERT", "UPDATE", "DELETE", "FEDERATED_INSERT", "FEDERATED_REGISTER",
             "FEDERATED_DELETE", "FEDERATED_QUARANTINE"}
CLEANSING_ROUTES = {"apply", "decide", "undo"}

WAIT_SEC = 4.0
TIMEOUT_SEC = 120.0

# Keyed by role: with --mode all both nodes run in one process and share this module.
_peer: Dict[str, str] = {}
_jobs: "queue.Queue[Dict[str, Any]]" = queue.Queue()
_worker_lock = threading.Lock()
_worker: Dict[str, Optional[threading.Thread]] = {"thread": None}


def is_copy(headers: Mapping[str, str]) -> bool:
    """True for a write another node forwarded here."""
    return bool(headers.get(HDR_REPLICA))


def same_storage(headers: Mapping[str, str]) -> bool:
    """True when the forwarded write came from a node using these very files."""
    return headers.get(HDR_REPLICA) == STORAGE_ID


def remember_peer(headers: Mapping[str, str], role: str) -> None:
    url = (headers.get(HDR_PEER) or "").strip().rstrip("/")
    if url.startswith("http://") or url.startswith("https://"):
        _peer[role] = url


def peer_url(role: str) -> str:
    if _peer.get(role):
        return _peer[role]
    from integration.distributed_config import get_topology_config
    cfg = get_topology_config()
    return cfg["pc2_node"]["url"] if role == "pc1" else cfg["pc1_node"]["url"]


def is_write(path: str, body: Dict[str, Any]) -> bool:
    if path == EXPLORER_PATH:
        return str(body.get("operation", "")).strip().upper() in WRITE_OPS
    if path.startswith("/api/v1/uncertainty/"):
        return path.rstrip("/").rsplit("/", 1)[-1] in CLEANSING_ROUTES
    return False


def _replayable(path: str, body: Dict[str, Any], res: Dict[str, Any]) -> Dict[str, Any]:
    """The request as the other node must apply it to end up with the same rows."""
    out = dict(body)
    if path == EXPLORER_PATH:
        op = str(body.get("operation", "")).strip().upper()
        data = dict(body.get("data") or {})
        if op in ("FEDERATED_INSERT", "FEDERATED_REGISTER") and res.get("item_code"):
            data["item_code"] = res["item_code"]
        if op in ("FEDERATED_DELETE", "FEDERATED_QUARANTINE") and res.get("blacklist_id"):
            data["blacklist_id"] = res["blacklist_id"]
        out["data"] = data
    elif res.get("run_id"):
        # The same run id on both copies, so "Undo this run" works on both.
        out["run_id"] = res["run_id"]
    return out


def after_write(headers: Mapping[str, str], path: str, body: Dict[str, Any],
                res: Dict[str, Any], role: str) -> Dict[str, Any]:
    """
    Called by a node after it applied a request itself. A successful write that
    came from the dashboard (not from the other node) is sent on, and the
    response says what happened to the copy under "replication".
    """
    remember_peer(headers, role)
    if is_copy(headers) or not isinstance(res, dict) or res.get("success") is False:
        return res
    if not is_write(path, body):
        return res
    res["replication"] = send(path, _replayable(path, body, res), role)
    return res


def send(path: str, body: Dict[str, Any], role: str, wait: float = WAIT_SEC) -> Dict[str, Any]:
    url = peer_url(role)
    job = {"url": url, "path": path, "body": body, "done": threading.Event(), "result": None}
    _ensure_worker()
    _jobs.put(job)
    if job["done"].wait(wait):
        return job["result"]
    return {"peer": url, "status": "pending",
            "message": "Still copying to the other PC; it finishes in the background."}


def _ensure_worker() -> None:
    with _worker_lock:
        t = _worker["thread"]
        if t is None or not t.is_alive():
            t = threading.Thread(target=_run, name="asali-replication", daemon=True)
            _worker["thread"] = t
            t.start()


def _run() -> None:
    while True:
        job = _jobs.get()
        try:
            job["result"] = _post(job["url"], job["path"], job["body"])
        except Exception as e:  # never let one bad copy stop the queue
            job["result"] = {"peer": job["url"], "status": "failed", "message": f"{type(e).__name__}: {e}"}
        finally:
            job["done"].set()


def _post(url: str, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    req = urllib.request.Request(url + path, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", HDR_REPLICA: STORAGE_ID})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as r:
            payload = json.loads(r.read().decode("utf-8") or "{}")
    except Exception as e:
        return {"peer": url, "status": "unreachable",
                "message": f"The other PC did not answer ({e}). Its copy was not updated."}
    if payload.get("replica") == "same_storage":
        return {"peer": url, "status": "same_storage",
                "message": "Both nodes use the same database files, so there was nothing to copy."}
    if payload.get("success") is False:
        return {"peer": url, "status": "failed",
                "message": "The other PC refused the copy: " + str(payload.get("error", "unknown error"))}
    return {"peer": url, "status": "copied", "message": "Also saved on the other PC."}


def same_storage_reply() -> Dict[str, Any]:
    return {"success": True, "replica": "same_storage", "storage_id": STORAGE_ID}
