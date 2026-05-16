"""Append-only hash-chained audit log.

Properties:
- Each entry's `entry_hash = SHA256(prev_hash | event_type | event_data | actor | timestamp)`
- The first entry's prev_hash is the genesis (64 zeros)
- DB triggers prevent UPDATE/DELETE
- Module-level mutex serialises (read-tail, compute, insert) so two concurrent
  threads can't fork the chain

Public API:
- append(): add a new event
- verify(): walk the chain, recompute hashes, return (ok, error_msg)
- get_trail(): paginated read with optional filters
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from backend.database.connection import audit_lock


GENESIS_HASH = "0" * 64


# ─── Event types (the union of all known events) ────────────────────────

EVENT_TYPES = frozenset({
    # Tender lifecycle
    "tender_created",
    "tender_metadata_updated",
    "tender_state_transition",
    "tender_deleted",
    # Documents
    "document_received",
    "document_processed",
    "document_failed",
    # Corrigenda
    "corrigendum_received",
    "corrigendum_summarised",
    "corrigendum_applied",
    "corrigendum_rejected",
    "criterion_amended",
    # Bidders
    "bidder_registered",
    "bidder_debarment_checked",
    "bidder_excluded",
    "bidder_emd_recorded",
    # Verification (external authorities)
    "verification_run",
    # Criteria
    "criteria_extracted",
    "criterion_edited",
    "criterion_version_created",
    "criteria_approved",
    # Checklist
    "checklist_extracted",
    "checklist_response_decided",
    "preliminary_finalised",
    # Evaluation
    "evaluation_computed",
    "evaluation_decided",
    "second_officer_decided",
    "concurrence_requested",
    "concurrence_decided",
    "anomaly_flagged",
    "anomaly_dismissed",
    "post_review_check_answered",
    "evidence_citation_recorded",
    "officer_comment_added",
    # Briefs / Vaults
    "brief_generated",
    "vault_generated",
    # Chat / replay
    "copilot_message",
    "decision_replay_captured",
    # Reports
    "report_generated",
    "report_signed",
    "reproduce_attempted",
    # ── Module 4: HITL co-authoring + Document Studio
    "tec_draft_generated",
    "tec_section_authored",
    "tec_section_revised",
    "tec_report_finalised",
    "studio_doc_created",
    "studio_doc_message",
    "studio_doc_finalised",
})


def _hash_entry(
    prev_hash: str,
    event_type: str,
    event_data: dict,
    actor: str,
    timestamp: str,
) -> str:
    """Compute the entry hash. Inputs are canonicalised for stability."""
    canonical = json.dumps(
        {
            "prev_hash": prev_hash,
            "event_type": event_type,
            "event_data": event_data,
            "actor": actor,
            "timestamp": timestamp,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append(
    conn: sqlite3.Connection,
    *,
    tender_id: str,
    event_type: str,
    event_data: dict,
    actor: str,
) -> dict:
    """Append an event, return the inserted row.

    Serialised by the module-level audit_lock so concurrent inserts cannot
    fork the chain.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown audit event_type: {event_type!r}")

    timestamp = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(event_data, sort_keys=True, default=str)
    if not payload:
        raise ValueError("event_data must be JSON-serialisable")

    with audit_lock:
        prev_row = conn.execute(
            "SELECT entry_hash FROM audit_events WHERE tender_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (tender_id,),
        ).fetchone()
        prev_hash = prev_row["entry_hash"] if prev_row else GENESIS_HASH

        entry_hash = _hash_entry(prev_hash, event_type, event_data, actor, timestamp)

        cur = conn.execute(
            """INSERT INTO audit_events
               (tender_id, event_type, event_data, actor, timestamp,
                prev_hash, entry_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tender_id, event_type, payload, actor, timestamp, prev_hash, entry_hash),
        )
        event_id = cur.lastrowid

    return {
        "id": event_id,
        "tender_id": tender_id,
        "event_type": event_type,
        "event_data": event_data,
        "actor": actor,
        "timestamp": timestamp,
        "prev_hash": prev_hash,
        "entry_hash": entry_hash,
    }


def verify(conn: sqlite3.Connection, tender_id: str) -> tuple[bool, Optional[str]]:
    """Walk the chain. Return (ok, error_message)."""
    rows = conn.execute(
        "SELECT id, event_type, event_data, actor, timestamp, prev_hash, entry_hash "
        "FROM audit_events WHERE tender_id = ? ORDER BY id ASC",
        (tender_id,),
    ).fetchall()

    if not rows:
        return True, None

    expected_prev = GENESIS_HASH
    for row in rows:
        if row["prev_hash"] != expected_prev:
            return False, (
                f"event {row['id']}: prev_hash mismatch "
                f"(expected {expected_prev[:16]}…, got {row['prev_hash'][:16]}…)"
            )
        try:
            data = json.loads(row["event_data"])
        except json.JSONDecodeError:
            return False, f"event {row['id']}: event_data is not JSON"

        recomputed = _hash_entry(
            row["prev_hash"], row["event_type"], data, row["actor"], row["timestamp"]
        )
        if recomputed != row["entry_hash"]:
            return False, (
                f"event {row['id']}: entry_hash mismatch "
                f"(stored {row['entry_hash'][:16]}…, recomputed {recomputed[:16]}…)"
            )
        expected_prev = row["entry_hash"]

    return True, None


def get_trail(
    conn: sqlite3.Connection,
    tender_id: str,
    *,
    event_type: Optional[str] = None,
    limit: int = 100,
    cursor: Optional[int] = None,
    order: str = "asc",
) -> tuple[list[dict], Optional[int]]:
    """Cursor-paginated read of audit events. Returns (items, next_cursor).

    order='asc' = oldest first (stable for pagination); 'desc' = newest first.
    """
    if order not in ("asc", "desc"):
        order = "asc"
    sql = "SELECT * FROM audit_events WHERE tender_id = ?"
    params: list = [tender_id]
    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)
    if cursor is not None:
        if order == "asc":
            sql += " AND id > ?"
        else:
            sql += " AND id < ?"
        params.append(cursor)
    sql += f" ORDER BY id {order.upper()} LIMIT ?"
    params.append(limit + 1)

    rows = conn.execute(sql, params).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = []
    for r in rows:
        try:
            data = json.loads(r["event_data"])
        except json.JSONDecodeError:
            data = r["event_data"]
        items.append({
            "id": r["id"],
            "tender_id": r["tender_id"],
            "event_type": r["event_type"],
            "event_data": data,
            "actor": r["actor"],
            "timestamp": r["timestamp"],
            "prev_hash": r["prev_hash"],
            "entry_hash": r["entry_hash"],
        })
    next_cursor = items[-1]["id"] if (has_more and items) else None
    return items, next_cursor
