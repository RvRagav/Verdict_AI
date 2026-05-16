"""Database schema for VerdictAI.

Constraints:
- Every state column has CHECK(state IN (...)) enumerating valid values
- Every JSON column has CHECK(json_valid(col))
- Foreign keys with explicit ON DELETE behaviour
- Append-only triggers on audit_events (UPDATE/DELETE blocked at the DB level)
- Soft-delete via deleted_at where applicable
- Officer identity is a real foreign key, not a free string

Use create_tables() once at startup; it is idempotent.
"""

from __future__ import annotations

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    """Create every table, index, and trigger. Safe to call repeatedly."""
    conn.executescript(_SCHEMA)
    _apply_migrations(conn)
    conn.commit()


# ─── Idempotent column additions ─────────────────────────────────────────

# SQLite cannot ALTER … ADD COLUMN inside CREATE TABLE IF NOT EXISTS, so
# we keep them here as a list of (table, column, ddl) tuples and check
# the live PRAGMA before applying. Each entry must be *additive only*
# — never drop or rename columns through this path.

_COLUMN_ADDITIONS: list[tuple[str, str, str]] = [
    # ── bidders: EMD + bid validity tracking (gap #5, #6)
    ("bidders", "emd_amount",          "INTEGER"),
    ("bidders", "emd_instrument",      "TEXT"),                   # DD/BG/e-payment
    ("bidders", "emd_instrument_no",   "TEXT"),
    ("bidders", "emd_validity_date",   "TEXT"),
    ("bidders", "emd_exempt",          "INTEGER NOT NULL DEFAULT 0"),
    ("bidders", "emd_exempt_reason",   "TEXT"),
    ("bidders", "bid_validity_until",  "TEXT"),
    ("bidders", "registered_address",  "TEXT"),                    # extracted from registration

    # ── criteria: pointer to current version + amendment provenance
    ("criteria", "current_version",     "INTEGER NOT NULL DEFAULT 1"),
    ("criteria", "last_amended_by",     "TEXT REFERENCES corrigenda(id)"),
    ("criteria", "last_amended_at",     "TEXT"),

    # ── evaluations: which criterion version was evaluated against
    #     (so a future re-extraction or amendment doesn't break audit)
    ("evaluations", "criterion_version", "INTEGER NOT NULL DEFAULT 1"),
    ("evaluations", "concurrence_request_id", "TEXT REFERENCES concurrence_requests(id)"),

    # ── reports: digital signature presence + signed-by list
    ("reports", "signatures_json",     "TEXT CHECK(signatures_json IS NULL OR json_valid(signatures_json))"),
    ("reports", "signed_at",           "TEXT"),

    # ── documents: which criterion-version was effective when the bidder
    #     uploaded this document (Calcutta HC defensibility — Phase 15.2).
    #     Computed at upload time from criterion_versions.created_at.
    ("documents", "criterion_version_at_upload", "INTEGER"),

    # ── officer_comments: AI classification of comment intent
    ("officer_comments", "category",         "TEXT"),
    ("officer_comments", "affects_verdict",   "INTEGER DEFAULT 0"),
    ("officer_comments", "suggested_action",  "TEXT"),
    ("officer_comments", "key_insight",       "TEXT"),
]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply additive column migrations idempotently.

    For each (table, column, ddl) tuple, look up the table's current
    columns via PRAGMA. If the column is missing, add it. Never drops.
    """
    for table, column, ddl in _COLUMN_ADDITIONS:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {r[1] for r in rows}  # row[1] is the column name
        if column in existing:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    _migrate_anomaly_flag_types(conn)


def _migrate_anomaly_flag_types(conn: sqlite3.Connection) -> None:
    """Rebuild anomaly_flags so its CHECK constraint accepts the new
    Phase-12 cartel flag types (sequential_dd, common_signatory,
    cover_letter_overlap). Idempotent — only rebuilds when the existing
    schema doesn't already include them.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='anomaly_flags'"
    ).fetchone()
    if not row or not row[0]:
        return
    sql = row[0]
    if "'sequential_dd'" in sql:
        return  # already migrated

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        # Get column names from the existing table
        col_info = conn.execute("PRAGMA table_info(anomaly_flags)").fetchall()
        colnames = [c[1] for c in col_info]
        col_csv = ",".join(colnames)

        old_rows = conn.execute(f"SELECT {col_csv} FROM anomaly_flags").fetchall()

        conn.execute("DROP INDEX IF EXISTS idx_anomaly_tender")
        conn.execute("DROP INDEX IF EXISTS idx_anomaly_bidder")
        conn.execute("ALTER TABLE anomaly_flags RENAME TO anomaly_flags__old")

        # Recreate from canonical _SCHEMA. Pull out the matching block.
        start = _SCHEMA.find("CREATE TABLE IF NOT EXISTS anomaly_flags")
        if start < 0:
            conn.execute("ALTER TABLE anomaly_flags__old RENAME TO anomaly_flags")
            return
        end = _SCHEMA.find(");", start)
        ddl = _SCHEMA[start:end + 2]
        conn.execute(ddl)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_tender ON anomaly_flags(tender_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_bidder ON anomaly_flags(bidder_id)")

        if old_rows:
            placeholders = ",".join("?" * len(colnames))
            conn.executemany(
                f"INSERT INTO anomaly_flags ({col_csv}) VALUES ({placeholders})",
                [tuple(r) for r in old_rows],
            )
        conn.execute("DROP TABLE anomaly_flags__old")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


_SCHEMA = """
-- ─── Pragmas ─────────────────────────────────────────────────────────────
PRAGMA foreign_keys     = ON;
PRAGMA journal_mode     = WAL;
PRAGMA synchronous      = NORMAL;
PRAGMA busy_timeout     = 5000;


-- ─── officers ─── identities for the lightweight auth picker
CREATE TABLE IF NOT EXISTS officers (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    department      TEXT NOT NULL,
    role            TEXT NOT NULL CHECK(role IN ('junior', 'senior', 'reviewer')),
    created_at      TEXT NOT NULL
);


-- ─── tenders ─── top-level workspace
CREATE TABLE IF NOT EXISTS tenders (
    id              TEXT PRIMARY KEY,
    tender_number   TEXT UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    department      TEXT NOT NULL,
    category        TEXT NOT NULL,
    estimated_cost  INTEGER,
    emd_amount      INTEGER,
    bid_open_date   TEXT,
    bid_close_date  TEXT,
    state           TEXT NOT NULL CHECK(state IN (
                        'DRAFT',
                        'DOCUMENTS_PENDING',
                        'DOCUMENTS_PROCESSING',
                        'DOCUMENTS_READY',
                        'CRITERIA_EXTRACTING',
                        'CRITERIA_PENDING_REVIEW',
                        'CRITERIA_APPROVED',
                        'CHECKLIST_PENDING',
                        'PRELIMINARY_DONE',
                        'EVALUATING',
                        'EVALUATIONS_COMPUTED',
                        'HITL_PENDING',
                        'EVALUATION_COMPLETE',
                        'REPORT_GENERATED',
                        'FINALIZED'
                    )),
    metadata        TEXT CHECK(metadata IS NULL OR json_valid(metadata)),
    created_by      TEXT NOT NULL REFERENCES officers(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    deleted_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_tenders_state ON tenders(state);
CREATE INDEX IF NOT EXISTS idx_tenders_dept ON tenders(department);


-- ─── bidders ─── companies bidding on a tender
CREATE TABLE IF NOT EXISTS bidders (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    company_name    TEXT NOT NULL,
    pan_number      TEXT,
    gstin           TEXT,
    cin             TEXT,
    udyam_number    TEXT,
    contact_email   TEXT,
    state           TEXT NOT NULL CHECK(state IN (
                        'pending',
                        'preliminary_passed',
                        'preliminary_failed',
                        'evaluated',
                        'excluded'
                    )),
    debarment_state TEXT NOT NULL DEFAULT 'unchecked' CHECK(debarment_state IN (
                        'unchecked', 'clear', 'flagged', 'confirmed_debarred'
                    )),
    debarment_checked_at TEXT,
    metadata        TEXT CHECK(metadata IS NULL OR json_valid(metadata)),
    created_at      TEXT NOT NULL,
    deleted_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_bidders_tender ON bidders(tender_id);


-- ─── documents ─── any file attached to a tender
CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    bidder_id       TEXT REFERENCES bidders(id) ON DELETE CASCADE,
    doc_type        TEXT NOT NULL CHECK(doc_type IN (
                        'nit', 'corrigendum', 'bidder_submission',
                        'certificate', 'attachment'
                    )),
    filename        TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    sha256_hash     TEXT NOT NULL,
    page_count      INTEGER NOT NULL DEFAULT 0,
    avg_ocr_conf    REAL NOT NULL DEFAULT 0,
    processing_state TEXT NOT NULL CHECK(processing_state IN (
                        'pending', 'processing', 'complete', 'error'
                    )),
    metadata        TEXT CHECK(metadata IS NULL OR json_valid(metadata)),
    uploaded_at     TEXT NOT NULL,
    deleted_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_documents_tender ON documents(tender_id);
CREATE INDEX IF NOT EXISTS idx_documents_bidder ON documents(bidder_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(doc_type);


-- ─── pages ─── one row per page of every document
CREATE TABLE IF NOT EXISTS pages (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number     INTEGER NOT NULL,
    image_path      TEXT,
    raw_text        TEXT,
    ocr_confidence  REAL NOT NULL DEFAULT 0,
    width_px        INTEGER,
    height_px       INTEGER,
    processing_notes TEXT,
    UNIQUE(document_id, page_number)
);
CREATE INDEX IF NOT EXISTS idx_pages_doc ON pages(document_id);


-- ─── word_objects ─── per-word OCR with bounding boxes (source highlighting)
CREATE TABLE IF NOT EXISTS word_objects (
    id              TEXT PRIMARY KEY,
    page_id         TEXT NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    text_content    TEXT NOT NULL,
    x_min           REAL NOT NULL,
    y_min           REAL NOT NULL,
    x_max           REAL NOT NULL,
    y_max           REAL NOT NULL,
    confidence      REAL NOT NULL,
    source_engine   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_words_page ON word_objects(page_id);
CREATE INDEX IF NOT EXISTS idx_words_bbox ON word_objects(page_id, x_min, y_min);


-- ─── criteria ─── eligibility criteria extracted from the NIT
CREATE TABLE IF NOT EXISTS criteria (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    criterion_text  TEXT NOT NULL,
    criterion_type  TEXT NOT NULL CHECK(criterion_type IN (
                        'numeric_threshold',
                        'categorical_presence',
                        'temporal_recency',
                        'qualitative_assessment',
                        'composite'
                    )),
    threshold_value TEXT CHECK(threshold_value IS NULL OR json_valid(threshold_value)),
    is_mandatory    INTEGER NOT NULL CHECK(is_mandatory IN (0, 1)),
    gfr_rule_number TEXT,
    gfr_override_permitted INTEGER NOT NULL CHECK(gfr_override_permitted IN (0, 1)),
    source_doc_id   TEXT REFERENCES documents(id),
    source_clause_ref TEXT,
    source_page     INTEGER,
    source_bbox     TEXT CHECK(source_bbox IS NULL OR json_valid(source_bbox)),
    amendment_history TEXT CHECK(amendment_history IS NULL OR json_valid(amendment_history)),
    acceptable_evidence TEXT CHECK(acceptable_evidence IS NULL OR json_valid(acceptable_evidence)),
    measurement_period TEXT,
    state           TEXT NOT NULL DEFAULT 'extracted' CHECK(state IN (
                        'extracted', 'edited', 'approved', 'rejected'
                    )),
    approved_by     TEXT REFERENCES officers(id),
    approved_at     TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_criteria_tender ON criteria(tender_id);
CREATE INDEX IF NOT EXISTS idx_criteria_state ON criteria(state);


-- ─── document_checklist ─── what each bidder must submit
CREATE TABLE IF NOT EXISTS document_checklist (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    document_label  TEXT NOT NULL,
    is_mandatory    INTEGER NOT NULL CHECK(is_mandatory IN (0, 1)),
    matches_doc_type TEXT,
    extracted_from  TEXT REFERENCES documents(id),
    source_page     INTEGER,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checklist_tender ON document_checklist(tender_id);


-- ─── checklist_responses ─── per-bidder response per checklist item
CREATE TABLE IF NOT EXISTS checklist_responses (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    bidder_id       TEXT NOT NULL REFERENCES bidders(id) ON DELETE CASCADE,
    checklist_item_id TEXT NOT NULL REFERENCES document_checklist(id) ON DELETE CASCADE,
    state           TEXT NOT NULL CHECK(state IN (
                        'present', 'missing', 'partial', 'unclear'
                    )),
    matched_doc_id  TEXT REFERENCES documents(id),
    confidence      REAL NOT NULL DEFAULT 0,
    officer_decision TEXT CHECK(officer_decision IS NULL OR officer_decision IN (
                        'accepted', 'rejected'
                    )),
    officer_id      TEXT REFERENCES officers(id),
    decided_at      TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    UNIQUE(tender_id, bidder_id, checklist_item_id)
);
CREATE INDEX IF NOT EXISTS idx_checklist_resp_bidder ON checklist_responses(bidder_id);


-- ─── evaluations ─── per (bidder × criterion) verdict
CREATE TABLE IF NOT EXISTS evaluations (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    bidder_id       TEXT NOT NULL REFERENCES bidders(id) ON DELETE CASCADE,
    criterion_id    TEXT NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,

    verdict         TEXT NOT NULL CHECK(verdict IN ('PASS', 'FAIL', 'REVIEW')),
    confidence      REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    confidence_breakdown TEXT CHECK(confidence_breakdown IS NULL OR json_valid(confidence_breakdown)),

    route           TEXT NOT NULL CHECK(route IN (
                        'auto_commit', 'hitl_review', 'mandatory_review'
                    )),
    routing_reason  TEXT,

    extracted_value TEXT CHECK(extracted_value IS NULL OR json_valid(extracted_value)),
    source_doc_id   TEXT REFERENCES documents(id),
    source_page     INTEGER,
    source_bbox     TEXT CHECK(source_bbox IS NULL OR json_valid(source_bbox)),

    rules_branch    TEXT CHECK(rules_branch IS NULL OR json_valid(rules_branch)),
    llm_branch      TEXT CHECK(llm_branch IS NULL OR json_valid(llm_branch)),
    dissent_branch  TEXT CHECK(dissent_branch IS NULL OR json_valid(dissent_branch)),
    branch_agreement TEXT CHECK(branch_agreement IS NULL OR branch_agreement IN (
                        'agree', 'partial', 'disagree'
                    )),
    branch_agreement_score REAL,

    anomalies       TEXT CHECK(anomalies IS NULL OR json_valid(anomalies)),
    entity_match_flag INTEGER NOT NULL DEFAULT 0 CHECK(entity_match_flag IN (0, 1)),

    explanation     TEXT CHECK(explanation IS NULL OR json_valid(explanation)),

    state           TEXT NOT NULL CHECK(state IN (
                        'pending_review',
                        'pending_second_officer',
                        'auto_committed',
                        'resolved'
                    )),
    officer_decision TEXT CHECK(officer_decision IS NULL OR officer_decision IN (
                        'confirmed', 'overridden'
                    )),
    officer_id      TEXT REFERENCES officers(id),
    structured_reason TEXT,
    reason_text     TEXT,
    decided_at      TEXT,

    requires_second_officer INTEGER NOT NULL DEFAULT 0 CHECK(requires_second_officer IN (0, 1)),
    second_officer_id TEXT REFERENCES officers(id),
    second_officer_decision TEXT CHECK(second_officer_decision IS NULL OR second_officer_decision IN (
                        'approve', 'reject'
                    )),
    second_officer_at TEXT,

    extraction_prompt_hash TEXT,
    verdict_prompt_hash    TEXT,
    dissent_prompt_hash    TEXT,
    pipeline_signature_hash TEXT NOT NULL,

    created_at      TEXT NOT NULL,
    resolved_at     TEXT,

    UNIQUE(tender_id, bidder_id, criterion_id)
);
CREATE INDEX IF NOT EXISTS idx_evaluations_tender ON evaluations(tender_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_state ON evaluations(state);
CREATE INDEX IF NOT EXISTS idx_evaluations_route ON evaluations(route);


-- ─── llm_invocations ─── every Bedrock call (the cache + the audit)
CREATE TABLE IF NOT EXISTS llm_invocations (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT REFERENCES tenders(id) ON DELETE SET NULL,
    invocation_type TEXT NOT NULL,
    prompt_hash     TEXT NOT NULL,
    prompt_content  TEXT NOT NULL,
    response_content TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    region          TEXT NOT NULL,
    temperature     REAL NOT NULL,
    max_tokens      INTEGER NOT NULL,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    latency_ms      INTEGER,
    error           TEXT,
    timestamp       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_hash ON llm_invocations(prompt_hash);
CREATE INDEX IF NOT EXISTS idx_llm_tender ON llm_invocations(tender_id);
CREATE INDEX IF NOT EXISTS idx_llm_type ON llm_invocations(invocation_type);


-- ─── audit_events ─── append-only hash-chained log
CREATE TABLE IF NOT EXISTS audit_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    event_data      TEXT NOT NULL CHECK(json_valid(event_data)),
    actor           TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    prev_hash       TEXT NOT NULL,
    entry_hash      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_tender ON audit_events(tender_id);
CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp);

DROP TRIGGER IF EXISTS audit_no_update;
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;

DROP TRIGGER IF EXISTS audit_no_delete;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;


-- ─── decision_replays ─── Time Capsule snapshots
CREATE TABLE IF NOT EXISTS decision_replays (
    id              TEXT PRIMARY KEY,
    evaluation_id   TEXT NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    officer_id      TEXT NOT NULL REFERENCES officers(id),
    snapshot        TEXT NOT NULL CHECK(json_valid(snapshot)),
    timestamp       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_replays_eval ON decision_replays(evaluation_id);


-- ─── precedents ─── institutional memory (FTS5-indexed)
CREATE TABLE IF NOT EXISTS precedents (
    id              TEXT PRIMARY KEY,
    criterion_text  TEXT NOT NULL,
    criterion_type  TEXT NOT NULL,
    department      TEXT NOT NULL,
    category        TEXT NOT NULL,
    resolved_interpretation TEXT NOT NULL,
    verdict         TEXT NOT NULL CHECK(verdict IN ('PASS', 'FAIL', 'REVIEW')),
    officer_action  TEXT NOT NULL CHECK(officer_action IN ('confirmed', 'overridden')),
    officer_id      TEXT NOT NULL REFERENCES officers(id),
    tender_id       TEXT REFERENCES tenders(id) ON DELETE SET NULL,
    criterion_id    TEXT REFERENCES criteria(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_precedents_dept_cat ON precedents(department, category);

CREATE VIRTUAL TABLE IF NOT EXISTS precedents_fts USING fts5(
    criterion_text, resolved_interpretation,
    content='precedents', content_rowid='rowid'
);


-- ─── anomaly_flags ─── Smell Test outputs
CREATE TABLE IF NOT EXISTS anomaly_flags (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    bidder_id       TEXT REFERENCES bidders(id) ON DELETE CASCADE,
    evaluation_id   TEXT REFERENCES evaluations(id) ON DELETE CASCADE,
    flag_type       TEXT NOT NULL CHECK(flag_type IN (
                        'round_number',
                        'address_collision',
                        'date_proximity',
                        'pan_format_mismatch',
                        'gstin_format_mismatch',
                        'parent_company_substitution',
                        'duplicate_document',
                        'suspicious_modification_date',
                        'cross_tender_appearance',
                        'sequential_dd',
                        'common_signatory',
                        'cover_letter_overlap',
                        'benford_violation',
                        'zscore_outlier',
                        'bid_spread_anomaly',
                        'metadata_cluster',
                        'entity_resolution_match',
                        'novel'
                    )),
    severity        TEXT NOT NULL CHECK(severity IN ('low', 'medium', 'high')),
    message         TEXT NOT NULL,
    evidence_data   TEXT CHECK(evidence_data IS NULL OR json_valid(evidence_data)),
    state           TEXT NOT NULL DEFAULT 'open' CHECK(state IN (
                        'open', 'reviewed', 'dismissed', 'confirmed'
                    )),
    reviewed_by     TEXT REFERENCES officers(id),
    reviewed_at     TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_anomaly_tender ON anomaly_flags(tender_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_bidder ON anomaly_flags(bidder_id);


-- ─── tender_chats ─── Copilot conversation history per tender
CREATE TABLE IF NOT EXISTS tender_chats (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    citations       TEXT CHECK(citations IS NULL OR json_valid(citations)),
    officer_id      TEXT REFERENCES officers(id),
    llm_invocation_id TEXT REFERENCES llm_invocations(id),
    timestamp       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chats_tender ON tender_chats(tender_id);


-- ─── post_review_checks ─── "Question I Should Have Asked" prompts
CREATE TABLE IF NOT EXISTS post_review_checks (
    id              TEXT PRIMARY KEY,
    evaluation_id   TEXT NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    check_text      TEXT NOT NULL,
    check_type      TEXT NOT NULL,
    answered_by     TEXT REFERENCES officers(id),
    answer          TEXT CHECK(answer IS NULL OR answer IN ('yes', 'no', 'not_applicable')),
    answered_at     TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_post_checks_eval ON post_review_checks(evaluation_id);


-- ─── reports ─── generated TEC reports
CREATE TABLE IF NOT EXISTS reports (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,
    sha256_hash     TEXT NOT NULL,
    generated_by    TEXT NOT NULL REFERENCES officers(id),
    generated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_tender ON reports(tender_id);


-- ─── verification_results ─── per-bidder × per-authority external check
CREATE TABLE IF NOT EXISTS verification_results (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    bidder_id       TEXT NOT NULL REFERENCES bidders(id) ON DELETE CASCADE,
    verifier_name   TEXT NOT NULL,
    status          TEXT NOT NULL CHECK(status IN (
                        'verified', 'mismatch', 'not_found',
                        'unreachable', 'unknown'
                    )),
    confidence      REAL NOT NULL,
    source_url      TEXT NOT NULL,
    verified_via    TEXT NOT NULL,
    source_snapshot TEXT NOT NULL CHECK(json_valid(source_snapshot)),
    snapshot_sha256 TEXT NOT NULL,
    notes           TEXT,
    verified_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verifications_bidder ON verification_results(bidder_id);
CREATE INDEX IF NOT EXISTS idx_verifications_verifier ON verification_results(verifier_name);


-- ─── officer_comments ─── per-cell threaded notes
CREATE TABLE IF NOT EXISTS officer_comments (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    evaluation_id   TEXT REFERENCES evaluations(id) ON DELETE CASCADE,
    bidder_id       TEXT REFERENCES bidders(id) ON DELETE SET NULL,
    criterion_id    TEXT REFERENCES criteria(id) ON DELETE SET NULL,
    officer_id      TEXT NOT NULL REFERENCES officers(id),
    body            TEXT NOT NULL,
    category        TEXT DEFAULT NULL CHECK(category IN (
                        'observation', 'logic', 'action_required', 'brainstorm', 'concern'
                    )),
    affects_verdict INTEGER DEFAULT 0,
    suggested_action TEXT DEFAULT NULL CHECK(suggested_action IN (
                        're_evaluate', 'verify_document', 'check_with_bidder', 'escalate'
                    )),
    key_insight     TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_eval ON officer_comments(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_comments_tender ON officer_comments(tender_id);


-- ═════════════════════════════════════════════════════════════════════════
-- Sprint A additions — defensibility infrastructure
--
-- The blocks below add:
--   - corrigenda (versioned NIT amendments)
--   - criterion_versions (append-only criterion text history)
--   - debarment_registry (CVC + GeM blacklist seedable)
--   - concurrence_requests (real second-officer inbox)
--   - evidence_citations (forward + reverse source-click index)
--   - tender_briefs (cached Pre-Mortem Brief output)
--   - vaults (Defence Vault exports tracked + sealed)
--
-- The bidder & criterion tables get new columns via the migration block
-- in connection.init_db (since SQLite cannot ALTER TABLE inside CREATE
-- IF NOT EXISTS — we keep this script declarative).
-- ═════════════════════════════════════════════════════════════════════════


-- ─── corrigenda ─── version-controlled NIT amendments
CREATE TABLE IF NOT EXISTS corrigenda (
    id                  TEXT PRIMARY KEY,
    tender_id           TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    document_id         TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    sequence_number     INTEGER NOT NULL,                   -- 1, 2, 3 …
    title               TEXT NOT NULL,
    issued_date         TEXT,
    summary             TEXT,                               -- AI-generated 2-3 line summary
    state               TEXT NOT NULL DEFAULT 'pending_apply' CHECK(state IN (
                            'pending_apply', 'applied', 'superseded', 'rejected'
                        )),
    applied_by          TEXT REFERENCES officers(id),
    applied_at          TEXT,
    created_at          TEXT NOT NULL,
    UNIQUE(tender_id, sequence_number)
);
CREATE INDEX IF NOT EXISTS idx_corrigenda_tender ON corrigenda(tender_id);


-- ─── criterion_versions ─── append-only history of criterion text
-- Every time a criterion is edited/amended a new row is written here.
-- The criteria.* row always reflects the latest. Older versions live here.
CREATE TABLE IF NOT EXISTS criterion_versions (
    id                  TEXT PRIMARY KEY,
    criterion_id        TEXT NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    version             INTEGER NOT NULL,                   -- 1, 2, 3 …
    criterion_text      TEXT NOT NULL,
    criterion_type      TEXT NOT NULL,
    threshold_value     TEXT CHECK(threshold_value IS NULL OR json_valid(threshold_value)),
    is_mandatory        INTEGER NOT NULL CHECK(is_mandatory IN (0, 1)),
    gfr_rule_number     TEXT,
    source_clause_ref   TEXT,
    source_page         INTEGER,
    -- Provenance: who/why this version
    change_source       TEXT NOT NULL CHECK(change_source IN (
                            'extracted', 'officer_edit', 'corrigendum'
                        )),
    corrigendum_id      TEXT REFERENCES corrigenda(id) ON DELETE SET NULL,
    changed_by          TEXT REFERENCES officers(id),
    change_note         TEXT,
    created_at          TEXT NOT NULL,
    UNIQUE(criterion_id, version)
);
CREATE INDEX IF NOT EXISTS idx_crit_versions_crit ON criterion_versions(criterion_id);
CREATE INDEX IF NOT EXISTS idx_crit_versions_corrig ON criterion_versions(corrigendum_id);

-- Append-only — once written, a version is the historical truth
DROP TRIGGER IF EXISTS criterion_versions_no_update;
CREATE TRIGGER criterion_versions_no_update BEFORE UPDATE ON criterion_versions
BEGIN SELECT RAISE(ABORT, 'criterion_versions is append-only'); END;
DROP TRIGGER IF EXISTS criterion_versions_no_delete;
CREATE TRIGGER criterion_versions_no_delete BEFORE DELETE ON criterion_versions
BEGIN SELECT RAISE(ABORT, 'criterion_versions is append-only'); END;


-- ─── debarment_registry ─── CVC + GeM blacklist (seedable)
-- Real product would refresh this from CVC + GeM portals on a schedule.
-- For now we seed it locally; the bidder_service.check_debarment() reads it.
CREATE TABLE IF NOT EXISTS debarment_registry (
    id              TEXT PRIMARY KEY,
    pan_number      TEXT,
    gstin           TEXT,
    company_name    TEXT,
    source          TEXT NOT NULL CHECK(source IN (
                        'cvc', 'gem', 'department', 'court_order', 'other'
                    )),
    reason          TEXT NOT NULL,
    debarred_until  TEXT,                              -- ISO date or NULL = indefinite
    notice_url      TEXT,
    added_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_debar_pan ON debarment_registry(pan_number);
CREATE INDEX IF NOT EXISTS idx_debar_gstin ON debarment_registry(gstin);
CREATE INDEX IF NOT EXISTS idx_debar_name ON debarment_registry(company_name);


-- ─── concurrence_requests ─── second-officer inbox
-- When an evaluation routes mandatory_review, a concurrence_request is
-- created targeting a second officer. They see it in their dashboard.
CREATE TABLE IF NOT EXISTS concurrence_requests (
    id                  TEXT PRIMARY KEY,
    tender_id           TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    evaluation_id       TEXT NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    requested_by        TEXT NOT NULL REFERENCES officers(id),  -- the deciding officer
    target_officer_id   TEXT REFERENCES officers(id),           -- NULL until the system picks
    request_reason      TEXT NOT NULL,
    state               TEXT NOT NULL DEFAULT 'open' CHECK(state IN (
                            'open', 'concurred', 'rejected', 'withdrawn'
                        )),
    decision_note       TEXT,
    decided_at          TEXT,
    decided_by          TEXT REFERENCES officers(id),
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_concur_target ON concurrence_requests(target_officer_id, state);
CREATE INDEX IF NOT EXISTS idx_concur_eval ON concurrence_requests(evaluation_id);


-- ─── evidence_citations ─── word-level link from evaluation to source bbox
-- Forward direction: evaluation → words it relied on (render in PDFViewer).
-- Reverse direction: word → all evaluations that cite it (Active Source-Click).
CREATE TABLE IF NOT EXISTS evidence_citations (
    id              TEXT PRIMARY KEY,
    evaluation_id   TEXT NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_id         TEXT REFERENCES pages(id) ON DELETE CASCADE,
    word_object_id  TEXT REFERENCES word_objects(id) ON DELETE CASCADE,
    quote           TEXT,                                   -- the actual phrase, for display
    role            TEXT NOT NULL CHECK(role IN (
                        'extracted_value',
                        'supporting_quote',
                        'dissent_basis',
                        'anomaly_basis'
                    )),
    confidence      REAL NOT NULL DEFAULT 1.0,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_citations_eval ON evidence_citations(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_citations_word ON evidence_citations(word_object_id);
CREATE INDEX IF NOT EXISTS idx_citations_doc_page ON evidence_citations(document_id, page_id);


-- ─── tender_briefs ─── cached Pre-Mortem Brief
-- One row per tender; regenerated on demand.
CREATE TABLE IF NOT EXISTS tender_briefs (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    brief_json      TEXT NOT NULL CHECK(json_valid(brief_json)),
    pipeline_signature_hash TEXT NOT NULL,
    generated_at    TEXT NOT NULL,
    UNIQUE(tender_id)
);
CREATE INDEX IF NOT EXISTS idx_briefs_tender ON tender_briefs(tender_id);


-- ─── vaults ─── Defence Vault exports
-- Each row records a generated, hash-sealed evidence package.
CREATE TABLE IF NOT EXISTS vaults (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,
    sha256_hash     TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    manifest        TEXT NOT NULL CHECK(json_valid(manifest)),  -- file → sha256 map
    pipeline_signature_hash TEXT NOT NULL,
    generated_by    TEXT NOT NULL REFERENCES officers(id),
    generated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vaults_tender ON vaults(tender_id);


-- ═════════════════════════════════════════════════════════════════════════
-- Sprint M2 additions — Module 4 Human-in-the-Loop infrastructure
--
--   tec_report_drafts          one editable draft per tender (re-generatable)
--   tec_report_sections        per-paragraph state + authored_by
--   tec_section_revisions      append-only diff history per section
--   studio_documents           officer-authored docs from Copilot Studio
--   studio_messages            chat turns inside one Studio doc thread
--
-- The Module 4 promise: AI helps, officer decides, every word that ends
-- up in the file is attributed and diff-tracked.
-- ═════════════════════════════════════════════════════════════════════════


CREATE TABLE IF NOT EXISTS tec_report_drafts (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    state           TEXT NOT NULL CHECK(state IN (
                        'draft', 'finalised', 'superseded'
                    )),
    generated_by    TEXT NOT NULL REFERENCES officers(id),
    generated_at    TEXT NOT NULL,
    finalised_at    TEXT,
    finalised_report_id TEXT REFERENCES reports(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_tec_drafts_tender ON tec_report_drafts(tender_id);


CREATE TABLE IF NOT EXISTS tec_report_sections (
    id              TEXT PRIMARY KEY,
    draft_id        TEXT NOT NULL REFERENCES tec_report_drafts(id) ON DELETE CASCADE,
    section_key     TEXT NOT NULL,           -- e.g. 'header', 'summary', 'bidder.{id}.criterion.{id}'
    section_label   TEXT NOT NULL,           -- human-readable heading
    sort_order      INTEGER NOT NULL,
    body            TEXT NOT NULL,           -- current rendered body (Markdown)
    authored_by     TEXT NOT NULL CHECK(authored_by IN (
                        'ai', 'officer', 'co-authored'
                    )),
    last_edited_by  TEXT REFERENCES officers(id),
    last_edited_at  TEXT NOT NULL,
    UNIQUE(draft_id, section_key)
);
CREATE INDEX IF NOT EXISTS idx_tec_sections_draft ON tec_report_sections(draft_id, sort_order);


-- Append-only revision history. Every save (AI suggestion accepted,
-- officer keystroke save, etc.) writes a row. Earlier versions are
-- never mutated; they are the diff trail the audit chain quotes.
CREATE TABLE IF NOT EXISTS tec_section_revisions (
    id              TEXT PRIMARY KEY,
    section_id      TEXT NOT NULL REFERENCES tec_report_sections(id) ON DELETE CASCADE,
    revision        INTEGER NOT NULL,
    body_before     TEXT,                    -- NULL on the first revision
    body_after      TEXT NOT NULL,
    diff_summary    TEXT,                    -- short description e.g. "officer rewrote opening paragraph"
    change_source   TEXT NOT NULL CHECK(change_source IN (
                        'ai_initial', 'ai_suggestion', 'officer_edit', 'officer_revert'
                    )),
    edited_by       TEXT REFERENCES officers(id),
    edited_at       TEXT NOT NULL,
    UNIQUE(section_id, revision)
);
CREATE INDEX IF NOT EXISTS idx_tec_revisions_section ON tec_section_revisions(section_id, revision);

DROP TRIGGER IF EXISTS tec_revisions_no_update;
CREATE TRIGGER tec_revisions_no_update BEFORE UPDATE ON tec_section_revisions
BEGIN SELECT RAISE(ABORT, 'tec_section_revisions is append-only'); END;
DROP TRIGGER IF EXISTS tec_revisions_no_delete;
CREATE TRIGGER tec_revisions_no_delete BEFORE DELETE ON tec_section_revisions
BEGIN SELECT RAISE(ABORT, 'tec_section_revisions is append-only'); END;


-- ─── studio_documents ─── officer-authored docs from the Document Studio
-- Examples: brief to CO, internal note, vendor query letter. Full chat
-- thread lives in studio_messages. The latest "rendered_body" is what
-- the officer downloads. State 'finalised' freezes the doc.
CREATE TABLE IF NOT EXISTS studio_documents (
    id              TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    officer_id      TEXT NOT NULL REFERENCES officers(id),
    title           TEXT NOT NULL,
    doc_kind        TEXT NOT NULL,           -- 'brief', 'note', 'letter', 'other'
    rendered_body   TEXT NOT NULL,           -- Markdown the user keeps refining
    state           TEXT NOT NULL DEFAULT 'draft' CHECK(state IN (
                        'draft', 'finalised'
                    )),
    file_path       TEXT,                    -- populated on finalise / download
    sha256_hash     TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    finalised_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_studio_docs_tender ON studio_documents(tender_id);
CREATE INDEX IF NOT EXISTS idx_studio_docs_officer ON studio_documents(officer_id);


CREATE TABLE IF NOT EXISTS studio_messages (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES studio_documents(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    -- the rendered_body snapshot the AI produced (for assistant messages)
    rendered_body   TEXT,
    llm_invocation_id TEXT REFERENCES llm_invocations(id),
    timestamp       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_studio_msgs_doc ON studio_messages(document_id, timestamp);
"""
