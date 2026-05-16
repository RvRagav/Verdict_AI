"""Evaluation service — drives L3 + L4 + L5 + L7 across (bidders × criteria).

Public surface:
    run_evaluation(tender_id) — score every approved-criterion × every
        bidder. Per cell: extract evidence (L3), compute verdict (L4),
        run smell test once per bidder (L5), emit post-review checks
        (L7) for non-auto-committed cells. Streams progress via
        the optional progress_cb.

    list_evaluations(...) — read-side.
    get_evaluation(...) — full row + post_review_checks.
    decide_evaluation(...) — officer confirms/overrides a verdict.
    second_officer_decide(...) — required-second-officer confirmation.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from backend.core import audit_chain, state_machine
from backend.pipeline import (
    anomaly_pipeline,
    evidence_extraction,
    post_review,
    verdict as verdict_pipeline,
)
from backend.services import bidder_service, criteria_service, tender_service

logger = logging.getLogger(__name__)


def run_evaluation(
    conn,
    *,
    tender_id: str,
    actor: str,
    progress_cb: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Run end-to-end evaluation: criteria × bidders.

    The tender must be in PRELIMINARY_DONE. We move it through EVALUATING
    → EVALUATIONS_COMPUTED → (HITL_PENDING | EVALUATION_COMPLETE).
    """
    tender = tender_service.get_tender(conn, tender_id)
    if not tender:
        raise ValueError(f"Tender not found: {tender_id}")
    if tender["state"] not in ("PRELIMINARY_DONE", "EVALUATING", "HITL_PENDING", "EVALUATION_COMPLETE"):
        raise ValueError(
            f"Cannot run evaluation from state {tender['state']!r}; "
            "tender must be PRELIMINARY_DONE, HITL_PENDING, or EVALUATION_COMPLETE."
        )

    if tender["state"] != "EVALUATING":
        tender_service.transition_state(
            conn, tender_id=tender_id, target_state="EVALUATING", actor=actor,
        )

    criteria = [c for c in criteria_service.list_criteria(conn, tender_id)
                if c["state"] == "approved"]
    # Evaluate ALL non-excluded bidders — not just preliminary_passed.
    # The product is decision-support, not an auto-rejector. The officer
    # sees every bidder side-by-side and decides. Bidders with missing
    # mandatory docs are still shown, with the missing items flagged.
    bidders = [b for b in bidder_service.list_bidders(conn, tender_id)
               if b["state"] != "excluded"]

    cpm_count = conn.execute(
        "SELECT COUNT(*) AS c FROM precedents"
    ).fetchone()["c"]

    total_cells = len(criteria) * len(bidders)
    cell_index = 0
    summary = {
        "total_cells": total_cells,
        "auto_committed": 0,
        "hitl_review": 0,
        "mandatory_review": 0,
        "anomalies_detected": 0,
        "errors": 0,
    }

    if progress_cb:
        progress_cb({"phase": "start", "total": total_cells})

    for bidder in bidders:
        for crit in criteria:
            cell_index += 1
            try:
                _evaluate_cell(
                    conn,
                    tender_id=tender_id,
                    bidder_id=bidder["id"],
                    criterion=crit,
                    cpm_count=cpm_count,
                    actor=actor,
                    summary=summary,
                )
            except Exception as exc:
                logger.exception(
                    "Evaluation cell failed (bidder=%s criterion=%s): %s",
                    bidder["id"], crit["id"], exc,
                )
                summary["errors"] += 1

            if progress_cb:
                progress_cb({
                    "phase": "cell_complete",
                    "index": cell_index,
                    "total": total_cells,
                    "bidder_id": bidder["id"],
                    "criterion_id": crit["id"],
                })

        # 5. Smell test runs once per bidder (cross-cell signals)
        try:
            anomalies = anomaly_pipeline.detect_anomalies(
                conn, tender_id=tender_id, bidder_id=bidder["id"],
                use_llm=True, actor=actor,
            )
            summary["anomalies_detected"] += len(anomalies)
        except Exception as exc:
            logger.exception("Smell test failed for bidder %s: %s", bidder["id"], exc)

        # Mark bidder evaluated
        bidder_service.update_state(
            conn, bidder_id=bidder["id"], state="evaluated", actor=actor,
        )

    tender_service.transition_state(
        conn, tender_id=tender_id, target_state="EVALUATIONS_COMPUTED", actor=actor,
    )

    next_state = "HITL_PENDING" if (summary["hitl_review"] + summary["mandatory_review"]) > 0 \
        else "EVALUATION_COMPLETE"
    tender_service.transition_state(
        conn, tender_id=tender_id, target_state=next_state, actor=actor,
    )

    if progress_cb:
        progress_cb({"phase": "complete", "summary": summary})

    return summary


# ─── Per-cell driver ──────────────────────────────────────────────────


def _evaluate_cell(
    conn,
    *,
    tender_id: str,
    bidder_id: str,
    criterion: dict,
    cpm_count: int,
    actor: str,
    summary: dict,
) -> None:
    # Skip if already evaluated for this (tender, bidder, criterion)
    existing = conn.execute(
        "SELECT id FROM evaluations "
        "WHERE tender_id = ? AND bidder_id = ? AND criterion_id = ?",
        (tender_id, bidder_id, criterion["id"]),
    ).fetchone()
    if existing:
        return

    evidence = evidence_extraction.extract_evidence(
        conn,
        tender_id=tender_id,
        bidder_id=bidder_id,
        criterion=criterion,
    )
    result = verdict_pipeline.compute_evaluation(
        conn,
        tender_id=tender_id,
        bidder_id=bidder_id,
        criterion=criterion,
        evidence=evidence,
        cpm_count=cpm_count,
        actor=actor,
    )

    route = result["route"]
    if route == "auto_commit":
        summary["auto_committed"] += 1
    elif route == "mandatory_review":
        summary["mandatory_review"] += 1
    else:
        summary["hitl_review"] += 1

    if route != "auto_commit":
        post_review.emit_post_review_checks(
            conn, evaluation_id=result["id"],
        )


# ─── Read-side ───────────────────────────────────────────────────────


def list_evaluations(
    conn,
    *,
    tender_id: str,
    bidder_id: Optional[str] = None,
    criterion_id: Optional[str] = None,
    state: Optional[str] = None,
    route: Optional[str] = None,
) -> list[dict]:
    sql = "SELECT * FROM evaluations WHERE tender_id = ?"
    params: list = [tender_id]
    if bidder_id:
        sql += " AND bidder_id = ?"; params.append(bidder_id)
    if criterion_id:
        sql += " AND criterion_id = ?"; params.append(criterion_id)
    if state:
        sql += " AND state = ?"; params.append(state)
    if route:
        sql += " AND route = ?"; params.append(route)
    sql += " ORDER BY created_at ASC"
    return [_row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def get_evaluation(conn, evaluation_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM evaluations WHERE id = ?", (evaluation_id,),
    ).fetchone()
    if not row:
        return None
    out = _row_to_dict(row)
    out["post_review_checks"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM post_review_checks WHERE evaluation_id = ?",
            (evaluation_id,),
        ).fetchall()
    ]
    out["anomalies_attached"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM anomaly_flags WHERE evaluation_id = ? OR "
            "(bidder_id = ? AND evaluation_id IS NULL)",
            (evaluation_id, out["bidder_id"]),
        ).fetchall()
    ]
    return out


def decide_evaluation(
    conn,
    *,
    evaluation_id: str,
    decision: str,                          # confirmed | overridden
    officer_id: str,
    structured_reason: Optional[str] = None,
    reason_text: Optional[str] = None,
    new_verdict: Optional[str] = None,      # required when decision=overridden
) -> dict:
    """Officer confirms or overrides a verdict.

    Side-effects:
      - Captures an automatic replay snapshot at the moment of decision
      - Opens a second-officer concurrence request when required
      - Advances the tender if no items remain pending
    """
    if decision not in ("confirmed", "overridden"):
        raise ValueError(f"decision must be confirmed|overridden, got {decision!r}")

    row = conn.execute(
        "SELECT * FROM evaluations WHERE id = ?", (evaluation_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Evaluation not found: {evaluation_id}")
    eval_row = dict(row)

    final_verdict = eval_row["verdict"]
    if decision == "overridden":
        if not new_verdict or new_verdict not in ("PASS", "FAIL", "REVIEW"):
            raise ValueError("new_verdict must be PASS|FAIL|REVIEW for an override.")
        final_verdict = new_verdict

    now = datetime.now(timezone.utc).isoformat()

    # Determine next state — concurrence-required cases stay pending until
    # the second officer signs off.
    # Concurrence fires when:
    #   (a) requires_second_officer was set during evaluation (GFR override), OR
    #   (b) officer OVERRIDES a mandatory_review cell (any override on mandatory = needs concurrence)
    requires_second = bool(eval_row["requires_second_officer"])
    if not requires_second and decision == "overridden" and eval_row["route"] == "mandatory_review":
        requires_second = True  # Override on mandatory always needs concurrence
    next_state = "pending_second_officer" if requires_second else "resolved"
    state_machine.eval_transition(eval_row["state"], next_state)

    conn.execute(
        """UPDATE evaluations
           SET officer_decision = ?, officer_id = ?,
               structured_reason = ?, reason_text = ?,
               verdict = ?, state = ?, decided_at = ?,
               resolved_at = ?
           WHERE id = ?""",
        (
            decision, officer_id, structured_reason, reason_text,
            final_verdict, next_state, now,
            now if next_state == "resolved" else None,
            evaluation_id,
        ),
    )
    audit_chain.append(
        conn,
        tender_id=eval_row["tender_id"],
        event_type="evaluation_decided",
        event_data={
            "evaluation_id": evaluation_id,
            "decision": decision,
            "final_verdict": final_verdict,
            "structured_reason": structured_reason,
        },
        actor=officer_id,
    )

    # Auto-snapshot — fire-and-forget point-in-time capture
    try:
        from backend.services import replay_service
        replay_service.capture(conn, evaluation_id=evaluation_id, officer_id=officer_id)
    except Exception as exc:
        logger.warning("Auto-replay capture failed: %s", exc)

    # Auto-open concurrence request when required
    if requires_second:
        try:
            from backend.services import concurrence_service
            reason = (
                "Override of mandatory criterion." if decision == "overridden"
                else "Mandatory-review evaluation requires second-officer concurrence."
            )
            concurrence_service.open_request(
                conn,
                tender_id=eval_row["tender_id"],
                evaluation_id=evaluation_id,
                requested_by=officer_id,
                request_reason=reason,
            )
        except Exception as exc:
            logger.warning("Failed to open concurrence request: %s", exc)

    # Write to institutional memory (Tender DNA) — every decision becomes a precedent
    try:
        _write_precedent(conn, eval_row, final_verdict, decision, officer_id)
    except Exception as exc:
        logger.warning("Failed to write precedent: %s", exc)

    # If we moved every cell to resolved, advance the tender
    _maybe_advance_to_complete(conn, eval_row["tender_id"], officer_id)

    return get_evaluation(conn, evaluation_id)


def second_officer_decide(
    conn,
    *,
    evaluation_id: str,
    decision: str,        # approve | reject
    officer_id: str,
) -> dict:
    """Required-second-officer confirmation for mandatory-review evaluations."""
    if decision not in ("approve", "reject"):
        raise ValueError(f"decision must be approve|reject, got {decision!r}")

    row = conn.execute(
        "SELECT * FROM evaluations WHERE id = ?", (evaluation_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Evaluation not found: {evaluation_id}")
    eval_row = dict(row)

    if eval_row["officer_id"] == officer_id:
        raise ValueError("Second officer must differ from primary officer.")

    next_state = "resolved" if decision == "approve" else "pending_review"
    state_machine.eval_transition(eval_row["state"], next_state)

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE evaluations
           SET second_officer_id = ?, second_officer_decision = ?,
               second_officer_at = ?, state = ?, resolved_at = ?
           WHERE id = ?""",
        (
            officer_id, decision, now, next_state,
            now if next_state == "resolved" else None,
            evaluation_id,
        ),
    )
    audit_chain.append(
        conn,
        tender_id=eval_row["tender_id"],
        event_type="second_officer_decided",
        event_data={
            "evaluation_id": evaluation_id,
            "decision": decision,
        },
        actor=officer_id,
    )
    _maybe_advance_to_complete(conn, eval_row["tender_id"], officer_id)
    return get_evaluation(conn, evaluation_id)


def matrix(
    conn,
    tender_id: str,
) -> dict:
    """Build the (bidder × criterion) matrix the UI renders."""
    bidders = bidder_service.list_bidders(conn, tender_id)
    criteria = criteria_service.list_criteria(conn, tender_id)
    rows = list_evaluations(conn, tender_id=tender_id)
    by_pair: dict[tuple[str, str], dict] = {}
    for r in rows:
        by_pair[(r["bidder_id"], r["criterion_id"])] = r
    cells = []
    for b in bidders:
        for c in criteria:
            ev = by_pair.get((b["id"], c["id"]))
            cells.append({
                "bidder_id": b["id"],
                "criterion_id": c["id"],
                "evaluation_id": ev["id"] if ev else None,
                "verdict": ev["verdict"] if ev else None,
                "confidence": ev["confidence"] if ev else None,
                "route": ev["route"] if ev else None,
                "state": ev["state"] if ev else None,
            })
    return {"bidders": bidders, "criteria": criteria, "cells": cells}


# ─── Helpers ─────────────────────────────────────────────────────────


def _maybe_advance_to_complete(conn, tender_id: str, actor: str) -> None:
    """If no evaluations remain in pending_*, move the tender forward."""
    pending = conn.execute(
        "SELECT COUNT(*) AS c FROM evaluations "
        "WHERE tender_id = ? AND state IN ('pending_review', 'pending_second_officer')",
        (tender_id,),
    ).fetchone()["c"]
    if pending > 0:
        return
    tender = tender_service.get_tender(conn, tender_id)
    if tender and tender["state"] == "HITL_PENDING":
        tender_service.transition_state(
            conn, tender_id=tender_id, target_state="EVALUATION_COMPLETE", actor=actor,
        )


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    d = dict(row)
    for col in ("confidence_breakdown", "extracted_value", "source_bbox",
                "rules_branch", "llm_branch", "dissent_branch",
                "anomalies", "explanation"):
        if d.get(col):
            try:
                d[col] = json.loads(d[col])
            except (json.JSONDecodeError, TypeError):
                pass
    d["entity_match_flag"] = bool(d.get("entity_match_flag"))
    d["requires_second_officer"] = bool(d.get("requires_second_officer"))
    return d


def _write_precedent(conn, eval_row: dict, verdict: str, decision: str, officer_id: str) -> None:
    """Write this decision to the precedents table for institutional memory."""
    import uuid
    from datetime import datetime, timezone

    # Load criterion + tender for context
    criterion = conn.execute(
        "SELECT criterion_text, criterion_type FROM criteria WHERE id = ?",
        (eval_row["criterion_id"],),
    ).fetchone()
    tender = conn.execute(
        "SELECT department, category FROM tenders WHERE id = ?",
        (eval_row["tender_id"],),
    ).fetchone()

    if not criterion or not tender:
        return

    # Build the interpretation text
    reason = eval_row.get("reason_text") or eval_row.get("structured_reason") or ""
    interpretation = f"Officer {decision} the AI's {eval_row.get('verdict', '?')} verdict"
    if reason:
        interpretation += f": {reason[:200]}"

    precedent_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT OR IGNORE INTO precedents
           (id, criterion_text, criterion_type, department, category,
            resolved_interpretation, verdict, officer_action, officer_id,
            tender_id, criterion_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            precedent_id,
            criterion["criterion_text"],
            criterion["criterion_type"],
            tender["department"],
            tender["category"],
            interpretation,
            verdict,
            decision,
            officer_id,
            eval_row["tender_id"],
            eval_row["criterion_id"],
            now,
        ),
    )

    # Update FTS index
    try:
        conn.execute(
            "INSERT INTO precedents_fts (rowid, criterion_text, resolved_interpretation) "
            "VALUES (last_insert_rowid(), ?, ?)",
            (criterion["criterion_text"], interpretation),
        )
    except Exception:
        pass  # FTS insert is best-effort
