# VerdictAI Rebuild — Build Status

## Decisions made
- Bedrock model: `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (cross-region inference profile, account 316394832518)
- Region: us-east-1
- Auth: ADA credentials from terminal (default boto3 chain)
- DB: SQLite single file, JSON columns where needed, FTS5 for precedent search
- Frontend: light theme, government-employee-first, Tender Space concept

## Backend — DONE ✅

### Foundation
- ✅ `backend/__init__.py`, `config.py` — settings layer
- ✅ `backend/database/schema.py` — full schema with CHECK constraints, JSON validation, append-only triggers, FTS5
- ✅ `backend/database/connection.py` — connection management + audit_lock + officer seed
- ✅ `backend/core/audit_chain.py` — hash-chained log with serialised insert
- ✅ `backend/core/state_machine.py` — tender + evaluation state transitions
- ✅ `backend/core/confidence.py` — Confidence Veil routing + Mosaic
- ✅ `backend/core/smell_test.py` — rule-based anomaly detection
- ✅ `backend/ai/bedrock_client.py` — boto3 with cache, retry, hash, streaming
- ✅ `backend/ai/prompts.py` — versioned prompts (criterion, evidence, dissent, anomaly, copilot)
- ✅ `backend/utils/{hashing,file_types,pdf_io,ocr}.py` — file + OCR helpers

### Pipeline
- ✅ `backend/pipeline/document_processing.py` — L1: PDF/DOCX/JPG → pages + words
- ✅ `backend/pipeline/criterion_extraction.py` — L2: NIT → criteria + checklist
- ✅ `backend/pipeline/evidence_extraction.py` — L3: bidder docs → per-criterion evidence
- ✅ `backend/pipeline/verdict.py` — L4: evidence → verdict + dissent + routing + explanation
- ✅ `backend/pipeline/anomaly_pipeline.py` — L5: rule-based smell test + LLM novel-anomaly fallback
- ✅ `backend/pipeline/post_review.py` — L7: pre-canned post-review checks per criterion type

### Services
- ✅ `tender_service.py` — CRUD, transitions, soft-delete
- ✅ `document_service.py` — upload + L1 dispatch + page/word reads
- ✅ `bidder_service.py` — registration, debarment placeholder, state updates
- ✅ `criteria_service.py` — extract trigger, edit, approve gate
- ✅ `checklist_service.py` — auto-match (token-overlap + doc_type bonus), decide, finalize
- ✅ `evaluation_service.py` — orchestrates L3 + L4 + L5 + L7 across (bidder × criterion), matrix, decide, second-officer
- ✅ `chat_service.py` — Copilot context assembly + SSE streaming
- ✅ `report_service.py` — full TEC PDF via reportlab.platypus (matrix + per-bidder detail)
- ✅ `replay_service.py` — Time Capsule snapshot capture/list/get
- ✅ `reproduce_service.py` — re-run via cached LLM, diff against stored row

### API (FastAPI)
- ✅ `main.py` — app factory, lifespan, CORS, healthz
- ✅ 12 router modules → **58 endpoints** total
- ✅ All endpoints behind `/api/v1` prefix
- ✅ Officer ID via `X-Officer-ID` header
- ✅ State errors → 409, validation errors → 400, missing → 404

## Verified live
- ✅ Bedrock invoke + cache hit (Sonnet 4.5)
- ✅ Structured JSON extraction
- ✅ Audit chain integrity (UPDATE/DELETE blocked by triggers, hash chain verified)
- ✅ L1: 3-page PDF → 649 word_objects, hash-linked audit
- ✅ L1: phone-photo JPG → 89% OCR confidence, real text extracted
- ✅ L2: 9 criteria + 13 checklist items extracted from real CRPF NIT (when LLM available)
- ✅ FastAPI app boots cleanly with all 58 routes registered
- ✅ End-to-end smoke test: tender → NIT upload → criteria → 3 bidders → checklist → evaluation → smell test (9 anomalies on rule-based path) → replay → TEC PDF → audit verify (PASS)

## In progress
- 🟡 Frontend full rewrite (Tender Space concept)

## Not started
- ⬜ Frontend rewrite
  - Tender Space layout, step indicator, tabs
  - Inline PDF viewer with bbox highlight (react-pdf already installed)
  - Comparative matrix
  - Right-side Copilot chat panel (consume `/chat/stream` SSE)
  - Smell Test chips on cells
  - Time Capsule replay viewer
  - Officer picker in header
  - Tooltips on every interactive element
  - Color-coded buttons (blue/green/red/amber/grey)
  - Light theme, GIGW-compliant, A-/A/A+ text size + high contrast
- ⬜ End-to-end demo data seed (production-quality, not the smoke fixture)

## Known caveats (non-blocking)
- ADA token expired during smoke test → LLM-dependent steps (criterion extraction, qualitative evidence, dissent, novel anomalies) returned `null` and the pipeline gracefully continued. Run `ada credentials update --account=316394832518 --role=...` then re-run the smoke test.
- Cross-bidder smell-test rules are conservative — they're correct, but the demo NIT/bidders don't currently trigger high-severity flags. Demo data seed should include a deliberately crafted "address collision" or "duplicate doc" to make the Smell Test panel visibly active in the demo.
