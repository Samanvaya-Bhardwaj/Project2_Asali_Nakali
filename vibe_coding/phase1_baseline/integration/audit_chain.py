#!/usr/bin/env python3
"""
audit_chain.py
--------------
Tamper-evident Hash Chain Audit Trail.

Every verification query is logged as an immutable entry linked to the
previous entry via SHA-256 hash  -  a simplified blockchain-style audit trail.

This ensures:
  1. Queries cannot be retroactively deleted or modified
  2. Any tampering is immediately detectable
  3. Full provenance of every verification is preserved
"""

from __future__ import annotations
import sqlite3, hashlib, json, os
from datetime import datetime

BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DB = os.path.join(BASE, "databases", "audit_chain.sqlite")

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS audit_log (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id     TEXT UNIQUE NOT NULL,             -- AUDIT-{timestamp}-{seq}
    item_code    TEXT NOT NULL,
    queried_at   TEXT NOT NULL,
    querier_id   TEXT,                             -- who/what triggered the query
    verdict      TEXT,                             -- ASALI / SUSPICIOUS / NAKALI
    trust_score  INTEGER,
    db_sources   TEXT,                             -- JSON array of DBs queried
    entry_hash   TEXT UNIQUE NOT NULL,             -- SHA-256 of this entry's content
    prev_hash    TEXT NOT NULL,                    -- SHA-256 of previous entry (chain link)
    chain_valid  INTEGER NOT NULL DEFAULT 1        -- 1 = chain intact at this point
);

CREATE TABLE IF NOT EXISTS chain_meta (
    id         INTEGER PRIMARY KEY CHECK(id = 1),
    genesis_hash TEXT NOT NULL,                    -- hash of first entry
    last_hash    TEXT NOT NULL,                    -- hash of most recent entry
    total_entries INTEGER NOT NULL DEFAULT 0,
    chain_intact  INTEGER NOT NULL DEFAULT 1
);
"""

GENESIS_HASH = "0" * 64   # The "genesis block"


class AuditChain:
    """Append-only, tamper-evident audit log with SHA-256 hash linking."""

    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(AUDIT_DB)
        conn.executescript(SCHEMA)
        # Initialize meta if empty
        meta = conn.execute("SELECT * FROM chain_meta").fetchone()
        if not meta:
            conn.execute(
                "INSERT INTO chain_meta (id, genesis_hash, last_hash, total_entries, chain_intact) "
                "VALUES (1, ?, ?, 0, 1)",
                (GENESIS_HASH, GENESIS_HASH))
            conn.commit()
        conn.close()

    def _get_last_hash(self) -> str:
        conn = sqlite3.connect(AUDIT_DB)
        row  = conn.execute("SELECT last_hash FROM chain_meta WHERE id=1").fetchone()
        conn.close()
        return row[0] if row else GENESIS_HASH

    def _compute_hash(self, content: dict) -> str:
        serialized = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def log(self,
            item_code:   str,
            verdict:     str,
            trust_score: int,
            db_sources:  list[str],
            querier_id:  str = "system") -> str:
        """
        Append a new entry to the audit chain.
        Returns the entry_id for reference.
        """
        now       = datetime.now().isoformat()
        prev_hash = self._get_last_hash()

        conn = sqlite3.connect(AUDIT_DB)
        seq_row = conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM audit_log").fetchone()
        seq     = seq_row[0]

        entry_id = f"AUDIT-{now[:10].replace('-','')}-{seq:06d}"

        # Compute content hash (before we store it)
        content = {
            "entry_id":    entry_id,
            "item_code":   item_code,
            "queried_at":  now,
            "querier_id":  querier_id,
            "verdict":     verdict,
            "trust_score": trust_score,
            "db_sources":  db_sources,
            "prev_hash":   prev_hash,
        }
        entry_hash = self._compute_hash(content)

        conn.execute(
            """INSERT INTO audit_log
               (entry_id, item_code, queried_at, querier_id, verdict, trust_score,
                db_sources, entry_hash, prev_hash, chain_valid)
               VALUES (?,?,?,?,?,?,?,?,?,1)""",
            (entry_id, item_code, now, querier_id, verdict, trust_score,
             json.dumps(db_sources), entry_hash, prev_hash))

        conn.execute(
            "UPDATE chain_meta SET last_hash=?, total_entries=total_entries+1 WHERE id=1",
            (entry_hash,))
        conn.commit()
        conn.close()
        return entry_id

    def verify_chain(self) -> dict:
        """
        Verify the integrity of the entire audit chain.
        Returns a report with any detected tampering.
        """
        conn    = sqlite3.connect(AUDIT_DB)
        entries = conn.execute(
            "SELECT * FROM audit_log ORDER BY seq ASC").fetchall()
        conn.close()

        if not entries:
            return {"intact": True, "entries_checked": 0, "broken_at": None}

        prev_hash = GENESIS_HASH
        issues    = []

        col = ["seq","entry_id","item_code","queried_at","querier_id","verdict",
               "trust_score","db_sources","entry_hash","prev_hash","chain_valid"]

        for row in entries:
            e = dict(zip(col, row))
            # Verify prev_hash link
            if e["prev_hash"] != prev_hash:
                issues.append(f"Chain broken at seq={e['seq']} (entry_id={e['entry_id']})")
            # Recompute entry hash
            content = {
                "entry_id":    e["entry_id"],
                "item_code":   e["item_code"],
                "queried_at":  e["queried_at"],
                "querier_id":  e["querier_id"],
                "verdict":     e["verdict"],
                "trust_score": e["trust_score"],
                "db_sources":  json.loads(e["db_sources"]),
                "prev_hash":   e["prev_hash"],
            }
            expected_hash = self._compute_hash(content)
            if expected_hash != e["entry_hash"]:
                issues.append(f"Entry tampered at seq={e['seq']}: hash mismatch")
            prev_hash = e["entry_hash"]

        return {
            "intact":          len(issues) == 0,
            "entries_checked": len(entries),
            "broken_at":       issues if issues else None,
            "last_hash":       prev_hash,
        }

    def get_item_history(self, item_code: str) -> list[dict]:
        """Return all audit entries for a given item_code."""
        conn = sqlite3.connect(AUDIT_DB)
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE item_code=? ORDER BY seq ASC",
            (item_code,)).fetchall()
        conn.close()
        cols = ["seq","entry_id","item_code","queried_at","querier_id","verdict",
                "trust_score","db_sources","entry_hash","prev_hash","chain_valid"]
        return [dict(zip(cols, r)) for r in rows]

    def stats(self) -> dict:
        conn  = sqlite3.connect(AUDIT_DB)
        meta  = conn.execute("SELECT * FROM chain_meta").fetchone()
        total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        nakali= conn.execute("SELECT COUNT(*) FROM audit_log WHERE verdict='NAKALI'").fetchone()[0]
        sus   = conn.execute("SELECT COUNT(*) FROM audit_log WHERE verdict='SUSPICIOUS'").fetchone()[0]
        asali = conn.execute("SELECT COUNT(*) FROM audit_log WHERE verdict='ASALI'").fetchone()[0]
        conn.close()
        return {
            "total_queries": total,
            "asali": asali, "suspicious": sus, "nakali": nakali,
            "chain_intact": bool(meta[4]) if meta else True,
            "last_hash": meta[2][:16]+"..." if meta else None,
        }


# --- Singleton ----------------------------------------------------------------
_chain = None

def get_chain() -> AuditChain:
    global _chain
    if _chain is None:
        _chain = AuditChain()
    return _chain


if __name__ == "__main__":
    chain = AuditChain()
    # Demo: log a few entries
    chain.log("MED-ASALI-001","ASALI",    95,["DB1","DB2","DB3","DB4"])
    chain.log("MED-NAKALI-001","NAKALI",  10,["DB1","DB2","DB3","DB4"])
    chain.log("MED-RECALL-001","SUSPICIOUS",60,["DB1","DB2","DB3","DB4"])

    result = chain.verify_chain()
    print(f"\n  Chain integrity: {'INTACT' if result['intact'] else 'COMPROMISED'}")
    print(f"  Entries checked: {result['entries_checked']}")
    print(f"  Stats: {chain.stats()}")
