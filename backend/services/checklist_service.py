"""Checklist matching — semantic LLM match + token-overlap pre-filter.

After bidders upload their documents, we run a *semantic* match against
the checklist items extracted from the NIT. Token overlap on filenames
gives us a cheap candidate; the LLM does the actual semantic match
using each upload's first-page text. Cached by prompt hash.

Officers can override individual matches in the UI. Once all checklist
responses are decided, the tender advances to PRELIMINARY_DONE.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.ai import bedrock_client
from backend.ai.prompts import CHECKLIST_MATCH
from backend.core import audit_chain
from backend.services import bidder_service, tender_service

logger = logging.getLogger(__name__)


def list_checklist(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM document_checklist WHERE tender_id = ? "
        "ORDER BY created_at ASC",
        (tender_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def auto_match(
    conn,
    *,
    tender_id: str,
    bidder_id: str,
    actor: str = "system",
) -> list[dict]:
    """Auto-populate checklist_responses for one bidder.

    Strategy:
      1. Fetch checklist + bidder uploads (with first-page summaries)
      2. Skip already-decided items
      3. One Bedrock call → semantic match (cached on prompt hash)
      4. Fall back to token-overlap if LLM call fails
      5. Insert checklist_responses rows
    """
    items = list_checklist(conn, tender_id)
    docs = conn.execute(
        "SELECT d.id, d.filename, d.doc_type, "
        "       (SELECT raw_text FROM pages WHERE document_id = d.id "
        "        ORDER BY page_number LIMIT 1) AS first_page_text "
        "FROM documents d "
        "WHERE d.tender_id = ? AND d.bidder_id = ? AND d.deleted_at IS NULL "
        "AND d.processing_state = 'complete'",
        (tender_id, bidder_id),
    ).fetchall()
    docs_list = [dict(d) for d in docs]

    # Skip items already responded
    items_to_match = []
    for item in items:
        existing = conn.execute(
            "SELECT id FROM checklist_responses "
            "WHERE tender_id = ? AND bidder_id = ? AND checklist_item_id = ?",
            (tender_id, bidder_id, item["id"]),
        ).fetchone()
        if not existing:
            items_to_match.append(item)
    if not items_to_match:
        return []

    matches_by_item = _semantic_match(
        conn, tender_id=tender_id, items=items_to_match, docs=docs_list,
    )

    now = datetime.now(timezone.utc).isoformat()
    inserted: list[dict] = []
    for item in items_to_match:
        match = matches_by_item.get(item["id"])
        response_id = str(uuid.uuid4())
        if match and match.get("matched_document_id"):
            conn.execute(
                """INSERT INTO checklist_responses
                   (id, tender_id, bidder_id, checklist_item_id, state,
                    matched_doc_id, confidence, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (response_id, tender_id, bidder_id, item["id"],
                 match.get("state") or "present",
                 match["matched_document_id"],
                 float(match.get("confidence") or 0.7),
                 match.get("reason"), now),
            )
        else:
            conn.execute(
                """INSERT INTO checklist_responses
                   (id, tender_id, bidder_id, checklist_item_id, state,
                    confidence, notes, created_at)
                   VALUES (?, ?, ?, ?, 'missing', 0, ?, ?)""",
                (response_id, tender_id, bidder_id, item["id"],
                 (match.get("reason") if match else None), now),
            )
        inserted.append({"id": response_id, "checklist_item_id": item["id"]})

    return inserted


def _semantic_match(
    conn,
    *,
    tender_id: str,
    items: list[dict],
    docs: list[dict],
) -> dict[str, dict]:
    """Bedrock semantic match for unmatched items. Returns {item_id: match}."""
    if not items or not docs:
        return {item["id"]: {"matched_document_id": None,
                              "state": "missing",
                              "confidence": 0.0,
                              "reason": "No bidder documents uploaded yet."}
                for item in items}

    checklist_payload = [
        {
            "id": item["id"],
            "label": item["document_label"],
            "is_mandatory": bool(item["is_mandatory"]),
            "matches_doc_type": item.get("matches_doc_type"),
        }
        for item in items
    ]
    uploads_payload = [
        {
            "id": d["id"],
            "filename": d["filename"],
            "doc_type": d["doc_type"],
            "first_page_excerpt": (d.get("first_page_text") or "")[:600],
        }
        for d in docs
    ]

    user_prompt = CHECKLIST_MATCH.render_user(
        checklist_json=json.dumps(checklist_payload, ensure_ascii=False),
        uploads_json=json.dumps(uploads_payload, ensure_ascii=False),
    )
    resp = bedrock_client.invoke(
        invocation_type="checklist_match",
        system=CHECKLIST_MATCH.system,
        user=user_prompt,
        prompt_version=CHECKLIST_MATCH.version,
        structured=True,
        schema_hint=CHECKLIST_MATCH.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )

    out: dict[str, dict] = {}
    if not resp.error and isinstance(resp.data, dict):
        for m in resp.data.get("matches") or []:
            if not isinstance(m, dict):
                continue
            cid = m.get("checklist_item_id")
            if cid:
                out[cid] = m

    # Fill in any items the LLM missed via token overlap fallback
    for item in items:
        if item["id"] in out:
            continue
        fallback = _token_overlap_match(item, docs)
        if fallback:
            out[item["id"]] = {
                "matched_document_id": fallback["doc_id"],
                "state": fallback["state"],
                "confidence": fallback["confidence"],
                "reason": "Filename token overlap (LLM did not return a match).",
            }
        else:
            out[item["id"]] = {
                "matched_document_id": None,
                "state": "missing",
                "confidence": 0.0,
                "reason": "No matching document found.",
            }
    return out


def list_responses(
    conn,
    *,
    tender_id: str,
    bidder_id: Optional[str] = None,
) -> list[dict]:
    sql = ("SELECT cr.*, dc.document_label, dc.is_mandatory "
           "FROM checklist_responses cr "
           "JOIN document_checklist dc ON dc.id = cr.checklist_item_id "
           "WHERE cr.tender_id = ?")
    params: list = [tender_id]
    if bidder_id:
        sql += " AND cr.bidder_id = ?"
        params.append(bidder_id)
    sql += " ORDER BY cr.created_at ASC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def decide_response(
    conn,
    *,
    response_id: str,
    decision: str,
    officer_id: str,
    notes: Optional[str] = None,
) -> dict:
    """Officer marks a checklist response accepted or rejected."""
    if decision not in ("accepted", "rejected"):
        raise ValueError(f"decision must be accepted|rejected, got {decision!r}")

    row = conn.execute(
        "SELECT tender_id, bidder_id, checklist_item_id "
        "FROM checklist_responses WHERE id = ?",
        (response_id,),
    ).fetchone()
    if not row:
        raise ValueError(f"Checklist response not found: {response_id}")

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE checklist_responses SET officer_decision = ?, officer_id = ?, "
        "decided_at = ?, notes = ? WHERE id = ?",
        (decision, officer_id, now, notes, response_id),
    )
    audit_chain.append(
        conn,
        tender_id=row["tender_id"],
        event_type="checklist_response_decided",
        event_data={
            "response_id": response_id,
            "bidder_id": row["bidder_id"],
            "checklist_item_id": row["checklist_item_id"],
            "decision": decision,
        },
        actor=officer_id,
    )
    return _get_response(conn, response_id)


def finalize_preliminary(
    conn,
    *,
    tender_id: str,
    actor: str,
) -> dict:
    """Advance the tender CHECKLIST_PENDING → PRELIMINARY_DONE.

    Sets each bidder's state based on whether they have any missing
    mandatory checklist items.
    """
    bidders = bidder_service.list_bidders(conn, tender_id)
    for b in bidders:
        responses = list_responses(conn, tender_id=tender_id, bidder_id=b["id"])
        has_missing_mandatory = any(
            r["is_mandatory"] and r["state"] == "missing"
            and r.get("officer_decision") != "accepted"
            for r in responses
        )
        new_state = "preliminary_failed" if has_missing_mandatory else "preliminary_passed"
        bidder_service.update_state(
            conn, bidder_id=b["id"], state=new_state, actor=actor,
        )

    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="preliminary_finalised",
        event_data={"bidder_count": len(bidders)},
        actor=actor,
    )
    return tender_service.transition_state(
        conn, tender_id=tender_id, target_state="PRELIMINARY_DONE", actor=actor,
    )


# ─── Matching algorithm ────────────────────────────────────────────────


_TOKENISE = re.compile(r"[a-z0-9]+")


def _tokenise(s: str) -> set[str]:
    return set(_TOKENISE.findall((s or "").lower()))


def _token_overlap_match(item: dict, docs: list[dict]) -> Optional[dict]:
    """Cheap fallback when LLM is unavailable."""
    label = (item.get("document_label") or "").lower()
    matches_type = (item.get("matches_doc_type") or "").lower()
    label_tokens = _tokenise(label)
    if not label_tokens:
        return None

    best: Optional[dict] = None
    best_score = 0.0
    for d in docs:
        fname_tokens = _tokenise(d.get("filename", ""))
        overlap = len(label_tokens & fname_tokens)
        score = overlap / max(1, len(label_tokens))
        if matches_type and matches_type == (d.get("doc_type") or "").lower():
            score += 0.3
        if score > best_score:
            best_score = score
            best = d

    if not best or best_score < 0.4:
        return None
    confidence = min(1.0, round(best_score, 3))
    state = "present" if best_score >= 0.7 else "partial"
    return {"doc_id": best["id"], "confidence": confidence, "state": state}


def _get_response(conn, response_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM checklist_responses WHERE id = ?", (response_id,),
    ).fetchone()
    return dict(row) if row else {}
