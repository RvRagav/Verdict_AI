#!/usr/bin/env python
"""End-to-end pipeline test against real CRPF ATT tender data.

Uses the NIT + 4 bidder packs generated from the actual CRPF acceptance
letter for Armoured Troop Transporters (U.II-1410/2022-23-Proc-VII).

Expected outcome:
  - Ashok Leyland: ELIGIBLE (real winner — turnover 185-210 Cr, 4 orders)
  - Tata Advanced: ELIGIBLE (turnover 142-165 Cr, 3 orders)
  - Mahindra Armoured: NOT ELIGIBLE (turnover 98-125 Cr < 150 Cr threshold)
  - Kalyani Strategic: ELIGIBLE (turnover 160-190 Cr, 3 orders)
"""

import sys
import os
import uuid
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timezone
from backend.database.connection import init_db
from backend.pipeline.document_processing import process_document
from backend.pipeline.criterion_extraction import extract_criteria
from backend.core import audit_chain
from backend.services import bidder_service, evaluation_service


TEST_DB = "test_real_crpf.db"
NIT_PATH = "sample_docs/real_crpf/NIT_ATT_124_CRPF.pdf"
BIDDERS_DIR = "sample_docs/real_crpf/bidders"

BIDDERS = [
    ("Ashok Leyland Defence Systems Ltd", "AABCA1234L", "33AABCA1234L1ZP", "ashok_leyland"),
    ("Tata Advanced Systems Ltd", "AABCT5678M", "27AABCT5678M1ZQ", "tata_advanced"),
    ("Mahindra Armoured Vehicles Pvt Ltd", "AABCM9012N", "27AABCM9012N1ZR", "mahindra_armoured"),
    ("Kalyani Strategic Systems Ltd", "AABCK3456P", "27AABCK3456P1ZS", "kalyani"),
]


def main():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    conn = init_db(TEST_DB)
    now = datetime.now(timezone.utc).isoformat()

    # 1. Create tender
    tender_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO tenders (id, tender_number, title, department, category,
           estimated_cost, emd_amount, state, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tender_id, "U.II-1410/2022-23-Proc-VII",
         "Procurement of Armoured Troop Transporter (ATT) — 124 Nos",
         "CRPF", "Defence Vehicles", 20000000000, 400000000,
         "DOCUMENTS_PENDING", "officer-sharma", now, now),
    )
    audit_chain.append(conn, tender_id=tender_id, event_type="tender_created",
                       event_data={"title": "ATT 124"}, actor="officer-sharma")
    print(f"[1/6] Tender created: {tender_id[:12]}")

    # 2. Upload NIT
    print("[2/6] Uploading NIT...")
    nit = process_document(conn, tender_id=tender_id, bidder_id=None,
                           doc_type="nit", file_path=NIT_PATH)
    print(f"       NIT: {nit['page_count']} pages, OCR: {nit['avg_ocr_conf']}")

    # 3. Extract criteria
    print("[3/6] Extracting criteria (Bedrock call)...")
    criteria = extract_criteria(conn, tender_id=tender_id, nit_document_id=nit["id"])
    print(f"       {len(criteria)} criteria extracted:")
    for c in criteria:
        m = "M" if c["is_mandatory"] else "O"
        print(f"         [{m}] {c['criterion_type']:25s} {c['criterion_text'][:80]}")

    conn.execute("UPDATE criteria SET state = 'approved' WHERE tender_id = ?", (tender_id,))
    conn.execute("UPDATE tenders SET state = 'CRITERIA_APPROVED' WHERE id = ?", (tender_id,))
    print(f"       All {len(criteria)} approved.")

    # 4. Register bidders + upload docs
    print("[4/6] Registering 4 bidders + uploading docs...")
    bidder_ids = []
    for name, pan, gstin, folder in BIDDERS:
        bid = bidder_service.register_bidder(
            conn, tender_id=tender_id,
            company_name=name, pan_number=pan, gstin=gstin,
            actor="officer-sharma",
        )
        bidder_ids.append(bid["id"])
        bdir = os.path.join(BIDDERS_DIR, folder)
        doc_count = 0
        for fname in sorted(os.listdir(bdir)):
            if not fname.endswith(".pdf"):
                continue
            dtype = "certificate" if ("cert" in fname.lower() or "completion" in fname.lower()) else "bidder_submission"
            process_document(conn, tender_id=tender_id, bidder_id=bid["id"],
                             doc_type=dtype, file_path=os.path.join(bdir, fname))
            doc_count += 1
        print(f"       {name}: {doc_count} docs")

    conn.execute("UPDATE tenders SET state = 'EVALUATING' WHERE id = ?", (tender_id,))

    # 5. Run evaluation
    print("[5/6] Running evaluation (Bedrock calls — may take 5-10 min)...")
    n_criteria = len(criteria)
    n_bidders = len(BIDDERS)
    print(f"       {n_bidders} bidders × {n_criteria} criteria = {n_bidders * n_criteria} cells")

    summary = evaluation_service.run_evaluation(conn, tender_id=tender_id, actor="officer-sharma")
    print(f"       Done: {summary['total_cells']} cells, {summary.get('errors', 0)} errors")

    # 6. Results
    print("\n[6/6] ═══ RESULTS ═══")
    print(f"{'Bidder':<42s} {'PASS':>5s} {'FAIL':>5s} {'REVIEW':>7s} {'Verdict'}")
    print("─" * 75)
    for (name, _, _, _), bid_id in zip(BIDDERS, bidder_ids):
        rows = conn.execute(
            "SELECT verdict, COUNT(*) c FROM evaluations WHERE bidder_id = ? GROUP BY verdict",
            (bid_id,),
        ).fetchall()
        counts = {r[0]: r[1] for r in rows}
        total = sum(counts.values())
        p, f, r = counts.get("PASS", 0), counts.get("FAIL", 0), counts.get("REVIEW", 0)
        # Determine overall eligibility
        if f > total * 0.3:
            verdict = "NOT ELIGIBLE"
        elif p > total * 0.5:
            verdict = "ELIGIBLE"
        else:
            verdict = "NEEDS REVIEW"
        print(f"  {name:<40s} {p:>5d} {f:>5d} {r:>7d}   → {verdict}")

    print("\n═══ EXPECTED ═══")
    print("  Ashok Leyland: ELIGIBLE (real winner)")
    print("  Tata Advanced: ELIGIBLE")
    print("  Mahindra Armoured: NOT ELIGIBLE (turnover < 150 Cr, net worth < 50 Cr)")
    print("  Kalyani Strategic: ELIGIBLE")

    # Verify audit chain
    ok, err = audit_chain.verify(conn, tender_id)
    print(f"\nAudit chain: {'✓ VALID' if ok else '✗ BROKEN: ' + str(err)}")

    conn.close()
    print(f"\nTest DB: {TEST_DB}")


if __name__ == "__main__":
    main()
