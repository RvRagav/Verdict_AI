# Completeness audit — VerdictAI vs the brief, the bar-raiser, and the panel

> Audit pass: walked `backend/` (22 service modules, 23 API routers, 7 verifier
> drivers, 7 pipeline modules) and `frontend/` (8 tab views, 22 components).
> Cross-referenced against `bar-raiser-decomposition.md` (16 phases × 70
> sub-tasks), `domain-truth.md`, `module-architecture.md`, `jury-research.md`,
> and the original problem brief. Findings below cite real file paths and
> line numbers wherever a verdict is asserted.

---

## A. End-to-end demo flow check

Walking *DIG Verma logs in → TEC report finalised + Defence Vault sealed*.

| # | Step | Status | Notes |
|---|---|---|---|
| 1 | Officer "logs in" via header dropdown picker | ⚠️ | `frontend/src/components/OfficerPicker.tsx` is a header shim, not auth. Comments at lines 2-4 own this; no SSO, no password. Audit chain *does* capture officer-id on every action via `X-Officer-ID` header (`backend/main.py:101`). For the demo this reads as honest; for production it is a known stub. |
| 2 | Dashboard shows dossiers + reviewing-counts | ✅ | `frontend/src/pages/Dashboard.tsx` — hero copy adapts to count of `HITL_PENDING` tenders (lines 32-43). |
| 3 | Open new dossier → fill NIT metadata | ✅ | `NewTender.tsx` + `Overview` tab. |
| 4 | Upload NIT PDF (typed or scanned) → OCR | ✅ | `backend/pipeline/document_processing.py` orchestrates Bedrock-vision (`backend/ai/vision_ocr.py`) with Tesseract fallback (`backend/utils/ocr.py`). Demo data already includes degraded scan + CA-stamped cert in `backend/demo_data/pages/`. |
| 5 | Officer clicks "Extract criteria" → L2 LLM run | ✅ | `criteria_service.extract_for_tender` → `pipeline/criterion_extraction.py`; v1 row written to `criterion_versions` (append-only, lines 139-148). |
| 6 | Review/edit/approve criteria | ✅ | `CriteriaView.tsx` inline edit + Approve button. Edits write a new `criterion_versions` row (`criteria_service.py:122`). |
| 7 | Register bidders + upload bidder packs | ✅ | `DocumentsView.tsx` UploadZone + bidder registration. |
| 8 | Click "Approve all & evaluate" | ✅ | Cascades transitions, runs auto-match for each bidder, runs evaluations (`CriteriaView.tsx:53-69`). |
| 9 | Evaluation matrix populates with Confidence Veil cells | ✅ | `Matrix.tsx` + `EvaluationDrawer.tsx`. Cell tooltip is decision-support ("AI suggests this satisfies …", line 113). |
| 10 | Cross-bidder smell test surfaces (address, format, dups) | ✅ | `EvaluationView.tsx` "Cross-bidder signals" card. Rules in `backend/core/smell_test.py`. |
| 11 | Sequential-DD / common-signatory / cover-letter overlap | ❌ | Searched repo — zero hits. Bar-raiser flagged 2.6, 12.3, 12.7, 5.4 (~1.5 days work, named in `module-architecture.md:421`). Phase 12 headline feature is half-built. |
| 12 | Open Verifiers tab → run all 7 external checks | ✅ (with caveat) | `VerifiersView.tsx`; matrix renders. Every cell stamps `verified_via: "stub"` (or `"local-registry"` for debarment). UI honestly badges this (`VerifiersView.tsx:74-77`). |
| 13 | GST live-on-bid-date check | ⚠️ | Format + bid-date math runs in stub (`backend/verifiers/gst.py:51-100`); live branch returns `unreachable` with explicit message (line 113). Demo-credible, panel-fragile. |
| 14 | UDIN/FRN actually verified against ICAI | ⚠️ | Format-only stubs (`udin.py:54-78`, `frn.py:50-77`). Bar-raiser's 7.1/7.2 still F at runtime; modeled as stubs in code. |
| 15 | Officer overrides a cell → reason captured | ✅ | `EvaluationDrawer.tsx:191-243`; `evaluations_decide` audit event. |
| 16 | Mandatory FAIL → concurrence request opens automatically | ✅ | `concurrence_service.open_request` is wired; `Inbox.tsx` shows real second-officer inbox with concur/reject. |
| 17 | Per-cell officer comment thread | ✅ | `CommentThread.tsx` mounted in drawer at line 156; `comments` API live. |
| 18 | Corrigendum upload + amendment apply | ⚠️ | Backend service complete (`corrigendum_service.py`), criterion version bumps. UI "diff view" + apply-amendment button only partial (Module 5 noted ⬜ at `module-architecture.md:323`). |
| 19 | Bidder responses tagged with criterion version they responded against | ❌ | Searched `backend/**/*.py` for `responded_against\|response_version\|effective_date` → 0 hits. `evaluations.criterion_version` records what *we* evaluated against, not what the *bidder* responded to. The Calcutta HC Dec 2023 story (`bar-raiser-decomposition.md:223`) cannot be told. |
| 20 | Co-author TEC report → edit sections, regenerate, finalise | ✅ | `ReportView.tsx` + `tec_drafts` API; `authored_by` chips render on each section. PDF written via `report_service._render_draft_pdf` (line 232). |
| 21 | TEC PDF carries 3 officer DSC stamps | ❌ | Bar-raiser 13.6 still D. Only sha256 stamp (`report_service.py:89`); no PKCS#7. Module-architecture lines 364-367 list this as ⬜. |
| 22 | Defence Vault sealed (ZIP + manifest + reproduce script) | ✅ | `vault_service.py` + `08_reproduce.py`. ReportView "Generate vault" CTA opens the ZIP. |
| 23 | "Reproduce on a fresh machine" claim | ⚠️ | `reproduce_service.py` re-walks evaluations using cached prompt-hash, returns diff. Vault's `08_reproduce.py` verifies *file hashes*, not LLM output (own admission at bar-raiser 16.6). README still over-claims. |
| 24 | Audit chain verify endpoint walks every event | ✅ | `AuditView.tsx` "Re-verify" button; `audit_chain.verify_chain` re-hashes prev→current chain; DB triggers block UPDATE/DELETE (schema.py around the `audit_events` block). |

**Net flow:** demo reaches the end. The gaps that hurt are #11 (cartel rules
named in our own domain doc), #19 (corrigendum-version-tagging on the bidder
side), #21 (DSC), and the soft #1/#23 over-claims if not pre-disclosed.

---

## B. Brief-by-brief conformance

The original brief has 7 hard requirements. Each below: **what's built · what's
weak · file paths**.

### 1. Extract criteria from the NIT

- **Built.** `backend/pipeline/criterion_extraction.py` runs an L2 Bedrock pass that
  produces criterion text + type + threshold + measurement period + GFR rule.
  Append-only history at `criterion_versions` table (`backend/database/schema.py:586-619`).
  Bar-raiser graded this **A**.
- **Weak.** Internal-NIT-contradictions (Phase 4.5), "similar-work" interpretation
  (4.4), department-precedent recall (4.6) all unattempted. Precedent table
  exists (`schema.py:415-436`) but no service writes to it; only `evaluation_service`
  + `reproduce_service` *read its count* (lines 72, 156).

### 2. Parse heterogeneous bidder docs

- **Built.** Dual stack: native PDF text via `backend/utils/pdf_io.py`, scan/photo
  routed to Bedrock-vision (`backend/ai/vision_ocr.py`), Tesseract fallback
  (`backend/utils/ocr.py`). DOCX, JPG, PNG, TIFF accepted. Demo data includes a
  tilted phone-photo, a stamp-overlapped CA cert, and a corrigendum bundle in
  `backend/demo_data/pages/`.
- **Weak.** Hindi/regional-language line-ordering not tuned (named in
  `module-architecture.md:80`). Stamp/seal authenticity classifier (Phase 11)
  is honest F.

### 3. Per-bidder per-criterion verdict (Eligible / Not Eligible / Manual Review with explanation)

- **Built.** `backend/pipeline/verdict.py` produces `verdict ∈ {PASS, FAIL, REVIEW}`,
  `confidence`, `route ∈ {auto_commit, hitl_review, mandatory_review}`,
  Confidence Mosaic, dissent branch, structured `explanation` with headline +
  detail + facts + source_reference + next_action (lines 311-413).
- **Weak.** The matrix cell still renders the bare verdict word (`Matrix.tsx:97-102`)
  — verdict-as-tooltip-string is honest, verdict-as-bold-chip-text reads as AI
  asserting. See section F.

### 4. Never silently disqualify

- **Built.** `_verdict_from_evidence` distinguishes *evidence missing in
  submission* (`extraction_confidence ≥ 0.5` → confident FAIL) from *no docs at
  all* (→ REVIEW) — `backend/pipeline/verdict.py:181-194`. Mandatory FAIL forces
  `mandatory_review` route via `core/confidence.py`. Override flow captures
  reason + opens concurrence request.
- **Weak.** A bidder *missing from the registry* never enters the matrix at all
  — there is no "we couldn't find evidence for this bidder, please clarify"
  surfacing. The branch-disagreement→REVIEW path is solid (`verdict.py:69-75`).

### 5. Handle scanned / photo docs

- **Built.** Vision OCR primary; OCR confidence flows into the Mosaic via
  `breakdown.ocr_quality` (`verdict.py:268`).
- **Weak.** When OCR confidence is below ~0.5, the cell routes to REVIEW
  correctly, but there is no UI affordance to *re-OCR with a higher-DPI render*
  or to manually re-scan a single page. Officer is stuck saying "REVIEW" with
  no recourse.

### 6. End-to-end auditable

- **Built (this is our strongest claim).** Hash-chained `audit_events` with DB
  triggers blocking UPDATE/DELETE (`backend/database/schema.py`). 30+ event
  types registered in `backend/core/audit_chain.py:53-90`. `AuditView.tsx`
  re-walks the chain on demand. Defence Vault ZIP + manifest +
  `08_reproduce.py`. Bar-raiser 16.4 graded **A**.
- **Weak.** Officer identity is a header shim (see flow #1). PKCS#7 / DSC on
  TEC PDF missing (Phase 13.6 still D). `08_reproduce.py` verifies archive
  integrity, not LLM output — README over-claims (Phase 16.6 graded C).

### 7. Decision-support framing (implied "AI assists, officer decides")

- **Built.** Confidence Veil headlines never assert ("I'm 91% confident this
  satisfies …" — `verdict.py:323-330`). Mosaic exposes 7 named confidence
  components. Devil's-advocate dissent runs every cell. Override flow front and
  centre.
- **Weak.** UI still leaks instructive copy (matrix cell verdict word, "auto
  committed" stat label, "Strongest / Weakest" labels in `PreMortemBrief.tsx:91-104`).
  See section F for exact strings + replacements.

---

## C. Bar-raiser regrade

Re-grading every D and F sub-task in `bar-raiser-decomposition.md` based on
what shipped. Verified by reading the cited files.

| # | Sub-task | Before | After | Change driver |
|---|---|---|---|---|
| 1.1 | Envelope condition / dak number | F | **F** | No CPPP/dak metadata captured. Unchanged. |
| 1.2 | CPPP cross-check | F | **F** | No CPPP integration. Unchanged. |
| 1.3 | Witness signature on receipt | F | **F** | Unchanged. |
| 1.4 | Late-bid auto-flag | D | **D** | `bid_close_date` stored; no comparator. Unchanged. |
| 2.1 | Read DD / e-payment receipt | C | **C** | Schema fields exist; no extractor. Unchanged. |
| 2.2 | EMD amount equals NIT-required | F | **F** | Unchanged. |
| 2.3 | EMD validity ≥ bid-validity + buffer | F | **F** | Unchanged. |
| 2.4 | Udyam active + NIC code | D | **C** | `udyam.py` stub validates format + asserts active; NIC code still missing. Slight lift. |
| 2.5 | DD ≠ cheque | F | **F** | Unchanged. |
| 2.6 | **Sequential DDs (CCI 2025 signal)** | F | **F** | Searched repo — zero hits. The single most embarrassing gap; named in our own domain doc. |
| 3.2 | Auto-classify bidder uploads | C | **C** | Unchanged. |
| 3.3 | Suggest "this is probably the GST cert" | C | **C** | Unchanged. |
| 3.4 | Doc degraded → REVIEW not FAIL | D | **C** | `verdict._verdict_from_evidence` distinguishes "no evidence at all" → REVIEW from "evidence missing in present submission" → FAIL (lines 181-194). Bridged. |
| 3.5 | Note unsolicited docs | F | **F** | Unchanged. |
| 4.4 | "Similar work" precedent recall | D | **D** | `precedents` table indexed; no service writes/reads it for HITL surface. Bar-raiser noted no change. |
| 4.5 | Internal NIT contradictions | F | **F** | Unchanged. |
| 4.6 | Recognise prior interpretations | F | **F** | Unchanged. |
| 5.1 | Cover-letter date precedes bid | F | **F** | Unchanged. |
| 5.2 | Cover-letter signatory authority | F | **F** | Unchanged. |
| 5.3 | Cover-letter tone | F | **F** | Unchanged. |
| 5.4 | **Cover-letter verbatim phrasing overlap** | F | **F** | Unchanged. Half-day, A-grade outcome — still our cheapest big win not picked up. |
| 6.1 | PAN 4th-char entity rule | C | **B** | `verifiers/pan.py:73-94` enforces this; mismatch returns `mismatch` with explanation. |
| 6.3 | CIN format + decode | F | **B** | `verifiers/mca.py:46-77` does format check + listing-status + state-code + year decoding. |
| 6.4 | Entity-name reconciliation across PAN/GSTIN/CIN/CA cert | F | **F** | Unchanged. |
| 6.5 | Parent-substitution fraud (Reliance Power pattern) | F | **F** | Smell test has the hook (`parent_company_substitution` flag type at `anomaly_pipeline.py:36`) but no rule writes it. |
| 7.1 | FRN exists on ICAI | F | **D** | `verifiers/frn.py` does format + region inference; live branch returns `unreachable`. Bar-raiser's promised lift to B requires the live API; today it's a credible stub. |
| 7.2 | UDIN registered for cert | F | **D** | Same as 7.1 — stub-mode lifts grade off the floor; live remains future work. |
| 7.3 | CA in practice | F | **F** | Unchanged. |
| 7.4 | CA-firm flagged in prior tender | F | **F** | Unchanged. |
| 7.5 | FY alignment on cert | D | **D** | Unchanged. |
| 8.2 | Standalone vs consolidated | D | **D** | Unchanged. |
| 8.4 | CA cert ↔ audited B/S reconciliation | D | **D** | Unchanged. |
| 8.5 | Multi-year roundness | C | **C** | `detect_round_number()` at `core/smell_test.py:38-58` is single-figure. Unchanged. |
| 9.1 | GST portal lookup | F | **D** | `verifiers/gst.py` stub validates format + status synthesis. Live branch returns `unreachable`. Bar-raiser's B requires live API. |
| 9.2 | GST active on bid-date | F | **C** | The stub *does* anchor the check to `bid_submission_date` (lines 64-72). Active-on-bid-date logic is real; only the live data source is stubbed. |
| 9.3 | GST jurisdiction matches address | F | **F** | Unchanged. |
| 9.4 | GST return-filing status | F | **F** | Unchanged. |
| 10.2 | Verify ordering authority exists | F | **F** | Unchanged. |
| 10.3 | Verify order ref on portal | F | **F** | Unchanged. |
| 10.4 | Market-rate plausibility | F | **F** | Honest F — needs price corpus. |
| 10.5 | Completion dates in NIT window | C | **C** | Unchanged. |
| 10.6 | Officer signature plausibility | F | **F** | Unchanged. |
| 11.1-3 | Stamp / signature visual forensics | F | **F** | Honest F. |
| 12.2 | Common phone / email-domain | C | **C** | Unchanged. |
| 12.3 | Sequential DD numbers | F | **F** | Unchanged — same as 2.6. |
| 12.4 | PDF metadata cluster (author/creator) | C | **C** | Unchanged. |
| 12.5 | Verbatim phrasing overlap | F | **F** | Unchanged — same as 5.4. |
| 12.6 | Common IP at CPPP | F | **F** | Unchanged. |
| 12.7 | Common signatory across bidders | F | **F** | Unchanged. |
| 13.2 | TEC narrative voice | C | **B** | Co-authored draft system live (`tec_drafts` API + `ReportView.tsx`). Section-level edit + revision audit + `authored_by` chip. Falls one short of bar-raiser's predicted A because "narrative voice" still defaults to AI prose unless officer rewrites. |
| 13.5 | Member-vs-member dissent reconciliation | F | **D** | Per-cell `CommentThread.tsx` exists; not a structured dissent-reconciliation flow. |
| 13.6 | PKCS#7 / DSC on PDF | D | **D** | Unchanged — sha256 only. |
| 13.7 | Page numbers + index | C | **C** | Unchanged. |
| 14.1 | GFR rule at override moment | D | **D** | `gfr_rule_number` displayed as a Pill in `CriteriaView.tsx:158`; not surfaced *at* the override moment in the EvaluationDrawer. |
| 14.2 | Override note template + GFR pre-fill | C | **C** | Free-text textarea in drawer. Unchanged. |
| 14.3 | Real second-officer concurrence | D | **A** | `concurrence_service.py` + `Inbox.tsx` are end-to-end. Inbox count badge (`InboxBadge.tsx`). Mirrors decision back onto evaluation row. Bar-raiser's promised lift achieved. |
| 14.4 | Append approval letter to file | F | **F** | Unchanged. |
| 15.1 | Corrigendum diff in UI | D | **D** | Backend complete; UI diff/apply still partial. |
| 15.2 | Bidder response tagged against version | F | **F** | Unchanged — schema does not record which corrigendum version each bidder responded against. The Calcutta HC defensibility hole is open. |
| 15.4 | TEC report footnote on version | D | **D** | Unchanged. |
| 16.2 | Point-in-time criterion-text API | C | **C** | Versions stored, no point-in-time GET. Unchanged. |
| 16.5 | Officer-id stamping with signature | C | **C** | Unchanged. |
| 16.6 | Reproduce script over-claim | C | **C** | README/UI still says "byte-identical" without qualifying the LLM-cache caveat. Unchanged. |

**Net delta from regrade:** 4 items moved up (3.4, 6.3, 14.3 most notably);
no item slid down. Phase 12 (cross-bidder cartel signals) is unchanged and is
the bar-raiser's loudest unfinished business.

---

## D. Jury risk register

Three questions per panel member ranked by likelihood × bite. `/10` = how
confidently we can answer today.

### Dr. Vipul Kumar, IPS (IG, KKS — senior-most)

His lens: *will this lose me a writ petition?*

| # | Question | Confidence /10 |
|---|---|---|
| 1 | "If a disqualified L1 challenges this in CAT, what record do you produce?" | **8/10** — Defence Vault is real, hash-chain verifies, audit walk is live. We *do* have a defensible package. Loses points only on the LLM-reproducibility over-claim. |
| 2 | "Show me where you actually checked CVC + GeM debarment, not just claimed it." | **5/10** — `debarment_registry` table is wired, seed in `seed_demo.py:87`, but in production it's empty unless seeded. No scheduled refresh. The verifier matrix shows `local-registry` provenance honestly; the panel will read that as "not really checked." |
| 3 | "On what page did the model find this fact, and can the officer click to it?" | **9/10** — `SourcePill` + `PDFViewer` with bbox highlight is the strongest demo move we have. |

Average: **7.3/10**. The IG question we're weakest on is debarment-corpus
freshness.

### Chinmay Shekar, AC (junior officer voice)

His lens: *can I actually use this on a Tuesday afternoon?*

| # | Question | Confidence /10 |
|---|---|---|
| 1 | "How long from PDF upload to a usable summary?" | **7/10** — Bedrock vision OCR + L2 extraction is fast on the demo NIT. Real CRPF tenders with 200-page bidder packs untested at scale. |
| 2 | "Walk me through the screen at 11:55 PM on closing day." | **6/10** — Single-screen matrix exists. But there is no "rush queue" prioritisation, no SLA chip, no "you have 45 min before bid-validity expires" warning. EMD/bid-validity tracking is a Module 5 ⬜. |
| 3 | "If I disagree with the AI, can I override and is my reason recorded?" | **9/10** — Override flow + reason capture + audit row is genuinely good (`EvaluationDrawer.tsx:191-244`). |

Average: **7.3/10**. The AC question we're weakest on is the closing-day
pressure UX.

### Rakesh Agarwal, founder, PDG (industry / strategy)

His lens: *is this a product or a one-off prototype?*

| # | Question | Confidence /10 |
|---|---|---|
| 1 | "What's the wedge vs a generic GenAI doc tool?" | **8/10** — Our answer is real: hash-chain audit + Confidence Veil + dual-branch + Defence Vault. Each is in the codebase. The pitch line *"the defensible product is the chain of evidence the AI produces"* lands. |
| 2 | "How does this scale beyond CRPF — BSF, ITBP, state police, GeM?" | **5/10** — Architecturally yes (every CAPF + GFR-bound buyer fits). But there is no tenant model, no multi-org config — `OfficerPicker.tsx:2` shim is single-org. Honest answer: "the architecture generalises; the deployment surface today is single-org." |
| 3 | "What's genuinely novel vs a thin LLM wrapper?" | **7/10** — The combo (append-only chain + DB-trigger-enforced + reproduce-script + verifier driver pattern + criterion-version append-only) is novel. The over-claim risk: he asks "show me byte-identical reproducibility" → today the script verifies archive hashes, not LLM output. |

Average: **6.7/10**. Founder question we're weakest on is multi-tenancy /
scale story.

**Cross-cutting takeaway:** all three converge on auditability. Where they
diverge is timing — IG cares about year-5 defensibility, AC about minute-5
usability, founder about quarter-2 deployment. We answer year-5 best.

---

## E. Top-5 gaps blocking "yes, take this product"

Ranked by ROI = (impact × certainty of demo question) / time-to-fix.

### Gap 1 — Sequential-DD + common-signatory cross-bidder rules

- **Why it matters.** This *is* the CCI 2025 cartel signature, named in our own
  `domain-truth.md:298` as a documented Indian cartel marker. The bar-raiser
  flagged it twice (2.6, 12.7). We extract DD numbers and signatory names on
  the cover letter; we just don't *compare across bidders*.
- **Fix in <8 hours.** Two new rules in `backend/core/smell_test.py` modeled on
  `detect_address_collision` (lines 91-108): collect DD numbers across
  bidders, flag when consecutive integers; collect signatory names, flag when
  the same name appears as Director on bidder A and Authorised Signatory on
  bidder B. New flag types are already declared in
  `anomaly_pipeline.py:30-43`'s `ALLOWED_FLAG_TYPES` (add two).
- **Demo certainty.** Near-100%. Any panel member who reads cartel cases will
  ask.

### Gap 2 — Bidder-response → corrigendum-version tagging (Calcutta HC story)

- **Why it matters.** `bar-raiser-decomposition.md:223` and Module 5 acceptance
  test #1 (`module-architecture.md:301`) both promise the Calcutta HC December
  2023 narrative. Today `evaluations.criterion_version` records what *we*
  evaluated against, not what *bidder X* responded to. If a corrigendum changed
  ₹10 Cr → ₹15 Cr mid-cycle, we can't show the panel which bidders saw v1 vs v2.
- **Fix in <8 hours.** Add `bidder_responded_to_version INTEGER` on
  `documents` table for `bidder_submission` types. Default to "the criterion
  version effective at the document's `uploaded_at`". Surface a chip in
  Verifiers and Bidder card. The data is already there in
  `criterion_versions.created_at`; we just don't join.
- **Demo certainty.** High. Any IPS officer who has seen a writ petition asks.

### Gap 3 — Decision-support copy hardening (matrix cell + Help text)

- **Why it matters.** The Confidence Veil works in the *headline string* but
  the matrix cell still bolds the bare verdict word `PASS / FAIL / REVIEW`
  (`Matrix.tsx:101`). Help text says "A FAIL is never silent" five times
  (`Help.tsx:53, 115`). The panel will read those as the AI deciding. See
  section F.
- **Fix in <8 hours.** Replace the cell's bold-verdict-word with the same
  "AI suggests: satisfies / does not satisfy / unclear" framing the tooltip
  uses. Rewrite Help.tsx FAQ. Total: ~6 string changes.
- **Demo certainty.** High. The IG specifically reads the screen for this.

### Gap 4 — Vault README + reproducibility framing honesty

- **Why it matters.** The bar-raiser already named this (16.6, C). The script
  proves *archive integrity*; the LLM-reproducibility comes from prompt-hash
  caching + frozen model snapshot. If the panel runs `08_reproduce.py` and
  says "is this byte-identical re-evaluation?" we have to walk it back.
- **Fix in <8 hours.** Update Vault README + add a one-line caveat to
  `ReportView.tsx`'s vault card. Add a separate `reproduce_evaluation` button
  in `AuditView.tsx` that calls `reproduce_service.reproduce()` per evaluation
  (the function already exists, just not surfaced).
- **Demo certainty.** Medium-high. The founder will probe this; the IG might.

### Gap 5 — Debarment-registry credibility loop

- **Why it matters.** A panel question "is the GeM debarment list current?"
  has no good answer if the registry is empty in the running demo. Seed +
  badge "as-of" date.
- **Fix in <8 hours.** (a) Make `seed_debarment_registry` always run on
  startup if registry is empty (idempotent). (b) Add `last_refreshed_at` on
  the verifier card → rendering "registry as-of N entries". (c) Add a flagged
  bidder to one of the demo tenders so the matrix shows a real `mismatch`.
- **Demo certainty.** High. The IG asked it explicitly in the jury-research
  doc (`jury-research.md:33`).

---

## F. Decision-support framing audit

5 exact strings where the AI sounds instructive, and the proposed replacement.

### 1. Matrix cell — bold verdict word

- **Now:** `frontend/src/components/Matrix.tsx:99-102`
  ```tsx
  <span className="font-bold">{cell.verdict}</span>
  <span className="text-[11px] opacity-80">{conf}%</span>
  ```
  Renders a bold `PASS` / `FAIL` / `REVIEW` chip. The tooltip is decision-support;
  the cell glance is not.
- **Replace with:** the verb phrase the tooltip already uses, which is shorter
  than people think:
  ```tsx
  <span className="font-semibold">
    {cell.verdict === 'PASS'   ? 'satisfies (suggested)'
   : cell.verdict === 'FAIL'   ? 'does not satisfy (suggested)'
                               : 'unclear (review)'}
  </span>
  ```
  Eliminates the all-caps shouting; the colour stripe (`vc-pass / vc-fail / vc-review`)
  carries the at-a-glance signal.

### 2. Help.tsx — "A FAIL is never silent"

- **Now:** `frontend/src/pages/Help.tsx:53` and again at line 115:
  > "A FAIL is never silent. A criterion the bidder failed to provide evidence
  > for resolves to FAIL only when the document is present but the value is
  > missing."
- **Replace with:** decision-support voice — the AI does not "FAIL" anything,
  the officer signs:
  > "The system never reports a bidder as failed without an officer's signature.
  > When the document is present but the figure is below the threshold, the
  > suggested verdict is 'does not satisfy', and the officer confirms or
  > overrides. Missing or unreadable evidence routes to officer review."

### 3. Pre-Mortem Brief — "Strongest / Weakest"

- **Now:** `frontend/src/components/PreMortemBrief.tsx:91-104`
  ```tsx
  <div className="...uppercase tracking-wide">
    <Trophy size={12} /> Strongest
  </div>
  <div className="text-sm font-semibold text-ink mt-1">{b.strongest_bidder.name}</div>
  ```
  An AI deciding the league table is exactly what the framing forbids.
- **Replace with:** a question the officer answers, not a label the AI assigns:
  > "Most-PASS so far · {name}" / "Most-FAIL so far · {name}" — pure tally,
  > no ranking verb. Or rename to "Bidder with strongest evidence stack" /
  > "Bidder with weakest evidence stack" with explicit "based on cell-counts,
  > not officer judgement" fineprint.

### 4. EvaluationView stat — "Auto-committed"

- **Now:** `frontend/src/pages/tender-space/EvaluationView.tsx:75`
  ```tsx
  <Stat label="Auto-committed" value={... .filter(c => c.route === 'auto_commit').length} tone="soft" />
  ```
  "Auto-committed" reads as "the AI decided and we recorded it without a human."
  Domain-truth principle 1 says we never auto-decide.
- **Replace with:** "AI agrees with itself · {n}" or "High-confidence cells ·
  {n} (officer can still review)". The route name stays in the API; the UI
  label softens.

### 5. Verifiers tab status pill — bare enum

- **Now:** `frontend/src/pages/tender-space/VerifiersView.tsx:208-211`
  ```tsx
  function StatusPill({ status }: { status: string }) {
    const tone = status === 'verified' ? 'success' : ... ;
    return <Pill tone={tone as any}>{status}</Pill>;
  }
  ```
  A pill saying `verified` / `mismatch` reads as the AI passing judgement on
  the bidder.
- **Replace with:** "matches authority record" / "differs from authority
  record" / "could not reach authority". The provenance badge already says
  `stub`, so the officer reads "format-only check, not live."

### Bonus — `report_service.py:259`

- **Now:** TEC PDF renders `Verdict: <b>{ev['verdict']}</b>`. The same fix as
  the matrix cell: render the verb phrase, not the enum word.

---

## G. The Module 4 (HITL) verdict

Where can the officer interfere? Where are they still locked out?

### Three places we've fixed

1. **Cell-level override with structured reason.**
   `EvaluationDrawer.tsx:191-244` exposes Confirm / Override; override mode
   takes a new verdict + free-text reason; the audit row records both.
2. **Per-cell comment thread.**
   `frontend/src/components/CommentThread.tsx` is mounted at line 156 of the
   drawer. Comments persist on the evaluation; survive a Replay snapshot.
3. **Co-authored TEC report.**
   `ReportView.tsx` + `tec_drafts` API give per-section edit, regenerate,
   revision history, finalise. Each section carries an `authored_by` chip
   ('AI draft' / 'Co-authored' / 'Officer-authored') stamped on the PDF
   itself (`report_service._render_draft_pdf:301`).

### Three places they're still locked out

1. **Re-OCR a single page when confidence is low.**
   When `breakdown.ocr_quality < 0.5` the cell routes to REVIEW, but the UI
   has no "re-OCR with higher DPI" affordance. The officer's only options are
   override or stay stuck. `PDFViewer.tsx` is read-only.
2. **Apply / un-apply a corrigendum amendment from the UI.**
   `corrigendum_service.apply_amendment` is wired in the backend but has no
   amendment-apply button; the criterion bumps still happen via API only.
   `module-architecture.md:323` lists this as ⬜.
3. **Resolve member-vs-member dissent.**
   Bar-raiser 13.5: only AI-vs-officer dissent is captured. There is no
   structured "Member A says PASS, Member B says REVIEW; record their
   reasoning side-by-side, escalate to chair" flow. `CommentThread` is the
   workaround, not a fit.

---

## H. The honesty list — what to tell the panel up-front

Five things to disclose before they catch us. Aiming for the "name our gaps
before they do" posture from `bar-raiser-decomposition.md:308`.

1. **The seven external verifiers run in stub mode.**
   GST, PAN, UDIN, FRN, Udyam, MCA — all do format + plausibility checks; the
   live branch is implemented but returns `unreachable` until an env-var is
   flipped per verifier (`VERIFIER_LIVE_GST=1` and similar — see
   `backend/verifiers/registry.py:21-25`). Live mode is a config change, not
   a re-architecture. The UI honestly badges every cell with its provenance.

2. **Officer authentication is a header shim.**
   `OfficerPicker.tsx` sets `X-Officer-ID` on every API call. There is no
   password, no SSO. The audit chain *does* capture the officer-ID on every
   action (`backend/main.py:101`). For a real CRPF deployment this would be
   replaced with the e-Office SSO. For the demo we own this is the auth
   shim and the audit-trail is the substantive guarantee.

3. **"Byte-identical reproducibility" means archive integrity, not LLM
   re-run identity.**
   `08_reproduce.py` re-hashes every file in the vault and confirms a match.
   It does *not* re-call Bedrock. LLM-reproducibility comes from prompt-hash
   caching + frozen model snapshot — they're real but in a different layer.
   The vault README must say so plainly.

4. **TEC PDF carries a sha256 hash but no PKCS#7 / DSC.**
   The hash is tamper-*evidence*; a real DSC would be tamper-*proof*. Path to
   live DSC is short (we already have officer + posting fields; sign with the
   officer's public key on finalise) but not shipped.

5. **CVC / GeM debarment is a local seedable registry, not a live feed.**
   `backend/services/debarment_service.py` reads a SQLite table; the seed
   ships in `seed_demo.py`. There is no scheduled refresh from `cvc.gov.in/punitive-information`
   or `gem.gov.in/blacklisting-of-bidders`. The Verifiers tab badges the
   provenance (`local-registry`); production is a cron job that pulls
   monthly.

Bonus #6: **Cross-bidder cartel rules implemented are 3 of 7 named.** Address
collision, duplicate-document, modification-time-cluster, and PDF-author cluster
land. Sequential-DD, common-signatory, cover-letter-verbatim-overlap, and
common-IP-at-CPPP are bar-raiser-named gaps the panel will probe.

---

## I. Recommendation

**Fix top-3 first, then ship.** The honesty-list posture works only if the
disclosed gaps don't include the panel's headline question. Today our
headline gap (Phase 12 cartel signals — Gap 1) is a *named* CRPF panel
risk; shipping with that hole and disclosing it as "future work" reads as
under-prepared. Gap 2 (Calcutta-HC bidder-response-version tagging) and Gap 3
(decision-support copy hardening on matrix + Help) are likewise high-certainty
demo questions with sub-day fixes. Spend the day. Phase 12 closure plus the
copy hardening shifts our jury averages from 7.3/7.3/6.7 to roughly 8.5/7.5/7.5
without touching live-API integration or DSC. After that, ship as-is and lead
with the honesty list — the audit chain, Defence Vault, dual-branch verdict,
co-authored TEC report and Confidence Veil are *already* the moat the founder
will recognise and the file that the IG will sign.
