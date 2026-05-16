"""Per-cell officer comments — Module 4 HITL.

A comment is an officer's note attached to one evaluation cell. It is
NOT a verdict and does NOT change routing — it's the human's space
to think out loud, capture context for a future inquiry, or push back
on the AI's framing.

Comments are now AI-classified into categories (observation, logic,
action_required, brainstorm, concern). When a comment contains logic
or concern that challenges the verdict, the system flags it for
re-evaluation consideration — making officer thinking and AI analysis
feel like one unified channel, not separate silos.

Append-only by convention (no edit/delete API). Audit-chained.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.core import audit_chain

logger = logging.getLogger(__name__)


def add_comment(
    conn,
    *,
    tender_id: str,
    evaluation_id: Optional[str],
    bidder_id: Optional[str],
    criterion_id: Optional[str],
    officer_id: str,
    body: str,
) -> dict:
    """Add a comment. evaluation_id is the typical case; bidder/criterion
    can be passed for "general note on this bidder" or "general note on
    this criterion".

    After insertion, triggers async AI classification which updates the
    comment's category, affects_verdict, suggested_action, and key_insight.
    """
    if not body or not body.strip():
        raise ValueError("Comment body cannot be empty.")
    if not evaluation_id and not bidder_id and not criterion_id:
        raise ValueError("Comment must target an evaluation, bidder, or criterion.")

    # Backfill bidder + criterion from evaluation when only evaluation_id
    # is given — makes downstream filtering simpler.
    if evaluation_id and (not bidder_id or not criterion_id):
        ev = conn.execute(
            "SELECT bidder_id, criterion_id FROM evaluations WHERE id = ?",
            (evaluation_id,),
        ).fetchone()
        if ev:
            bidder_id = bidder_id or ev["bidder_id"]
            criterion_id = criterion_id or ev["criterion_id"]

    comment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO officer_comments
           (id, tender_id, evaluation_id, bidder_id, criterion_id,
            officer_id, body, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (comment_id, tender_id, evaluation_id, bidder_id, criterion_id,
         officer_id, body.strip(), now),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="officer_comment_added",
        event_data={
            "comment_id": comment_id,
            "evaluation_id": evaluation_id,
            "bidder_id": bidder_id,
            "criterion_id": criterion_id,
        },
        actor=officer_id,
    )

    # AI classification — best-effort, non-blocking for the response
    if evaluation_id:
        try:
            _classify_comment(conn, comment_id, evaluation_id, body.strip())
        except Exception as exc:
            logger.warning("Comment classification failed: %s", exc)

    return get_comment(conn, comment_id)


def _classify_comment(conn, comment_id: str, evaluation_id: str, body: str) -> None:
    """Use Bedrock to classify the comment and update the row."""
    from backend.ai.bedrock_client import invoke
    from backend.ai.prompts import COMMENT_CLASSIFY

    # Get evaluation context
    ev = conn.execute(
        """SELECT e.verdict, e.confidence, e.tender_id, c.criterion_text, b.company_name
           FROM evaluations e
           JOIN criteria c ON c.id = e.criterion_id
           JOIN bidders b ON b.id = e.bidder_id
           WHERE e.id = ?""",
        (evaluation_id,),
    ).fetchone()
    if not ev:
        return

    user_msg = COMMENT_CLASSIFY.render_user(
        verdict=ev["verdict"],
        confidence=f"{ev['confidence']:.2f}",
        criterion_text=ev["criterion_text"],
        bidder_name=ev["company_name"],
        comment_body=body,
    )

    result = invoke(
        invocation_type="comment_classify",
        system=COMMENT_CLASSIFY.system,
        user=user_msg,
        prompt_version=COMMENT_CLASSIFY.version,
        structured=True,
        schema_hint=COMMENT_CLASSIFY.schema_hint,
        max_tokens=300,
        tender_id=ev["tender_id"],
        conn=conn,
        use_cache=False,  # Each comment is unique
    )

    if result.error or not result.data:
        return

    data = result.data
    category = data.get("category")
    affects_verdict = 1 if data.get("affects_verdict") else 0
    suggested_action = data.get("suggested_action")
    key_insight = data.get("key_insight")

    # Validate category
    valid_categories = ("observation", "logic", "action_required", "brainstorm", "concern")
    if category not in valid_categories:
        category = "observation"

    valid_actions = ("re_evaluate", "verify_document", "check_with_bidder", "escalate")
    if suggested_action not in valid_actions:
        suggested_action = None

    conn.execute(
        """UPDATE officer_comments
           SET category = ?, affects_verdict = ?, suggested_action = ?, key_insight = ?
           WHERE id = ?""",
        (category, affects_verdict, suggested_action, key_insight, comment_id),
    )


def get_comment(conn, comment_id: str) -> Optional[dict]:
    row = conn.execute(
        """SELECT c.*, o.name AS officer_name, o.role AS officer_role
           FROM officer_comments c
           JOIN officers o ON o.id = c.officer_id
           WHERE c.id = ?""",
        (comment_id,),
    ).fetchone()
    return dict(row) if row else None


def list_for_evaluation(conn, evaluation_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT c.*, o.name AS officer_name, o.role AS officer_role
           FROM officer_comments c
           JOIN officers o ON o.id = c.officer_id
           WHERE c.evaluation_id = ?
           ORDER BY c.created_at ASC""",
        (evaluation_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_for_tender(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT c.*, o.name AS officer_name, o.role AS officer_role
           FROM officer_comments c
           JOIN officers o ON o.id = c.officer_id
           WHERE c.tender_id = ?
           ORDER BY c.created_at DESC""",
        (tender_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_actionable_comments(conn, evaluation_id: str) -> list[dict]:
    """Get comments that AI flagged as affecting the verdict — used by
    the pre-mortem and re-evaluation suggestion system."""
    rows = conn.execute(
        """SELECT c.*, o.name AS officer_name, o.role AS officer_role
           FROM officer_comments c
           JOIN officers o ON o.id = c.officer_id
           WHERE c.evaluation_id = ? AND c.affects_verdict = 1
           ORDER BY c.created_at ASC""",
        (evaluation_id,),
    ).fetchall()
    return [dict(r) for r in rows]
