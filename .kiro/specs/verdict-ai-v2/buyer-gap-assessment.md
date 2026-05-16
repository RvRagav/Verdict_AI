# Buyer's gap assessment

> **Persona:** DIG R. Verma, CRPF. 28 years in service. Has chaired 40+ TECs.
> Approves IT tools for the directorate. Reads `domain-truth.md` and the
> current product, then decides: **buy / pilot / reject**.
>
> **Question I'm asking:** does this product actually reduce my time-to-decision
> *and* give me defensibility I don't already have, or is it just a
> better-looking front-end on the same manual process I already do?

---

## My one-line verdict

**Pilot, not buy. Today the product is a competent digitisation of the TEC's
manual workflow. It gets out of my team's way, but it doesn't yet *change* the
way the TEC works. Several non-negotiables for a CVC-defensible system are
missing or mocked. Below are the 30 reasons I'd cite in committee.**

---

## How I read each module

### What works (I would keep these)

| Capability | Verdict | Why |
|---|---|---|
| Hash-chained audit trail | **Keep** | Append-only, verifiable, byte-identical reproducible. This is rare. |
| Two-branch (rules + LLM) for numeric / categorical / temporal | **Keep** | The reconciliation language ("rules and LLM agree" / "disagreed; officer review") is exactly how I'd brief the CVC. |
| Confidence Veil framing in headlines | **Keep** | The AI deliberately understates. My authority is preserved. |
| Source-click pill from criterion → NIT page | **Keep** | The trust mechanism. Click → I see the clause myself in seconds. |
| Bedrock-vision OCR for scans (no third-party doc-AI service in the stack) | **Keep** | One vendor. One audit boundary. |
| Smell-test rules (address collision, duplicate doc, GSTIN-PAN mismatch) | **Keep** | Catches what real cartels do. CCI evidence patterns from public cases line up with the detectors. |
| TEC PDF generator | **Keep** | Saves the scribe a day. |
| Officer picker as real FK on every action | **Keep** | The "who decided what" question is answerable. |

These together are **table stakes**. They don't yet justify a buy — they
justify "you're not embarrassing yourself".

---

## The 30 gaps that block a buy

I am ranking these by what loses me the deal in front of CVC, then by what
loses me the deal in front of my own staff who have to use it daily.

### A. Defensibility holes (CVC inquiry will find these)

**1. No corrigendum lifecycle.**
The system has `doc_type='corrigendum'` and that's it. Real tenders amend
NIT clauses 1–4 times. After the amendment, *the criterion text changed
under the bidder's feet*. My TEC must show the inquiry: "the bidder
responded against criterion text version 2; we evaluated against version 2;
here is the diff against version 1; here is the corrigendum that effected
it."
**Today this story cannot be told.** No diff. No version history per criterion.
No "applies after corrigendum 2" tag. The Calcutta HC ruling I cite in the
domain-truth doc (Dec 2023) makes this a hard requirement.

**2. No GFR rule reference visible at the override moment.**
The schema stores `gfr_rule_number` and `gfr_override_permitted`. The UI
doesn't surface them where they matter. When I'm overriding a mandatory
FAIL, I expect to see *"GFR Rule 173 (iii) — override of a mandatory
eligibility criterion requires the prior approval of the next-higher
authority. Click to attach approval letter."* Today the override button
just shows "Override". Without the rule reference inline, my second-officer
sign-off is procedurally weak.

**3. No second-officer flow as a real workflow.**
The schema has `requires_second_officer` and `second_officer_id` columns,
the API accepts `POST /evaluations/:id/second-officer`. There is no
**inbox** for that second officer. They don't get notified. They have no
view of "items awaiting my concurrence". So in practice the field stays NULL
and the audit trail records "first officer decided alone" — exactly the
situation GFR is trying to prevent.

**4. No CVC debarment / GeM-blacklist check at ingestion.**
`bidder_service.check_debarment()` is a stub that returns `clear` unless
the company name contains the string "blacklisted". Real cross-checks need
to query the **CVC debarred-entities list** and the **GeM blacklist**.
Without this, a bidder ED has chargesheeted (à la Reliance Power / SECI,
Nov 2024) could quietly pass our preliminary exam. That's a career-ending
miss.

**5. No bid validity tracking.**
Each bid has a validity window declared in the bid form (typically 90 or
120 days). Patna HC ruled (Mar 2026) disqualification challenges expire
with bid validity. We must capture and clock this. We don't.

**6. No EMD reconciliation.**
Earnest Money Deposit is a legal requirement. Each bidder either paid
(DD / e-payment / BG) or is exempt (MSE / Udyam). Today there's no field
to capture the instrument number, amount, validity, or exemption proof.
This is the easiest gotcha the inquiry will find.

**7. No criterion-level version history.**
We approve criteria but don't keep prior versions when an officer edits.
If the officer edits "annual turnover ≥ ₹15 Cr" to "annual turnover ≥ ₹10 Cr"
during review, the original is lost. CVC asks "what was the original AI
extraction?" — we can't answer.

**8. No e-signature on the TEC report.**
The PDF carries a sha256 hash. That's tamper-evidence, not authentication.
Real reports must be **digitally signed** (PKCS#7 / DSC) by every TEC
member. Without it, the PDF is "a document the system produced" not
"a document the committee adopted".

**9. No replay snapshot at the moment of the decision.**
Replay capture is on demand. By the time I think to capture, the screen
state has moved on. The schema fields the snapshot uses are present-tense,
not point-in-time. **Replay must be automatic at the moment a decision is
saved**, not a separate user action.

**10. No print-friendly audit trail export.**
The audit trail exists as JSON in the DB. The CVC inquiry will arrive
with a paper request. We have no "Export audit trail of this tender as a
signed PDF with hash chain visible" button.

### B. Pain points the system claims to solve but doesn't

**11. The Smell Test rules don't show up where I make the decision.**
46 anomaly flags fire in the smoke test. The matrix shows them as a
secondary list. They should appear as **chips on the bidder column header
in the matrix** ("⚠ shares address with Bravo Industries") so I see them
the moment I look at the bidder, not when I scroll past the matrix.

**12. The Confidence Mosaic is decorative, not actionable.**
Five pretty bars. Beautiful. But when one bar is weak, what do I do?
There's no "click the OCR bar → see which page failed OCR → re-upload
this page in better quality" loop. Decoration without affordance.

**13. The Copilot doesn't ground its answers in source-clickable cites.**
The system prompt says "always cite sources" and includes a `[doc:DOC_ID#page=N]`
format hint. The frontend doesn't *render* those citations as click-through
pills. The Copilot is therefore another wall of text I have to verify
manually. The wow is missing.

**14. No precedent memory.**
The vision doc V1 promised "CPM — institutional memory of how 'similar
work' was resolved in past tenders". Schema has a `precedents` table with
FTS5 index. **The product never reads from it during evaluation, never
writes to it after a decision, and never displays a precedent during HITL
review.** It's wired to nothing.

**15. No bid capacity calculator.**
Real CAPF tenders use `2.5 × N × A_max − B` (or local variants) for bid
capacity. The system doesn't compute or capture this — yet bid capacity
is one of the most contested rejections in court.

**16. Hindi text in scans is silently ignored.**
Bedrock-vision OCR can read Hindi, but our prompts ask for English-only
output. CRPF NITs in north-India zones often have Hindi headings.
**A bilingual NIT will silently lose half its text.**

**17. No FY (financial year) normalisation.**
A turnover figure is meaningless without "in which FY". Our extractor
stores the rupee value and the source quote but doesn't extract or enforce
FY alignment. A bidder claiming "₹15 Cr" without specifying year passes
silently. The Finance Member of the TEC will catch this — too late.

### C. Things that aren't built

**18. No Bidder Profile page.**
A TEC member needs ONE page per bidder showing: identity, every uploaded
doc, every verdict, every flag, every decision, history. Today I'd have
to filter the matrix by column, click through cells one by one. Slow.

**19. No comparative L1 / ranking view.**
The TEC's output is "ordered list of qualified bidders". The system
produces verdicts. I have to mentally rank them. The simple table
"qualified / not qualified, with reasons" doesn't render.

**20. No timeline / Gantt view.**
A tender has events: NIT published, corrigendum 1, bid opened, eval
started, override #1, second-officer concurrence, report. The future
inquiry officer needs this in a single picture. We have raw audit events
in JSON but no visual.

**21. No Tender Clone / template.**
I run 30 similar tenders a year. I should clone criteria + checklist from
the last successful one. Today I extract from scratch every time.

**22. No "what changed from last similar tender" diff.**
I want to reuse criteria from a previous tender, then see only what's new
or different. Saves hours and reduces errors.

**23. No "documents you might be missing" prompt.**
A bidder uploads 4 docs; checklist needs 12. Today the system says
"missing × 8". It should say *"likely missing: GST certificate, PAN, ISO
9001, MoA — typical filenames are gst_cert.pdf / iso_9001.pdf"* so the
TEC scribe can write to the bidder for clarification within the bid
validity window.

**24. No officer dashboard.**
The Dashboard lists "active tenders" — globally. I want **my** workload:
"3 evaluations need your decision · 1 second-officer concurrence ·
2 reports awaiting your e-signature".

**25. No mobile / tablet view.**
DIGs review on iPad in meetings. Today the layout breaks below 1100px.

### D. Quality gaps in what is built

**26. Frontend tooltips were appearing on top of buttons unnecessarily.**
Fixed in the latest pass, but the placement logic still doesn't account
for occluded scroll containers — at the rightmost matrix cell the tooltip
clipped behind the Copilot panel. Polish.

**27. The matrix doesn't lock the leftmost column on scroll.**
For 9 criteria × 5 bidders the table fits. For 16 × 12 it scrolls
horizontally and I lose the criterion name. The first column needs
`position: sticky`.

**28. The PDF viewer renders the page image but does not let me search.**
A scanned 12-page certificate, I want to type "turnover" and jump to
the page. Today I scroll. (We have word-level OCR + bboxes — search is
trivial to add and missing.)

**29. The Copilot stream doesn't survive page navigation.**
If I switch from Evaluation to Documents while the Copilot is generating,
the answer is lost. The chat history is per-tender — fine — but the
in-flight stream should park.

**30. Demo data is too clean.**
Acme / Bravo / Charlie are 1-page bidders with deliberately-seeded
collisions. Real CRPF bidders submit 200+ page packages. The product's
behaviour at 200 pages × 5 bidders has not been demonstrated.

---

## What I would expect to see before I sign the buy order

A short, hard list. Each item must work end-to-end with real data, no
mocks, on the live demo:

1. **Corrigendum applied** — upload a corrigendum, see the criterion text
   diff, see which bidder responded against which version. Audit shows
   both versions linked.
2. **Defence Vault export** — one click, get a zip containing the timeline,
   criterion versions, evidence pages with bboxes, decisions, audit trail
   PDF (signed), pipeline-signature hash, replay script. A second officer
   on a different machine can reproduce the same TEC report from this zip.
3. **Second-officer inbox** — log in as Officer Verma, see "1 evaluation
   waiting on your concurrence; click to review and concur/reject".
4. **Real CVC + GeM blacklist check** — paste a known-debarred PAN/GSTIN
   and watch the bidder get flagged before evaluation runs.
5. **Source-click cite in Copilot** — ask the Copilot a factual question;
   click any cite chip in its answer; the PDF opens at the cited page
   with the cited line highlighted.
6. **Precedent surfacing** — during HITL on a "similar work" criterion,
   see at least one prior decision in the same department/category, with
   tender ID and officer who decided.
7. **Officer dashboard** — what's awaiting *me* across all my tenders.
8. **Frozen, signed report** — TEC report with three TEC members'
   digital signatures on the PDF and a verifiable hash chain in an
   appendix.

Without these eight, the product is a usability win, not a procurement-
transformation win.

---

## What would actually make me sign on the spot

Three things, none of which the procurement community has seen before:

**a. The Defence Vault.** A single button that produces an offline-
verifiable, sealed evidence package for any tender. CVC, CAG, ED — they
all want the same thing in different formats. Give it to them in one
click.

**b. Tender Lineage Graph.** Every event in the tender's life as a node;
every dependency as an edge. Click any node to time-travel to that
moment. This is the *time machine for defensibility* the V1 vision
promised. Today it's missing entirely.

**c. The Pre-Mortem Brief.** Before I open the matrix, the system has
already read everything and tells me: *"3 things might bite you on this
tender — Acme and Bravo share an address; Charlie's net-worth proof is
two years stale; corrigendum 2 changed the ISO requirement and only 2 of
5 bidders responded against the new version."* This makes me **2 hours
faster to the decision** on every tender. Multiply that by 30 tenders a
year — that's how I justify the budget line.

If the team can show me **a, b, c working live** with the eight items
above, I move from pilot to roll-out across all CRPF zones.
