"""Shared FastAPI dependencies.

`get_db` returns the singleton SQLite connection initialised at startup.
`get_actor` extracts the officer ID from the X-Officer-ID header
(set by the front-end's officer picker).
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import Header, HTTPException

from backend.database.connection import init_db


_conn: Optional[sqlite3.Connection] = None


def get_db() -> sqlite3.Connection:
    """Return the shared connection. Initialised on first call."""
    global _conn
    if _conn is None:
        _conn = init_db()
    return _conn


def get_actor(x_officer_id: Optional[str] = Header(None)) -> str:
    """Resolve the calling officer's ID from the request header.

    For the demo, we accept any seeded officer ID; in production this
    would validate against an SSO session. Falls back to officer-sharma
    if no header is provided so the API stays usable from curl.
    """
    return x_officer_id or "officer-sharma"


def require_officer(x_officer_id: Optional[str] = Header(None)) -> str:
    """Same as get_actor but raises 400 if missing."""
    if not x_officer_id:
        raise HTTPException(status_code=400, detail="X-Officer-ID header is required.")
    return x_officer_id


def get_officer_record(conn: sqlite3.Connection, officer_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT id, name, department, role FROM officers WHERE id = ?",
        (officer_id,),
    ).fetchone()
    return dict(row) if row else None
