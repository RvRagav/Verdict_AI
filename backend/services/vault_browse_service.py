"""File Vault — read-side service for the per-tender file browser.

Different from `vault_service` (which builds the sealed Defence Vault
ZIP). This one answers: "Show me every document in this tender,
grouped, sortable, click-to-view."
"""

from __future__ import annotations

from typing import Optional


def list_tender_files(conn, tender_id: str) -> dict:
    """Return all files attached to a tender, grouped by role.

    Output:
      {
        "tender_files":   [...],   # NIT, corrigenda, attachments
        "by_bidder": [
          {
             "bidder": {...},
             "files": [...],
          },
          ...
        ],
        "totals": {"docs": int, "pages": int, "size_bytes_proxy": int}
      }
    """
    tender_docs = [dict(r) for r in conn.execute(
        """SELECT d.id, d.doc_type, d.filename, d.sha256_hash, d.page_count,
                  d.avg_ocr_conf, d.processing_state, d.uploaded_at,
                  d.bidder_id
           FROM documents d
           WHERE d.tender_id = ? AND d.deleted_at IS NULL
           ORDER BY d.uploaded_at""",
        (tender_id,),
    ).fetchall()]

    bidders = [dict(r) for r in conn.execute(
        """SELECT id, company_name, state, debarment_state, pan_number,
                  gstin, emd_amount, bid_validity_until
           FROM bidders WHERE tender_id = ? AND deleted_at IS NULL""",
        (tender_id,),
    ).fetchall()]

    bidder_index: dict[str, list[dict]] = {b["id"]: [] for b in bidders}
    tender_level: list[dict] = []
    for d in tender_docs:
        if d.get("bidder_id"):
            bidder_index.setdefault(d["bidder_id"], []).append(d)
        else:
            tender_level.append(d)

    grouped = []
    for b in bidders:
        files = bidder_index.get(b["id"], [])
        grouped.append({
            "bidder": b,
            "file_count": len(files),
            "page_count_total": sum(f.get("page_count") or 0 for f in files),
            "files": files,
        })

    totals = {
        "docs": len(tender_docs),
        "pages": sum(d.get("page_count") or 0 for d in tender_docs),
        "complete": sum(1 for d in tender_docs if d.get("processing_state") == "complete"),
    }
    return {
        "tender_files": tender_level,
        "by_bidder": grouped,
        "totals": totals,
    }
