# VerdictAI v2 — Redesign for Grand Finale

## Core Principle
Reduce time from tender submission to TEC decision. Every screen answers: "what do I need to do next?"

## New Backend Architecture

### API Routes (restructured)

```
POST   /api/v1/tenders                    → Create tender with metadata
GET    /api/v1/tenders                    → List all tenders
GET    /api/v1/tenders/:id                → Tender detail + status
PATCH  /api/v1/tenders/:id                → Update tender metadata

POST   /api/v1/tenders/:id/documents      → Upload document (NIT/corrigendum/bidder)
GET    /api/v1/tenders/:id/documents      → List documents
GET    /api/v1/documents/:id/view         → Serve PDF for inline viewer
GET    /api/v1/documents/:id/page/:num    → Serve page image for bbox overlay

POST   /api/v1/tenders/:id/process        → Run OCR + criteria extraction
GET    /api/v1/tenders/:id/criteria       → Get extracted criteria
PATCH  /api/v1/tenders/:id/criteria/:cid  → Edit criterion
POST   /api/v1/tenders/:id/criteria/approve → Approve schema

POST   /api/v1/tenders/:id/bidders        → Register bidder
GET    /api/v1/tenders/:id/bidders        → List bidders

GET    /api/v1/tenders/:id/checklist      → Document checklist matrix
POST   /api/v1/tenders/:id/preliminary    → Run preliminary examination

POST   /api/v1/tenders/:id/evaluate       → Run detailed technical evaluation
GET    /api/v1/tenders/:id/evaluations    → All evaluations (full detail)
GET    /api/v1/tenders/:id/matrix         → Comparative matrix (bidders × criteria)

GET    /api/v1/tenders/:id/hitl           → HITL queue
GET    /api/v1/hitl/:evalId/card          → HITL card detail
POST   /api/v1/hitl/:evalId/decide        → Officer decision

GET    /api/v1/tenders/:id/audit          → Audit trail
POST   /api/v1/tenders/:id/report         → Generate TEC report
POST   /api/v1/tenders/:id/reproduce      → Reproducibility check
```

### New: Document Checklist
Before detailed evaluation, verify all required documents are present per bidder.
Returns a matrix: bidder × required_document → present/missing/partial.

### New: Preliminary Examination
Mark bidders as "technically responsive" or "non-responsive" based on checklist.
Non-responsive bidders are excluded before detailed evaluation.

### New: Comparative Matrix
Single endpoint returns all bidders × all criteria with verdicts, confidence, and source refs.
Frontend renders this as a color-coded table.

### LLM: AWS Bedrock (Claude 3.5 Sonnet)
- Region: us-east-1
- Auth: default credential chain (ADA from terminal)
- Model: anthropic.claude-3-5-sonnet-20241022-v2:0
- Direct boto3 `invoke_model` calls
- No logging to CloudWatch, no traces

## New Frontend Architecture

### Pages (new flow order)
1. `/` — Dashboard (tender list + create)
2. `/tender/:id` — Tender workspace (single page with tabs)
   - Tab: Setup (metadata + NIT upload)
   - Tab: Bidders (register + upload docs)
   - Tab: Checklist (document verification matrix)
   - Tab: Criteria (extracted + editable)
   - Tab: Evaluation (comparative matrix)
   - Tab: Review (HITL decisions)
   - Tab: Report (generate + download)
   - Tab: Audit (hash chain viewer)

### Design System
- Light theme, white background
- System font stack
- 16px base, min 14px
- Blue primary, green success, red danger, amber warning
- Pencil borders (1px #E5E7EB)
- Cards: white, subtle shadow
- Buttons: solid fill, 44px min height, color-coded by action type
- Hover: scale(1.02) + shadow
- Accessibility: text resize, high contrast toggle, keyboard nav, ARIA labels

### Key Component: PDF Viewer with Source Highlighting
- Uses react-pdf (pdf.js wrapper)
- Split view: AI explanation left, PDF right
- Click any AI reference → PDF scrolls to page, yellow highlight on bbox
- Officer can zoom, pan, navigate pages
