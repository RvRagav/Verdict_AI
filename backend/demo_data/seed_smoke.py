"""End-to-end smoke test that proves the whole pipeline works.

Creates a fresh DB at smoke_test.db, then runs:
    1. Create tender
    2. Upload NIT  → L1
    3. Extract criteria + checklist  → L2
    4. Approve criteria → state advance
    5. Register 3 bidders, upload their submissions → L1
    6. Auto-match checklist → finalize preliminary
    7. Run evaluation → L3 + L4 + L5 + L7 across (3 × N) cells
    8. Capture a replay snapshot
    9. Generate the TEC report
   10. Verify the audit chain

If LLM_DISABLED=1, the smoke test still runs but skips Bedrock calls
(qualitative criteria → REVIEW, dissent absent). Cached LLM results
make subsequent runs fast.
"""

from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path

# Ensure repo root on path before anything else
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

DEMO_DIR = Path(__file__).resolve().parent
NIT_PATH = DEMO_DIR / "sample_nit_crpf.pdf"
GOOD_BIDDER_PATH = DEMO_DIR / "sample_bidder_good.pdf"
MISMATCH_BIDDER_PATH = DEMO_DIR / "sample_bidder_mismatch.pdf"
WEAK_BIDDER_PATH = DEMO_DIR / "sample_bidder_weak.pdf"
CA_CERT_PATH = DEMO_DIR / "sample_ca_certificate.pdf"
CA_CERT_STAMPED_PATH = DEMO_DIR / "sample_ca_certificate_stamp.pdf"
CA_CERT_PHOTO_PATH = DEMO_DIR / "sample_ca_certificate_scan.jpg"


def main() -> int:
    # Use a separate test DB so the live DB is untouched
    test_db = "smoke_test.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    for d in ("smoke_uploads", "smoke_pages", "smoke_reports"):
        if os.path.exists(d):
            shutil.rmtree(d)

    os.environ["DB_PATH"] = test_db
    os.environ["UPLOAD_DIR"] = "smoke_uploads"
    os.environ["PAGES_DIR"] = "smoke_pages"
    os.environ["REPORTS_DIR"] = "smoke_reports"

    # Force a fresh import after env vars set
    for mod in list(sys.modules):
        if mod.startswith("backend."):
            del sys.modules[mod]

    from backend.database.connection import init_db
    from backend.services import (
        bidder_service, checklist_service, criteria_service,
        document_service, evaluation_service, replay_service,
        report_service, tender_service,
    )
    from backend.core import audit_chain

    print("=" * 70)
    print("VerdictAI smoke test")
    print("=" * 70)

    conn = init_db(test_db)

    # 1. Create tender
    print("\n[1/10] Create tender …")
    tender = tender_service.create_tender(
        conn,
        tender_number="CRPF/SMOKE/2026/001",
        title="Supply of Patrol Vehicles — Smoke Test",
        department="CRPF",
        category="Goods",
        estimated_cost=150_000_000,
        emd_amount=1_500_000,
        bid_open_date="2026-04-01",
        bid_close_date="2026-04-30",
        created_by="officer-sharma",
    )
    tid = tender["id"]
    print(f"  Created tender id={tid[:8]} state={tender['state']}")

    # 2. Upload NIT → L1
    print("\n[2/10] Upload NIT and run L1 …")
    tender_service.transition_state(
        conn, tender_id=tid, target_state="DOCUMENTS_PENDING", actor="officer-sharma",
    )
    tender_service.transition_state(
        conn, tender_id=tid, target_state="DOCUMENTS_PROCESSING", actor="officer-sharma",
    )
    nit_doc = document_service.save_path_and_process(
        conn, tender_id=tid, bidder_id=None, doc_type="nit",
        src_path=str(NIT_PATH), actor="officer-sharma",
    )
    print(f"  NIT id={nit_doc['id'][:8]} pages={nit_doc['page_count']} "
          f"avg_ocr={nit_doc['avg_ocr_conf']}")
    tender_service.transition_state(
        conn, tender_id=tid, target_state="DOCUMENTS_READY", actor="officer-sharma",
    )

    # 3. Extract criteria + checklist (L2)
    print("\n[3/10] Extract criteria + checklist (L2) …")
    extract_summary = criteria_service.extract_for_tender(
        conn, tender_id=tid, actor="officer-sharma",
    )
    print(f"  Criteria: {extract_summary['criteria_count']}")
    print(f"  Checklist: {extract_summary['checklist_count']}")

    # 4. Approve criteria
    print("\n[4/10] Approve all criteria …")
    criteria_service.approve_all(
        conn, tender_id=tid, officer_id="officer-sharma",
    )
    tender_service.transition_state(
        conn, tender_id=tid, target_state="CHECKLIST_PENDING", actor="officer-sharma",
    )

    # 5. Register bidders + upload their docs
    print("\n[5/10] Register 3 bidders, upload submissions …")
    # NOTE: Acme & Bravo deliberately share the same address (collision)
    # and Charlie's PAN starts with the same chars as Acme's so the
    # smell test has something to flag in the demo.
    SHARED_ADDRESS = "Plot 42, Sector 18, Gurugram, Haryana - 122015"
    bidder_paths = [
        # name, pan, gstin, address, [list of upload paths]
        ("Acme Defence Manufacturing Pvt Ltd", "AAACA1234B", "29AAACA1234B1Z5", SHARED_ADDRESS,
         [GOOD_BIDDER_PATH, CA_CERT_PATH]),
        ("Bravo Industries Ltd",                "BBBCB2345C", "07BBBCB2345C1Z3", SHARED_ADDRESS,
         [MISMATCH_BIDDER_PATH, CA_CERT_STAMPED_PATH]),
        ("Charlie Auto Components",             "CCCAC3456D", "33CCCAC3456D1Z8", "12 MG Road, Bengaluru - 560001",
         [WEAK_BIDDER_PATH, CA_CERT_PHOTO_PATH]),
    ]
    bidder_ids = []
    for name, pan, gstin, address, paths in bidder_paths:
        b = bidder_service.register_bidder(
            conn, tender_id=tid, company_name=name,
            pan_number=pan, gstin=gstin, address=address,
            actor="officer-sharma",
        )
        bidder_ids.append(b["id"])
        for p in paths:
            doc_type = "certificate" if "certificate" in p.name else "bidder_submission"
            document_service.save_path_and_process(
                conn, tender_id=tid, bidder_id=b["id"],
                doc_type=doc_type,
                src_path=str(p), actor="officer-sharma",
            )
        bidder_service.check_debarment(
            conn, bidder_id=b["id"], actor="officer-sharma",
        )
        print(f"  Bidder: {name[:40]:<40} -> {b['id'][:8]} ({len(paths)} files)")

    # 6. Auto-match checklist + finalize preliminary
    print("\n[6/10] Auto-match checklist + finalize preliminary …")
    for bid in bidder_ids:
        responses = checklist_service.auto_match(
            conn, tender_id=tid, bidder_id=bid, actor="officer-sharma",
        )
        # Auto-accept any matched-or-partial response so the smoke test
        # finalizes without manual UI clicks
        all_responses = checklist_service.list_responses(
            conn, tender_id=tid, bidder_id=bid,
        )
        for r in all_responses:
            if r["state"] in ("present", "partial"):
                checklist_service.decide_response(
                    conn, response_id=r["id"], decision="accepted",
                    officer_id="officer-sharma",
                )
    checklist_service.finalize_preliminary(
        conn, tender_id=tid, actor="officer-sharma",
    )
    print("  Preliminary finalised.")

    # 7. Run full evaluation
    print("\n[7/10] Run evaluation (L3 + L4 + L5 + L7) …")
    summary = evaluation_service.run_evaluation(
        conn, tender_id=tid, actor="officer-sharma",
    )
    print(f"  Total cells: {summary['total_cells']}")
    print(f"  Auto-committed: {summary['auto_committed']}")
    print(f"  HITL review: {summary['hitl_review']}")
    print(f"  Mandatory review: {summary['mandatory_review']}")
    print(f"  Anomalies: {summary['anomalies_detected']}")
    print(f"  Errors: {summary['errors']}")

    # 8. Capture a replay
    print("\n[8/10] Capture a replay snapshot …")
    evals = evaluation_service.list_evaluations(conn, tender_id=tid)
    if evals:
        replay = replay_service.capture(
            conn, evaluation_id=evals[0]["id"], officer_id="officer-sharma",
        )
        print(f"  Replay id={replay['id'][:8]} eval={replay['evaluation_id'][:8]}")

    # 9. Generate report (only if state allows)
    print("\n[9/10] Generate TEC report …")
    tender_now = tender_service.get_tender(conn, tid)
    if tender_now["state"] == "EVALUATION_COMPLETE":
        report = report_service.generate_report(
            conn, tender_id=tid, officer_id="officer-sharma",
        )
        print(f"  Report id={report['id'][:8]} sha256={report['sha256_hash'][:16]}…")
        print(f"  Path: {report['file_path']}")
    else:
        print(f"  Tender state is {tender_now['state']}; "
              f"some evaluations need officer decisions before report generation.")

    # 10. Verify audit chain
    print("\n[10/10] Verify audit chain …")
    ok, error = audit_chain.verify(conn, tid)
    print(f"  Audit chain valid: {ok}")
    if error:
        print(f"  Error: {error}")

    print("\n" + "=" * 70)
    print("SMOKE TEST COMPLETE")
    print("=" * 70)
    return 0 if ok and summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
