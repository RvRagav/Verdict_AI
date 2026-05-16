"""Criterion extraction (L2) — NIT → structured eligibility criteria.

Uses Claude on Bedrock to read the NIT text and return a list of
typed criteria. We feed the LLM the concatenated raw_text from all
pages of the NIT document, plus its page→text map so we can attribute
each extracted criterion back to its source page.

Pipeline:
    1. Concatenate NIT pages with markers
    2. Single Bedrock call → {criteria: [...]}
    3. For each criterion, infer source_page by substring matching
    4. Insert criteria rows + audit event

The function also extracts the document checklist via a second Bedrock
call (separate prompt). Both runs are cached by prompt_hash, so
re-running on the same NIT is a no-op cost-wise.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.ai import bedrock_client
from backend.ai.prompts import (
    CRITERION_EXTRACTION,
    CHECKLIST_EXTRACTION,
)
from backend.core import audit_chain

logger = logging.getLogger(__name__)


def extract_criteria(
    conn,
    *,
    tender_id: str,
    nit_document_id: str,
    actor: str = "system",
) -> list[dict]:
    """Extract criteria from the NIT document. Returns inserted rows."""
    pages = conn.execute(
        "SELECT page_number, raw_text FROM pages WHERE document_id = ? "
        "ORDER BY page_number",
        (nit_document_id,),
    ).fetchall()

    if not pages:
        return []

    # Build the NIT text with page markers
    parts = []
    for p in pages:
        parts.append(f"[Page {p['page_number']}]\n{p['raw_text']}")
    nit_text = "\n\n".join(parts)

    # Truncate if absurdly long — Claude can handle a lot but cost adds up
    # ~24k chars ≈ ~6k tokens leaves headroom under 8k max output.
    if len(nit_text) > 60_000:
        nit_text = nit_text[:60_000] + "\n\n[truncated]"

    # ─── Bedrock call ───────────────────────────────────────────────
    user_prompt = CRITERION_EXTRACTION.render_user(nit_text=nit_text)
    resp = bedrock_client.invoke(
        invocation_type="criterion_extraction",
        system=CRITERION_EXTRACTION.system,
        user=user_prompt,
        prompt_version=CRITERION_EXTRACTION.version,
        structured=True,
        schema_hint=CRITERION_EXTRACTION.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )

    if resp.error or not resp.data:
        logger.error("Criterion extraction failed: %s", resp.error)
        return []

    raw_criteria = []
    if isinstance(resp.data, dict):
        raw_criteria = resp.data.get("criteria", [])
    elif isinstance(resp.data, list):
        raw_criteria = resp.data

    inserted: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    for item in raw_criteria:
        if not isinstance(item, dict):
            continue
        criterion_text = item.get("criterion_text") or ""
        criterion_type = item.get("criterion_type") or "qualitative_assessment"
        if criterion_type not in (
            "numeric_threshold", "categorical_presence",
            "temporal_recency", "qualitative_assessment", "composite",
        ):
            criterion_type = "qualitative_assessment"

        is_mandatory = bool(item.get("is_mandatory", False))
        threshold_value = item.get("threshold_value")
        gfr_rule_number = item.get("gfr_rule_number")
        source_clause = item.get("source_clause_ref")
        acceptable_evidence = item.get("acceptable_evidence")

        # Find which page contains this criterion text
        source_page = _find_source_page(criterion_text, pages)

        # GFR override: by default, mandatory financial/categorical criteria
        # don't permit override; qualitative ones do
        gfr_override_permitted = (
            criterion_type == "qualitative_assessment"
        )

        criterion_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO criteria
               (id, tender_id, criterion_text, criterion_type, threshold_value,
                is_mandatory, gfr_rule_number, gfr_override_permitted,
                source_doc_id, source_clause_ref, source_page, source_bbox,
                amendment_history, acceptable_evidence, measurement_period,
                state, current_version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'extracted', 1, ?)""",
            (
                criterion_id, tender_id, criterion_text, criterion_type,
                json.dumps(threshold_value) if threshold_value is not None else None,
                1 if is_mandatory else 0,
                gfr_rule_number,
                1 if gfr_override_permitted else 0,
                nit_document_id, source_clause, source_page, None,
                None,
                json.dumps(acceptable_evidence) if acceptable_evidence else None,
                None,
                now,
            ),
        )
        # Append the v1 row to criterion_versions (the append-only history)
        _write_criterion_version(
            conn, criterion_id=criterion_id, version=1,
            criterion_text=criterion_text, criterion_type=criterion_type,
            threshold_value=threshold_value,
            is_mandatory=is_mandatory,
            gfr_rule_number=gfr_rule_number,
            source_clause_ref=source_clause,
            source_page=source_page,
            change_source="extracted",
            corrigendum_id=None,
            changed_by=actor if actor != "system" else None,
            change_note="Initial AI extraction from NIT.",
            now=now,
        )
        inserted.append({
            "id": criterion_id,
            "criterion_text": criterion_text,
            "criterion_type": criterion_type,
            "is_mandatory": is_mandatory,
            "gfr_rule_number": gfr_rule_number,
            "gfr_override_permitted": gfr_override_permitted,
            "source_clause_ref": source_clause,
            "source_page": source_page,
        })

    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="criteria_extracted",
        event_data={
            "nit_document_id": nit_document_id,
            "criteria_count": len(inserted),
            "prompt_hash": resp.prompt_hash,
            "cached": resp.cached,
        },
        actor=actor,
    )

    return inserted


def _write_criterion_version(
    conn,
    *,
    criterion_id: str,
    version: int,
    criterion_text: str,
    criterion_type: str,
    threshold_value,
    is_mandatory: bool,
    gfr_rule_number: Optional[str],
    source_clause_ref: Optional[str],
    source_page: Optional[int],
    change_source: str,
    corrigendum_id: Optional[str],
    changed_by: Optional[str],
    change_note: Optional[str],
    now: str,
) -> str:
    """Insert a row into the append-only criterion_versions table."""
    version_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO criterion_versions
           (id, criterion_id, version, criterion_text, criterion_type,
            threshold_value, is_mandatory, gfr_rule_number,
            source_clause_ref, source_page,
            change_source, corrigendum_id, changed_by, change_note,
            created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            version_id, criterion_id, version, criterion_text, criterion_type,
            json.dumps(threshold_value) if threshold_value is not None else None,
            1 if is_mandatory else 0,
            gfr_rule_number, source_clause_ref, source_page,
            change_source, corrigendum_id, changed_by, change_note,
            now,
        ),
    )
    return version_id


def extract_checklist(
    conn,
    *,
    tender_id: str,
    nit_document_id: str,
    actor: str = "system",
) -> list[dict]:
    """Extract the document submission checklist from the NIT."""
    pages = conn.execute(
        "SELECT page_number, raw_text FROM pages WHERE document_id = ? "
        "ORDER BY page_number",
        (nit_document_id,),
    ).fetchall()
    if not pages:
        return []

    parts = []
    for p in pages:
        parts.append(f"[Page {p['page_number']}]\n{p['raw_text']}")
    nit_text = "\n\n".join(parts)
    if len(nit_text) > 60_000:
        nit_text = nit_text[:60_000]

    user_prompt = CHECKLIST_EXTRACTION.render_user(nit_text=nit_text)
    resp = bedrock_client.invoke(
        invocation_type="checklist_extraction",
        system=CHECKLIST_EXTRACTION.system,
        user=user_prompt,
        prompt_version=CHECKLIST_EXTRACTION.version,
        structured=True,
        schema_hint=CHECKLIST_EXTRACTION.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )

    if resp.error or not resp.data:
        return []

    raw_items = []
    if isinstance(resp.data, dict):
        raw_items = resp.data.get("items", [])
    elif isinstance(resp.data, list):
        raw_items = resp.data

    inserted: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        label = (item.get("document_label") or "").strip()
        if not label:
            continue
        is_mandatory = bool(item.get("is_mandatory", True))
        matches_doc_type = item.get("matches_doc_type")
        item_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO document_checklist
               (id, tender_id, document_label, is_mandatory,
                matches_doc_type, extracted_from, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (item_id, tender_id, label,
             1 if is_mandatory else 0,
             matches_doc_type, nit_document_id, now),
        )
        inserted.append({
            "id": item_id,
            "document_label": label,
            "is_mandatory": is_mandatory,
        })

    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="checklist_extracted",
        event_data={
            "nit_document_id": nit_document_id,
            "items_count": len(inserted),
            "prompt_hash": resp.prompt_hash,
            "cached": resp.cached,
        },
        actor=actor,
    )

    return inserted


def _find_source_page(criterion_text: str, pages: list) -> Optional[int]:
    """Find which page's raw_text contains a matching substring of the criterion."""
    if not criterion_text:
        return None
    # Use first 40 chars (likely unique) for matching
    needle = criterion_text[:40].lower().strip()
    if not needle:
        return None
    for p in pages:
        haystack = (p["raw_text"] or "").lower()
        if needle in haystack:
            return p["page_number"]
    return None
