"""
activity_log.py
---------------
An append-only record of every operation performed against the silos: schema
reads, row browsing, searches, and the create/update/delete work run from the
code bench.

This is deliberately separate from the audit chain. The audit chain is
evidentiary — it records verification verdicts and is hash-linked so tampering
shows up. This log is operational: it answers "what has been done to this
database, and by whom", including reads, which never enter the chain.

Each row carries the node that served the request, so the two nodes can keep
their own logs when they run on separate machines and the dashboard can merge
them without double-counting.
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DB = os.path.join(BASE_DIR, "databases", "activity_log.sqlite")

# Keeps the file from growing without bound during a long demo session.
MAX_ROWS = 5000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS activity_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    node        TEXT    NOT NULL,
    db_id       TEXT    NOT NULL,
    action      TEXT    NOT NULL,
    target      TEXT,
    summary     TEXT,
    rows        INTEGER DEFAULT 0,
    ms          REAL    DEFAULT 0,
    ok          INTEGER DEFAULT 1,
    client      TEXT
);
CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(id DESC);
CREATE INDEX IF NOT EXISTS idx_activity_db ON activity_log(db_id);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(LOG_DB), exist_ok=True)
    conn = sqlite3.connect(LOG_DB, timeout=5.0)
    conn.row_factory = sqlite3.Row
    # Both node processes write to this file when they share a machine.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def record(
    db_id: str,
    action: str,
    target: str = "",
    summary: str = "",
    rows: int = 0,
    ms: float = 0.0,
    ok: bool = True,
    node: str = "",
    client: str = "",
) -> None:
    """
    Appends one entry. Logging must never be the reason a request fails, so
    every error here is swallowed deliberately.
    """
    try:
        conn = _connect()
        with conn:
            conn.execute(
                """INSERT INTO activity_log
                   (ts, node, db_id, action, target, summary, rows, ms, ok, client)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    node or "UNKNOWN",
                    db_id or "-",
                    action.upper(),
                    target or "",
                    summary or "",
                    int(rows or 0),
                    round(float(ms or 0.0), 2),
                    1 if ok else 0,
                    client or "",
                ),
            )
            # Trim oldest rows past the cap.
            conn.execute(
                """DELETE FROM activity_log WHERE id <= (
                       SELECT MAX(id) - ? FROM activity_log
                   )""",
                (MAX_ROWS,),
            )
        conn.close()
    except Exception:
        pass


def recent(
    db_id: Optional[str] = None,
    limit: int = 50,
    node: Optional[str] = None,
) -> Dict[str, Any]:
    """Most recent entries first, optionally narrowed to one silo."""
    t0 = time.perf_counter()
    try:
        conn = _connect()
        sql = "SELECT * FROM activity_log"
        where, params = [], []

        if db_id and db_id not in ("all", "*"):
            where.append("db_id = ?")
            params.append(db_id)
        if node:
            where.append("node = ?")
            params.append(node)
        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(int(limit or 50), 500)))

        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

        # Counts follow the same node scope as the rows, or a node's totals would
        # include work done by its sibling when the two share a machine.
        scope, scope_params = "", []
        if node:
            scope, scope_params = " WHERE node = ?", [node]

        counts = {
            r["db_id"]: r["n"]
            for r in conn.execute(
                "SELECT db_id, COUNT(*) AS n FROM activity_log" + scope + " GROUP BY db_id",
                scope_params,
            ).fetchall()
        }
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM activity_log" + scope, scope_params
        ).fetchone()["n"]
        conn.close()

        return {
            "success": True,
            "entries": rows,
            "counts_by_db": counts,
            "total_entries": total,
            "execution_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "entries": [],
            "counts_by_db": {},
            "total_entries": 0,
            "execution_ms": round((time.perf_counter() - t0) * 1000, 2),
        }


def clear() -> Dict[str, Any]:
    """Empties the log. Used by the demo reset."""
    try:
        conn = _connect()
        with conn:
            conn.execute("DELETE FROM activity_log")
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
