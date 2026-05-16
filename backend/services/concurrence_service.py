"""Concurrence requests — the real second-officer inbox.

When an evaluation routes `mandatory_review` and the criterion's GFR
override is permitted, a concurrence_request is created. The first
officer decides; the request goes into a target second officer's inbox;
they concur or reject. The audit chain records both ends.

Selection of target officer: today we rotate among officers with role
'reviewer' (excluding the requesting officer). In production this would
come from the procurement-entity's authority matrix.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.core import audit_chain


def open_request(
    conn,
    *,
    tender_id: str,
    evaluation_id: str,
    requested_by: str,
    request_reason: str,
    target_officer_id: Optional[str] = None,
) -> dict:
    """Open a concurrence request for an evaluation.

    Idempotent on (evaluation_id, state='open') — re-opening returns the
    existing request.
    """
    existing = conn.execute(
        "SELECT * FROM concurrence_requests "
        "WHERE evaluation_id = ? AND state = 'open' LIMIT 1",
        (evaluation_id,),
    ).fetchone()
    if existing:
        return dict(existing)

    if not target_officer_id:
        target_officer_id = _pick_target(conn, requested_by)

    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO concurrence_requests
           (id, tender_id, evaluation_id, requested_by, target_officer_id,
            request_reason, state, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'open', ?)""",
        (request_id, tender_id, evaluation_id, requested_by,
         target_officer_id, request_reason, now),
    )
    # Link back from evaluations row
    conn.execute(
        "UPDATE evaluations SET concurrence_request_id = ? WHERE id = ?",
        (request_id, evaluation_id),
    )

    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="concurrence_requested",
        event_data={
            "request_id": request_id,
            "evaluation_id": evaluation_id,
            "target_officer_id": target_officer_id,
            "reason": request_reason,
        },
        actor=requested_by,
    )
    return get_request(conn, request_id)


def list_inbox(conn, officer_id: str, *, state: str = "open") -> list[dict]:
    """List concurrence requests routed to this officer."""
    rows = conn.execute(
        """SELECT cr.*, t.tender_number, t.title, e.criterion_id, e.bidder_id, e.verdict
           FROM concurrence_requests cr
           JOIN tenders t ON t.id = cr.tender_id
           JOIN evaluations e ON e.id = cr.evaluation_id
           WHERE cr.target_officer_id = ? AND cr.state = ?
           ORDER BY cr.created_at DESC""",
        (officer_id, state),
    ).fetchall()
    return [dict(r) for r in rows]


def get_request(conn, request_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM concurrence_requests WHERE id = ?",
        (request_id,),
    ).fetchone()
    return dict(row) if row else None


def decide(
    conn,
    *,
    request_id: str,
    decision: str,                       # 'concurred' | 'rejected'
    decision_note: str,
    decided_by: str,
) -> dict:
    """Second officer signs off (or rejects). Updates evaluations row too."""
    if decision not in ("concurred", "rejected"):
        raise ValueError(f"decision must be concurred|rejected, got {decision!r}")

    req = get_request(conn, request_id)
    if not req:
        raise ValueError(f"Concurrence request not found: {request_id}")
    if req["state"] != "open":
        raise ValueError(f"Concurrence request is {req['state']}, not open.")
    if req["requested_by"] == decided_by:
        raise ValueError("Second officer must differ from the requesting officer.")

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE concurrence_requests
           SET state = ?, decision_note = ?, decided_at = ?, decided_by = ?
           WHERE id = ?""",
        (decision, decision_note, now, decided_by, request_id),
    )
    # Mirror onto the evaluation
    eval_decision = "approve" if decision == "concurred" else "reject"
    new_eval_state = "resolved" if decision == "concurred" else "pending_review"
    conn.execute(
        """UPDATE evaluations
           SET second_officer_id = ?, second_officer_decision = ?,
               second_officer_at = ?, state = ?,
               resolved_at = ?
           WHERE id = ?""",
        (decided_by, eval_decision, now, new_eval_state,
         now if new_eval_state == "resolved" else None,
         req["evaluation_id"]),
    )

    audit_chain.append(
        conn,
        tender_id=req["tender_id"],
        event_type="concurrence_decided",
        event_data={
            "request_id": request_id,
            "evaluation_id": req["evaluation_id"],
            "decision": decision,
        },
        actor=decided_by,
    )
    audit_chain.append(
        conn,
        tender_id=req["tender_id"],
        event_type="second_officer_decided",
        event_data={
            "evaluation_id": req["evaluation_id"],
            "decision": eval_decision,
        },
        actor=decided_by,
    )
    return get_request(conn, request_id)


def withdraw(
    conn, *, request_id: str, by: str,
) -> dict:
    """First officer can withdraw an open request before second officer acts."""
    req = get_request(conn, request_id)
    if not req:
        raise ValueError(f"Concurrence request not found: {request_id}")
    if req["state"] != "open":
        raise ValueError("Only open requests can be withdrawn.")
    if req["requested_by"] != by:
        raise ValueError("Only the requesting officer may withdraw.")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE concurrence_requests SET state = 'withdrawn', decided_at = ? "
        "WHERE id = ?",
        (now, request_id),
    )
    return get_request(conn, request_id)


# ─── Helper ──────────────────────────────────────────────────────────


def _pick_target(conn, exclude_officer_id: str) -> Optional[str]:
    """Pick a concurrence target. Prefer 'reviewer' role; fallback to senior."""
    row = conn.execute(
        "SELECT id FROM officers "
        "WHERE id != ? AND role = 'reviewer' "
        "ORDER BY name LIMIT 1",
        (exclude_officer_id,),
    ).fetchone()
    if row:
        return row["id"]
    row = conn.execute(
        "SELECT id FROM officers WHERE id != ? AND role = 'senior' "
        "ORDER BY name LIMIT 1",
        (exclude_officer_id,),
    ).fetchone()
    return row["id"] if row else None
