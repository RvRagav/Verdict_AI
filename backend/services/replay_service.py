"""Time Capsule Replay — capture & retrieve decision snapshots.

Every officer decision (and key system computations) creates an
immutable "replay snapshot" — a JSON freeze of:
  - the criterion as it was at decision time
  - the evidence as extracted
  - the verdict, confidence, breakdown, dissent
  - the routing decision
  - the officer's reason and choice
  - the prompt hashes + pipeline_signature

Months later, an officer (or auditor) can open the same evaluation
and play back exactly what was on the screen the moment the decision
was made. Schema-evolution-proof: snapshots are JSON, not joins.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.core import audit_chain


def capture(
    conn,
    *,
    evaluation_id: str,
    officer_id: str,
) -> dict:
    """Snapshot the current state of an evaluation."""
    row = conn.execute(
        """SELECT e.*, c.criterion_text, c.criterion_type, c.threshold_value,
                  c.is_mandatory, c.gfr_rule_number, c.source_clause_ref,
                  b.company_name AS bidder_name
           FROM evaluations e
           JOIN criteria c ON c.id = e.criterion_id
           JOIN bidders b ON b.id = e.bidder_id
           WHERE e.id = ?""",
        (evaluation_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Evaluation not found: {evaluation_id}")

    snapshot = _build_snapshot(dict(row))

    replay_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO decision_replays
           (id, evaluation_id, officer_id, snapshot, timestamp)
           VALUES (?, ?, ?, ?, ?)""",
        (replay_id, evaluation_id, officer_id,
         json.dumps(snapshot), now),
    )
    audit_chain.append(
        conn,
        tender_id=row["tender_id"],
        event_type="decision_replay_captured",
        event_data={
            "replay_id": replay_id,
            "evaluation_id": evaluation_id,
        },
        actor=officer_id,
    )
    return {"id": replay_id, "evaluation_id": evaluation_id,
            "officer_id": officer_id, "timestamp": now,
            "snapshot": snapshot}


def list_replays(conn, evaluation_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, evaluation_id, officer_id, timestamp "
        "FROM decision_replays WHERE evaluation_id = ? "
        "ORDER BY timestamp ASC",
        (evaluation_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_replay(conn, replay_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM decision_replays WHERE id = ?", (replay_id,),
    ).fetchone()
    if not row:
        return None
    out = dict(row)
    try:
        out["snapshot"] = json.loads(out["snapshot"])
    except (json.JSONDecodeError, TypeError):
        pass
    return out


def _build_snapshot(eval_row: dict) -> dict:
    """Pack the evaluation + criterion + bidder info into a JSON blob."""
    def _maybe_load(v):
        if not v:
            return None
        if isinstance(v, (dict, list)):
            return v
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return v

    return {
        "schema_version": "1.0",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "tender_id": eval_row.get("tender_id"),
        "evaluation_id": eval_row.get("id"),
        "criterion": {
            "id": eval_row.get("criterion_id"),
            "text": eval_row.get("criterion_text"),
            "type": eval_row.get("criterion_type"),
            "threshold_value": _maybe_load(eval_row.get("threshold_value")),
            "is_mandatory": bool(eval_row.get("is_mandatory")),
            "gfr_rule_number": eval_row.get("gfr_rule_number"),
            "source_clause_ref": eval_row.get("source_clause_ref"),
        },
        "bidder": {
            "id": eval_row.get("bidder_id"),
            "name": eval_row.get("bidder_name"),
        },
        "verdict": eval_row.get("verdict"),
        "confidence": eval_row.get("confidence"),
        "confidence_breakdown": _maybe_load(eval_row.get("confidence_breakdown")),
        "route": eval_row.get("route"),
        "routing_reason": eval_row.get("routing_reason"),
        "evidence": {
            "extracted_value": _maybe_load(eval_row.get("extracted_value")),
            "source_doc_id": eval_row.get("source_doc_id"),
            "source_page": eval_row.get("source_page"),
            "source_bbox": _maybe_load(eval_row.get("source_bbox")),
        },
        "branches": {
            "rules": _maybe_load(eval_row.get("rules_branch")),
            "llm": _maybe_load(eval_row.get("llm_branch")),
            "dissent": _maybe_load(eval_row.get("dissent_branch")),
        },
        "anomalies": _maybe_load(eval_row.get("anomalies")),
        "explanation": _maybe_load(eval_row.get("explanation")),
        "officer_decision": {
            "decision": eval_row.get("officer_decision"),
            "officer_id": eval_row.get("officer_id"),
            "structured_reason": eval_row.get("structured_reason"),
            "reason_text": eval_row.get("reason_text"),
            "decided_at": eval_row.get("decided_at"),
        },
        "second_officer": {
            "officer_id": eval_row.get("second_officer_id"),
            "decision": eval_row.get("second_officer_decision"),
            "decided_at": eval_row.get("second_officer_at"),
        },
        "hashes": {
            "extraction_prompt": eval_row.get("extraction_prompt_hash"),
            "verdict_prompt": eval_row.get("verdict_prompt_hash"),
            "dissent_prompt": eval_row.get("dissent_prompt_hash"),
            "pipeline_signature": eval_row.get("pipeline_signature_hash"),
        },
    }
