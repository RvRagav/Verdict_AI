"""Demo data seed for the live VerdictAI app.

Populates the *live* DB (verdict_ai.db) with three tenders at different
stages so every screen has something real to show. Uses the realistic
synthetic packs from `realistic_generator.py`.

Idempotent + resumable: if a previous partial run left a tender behind
in an intermediate state, this script picks it up from there.
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from pathlib import Path

# Repo root onto path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from backend.database.connection import init_db
from backend.services import (
    bidder_service, brief_service, checklist_service, criteria_service,
    concurrence_service, debarment_service, document_service, evaluation_service,
    tender_service,
)


DEMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = DEMO_DIR.parent.parent
SAMPLE_DOCS = REPO_ROOT / "sample_docs"

NIT = SAMPLE_DOCS / "nit_crpf_patrol_vehicles.pdf"
CORRIG = SAMPLE_DOCS / "corrigendum_1.pdf"

ACME_DIR    = SAMPLE_DOCS / "bidders" / "acme"
BRAVO_DIR   = SAMPLE_DOCS / "bidders" / "bravo"
CHARLIE_DIR = SAMPLE_DOCS / "bidders" / "charlie"


def main() -> int:
    conn = init_db()
    print("=" * 64)
    print(" Seeding demo data into the live DB …")
    print("=" * 64)

    # ── Debarment registry ─────────────────────────────────────────
    seed_debarment_registry(conn)

    # ── Tender 1: full pipeline run (evaluations + brief + concurrence)
    print("\n[1] CRPF/2026/15-A — Patrol Vehicles")
    try:
        seed_full_tender(conn)
    except Exception as exc:
        print(f"  ERROR while seeding Tender 1: {type(exc).__name__}: {exc}")
        traceback.print_exc()

    # ── Tender 2: criteria-approved, no evaluations
    print("\n[2] CRPF/2026/22-B — Bullet-proof Jackets")
    try:
        seed_criteria_tender(conn)
    except Exception as exc:
        print(f"  ERROR while seeding Tender 2: {type(exc).__name__}: {exc}")
        traceback.print_exc()

    # ── Tender 3: empty workspace
    print("\n[3] CRPF/2026/30-C — IT Hardware Refresh")
    try:
        seed_empty_tender(conn)
    except Exception as exc:
        print(f"  ERROR while seeding Tender 3: {type(exc).__name__}: {exc}")
        traceback.print_exc()

    print("\nDone.")
    return 0


# ─── Debarment seed ────────────────────────────────────────────────


def seed_debarment_registry(conn) -> None:
    seeds = [
        {
            "pan_number": "ZZZZZ9999Z",
            "company_name": "Phantom Defence Pvt Ltd",
            "source": "cvc",
            "reason": "CVC notice 23/2025 — fraudulent BG submission, debarred 3 yrs",
            "debarred_until": "2028-11-15",
            "notice_url": "https://cvc.gov.in/notice/23-2025",
        },
        {
            "pan_number": "BLOCK1234A",
            "company_name": "BlockedCo Industries",
            "source": "gem",
            "reason": "GeM blacklist — non-performance on 2 prior tenders",
            "debarred_until": None,
        },
        {
            "gstin": "27AAAEM1234R1Z9",
            "company_name": "Mock Components Limited",
            "source": "court_order",
            "reason": "High Court order Dec 2025 — pending ED chargesheet",
            "debarred_until": "2027-01-01",
        },
        {
            "pan_number": "FAKEN5678C",
            "company_name": "Fakename Solutions Pvt Ltd",
            "source": "department",
            "reason": "Internal CRPF debarment — false past-performance certificate",
            "debarred_until": "2027-05-10",
        },
    ]
    inserted = 0
    for s in seeds:
        r = debarment_service.add_entry(conn, **s)
        if not r.get("duplicate"):
            inserted += 1
    print(f"  debarment registry: {inserted} new (skipped duplicates)")


# ─── Full pipeline tender ──────────────────────────────────────────


def seed_full_tender(conn) -> None:
    tnum = "CRPF/2026/15-A"

    # ── Resume-able: pick up an existing partially-seeded tender
    existing = conn.execute(
        "SELECT id, state FROM tenders WHERE tender_number = ? AND deleted_at IS NULL",
        (tnum,),
    ).fetchone()
    if existing:
        print(f"  Resuming existing tender (state={existing['state']}).")
        tid = existing["id"]
    else:
        # 1. Create
        t = tender_service.create_tender(
            conn,
            tender_number=tnum,
            title="Supply of Armoured Patrol Vehicles for CRPF Operations",
            department="CRPF",
            category="Goods",
            estimated_cost=150_000_000,
            emd_amount=1_500_000,
            bid_open_date="2026-04-15",
            bid_close_date="2026-05-15",
            created_by="officer-sharma",
        )
        tid = t["id"]

    # 2. Upload NIT (skip if a NIT doc already exists)
    nit_row = conn.execute(
        "SELECT id FROM documents WHERE tender_id = ? AND doc_type = 'nit' "
        "AND deleted_at IS NULL LIMIT 1", (tid,),
    ).fetchone()
    if not nit_row:
        _ensure_state(conn, tid, "DOCUMENTS_PENDING", "officer-sharma")
        _ensure_state(conn, tid, "DOCUMENTS_PROCESSING", "officer-sharma")
        print("    uploading NIT and running OCR pipeline…", flush=True)
        document_service.save_path_and_process(
            conn, tender_id=tid, bidder_id=None, doc_type="nit",
            src_path=str(NIT), actor="officer-sharma",
        )
    else:
        print(f"    NIT already uploaded; skipping.", flush=True)
    _ensure_state(conn, tid, "DOCUMENTS_READY", "officer-sharma")
    print(f"  step 1/7: NIT uploaded.", flush=True)

    # 3. Extract criteria (skip if already extracted)
    crits = conn.execute("SELECT COUNT(*) c FROM criteria WHERE tender_id = ?", (tid,)).fetchone()
    if crits["c"] == 0:
        print("    calling Bedrock to extract criteria from NIT…", flush=True)
        criteria_service.extract_for_tender(conn, tender_id=tid, actor="officer-sharma")
    else:
        print(f"    {crits['c']} criteria already extracted; skipping LLM call.", flush=True)
    pending_or_extracted = conn.execute(
        "SELECT COUNT(*) c FROM criteria WHERE tender_id = ? AND state != 'approved'", (tid,)
    ).fetchone()["c"]
    if pending_or_extracted > 0:
        criteria_service.approve_all(conn, tender_id=tid, officer_id="officer-sharma")
    _ensure_state(conn, tid, "CHECKLIST_PENDING", "officer-sharma")
    print(f"  step 2/7: criteria extracted + approved.", flush=True)

    # 4. Bidders — Acme & Bravo share an address (smell test will fire)
    SHARED = "Plot 42, Sector 18, Industrial Area, Gurugram, Haryana 122015"
    bidders_seed = [
        ("Acme Defence Manufacturing Pvt Ltd", "AAACA1234B", "06AAACA1234B1Z5", SHARED,
         15_00_000, "BG", "BG-IDBI-44521", "2026-08-15", False,
         sorted(ACME_DIR.glob("*.pdf"))),
        ("Bravo Industries Ltd",                "BBBCB2345C", "06BBBCB2345C1Z3", SHARED,
         15_00_000, "DD", "DD-SBI-9988", "2026-08-10", False,
         sorted(BRAVO_DIR.glob("*.pdf"))),
        ("Charlie Auto Components",             "CCCAC3456D", "29CCCAC3456D1Z8",
         "12 MG Road, Bengaluru 560001",
         None, None, None, None, True,
         sorted(CHARLIE_DIR.glob("*.pdf")) + sorted(CHARLIE_DIR.glob("*.jpg"))),
    ]
    bidder_ids = []
    for (name, pan, gstin, address, emd_amt, emd_inst, emd_no, emd_val,
         emd_exempt, paths) in bidders_seed:
        # If a bidder with this name already exists for this tender, reuse it
        existing_b = conn.execute(
            "SELECT id FROM bidders WHERE tender_id = ? AND company_name = ? "
            "AND deleted_at IS NULL", (tid, name),
        ).fetchone()
        if existing_b:
            bidder_ids.append(existing_b["id"])
            continue
        b = bidder_service.register_bidder(
            conn, tender_id=tid, company_name=name,
            pan_number=pan, gstin=gstin, address=address,
            emd_amount=emd_amt, emd_instrument=emd_inst,
            emd_instrument_no=emd_no, emd_validity_date=emd_val,
            emd_exempt=emd_exempt,
            emd_exempt_reason="MSE registration" if emd_exempt else None,
            bid_validity_until="2026-08-15",
            actor="officer-sharma",
        )
        bidder_ids.append(b["id"])
        print(f"    bidder: {name}  ({len(paths)} docs)")
        for p in paths:
            ext = p.suffix.lower()
            name_low = p.name.lower()
            if ext in (".jpg", ".jpeg", ".png") or "certificate" in name_low or \
               "iso" in name_low or "gst" in name_low or "pan" in name_low or \
               "udyam" in name_low or "turnover" in name_low:
                doc_type = "certificate"
            else:
                doc_type = "bidder_submission"
            print(f"      uploading {p.name} as {doc_type} …", flush=True)
            document_service.save_path_and_process(
                conn, tender_id=tid, bidder_id=b["id"], doc_type=doc_type,
                src_path=str(p), actor="officer-sharma",
            )
        bidder_service.check_debarment(conn, bidder_id=b["id"], actor="officer-sharma")
    print(f"  step 3/7: {len(bidder_ids)} bidders registered.")

    # 5. Auto-match checklist + finalise (skip if already past PRELIMINARY_DONE)
    cur_state = conn.execute("SELECT state FROM tenders WHERE id = ?", (tid,)).fetchone()["state"]
    if cur_state in ("CHECKLIST_PENDING",):
        for bid in bidder_ids:
            checklist_service.auto_match(conn, tender_id=tid, bidder_id=bid, actor="officer-sharma")
            for r in checklist_service.list_responses(conn, tender_id=tid, bidder_id=bid):
                if r["state"] in ("present", "partial"):
                    checklist_service.decide_response(
                        conn, response_id=r["id"], decision="accepted",
                        officer_id="officer-sharma",
                    )
        checklist_service.finalize_preliminary(conn, tender_id=tid, actor="officer-sharma")
    print(f"  step 4/7: preliminary finalised.")

    # 6. Run evaluation (skip if any evaluations exist)
    has_evals = conn.execute(
        "SELECT COUNT(*) c FROM evaluations WHERE tender_id = ?", (tid,)
    ).fetchone()["c"]
    if has_evals == 0:
        print("    running evaluation across (bidders × criteria) — this may take a few minutes…", flush=True)
        # Cell-level progress callback so you see something every couple of seconds
        def _on_progress(evt: dict) -> None:
            phase = evt.get("phase")
            if phase == "start":
                print(f"      total cells: {evt.get('total')}", flush=True)
            elif phase == "cell_complete":
                print(f"      [{evt['index']}/{evt['total']}]", flush=True)
            elif phase == "complete":
                pass
        summary = evaluation_service.run_evaluation(
            conn, tender_id=tid, actor="officer-sharma",
            progress_cb=_on_progress,
        )
        print(f"  step 5/7: {summary['total_cells']} cells, "
              f"{summary['hitl_review']} HITL, "
              f"{summary['mandatory_review']} mandatory, "
              f"{summary['anomalies_detected']} anomalies, "
              f"{summary['errors']} errors.", flush=True)
    else:
        print(f"  step 5/7: {has_evals} evaluations already present (skipping).", flush=True)

    # 7. Decide a couple of mandatory-review cells to populate the inbox
    mandatory_evals = evaluation_service.list_evaluations(
        conn, tender_id=tid, route="mandatory_review",
    )
    confirmed = 0
    for ev in mandatory_evals[:3]:
        if ev.get("officer_decision"):
            continue  # already decided
        try:
            evaluation_service.decide_evaluation(
                conn,
                evaluation_id=ev["id"],
                decision="confirmed",
                officer_id="officer-sharma",
                structured_reason="evidence_sufficient",
                reason_text="Reviewed evidence; confirming AI suggestion.",
            )
            confirmed += 1
        except Exception as exc:
            print(f"    skipping decide: {exc}")
    print(f"  step 6/7: {confirmed} mandatory-review cell(s) decided "
          f"(opens concurrence requests).")

    # 8. Generate Pre-Mortem Brief
    brief_service.generate(conn, tender_id=tid, actor="officer-sharma")
    print(f"  step 7/7: brief generated.")


# ─── Criteria-approved tender (no evaluation) ──────────────────────


def seed_criteria_tender(conn) -> None:
    tnum = "CRPF/2026/22-B"
    if _tender_exists(conn, tnum):
        print(f"  Tender {tnum} already exists — skipping.")
        return

    t = tender_service.create_tender(
        conn,
        tender_number=tnum,
        title="Procurement of Bullet-Proof Jackets and Helmets",
        department="CRPF",
        category="Goods",
        estimated_cost=85_000_000,
        emd_amount=850_000,
        bid_open_date="2026-05-01",
        bid_close_date="2026-06-01",
        created_by="officer-kumar",
    )
    tid = t["id"]
    tender_service.transition_state(conn, tender_id=tid, target_state="DOCUMENTS_PENDING", actor="officer-kumar")
    tender_service.transition_state(conn, tender_id=tid, target_state="DOCUMENTS_PROCESSING", actor="officer-kumar")
    document_service.save_path_and_process(
        conn, tender_id=tid, bidder_id=None, doc_type="nit",
        src_path=str(NIT), actor="officer-kumar",
    )
    tender_service.transition_state(conn, tender_id=tid, target_state="DOCUMENTS_READY", actor="officer-kumar")
    criteria_service.extract_for_tender(conn, tender_id=tid, actor="officer-kumar")

    # Add one bidder with EMD details so EMD UI has data to show
    bidder_service.register_bidder(
        conn, tender_id=tid,
        company_name="Sentinel Body-Armor Pvt Ltd",
        pan_number="SENTI1234X", gstin="29SENTI1234X1Z7",
        address="Industrial Area Phase 2, Pune 411019",
        emd_amount=850_000, emd_instrument="BG",
        emd_instrument_no="BG-HDFC-77291",
        emd_validity_date="2026-09-01",
        bid_validity_until="2026-09-01",
        actor="officer-kumar",
    )
    print("  criteria extracted; tender remains in CRITERIA_PENDING_REVIEW.")


# ─── Empty workspace ───────────────────────────────────────────────


def seed_empty_tender(conn) -> None:
    tnum = "CRPF/2026/30-C"
    if _tender_exists(conn, tnum):
        print(f"  Tender {tnum} already exists — skipping.")
        return
    t = tender_service.create_tender(
        conn,
        tender_number=tnum,
        title="IT Hardware Refresh — Workstations and Networking",
        department="CRPF",
        category="Goods",
        estimated_cost=42_000_000,
        emd_amount=420_000,
        bid_open_date="2026-06-01",
        bid_close_date="2026-07-01",
        created_by="officer-verma",
    )
    tender_service.transition_state(
        conn, tender_id=t["id"], target_state="DOCUMENTS_PENDING", actor="officer-verma",
    )
    print("  blank workspace ready (DOCUMENTS_PENDING).")


def _tender_exists(conn, tender_number: str) -> bool:
    r = conn.execute(
        "SELECT id FROM tenders WHERE tender_number = ? AND deleted_at IS NULL",
        (tender_number,),
    ).fetchone()
    return r is not None


def _ensure_state(conn, tender_id: str, target: str, actor: str) -> None:
    """Advance a tender to `target`, no-op if already at or past it."""
    cur = conn.execute(
        "SELECT state FROM tenders WHERE id = ?", (tender_id,)
    ).fetchone()
    if not cur:
        return
    if cur["state"] == target:
        return
    try:
        tender_service.transition_state(
            conn, tender_id=tender_id, target_state=target, actor=actor,
        )
    except Exception:
        # State machine may already be past `target` — that's fine.
        pass


if __name__ == "__main__":
    sys.exit(main())
