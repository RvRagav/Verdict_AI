# Bar-Raiser Decomposition — VerdictAI vs the CRPF TEC Member-Secretary

> Bar-Raiser hat. 50+ tenders manually evaluated as CRPF TEC
> Member-Secretary. Decomposing what I *actually* do — including the
> moves I cannot articulate — and grading what VerdictAI replaces.
>
> **Grades.** A better than experienced officer · B matches · C
> trainee level · D fakes it (UI surface, no cognition) · F does not
> attempt; officer does it manually. Brutal by design.

---

## Phase 1 — Bid receipt and registration

| # | Task | Time | Lvl | Today | Grade |
|---|---|---|---|---|---|
| 1.1 | Inspect each envelope's seal; note tampering, stamp time | 4 min/bid | L0 | `created_at` only; no envelope-condition / CPPP-receipt capture | **F** |
| 1.2 | Cross-check envelope label vs CPPP-listed bidder | 1 min | L1 | Bidders registered manually; no CPPP integration | **F** |
| 1.3 | Capture *who* received, *when*, witness signature | 2 min | L0 | `actor` exists; no witness, no dak number | **F** |
| 1.4 | Late-bid decision (auto-DQ trigger) | 30 s | L2 | `bid_close_date` on tenders; no late-bid auto-flag | **D** |

**Hidden moves:** typo on the envelope label, smell of a re-sealed
flap, the same letterhead from a flagged 2024 bid, the courier the
previously-DQ'd bidder uses. None caught.

---

## Phase 2 — Tender fee + EMD verification

| # | Task | Time | Lvl | Today | Grade |
|---|---|---|---|---|---|
| 2.1 | Read DD/e-payment receipt — instrument no., bank, payee | 3 min | L0 | Schema fields exist; **no extraction pipeline reads them off the doc** | **C** |
| 2.2 | EMD amount equals NIT-required EMD | 1 min | L2 | No comparator fires on amount mismatch | **F** |
| 2.3 | EMD validity ≥ bid-validity + 30/45 days | 2 min | L2 | Date math not implemented | **F** |
| 2.4 | If MSE exempt: Udyam active, name match, NIC code matches tender category | 4 min | L3 | Udyam regex only; no NIC-code or live Udyam lookup | **D** |
| 2.5 | Confirm DD ≠ cheque (CVC red flag) | 30 s | L1 | Not classified | **F** |
| 2.6 | **Cross-bidder: are EMD DDs sequentially numbered?** (CCI 2025 cartel signature) | 4 min total | L4 | Smell test catches address collisions but not sequential DDs — the *exact* CCI bust pattern, missed | **F** |

Item 2.6 is half a day and the most procurement-defining miss we
have today.

---

## Phase 3 — Preliminary examination (each bidder × each mandatory document)

| # | Task | Time | Lvl | Today | Grade |
|---|---|---|---|---|---|
| 3.1 | Build the document checklist from NIT (8–20 items) | 30 min one-time | L2 | `extract_checklist()` Bedrock pass — strongest single feature | **A** |
| 3.2 | Tag each bidder upload as one of the checklist items | 20 min/bidder | L1 | `matches_doc_type` field exists; **no auto-classify** of which file is what | **C** |
| 3.3 | Identify *missing* mandatories | 5 min/bidder | L2 | Counts only; doesn't suggest "this file is probably the GST cert" | **C** |
| 3.4 | Doc *present but degraded* → REVIEW, not FAIL | 3 min/case | L3 | OCR confidence captured; not bridged to checklist state | **D** |
| 3.5 | Note docs *not asked for* but submitted | 2 min | L1 | Not done | **F** |

**Hidden:** six files all named `Document_N.pdf` and instant
distrust; an MoA template last seen in CRPF Jharkhand 2024.

---

## Phase 4 — Reading the NIT clause-by-clause

| # | Task | Time | Lvl | Today | Grade |
|---|---|---|---|---|---|
| 4.1 | Identify modal verb (must / shall / may) and quantify | 4 min/cl | L3 | `CRITERION_EXTRACTION` does this — close to officer quality | **B** |
| 4.2 | Distinguish mandatory from desirable | 1 min/cl | L2 | LLM classifies; verdict layer enforces no-auto-commit on mandatory FAIL | **B** |
| 4.3 | For numerics, decide measurement period (each / avg / cumulative / single) | 2 min/cl | L3 | `measurement_period` enum + verdict logic — recently fixed | **B** |
| 4.4 | "Similar work" interpretation (80% of disputes) | 8 min/cl | L4 | `precedents` table exists; **nothing reads or writes it** | **D** |
| 4.5 | Internal contradictions inside the NIT (cl 4.1 ₹15 Cr, schedule ₹10 Cr) | 5 min | L4 | Not attempted | **F** |
| 4.6 | Recognise the same clause text resolved a particular way before | 2 min/cl | L4 | Not attempted | **F** |

**Hidden:** "estimated cost ₹14.95 Cr is just below the ₹15 Cr DG
sanction threshold" — a class-A vigilance signal we miss.

---

## Phase 5 — Reading each bidder's cover letter

Often skipped by trainees; senior officers always read it.

| # | Task | Time | Lvl | Today | Grade |
|---|---|---|---|---|---|
| 5.1 | Date precedes bid-submission | 30 s | L0 | Not extracted | **F** |
| 5.2 | Signatory authority (POA / Board Resolution) | 2 min | L2 | Not extracted | **F** |
| 5.3 | Tone — overly defensive language signals weak bid | 1 min | L4 | Not attempted | **F** |
| 5.4 | **Compare phrasings across bidders — verbatim overlap = collusion** | 5 min total | L4 | Not implemented despite citation infrastructure | **F** |

5.4 is half a day of work, A-grade outcome. The simplest under-used
signal we have.

---

## Phase 6 — Cross-referencing bidder identity (PAN ↔ GSTIN ↔ CIN ↔ CA cert)

| # | Task | Time | Lvl | Today | Grade |
|---|---|---|---|---|---|
| 6.1 | PAN format AAAAA9999A + 4th-char entity code | 2 min | L1 | Regex yes; **4th-char-vs-entity-type rule missing** | **C** |
| 6.2 | GSTIN format + positions 3–12 == PAN | 2 min | L2 | `detect_gstin_format_mismatch()` does both | **B** |
| 6.3 | CIN format LXXXXXXXXXXXXXXXXXX, decode state/year/type | 2 min | L2 | No regex, no decode | **F** |
| 6.4 | Entity name on PAN == GSTIN == CIN == CA cert (allowing Pvt Ltd / P Ltd / India variants) | 3 min | L3 | Not done | **F** |
| 6.5 | **CA cert in a *different* entity name (parent-substitution fraud)** | 1 min | L4 | Not implemented — and this is the Reliance-Power-vs-SECI pattern | **F** |

---

## Phase 7 — CA-certificate authenticity

| # | Task | Time | Lvl | Today | Grade |
|---|---|---|---|---|---|
| 7.1 | Read FRN; verify on ICAI portal | 5 min | L2 | Not implemented (portal is public, free) | **F** |
| 7.2 | Read UDIN; verify on ICAI UDIN portal that it was generated for *this* certificate | 5 min | L2 | Not implemented — massive vigilance gap | **F** |
| 7.3 | CA in practice (not deceased / surrendered) | 3 min | L2 | Not done | **F** |
| 7.4 | Visually inspect signature against past CA signatures (memory) | 2 min | L4 | Not done | **F** |
| 7.5 | Financial year on cert matches bid-period FYs | 2 min | L2 | `period_label` captured; no FY-alignment check | **D** |

UDIN/FRN (7.1, 7.2) — public ICAI APIs, two days, the move that makes
the defence vault credible.

---

## Phase 8 — Comparing turnover figures across years

| # | Task | Time | Lvl | Today | Grade |
|---|---|---|---|---|---|
| 8.1 | Identify *all* turnover figures across 3–5 years (not just the largest) | 6 min | L2 | `_rules_numeric` + LLM return all figures | **B** |
| 8.2 | Standalone vs consolidated (criterion-dependent) | 3 min | L3 | Free-text on Indian B/Ses; **not extracted** | **D** |
| 8.3 | Apply measurement period (each / avg / cumulative) | 2 min | L2 | Verdict layer enforces; REVIEW when periods missing — genuinely better than a hurried trainee who would FAIL | **A** |
| 8.4 | CA cert reconciles with audited balance sheet | 5 min | L3 | No cross-doc reconciliation | **D** |
| 8.5 | Sanity-check ₹15.00 Cr × 3 years (multi-year roundness) | 1 min | L4 | Single-year `detect_round_number()`; no multi-year escalation | **C** |

---

## Phase 9 — GST liveness verification

The five-second move every officer does. We do not attempt it.

| # | Task | Time | Lvl | Today | Grade |
|---|---|---|---|---|---|
| 9.1 | `gst.gov.in/services/searchtp` lookup | 30 s | L0 | Not done | **F** |
| 9.2 | GSTIN was *active on bid submission date* (not today) | 30 s | L2 | Not done | **F** |
| 9.3 | Jurisdiction state matches bidder address state | 30 s | L1 | Not done | **F** |
| 9.4 | Return-filing status (no filing in 6 months = red flag) | 1 min | L2 | Not done | **F** |

GST portal is public. Bid-date-anchored check (9.2) — one day, A-grade
outcome. A panel question as simple as "did you confirm GST was active
when they bid?" lands here.

---

## Phase 10 — Past-project completion certificates

| # | Task | Time | Lvl | Today | Grade |
|---|---|---|---|---|---|
| 10.1 | Identify ordering authority on cert | 1 min | L1 | LLM extracts at trainee level | **C** |
| 10.2 | Verify the ordering authority *exists* (real vs invented dept name) | 2 min | L4 | Not attempted | **F** |
| 10.3 | Verify order ref exists on issuing authority's eProcurement portal | 5 min | L3 | Not attempted | **F** |
| 10.4 | Sanity-check value against market rates (₹2 Cr armoured vehicle = too low) | 2 min | L4 | Not attempted | **F** |
| 10.5 | Completion dates fall in NIT-required window | 1 min | L2 | Temporal extractor counts dates; no NIT-window check | **C** |
| 10.6 | Contracting officer's signature plausibility | 2 min | L4 | Not attempted | **F** |

10.4 — *market-rate plausibility* — needs a price-history corpus. No
quick fix.

---

## Phase 11 — Stamp / seal authenticity

| # | Task | Lvl | Today | Grade |
|---|---|---|---|---|
| 11.1 | Rubber stamp genuine (round, ink consistent, overlap with text) | L4 | OCR reads through stamps; no authenticity classifier | **F** |
| 11.2 | "Computer signature" — perfect baseline → scan-and-pasted | L4 | Not attempted | **F** |
| 11.3 | Stamp misaligned with page edge (image-pasted) | L4 | Not attempted | **F** |

Visual forensics is research-grade. Honest F.

---

## Phase 12 — Cross-bidder pattern (collusion signals)

This is supposed to be one of our headline features.

| # | Task | Lvl | Today | Grade |
|---|---|---|---|---|
| 12.1 | Compare registered addresses | L2 | `detect_address_collision()` is solid | **A** |
| 12.2 | Common phone numbers / email domains | L2 | Email captured; no shared-domain rule | **C** |
| 12.3 | Sequential DD numbers | L2 | Not implemented (see 2.6) | **F** |
| 12.4 | PDF metadata cluster (creation timestamp, author, software) | L2 | `date_proximity` covers mod-time; author/creator missing | **C** |
| 12.5 | Verbatim phrasing overlap across cover letters | L4 | Not done | **F** |
| 12.6 | Common IP at CPPP submission (CCI 2025 marker) | L0 with data | No CPPP integration | **F** |
| 12.7 | **Same individual signs as Director on Bidder A and Authorised Signatory on Bidder B** | L4 | Not attempted — and this is the classic Indian-cartel signal | **F** |

12.7 is half a day. Signatures + signatory names are extracted on
every cover letter; we just don't compare them.

---

## Phase 13 — Composing the TEC committee report

| # | Task | Lvl | Today | Grade |
|---|---|---|---|---|
| 13.1 | Committee constitution paragraph | L0 | Generated | **B** |
| 13.2 | Per-bidder per-criterion narrative in *committee voice* | L3 | Cell-level explanations only; not stitched into TEC narrative | **C** |
| 13.3 | Tabulate qualified vs disqualified with reasons | L1 | Generated | **B** |
| 13.4 | Recommendation paragraph | L2 | Generated | **B** |
| 13.5 | Reconcile *member* dissent (officer-vs-officer) | L3 | We capture AI-vs-officer dissent, **not member-vs-member** | **F** |
| 13.6 | Every member signs with date + designation + posting | L0 | sha256 hash exists; **no PKCS#7 / DSC** | **D** |
| 13.7 | Page numbers, staple, index | L0 | Numbering yes; index missing | **C** |

---

## Phase 14 — Coordinating override approval with next-higher authority

| # | Task | Lvl | Today | Grade |
|---|---|---|---|---|
| 14.1 | Identify GFR rule that permits override | L3 | Schema has `gfr_rule_number`; **not surfaced at the override moment** | **D** |
| 14.2 | Draft override note explaining the deviation | L3 | Free-text; no template, no GFR pre-fill, no side-by-side | **C** |
| 14.3 | Hand to next-higher authority; collect signed approval | L0 | `concurrence_requests` table exists; **no real inbox UI** | **D** |
| 14.4 | Append approval letter to bid file | L0 | Attach point doesn't exist | **F** |

Until the second-officer inbox ships end-to-end, "real second-officer
concurrence" is D-grade fiction.

---

## Phase 15 — Dealing with the inevitable corrigendum mid-evaluation

| # | Task | Lvl | Today | Grade |
|---|---|---|---|---|
| 15.1 | Read corrigendum, identify changed clauses | L2 | Tables exist; UI diff partial | **D** |
| 15.2 | **Per bidder, decide whether they responded under v1 or v2** | L3 | Not implemented — bidder responses aren't tagged with criterion version | **F** |
| 15.3 | Re-evaluate affected (bidder × criterion) cells | L1 | `evaluations.criterion_version` stored; re-trigger is manual | **C** |
| 15.4 | Footnote in TEC report: "evaluation used version 2 effective DD-MM-YYYY" | L2 | Audit chain has data; report doesn't render | **D** |

15.2 is the exact failure the Calcutta HC December 2023 ruling
targets. Schema knows the version; UI hasn't connected bidder
response timestamps to corrigendum effective dates. Half a day, hard
defensibility hole.

---

## Phase 16 — Defending the decision 3–7 years later (CVC / writ / DG review)

| # | Task | Lvl | Today | Grade |
|---|---|---|---|---|
| 16.1 | Locate the file | L0 | DB + audit chain | **B** |
| 16.2 | Reconstruct criterion text *as-of* a date | L2 | `criterion_versions` holds it; no point-in-time API | **C** |
| 16.3 | Reproduce the rationale (doc, page, figure, rule) | L3 | Defence Vault — real and working | **A** |
| 16.4 | Demonstrate no destructive edits (chain unbroken) | L0 | Hash-chained `audit_events` + DB triggers | **A** |
| 16.5 | Every officer who touched it identified themselves | L0 | `actor` FK on every touch; PDF signatures still missing | **C** |
| 16.6 | Reproduce the verdict on a fresh machine | L0 | `08_reproduce.py` verifies *file hashes*, **not** that the LLM produces byte-identical output | **C** |
| 16.7 | Show how AI was used and where the officer overrode it | L2 | Route + officer-decision capture is genuine | **A** |

16.6 is a quiet over-claim. The script verifies the *vault* is
intact, not that the *evaluation* re-runs identically. The vault
README should say so.

---

## Synthesis

### TOP 5 — WE ARE BEATING THE OFFICER

| # | Task | Why we beat |
|---|---|---|
| 1 | Audit-chain integrity (16.4) | Hash-chained, append-only, DB-trigger-enforced. No paper file does this. |
| 2 | Numeric measurement-rule on multi-year figures (8.3) | Returns REVIEW where a hurried trainee FAILs. |
| 3 | Defence Vault reconstruction (16.3) | One click for a week-long reconstruction. Manifest + reproduce script genuinely novel. |
| 4 | Document-checklist extraction (3.1) | A 30-minute task in seconds; output an officer can trust. |
| 5 | Address-collision + PAN/GSTIN-segment cross-check (12.1, 6.2) | Cheap, deterministic, never tires. Hour-6 officers miss what regex catches every time. |

### TOP 5 — WE ARE ONLY SIMULATING (the panel will catch us)

| # | The lie | What's actually missing |
|---|---|---|
| 1 | "Real second-officer concurrence" (14.3) | No inbox, no notification, no acceptance flow; field stays NULL in production |
| 2 | "Corrigendum lifecycle" (15.1, 15.2) | Bidder responses are not tagged with the version they responded against; Calcutta HC story cannot be told |
| 3 | "Byte-identical reproducibility" (16.6) | Reproduce script verifies file hashes, not LLM output. We mean "byte-identical archive". |
| 4 | "Confidence Mosaic" — five bars per cell | Officer cannot click a weak bar and act on it. Decoration that *looks* like cognition. |
| 5 | "Real CVC / GeM debarment check" (Phase 1) | Local registry seedable but in practice empty; no scheduled refresh; debarred bidder passes silently |

### TOP 5 — UNTOUCHED GAPS TO CLOSE

| # | Task | Why next | Effort |
|---|---|---|---|
| 1 | GST portal liveness anchored to bid-date (9.1, 9.2) | Public, free, the most embarrassing miss | 1 day |
| 2 | Sequential-DD detection (2.6, 12.3) | Exact CCI 2025 cartel signature; cited in our domain doc; smell test silent | 0.5 day |
| 3 | UDIN + FRN verification (7.1, 7.2) | Two CA-fraud signals every officer checks; ICAI portals are public | 2 days |
| 4 | Common-signatory cross-bidder (12.7) | Signatures + names already extracted; just compare | 0.5 day |
| 5 | Bidder-version-tag-against-corrigendum (15.2) | Calcutta HC requirement; we have the data, we don't connect it | 1 day |

---

## Hidden cognition the panel will probe

| Hidden move | Where it bites |
|---|---|
| Multi-year roundness — ₹15.00 Cr × 3 years exactly | 8.5 |
| Going market rate for armoured patrol vehicles 2025-26 | 10.4 |
| Recognising a CA firm name flagged in a prior tender | 7.4 |
| Cover letters with identical idiosyncratic phrasings | 5.4 |
| Freshly-Udyam (<90 days) MSE certificate as a known mask | 2.4 |
| Estimated cost set just below a delegation threshold | 4.6 |
| Courier service the previously-DQ'd bidder used | 1.1 |
| "Computer signature" with perfect baseline | 11.2 |

The honest position: name what we don't do. The Pre-Mortem Brief
should *list* the things the system did not check, so the officer
isn't lulled.

---

## Three days before the panel — what to ship

1. **Day 1 AM** — sequential-DD + common-signatory smell-test rules.
2. **Day 1 PM** — GST portal liveness anchored to bid-date.
3. **Day 2 AM** — bidder-response-version-vs-corrigendum tagging.
4. **Day 2 PM** — second-officer real inbox.
5. **Day 3 AM** — FRN existence check on CA certs (UDIN if time).
6. **Day 3 PM** — honest README in the Defence Vault: archive
   integrity is what the script proves; LLM reproducibility comes
   from prompt-hash caching plus a frozen model snapshot. Stop
   over-claiming.

If we ship those six, every D moves to C, every C moves to B, the
simulation gaps close. F-grade items (visual stamp forensics,
market-rate plausibility) we *say* are F and position as the human
officer's irreplaceable contribution.

The panel will not catch us if we name our own gaps before they do.
