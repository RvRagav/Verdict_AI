# Module architecture — VerdictAI

> Stop shipping *features*. Start shipping *modules* — six of them. Each
> module has one job, one interface, one set of acceptance tests, and
> one screen the panel can probe.
>
> This document is the contract. Anything we build slots into one of
> these six modules. Anything that doesn't slot — we don't build.

---

## The six modules at a glance

```
                       ┌──────────────────────────────┐
                       │  6. Security & Audit Module  │
                       │  hash chain · DSC · vault    │ ← cross-cutting
                       └──────────────────────────────┘
                                      ↑
   ┌──────────────────────────────────┼──────────────────────────────────┐
   │                                  │                                  │
   │  1. DATA EXTRACTION              │  4. HUMAN-IN-THE-LOOP            │
   │  PDF/DOCX/JPG → text+bboxes      │  Co-author, override, ask,       │
   │  Bedrock-vision OCR              │  comment, nitpick, document      │
   │  Tesseract fallback              │  studio inside Copilot           │
   │                                  │                                  │
   ├──────────────────┬───────────────┼─────────────────┬────────────────┤
   │                  │                                 │                │
   │ 2. DATA          │ 3. INTELLIGENCE                 │ 5. LIFECYCLE   │
   │ CORRECTNESS      │ & ORGANISING                    │ HANDLER        │
   │                  │                                 │                │
   │ External         │ Dual-branch extract             │ State machine  │
   │ verifiers:       │ Verdict + measurement-rule      │ Corrigendum    │
   │  - GST           │ Dissent (devil's advocate)      │ chain          │
   │  - PAN-NSDL      │ Smell test (rules + LLM)        │ File Vault     │
   │  - UDIN/FRN      │ Precedent memory                │ Versioning     │
   │  - MCA21         │ Confidence Mosaic               │ Bid validity   │
   │  - GeM blacklist │ Pre-Mortem Brief                │ EMD tracker    │
   │  - CVC debarment │                                 │                │
   │                  │                                 │                │
   │  pluggable       │                                 │                │
   │  drivers + stubs │                                 │                │
   └──────────────────┴─────────────────────────────────┴────────────────┘
```

The numbers map to *tabs the panel sees during the demo*:

> Tabs in the Tender Space (in order, top-to-bottom in the rail):
> Overview · **Documents (1)** · **File Vault (5)** · **Verifiers (2)** · **Criteria (3)** · **Evaluation (3)** · **Review (4)** · **Report (4)** · **Audit (6)**

---

## Module 1 — Data Extraction

> "We have eyes. We read every format the bidder throws at us."

### Responsibilities (single sentence)
Convert any uploaded file into structured text with per-word bounding
boxes, regardless of format or quality.

### Inputs / Outputs
| Input | Output |
|---|---|
| PDF (text/scan/hybrid), DOCX, JPG, PNG, TIFF | `pages` + `word_objects` rows; sha256 digest; per-word confidence |

### Components
- `backend/utils/pdf_io.py` — text extraction + raster
- `backend/ai/vision_ocr.py` — Bedrock Sonnet vision OCR (primary for scans)
- `backend/utils/ocr.py` — Tesseract fallback
- `backend/pipeline/document_processing.py` — orchestration

### Acceptance tests
1. Typed PDF → 100% text recovery, all words with bboxes
2. JPG photo at 15° tilt with stamp over a figure → ≥85% OCR confidence
3. DOCX → all paragraphs extracted, tables flattened with separators
4. Hindi-mixed PDF → Hindi headings preserved
5. Multi-page PDF → page numbers + image rasters saved

### Demo-time talking point
> "Watch this — same Charlie tilted, stamped phone-photo of a CA cert.
> We don't use Textract or any third-party document service. We send
> the page directly to Claude Sonnet 4.5 vision via Bedrock. Same
> model that does the reasoning later. **No OCR/LLM gap.**"

### Open work
- ✅ Built and verified live
- ⬜ Hindi handling could be sharper (line ordering on bilingual pages)

---

## Module 2 — Data Correctness

> "We don't take the bidder's word for it. We verify against the issuing authority."

This is the module the panel will probe hardest. **Today most of it is
mocked, and that's a feature, not a bug — we own the stubs.**

### Responsibilities (single sentence)
For every claim a bidder makes about an external authority (GST, PAN,
ISO, Udyam, banking, prior-supply), check it against the authority's
own record.

### The driver-stub pattern
Every external verifier is a `Verifier` interface with two
implementations:

```
backend/verifiers/
├── base.py                # Verifier ABC, VerificationResult dataclass
├── gst.py                 # GSTPortalVerifier(live=False) → stub
├── pan.py                 # PANNSDLVerifier(live=False) → stub
├── udin.py                # UDINPortalVerifier(live=False) → stub
├── frn.py                 # ICAIFRNVerifier(live=False) → stub
├── mca.py                 # MCA21Verifier(live=False) → stub
├── udyam.py               # UdyamPortalVerifier(live=False) → stub
└── debarment.py           # CVCGeMVerifier — uses local registry
```

Each verifier exposes:
```python
class Verifier(Protocol):
    name: str
    source_url: str
    live: bool
    def verify(self, *, claim: dict) -> VerificationResult: ...
```

`VerificationResult` carries `status` (verified / mismatch / unreachable / not_found),
`confidence`, `source_snapshot` (what the authority said), `verified_at`,
and `notes`.

### Today (stub mode)
Stubs return deterministic results based on the claim contents:
- GST → "active" if the GSTIN format is valid AND the date math works
- PAN → "valid" if format matches and 4th-character entity-code matches
- UDIN → "registered to FRN X for date Y" — derived from the cert text
- FRN → "in practice" if format AAAAAA matches
- Udyam → "active" if format UDYAM-XX-99-9999999 matches
- Debarment → reads `debarment_registry` table

Each stub clearly logs `verifier=stub source_url=<authority_portal>`
and the UI badges the result with **"verified-via-stub (demo mode)"**
in italic so the panel never thinks we're claiming live integration.

### Tomorrow (live mode)
Drop-in real implementations via env-flagged switching. Live mode
configured per-deployment; stubs remain available for offline demos.

### UI surface — Verifiers tab in Tender Space
A new tab per tender showing the verification matrix:

```
Bidder          GST    PAN    UDIN   FRN    Udyam  Debarment
─────────────────────────────────────────────────────────────
Acme           ✓ live ✓ live ✓ stub ✓ stub ✓ live ✓ clear
Bravo          ✗ exp  ✓ live (n/a)  (n/a) (n/a)  ✓ clear
Charlie        ✓ live ✓ live (n/a)  (n/a) ✓ live ⚠ flagged
```

Click any cell → side panel shows: claim text, source URL, snapshot
of the authority response, verified_at timestamp, hash of the
response so the audit chain can prove what we received.

### Acceptance tests
1. Bidder with valid GSTIN + active date → ✓ verified
2. Bidder with expired GSTIN → ✗ expired with reason
3. Bidder PAN where 4th char is "P" but they're a Pvt Ltd → ⚠ entity-type mismatch
4. Bidder appears in `debarment_registry` → ✗ flagged with notice URL
5. Live mode → real GST portal hit, response stored verbatim
6. Verifier unreachable → not silent — UI shows ⚪ "could not verify, retry"

### Demo-time talking point
> "Module 2 is what tells the panel we're not gullible. The bidder
> claims a GSTIN; we don't trust them — we go to gst.gov.in (in stub
> today, real port tomorrow) and check it on the bid-submission date,
> not today. Same for PAN, UDIN, FRN. Six external sources of truth.
> Each one is a swappable driver."

### Open work — to ship
- ⬜ `backend/verifiers/*` — driver classes (this turn)
- ⬜ `Verifiers` tab in the frontend — matrix + side panel
- ⬜ `audit_events` event type `verification_run`

---

## Module 3 — Intelligence & Organising

> "We reason about the data. We don't just store it."

### Responsibilities (single sentence)
Take the extracted + verified data and produce, per (bidder × criterion),
a Confidence Veil headline + Mosaic + Dissent + routing decision +
precedent context — at the level of a senior officer who has seen 50
similar tenders.

### Components
- `backend/pipeline/criterion_extraction.py` — L2: NIT → criteria with measurement period
- `backend/pipeline/evidence_extraction.py` — L3: dual-branch (regex + LLM) reconciled
- `backend/pipeline/verdict.py` — L4: verdict + Mosaic + Dissent + routing
- `backend/pipeline/anomaly_pipeline.py` — L5: smell test (rules + novel)
- `backend/services/brief_service.py` — Pre-Mortem Brief
- `backend/core/confidence.py` — routing rules
- `backend/services/precedent_service.py` — **[gap]** institutional memory; not yet read/written

### Acceptance tests
1. Numeric criterion w/ "each of 3 years" → all 3 figures extracted, rule applied (✅ done)
2. Disagreement between rules and LLM → confidence drops, REVIEW route
3. LLM-FAIL on qualitative → never auto-commit
4. Mandatory-FAIL → mandatory_review route, second-officer required
5. Smell test fires on shared address (✅ done)
6. Precedent surfaced in HITL when criterion text matches a prior decision in same dept × category

### Demo-time talking point
> "Two branches run in parallel. When they agree, confidence is high.
> When they disagree, we don't pick — we route to the officer with
> both interpretations side by side. **No silent disqualifications.**
> And then a third AI, the Devil's Advocate, argues against whichever
> verdict we landed on. If it raises a serious doubt, we route again."

### Open work — to ship
- ⬜ Tone the dissent down: severity=high should require concrete contradiction, not procedural nitpicks
- ⬜ Wire `precedent_service` — read at HITL time, write on every officer decision
- ⬜ Sequential-DD + common-signatory smell-test rules (CCI 2025 cartel signal)

---

## Module 4 — Human-in-the-Loop

> "AI helps. Officer decides. AI never insists."

This module is the *philosophical* difference between us and every
generic GenAI procurement tool. Today it's spread across the codebase;
we now name it.

### Sub-features
1. **Confidence Veil** — AI never says "this PASSES". Says "I'm 91%
   confident this satisfies clause 4.1(a)." (✅ done)
2. **Override-with-reason** — every cell can be overridden; reason is
   structured + free-text; recorded in audit chain. (✅ done)
3. **Per-cell officer comment thread** — *new*. Officer adds a note
   to any cell ("I disagree because the CA cert is from a flagged
   firm"). Recorded permanently.
4. **Co-author the TEC report** — *new*. Officer doesn't just hit
   "Generate". They click into each section, edit prose, accept or
   reject AI-suggested paragraphs, see redlines. The system
   tracks every diff and stamps `authored_by` per paragraph.
5. **Document Studio (inside Copilot)** — *new*. A second tab inside
   the Copilot panel: "Brief / Report / Other doc". Officer types
   "I need a 1-page brief for my CO covering the smell-test signals".
   AI drafts it with full tender context. Officer chats to refine.
   Download as PDF/DOCX. Saved to the tender's File Vault.
6. **Pre-Mortem Brief is a *suggestion*, not a verdict** — already
   framed that way; sharpen the copy.
7. **Concurrence inbox** for second-officer sign-off. (built; needs UI polish)
8. **Post-review checks** ("did you also check…?") (✅ done)

### Acceptance tests
1. Officer overrides AI verdict; audit row records old verdict, new
   verdict, structured reason, free-text reason, officer ID, time.
2. Officer adds a comment on a cell; comment surfaces on the Replay
   snapshot taken on next decision.
3. TEC report generates a *draft* with section-level edit markers;
   officer edits one paragraph; on save, audit row records the diff.
4. Officer asks Document Studio: "draft a note to CO summarising
   smell-test signals". Studio produces 4-paragraph note with citations
   to the smell-test entries. Officer downloads. File appears in Vault
   tagged `officer_authored=true`.

### Demo-time talking point
> "Notice every output here says *'I suggest'*, never *'this is FAIL'*.
> The TEC report is co-authored. Look — I click here, the section
> opens for editing, I rewrite this paragraph, the system tracks who
> wrote what. Even my prompt to the Document Studio is recorded in
> the audit chain. The AI helps. The officer still decides every
> word that goes into the file."

### Open work — to ship
- ⬜ Per-cell `officer_comments` table + UI thread
- ⬜ Co-authored TEC report (paragraph-level edit + diff tracking)
- ⬜ Document Studio as a tab inside the Copilot

---

## Module 5 — Lifecycle Handler

> "The file room. Every artefact, every version, every state — one place."

### Responsibilities (single sentence)
Manage the tender's full lifecycle: states, corrigenda, criterion
versions, bidder docs, EMD validity, bid validity — and surface them
in a **File Vault** tab the panel can browse.

### Sub-features
1. **State machine** with progress %. (✅ done)
2. **Corrigendum chain** — upload → AI summary → officer applies amendments → criterion versions bumped. (built backend; UI to ship)
3. **Append-only `criterion_versions`** with append-only triggers. (✅ done)
4. **File Vault tab** — *new*. One screen per tender showing every
   uploaded file (NIT, corrigenda, every bidder's pack), grouped by
   role, sortable by uploaded_at, click-to-view. The "where are my
   docs?" question answered in one click.
5. **EMD + bid-validity tracking** with auto-warning when validity
   expires soon.
6. **Bidder card** — one canonical page per bidder showing every doc,
   every verdict, every flag, every officer decision. (the panel keeps
   asking for this)

### Acceptance tests
1. Apply a corrigendum that changes turnover ₹10 Cr → ₹15 Cr → criterion
   version bumps from 1 → 2, history preserved, evaluations
   correctly tagged with the version they used.
2. Bid validity within 14 days → warning chip on bidder card.
3. File Vault shows all 19 docs across 3 bidders + 1 NIT + 1 corrig,
   total 21 entries, click any to open inline PDFViewer.

### Demo-time talking point
> "One click — File Vault. Every document this tender ever saw, in
> one place. Two clicks — corrigendum chain. The criterion text was
> ₹10 Cr originally; corrigendum 1 changed it to ₹15 Cr; **here's
> which bidders responded against version 1 and which against version
> 2**. That's the Calcutta High Court December 2023 audit story
> answered."

### Open work — to ship
- ⬜ File Vault tab (ship this turn)
- ⬜ Corrigendum upload + apply-amendment UI
- ⬜ Bidder profile page
- ⬜ EMD/bid-validity warning chips

---

## Module 6 — Security & Audit

> "Every action signed, every record sealed, every decision reproducible."

### Responsibilities (single sentence)
Prove, after the fact, that no action in the system happened without
being recorded, no record was tampered, and no decision can be
reconstructed in any way other than what actually happened.

### Sub-features
1. **Append-only hash-chained audit log** with DB triggers blocking UPDATE/DELETE. (✅ done)
2. **Defence Vault** — sealed ZIP with manifest + reproduce script. (✅ done)
3. **Signed TEC report** — *new*. Each TEC member's PKCS#7 (or simulated DSC) on the PDF.
4. **Officer authentication** — *currently* lightweight picker. **For real deployment** SSO would replace this; for the demo we honestly own that this is the auth shim and the audit chain captures officer ID on every action.
5. **Verifier provenance** — every external-source check stores the response verbatim + sha256 + timestamp.
6. **Reproduce-from-vault** — `08_reproduce.py` validates archive integrity. We **explicitly do not over-claim** byte-identical LLM output; the archive is what's reproduced. (Bar-Raiser flagged this — fixed in next vault revision.)

### Acceptance tests
1. Audit chain verify endpoint walks every event, recomputes hashes, returns ok=true.
2. Attempt to UPDATE an audit_events row → DB trigger raises ABORT.
3. Defence Vault for a tender, extracted on a clean machine, runs `08_reproduce.py` → all file hashes match.
4. TEC report generated → has 3 simulated officer signatures, sha256 hash on the PDF + QR code linking to the audit-trail endpoint.

### Demo-time talking point
> "I generate the TEC report. Notice three signatures — chair,
> member-secretary, finance member. The PDF carries a sha256 hash
> AND a QR code. Scan the QR — it goes to the audit-trail endpoint
> for this tender. Walk it. 247 events, every one hash-linked.
> Tamper with any one — the chain breaks. Generate the Defence Vault.
> ZIP. 41 files. Manifest signed. Hand it to CVC three years from now;
> they can run the verify script on a fresh machine."

### Open work — to ship
- ⬜ Simulated DSC on TEC PDF (3 stamps with officer name + datetime + sha256)
- ⬜ Update vault README to be precise about what's reproducible
- ⬜ "Verify chain" button on Audit tab that runs verify and shows result inline

---

## What this re-architecture changes for the demo flow

Old flow: feature-by-feature. Panel asks "ok what about X" and we hunt
for the right screen.

New flow: module-by-module. Panel asks "show me data correctness" and
we click the **Verifiers** tab. They ask "show me the human in the
loop" and we click into a cell, write a comment, override a verdict,
ask the Document Studio to draft a note — all in one minute. They ask
"show me security" and we hit **Generate vault**.

**Each module has one screen the panel can probe.**

---

## Where the bar-raiser doc grades change after this re-architecture

Pulling from `bar-raiser-decomposition.md` — the D-grade items that
become C or B once these modules ship:

| Sub-task | Current | After |
|---|---|---|
| 9.1 GST liveness | F | **B** (stub today; real switch is one env var) |
| 9.2 GST active on bid-date | F | **B** |
| 7.1 FRN exists on ICAI | F | **B** (stub) |
| 7.2 UDIN registered for cert | F | **B** (stub) |
| 6.1 PAN 4th-char entity rule | C | **B** |
| 14.3 Second-officer concurrence | D | **A** (real inbox UI) |
| 13.5 Member-vs-member dissent | F | **C** (officer comments thread) |
| 13.2 TEC narrative voice | C | **A** (co-authored report) |
| 16.6 Reproduce script over-claim | C | **B** (honest README) |

The F-grade items I'm explicitly *keeping* as F and naming so the
panel sees we're honest about them:
- Visual stamp forensics (research-grade, not yet)
- Market-rate plausibility (needs price-history corpus)
- Recognising a flagged CA firm by memory (Module 3 precedents
  partially addresses; not a full replacement for the seasoned officer)

---

## Build order — three sprints

**Sprint M1 (today + tomorrow): Module 5 + Module 2**
- File Vault tab (Module 5)
- Bidder profile page (Module 5)
- `backend/verifiers/*` driver classes with stubs (Module 2)
- Verifiers tab in the frontend (Module 2)
- Verifier audit events

**Sprint M2: Module 4**
- Per-cell officer comments
- Co-authored TEC report (paragraph-level edit + diff)
- Document Studio inside Copilot (second tab)

**Sprint M3: Module 3 + Module 6 polish**
- Sequential-DD + common-signatory smell-test rules
- Tone-down dissent prompt
- Precedent service end-to-end
- Simulated DSC stamps on TEC PDF
- Vault README rewrite

After M1 + M2 the system has a screen for every panel question. After
M3 it can keep up under cross-examination.

---

## What I will NOT do (and why)

- **No new fonts, colours, layouts, or wow concepts.** The pencil
  light theme + Bricolage display + Inter body is set.
- **No live external API integration today.** Stubs for Module 2,
  honest UI badges, swap to live in production. Live calls add
  flakiness with no demo upside.
- **No "AI vs human" gimmicks.** No talking avatars, no animations.
  Government tool, calm presence.

---

## My honest tradeoff acknowledgement

The Module 2 Verifiers tab will have a label `verified-via-stub`
on every result during the demo. **Some panellists will see that
as a weakness.** The frame is: "we built the *integration architecture*
that makes live verification a 1-line change; flipping the env-var
takes 3 hours; doing it without breaking the demo is the wrong
trade-off." Naming it on the screen is what makes us trustworthy.
