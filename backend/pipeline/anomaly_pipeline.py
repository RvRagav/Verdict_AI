"""Anomaly pipeline (L5) — Smell Test driver + novel-anomaly LLM fallback.

Two layers:
1. Rule-based: cheap, deterministic, runs every time. Implemented in
   `core.smell_test`. Catches known patterns: round numbers, address
   collisions, duplicate documents, format mismatches, date proximity.

2. LLM-based: optional. Once per bidder. Asks Claude to surface
   *novel* anomalies the rules don't know about. Conservative — false
   positives erode officer trust. Cached like every other Bedrock call.

The driver dedupes (same flag_type + bidder + similar evidence_data
won't be inserted twice) and writes one audit event per flag.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.ai import bedrock_client
from backend.ai.prompts import ANOMALY_DETECTION
from backend.core import audit_chain
from backend.core.smell_test import run_smell_test

logger = logging.getLogger(__name__)


# Allowed flag_type values — must match the CHECK constraint in schema.py
ALLOWED_FLAG_TYPES = {
    "round_number",
    "address_collision",
    "date_proximity",
    "pan_format_mismatch",
    "gstin_format_mismatch",
    "parent_company_substitution",
    "duplicate_document",
    "suspicious_modification_date",
    "cross_tender_appearance",
    # Phase-12 cartel rules (CCI 2025 signals)
    "sequential_dd",
    "common_signatory",
    "cover_letter_overlap",
    # Statistical anomaly (research-grade)
    "benford_violation",
    "zscore_outlier",
    "bid_spread_anomaly",
    "metadata_cluster",
    "entity_resolution_match",
    "novel",
}


def detect_anomalies(
    conn,
    *,
    tender_id: str,
    bidder_id: str,
    use_llm: bool = True,
    actor: str = "system",
) -> list[dict]:
    """Run rule-based + LLM anomaly detection for one bidder.

    Returns the list of anomaly dicts inserted into anomaly_flags.
    """
    bidder = _load_bidder(conn, bidder_id)
    if not bidder:
        return []

    all_bidders = _load_all_bidders(conn, tender_id)
    tender_docs = _load_tender_documents(conn, tender_id)
    extracted_values = _load_extracted_numerics(conn, tender_id, bidder_id)

    # 1. Rule-based
    rule_flags = run_smell_test(
        bidder=bidder,
        tender_documents=tender_docs,
        all_bidders=all_bidders,
        extracted_values=extracted_values,
    )

    # 2. LLM novel-anomaly fallback (one call per bidder)
    llm_flags: list[dict] = []
    if use_llm:
        llm_flags = _run_llm_anomaly_check(
            conn,
            tender_id=tender_id,
            bidder=bidder,
            all_bidders=all_bidders,
            extracted_values=extracted_values,
        )

    # 3. Statistical anomaly analysis (Benford, Z-score, CV, metadata, entity resolution)
    from backend.core.statistical_anomaly import run_statistical_analysis
    stat_flags = _run_statistical_analysis_safe(
        conn, tender_id=tender_id, all_bidders=all_bidders, tender_docs=tender_docs,
    )

    # Merge + dedupe + insert
    inserted: list[dict] = []
    seen_keys = _existing_flag_keys(conn, tender_id, bidder_id)
    now = datetime.now(timezone.utc).isoformat()

    for flag in rule_flags + llm_flags + stat_flags:
        flag_type = flag.get("flag_type")
        if flag_type not in ALLOWED_FLAG_TYPES:
            flag_type = "novel"
        key = _flag_key(flag_type, flag.get("evidence_data") or {})
        if key in seen_keys:
            continue
        seen_keys.add(key)

        # Filter out cross-bidder flags that don't actually involve this bidder
        if not _flag_involves_bidder(flag, bidder_id):
            continue

        flag_id = str(uuid.uuid4())
        severity = flag.get("severity", "medium")
        if severity not in ("low", "medium", "high"):
            severity = "medium"

        conn.execute(
            """INSERT INTO anomaly_flags
               (id, tender_id, bidder_id, evaluation_id,
                flag_type, severity, message, evidence_data,
                state, created_at)
               VALUES (?, ?, ?, NULL, ?, ?, ?, ?, 'open', ?)""",
            (
                flag_id, tender_id, bidder_id,
                flag_type, severity,
                flag.get("message", ""),
                json.dumps(flag.get("evidence_data") or {}),
                now,
            ),
        )
        audit_chain.append(
            conn,
            tender_id=tender_id,
            event_type="anomaly_flagged",
            event_data={
                "anomaly_id": flag_id,
                "bidder_id": bidder_id,
                "flag_type": flag_type,
                "severity": severity,
            },
            actor=actor,
        )
        inserted.append({
            "id": flag_id,
            "flag_type": flag_type,
            "severity": severity,
            "message": flag.get("message", ""),
            "evidence_data": flag.get("evidence_data") or {},
        })

    return inserted


# ─── LLM novel-anomaly call ────────────────────────────────────────────


def _run_llm_anomaly_check(
    conn,
    *,
    tender_id: str,
    bidder: dict,
    all_bidders: list[dict],
    extracted_values: list[dict],
) -> list[dict]:
    """One Bedrock call per bidder. Returns LLM-flagged anomalies."""
    bidder_summary = _summarise_bidder(bidder, extracted_values)
    other_bidders_summary = "\n".join(
        f"- {b.get('company_name', '?')} (PAN: {b.get('pan_number', '?')})"
        for b in all_bidders if b.get("id") != bidder.get("id")
    ) or "(none)"

    user_prompt = ANOMALY_DETECTION.render_user(
        bidder_name=bidder.get("company_name", "Unknown"),
        bidder_summary=bidder_summary,
        other_bidders=other_bidders_summary,
    )
    resp = bedrock_client.invoke(
        invocation_type="anomaly_detection",
        system=ANOMALY_DETECTION.system,
        user=user_prompt,
        prompt_version=ANOMALY_DETECTION.version,
        structured=True,
        schema_hint=ANOMALY_DETECTION.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )

    if resp.error or not resp.data:
        if resp.error:
            logger.warning("Anomaly LLM call failed: %s", resp.error)
        return []

    data = resp.data if isinstance(resp.data, dict) else {}
    flags = data.get("anomalies") or []
    return [f for f in flags if isinstance(f, dict)]


def _summarise_bidder(bidder: dict, extracted_values: list[dict]) -> str:
    parts = [
        f"Company: {bidder.get('company_name', '?')}",
        f"PAN: {bidder.get('pan_number') or '(not provided)'}",
        f"GSTIN: {bidder.get('gstin') or '(not provided)'}",
    ]
    if extracted_values:
        parts.append("Extracted figures:")
        for ev in extracted_values[:10]:
            parts.append(f"  - {ev.get('label', 'figure')}: {ev.get('value')}")
    return "\n".join(parts)


# ─── Loaders ───────────────────────────────────────────────────────────


def _load_bidder(conn, bidder_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT id, company_name, pan_number, gstin, cin, udyam_number, "
        "       contact_email, metadata "
        "FROM bidders WHERE id = ? AND deleted_at IS NULL",
        (bidder_id,),
    ).fetchone()
    if not row:
        return None
    out = dict(row)
    if out.get("metadata"):
        try:
            md = json.loads(out["metadata"])
            if isinstance(md, dict):
                out["address"] = md.get("address")
        except json.JSONDecodeError:
            pass
    return out


def _load_all_bidders(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, company_name, pan_number, gstin, metadata "
        "FROM bidders WHERE tender_id = ? AND deleted_at IS NULL",
        (tender_id,),
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        if d.get("metadata"):
            try:
                md = json.loads(d["metadata"])
                if isinstance(md, dict):
                    d["address"] = md.get("address")
            except json.JSONDecodeError:
                pass
        out.append(d)
    return out


def _load_tender_documents(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, bidder_id, sha256_hash, filename, uploaded_at, metadata "
        "FROM documents WHERE tender_id = ? AND deleted_at IS NULL "
        "AND processing_state = 'complete'",
        (tender_id,),
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        d["modification_date"] = d.get("uploaded_at")
        if d.get("metadata"):
            try:
                md = json.loads(d["metadata"])
                if isinstance(md, dict) and md.get("modification_date"):
                    d["modification_date"] = md["modification_date"]
            except json.JSONDecodeError:
                pass
        out.append(d)
    return out


def _load_extracted_numerics(conn, tender_id: str, bidder_id: str) -> list[dict]:
    """Pull numeric values previously extracted for this bidder.

    These come from `evaluations.extracted_value` JSON for criterion_type
    = numeric_threshold. If nothing has been evaluated yet, returns [].
    """
    rows = conn.execute(
        """SELECT e.extracted_value, c.criterion_text
           FROM evaluations e
           JOIN criteria c ON c.id = e.criterion_id
           WHERE e.tender_id = ? AND e.bidder_id = ?
             AND c.criterion_type = 'numeric_threshold'
             AND e.extracted_value IS NOT NULL""",
        (tender_id, bidder_id),
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        try:
            v = json.loads(r["extracted_value"])
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(v, dict) and v.get("rupees") is not None:
            out.append({"value": float(v["rupees"]), "label": (r["criterion_text"] or "")[:60]})
    return out


# ─── Dedup helpers ─────────────────────────────────────────────────────


def _existing_flag_keys(conn, tender_id: str, bidder_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT flag_type, evidence_data FROM anomaly_flags "
        "WHERE tender_id = ? AND bidder_id = ?",
        (tender_id, bidder_id),
    ).fetchall()
    keys = set()
    for r in rows:
        try:
            ev = json.loads(r["evidence_data"]) if r["evidence_data"] else {}
        except json.JSONDecodeError:
            ev = {}
        keys.add(_flag_key(r["flag_type"], ev))
    return keys


def _flag_key(flag_type: str, evidence_data: dict) -> str:
    """Stable key for dedup. Rule + LLM agreement collapse to one row.

    For format/identity flags we key on the *normalised identifier*
    (PAN, GSTIN, address, hash) so multiple detectors finding the
    same fact about the same entity produce one row, not many.
    """
    ev = evidence_data or {}
    if flag_type == "address_collision":
        ids = ev.get("bidder_ids") or []
        # Sort so any pair is the same key regardless of order
        return f"address_collision::{tuple(sorted(ids))}"
    if flag_type == "duplicate_document":
        return f"duplicate_document::{ev.get('sha256') or ev.get('sha256_hash')}"
    if flag_type == "pan_format_mismatch":
        return f"pan_format_mismatch::{(ev.get('pan') or '').upper()}"
    if flag_type == "gstin_format_mismatch":
        return f"gstin_format_mismatch::{(ev.get('gstin') or '').upper()}"
    if flag_type == "round_number":
        return f"round_number::{ev.get('label', '')}::{ev.get('value', '')}"
    if flag_type == "sequential_dd":
        ids = ev.get("bidder_ids") or []
        return f"sequential_dd::{tuple(sorted(ids))}"
    if flag_type == "common_signatory":
        return f"common_signatory::{(ev.get('signatory_name') or '').lower()}"
    if flag_type == "cover_letter_overlap":
        ids = ev.get("bidder_ids") or []
        return f"cover_letter_overlap::{tuple(sorted(ids))}"
    if flag_type == "benford_violation":
        return f"benford_violation::{ev.get('n_values', 0)}"
    if flag_type == "zscore_outlier":
        return f"zscore_outlier::{ev.get('bidder_id', '')}::{ev.get('z_score', '')}"
    if flag_type == "bid_spread_anomaly":
        return f"bid_spread_anomaly::{ev.get('signal', '')}::{ev.get('n_bidders', '')}"
    if flag_type == "metadata_cluster":
        return f"metadata_cluster::{(ev.get('producer') or '')[:40]}"
    if flag_type == "entity_resolution_match":
        ids = ev.get("bidder_ids") or []
        return f"entity_resolution::{tuple(sorted(ids))}"
    canonical = json.dumps(ev or {}, sort_keys=True, default=str)[:200]
    return f"{flag_type}::{canonical}"


def _flag_involves_bidder(flag: dict, bidder_id: str) -> bool:
    """Cross-bidder flags from smell_test return *all* affected bidders.
    We only want to insert a row for a flag that involves this bidder."""
    ev = flag.get("evidence_data") or {}
    bidder_ids = ev.get("bidder_ids")
    if isinstance(bidder_ids, list) and bidder_ids:
        return bidder_id in bidder_ids
    return True


# ─── Statistical analysis wrapper ───────────────────────────────────────


def _run_statistical_analysis_safe(
    conn,
    *,
    tender_id: str,
    all_bidders: list[dict],
    tender_docs: list[dict],
) -> list[dict]:
    """Run statistical anomaly analysis. Catches exceptions so it never
    blocks the main pipeline.
    """
    try:
        from backend.core.statistical_anomaly import run_statistical_analysis

        # Collect all numeric values per criterion for Z-score + CV
        numeric_by_criterion: dict[str, list[dict]] = {}
        all_figures: list[float] = []

        evaluations = conn.execute(
            "SELECT e.bidder_id, e.criterion_id, e.extracted_value, "
            "       b.company_name, c.criterion_text "
            "FROM evaluations e "
            "JOIN bidders b ON b.id = e.bidder_id "
            "JOIN criteria c ON c.id = e.criterion_id "
            "WHERE e.tender_id = ? AND c.criterion_type = 'numeric_threshold' "
            "AND e.extracted_value IS NOT NULL",
            (tender_id,),
        ).fetchall()

        for ev in evaluations:
            import json as _json
            try:
                val_data = _json.loads(ev["extracted_value"]) if isinstance(ev["extracted_value"], str) else ev["extracted_value"]
            except (_json.JSONDecodeError, TypeError):
                continue

            # Extract the primary numeric value
            figures = val_data.get("figures") if isinstance(val_data, dict) else None
            if figures and isinstance(figures, list):
                for fig in figures:
                    rupees = fig.get("rupees") if isinstance(fig, dict) else None
                    if rupees and isinstance(rupees, (int, float)) and rupees > 0:
                        all_figures.append(float(rupees))
                        crit_id = ev["criterion_id"]
                        if crit_id not in numeric_by_criterion:
                            numeric_by_criterion[crit_id] = []
                        numeric_by_criterion[crit_id].append({
                            "bidder_id": ev["bidder_id"],
                            "company_name": ev["company_name"],
                            "value": float(rupees),
                            "criterion_text": ev["criterion_text"],
                        })
            elif isinstance(val_data, dict) and val_data.get("rupees"):
                rupees = val_data["rupees"]
                if isinstance(rupees, (int, float)) and rupees > 0:
                    all_figures.append(float(rupees))
                    crit_id = ev["criterion_id"]
                    if crit_id not in numeric_by_criterion:
                        numeric_by_criterion[crit_id] = []
                    numeric_by_criterion[crit_id].append({
                        "bidder_id": ev["bidder_id"],
                        "company_name": ev["company_name"],
                        "value": float(rupees),
                        "criterion_text": ev["criterion_text"],
                    })

        return run_statistical_analysis(
            all_bidders=all_bidders,
            numeric_values_by_criterion=numeric_by_criterion,
            all_financial_figures=all_figures,
            tender_documents=tender_docs,
        )
    except Exception as exc:
        logger.warning("Statistical analysis failed (non-fatal): %s", exc)
        return []
