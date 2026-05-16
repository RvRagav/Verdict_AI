"""Debarment registry — CVC + GeM blacklist.

In production this would refresh from the CVC and GeM portals on a
schedule. Here we provide a seedable local registry with a real lookup
that the bidder service consults during preliminary check.

The match logic is:
    1. Exact PAN match (highest confidence)
    2. Exact GSTIN match
    3. Fuzzy company-name match against a normalised key
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional


def add_entry(
    conn,
    *,
    pan_number: Optional[str] = None,
    gstin: Optional[str] = None,
    company_name: Optional[str] = None,
    source: str = "department",
    reason: str = "",
    debarred_until: Optional[str] = None,
    notice_url: Optional[str] = None,
) -> dict:
    """Register a debarred entity. Idempotent on (PAN, source) pair."""
    if pan_number:
        existing = conn.execute(
            "SELECT id FROM debarment_registry WHERE pan_number = ? AND source = ?",
            (pan_number.upper(), source),
        ).fetchone()
        if existing:
            return {"id": existing["id"], "duplicate": True}

    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO debarment_registry
           (id, pan_number, gstin, company_name, source, reason,
            debarred_until, notice_url, added_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entry_id,
         pan_number.upper() if pan_number else None,
         gstin.upper() if gstin else None,
         company_name, source, reason, debarred_until, notice_url, now),
    )
    return {"id": entry_id, "duplicate": False}


def list_entries(conn, *, source: Optional[str] = None) -> list[dict]:
    sql = "SELECT * FROM debarment_registry"
    params: list = []
    if source:
        sql += " WHERE source = ?"
        params.append(source)
    sql += " ORDER BY added_at DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def check_bidder(
    conn,
    *,
    pan_number: Optional[str] = None,
    gstin: Optional[str] = None,
    company_name: Optional[str] = None,
) -> dict:
    """Return {flagged: bool, matches: [...], confidence: 'high|medium|low'}."""
    matches: list[dict] = []
    today = datetime.now(timezone.utc).date().isoformat()

    if pan_number:
        rows = conn.execute(
            "SELECT * FROM debarment_registry WHERE pan_number = ?",
            (pan_number.upper(),),
        ).fetchall()
        for r in rows:
            if r["debarred_until"] and r["debarred_until"] < today:
                continue  # debarment expired
            matches.append({**dict(r), "match_type": "pan", "confidence": "high"})

    if gstin:
        rows = conn.execute(
            "SELECT * FROM debarment_registry WHERE gstin = ?",
            (gstin.upper(),),
        ).fetchall()
        for r in rows:
            if r["debarred_until"] and r["debarred_until"] < today:
                continue
            matches.append({**dict(r), "match_type": "gstin", "confidence": "high"})

    if company_name:
        norm = _normalise_name(company_name)
        rows = conn.execute(
            "SELECT * FROM debarment_registry WHERE company_name IS NOT NULL"
        ).fetchall()
        for r in rows:
            if not r["company_name"]:
                continue
            if _normalise_name(r["company_name"]) == norm:
                if r["debarred_until"] and r["debarred_until"] < today:
                    continue
                matches.append({**dict(r), "match_type": "name", "confidence": "medium"})

    flagged = bool(matches)
    confidence = "high" if any(m["confidence"] == "high" for m in matches) else (
        "medium" if matches else "none"
    )
    return {"flagged": flagged, "matches": matches, "confidence": confidence}


def _normalise_name(name: str) -> str:
    """Casefold + strip company suffixes + strip non-alnum."""
    n = name.lower()
    for suffix in ("private limited", "pvt ltd", "pvt. ltd.", "pvt ltd.",
                   "limited", "ltd.", "ltd", "industries", "company",
                   "co.", "corporation", "corp.", "corp", "llp", "llc"):
        n = n.replace(suffix, "")
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n.strip()
