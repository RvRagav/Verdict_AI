"""Tender DNA — Institutional Memory.

Reads precedents for a given evaluation cell (similar criteria evaluated
before in the same department/category). Returns the top matches with
what was decided, by whom, and how long ago.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from backend.api.dependencies import get_db


router = APIRouter(prefix="/evaluations/{evaluation_id}/precedents", tags=["precedents"])


@router.get("")
def get_precedents(evaluation_id: str, limit: int = 5, conn=Depends(get_db)):
    """Find similar past decisions for this evaluation's criterion."""

    # Load the evaluation + criterion
    ev = conn.execute(
        """SELECT e.tender_id, e.criterion_id, c.criterion_text, c.criterion_type,
                  t.department, t.category
           FROM evaluations e
           JOIN criteria c ON c.id = e.criterion_id
           JOIN tenders t ON t.id = e.tender_id
           WHERE e.id = ?""",
        (evaluation_id,),
    ).fetchone()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    ev = dict(ev)

    # Search precedents_fts for similar criterion text
    # FTS5 MATCH query — use key terms from the criterion
    search_terms = _extract_search_terms(ev["criterion_text"])

    precedents = []
    if search_terms:
        try:
            rows = conn.execute(
                """SELECT p.*, o.name as officer_name
                   FROM precedents p
                   JOIN officers o ON o.id = p.officer_id
                   WHERE p.id IN (
                       SELECT rowid FROM precedents_fts
                       WHERE precedents_fts MATCH ?
                   )
                   AND p.department = ?
                   ORDER BY p.created_at DESC
                   LIMIT ?""",
                (search_terms, ev["department"], limit),
            ).fetchall()
            precedents = [dict(r) for r in rows]
        except Exception:
            # FTS might not have data yet — fall back to type + department match
            rows = conn.execute(
                """SELECT p.*, o.name as officer_name
                   FROM precedents p
                   JOIN officers o ON o.id = p.officer_id
                   WHERE p.criterion_type = ? AND p.department = ?
                   ORDER BY p.created_at DESC
                   LIMIT ?""",
                (ev["criterion_type"], ev["department"], limit),
            ).fetchall()
            precedents = [dict(r) for r in rows]

    # Format for frontend
    results = []
    for p in precedents:
        results.append({
            "id": p["id"],
            "criterion_text": p["criterion_text"][:100],
            "criterion_type": p["criterion_type"],
            "verdict": p["verdict"],
            "officer_action": p["officer_action"],
            "officer_name": p.get("officer_name", p["officer_id"]),
            "interpretation": p["resolved_interpretation"][:150],
            "created_at": p["created_at"],
            "tender_id": p.get("tender_id"),
        })

    return {
        "evaluation_id": evaluation_id,
        "criterion_text": ev["criterion_text"][:100],
        "department": ev["department"],
        "category": ev["category"],
        "precedents": results,
        "count": len(results),
        "ai_insight": _generate_precedent_insight(conn, ev, results),
    }


def _generate_precedent_insight(conn, ev: dict, precedents: list) -> Optional[str]:
    """Use AI to synthesize a pattern from past precedents.

    Instead of just listing past decisions, the AI identifies the PATTERN:
    - How has this type of criterion been interpreted historically?
    - Is there a consistent approach or conflicting interpretations?
    - What should the officer be aware of?
    """
    if not precedents:
        # Even without precedents, give context about this criterion type
        try:
            from backend.ai import bedrock_client

            prompt = (
                f"You are advising a procurement officer. This is the FIRST TIME this criterion "
                f"is being evaluated in this department. Give one sentence of advice.\n\n"
                f"Criterion: {ev['criterion_text'][:200]}\n"
                f"Type: {ev['criterion_type']}\n"
                f"Department: {ev['department']}\n\n"
                f"What should the officer be careful about when evaluating this for the first time? "
                f"One sentence, specific to this criterion type."
            )
            resp = bedrock_client.invoke(
                invocation_type="precedent_insight",
                system="You are a senior procurement advisor. One sentence max. Be specific.",
                user=prompt,
                prompt_version="1.0.0",
                conn=conn,
                max_tokens=100,
            )
            if resp.text and not resp.error:
                return resp.text.strip()
        except Exception:
            pass
        return None

    # With precedents — synthesize the pattern
    try:
        from backend.ai import bedrock_client

        precedent_summary = "\n".join([
            f"- {p['officer_name']} {p['officer_action']} ({p['verdict']}) — {p['interpretation'][:80]}"
            for p in precedents[:5]
        ])

        prompt = (
            f"You are advising a procurement officer about institutional precedent.\n\n"
            f"Current criterion: {ev['criterion_text'][:200]}\n"
            f"Department: {ev['department']}, Category: {ev['category']}\n\n"
            f"Past decisions on similar criteria:\n{precedent_summary}\n\n"
            f"In 2-3 sentences: What pattern do you see? Is there a consistent interpretation? "
            f"What should the officer know before deciding?"
        )
        resp = bedrock_client.invoke(
            invocation_type="precedent_insight",
            system="You are a senior procurement advisor. Be concise and specific. 2-3 sentences max.",
            user=prompt,
            prompt_version="1.0.0",
            conn=conn,
            max_tokens=200,
        )
        if resp.text and not resp.error:
            return resp.text.strip()
    except Exception:
        pass
    return None


def _extract_search_terms(text: str) -> str:
    """Extract key terms for FTS5 search from criterion text."""
    import re
    # Remove common words, keep domain-specific terms
    stop = {'the', 'shall', 'have', 'been', 'not', 'less', 'than', 'for', 'and',
            'with', 'from', 'that', 'this', 'which', 'are', 'was', 'were', 'has',
            'had', 'will', 'can', 'may', 'must', 'should', 'would', 'could',
            'each', 'last', 'years', 'year', 'bidder', 'valid', 'certificate'}
    words = re.findall(r'[A-Za-z]+', text.lower())
    terms = [w for w in words if w not in stop and len(w) > 3][:8]
    if not terms:
        return ""
    return " OR ".join(terms)
