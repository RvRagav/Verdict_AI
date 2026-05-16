"""SQLite connection management with proper concurrency settings.

The single global connection is OK for the demo (single-user). For production
multi-user, swap to a per-request connection or a connection pool.

We use a dedicated lock around audit-event inserts to serialise the hash
chain (`prev_hash → entry_hash`) under WAL + check_same_thread=False.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional

from backend.config import settings
from backend.database.schema import create_tables


# A single mutex serialising critical sections that read-then-write
# (e.g. computing the next audit-event hash). Without this, two
# concurrent inserts can fork the chain.
audit_lock = threading.Lock()


_initialised: bool = False


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a fresh connection. Caller closes it. Idempotent schema setup."""
    path = db_path or settings.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True) if Path(path).parent != Path(".") else None

    conn = sqlite3.connect(
        path,
        check_same_thread=False,
        isolation_level=None,  # autocommit; we manage transactions explicitly
        timeout=10.0,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create or open the database and ensure the schema is in place.

    Called once at FastAPI startup. Seeds the demo officers if missing.
    """
    global _initialised
    conn = get_connection(db_path)
    if not _initialised:
        create_tables(conn)
        seed_officers_if_empty(conn)
        _initialised = True
    return conn


def seed_officers_if_empty(conn: sqlite3.Connection) -> None:
    """Insert three demo officers if the table is empty.

    These power the lightweight officer picker in the UI. In production
    this would be replaced with SSO + IAM.
    """
    from datetime import datetime, timezone
    cur = conn.execute("SELECT COUNT(*) AS c FROM officers")
    if cur.fetchone()["c"] > 0:
        return
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        ("officer-sharma", "Inspector A. Sharma", "CRPF", "senior", now),
        ("officer-kumar",  "DSP P. Kumar",        "CRPF", "junior", now),
        ("officer-verma",  "DIG R. Verma",        "CRPF", "reviewer", now),
    ]
    conn.executemany(
        "INSERT INTO officers (id, name, department, role, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
