"""Pre-Mortem Brief generator + cache.

Composes the tender snapshot from existing tables, calls Bedrock with a
focused prompt, caches the result. Cache invalidates on `pipeline_signature`
or any modification to underlying data — for v1 we simply regenerate on
demand and store the latest.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.ai import bedrock_client
from backend.ai.brief_prompts import BRIEF_PROMPT
from backend.ai.prompts import pipeline_signature
from backend.core import audit_chain


def get_or_generate(
    conn,
    *,
    tender_id: str,
    actor: str = "system",
    force: bool = False,
) -> dict:
    """Return the latest brief, generating one if missing or forced."""
    if not force:
        row = conn.execute(
            "SELECT * FROM tender_briefs WHERE tender_id = ?",
            (tender_id,),
        ).fetchone()
        if row:
            return _to_dict(row)
    return generate(conn, tender_id=tender_id, actor=actor)


def generate(
    conn,
    *,
    tender_id: str,
    actor: str = "system",
) -> dict:
    """Build snapshot, call Bedrock, store + return brief."""
    snapshot = _build_snapshot(conn, tender_id)
    user_prompt = BRIEF_PROMPT.render_user(
        snapshot_json=json.dumps(snapshot, ensure_ascii=False, default=str)[:24_000],
    )
    resp = bedrock_client.invoke(
        invocation_type="tender_brief",
        system=BRIEF_PROMPT.system,
        user=user_prompt,
        prompt_version=BRIEF_PROMPT.version,
        structured=True,
        schema_hint=BRIEF_PROMPT.schema_hint,
        tender_id=tender_id,
        conn=conn,
    )
    if resp.error or not isinstance(resp.data, dict):
        # Fall back to a deterministic mini-brief built locally
        brief = _local_fallback_brief(snapshot)
    else:
        brief = resp.data

    now = datetime.now(timezone.utc).isoformat()
    sig = pipeline_signature()

    # Upsert (one brief per tender)
    existing = conn.execute(
        "SELECT id FROM tender_briefs WHERE tender_id = ?",
        (tender_id,),
    ).fetchone()
    brief_id = existing["id"] if existing else str(uuid.uuid4())
    if existing:
        conn.execute(
            "UPDATE tender_briefs SET brief_json = ?, pipeline_signature_hash = ?, "
            "generated_at = ? WHERE id = ?",
            (json.dumps(brief), sig, now, brief_id),
        )
    else:
        conn.execute(
            """INSERT INTO tender_briefs
               (id, tender_id, brief_json, pipeline_signature_hash, generated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (brief_id, tender_id, json.dumps(brief), sig, now),
        )

    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="brief_generated",
        event_data={
            "brief_id": brief_id,
            "cached": resp.cached if not resp.error else False,
            "fallback": bool(resp.error),
        },
        actor=actor,
    )
    return {
        "id": brief_id,
        "tender_id": tender_id,
        "brief": brief,
        "pipeline_signature_hash": sig,
        "generated_at": now,
    }


# ─── Snapshot composition ────────────────────────────────────────────


def _build_snapshot(conn, tender_id: str) -> dict:
    """Compose the tender state as one JSON blob the prompt understands."""
    tender = dict(conn.execute(
        "SELECT * FROM tenders WHERE id = ?", (tender_id,),
    ).fetchone() or {})

    bidders = [dict(r) for r in conn.execute(
        "SELECT id, company_name, state, debarment_state, bid_validity_until, "
        "       emd_amount, emd_exempt FROM bidders "
        "WHERE tender_id = ? AND deleted_at IS NULL",
        (tender_id,),
    ).fetchall()]

    criteria = [dict(r) for r in conn.execute(
        "SELECT id, criterion_text, criterion_type, is_mandatory, "
        "       gfr_rule_number, current_version, last_amended_by "
        "FROM criteria WHERE tender_id = ?",
        (tender_id,),
    ).fetchall()]

    # verdict + confidence per (bidder, criterion)
    cells = [dict(r) for r in conn.execute(
        """SELECT bidder_id, criterion_id, verdict, confidence, route, state,
                  routing_reason
           FROM evaluations WHERE tender_id = ?""",
        (tender_id,),
    ).fetchall()]

    anomalies = [dict(r) for r in conn.execute(
        """SELECT id, bidder_id, flag_type, severity, message
           FROM anomaly_flags WHERE tender_id = ? AND state = 'open'
           ORDER BY CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
           LIMIT 30""",
        (tender_id,),
    ).fetchall()]

    corrigenda = [dict(r) for r in conn.execute(
        "SELECT id, sequence_number, title, summary, state, issued_date "
        "FROM corrigenda WHERE tender_id = ? ORDER BY sequence_number",
        (tender_id,),
    ).fetchall()]

    return {
        "tender": {
            "tender_number": tender.get("tender_number"),
            "title": tender.get("title"),
            "department": tender.get("department"),
            "category": tender.get("category"),
            "state": tender.get("state"),
            "bid_close_date": tender.get("bid_close_date"),
        },
        "bidders": bidders,
        "criteria": criteria,
        "evaluations": cells,
        "open_anomalies": anomalies,
        "corrigenda": corrigenda,
    }


# ─── Deterministic fallback (no Bedrock needed) ────────────────────


def _local_fallback_brief(snap: dict) -> dict:
    bidders = snap.get("bidders", [])
    cells = snap.get("evaluations", [])
    anomalies = snap.get("open_anomalies", [])

    by_bidder: dict[str, dict] = {}
    for b in bidders:
        by_bidder[b["id"]] = {
            "name": b["company_name"], "pass": 0, "fail": 0, "review": 0,
        }
    for c in cells:
        bid = by_bidder.get(c["bidder_id"])
        if not bid:
            continue
        if c["verdict"] == "PASS":   bid["pass"] += 1
        elif c["verdict"] == "FAIL": bid["fail"] += 1
        else:                         bid["review"] += 1

    strongest = max(by_bidder.values(),
                    key=lambda b: (b["pass"], -b["fail"]),
                    default=None)
    weakest = min(by_bidder.values(),
                  key=lambda b: (b["pass"], -b["fail"]),
                  default=None)

    hitl = [
        {"label": f"{by_bidder.get(c['bidder_id'], {}).get('name', '?')}: {c['routing_reason']}",
         "evaluation_id": c.get("evaluation_id"),
         "why": c.get("routing_reason") or ""}
        for c in cells if c["route"] != "auto_commit"
    ][:8]

    risks = [
        {"severity": a["severity"], "label": a["flag_type"].replace("_", " "),
         "evidence": a["message"]}
        for a in anomalies if a["severity"] in ("medium", "high")
    ][:6]

    return {
        "lay_of_land": (
            f"{len(bidders)} bidders · {len(snap.get('criteria', []))} criteria · "
            f"{len([c for c in cells if c['route'] != 'auto_commit'])} need review."
        ),
        "strongest_bidder": (
            {"name": strongest["name"],
             "reason": f"{strongest['pass']} likely-PASS / {strongest['fail']} fail"}
            if strongest else None
        ),
        "weakest_bidder": (
            {"name": weakest["name"],
             "reason": f"{weakest['pass']} likely-PASS / {weakest['fail']} fail"}
            if weakest else None
        ),
        "hitl_items": hitl,
        "premortem_risks": risks,
    }


def _to_dict(row) -> dict:
    d = dict(row)
    try:
        d["brief"] = json.loads(d.pop("brief_json"))
    except (json.JSONDecodeError, TypeError):
        d["brief"] = None
    return d
