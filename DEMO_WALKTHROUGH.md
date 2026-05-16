# VerdictAI — Demo Walkthrough Script

> For the CRPF Hackathon Grand Finale. Follow this step-by-step.
> Each step has: what to DO, what to SAY, and what the JURY SEES.

---

## Pre-Demo Setup

1. Refresh AWS credentials: `ada credentials update --account=316394832518 --provider=conduit --role=IibsAdminAccess-DO-NOT-DELETE --once`
2. Start backend: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
3. Start frontend: `cd frontend && npm run dev`
4. Open browser: `http://localhost:5173`
5. Verify: Dashboard shows "AI ready" (green) in the search bar area

---

## Step 1: Create a New Dossier

**Click:** "New Evaluation" in the nav bar

**Fill in:**
| Field | Value | Why this value |
|---|---|---|
| Tender Number | `U.II-1410/2022-23-Proc-VII` | Real CRPF tender number |
| Title | `Procurement of Armoured Troop Transporter (ATT) — 124 Nos` | Real title |
| Department | `CRPF` | Select from dropdown |
| Category | `Goods` | Select from dropdown |
| Estimated Cost | `20000000000` (₹200 Cr) | Real estimated cost |
| EMD Amount | `40000000` (₹4 Cr) | Real EMD |
| Bid Open | `2023-03-16` | Real date |
| Bid Close | `2023-08-07` | Real date |

**Click:** Submit

**Say:** "This is a real CRPF tender — ₹200 Crore for 124 armoured vehicles. We're using the actual tender number from crpf.gov.in."

**Jury sees:** Dossier created, redirected to workspace with 8-section sidebar.

---

## Step 2: Upload the NIT

**Click:** "Documents" in the sidebar

**Upload:** `sample_docs/real_crpf/NIT_ATT_124_CRPF.pdf`
- Select doc_type: "NIT"

**Say:** "The NIT has 12 eligibility criteria across 4 pages — financial thresholds, certifications, past experience, manufacturing capacity. The system will OCR it and extract all criteria automatically."

**Jury sees:** Document appears in the list with page count + OCR confidence.

---

## Step 3: Extract Criteria

**Click:** "Criteria" in the sidebar

**Click:** "Extract Criteria" button (shows loading spinner)

**Wait:** 30-60 seconds (Bedrock processes the NIT)

**Say while waiting:** "The AI reads every page, identifies each eligibility clause, classifies it (numeric threshold, categorical presence, temporal recency), extracts the threshold value, and tags the source clause reference. Two branches run independently — regex patterns AND the LLM — and reconcile."

**Jury sees:** 12 criteria appear with:
- Type chips (numeric_threshold, categorical_presence, etc.)
- Mandatory/optional flags
- Source clause references (Clause 4.1(a), etc.)

**Say:** "12 criteria extracted. All mandatory. Each has a threshold, measurement period, and source clause. The officer can edit any of these before approving."

---

## Step 4: Approve Criteria

**Click:** "Approve all & evaluate"

**Say:** "In production, the officer reviews each criterion individually. For the demo, we approve all at once. Every approval is recorded in the audit chain."

---

## Step 5: Upload Bidder Documents

**Click:** "Documents" in the sidebar

**Upload for Ashok Leyland (the real winner):**
- Navigate to `sample_docs/real_crpf/bidders/ashok_leyland/`
- Upload all 11 PDFs (cover letter, turnover cert, GST, PAN, ISO, BIS, completion certs, facility, non-debarment, EMD, service centres)
- Mark each as "certificate" or "bidder_submission"

**Say:** "Ashok Leyland — the actual winner of this ₹187 Crore contract. 11 documents: CA-certified turnover, GST certificate, ISO 9001, BIS licence, completion certificates for 4 prior defence contracts, manufacturing facility details."

**Repeat for Mahindra (the one that should FAIL):**
- Upload from `sample_docs/real_crpf/bidders/mahindra_armoured/`

**Say:** "Mahindra — deliberately below the threshold. Turnover ₹98-125 Cr (needs ₹150 Cr). Only 2 similar orders (needs 3). No BIS licence. The system should catch all of these."

---

## Step 6: Run Evaluation (Live Stream)

**Click:** "Evaluation Matrix" in the sidebar

**Click:** "Run Live Evaluation" button

**Jury sees:** Cells filling in one-by-one with live scoreboard:
- Progress bar advancing
- PASS/FAIL/REVIEW counter updating
- Each cell appearing with color

**Say:** "Watch the matrix fill in real-time. Each cell is one Bedrock call — the AI reads the bidder's document, extracts the relevant value, compares against the threshold, and produces a verdict with confidence score. Two branches cross-validate."

**Wait:** 3-5 minutes for all cells

---

## Step 7: Show the Matrix + Radar + Heatmap

**Scroll down** below the matrix

**Jury sees:**
- **Bidder Radar Chart** — spider chart showing Ashok Leyland strong on Experience, Mahindra weak on Financial
- **Risk Heatmap** — bar charts showing anomaly concentration

**Say:** "One glance — which bidder is strongest. Ashok Leyland dominates Experience (100). Mahindra is weak across Financial and Compliance. The risk heatmap shows where the anomalies cluster."

---

## Step 8: Click a Cell — Show the Drawer

**Click:** Ashok Leyland's turnover cell (green, 95%)

**Jury sees the drawer with:**
1. Confidence Veil: "I'm 95% confident this satisfies Clause 4.1(a)"
2. Extracted figures: FY 2022-23: ₹185 Cr, FY 2023-24: ₹192 Cr, FY 2024-25: ₹210 Cr
3. Confidence Mosaic (5 bars)
4. 🧬 Tender DNA (institutional memory + AI insight)
5. Devil's Advocate dissent
6. Evidence Provenance Graph (visual chain)
7. Officer Notes
8. ⚡ What-If Preview (consequence analysis)
9. Confirm / Override buttons

**Say:** "Every AI claim is traceable. Click the source pill → opens the PDF at the exact page. The Confidence Mosaic shows WHERE the confidence comes from. The Devil's Advocate argues against the verdict. The What-If shows what happens if I override. And the Tender DNA shows how similar criteria were decided before."

---

## Step 9: Add a Comment + Override

**Type in Officer Notes:** "Verified against audited balance sheet. All 3 years exceed ₹150 Cr threshold."

**Click:** "Add note"

**Click:** "Override" on a FAIL cell (e.g., manufacturing facility)

**Fill reason:** "Manufacturing facility document clearly states 80 vehicles/year capacity, exceeding the 50/year requirement."

**Click:** "Save override"

**Say:** "The override is recorded with my reason. A concurrence request automatically opens for a second officer. Every word I write here is hash-chained and will appear in the Defence Vault."

---

## Step 10: Show Concurrence Flow

**Switch officer** (top-right dropdown) → DIG R. Verma (reviewer)

**Click:** "Review Queue" in the nav bar

**Jury sees:** 1 pending concurrence request

**Click:** the request → Concur with note: "Agreed — facility document is clear."

**Say:** "GFR 2017 requires multiple signatories. The system enforces this — a second officer must concur on any mandatory override. Both decisions are audit-chained."

---

## Step 11: Show the TEC Report (Co-Authored)

**Switch back** to Inspector Sharma

**Click:** "TEC Report" in the sidebar

**Click:** "Open draft"

**Jury sees:** Sections appearing (AI drafts each one)

**Click "Edit"** on one section → modify a sentence → Save

**Say:** "The report is co-authored, not auto-generated. Each section carries who wrote it — AI draft, co-authored, or officer-authored. I can rewrite any paragraph. The revision trail is append-only."

---

## Step 12: Generate Defence Vault

**Scroll down** on the Report page

**Click:** "Generate vault"

**Jury sees:** ZIP downloaded with file count + sha256

**Say:** "One click. Sealed evidence package. 39 files. SHA-256 manifest. Hand this to CVC three years from now — they run one script, every hash matches. The decision is reconstructed. No other system in this competition offers this."

---

## Step 13: Show Audit Replay (Time-Travel)

**Click:** "Audit Chain" in the sidebar

**Jury sees:** Audit Replay timeline at the top

**Click** any decision point on the timeline

**Say:** "Time-travel. Click any point → see the exact state of the dossier at that moment. What did the matrix look like before I overrode cell 7? Here it is. This is the CVC defence killer feature."

---

## Step 14: Show Help & About System

**Click:** "Help & Manual" in the nav bar

**Click:** "About the System" tab

**Say:** "Full technical documentation inside the product. 6 modules, 18 anomaly techniques, research-cited algorithms. Benford's Law, Z-score pooling, entity resolution — all with peer-reviewed references."

---

## Closing Statement

**Say:** "Every other approach automates the tender flow. We made the decision defensible. The AI never decides — it suggests. The officer signs every word. And three years from now, when CVC asks 'why did you qualify this bidder?' — the Defence Vault answers in one click."

---

## If They Ask...

| Question | Answer |
|---|---|
| "Is the GST check real?" | "The architecture is real — pluggable driver pattern. Today it runs in stub mode (format + logic validation). Flipping to live = one environment variable. The UI honestly badges every result as 'stub' or 'live'." |
| "Where does the data go?" | "Nowhere except AWS Bedrock (us-east-1). Source documents never leave the machine. Only extracted text goes to the model. Single cloud. Single account." |
| "Can this scale beyond CRPF?" | "Every GFR-bound buyer (BSF, ITBP, CISF, state police, PSUs) uses the same process. The architecture is org-agnostic. Multi-tenant is a deployment config, not a re-architecture." |
| "What if the AI is wrong?" | "That's why we have dual-branch cross-validation, Devil's Advocate dissent, and mandatory officer review. The system is designed to surface uncertainty, not hide it." |
| "How is this different from just using ChatGPT?" | "ChatGPT gives you one answer with no source, no confidence breakdown, no audit trail, no reproducibility. We give you two branches that cross-validate, a 5-component confidence mosaic, a hash-chained audit log, and a sealed evidence vault. The difference is defensibility." |
