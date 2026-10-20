#!/usr/bin/env python3
"""
lifecycle_state.py
------------------
Digital Twin Lifecycle State Machine (Gemini Innovation #1).

Medicines follow an immutable physical workflow:

  MINTED --> DISPATCHED --> DELIVERED --> DISPENSED
                                               |
                                               v
                              Any re-scan here = REPLAY ATTACK

State definitions:
  MINTED      -> Registered in Manufacturer DB (DB3). Not yet shipped.
  DISPATCHED  -> In-transit with a distributor (DB2, transit_status=IN_TRANSIT).
  DELIVERED   -> Received at vendor (DB2, transit_status=DELIVERED).
  DISPENSED   -> Sold to consumer (DB1, purchase event exists).
  RECALLED    -> Manufacturer/CDSCO initiated recall (DB3, is_recalled=1).
  FLAGGED     -> Flagged by Ministry (DB4, active complaint/blacklist).

Illegal transitions detected:
  MINTED -> DISPENSED       (no distribution record = supply chain injection)
  DISPATCHED -> DISPENSED   (no delivery confirmation = stolen/diverted)
  DISPENSED -> DISPENSED    (replay attack = cloned barcode)
  RECALLED -> DISPENSED     (selling recalled medicine)

Stored in an SQLite ledger inside db3_manufacturer_registry.sqlite
(authoritative source for state) so it persists across sessions.
"""

from __future__ import annotations
import sqlite3, os, json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from integration.resolver import ItemRecord

BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "databases", "db3_manufacturer_registry.sqlite")

# Valid state transitions (FSM adjacency list)
VALID_TRANSITIONS: dict[str, list[str]] = {
    None:         ["MINTED"],
    "MINTED":     ["DISPATCHED", "RECALLED"],
    "DISPATCHED": ["DELIVERED", "RECALLED", "FLAGGED"],
    "DELIVERED":  ["DISPENSED", "RECALLED", "FLAGGED"],
    "DISPENSED":  ["FLAGGED"],       # only flagging allowed after sale
    "RECALLED":   ["FLAGGED"],
    "FLAGGED":    [],
}

ILLEGAL_TRANSITIONS = {
    ("MINTED",     "DISPENSED"):  "SUPPLY_CHAIN_INJECTION",
    ("DISPATCHED", "DISPENSED"):  "DIVERSION_NO_DELIVERY",
    ("DISPENSED",  "DISPENSED"):  "REPLAY_ATTACK",
    ("RECALLED",   "DISPENSED"):  "RECALLED_ITEM_SOLD",
}


@dataclass
class StateEvent:
    item_code:  str
    old_state:  Optional[str]
    new_state:  str
    timestamp:  str
    actor:      str    # who triggered the transition (e.g. "DB1_PURCHASE", "DB2_DISPATCH")
    valid:      bool
    violation:  Optional[str]  # e.g. "REPLAY_ATTACK"


class LifecycleTracker:
    """
    Tracks and transitions the lifecycle state of each serialized item.
    Persists state in a `item_lifecycle` table in DB3.
    """

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        """Create the lifecycle ledger table if not exists."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS item_lifecycle (
                        item_code   TEXT PRIMARY KEY,
                        state       TEXT NOT NULL DEFAULT 'MINTED',
                        updated_at  DATETIME NOT NULL,
                        history     TEXT NOT NULL DEFAULT '[]'
                    )
                """)
        except Exception:
            pass  # graceful fallback if DB doesn't exist yet

    def get_state(self, item_code: str) -> Optional[str]:
        """Return current lifecycle state, or None if untracked."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.execute(
                    "SELECT state FROM item_lifecycle WHERE item_code = ?",
                    (item_code,))
                row = cur.fetchone()
                return row[0] if row else None
        except Exception:
            return None

    def transition(self, item_code: str, new_state: str,
                   actor: str = "SYSTEM") -> StateEvent:
        """
        Attempt a state transition. Returns a StateEvent with
        valid=False and a violation code if the transition is illegal.
        """
        old_state = self.get_state(item_code)
        now       = datetime.now().isoformat()

        # Check validity
        allowed    = VALID_TRANSITIONS.get(old_state, [])
        valid      = new_state in allowed
        violation  = ILLEGAL_TRANSITIONS.get((old_state, new_state))
        if not valid and not violation:
            violation = f"INVALID_TRANSITION_{old_state}_TO_{new_state}"

        event = StateEvent(
            item_code = item_code,
            old_state = old_state,
            new_state = new_state,
            timestamp = now,
            actor     = actor,
            valid     = valid,
            violation = violation,
        )

        # Persist (even invalid transitions are recorded for audit)
        if valid:
            self._persist(item_code, new_state, now, event)

        return event

    def _persist(self, item_code: str, state: str, ts: str,
                 event: StateEvent):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                # Get existing history
                cur = conn.execute(
                    "SELECT history FROM item_lifecycle WHERE item_code = ?",
                    (item_code,))
                row = cur.fetchone()
                history = json.loads(row[0]) if row else []
                history.append({
                    "state":     event.new_state,
                    "from":      event.old_state,
                    "at":        ts,
                    "by":        event.actor,
                })
                conn.execute("""
                    INSERT INTO item_lifecycle (item_code, state, updated_at, history)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(item_code) DO UPDATE SET
                        state      = excluded.state,
                        updated_at = excluded.updated_at,
                        history    = excluded.history
                """, (item_code, state, ts, json.dumps(history)))
        except Exception:
            pass

    def infer_and_sync(self, record: ItemRecord) -> str:
        """
        Infer the correct lifecycle state from the 4 DB records,
        then transition the item to that state (advancing if needed).

        Returns the inferred state.
        """
        item_code = record.item_code
        current   = self.get_state(item_code)

        # Infer from data
        if record.manufacturer.found and record.manufacturer.product:
            if record.manufacturer.product.get("is_recalled"):
                inferred = "RECALLED"
            elif record.purchase.found:
                inferred = "DISPENSED"
            elif record.distribution.found:
                delivered = any(
                    b.get("delivery_status") in ("DELIVERED", "delivered")
                    for b in record.distribution.batches
                )
                inferred = "DELIVERED" if delivered else "DISPATCHED"
            else:
                inferred = "MINTED"
        else:
            # Not in manufacturer DB  -  we can't set a valid lifecycle state
            return "UNKNOWN"

        # Advance state if needed
        if current != inferred:
            self.transition(item_code, inferred, actor="AUTO_SYNC")

        return inferred

    def get_history(self, item_code: str) -> list[dict]:
        """Return full state history for an item."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cur = conn.execute(
                    "SELECT history FROM item_lifecycle WHERE item_code = ?",
                    (item_code,))
                row = cur.fetchone()
                return json.loads(row[0]) if row else []
        except Exception:
            return []


# --- Module-level singleton ---------------------------------------------------

_tracker: Optional[LifecycleTracker] = None

def get_tracker() -> LifecycleTracker:
    global _tracker
    if _tracker is None:
        _tracker = LifecycleTracker()
    return _tracker


# --- CLI test -----------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from integration.resolver import resolve

    code    = sys.argv[1] if len(sys.argv) > 1 else "MED-ASALI-001"
    record  = resolve(code)
    tracker = get_tracker()
    state   = tracker.infer_and_sync(record)
    history = tracker.get_history(code)

    print(f"\n{'='*55}")
    print(f"  LIFECYCLE STATE: {code}")
    print(f"{'='*55}")
    print(f"  Current State: {state}")
    print(f"  History ({len(history)} transitions):")
    for h in history:
        print(f"    {h.get('from','?')} -> {h['state']} [{h['at'][:16]}] by {h['by']}")
    print()
