"""Run external-source verifiers across a tender's bidders.

Each (bidder, verifier) pair produces one VerificationResult that is
persisted to `verification_results` and audited via the chain.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.core import audit_chain
from backend.services import tender_service
from backend.verifiers import get_registry


def run_for_bidder(
    conn,
    *,
    tender_id: str,
    bidder_id: str,
    actor: str = "system",
) -> list[dict]:
    """Run every applicable verifier on one bidder. Persist + audit each."""
    bidder = conn.execute(
        "SELECT * FROM bidders WHERE id = ?", (bidder_id,)
    ).fetchone()
    if not bidder:
        raise ValueError(f"Bidder not found: {bidder_id}")
    bidder = dict(bidder)
    tender = tender_service.get_tender(conn, tender_id)

    # Pull CA cert metadata from any uploaded certificate doc (best-effort)
    ca_meta = _ca_metadata_from_docs(conn, tender_id, bidder_id)

    claim_base = {
        "company_name": bidder.get("company_name"),
        "constitution": bidder.get("constitution") or "Private Limited",
        "pan_number": bidder.get("pan_number"),
        "gstin": bidder.get("gstin"),
        "cin": bidder.get("cin"),
        "udyam": bidder.get("udyam_number"),
        "bid_submission_date": (tender or {}).get("bid_close_date"),
        "valid_until": bidder.get("emd_validity_date"),
        "legal_name": bidder.get("company_name"),
        "frn": ca_meta.get("frn"),
        "udin": ca_meta.get("udin"),
        "ca_membership": ca_meta.get("ca_membership"),
        "firm_name": ca_meta.get("firm_name"),
    }

    registry = get_registry(conn)
    out: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for vname, verifier in registry.all().items():
        result = verifier.verify(claim_base)
        rid = str(uuid.uuid4())
        snapshot_str = json.dumps(result.source_snapshot, default=str)
        snapshot_sha = result.snapshot_sha256()

        # Replace any previous result for this (bidder, verifier) — keep the
        # most recent one as the canonical (and let the audit log carry history).
        conn.execute(
            "DELETE FROM verification_results WHERE bidder_id = ? AND verifier_name = ?",
            (bidder_id, vname),
        )
        conn.execute(
            """INSERT INTO verification_results
               (id, tender_id, bidder_id, verifier_name, status, confidence,
                source_url, verified_via, source_snapshot, snapshot_sha256,
                notes, verified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rid, tender_id, bidder_id, vname, result.status,
             result.confidence, result.source_url, result.verified_via,
             snapshot_str, snapshot_sha, result.notes, result.verified_at),
        )
        audit_chain.append(
            conn,
            tender_id=tender_id,
            event_type="verification_run",
            event_data={
                "verification_id": rid,
                "bidder_id": bidder_id,
                "verifier_name": vname,
                "status": result.status,
                "verified_via": result.verified_via,
                "snapshot_sha256": snapshot_sha,
            },
            actor=actor,
        )
        out.append({
            "id": rid, "verifier_name": vname,
            "status": result.status, "confidence": result.confidence,
            "verified_via": result.verified_via,
            "source_url": result.source_url, "notes": result.notes,
            "verified_at": result.verified_at,
            "source_snapshot": result.source_snapshot,
            "snapshot_sha256": snapshot_sha,
        })
    return out


def run_for_tender(
    conn, *, tender_id: str, actor: str = "system",
) -> dict:
    """Run all verifiers for every bidder in the tender."""
    bidders = [dict(r) for r in conn.execute(
        "SELECT id, company_name FROM bidders "
        "WHERE tender_id = ? AND deleted_at IS NULL",
        (tender_id,),
    ).fetchall()]
    summary = {"bidder_count": len(bidders), "verifications": []}
    for b in bidders:
        results = run_for_bidder(conn, tender_id=tender_id,
                                 bidder_id=b["id"], actor=actor)
        summary["verifications"].append({
            "bidder_id": b["id"],
            "company_name": b["company_name"],
            "results": results,
        })
    return summary


def list_for_tender(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT vr.*, b.company_name
           FROM verification_results vr
           JOIN bidders b ON b.id = vr.bidder_id
           WHERE vr.tender_id = ?
           ORDER BY b.company_name, vr.verifier_name""",
        (tender_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["source_snapshot"] = json.loads(d["source_snapshot"])
        except (json.JSONDecodeError, TypeError):
            pass
        out.append(d)
    return out


def matrix(conn, tender_id: str) -> dict:
    """Build the bidder × verifier matrix for the Verifiers tab."""
    rows = list_for_tender(conn, tender_id)
    bidders = [dict(r) for r in conn.execute(
        "SELECT id, company_name FROM bidders "
        "WHERE tender_id = ? AND deleted_at IS NULL",
        (tender_id,),
    ).fetchall()]
    verifier_order = ["gst", "pan", "udin", "frn", "udyam", "mca", "debarment"]

    cells: dict[tuple[str, str], dict] = {}
    for r in rows:
        cells[(r["bidder_id"], r["verifier_name"])] = r

    return {
        "bidders": bidders,
        "verifiers": verifier_order,
        "cells": [
            {
                "bidder_id": b["id"],
                "company_name": b["company_name"],
                "verifier_name": v,
                "result": cells.get((b["id"], v)),
            }
            for b in bidders
            for v in verifier_order
        ],
    }


# ─── Helpers ──────────────────────────────────────────────────


def _ca_metadata_from_docs(conn, tender_id: str, bidder_id: str) -> dict:
    """Best-effort: pull FRN, UDIN, CA membership from any uploaded
    certificate doc text. We don't fail if it's not there — the
    verifier surfaces the gap.
    """
    import re
    rows = conn.execute(
        """SELECT p.raw_text
           FROM documents d
           JOIN pages p ON p.document_id = d.id
           WHERE d.tender_id = ? AND d.bidder_id = ?
             AND d.doc_type = 'certificate'
             AND d.deleted_at IS NULL""",
        (tender_id, bidder_id),
    ).fetchall()
    text = "\n".join((r["raw_text"] or "") for r in rows)

    out = {}
    m = re.search(r"FRN[:\s]+([0-9]{6}[A-Z])", text)
    if m: out["frn"] = m.group(1)
    m = re.search(r"UDIN[:\s]+([A-Z0-9\-]{12,20})", text)
    if m: out["udin"] = m.group(1)
    m = re.search(r"M\.?\s*No\.?[:\s]+([0-9]{4,7})", text, re.IGNORECASE)
    if m: out["ca_membership"] = m.group(1)
    m = re.search(r"M/s\s+([A-Z][A-Za-z &\.,]+(?:Associates|Co\.|& Co|& Associates|Partners))", text)
    if m: out["firm_name"] = m.group(1).strip()
    return out
