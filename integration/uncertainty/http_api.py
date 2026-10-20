"""
http_api.py
-----------
The /api/v1/uncertainty/* endpoints. Both nodes delegate here, so whichever
machine the dashboard reaches answers the same way.

  GET  match      noisy code + optional context -> ranked candidates, decision
  GET  compare    every string metric's own top candidates for one code
  GET  reverse    every noisy record that refers to a registered product
  GET  catalog    products and vendors, for the dashboard's pickers
  GET  samples    records that carry a photographed label
  GET  scan       data-quality scan: issues, decisions, accuracy vs ground truth
  POST apply      apply automatic fixes, or selected issues
  POST decide     a reviewer accepts or rejects one issue
  POST undo       revert a cleansing run
  GET  lineage    cleansing runs and the individual changes they made
  GET  benchmark  the saved algorithm comparison
  POST train      refit the model and rerun the benchmark
"""

from __future__ import annotations
import json
import os
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

from . import paths

PREFIX = "/api/v1/uncertainty/"

# Training takes about a minute and the nodes serve one request at a time, so it
# runs on its own thread and the dashboard polls train_status.
_TRAINING = {"running": False, "started_at": None, "finished_at": None, "error": None}


def _train_in_background(quick: bool, node: str) -> None:
    _TRAINING.update(running=True, started_at=datetime.now().isoformat(timespec="seconds"),
                     finished_at=None, error=None)
    try:
        from .train import run
        res = run(quick=quick)
        _log("DQ_TRAIN", f"Model refitted and benchmarked in {res['elapsed_s']} s", node=node)
    except BaseException as e:  # SystemExit included: report it, never kill the node
        _TRAINING["error"] = f"{type(e).__name__}: {e}"
    finally:
        _TRAINING.update(running=False, finished_at=datetime.now().isoformat(timespec="seconds"))


def _p(params: Dict, name: str, default: str = "") -> str:
    v = params.get(name, [default])
    return (v[0] if isinstance(v, list) else v) or default


def _log(action: str, summary: str, rows: int = 0, ms: float = 0.0, node: str = "", ok: bool = True):
    try:
        from integration import activity_log
        activity_log.record(db_id="all", action=action, target="data_quality", summary=summary,
                            rows=rows, ms=ms, ok=ok, node=node)
    except Exception:
        pass


def handle(method: str, path: str, params: Dict, body: Optional[Dict] = None,
           node: str = "") -> Optional[Tuple[int, Dict]]:
    """Returns (status, payload), or None when the path is not one of ours."""
    if not path.startswith(PREFIX):
        return None
    route = path[len(PREFIX):].strip("/")
    body = body or {}
    try:
        if method == "GET" and route == "match":
            return 200, _match(params)
        if method == "GET" and route == "compare":
            from .linkage import compare_algorithms
            return 200, {"code": _p(params, "code"), "algorithms": compare_algorithms(_p(params, "code"))}
        if method == "GET" and route == "reverse":
            from .cleanser import live_matcher
            return 200, live_matcher().reverse(_p(params, "uid"))
        if method == "GET" and route == "catalog":
            return 200, _catalog()
        if method == "GET" and route == "samples":
            return 200, _samples()
        if method == "GET" and route == "scan":
            from .cleanser import scan
            t0 = time.perf_counter()
            res = scan(include_issues=_p(params, "issues", "1") != "0")
            s = res["summary"]
            _log("DQ_SCAN", f"{s['auto']} automatic, {s['review']} to review, {s['retain']} quarantined",
                 rows=s["total_open"], ms=(time.perf_counter() - t0) * 1000, node=node)
            return 200, res
        if method == "POST" and route == "apply":
            from .cleanser import apply
            res = apply(mode=body.get("mode", "auto"), issue_ids=body.get("issue_ids"),
                        overrides=body.get("overrides"), actor=body.get("actor", "dashboard"))
            _log("DQ_APPLY", f"Run {res['run_id']}: {res['issues_applied']} issue(s), "
                             f"{res['changes_applied']} change(s)", rows=res["changes_applied"],
                 ms=res["elapsed_ms"], node=node)
            return 200, res
        if method == "POST" and route == "decide":
            from .cleanser import decide
            res = decide(body.get("issue_id", ""), body.get("decision", ""), body.get("uid"), body.get("note", ""))
            _log("DQ_REVIEW", f"{body.get('decision', '?')} {body.get('issue_id', '?')}", node=node,
                 ok=res.get("success", False))
            return 200, res
        if method == "POST" and route == "undo":
            from .cleanser import undo
            res = undo(body.get("run_id", ""))
            _log("DQ_UNDO", f"Reverted {res.get('actions_reverted', 0)} change(s) of {body.get('run_id')}",
                 rows=res.get("actions_reverted", 0), node=node, ok=res.get("success", False))
            return 200, res
        if method == "GET" and route == "lineage":
            from .cleanser import lineage
            return 200, lineage(int(_p(params, "limit", "80")))
        if method == "GET" and route == "benchmark":
            return 200, _benchmark()
        if method == "POST" and route == "train":
            if _TRAINING["running"]:
                return 200, dict(_TRAINING, started=False)
            threading.Thread(target=_train_in_background, args=(bool(body.get("quick")), node),
                             daemon=True).start()
            return 202, dict(_TRAINING, started=True)
        if method == "GET" and route == "train_status":
            return 200, dict(_TRAINING)
        return 404, {"error": f"Unknown uncertainty endpoint: {method} {route}"}
    except Exception as e:  # the dashboard shows this message instead of a dead request
        return 500, {"success": False, "error": f"{type(e).__name__}: {e}"}


def _match(params: Dict) -> Dict:
    from .cleanser import live_matcher
    from .linkage import compare_algorithms
    m = live_matcher()
    source = _p(params, "source", "db1")
    rec = {"source": source, "key": "query", "code": _p(params, "code"),
           "channel": _p(params, "channel", "manual")}
    if source == "db1":
        rec.update(vendor_id=_p(params, "vendor_id") or None, price_paid=_p(params, "price") or None,
                   quantity=_p(params, "qty") or None, date=_p(params, "date") or None,
                   label_text=_p(params, "label") or None)
    elif source == "db2":
        rec.update(channel="erp", manufacturer_ref=_p(params, "manufacturer_ref") or None,
                   distributor_id=_p(params, "distributor_id") or None,
                   vendor_id=_p(params, "vendor_id") or None, date=_p(params, "date") or None)
    elif source == "db4":
        rec.update(channel="citizen", description=_p(params, "description") or None,
                   purchase_location=_p(params, "location") or None, date=_p(params, "date") or None)
    t0 = time.perf_counter()
    res = m.match(rec, limit=int(_p(params, "limit", "8")))
    out = res.to_dict()
    out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    out["catalogue_size"] = len(m.ctx.products)
    out["thresholds"] = m.model.thresholds
    out["model"] = m.model.meta
    for c in out["candidates"]:
        c["shipped_to"] = sorted(m.ctx.shipped_to(c["uid"]))
    if _p(params, "compare") == "1" and res.code:
        out["algorithms"] = compare_algorithms(res.code, m.ctx, m.model)
    return out


def _catalog() -> Dict:
    from .cleanser import live_matcher
    ctx = live_matcher().ctx
    products = [{"uid": u, "name": p.get("product_name"), "strength": p.get("strength"),
                 "manufacturer": p.get("manufacturer_name"), "mrp": p.get("msrp_kes"),
                 "batch": p.get("batch_number")} for u, p in sorted(ctx.products.items())]
    vendors = [{"id": v["vendor_id"], "name": v.get("vendor_name"), "city": v.get("city"),
                "active": v.get("active")} for v in sorted(ctx.vendors.values(), key=lambda v: v["vendor_id"])]
    return {"products": products, "vendors": vendors}


def _samples() -> Dict:
    from .context import get_context
    ctx = get_context()
    rows = []
    for r in ctx.db1_events:
        if r.get("label_text"):
            img = r.get("label_image")
            exists = bool(img) and os.path.exists(os.path.join(paths.BASE_DIR, "dashboard", img))
            rows.append({"event_id": r["event_id"], "scan_code": r.get("scan_code"),
                         "vendor_id": r.get("vendor_id"), "price_paid": r.get("price_paid"),
                         "quantity": r.get("quantity_bought"), "date": r.get("scan_timestamp"),
                         "label_text": r.get("label_text"), "image": img if exists else None,
                         "scan_method": r.get("scan_method")})
    rows.sort(key=lambda r: (r["image"] is None, r["event_id"]))
    return {"samples": rows[:120], "total": len(rows)}


def _benchmark() -> Dict:
    try:
        with open(paths.benchmark_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"missing": True,
                "message": "No benchmark yet. Run: python -m integration.uncertainty.train"}
