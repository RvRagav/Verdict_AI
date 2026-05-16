# Implementation Plan: VerdictAI

## Overview

Build the VerdictAI Explainable AI Procurement Intelligence Platform as a pure local application with Python FastAPI backend, SQLite database, and React + Vite + TailwindCSS frontend. Implementation follows dependency order: project scaffolding → database layer → backend layers (L1–L5) in pipeline order → services → API endpoints → frontend → integration testing → demo data.

## Tasks

- [x] 1. Project scaffolding and configuration
  - [x] 1.1 Initialize backend project structure
    - Create `backend/` directory with the module structure defined in design (main.py, config.py, database/, models/, layers/, services/, api/, utils/)
    - Create `backend/requirements.txt` with dependencies: fastapi, uvicorn, pydantic, python-multipart, aiosqlite, Pillow, reportlab, python-dateutil, hypothesis (dev)
    - Create `backend/config.py` with settings: DB path, confidence thresholds (auto_commit=0.85, mandatory_floor=0.50, conservative_auto=0.90, conservative_floor=0.60), entity match threshold (0.85), CPM calibration threshold (50)
    - Create all `__init__.py` files for package structure
    - _Requirements: 16.2, 16.4_

  - [x] 1.2 Initialize frontend project structure
    - Scaffold React + Vite + TypeScript project in `frontend/` directory
    - Install and configure TailwindCSS
    - Install dependencies: react-router-dom, axios
    - Create directory structure matching design: pages/, components/, hooks/, types/, api/, utils/
    - Create `frontend/src/types/index.ts` with TypeScript interfaces matching all API response types
    - _Requirements: 15.1_

  - [x] 1.3 Create development configuration
    - Create root `README.md` with setup instructions (single-command start for backend, npm run dev for frontend)
    - Create `backend/main.py` FastAPI app entry point with CORS middleware for localhost frontend
    - Verify backend starts with `uvicorn backend.main:app --reload`
    - _Requirements: 16.4_

- [x] 2. Database layer and schema
  - [x] 2.1 Implement SQLite connection and WAL mode
    - Create `backend/database/connection.py` with SQLite connection factory using WAL mode for concurrent reads
    - Implement connection context manager for transaction handling
    - Implement database initialization function that creates tables on first run
    - _Requirements: 16.2_

  - [x] 2.2 Implement full database schema
    - Create `backend/database/schema.py` with CREATE TABLE statements for all 10 tables: tenders, documents, pages, word_objects, criteria, bidders, evaluations, audit_events, cpm_entries, debarment_list, llm_stub_log
    - Implement FTS5 virtual table `cpm_fts` with content sync triggers
    - Implement audit immutability triggers (audit_no_update, audit_no_delete)
    - All columns, types, and constraints must match the design ERD exactly
    - _Requirements: 12.2, 12.5, 11.6, 16.2_

  - [ ]* 2.3 Write property tests for audit immutability triggers
    - **Property 9: Audit ledger immutability**
    - **Validates: Requirements 12.2, 12.5**
    - Generate random UPDATE/DELETE attempts on audit_events table and verify all raise exceptions

  - [x] 2.4 Implement demo data seeding
    - Create `backend/database/seed.py` with functions to populate: CVC debarment list stub (5+ entries), CPM bootstrap corpus (10+ synthetic precedents for common criterion types), sample tender with NIT criteria
    - Seed function must be idempotent (check before insert)
    - _Requirements: 17.2, 17.3, 17.4_

- [x] 3. Backend data models (Pydantic)
  - [x] 3.1 Implement all Pydantic models
    - Create `backend/models/document.py`: Document, Page, WordObject models
    - Create `backend/models/criterion.py`: Criterion model with CriterionType enum (numeric_threshold, categorical_presence, temporal_recency, composite, qualitative_assessment)
    - Create `backend/models/evidence.py`: Evidence, EntityMatchResult models
    - Create `backend/models/evaluation.py`: Verdict enum, Route enum, RoutingDecision, Evaluation models
    - Create `backend/models/audit.py`: AuditEvent model with event_type enum
    - Create `backend/models/cpm.py`: CPMEntry model
    - All models must match the interfaces defined in the design document
    - _Requirements: 1.6, 3.3, 6.5, 7.6, 12.1_

- [x] 4. Checkpoint — Verify foundation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Layer 5: Audit Ledger (implement first — used by all other layers)
  - [x] 5.1 Implement SHA-256 hash utilities
    - Create `backend/utils/hash_utils.py` with `compute_entry_hash()` function matching the design algorithm
    - Implement deterministic JSON serialisation (sort_keys=True, separators=(',', ':'))
    - _Requirements: 12.4_

  - [x] 5.2 Implement audit ledger service
    - Create `backend/layers/l5_audit.py` with `append_audit_event()` function
    - Implement hash chain: each event links to previous via prev_hash field
    - Genesis hash is 64 zeros for first entry per tender
    - Implement `verify_hash_chain()` function to validate integrity of entire chain for a tender
    - Implement `get_audit_trail()` with filtering by event_type and date range
    - _Requirements: 12.1, 12.2, 12.4_

  - [ ]* 5.3 Write property tests for audit hash chain integrity
    - **Property 8: Audit hash chain integrity**
    - **Validates: Requirements 12.4**
    - Generate sequences of N audit events, verify each event[i].prev_hash == event[i-1].entry_hash and recomputing entry_hash from fields matches stored value

- [x] 6. Services layer
  - [x] 6.1 Implement LLM Stub service
    - Create `backend/services/llm_stub.py` with LLMStub class matching design interface
    - Implement `invoke()` method with scenario matching and default response strategy
    - Implement all 4 pre-configured demo scenarios: criterion extraction with corrigendum, stamp-obscured certificate, entity mismatch, CPM precedent injection
    - Implement prompt hash computation (SHA-256 of serialised request)
    - Implement logging to llm_stub_log table for every invocation
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ]* 6.2 Write property tests for LLM Stub response structure
    - **Property 16: LLM Stub response structure invariant**
    - **Validates: Requirements 14.1, 14.2, 14.5**
    - Generate random LLMStubRequest objects, verify response always contains: result (dict), confidence (float 0-1), reasoning (non-empty), is_simulated (True), model_version (non-empty), prompt_hash (64-char hex matching SHA-256 of input)

  - [x] 6.3 Implement Entity Matcher service
    - Create `backend/services/entity_matcher.py` with `normalise_company_name()` and `match_entity()` functions
    - Implement abbreviation expansion dictionary for Indian company names
    - Implement suffix removal, punctuation stripping, and SequenceMatcher similarity
    - Implement mismatch type classification: parent_company, abbreviation, different_entity
    - _Requirements: 6.6_

  - [ ]* 6.4 Write property tests for Entity Matcher
    - **Property 7: Entity matcher detects mismatches symmetrically**
    - **Validates: Requirements 6.6**
    - Generate random company names, verify normalisation is idempotent: normalise(normalise(x)) == normalise(x)
    - Verify that similarity below threshold always sets requires_review=True

  - [x] 6.5 Implement CPM service
    - Create `backend/services/cpm_service.py` with `search_cpm_precedents()` and `store_precedent()` functions
    - Implement FTS5 query construction with stop word removal and BM25 ranking
    - Implement department and category filtering
    - Enforce maximum 3 results limit
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.6_

  - [ ]* 6.6 Write property tests for CPM search
    - **Property 13: CPM search results bounded and filtered**
    - **Validates: Requirements 4.5, 8.4, 11.3, 11.4**
    - Generate random queries with department/category, verify result count ≤ 3 and all results match requested department and category exactly

  - [x] 6.7 Implement Debarment service
    - Create `backend/services/debarment_service.py` with `check_debarment()` function
    - Cross-reference bidder PAN and company name against debarment_list table
    - Return match status with matched entity details
    - _Requirements: 5.1, 5.2, 5.3_

- [ ] 7. Layer 1: Document Intelligence
  - [x] 7.1 Implement PDF parsing utilities
    - Create `backend/utils/pdf_utils.py` with PDF page extraction (using PyPDF2 or pdfplumber)
    - Extract embedded text content and page count
    - Compute SHA-256 hash of uploaded file
    - Handle corrupted/unreadable PDFs with descriptive error messages
    - _Requirements: 1.1, 1.7_

  - [x] 7.2 Implement image pre-processing pipeline
    - Create `backend/utils/image_processing.py` with the 5-step pipeline:
      1. DPI normalisation to 300 DPI
      2. Deskew correction (Hough line detection, up to 15 degrees)
      3. Adaptive binarisation (Sauvola thresholding)
      4. Red-channel stamp separation
      5. Page image extraction
    - For prototype: implement as stubs that pass through images with processing_notes indicating what would be done
    - _Requirements: 1.2, 1.3, 1.4, 1.5_

  - [x] 7.3 Implement OCR utilities
    - Create `backend/utils/ocr_utils.py` with Tesseract wrapper (or stub for environments without Tesseract)
    - Implement word-level extraction with bounding boxes and confidence scores
    - Implement page-level confidence as length-weighted mean of per-word confidences
    - Flag pages with confidence below 0.50 as degraded
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 7.4 Write property test for OCR page confidence calculation
    - **Property 14: OCR page confidence is length-weighted mean**
    - **Validates: Requirements 2.2**
    - Generate lists of (word_text, confidence) pairs, verify computed page confidence equals sum(len[i]*conf[i]) / sum(len[i]) and result is always in [0.0, 1.0]

  - [x] 7.5 Implement L1 Document Intelligence layer
    - Create `backend/layers/l1_document.py` orchestrating: PDF upload → parse → pre-process → OCR → store normalised document objects
    - Store documents, pages, and word_objects in database
    - Log document_received and ocr_completed events to audit ledger
    - _Requirements: 1.1, 1.6, 2.1_

- [x] 8. Layer 2: ETS Builder
  - [x] 8.1 Implement ETS Builder layer
    - Create `backend/layers/l2_ets_builder.py` with criterion extraction via LLM Stub
    - Implement type classification into 5 criterion types
    - Implement corrigendum version assembly (chronological amendment application)
    - Implement amendment history tracking (original + all amendments)
    - Implement missing corrigendum detection (amendment indicators without file)
    - Annotate criteria with GFR_override_permitted flag, source document, clause reference
    - Log corrigendum_linked events to audit ledger
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 8.2 Write property tests for corrigendum amendment history
    - **Property 12: Corrigendum amendments preserve history**
    - **Validates: Requirements 3.5**
    - Generate random corrigenda sequences, verify amendment_history contains original + all amendments in order, and final threshold_value equals most recent amendment

  - [x] 8.3 Implement Schema Review Gate
    - Implement state enforcement: evaluation cannot proceed without explicit schema approval
    - Store approval event with officer_id and timestamp in audit ledger
    - Implement criterion editing during review (update criterion fields, store CPM precedent if interpretation changed)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6_

  - [ ]* 8.4 Write property tests for schema review gate enforcement
    - **Property 10: Schema review gate enforcement**
    - **Validates: Requirements 4.1**
    - Generate random action sequences without schema approval, verify all evaluation attempts are rejected

- [x] 9. Layer 3: Evidence Extraction
  - [x] 9.1 Implement Evidence Extractor layer
    - Create `backend/layers/l3_evidence.py` with type-specific evidence extraction:
      - numeric_threshold: table-aware value extraction with fiscal year verification
      - categorical_presence: certificate search by name/synonyms, extract registration number and validity
      - temporal_recency: extract project value, completion date, description
      - qualitative_assessment: retrieve relevant passages + CPM precedents via LLM Stub
    - Output structured evidence objects with value, source document, page, bbox, OCR confidence, extraction confidence, entity match flag
    - Integrate Entity Matcher for company name verification
    - Log evidence_extracted events to audit ledger
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 10. Layer 4: Evaluation Engine
  - [x] 10.1 Implement Confidence Router
    - Create `backend/layers/l4_evaluation.py` with `compute_route()` function matching the design algorithm exactly
    - Implement all 6 routing rules in priority order:
      1. Mandatory FAIL → mandatory_review
      2. Flags present → mandatory_review
      3. Low confidence (< floor) → mandatory_review
      4. LLM FAIL → hitl_review
      5. Medium confidence → hitl_review
      6. High confidence + deterministic + no flags → auto_commit
    - Implement conservative thresholds when cpm_data_count < 50
    - _Requirements: 7.1, 7.2, 7.5, 7.6, 7.7, 7.8, 7.9, 11.5_

  - [ ]* 10.2 Write property tests for Confidence Router (Properties 1-5)
    - **Property 1: Mandatory FAIL always routes to mandatory review**
    - **Property 2: LLM FAIL verdict never auto-commits**
    - **Property 3: Confidence thresholds determine routing for unflagged deterministic criteria**
    - **Property 4: Flags force mandatory review regardless of confidence**
    - **Property 5: Conservative thresholds when CPM data is insufficient**
    - **Validates: Requirements 7.1, 7.5, 7.6, 7.7, 7.8, 7.9, 9.1, 9.2, 9.3, 11.5**

  - [x] 10.3 Implement type-specific evaluation logic
    - Implement evaluation for each criterion type using evidence objects
    - Compute confidence scores based on OCR confidence and extraction confidence
    - Integrate debarment check (must precede evaluation per state machine)
    - Implement CVC debarment pre-check with pipeline halt on match
    - Log verdict_computed and case_routed events to audit ledger
    - _Requirements: 5.1, 5.2, 5.4, 7.1, 7.2, 7.3, 7.4_

  - [ ]* 10.4 Write property test for debarment ordering
    - **Property 11: Debarment check precedes evaluation**
    - **Validates: Requirements 5.1, 5.2**
    - Generate bidder sequences, verify debarment_checked event timestamp always precedes evidence_extracted and verdict_computed events in audit log

- [x] 11. Checkpoint — Verify all backend layers
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. HITL Review and GFR Enforcement
  - [x] 12.1 Implement HITL decision processing
    - Implement officer decision handling: confirm or override
    - Enforce structured reason requirement for overrides (reject if empty/missing)
    - Implement GFR override prevention: if gfr_override_permitted=false and verdict=FAIL, reject override attempts
    - Implement second-officer confirmation flow for borderline GFR-adjacent overrides
    - Log officer_decision events to audit ledger with officer_id, timestamp, reason
    - Store CPM precedent entry on every officer decision
    - _Requirements: 8.5, 8.6, 8.7, 9.1, 9.2, 10.2, 10.3, 10.4, 10.5, 11.1_

  - [ ]* 12.2 Write property tests for GFR enforcement and override validation
    - **Property 6: GFR override prevention**
    - **Property 17: Override requires structured reason**
    - **Validates: Requirements 8.5, 8.6, 10.2**
    - Generate override attempts on GFR-mandatory FAILs, verify all rejected
    - Generate override submissions with empty/missing reasons, verify all rejected

- [x] 13. Report generation
  - [x] 13.1 Implement PDF report export
    - Implement report generation in `backend/layers/l5_audit.py` (or separate report module)
    - Generate PDF with: evaluation summary per bidder, criterion-level verdicts, confidence scores, evidence references, officer decisions
    - Compute SHA-256 hash of complete audit trail and embed in PDF (human-readable string + placeholder for QR code)
    - Include source references (document, page, bbox) for each verdict
    - Prominently display any officer overrides with structured reason
    - Log report_generated event to audit ledger
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

- [x] 14. REST API endpoints
  - [x] 14.1 Implement Document API endpoints
    - Create `backend/api/documents.py` with: POST /documents/upload (multipart), GET /documents/{id}, GET /documents/{id}/pages, GET /documents/{id}/pages/{page_num}/image, GET /documents/{id}/pages/{page_num}/words
    - Implement file upload with SHA-256 deduplication (idempotent by hash)
    - _Requirements: 1.1, 16.1_

  - [x] 14.2 Implement Tender API endpoints
    - Create `backend/api/tenders.py` with: POST /tenders, GET /tenders, GET /tenders/{id}, POST /tenders/{id}/process, GET /tenders/{id}/status
    - Implement state machine enforcement on all state-changing endpoints
    - _Requirements: 16.1_

  - [x] 14.3 Implement ETS/Schema Review API endpoints
    - Create `backend/api/tenders.py` (extend) with: GET /tenders/{id}/criteria, PUT /tenders/{id}/criteria/{cid}, GET /tenders/{id}/criteria/{cid}/diff, POST /tenders/{id}/schema/approve, GET /tenders/{id}/criteria/{cid}/cpm
    - Enforce schema approval gate (409 if evaluating before approval)
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 16.1_

  - [x] 14.4 Implement Evaluation API endpoints
    - Create `backend/api/evaluation.py` with: POST /tenders/{id}/evaluate, GET /tenders/{id}/evaluations, GET /evaluations/{id}, GET /tenders/{id}/summary
    - Create `backend/api/evaluation.py` (extend) with: POST /tenders/{id}/debarment-check, GET /bidders/{id}/debarment
    - Enforce state guards: schema must be approved, debarment must be checked
    - _Requirements: 5.1, 7.6, 16.1_

  - [x] 14.5 Implement HITL Review API endpoints
    - Create `backend/api/hitl.py` with: GET /tenders/{id}/hitl/queue, GET /hitl/{evaluation_id}/card, POST /hitl/{evaluation_id}/decide, POST /hitl/{evaluation_id}/second-officer
    - Return full HITL card data: criterion details, evidence with bbox, system analysis, CPM precedents, decision options
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 16.1_

  - [x] 14.6 Implement CPM and Audit API endpoints
    - Create `backend/api/cpm.py` with: GET /cpm/search, GET /cpm/stats
    - Create `backend/api/audit.py` with: GET /tenders/{id}/audit, POST /tenders/{id}/report, GET /reports/{id}/download, POST /tenders/{id}/reproduce
    - _Requirements: 11.3, 12.1, 13.1, 18.2, 16.1_

  - [x] 14.7 Implement global error handling
    - Implement FastAPI exception handlers for all error codes defined in design
    - Implement consistent error response format: {error: {code, message, details, timestamp, request_id}}
    - Implement input validation with descriptive 400/422 responses
    - _Requirements: 16.5_

- [x] 15. Checkpoint — Verify all API endpoints
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Frontend — Layout and navigation
  - [x] 16.1 Implement layout components
    - Create `frontend/src/components/layout/Sidebar.tsx` with navigation links: Dashboard, Upload, Schema Review, Evaluation, HITL Queue, Reports
    - Create `frontend/src/components/layout/Header.tsx` with tender context display
    - Create `frontend/src/components/layout/PageLayout.tsx` as common page wrapper
    - Set up React Router with routes for all pages
    - _Requirements: 15.1_

  - [x] 16.2 Implement API client
    - Create `frontend/src/api/client.ts` with axios/fetch wrapper configured for `http://localhost:8000/api/v1`
    - Implement typed API functions for all endpoints matching backend API design
    - Implement error handling that surfaces backend error messages
    - _Requirements: 15.6_

- [x] 17. Frontend — Pages and features
  - [x] 17.1 Implement Dashboard page
    - Create `frontend/src/pages/Dashboard.tsx` showing evaluation progress per tender
    - Display counts: auto-committed, pending review, completed cases
    - List all tenders with status indicators
    - _Requirements: 15.5_

  - [x] 17.2 Implement Document Upload page
    - Create `frontend/src/pages/TenderUpload.tsx` with drag-drop PDF upload
    - Create `frontend/src/components/documents/FileUploader.tsx` accepting PDF files
    - Create `frontend/src/components/documents/DocumentList.tsx` showing uploaded documents
    - Support upload for NIT, corrigenda, and bidder submissions with doc_type selection
    - _Requirements: 15.2_

  - [x] 17.3 Implement Schema Review page
    - Create `frontend/src/pages/SchemaReview.tsx` displaying extracted criteria
    - Create `frontend/src/components/criteria/CriterionCard.tsx`, `CriterionList.tsx`, `TypeBadge.tsx`, `GFRBadge.tsx`
    - Create `frontend/src/components/criteria/CorrigendumDiff.tsx` for side-by-side diff view
    - Display each criterion with type, threshold, measurement period, evidence types, GFR status
    - Implement schema approval button with officer_id input
    - _Requirements: 15.3, 4.2, 4.3_

  - [x] 17.4 Implement HITL Queue and Review Card pages
    - Create `frontend/src/pages/HITLQueue.tsx` displaying pending cases ordered by routing priority
    - Create `frontend/src/pages/HITLReviewCard.tsx` with 5-component single-screen layout:
      1. Criterion details panel
      2. Evidence panel with bbox overlay (`EvidencePanel.tsx`)
      3. System analysis panel (`AnalysisPanel.tsx`)
      4. CPM context panel (`CPMPanel.tsx`)
      5. Decision controls (`DecisionPanel.tsx`)
    - Create `frontend/src/components/hitl/OverrideModal.tsx` with structured reason form
    - Implement GFR override button disabling when gfr_override_permitted=false
    - _Requirements: 15.4, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 17.5 Implement Evaluation View page
    - Create `frontend/src/pages/EvaluationView.tsx` showing per-bidder evaluation status
    - Create `frontend/src/components/evaluation/VerdictBadge.tsx`, `ConfidenceBar.tsx`, `RouteBadge.tsx`, `BidderSummary.tsx`
    - Display verdict, confidence, and routing for each (bidder, criterion) pair
    - _Requirements: 15.5_

  - [x] 17.6 Implement Report Export page
    - Create `frontend/src/pages/ReportExport.tsx` with report generation trigger and PDF download
    - Display SHA-256 hash of audit trail after generation
    - _Requirements: 13.1_

  - [x] 17.7 Implement common components and hooks
    - Create `frontend/src/components/common/StatusChip.tsx`, `ProgressBar.tsx`, `EmptyState.tsx`
    - Create `frontend/src/hooks/useTender.ts`, `useEvaluation.ts`, `useHITL.ts` for state management
    - Create `frontend/src/utils/formatters.ts` for date, confidence, and currency formatting
    - _Requirements: 15.1_

- [x] 18. Checkpoint — Verify frontend builds and renders
  - Ensure all tests pass, ask the user if questions arise.

- [x] 19. Demo data and sample documents
  - [x] 19.1 Create sample PDF documents
    - Create sample PDF files for the 4 demo scenarios:
      1. Base NIT with corrigendum (text PDF with eligibility criteria)
      2. Scanned CA certificate with simulated stamp obscuration
      3. Bidder submission with parent-company entity mismatch
      4. Tender with ambiguous criterion language matching CPM precedents
    - Store in `backend/demo_data/` directory
    - _Requirements: 17.1_

  - [x] 19.2 Implement first-run database initialization
    - Ensure database is created and seeded on first application start
    - Load demo documents, CVC debarment list, and CPM bootstrap corpus
    - Verify all 4 demo scenarios are exercisable end-to-end through the UI
    - _Requirements: 17.4_

- [x] 20. Integration and wiring
  - [x] 20.1 Wire state machine transitions end-to-end
    - Implement tender state machine in backend: DOCUMENTS_UPLOADED → PROCESSING_OCR → OCR_COMPLETE → EXTRACTING_CRITERIA → SCHEMA_PENDING_REVIEW → SCHEMA_APPROVED → DEBARMENT_CHECK → EVALUATING → VERDICTS_COMPUTED → HITL_PENDING → EVALUATION_COMPLETE → REPORT_GENERATED
    - Enforce all guard conditions from design state transition table
    - Ensure frontend reflects state changes via polling or status endpoint
    - _Requirements: 4.1, 5.1, 9.1_

  - [x] 20.2 Wire reproducibility pipeline
    - Implement `POST /tenders/{id}/reproduce` endpoint
    - Store all inputs required for reproduction: original documents (SHA-256), ETS at evaluation time, LLM Stub prompts/responses, extracted values, officer decisions
    - Re-run evaluation from stored inputs and compare output (excluding timestamps)
    - _Requirements: 18.1, 18.2, 18.3_

  - [ ]* 20.3 Write property test for evaluation reproducibility
    - **Property 15: Evaluation reproducibility (round-trip)**
    - **Validates: Requirements 18.2**
    - Generate completed evaluations with stored inputs, verify re-run produces identical output excluding timestamp fields

  - [ ]* 20.4 Write integration tests for end-to-end flows
    - Test happy path: Upload → Extract → Approve → Evaluate → Auto-commit → Export
    - Test HITL flow: Evaluate → Medium confidence → Officer confirms → Audit recorded
    - Test debarment flow: Upload bidder → Match → Pipeline halted → Officer reviews
    - Test entity mismatch: Parent-company docs → Mismatch → Mandatory review
    - Test GFR enforcement: Mandatory FAIL → Override disabled → Confirm only
    - Test CPM accumulation: Officer decision → Precedent stored → Next evaluation shows it
    - _Requirements: 5.1, 7.6, 8.6, 9.1, 10.2, 11.1_

- [x] 21. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after major milestones
- Property tests validate the 17 universal correctness properties from the design document
- The backend is implemented layer-by-layer following pipeline dependency order (L5 first since audit is used by all layers, then L1→L4)
- Frontend implementation begins only after all API endpoints are functional
- Demo data is loaded last to exercise the complete pipeline
