# VerdictAI v2 — Backend Architecture

## Design Principles

1. **Defensibility-first** — every operation produces an evidence trail an officer can defend years later
2. **AI deliberately weak** — the system never auto-decides; it surfaces options for the officer
3. **Reproducibility is sacred** — every decision is reproducible byte-for-byte
4. **Bedrock-only** — no OpenRouter, no fallback. Claude 3.5 Sonnet via boto3 in us-east-1
5. **SQLite + JSONB** — structured tables for relational data, JSON columns for flexible payloads
6. **Append-only audit** — DB triggers prevent UPDATE/DELETE on audit tables

---

## Database Schema (complete redesign)

### Core entities

```sql
-- ─── 1. tenders ─── the top-level workspace
CREATE TABLE tenders (
    id              TEXT PRIMARY KEY,            -- UUID v4
    tender_number   TEXT UNIQUE NOT NULL,        -- e.g. "CRPF/DG/PROV-VI/SEC-EQUIP/2024-25/001"
    title           TEXT NOT NULL,
    department      TEXT NOT NULL,
    category        TEXT NOT NULL,
    estimated_cost  INTEGER,                     -- in rupees
    emd_amount      INTEGER,                     -- earnest money deposit
    bid_open_date   TEXT,                        -- ISO 8601
    bid_close_date  TEXT,
    state           TEXT NOT NULL,               -- state machine value
    metadata        TEXT,                        -- JSON: any extra unstructured data
    created_by      TEXT NOT NULL,               -- officer ID
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX idx_tenders_state ON tenders(state);
CREATE INDEX idx_tenders_dept ON tenders(department);

-- ─── 2. documents ─── any file attached to a tender (NIT, corrigendum, bidder doc)
CREATE TABLE documents (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id),
    bidder_id       TEXT REFERENCES bidders(id),  -- null for NIT/corrigendum
    doc_type        TEXT NOT NULL,                -- nit | corrigendum | bidder_submission | certificate
    filename        TEXT NOT NULL,
    file_path       TEXT NOT NULL,                -- relative path on disk
    sha256_hash     TEXT NOT NULL,
    page_count      INTEGER NOT NULL DEFAULT 0,
    avg_ocr_conf    REAL NOT NULL DEFAULT 0,
    processing_state TEXT NOT NULL,               -- pending | processing | complete | error
    metadata        TEXT,                         -- JSON: format, dpi, etc.
    uploaded_at     TEXT NOT NULL
);
CREATE INDEX idx_documents_tender ON documents(tender_id);
CREATE INDEX idx_documents_bidder ON documents(bidder_id);

-- ─── 3. pages ─── one row per page of every document
CREATE TABLE pages (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(id),
    page_number     INTEGER NOT NULL,
    image_path      TEXT,
    raw_text        TEXT,
    ocr_confidence  REAL NOT NULL DEFAULT 0,
    width_px        INTEGER,
    height_px       INTEGER,
    processing_notes TEXT
);
CREATE INDEX idx_pages_doc ON pages(document_id);

-- ─── 4. word_objects ─── per-word OCR with bounding boxes (for source highlighting)
CREATE TABLE word_objects (
    id              TEXT PRIMARY KEY,
    page_id         TEXT NOT NULL REFERENCES pages(id),
    text_content    TEXT NOT NULL,
    x_min           REAL NOT NULL,
    y_min           REAL NOT NULL,
    x_max           REAL NOT NULL,
    y_max           REAL NOT NULL,
    confidence      REAL NOT NULL,
    source_engine   TEXT NOT NULL                 -- tesseract | embedded
);
CREATE INDEX idx_words_page ON word_objects(page_id);

-- ─── 5. bidders ─── companies bidding on a tender
CREATE TABLE bidders (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id),
    company_name    TEXT NOT NULL,
    pan_number      TEXT,
    gstin           TEXT,
    cin             TEXT,
    udyam_number    TEXT,
    contact_email   TEXT,
    state           TEXT NOT NULL,                -- pending | preliminary_passed | preliminary_failed | evaluated | excluded
    debarment_state TEXT NOT NULL DEFAULT 'unchecked',  -- unchecked | clear | flagged | confirmed_debarred
    debarment_checked_at TEXT,
    metadata        TEXT,                         -- JSON: any extra fields
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_bidders_tender ON bidders(tender_id);

-- ─── 6. criteria ─── extracted eligibility criteria from NIT
CREATE TABLE criteria (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id),
    criterion_text  TEXT NOT NULL,
    criterion_type  TEXT NOT NULL,                -- numeric_threshold | categorical_presence | temporal_recency | qualitative_assessment | composite
    threshold_value TEXT,                         -- JSON: type-specific structured value
    is_mandatory    INTEGER NOT NULL,             -- 0 or 1
    gfr_rule_number TEXT,
    gfr_override_permitted INTEGER NOT NULL,
    source_doc_id   TEXT REFERENCES documents(id),
    source_clause_ref TEXT,                       -- e.g. "Clause 4.1"
    source_page     INTEGER,
    source_bbox     TEXT,                         -- JSON: {x_min, y_min, x_max, y_max}
    amendment_history TEXT,                       -- JSON array of {value, corrigendum_id, date}
    acceptable_evidence TEXT,                     -- JSON array of doc types
    measurement_period TEXT,
    state           TEXT NOT NULL DEFAULT 'extracted',  -- extracted | edited | approved
    approved_by     TEXT,
    approved_at     TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_criteria_tender ON criteria(tender_id);

-- ─── 7. document_checklist ─── what docs each bidder is REQUIRED to submit
CREATE TABLE document_checklist (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id),
    document_label  TEXT NOT NULL,                -- "EMD Receipt" | "Affidavit" | "GST Certificate"
    is_mandatory    INTEGER NOT NULL,
    matches_doc_type TEXT,                        -- which uploaded doc_type satisfies this
    extracted_from  TEXT REFERENCES documents(id),  -- the NIT doc this requirement came from
    source_page     INTEGER,
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_checklist_tender ON document_checklist(tender_id);

-- ─── 8. checklist_responses ─── per-bidder response to each checklist item
CREATE TABLE checklist_responses (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL,
    bidder_id       TEXT NOT NULL REFERENCES bidders(id),
    checklist_item_id TEXT NOT NULL REFERENCES document_checklist(id),
    state           TEXT NOT NULL,                -- present | missing | partial | unclear
    matched_doc_id  TEXT REFERENCES documents(id),
    confidence      REAL NOT NULL DEFAULT 0,
    officer_decision TEXT,                        -- accepted | rejected | null (not yet reviewed)
    officer_id      TEXT,
    decided_at      TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(tender_id, bidder_id, checklist_item_id)
);

-- ─── 9. evaluations ─── per (bidder × criterion) verdict
CREATE TABLE evaluations (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id),
    bidder_id       TEXT NOT NULL REFERENCES bidders(id),
    criterion_id    TEXT NOT NULL REFERENCES criteria(id),

    -- Verdict & confidence (the AI never auto-applies these; officer confirms)
    verdict         TEXT NOT NULL,                -- PASS | FAIL | REVIEW
    confidence      REAL NOT NULL,
    confidence_breakdown TEXT,                    -- JSON: ocr/extraction/entity/composite (mosaic)

    -- Routing
    route           TEXT NOT NULL,                -- auto_commit | hitl_review | mandatory_review
    routing_reason  TEXT,                         -- human-readable explanation

    -- Evidence
    extracted_value TEXT,                         -- JSON: type-specific extracted data
    source_doc_id   TEXT REFERENCES documents(id),
    source_page     INTEGER,
    source_bbox     TEXT,                         -- JSON: bbox

    -- Dual-branch results
    rules_branch    TEXT,                         -- JSON: rules engine output
    llm_branch      TEXT,                         -- JSON: LLM output
    dissent_branch  TEXT,                         -- JSON: devil's advocate output
    branch_agreement TEXT,                        -- agree | partial | disagree
    branch_agreement_score REAL,

    -- Anomaly / smell test
    anomalies       TEXT,                         -- JSON array of {type, severity, message}
    entity_match_flag INTEGER NOT NULL DEFAULT 0,

    -- Officer-grade explanation (for the UI)
    explanation     TEXT,                         -- JSON: {headline, detail, facts, source_ref, confidence_note, next_action}

    -- Officer decision
    state           TEXT NOT NULL,                -- pending_review | auto_committed | resolved
    officer_decision TEXT,                        -- confirmed | overridden | null
    officer_id      TEXT,
    structured_reason TEXT,                       -- e.g. "data_extraction_error" | "domain_context_override"
    reason_text     TEXT,
    decided_at      TEXT,

    -- Two-officer lock
    requires_second_officer INTEGER NOT NULL DEFAULT 0,
    second_officer_id TEXT,
    second_officer_decision TEXT,                 -- approve | reject | null
    second_officer_at TEXT,

    -- Reproducibility
    llm_prompt_hash TEXT,                         -- SHA-256 of the LLM prompt for cache lookup
    pipeline_version TEXT NOT NULL,               -- e.g. "v2.0.0" — pinned for reproducibility

    created_at      TEXT NOT NULL,
    resolved_at     TEXT
);
CREATE INDEX idx_evaluations_tender ON evaluations(tender_id);
CREATE INDEX idx_evaluations_state ON evaluations(state);
CREATE INDEX idx_evaluations_route ON evaluations(route);
CREATE UNIQUE INDEX idx_evaluations_unique ON evaluations(tender_id, bidder_id, criterion_id);

-- ─── 10. llm_invocations ─── every Bedrock call logged for reproducibility
CREATE TABLE llm_invocations (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT REFERENCES tenders(id),
    invocation_type TEXT NOT NULL,                -- criterion_extraction | qualitative_eval | entity_disambig | dissent | chat | translate
    prompt_hash     TEXT NOT NULL,                -- SHA-256 of (system + user) — for cache lookup
    prompt_content  TEXT NOT NULL,                -- full prompt as sent
    response_content TEXT NOT NULL,               -- full response as received
    model_id        TEXT NOT NULL,                -- e.g. "anthropic.claude-3-5-sonnet-20241022-v2:0"
    region          TEXT NOT NULL,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    latency_ms      INTEGER,
    error           TEXT,
    timestamp       TEXT NOT NULL
);
CREATE INDEX idx_llm_hash ON llm_invocations(prompt_hash);
CREATE INDEX idx_llm_tender ON llm_invocations(tender_id);

-- ─── 11. audit_events ─── append-only hash-chained log
CREATE TABLE audit_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,                -- many: see audit_event_type enum
    event_data      TEXT NOT NULL,                -- JSON: event-specific payload
    actor           TEXT NOT NULL,                -- officer ID or "system"
    timestamp       TEXT NOT NULL,
    prev_hash       TEXT NOT NULL,                -- 64-char hex
    entry_hash      TEXT NOT NULL                 -- 64-char hex
);
CREATE INDEX idx_audit_tender ON audit_events(tender_id);
CREATE INDEX idx_audit_type ON audit_events(event_type);

-- Append-only triggers — block UPDATE and DELETE
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;

-- ─── 12. decision_replays ─── snapshot of UI state at moment of decision (Time Capsule)
CREATE TABLE decision_replays (
    id              TEXT PRIMARY KEY,
    evaluation_id   TEXT NOT NULL REFERENCES evaluations(id),
    officer_id      TEXT NOT NULL,
    snapshot        TEXT NOT NULL,                -- JSON: {visible_evidence, ai_response, page_image_url, bbox, criterion_text}
    timestamp       TEXT NOT NULL
);

-- ─── 13. precedents (CPM) ─── institutional memory
CREATE TABLE precedents (
    id              TEXT PRIMARY KEY,
    criterion_text  TEXT NOT NULL,                -- the criterion text (for similarity search)
    criterion_type  TEXT NOT NULL,
    department      TEXT NOT NULL,
    category        TEXT NOT NULL,
    resolved_interpretation TEXT NOT NULL,        -- how this was decided
    verdict         TEXT NOT NULL,
    officer_action  TEXT NOT NULL,                -- confirmed | overridden
    officer_id      TEXT NOT NULL,
    tender_id       TEXT REFERENCES tenders(id),
    criterion_id    TEXT REFERENCES criteria(id),
    embedding       BLOB,                         -- vector embedding for semantic search
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_precedents_dept_cat ON precedents(department, category);

-- ─── 14. anomaly_flags ─── smell test outputs
CREATE TABLE anomaly_flags (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL,
    bidder_id       TEXT REFERENCES bidders(id),
    flag_type       TEXT NOT NULL,                -- round_number | address_collision | date_proximity | pan_format_mismatch | etc.
    severity        TEXT NOT NULL,                -- low | medium | high
    message         TEXT NOT NULL,
    evidence_data   TEXT,                         -- JSON
    state           TEXT NOT NULL DEFAULT 'open', -- open | reviewed | dismissed
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_anomaly_tender ON anomaly_flags(tender_id);

-- ─── 15. officer_endorsements ─── who else has decided similar cases
-- (computed from precedents but cached for fast UI display)
CREATE TABLE officer_endorsements (
    id              TEXT PRIMARY KEY,
    criterion_text_hash TEXT NOT NULL,            -- hash of normalized criterion text
    officer_ids     TEXT NOT NULL,                -- JSON array
    last_updated    TEXT NOT NULL
);

-- ─── 16. tender_chats ─── per-tender Copilot conversation history
CREATE TABLE tender_chats (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id),
    role            TEXT NOT NULL,                -- user | assistant | system
    content         TEXT NOT NULL,
    citations       TEXT,                         -- JSON array of {doc_id, page, bbox, text}
    officer_id      TEXT,                         -- null for assistant messages
    llm_invocation_id TEXT REFERENCES llm_invocations(id),
    timestamp       TEXT NOT NULL
);
CREATE INDEX idx_chats_tender ON tender_chats(tender_id);

-- ─── 17. checks_to_have_done ─── "Question I Should Have Asked" prompts
CREATE TABLE post_review_checks (
    id              TEXT PRIMARY KEY,
    evaluation_id   TEXT NOT NULL REFERENCES evaluations(id),
    check_text      TEXT NOT NULL,                -- "Did you verify GSTIN matches PAN?"
    check_type      TEXT NOT NULL,                -- entity_consistency | regulatory_check | etc.
    answered_by     TEXT,
    answer          TEXT,                         -- yes | no | not_applicable
    answered_at     TEXT,
    created_at      TEXT NOT NULL
);
```

---

## State Machines

### Tender state machine

```
DRAFT
  └─→ DOCUMENTS_PENDING (after metadata saved)
        └─→ DOCUMENTS_PROCESSING (after first doc upload)
              └─→ DOCUMENTS_READY (all OCR complete)
                    └─→ CRITERIA_EXTRACTING (after /process trigger)
                          └─→ CRITERIA_PENDING_REVIEW
                                └─→ CRITERIA_APPROVED (officer signs off)
                                      └─→ CHECKLIST_PENDING
                                            └─→ PRELIMINARY_DONE
                                                  └─→ EVALUATING
                                                        └─→ EVALUATIONS_COMPUTED
                                                              └─→ HITL_PENDING (if any need review)
                                                                    └─→ EVALUATION_COMPLETE
                                                                          └─→ REPORT_GENERATED
                                                                                └─→ FINALIZED
```

### Evaluation state machine

```
pending_review ─→ resolved (officer confirms)
              ─→ pending_second_officer (if requires_second_officer)
                  ─→ resolved (second officer approves)
                  ─→ pending_review (second officer rejects)
auto_committed ─→ (terminal)
```

---

## API Endpoints (REST)

### Tender lifecycle

```
POST   /api/v1/tenders                      Create tender (metadata only)
GET    /api/v1/tenders                      List all tenders for current officer
GET    /api/v1/tenders/:id                  Get full tender state
PATCH  /api/v1/tenders/:id                  Update metadata
DELETE /api/v1/tenders/:id                  Soft-delete (audit-logged)

GET    /api/v1/tenders/:id/state            Get state machine position + progress %
POST   /api/v1/tenders/:id/transition       Move to next state (validates preconditions)
```

### Documents

```
POST   /api/v1/tenders/:id/documents        Upload document (multipart)
GET    /api/v1/tenders/:id/documents        List documents
GET    /api/v1/documents/:id                Get document metadata
GET    /api/v1/documents/:id/serve          Serve PDF for inline viewer (auth-gated)
GET    /api/v1/documents/:id/page/:n        Serve page image (PNG)
GET    /api/v1/documents/:id/page/:n/words  Word objects for highlighting
DELETE /api/v1/documents/:id                Soft-delete
```

### Bidders

```
POST   /api/v1/tenders/:id/bidders          Register bidder
GET    /api/v1/tenders/:id/bidders          List bidders
PATCH  /api/v1/bidders/:id                  Update bidder metadata
POST   /api/v1/bidders/:id/debarment-check  Run debarment check
```

### Processing pipeline

```
POST   /api/v1/tenders/:id/process          Run OCR on all docs
GET    /api/v1/tenders/:id/process/status   Real-time progress (server-sent events)
POST   /api/v1/tenders/:id/extract-criteria Run L2 ETS builder
POST   /api/v1/tenders/:id/extract-checklist Extract document checklist from NIT
```

### Criteria

```
GET    /api/v1/tenders/:id/criteria         List extracted criteria
PATCH  /api/v1/criteria/:id                 Edit criterion (during review)
POST   /api/v1/criteria/:id/approve         Approve single criterion
POST   /api/v1/tenders/:id/criteria/approve Approve all criteria (gate)
GET    /api/v1/criteria/:id/precedents      "Precedent Constellation" data
```

### Checklist (preliminary examination)

```
GET    /api/v1/tenders/:id/checklist        Get checklist matrix (bidder × required doc)
POST   /api/v1/tenders/:id/checklist/run    Auto-match uploaded docs against checklist
POST   /api/v1/checklist-responses/:id/decide  Officer accepts/rejects per cell
POST   /api/v1/tenders/:id/preliminary/finalize  Lock preliminary examination
```

### Evaluation

```
POST   /api/v1/tenders/:id/evaluate         Run detailed eval for all responsive bidders
GET    /api/v1/tenders/:id/evaluate/status  Real-time progress (SSE)
GET    /api/v1/tenders/:id/matrix           Comparative matrix (bidders × criteria)
GET    /api/v1/evaluations/:id              Full evaluation detail
POST   /api/v1/evaluations/:id/decide       Officer confirms/overrides
POST   /api/v1/evaluations/:id/dissent      Run "Dissent Mode" (devil's advocate)
GET    /api/v1/evaluations/:id/replay       Time Capsule Replay snapshot
GET    /api/v1/evaluations/:id/checks       "Question I Should Have Asked" prompts
POST   /api/v1/post-review-checks/:id/answer Officer answers a post-review check
```

### Anomalies (Smell Test)

```
GET    /api/v1/tenders/:id/anomalies        List all anomaly flags
POST   /api/v1/anomalies/:id/dismiss        Officer dismisses a flag
POST   /api/v1/tenders/:id/anomalies/run    Re-run anomaly detection
```

### Audit & Reproducibility

```
GET    /api/v1/tenders/:id/audit            Audit trail (paginated)
GET    /api/v1/tenders/:id/audit/stream     Server-sent events for live audit
POST   /api/v1/tenders/:id/reproduce        Reproducibility check
GET    /api/v1/tenders/:id/replay/:eval_id  Replay a specific decision
POST   /api/v1/tenders/:id/report           Generate TEC report PDF
GET    /api/v1/reports/:id/download         Download generated report
```

### Copilot (live chat)

```
POST   /api/v1/tenders/:id/chat             Send message; returns streaming response (SSE)
GET    /api/v1/tenders/:id/chat/history     Get conversation history
DELETE /api/v1/tenders/:id/chat/clear       Clear conversation
```

### Translation (Vernacular Mode)

```
POST   /api/v1/translate                    Translate text (Bedrock-powered)
                                            Body: {text, source_lang, target_lang}
```

### Officer endorsements

```
GET    /api/v1/criteria/:id/endorsements    Who else has decided similar criteria
```

---

## Service Layer (Python modules)

```
backend/
├── api/                       FastAPI route handlers (thin)
│   ├── tenders.py
│   ├── documents.py
│   ├── bidders.py
│   ├── criteria.py
│   ├── checklist.py
│   ├── evaluation.py
│   ├── anomalies.py
│   ├── audit.py
│   ├── chat.py
│   └── reports.py
│
├── core/                      Pure business logic (no I/O)
│   ├── state_machine.py       Tender + evaluation state transitions
│   ├── confidence.py          Confidence breakdown + routing rules
│   ├── verdict_engine.py      Verdict computation per criterion type
│   └── audit_chain.py         Hash chain logic
│
├── pipeline/                  Multi-step processing
│   ├── l1_ocr.py              Document → pages → words
│   ├── l2_criterion_extract.py NIT → criteria + checklist
│   ├── l3_evidence_extract.py Bidder docs → per-criterion evidence
│   ├── l4_evaluate.py         Verdict + routing + explanation
│   ├── l5_anomaly_smell.py    Smell test (round numbers, etc.)
│   ├── l6_dissent.py          Devil's advocate AI
│   └── l7_post_checks.py      "Question I Should Have Asked"
│
├── ai/
│   ├── bedrock_client.py      boto3 invoke_model wrapper
│   ├── prompts.py             All system prompts (versioned)
│   ├── streaming.py           SSE-friendly streaming helper
│   └── cached_invocation.py   Reproducibility via prompt_hash lookup
│
├── services/
│   ├── document_service.py    File handling, OCR orchestration
│   ├── bidder_service.py      Debarment checks
│   ├── checklist_service.py   Auto-matching uploaded docs to checklist
│   ├── precedent_service.py   CPM (institutional memory) operations
│   ├── chat_service.py        Copilot context assembly
│   ├── replay_service.py      Time Capsule snapshot reconstruction
│   ├── translation_service.py Vernacular mode
│   └── report_service.py      TEC PDF generation
│
├── database/
│   ├── connection.py
│   ├── schema.py              All CREATE TABLE + triggers
│   ├── migrations/            Forward-only migrations
│   └── seed.py                Demo data seed
│
├── utils/
│   ├── pdf_utils.py
│   ├── image_processing.py
│   ├── ocr_utils.py
│   ├── hash_utils.py
│   └── docx_utils.py
│
├── config.py
└── main.py                    FastAPI app + middleware
```

---

## Bedrock Integration

### Model
- ID: `anthropic.claude-3-5-sonnet-20241022-v2:0`
- Region: `us-east-1`
- Auth: default credential chain (ADA from terminal)

### Pattern: every Bedrock call goes through one wrapper

```python
# backend/ai/bedrock_client.py

def invoke(
    invocation_type: str,        # for logging + cache scoping
    system: str,
    user: str,
    tender_id: str | None = None,
    schema_hint: str = "",
    streaming: bool = False,
    cache_lookup: bool = True,   # for reproducibility
    conn: sqlite3.Connection | None = None,
) -> BedrockResponse:
    """
    1. Compute prompt_hash
    2. If cache_lookup and we have a previous response with this hash → return it
    3. Otherwise, call boto3.invoke_model (or invoke_model_with_response_stream)
    4. Log to llm_invocations table (if conn provided)
    5. Return structured response
    """
```

### All prompts in one place: `backend/ai/prompts.py`

Each prompt has:
- A version (e.g. `v2.0.0`)
- A system prompt template
- A user prompt template
- A schema hint (for structured output)

Example:
```python
CRITERION_EXTRACTION_V2 = PromptTemplate(
    version="v2.0.0",
    system="You are a procurement compliance expert. Extract eligibility criteria...",
    user_template="Extract criteria from this NIT:\n\n{nit_text}\n\nReturn JSON:",
    schema_hint='{"criteria": [{"text": str, "type": str, "is_mandatory": bool, ...}]}',
)
```

When the criteria extractor evaluates a tender, it stores `pipeline_version="v2.0.0"` on the evaluation. Reproduce-time looks up the prompt with that version, ensuring byte-identical replay.

---

## Reproducibility Architecture

### Three layers of caching:
1. **Prompt cache** — same prompt_hash → return logged response
2. **Pipeline version pinning** — every evaluation stores `pipeline_version`
3. **Document hash verification** — re-run validates source SHA-256 hashes match

### Reproduce flow:
1. Officer hits "Reproduce evaluation" on tender X
2. Backend loads all evaluations with their `pipeline_version`
3. For each: re-run extraction + verdict using cached LLM responses
4. Compare result hashes against original
5. Return: `match: bool, diffs: [...], byte_identical: bool`

---

## "Confidence Veil" implementation

The `evaluations` table has these fields:
- `verdict: PASS | FAIL | REVIEW`
- `confidence: float`
- `confidence_breakdown: JSON`
- `state: pending_review | auto_committed | resolved`

**Default state is `pending_review` for everything except very-high-confidence + deterministic.** This means:
- The UI shows "I'm 91% confident this passes" not "PASS"
- The officer must click to confirm before it becomes "resolved"
- Auto-commit threshold is intentionally high (0.92+)

This forces the AI to be a colleague, not a judge.

---

## "Dissent Mode" implementation

Pipeline L6 runs a separate Bedrock call with this system prompt:
```
You are a senior procurement officer reviewing an AI's verdict.
Your job is to find any reason this verdict could be WRONG.
Be specific. Cite which document/value/clause makes you doubt the verdict.
If the verdict is PASS, argue why it could be FAIL.
If the verdict is FAIL, argue why it could be PASS.
Output JSON: {dissent: str, severity: low|medium|high, suggested_check: str}
```

Stored in `evaluations.dissent_branch`. Surfaced in the HITL card.

---

## Authentication (minimal for demo)

For the finale demo, we use a **single hardcoded officer ID** input. No real auth.

Production sketch (post-finale):
- SAML SSO with NIC's auth provider
- Officer roles: junior, senior, second-officer-eligible
- Department-scoped tender visibility

---

## Concerns / open questions for review

1. **Streaming SSE for chat** — boto3's `invoke_model_with_response_stream` works; need to wrap it for FastAPI's StreamingResponse
2. **Embedding model** — for precedent semantic search, do we use Bedrock Titan Embeddings or sentence-transformers locally? (Bedrock for consistency, but adds latency)
3. **Tooltip system** — server-side or client-side text? (Client for speed, but want consistency across deployments)
4. **State machine enforcement** — should we use a library like `transitions` or hand-roll? (Hand-roll for clarity)
5. **Anomaly detection rules** — hardcoded list or LLM-driven? (Hybrid: hardcoded for fast known patterns, LLM for novel ones)
