"""Tender CRUD + state transitions.

A tender is the top-level workspace. All other entities (bidders,
documents, criteria, evaluations) hang off a tender_id. Soft-delete
via deleted_at; we never hard-delete an audited tender.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.core import audit_chain, state_machine


def create_tender(
    conn,
    *,
    tender_number: str,
    title: str,
    department: str,
    category: str,
    estimated_cost: Optional[int] = None,
    emd_amount: Optional[int] = None,
    bid_open_date: Optional[str] = None,
    bid_close_date: Optional[str] = None,
    metadata: Optional[dict] = None,
    created_by: str,
) -> dict:
    """Create a new tender in DRAFT state."""
    tender_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT INTO tenders
           (id, tender_number, title, department, category,
            estimated_cost, emd_amount, bid_open_date, bid_close_date,
            state, metadata, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?)""",
        (
            tender_id, tender_number, title, department, category,
            estimated_cost, emd_amount, bid_open_date, bid_close_date,
            json.dumps(metadata) if metadata else None,
            created_by, now, now,
        ),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="tender_created",
        event_data={
            "tender_number": tender_number,
            "title": title,
            "department": department,
            "category": category,
        },
        actor=created_by,
    )
    return get_tender(conn, tender_id)


def get_tender(conn, tender_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM tenders WHERE id = ? AND deleted_at IS NULL",
        (tender_id,),
    ).fetchone()
    if not row:
        return None
    out = _row_to_dict(row)
    out["progress_pct"] = state_machine.progress_pct(out["state"])
    out["step"] = state_machine.step_for_state(out["state"])
    return out


def list_tenders(
    conn,
    *,
    state: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    sql = "SELECT * FROM tenders WHERE deleted_at IS NULL"
    params: list = []
    if state:
        sql += " AND state = ?"
        params.append(state)
    if department:
        sql += " AND department = ?"
        params.append(department)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    out = []
    for r in conn.execute(sql, params).fetchall():
        d = _row_to_dict(r)
        d["progress_pct"] = state_machine.progress_pct(d["state"])
        d["step"] = state_machine.step_for_state(d["state"])
        out.append(d)
    return out


def transition_state(
    conn,
    *,
    tender_id: str,
    target_state: str,
    actor: str,
) -> dict:
    """Move a tender to the next state. Raises StateError on illegal moves."""
    current = conn.execute(
        "SELECT state FROM tenders WHERE id = ? AND deleted_at IS NULL",
        (tender_id,),
    ).fetchone()
    if not current:
        raise ValueError(f"Tender not found: {tender_id}")

    state_machine.transition(current["state"], target_state)

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE tenders SET state = ?, updated_at = ? WHERE id = ?",
        (target_state, now, tender_id),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="tender_state_transition",
        event_data={"from": current["state"], "to": target_state},
        actor=actor,
    )
    return get_tender(conn, tender_id)


def update_metadata(
    conn,
    *,
    tender_id: str,
    metadata: dict,
    actor: str,
) -> dict:
    """Patch the tender's metadata JSON."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE tenders SET metadata = ?, updated_at = ? "
        "WHERE id = ? AND deleted_at IS NULL",
        (json.dumps(metadata), now, tender_id),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="tender_metadata_updated",
        event_data={"metadata": metadata},
        actor=actor,
    )
    return get_tender(conn, tender_id)


def soft_delete(conn, *, tender_id: str, actor: str) -> None:
    """Soft-delete a tender (preserves audit trail)."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE tenders SET deleted_at = ? WHERE id = ?",
        (now, tender_id),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="tender_deleted",
        event_data={"timestamp": now},
        actor=actor,
    )


def _row_to_dict(row) -> dict:
    d = dict(row)
    if d.get("metadata"):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d
