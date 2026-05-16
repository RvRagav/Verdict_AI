"""Bidder registration + debarment placeholder.

A bidder is a company submitting against a tender. Registration is
lightweight — name + identity numbers (PAN/GSTIN/CIN/Udyam). The
debarment check is a stubbed placeholder for the demo; in production
this would integrate with the official debarment registry.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.core import audit_chain


def register_bidder(
    conn,
    *,
    tender_id: str,
    company_name: str,
    pan_number: Optional[str] = None,
    gstin: Optional[str] = None,
    cin: Optional[str] = None,
    udyam_number: Optional[str] = None,
    contact_email: Optional[str] = None,
    address: Optional[str] = None,
    emd_amount: Optional[int] = None,
    emd_instrument: Optional[str] = None,
    emd_instrument_no: Optional[str] = None,
    emd_validity_date: Optional[str] = None,
    emd_exempt: bool = False,
    emd_exempt_reason: Optional[str] = None,
    bid_validity_until: Optional[str] = None,
    actor: str,
) -> dict:
    """Register a new bidder against a tender. Returns the bidder dict."""
    bidder_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    metadata = {}
    if address:
        metadata["address"] = address

    conn.execute(
        """INSERT INTO bidders
           (id, tender_id, company_name, pan_number, gstin, cin,
            udyam_number, contact_email, state, debarment_state,
            metadata, registered_address,
            emd_amount, emd_instrument, emd_instrument_no, emd_validity_date,
            emd_exempt, emd_exempt_reason, bid_validity_until,
            created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'unchecked',
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            bidder_id, tender_id, company_name, pan_number, gstin, cin,
            udyam_number, contact_email,
            json.dumps(metadata) if metadata else None,
            address,
            emd_amount, emd_instrument, emd_instrument_no, emd_validity_date,
            1 if emd_exempt else 0, emd_exempt_reason, bid_validity_until,
            now,
        ),
    )
    audit_chain.append(
        conn,
        tender_id=tender_id,
        event_type="bidder_registered",
        event_data={
            "bidder_id": bidder_id,
            "company_name": company_name,
            "pan_number": pan_number,
            "gstin": gstin,
            "emd_amount": emd_amount,
            "emd_exempt": emd_exempt,
        },
        actor=actor,
    )
    if emd_amount is not None or emd_exempt:
        audit_chain.append(
            conn,
            tender_id=tender_id,
            event_type="bidder_emd_recorded",
            event_data={
                "bidder_id": bidder_id,
                "emd_amount": emd_amount,
                "emd_instrument": emd_instrument,
                "emd_instrument_no": emd_instrument_no,
                "emd_validity_date": emd_validity_date,
                "emd_exempt": emd_exempt,
            },
            actor=actor,
        )
    return get_bidder(conn, bidder_id)


def get_bidder(conn, bidder_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM bidders WHERE id = ? AND deleted_at IS NULL",
        (bidder_id,),
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def list_bidders(conn, tender_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM bidders WHERE tender_id = ? AND deleted_at IS NULL "
        "ORDER BY created_at ASC",
        (tender_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def check_debarment(
    conn,
    *,
    bidder_id: str,
    actor: str,
) -> dict:
    """Real debarment check against the local registry.

    Looks up by PAN, GSTIN, and normalised company name. Updates
    debarment_state to one of:
      - clear            no match
      - flagged          some match (officer must confirm)
      - confirmed_debarred  high-confidence PAN/GSTIN match
    Audit event records the matches found.
    """
    bidder = get_bidder(conn, bidder_id)
    if not bidder:
        raise ValueError(f"Bidder not found: {bidder_id}")

    from backend.services import debarment_service
    result = debarment_service.check_bidder(
        conn,
        pan_number=bidder.get("pan_number"),
        gstin=bidder.get("gstin"),
        company_name=bidder.get("company_name"),
    )

    if not result["flagged"]:
        new_state = "clear"
    elif result["confidence"] == "high":
        new_state = "confirmed_debarred"
    else:
        new_state = "flagged"

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE bidders SET debarment_state = ?, debarment_checked_at = ? "
        "WHERE id = ?",
        (new_state, now, bidder_id),
    )
    audit_chain.append(
        conn,
        tender_id=bidder["tender_id"],
        event_type="bidder_debarment_checked",
        event_data={
            "bidder_id": bidder_id,
            "result": new_state,
            "match_count": len(result["matches"]),
            "match_summary": [
                {"source": m["source"], "match_type": m["match_type"],
                 "reason": m["reason"]}
                for m in result["matches"][:5]
            ],
        },
        actor=actor,
    )
    return get_bidder(conn, bidder_id)


def update_state(
    conn,
    *,
    bidder_id: str,
    state: str,
    actor: str,
) -> dict:
    """Move a bidder to a new state (preliminary_passed/_failed/evaluated/excluded)."""
    valid = {"pending", "preliminary_passed", "preliminary_failed",
             "evaluated", "excluded"}
    if state not in valid:
        raise ValueError(f"Invalid bidder state: {state}")
    bidder = get_bidder(conn, bidder_id)
    if not bidder:
        raise ValueError(f"Bidder not found: {bidder_id}")
    conn.execute("UPDATE bidders SET state = ? WHERE id = ?", (state, bidder_id))

    if state == "excluded":
        audit_chain.append(
            conn,
            tender_id=bidder["tender_id"],
            event_type="bidder_excluded",
            event_data={"bidder_id": bidder_id},
            actor=actor,
        )

    return get_bidder(conn, bidder_id)


def _row_to_dict(row) -> dict:
    d = dict(row)
    if d.get("metadata"):
        try:
            md = json.loads(d["metadata"])
            d["metadata"] = md
            if isinstance(md, dict):
                d["address"] = md.get("address")
        except (json.JSONDecodeError, TypeError):
            pass
    return d
