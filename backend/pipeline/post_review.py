"""Post-review checks (L7) — "Question I Should Have Asked".

After every evaluation is computed, we drop a set of pre-canned check
prompts into post_review_checks. The UI shows them after the officer
makes their decision: "Did you also verify…?"

These are deterministic — no LLM call, no cost. The prompts are
scoped by criterion_type (and optionally a sub-tag the prompt
defines). Each is one row in post_review_checks with check_text +
check_type. The UI presents them as a yes/no/n_a checklist.

Design choice: we run this lazily — only when the officer reaches
the review screen for that evaluation. That avoids polluting the
table with dead rows for evaluations that auto-commit.

The `emit_post_review_checks(evaluation_id)` is idempotent — if checks
already exist for an evaluation, it does nothing.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from backend.ai.prompts import POST_REVIEW_CHECKS_BY_TYPE

logger = logging.getLogger(__name__)


def emit_post_review_checks(conn, *, evaluation_id: str) -> list[dict]:
    """Write the pre-canned checks for one evaluation. Idempotent.

    Returns the list of inserted rows (or existing rows on the second call).
    """
    row = conn.execute(
        """SELECT e.id, c.criterion_type
           FROM evaluations e
           JOIN criteria c ON c.id = e.criterion_id
           WHERE e.id = ?""",
        (evaluation_id,),
    ).fetchone()
    if not row:
        return []

    existing = conn.execute(
        "SELECT id, check_text, check_type, answer FROM post_review_checks "
        "WHERE evaluation_id = ?",
        (evaluation_id,),
    ).fetchall()
    if existing:
        return [dict(r) for r in existing]

    ctype = row["criterion_type"]
    checks = POST_REVIEW_CHECKS_BY_TYPE.get(ctype, [])
    if not checks:
        return []

    now = datetime.now(timezone.utc).isoformat()
    inserted: list[dict] = []
    for check_text, check_type in checks:
        check_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO post_review_checks
               (id, evaluation_id, check_text, check_type,
                answered_by, answer, answered_at, created_at)
               VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?)""",
            (check_id, evaluation_id, check_text, check_type, now),
        )
        inserted.append({
            "id": check_id,
            "evaluation_id": evaluation_id,
            "check_text": check_text,
            "check_type": check_type,
            "answer": None,
        })
    return inserted


def answer_check(
    conn,
    *,
    check_id: str,
    answer: str,
    officer_id: str,
) -> dict:
    """Record the officer's answer to a single check."""
    if answer not in ("yes", "no", "not_applicable"):
        raise ValueError(f"answer must be yes|no|not_applicable, got {answer!r}")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE post_review_checks SET answer = ?, answered_by = ?, answered_at = ? "
        "WHERE id = ?",
        (answer, officer_id, now, check_id),
    )
    row = conn.execute(
        "SELECT id, evaluation_id, check_text, check_type, answer, "
        "       answered_by, answered_at "
        "FROM post_review_checks WHERE id = ?",
        (check_id,),
    ).fetchone()
    return dict(row) if row else {}
