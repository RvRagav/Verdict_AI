# Requirements Document

## Introduction

VerdictAI is an Explainable AI Procurement Intelligence Platform for government tender evaluation. It automates tender eligibility evaluation with criterion-aware logic, explainable verdicts, human-in-the-loop (HITL) review, and institutional memory via Criterion Precedent Memory (CPM). The system is a pure local, self-contained prototype with no external dependencies — no cloud services, no blockchain, no external APIs. Everything runs locally using React + Vite + TailwindCSS (frontend), Python FastAPI (backend), and SQLite (database).

## Glossary

- **VerdictAI_System**: The complete local application comprising frontend, backend, and database layers
- **Document_Intelligence_Layer (L1)**: The subsystem responsible for PDF parsing, image pre-processing, and OCR text extraction
- **ETS_Builder (L2)**: The subsystem that assembles the Effective Tender Specification from base NIT and corrigenda
- **Evidence_Extractor (L3)**: The subsystem that locates and extracts evidence values per (bidder, criterion) pair
- **Evaluation_Engine (L4)**: The subsystem that computes verdicts, confidence scores, and routing decisions
- **Audit_Ledger (L5)**: The append-only immutable event log subsystem
- **CPM (Criterion Precedent Memory)**: The institutional memory system that stores officer interpretation precedents for reuse
- **HITL (Human-in-the-Loop)**: The review interface where officers confirm or override system verdicts
- **ETS (Effective Tender Specification)**: The version-controlled tender specification produced by applying corrigenda to the base NIT
- **NIT (Notice Inviting Tender)**: The original tender document published by the procuring authority
- **Corrigendum**: An amendment document that modifies one or more clauses of the original NIT
- **GFR (General Financial Rules 2017)**: The regulatory framework governing government procurement criteria hierarchy
- **CVC (Central Vigilance Commission)**: The anti-corruption body whose debarment list must be checked pre-evaluation
- **Confidence_Router**: The component within L4 that assigns cases to auto-commit, HITL review, or mandatory review routes
- **Schema_Review_Gate**: The mandatory officer approval step before bidder evaluation begins
- **LLM_Stub**: A local mock/simulated LLM service providing structured responses for criterion extraction and evaluation
- **OCR_Engine**: The local Tesseract-based optical character recognition component
- **Criterion_Type**: One of five classifications — numeric_threshold, categorical_presence, temporal_recency, composite, qualitative_assessment
- **Entity_Matcher**: The component that detects company name mismatches between bidder registration and submitted documents
- **Auto_Commit_Route**: The routing path for high-confidence (≥0.85) deterministic verdicts requiring no officer action
- **HITL_Review_Route**: The routing path for medium-confidence (0.50–0.84) verdicts requiring officer confirmation
- **Mandatory_Review_Route**: The routing path for low-confidence (<0.50) or flagged verdicts requiring explicit officer decision

## Requirements

### Requirement 1: PDF Document Ingestion

**User Story:** As a procurement officer, I want to upload PDF tender documents and bidder submissions, so that the system can process them for evaluation.

#### Acceptance Criteria

1. WHEN a PDF file is uploaded, THE Document_Intelligence_Layer SHALL parse the file and extract page images and embedded text content
2. WHEN a scanned PDF is uploaded, THE Document_Intelligence_Layer SHALL apply deskew correction for rotation up to fifteen degrees using Hough line detection
3. WHEN a scanned PDF is uploaded, THE Document_Intelligence_Layer SHALL apply adaptive binarisation using Sauvola thresholding to handle uneven illumination
4. WHEN a scanned PDF page contains rubber stamp ink overlapping text, THE Document_Intelligence_Layer SHALL isolate the stamp region via red-channel separation and recover underlying text
5. WHEN a scanned PDF page has resolution below 300 DPI, THE Document_Intelligence_Layer SHALL normalise the resolution to 300 DPI
6. WHEN pre-processing is complete, THE Document_Intelligence_Layer SHALL produce normalised document objects containing page number, bounding box coordinates, text content, OCR confidence score, and source format per word
7. IF a PDF file is corrupted or unreadable, THEN THE Document_Intelligence_Layer SHALL return a descriptive error message identifying the failure reason

### Requirement 2: OCR Text Extraction

**User Story:** As a procurement officer, I want accurate text extraction from scanned documents, so that eligibility values can be reliably identified.

#### Acceptance Criteria

1. WHEN a pre-processed page image is ready, THE OCR_Engine SHALL extract text using Tesseract 5 with word-level confidence scores
2. THE OCR_Engine SHALL compute page-level OCR confidence as the length-weighted mean of per-word confidence values
3. WHEN OCR extraction is complete, THE OCR_Engine SHALL output structured results containing text, bounding box coordinates, and confidence per word
4. IF page-level OCR confidence falls below 0.50, THEN THE OCR_Engine SHALL flag the page as degraded quality for downstream routing

### Requirement 3: Effective Tender Specification Assembly

**User Story:** As a procurement officer, I want the system to assemble the complete tender specification from the base NIT and all corrigenda, so that evaluation uses the correct and current criteria.

#### Acceptance Criteria

1. WHEN a base NIT document is uploaded, THE ETS_Builder SHALL parse and extract all eligibility criteria with clause references
2. WHEN one or more corrigenda are uploaded, THE ETS_Builder SHALL apply amendments in chronological order to produce the Effective Tender Specification
3. THE ETS_Builder SHALL classify each extracted criterion into exactly one of five types: numeric_threshold, categorical_presence, temporal_recency, composite, or qualitative_assessment
4. THE ETS_Builder SHALL annotate each criterion with a GFR_override_permitted flag, originating document reference, and clause reference
5. WHEN a corrigendum amends a criterion, THE ETS_Builder SHALL retain both the original and amended values with amendment history
6. WHEN the NIT text contains amendment indicators such as "as amended" or "refer addendum" without a corresponding corrigendum file, THE ETS_Builder SHALL block evaluation and notify the officer of the missing corrigendum
7. IF criterion extraction produces ambiguous or incomplete results, THEN THE ETS_Builder SHALL flag the affected criteria for officer review during schema review

### Requirement 4: Mandatory Schema Review Gate

**User Story:** As a procurement officer, I want to review and approve the extracted criterion schema before any bidder evaluation begins, so that extraction errors are caught once rather than propagating to all bidders.

#### Acceptance Criteria

1. THE Schema_Review_Gate SHALL prevent any bidder evaluation from starting until the officer has explicitly approved the criterion schema
2. WHEN the officer reviews the schema, THE Schema_Review_Gate SHALL display each criterion with its type, threshold, measurement period, acceptable evidence types, and GFR_override_permitted status
3. WHEN a corrigendum has been applied, THE Schema_Review_Gate SHALL display a diff view showing original and amended values side by side
4. WHEN the officer approves the schema, THE Audit_Ledger SHALL record the approval event with officer identifier and timestamp
5. WHEN CPM precedents exist for ambiguous criterion language, THE Schema_Review_Gate SHALL display up to three matching precedents from the same department with tender identifiers and dates
6. WHEN the officer modifies a criterion interpretation during schema review, THE CPM SHALL store the decision as a new precedent entry

### Requirement 5: CVC Debarment Pre-Check

**User Story:** As a procurement officer, I want the system to check bidders against the CVC debarment list before evaluation, so that debarred entities are identified immediately.

#### Acceptance Criteria

1. WHEN a bidder submission is received, THE Evaluation_Engine SHALL cross-reference the bidder PAN and company name against the local CVC debarred entities list before any criterion evaluation begins
2. WHEN a match is found in the debarment list, THE Evaluation_Engine SHALL halt the evaluation pipeline for that bidder and route the case to mandatory review
3. WHEN a debarment match is detected, THE Audit_Ledger SHALL record the match event with the matched entity details and timestamp
4. IF no debarment match is found, THEN THE Evaluation_Engine SHALL proceed with criterion-level evaluation for that bidder

### Requirement 6: Evidence Extraction

**User Story:** As a procurement officer, I want the system to locate and extract relevant evidence from bidder documents for each criterion, so that evaluation is based on traceable source data.

#### Acceptance Criteria

1. WHEN evaluating a numeric_threshold criterion, THE Evidence_Extractor SHALL locate the relevant document type, extract the value with fiscal year and unit using table-aware parsing, and verify the fiscal year against the measurement period
2. WHEN evaluating a categorical_presence criterion, THE Evidence_Extractor SHALL search for the certificate type by name and regulatory synonyms, and extract the registration number and validity date
3. WHEN evaluating a temporal_recency criterion, THE Evidence_Extractor SHALL extract project value, completion date, and project description from completion certificates
4. WHEN evaluating a qualitative_assessment criterion, THE Evidence_Extractor SHALL retrieve semantically relevant passages and any CPM precedents for similar language from the same department
5. THE Evidence_Extractor SHALL output a structured result containing value, source document, page number, bounding box coordinates, OCR confidence, extraction confidence, and entity match flag for each (bidder, criterion) pair
6. WHEN the extracted company name does not match the registered bidder name, THE Entity_Matcher SHALL flag the mismatch and route the case to mandatory review regardless of numeric confidence

### Requirement 7: Evaluation Engine and Confidence Routing

**User Story:** As a procurement officer, I want the system to evaluate each criterion with type-specific logic and route cases appropriately based on confidence, so that high-confidence cases are automated and ambiguous cases are surfaced for review.

#### Acceptance Criteria

1. WHEN evaluating a numeric_threshold criterion with extraction confidence at or above 0.85 and no flags, THE Evaluation_Engine SHALL auto-commit the verdict
2. WHEN evaluating a numeric_threshold criterion with extraction confidence below 0.75, THE Evaluation_Engine SHALL route to HITL review regardless of the comparison result
3. WHEN evaluating a categorical_presence criterion where the document is found with a current validity date, THE Evaluation_Engine SHALL assign a PASS verdict
4. WHEN evaluating a categorical_presence criterion where the validity date is unreadable, THE Evaluation_Engine SHALL route to HITL review rather than assuming invalidity
5. WHEN evaluating a qualitative_assessment criterion where the LLM_Stub produces a FAIL verdict, THE Evaluation_Engine SHALL route to HITL review regardless of confidence score
6. WHEN confidence is at or above 0.85 with no entity flags and a deterministic criterion, THE Confidence_Router SHALL assign the Auto_Commit_Route
7. WHEN confidence is between 0.50 and 0.84 inclusive, THE Confidence_Router SHALL assign the HITL_Review_Route
8. WHEN confidence is below 0.50 or an explicit flag is present, THE Confidence_Router SHALL assign the Mandatory_Review_Route
9. WHEN any mandatory criterion produces a FAIL verdict, THE Confidence_Router SHALL assign the Mandatory_Review_Route regardless of confidence score

### Requirement 8: HITL Review Interface

**User Story:** As a procurement officer, I want a single-screen review card with complete context, so that I can make informed decisions on ambiguous cases without navigating between views.

#### Acceptance Criteria

1. THE HITL review interface SHALL display five components on a single screen: criterion details, evidence with bounding box overlay, system analysis, CPM context, and decision controls
2. WHEN displaying evidence for a scanned document, THE HITL review interface SHALL show the original page image with the extracted region highlighted by a bounding box overlay
3. THE HITL review interface SHALL display the system analysis including verdict, confidence score, evaluation method, and routing reason in plain language
4. WHEN CPM precedents exist for the criterion, THE HITL review interface SHALL display up to three matching precedents from the same department with tender identifiers and dates
5. WHEN the officer selects Override, THE HITL review interface SHALL require a structured reason selection and optional free-text note before submission
6. WHEN the criterion has GFR_override_permitted set to false and the verdict is FAIL, THE HITL review interface SHALL disable the Override button and display the applicable GFR rule number in its place
7. WHEN the officer confirms or overrides a verdict, THE Audit_Ledger SHALL record the decision with officer identifier, timestamp, and reason

### Requirement 9: Never-Silent Disqualification Guarantee

**User Story:** As a procurement officer, I want assurance that no bidder is automatically disqualified without my explicit confirmation, so that due process is maintained.

#### Acceptance Criteria

1. WHEN any mandatory criterion produces a FAIL verdict, THE VerdictAI_System SHALL route the case to mandatory review before committing the verdict to the evaluation record
2. THE VerdictAI_System SHALL require explicit officer confirmation for every mandatory-criterion FAIL before the disqualification is recorded
3. THE VerdictAI_System SHALL never auto-commit a disqualification based on LLM_Stub interpretation alone
4. WHEN an officer confirms a mandatory-criterion FAIL, THE Audit_Ledger SHALL record the confirmation as a distinct event type with officer identifier and timestamp

### Requirement 10: GFR 2017 Compliance Enforcement

**User Story:** As a procurement officer, I want the system to enforce GFR 2017 override rules in code, so that mandatory criteria cannot be improperly overridden.

#### Acceptance Criteria

1. THE VerdictAI_System SHALL store a GFR_override_permitted flag for each criterion in the ETS
2. WHEN a criterion has GFR_override_permitted set to false and the verdict is FAIL, THE HITL review interface SHALL prevent the officer from overriding the verdict
3. WHEN a criterion has GFR_override_permitted set to true, THE HITL review interface SHALL allow the officer to override the verdict with a structured reason
4. WHEN an officer overrides a verdict on a criterion adjacent to GFR-mandatory thresholds, THE VerdictAI_System SHALL require second-officer confirmation before the override is committed
5. WHEN a second-officer confirmation is required, THE Audit_Ledger SHALL record both the initial override and the confirmation with respective officer identifiers and timestamps

### Requirement 11: Criterion Precedent Memory (CPM)

**User Story:** As a procurement officer, I want the system to accumulate and reuse interpretation precedents from past evaluations, so that criterion interpretation becomes consistent and institutionally grounded.

#### Acceptance Criteria

1. WHEN an officer confirms or overrides a verdict during HITL review, THE CPM SHALL generate a precedent entry containing criterion text, resolved interpretation, department, tender category, verdict, officer action, anonymised officer identifier, and tender identifier
2. WHEN an officer confirms a criterion interpretation during schema review, THE CPM SHALL store the decision as a new precedent entry
3. WHEN a criterion contains ambiguous language, THE CPM SHALL query for matching precedents from the same department and category using text similarity
4. WHEN matching CPM precedents exist, THE VerdictAI_System SHALL present up to three precedents with frequency of prior application and supporting tender identifiers
5. WHILE insufficient CPM data exists for calibration, THE Confidence_Router SHALL apply conservative defaults with auto-commit ceiling of 0.90 and mandatory review floor of 0.60
6. THE CPM SHALL use SQLite FTS5 for text similarity search across stored precedent entries

### Requirement 12: Immutable Audit Ledger

**User Story:** As a procurement officer, I want a complete, tamper-evident audit trail of every system and officer action, so that evaluations survive legal challenge and CVC inquiry.

#### Acceptance Criteria

1. THE Audit_Ledger SHALL record every system event as an append-only entry including: document received, OCR completed, corrigendum linked, schema approved, debarment checked, evidence extracted, verdict computed, case routed, officer decision recorded, and report generated
2. THE Audit_Ledger SHALL enforce append-only semantics using a SQLite trigger that raises an exception on any UPDATE or DELETE operation on the audit table
3. WHEN an evaluation report is exported, THE Audit_Ledger SHALL compute a SHA-256 hash of the complete audit trail and embed it in the exported PDF report
4. THE Audit_Ledger SHALL maintain a local SHA-256 hash chain linking each entry to the previous entry for tamper detection
5. IF any attempt is made to UPDATE or DELETE an audit record, THEN THE Audit_Ledger SHALL reject the operation and log the attempted violation

### Requirement 13: Evaluation Report Export

**User Story:** As a procurement officer, I want to export a complete evaluation report as a PDF, so that I have a formal record for filing and audit purposes.

#### Acceptance Criteria

1. WHEN the officer requests a report export, THE VerdictAI_System SHALL generate a PDF containing the complete evaluation summary per bidder with criterion-level verdicts, confidence scores, evidence references, and officer decisions
2. THE exported PDF SHALL include the SHA-256 hash of the audit trail as both a human-readable string and a machine-readable QR code
3. THE exported PDF SHALL include source references linking each verdict to a specific document, page number, and bounding box coordinates
4. WHEN an officer override was recorded, THE exported PDF SHALL prominently display the override with the structured reason and authorising officer identifier

### Requirement 14: Local LLM Stub for Criterion Extraction and Evaluation

**User Story:** As a developer, I want a local mock LLM service that provides structured responses, so that the system can demonstrate criterion extraction and qualitative evaluation without external API dependencies.

#### Acceptance Criteria

1. THE LLM_Stub SHALL accept structured prompts and return structured JSON responses simulating criterion extraction from tender documents
2. THE LLM_Stub SHALL accept evaluation prompts for qualitative_assessment criteria and return verdict, confidence, and reasoning in structured format
3. THE LLM_Stub SHALL include pre-configured responses for the four demo scenarios: criterion extraction with corrigendum, stamp-obscured certificate, entity mismatch, and CPM precedent injection
4. THE LLM_Stub SHALL operate entirely locally with no network calls to external services
5. WHEN the LLM_Stub receives a prompt not matching any pre-configured scenario, THE LLM_Stub SHALL return a default response with medium confidence and a flag indicating simulated output

### Requirement 15: Frontend User Interface

**User Story:** As a procurement officer, I want a web-based interface to manage tender evaluations, so that I can upload documents, review criteria, and make decisions through a browser.

#### Acceptance Criteria

1. THE VerdictAI_System SHALL provide a React-based frontend served via Vite with TailwindCSS styling
2. THE frontend SHALL provide a document upload interface accepting PDF files for NIT, corrigenda, and bidder submissions
3. THE frontend SHALL provide a schema review interface displaying extracted criteria with type, threshold, and GFR status
4. THE frontend SHALL provide a HITL review queue displaying pending cases ordered by routing priority
5. THE frontend SHALL provide a dashboard showing evaluation progress per tender with counts of auto-committed, pending review, and completed cases
6. THE frontend SHALL communicate with the backend exclusively via REST API calls to the local FastAPI server

### Requirement 16: Backend API

**User Story:** As a developer, I want a FastAPI backend that orchestrates all processing layers, so that the frontend can trigger and monitor evaluations through a clean API.

#### Acceptance Criteria

1. THE VerdictAI_System SHALL provide a Python FastAPI backend exposing REST endpoints for document upload, ETS assembly, schema review, evaluation triggering, HITL decisions, and report export
2. THE backend SHALL use SQLite as the sole database with no external database dependencies
3. THE backend SHALL use SQLite FTS5 for text search functionality replacing pgvector similarity search
4. THE backend SHALL be startable with a single command: uvicorn or python main.py
5. IF a request contains invalid input, THEN THE backend SHALL return a structured error response with HTTP status code and descriptive message

### Requirement 17: Demo Data and Sample Documents

**User Story:** As a reviewer, I want pre-loaded sample documents and demo scenarios, so that I can evaluate the system without sourcing real procurement documents.

#### Acceptance Criteria

1. THE VerdictAI_System SHALL include sample PDF documents for the four demo scenarios: a base NIT with corrigendum, a scanned CA certificate with stamp obscuration, a bidder submission with parent-company entity mismatch, and a tender with ambiguous criterion language matching CPM precedents
2. THE VerdictAI_System SHALL include a pre-loaded CVC debarment list stub for demo cross-referencing
3. THE VerdictAI_System SHALL include a CPM bootstrap corpus with synthetic precedents for common government criterion types
4. WHEN the system starts for the first time, THE VerdictAI_System SHALL initialise the SQLite database with the demo data and sample configurations

### Requirement 18: Reproducibility

**User Story:** As an auditor, I want to regenerate any past evaluation from stored inputs, so that I can verify the evaluation was conducted correctly.

#### Acceptance Criteria

1. THE VerdictAI_System SHALL store all inputs required for evaluation reproduction: original documents with SHA-256 checksums, the ETS at evaluation time, all LLM_Stub prompts and responses, all extracted values with source coordinates, and all officer decisions with timestamps
2. WHEN a reproduction is requested for a completed evaluation, THE VerdictAI_System SHALL regenerate the evaluation from stored inputs and produce output identical to the original report excluding timestamp fields
3. THE VerdictAI_System SHALL store the LLM_Stub version identifier in every audit record to ensure prompt-response reproducibility
