# Product vision — V3

> Wearing the product-engineer hat. Reading `domain-truth.md` (what the
> domain *is*) and `buyer-gap-assessment.md` (what the buyer needs).
> Going beyond the surface "AI-fy the manual flow" to invent the moves
> the procurement community has not seen.
>
> Anything in this document must be **buildable, demonstrable, and not
> mocked**.

---

## Reframe

The buyer's mental model is **defensibility**, not productivity. Speed is
the side-effect of doing it right.

The current product accelerates the existing manual flow. That makes us
*better than nothing*. To win, we have to **change the unit of work**
from "evaluate this bidder against this criterion" to "**produce a
defensible Decision Package for this tender**".

A Decision Package is the unit the CVC, the CAG, the ED, the High
Court, and a successor officer all want — and none of them get today.

---

## The five tentpole features (the product-side wow moments)

Each tentpole has: what it is, why it changes the buyer's day, and what
it concretely looks like end-to-end. Nothing here is a mock.

### Tentpole 1 — The Defence Vault™ (single-button evidence package)

**What it is.** One click on any tender → produces a sealed, offline-
verifiable evidence package. ZIP file containing:

```
verdict-vault-CRPF-2026-15A.zip
├── 01_summary.pdf                 ← signed TEC report, every member's DSC
├── 02_timeline.pdf                ← visual timeline of every event
├── 03_decisions/
│    ├── eval-<bidder>-<criterion>.json   ← Replay snapshot, point-in-time
│    └── eval-<bidder>-<criterion>.pdf    ← rendered version of the above
├── 04_evidence/
│    └── <doc>/page-N.png + page-N.bboxes.json
├── 05_corrigenda/
│    ├── version-1/
│    └── version-2/...             ← criterion text at each version
├── 06_audit-chain.json            ← full hash-linked log
├── 07_pipeline-signature.txt      ← model_id + prompt versions
├── 08_reproduce.py                ← runs the same evaluation, same output
├── 09_manifest.json               ← sha256 of every file above
└── 10_seal.sig                    ← detached PKCS#7 signature of manifest
```

**Why this changes the buyer's day.** When CVC asks "send me everything
for tender X", today the officer compiles a PDF, exports the audit log
as Excel, finds the bidder docs in a shared drive, screenshots the
matrix, etc. — half a day. **With the Vault: 1 click, 30 seconds.**
And the inquiry officer can reproduce the verdict on their own machine.

**Why no one else has it.** This requires byte-identical reproducibility,
prompt-hash caching, signed PDFs, and a hash-chained audit trail —
*together*. We already have the parts; nobody has assembled them.

**Build cost.** ~3 days. Most pieces exist (replay snapshots, audit
chain, hash). New: signing pipeline + zip composer + reproduce script.

---

### Tentpole 2 — Tender Lineage Graph (time machine for defensibility)

**What it is.** A single screen that shows every event in a tender's
life as nodes on a horizontal swim-lane timeline:

```
Time →
NIT pub.   pre-bid    Corr#1     Corr#2     bids open    eval start    decisions    report   final
   ●───────●────●─────●──────────●─────●──────●─────●─────●─────●─────●──●●──────●
                ↑     ↑          ↑     ↑      ↑     ↑     ↑     ↑     ↑   ↑       ↑
                ╰─ click any node to time-travel: see exactly what an
                   officer would have seen at that moment in time
```

Lanes:
- **Tender state** (DRAFT → … → FINALIZED)
- **Documents** (NIT, corrigendum 1, bidder uploads)
- **Decisions** (criterion approval, override, second-officer)
- **Anomalies** (smell-test flags raised / dismissed / confirmed)

Clicking any node opens a **point-in-time view** of the tender as it
was at that timestamp. Like Git's `checkout HEAD@{2 days ago}` for
procurement.

**Why this changes the buyer's day.** A future inquiry officer doesn't
need a narrative. They need "what did the TEC see when they decided?"
The lineage graph IS the answer. No paperwork.

**Why no one else has it.** Requires correctly-modelled corrigenda +
versioned criteria + audit chain + officer-decision points-in-time —
all linked. Most procurement systems have at most one of these.

**Build cost.** ~4 days. Backend: surface point-in-time queries from
existing audit + replay tables. Frontend: SVG timeline component.

---

### Tentpole 3 — Pre-Mortem Brief (the 90-second TEC briefing)

**What it is.** Before the officer opens the matrix, the system has
already read everything and produces a **one-page brief** answering
five questions:

```
┌──────────────────────────────────────────────────────────────────┐
│  Tender CRPF/2026/15-A — Pre-Mortem Brief                        │
│  AI-generated · officer to confirm · do NOT use as decision      │
├──────────────────────────────────────────────────────────────────┤
│  ① What's the lay of the land?                                   │
│     5 bidders · 9 criteria · 1 mandatory FAIL likely             │
│                                                                  │
│  ② Who looks strongest?                                          │
│     Acme Defence — 8/9 likely-PASS, 1 mid-band                   │
│                                                                  │
│  ③ Who looks weakest?                                            │
│     Bravo Industries — 4/9 unclear, missing docs ×3              │
│                                                                  │
│  ④ Where will I have to think hardest? (HITL items)              │
│     • clause 4.1(a) Acme: turnover branches disagreed (20% gap)  │
│     • clause 4.5 Charlie: ISO certificate validity unreadable    │
│     • clause 4.3 Bravo: address collision with Acme              │
│                                                                  │
│  ⑤ What might bite me later? (Pre-Mortem Risks)                  │
│     ▲ Corrigendum 2 changed turnover from ₹10 Cr to ₹15 Cr —     │
│       did Charlie respond to v2? (their cover letter dates       │
│       2 days BEFORE corrigendum 2)                               │
│     ▲ Acme & Bravo share registered address — possible cartel    │
│     ▲ Bid validity for Bravo expires in 14 days                  │
└──────────────────────────────────────────────────────────────────┘
```

**Why this changes the buyer's day.** The hardest part of evaluation
isn't reading documents — it's **knowing where to focus**. The Brief
gives the officer a 90-second mental model before they open the matrix.
Multiplies decision speed by 3–5×.

**Why no one else has it.** Requires the Smell Test, dual-branch
extraction, corrigendum versioning, AND a thoughtful summarisation
prompt — together. Most teams build the parts in isolation.

**Build cost.** ~2 days. Mostly composition of signals already in the
DB into a focused Bedrock prompt. Cached.

---

### Tentpole 4 — Active Source-Click (the trust mechanism, finally)

**What it is.** Every AI-generated string that references a fact is a
**bidirectional citation**:

- Forward direction: click any inline cite chip in any AI text →
  PDFViewer opens at the exact page with the exact phrase highlighted in
  pencil border. (The current product does this *partially*.)
- Reverse direction: hover any word in the PDFViewer → see *every place
  in the system that relies on this word*. The bbox carries badges for
  "extracted as net worth", "cited in dissent", "matched smell-test rule
  X". Click a badge → jump back to the evaluation that uses this word.

This makes the relationship between *evidence ↔ inference* visible and
navigable in both directions. The officer can audit a single phrase's
"blast radius" through the system.

**Why this changes the buyer's day.** It's the difference between trust
("the AI said so") and verification ("I can see for myself, in 2 clicks,
that the AI's claim resolves to this exact word on this exact page, and
I can also see what else depends on it"). This is **how the AI earns
its keep**.

**Why no one else has it.** Word-level bboxes per page, link table from
evaluation → words, reverse index — all need to exist. We have the first
two. We're missing the reverse index and the UI.

**Build cost.** ~3 days. New table `evidence_citations(evaluation_id,
word_object_id)`. Reverse-lookup endpoint. PDFViewer hover badges.

---

### Tentpole 5 — Tender DNA (institutional memory that compounds)

**What it is.** Every decision the officer makes generates a "DNA strand":

```
DNA strand for evaluation 6c4f…
{
  criterion_text:  "annual turnover ≥ ₹15 Cr in last 3 FYs"
  criterion_type:  numeric_threshold
  department:      CRPF
  category:        Goods
  resolution:      "We treated standalone (not consolidated) figures
                    because the OEM contract clause required principal
                    responsibility."
  officer_action:  confirmed
  officer:         officer-verma
  tender_id:       CRPF-2026-15-A
  pipeline_sig:    b1cda53f50fa48f3
}
```

These strands populate the **Precedent Constellation** — a searchable,
embedding-indexed corpus of "how a phrase has been resolved before in
this department × this category". When the officer is about to decide a
similar criterion in a future tender, the system surfaces the matching
strands inline:

> *Last 3 times this department evaluated "similar work":*
> - CRPF-2025-103: officer Sharma resolved as "RCC box culverts qualify"
> - CRPF-2024-92:  officer Verma resolved as "canal crossings DO qualify"
> - CRPF-2024-15:  officer Kumar resolved as "minor bridges DO NOT
>   qualify"

The officer's interpretation **becomes institutional record**, not
individual judgement. Over 50 evaluations, the Constellation becomes a
moat — replicable only by people with the same data.

**Why this changes the buyer's day.** Officers rotate every 2–3 years.
Today, every new officer reinvents how to interpret "similar work" in
their first three tenders. With the Constellation, the new officer
inherits 28 years of departmental judgement on day one.

**Why no one else has it.** Requires real officer-decision capture +
embeddings + a UI that shows precedents in context. The schema's
`precedents` table + FTS5 already exists; nothing reads or writes it.

**Build cost.** ~3 days. Wire the existing table; add embedding index;
surface in HITL drawer.

---

## Two more wow moments (smaller, equally striking)

### Wow 6 — The Crystal Pane

A faint, always-visible *what-if* on every cell of the matrix. Hover a
cell → "if you confirm this PASS, total qualified bidders becomes 4. If
you override to FAIL, total becomes 3 and triggers Single-bidder rule
GFR 161." Lets the officer see the consequence of each decision before
making it.

### Wow 7 — Shadow Officer

A hidden second AI persona running quietly. Whenever the primary AI is
*least uncertain*, the Shadow Officer asks one provocative question. If
the primary AI says "92% confident this turnover satisfies", the Shadow
asks "Can you tell me if the turnover figure is from standalone or
consolidated accounts? If you can't, your confidence should be 70." It
appears as a small italic sidebar note. Not a button. Not a pop-up. A
whisper.

---

## What we drop, sharpen, or downgrade

| Item | Action | Why |
|---|---|---|
| Time-Capsule Replay (V1 #9) | **Subsumed** by Tentpole 2 (Lineage Graph) | The graph IS the time-machine. No separate concept. |
| Decision Memory Vault (V1 #1) | **Subsumed** by Tentpole 1 (Defence Vault) | Same idea, sharper packaging. |
| Officer Endorsement Trail (V1 #12) | **Drop** | Cold-start problem; no demo wow. |
| Quiet/Loud Mode (V1 #6) | **Drop** | Solves a small problem at the cost of a UI mode. |
| Two-Officer Lock (V1 #7) | **Sharpen → Real Inbox** | Make it the second-officer inbox surface, with notifications. |
| Vernacular Mode | **Drop "live translation"; keep bilingual OCR** | Bedrock vision reads Hindi natively; keep that. Live translation is overreach. |
| Confidence Veil | **Promote** | Already in. Make it pervasive — every chip, every headline. |
| Smell Test | **Promote** | Move chips into the matrix, not a separate panel. |
| Dissent Mode | **Promote** | Always run; render the dissent quote inside the eval drawer. |

---

## What this looks like to DIG Verma in 30 seconds

She lands on her dashboard. **3 tenders** awaiting her concurrence —
each chip says exactly what's needed (concur on Acme override · sign
TEC report · review smell-test on Charlie). She clicks the first.

She lands on the **Tender Space** for CRPF-2026-15-A. The first thing
she sees is the **Pre-Mortem Brief** — five bullets, 90 seconds. She
notes one item that surprises her: corrigendum 2 changed the ISO
requirement and Charlie's response predates it.

She clicks Charlie's row in the **Comparative Matrix**. The **Lineage
Graph** rail shows her exactly when each event happened. The drawer
opens with the **Confidence Veil headline** + **Mosaic** + **Dissent
quote** + **Smell Test chip** + **Source pill**.

She clicks the source pill. The **PDFViewer** shows page 4 of Charlie's
ISO certificate. Hovering the certification number, she sees a **reverse
badge**: "Smell Test rule: certification body not on NABCB accredited
list — flag medium severity."

She decides to override the AI's PASS to REVIEW. As she types her
reason, the **Crystal Pane** updates: "If REVIEW, this bidder cannot
proceed without resolving the certification. Total qualified: 3 of 5."

She saves. The **second-officer inbox** notifies the next-higher
authority. The **Tender DNA strand** is captured. The audit chain
extends by one entry.

She clicks **Generate Defence Vault**. 30 seconds later a signed ZIP
sits in her downloads. She emails it to the CVC.

Done in 5 minutes. Old way: 4 hours.

---

## The order I would build these

We have 5 tentpoles + 2 wows + 30 gap items + the buyer's 8-item must-list.
Not all can ship at once. Priority for maximum buyer-perception lift:

**Sprint A (the buyer-blocker fixes — must have):**
1. Corrigendum lifecycle (gap #1 + #7 + Tentpole 2 prereq)
2. GFR rule visible at override moment (gap #2)
3. Real second-officer inbox (gap #3)
4. CVC + GeM blacklist real check (gap #4)
5. EMD + bid-validity capture (gap #5 + #6)
6. Auto replay-snapshot at decision time (gap #9)
7. PDF e-signature (gap #8)
8. Defence Vault (Tentpole 1) — composes #1-7

**Sprint B (the wow moments — competitive differentiator):**
9. Pre-Mortem Brief (Tentpole 3)
10. Tender Lineage Graph (Tentpole 2 — uses Sprint A's data)
11. Active Source-Click (Tentpole 4)
12. Tender DNA / Precedent Constellation (Tentpole 5)

**Sprint C (the polish — the daily-use lift):**
13. Officer dashboard (gap #24)
14. Bidder Profile page (gap #18)
15. Comparative L1 ranking view (gap #19)
16. Smell Test chips on matrix columns (gap #11)
17. Confidence Mosaic actionable (gap #12)
18. Copilot citations rendered as click-through (gap #13)
19. Mobile/tablet layout (gap #25)
20. Tooltip occlusion fix + matrix sticky column + PDF in-doc search (gaps #26, #27, #28)

**Sprint D (creative-frosting — the demo unforgettables):**
21. Crystal Pane (Wow 6)
22. Shadow Officer (Wow 7)

After Sprint A + B the buyer **signs**. After Sprint C they **roll out
across CRPF**. After Sprint D they **become a reference customer for
other CAPFs**.

---

## Definition of Done for V3

- Every tentpole works on the live demo with real Bedrock and a
  realistic NIT + 5 bidders × 9 criteria × at least one corrigendum.
- Defence Vault produced for one tender, opened on a second machine,
  same TEC report regenerated byte-identical.
- Pre-Mortem Brief flags every seeded fraud signal AND at least one
  honest-mistake signal we didn't seed.
- Source-click round-trip works in <500ms from cite to highlighted
  PDF page.
- Lineage Graph shows the corrigendum diff visibly affecting the
  criterion text.
- Tender DNA: at least 5 strands captured during the demo and 1 of
  them surfaces as a precedent in a later evaluation.
