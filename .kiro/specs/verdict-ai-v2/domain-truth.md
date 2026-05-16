# Domain truth — Indian government tender evaluation

> **Purpose.** This document is the canonical product-side reference for VerdictAI.
> It captures *how Indian government tender evaluation actually works in 2025–26* —
> the law, the workflow, the people, the documents, the failure modes — sourced
> from publicly available material rather than from imagination.
>
> Every product decision (UI, schema, flow, copy) must be traceable to a fact in
> this document. Where a fact is contested, both interpretations are listed.
> Where the public sources are silent on a detail, this is marked **[gap]**.
>
> **Scope.** Goods and services procurement by central-government ministries,
> central-armed police forces (CRPF / BSF / CISF / SSB / ITBP), public sector
> undertakings (PSUs), and (by analogy) state-government departments using GFR
> 2017 plus the central manuals.
>
> **Sources.** Citations inline. Last research pass: May 2026.

---

## 1. Legal foundation — there is no single procurement act

India does not have a unified public procurement law. The framework is a stack
of executive instructions, manuals, and judicial principles that procuring
entities follow.

| Instrument | Status | Coverage |
|---|---|---|
| **General Financial Rules, 2017 (GFRs)** | Executive instructions | Chapter 5 — works · Chapter 6 — goods and services |
| **Manual for Procurement of Goods, 2024 (MPG 2024)** | Guideline | Goods, including auto bid extensions, LD norms |
| **Manual for Procurement of Works, 2019 (MPW)** | Guideline | Construction, civil works |
| **Manual for Procurement of Consultancy Services, 2025 (MPS 2025)** | Guideline | Consultancies |
| **Manual for Procurement of Non-Consultancy Services, 2025** | Guideline | Non-consultancy services |
| **General Instructions on Procurement and Project Management, 2021** | Overrides conflicting prior instructions | Cross-cutting |
| **Indian Contract Act 1872** + **Sale of Goods Act 1930** | Statute | Contract law applied to award |
| **Competition Act 2002** | Statute | Bid rigging, cartels |
| **Article 14 of the Constitution** | Constitutional | Procurement must be transparent, non-arbitrary, non-discriminatory; courts apply this when reviewing tender disputes |
| **CVC guidelines** | Vigilance directives | Layered on top of GFRs; checklists for procurement officers |

Source: ICLG India 2026 chapter — *"There is no singular legislation that
encompasses all aspects of public procurement in India"*, Department of
Expenditure GFR 2017. Content rephrased for compliance with licensing.

**Implication for our product.** We cannot hard-code a single statutory
checklist. Eligibility rules come from *the tender's NIT clauses*, sometimes
modified by *amendments via corrigenda*, and are interpreted with reference to
*GFR rule numbers*. The product must store all four.

---

## 2. The actors — who is in the room

### The procuring entity
A ministry, department, attached/subordinate office, autonomous body, central
public sector enterprise, or central-armed police force. For CRPF specifically:
the procurement chain runs from **Commandant** (battalion-level) →
**Inspector General** → **Director General (DG)** with progressively higher
financial powers.

> The Ministry of Home Affairs has delegated financial powers up to
> commandant level for arms, ammunition, clothing/tentage, machinery and
> equipment. DGs of CRPF/BSF/etc. have been empowered to sanction **up to
> ₹15 crore for major projects, ₹1 crore for minor works**.
> *Source: Times of India, 6 September 2017; News18, July 2022.*

### The Tender Evaluation Committee (TEC)
A multi-member committee (typically 3–7 officers) constituted to evaluate bids.
Members are senior officers from finance, technical, user, and procurement
streams. Members must declare impartiality (no conflict of interest with any
bidder).

The TEC is the entity our product is built for. **The TEC's report is what
we are accelerating.**

### The bidders
Private companies (or PSUs / cooperatives / MSMEs) submitting bids against a
tender. Categories that get special treatment under GFR/MPG:
- **MSME / Udyam-registered**: EMD exemption, price preference
- **Make-in-India / domestic manufacturer**: price preference
- **Startups under DPIIT**: turnover relaxation
- **Foreign bidders**: only for tenders with international competitive bidding

### The vigilance and audit chain
- **Internal vigilance** — Chief Vigilance Officer (CVO) of the procuring entity
- **Central Vigilance Commission (CVC)** — apex body, sets vigilance guidelines
- **CAG (Comptroller and Auditor General)** — post-award audit
- **Courts** — writ jurisdiction under Article 14 / 226 if tender process is
  challenged. Indian Supreme Court has repeatedly held that **post-bid
  corrections cannot be entertained** even if they would yield more revenue;
  *State of MP v Suresh Mehra (12 Sep 2025)*. Calcutta HC similarly ruled in
  Dec 2023 that **post-submission tender alterations are arbitrary and violate
  Article 14**.

**Implication.** The audit trail in the product must be defensible against
all four. Hash-chained, append-only, byte-identical reproducible.

---

## 3. The end-to-end workflow

Public tendering in India follows a well-defined sequence. Steps in *italics*
are out of scope for VerdictAI; **bold** steps are the ones our product touches.

```
   Pre-tender                   Tendering                  Award
 ┌──────────────┐    ┌─────────────────────────────┐    ┌───────────────┐
 │ 1. Need      │    │ 4. NIT published on CPPP    │    │ 9. L1 / H1    │
 │ 2. Approval  │ →  │ 5. Pre-bid + corrigenda     │ →  │ 10. AOC       │
 │ 3. Indent    │    │ 6. Bid submission           │    │ 11. Contract  │
 └──────────────┘    │ 7. Technical bid opening    │    └───────────────┘
                     │    + preliminary exam       │
                     │ 8. TECHNICAL EVALUATION ★   │  ← VerdictAI
                     │ 9. Financial bid opening    │     accelerates
                     └─────────────────────────────┘     this step
```

### 3.1 Pre-tender (out of our scope)
- The user department raises an **indent** — what is needed, why, in what
  quantity, by when.
- Administrative and financial sanction is obtained from the competent
  authority based on the financial powers delegation.
- The procurement category (open tender / limited tender / single tender /
  GeM / framework agreement) is decided per GFR Rule 161-166.

### 3.2 Tender publication and submission
- Tenders **must be published on the Central Public Procurement Portal
  (CPPP)** — `eprocure.gov.in` — for all central ministries, CPSEs, and
  autonomous bodies. Publication is mandatory.
- A **Notice Inviting Tender (NIT)** is the legal document. Bidders download
  it free of cost. The NIT typically contains:
  - Tender number, brief description, estimated cost
  - **EMD (Earnest Money Deposit)** amount and instrument
  - **Eligibility / pre-qualification criteria**
  - **List of mandatory documents** (the document checklist)
  - Technical specifications
  - Bid submission deadline and bid opening date/time
  - Pre-bid meeting date (if any)
- During the bid period, the procuring entity may issue **corrigenda** that
  amend any part of the NIT. *Research finding (LEAP Journal 2020): a
  significant proportion of high-value Indian tenders are modified via
  corrigendum.* Corrigenda may extend deadlines, change thresholds, alter
  scope, clarify language. Each corrigendum is a distinct document linked
  to the parent NIT.
- Bidders submit their bids electronically through CPPP using a **digital
  signature certificate (DSC)**.

### 3.3 Two-bid system
Most non-trivial tenders use the **Two-Bid System** (also called Two-Envelope
or Two-Cover system) per GFR. The bidder submits two sealed/encrypted
envelopes simultaneously:
- **Envelope 1 — Technical bid**: company information, eligibility documents,
  technical compliance, methodology
- **Envelope 2 — Financial bid (Price bid)**: per-line item pricing,
  total cost

Envelope 2 is **opened only for bidders whose Envelope 1 passes evaluation**.
This is the key procedural rule that gives us our product surface — *the
technical evaluation determines who gets their price seen at all*.

Source: Lexology (procurement disputes with the Indian Government, 2021):
> *"The technical bids are opened by the procuring authority in the first
> instance, and evaluated by a competent committee. At the second stage, the
> financial bids of only those bidders are opened whose offers are found to
> be technically acceptable."* Content rephrased for compliance with licensing.

### 3.4 Bid opening and preliminary examination
On the appointed date the TEC meets and:
1. Logs every bid received (digital + offline if any)
2. Verifies each bidder paid the **tender fee** (or is exempt)
3. Verifies each bidder paid the **EMD** (or is MSME-exempt)
4. **Preliminary examination**: checks each bid against the *list of
   mandatory documents*. A bid missing any mandatory document is
   summarily rejected at this stage — the technical bid is not even
   evaluated.

This is the **document checklist** stage. In practice the TEC scribe
maintains a spreadsheet with bidders × required documents and ticks
off what's present. This step alone can disqualify 20–40% of bidders.

### 3.5 Technical evaluation (the heart of our product)

For each bidder that survives preliminary examination, the TEC evaluates
technical compliance against the eligibility criteria spelled out in the
NIT. **This is where days of officer time are consumed.**

Eligibility criteria fall into recurring categories:

| Category | Example clause | What the TEC must verify |
|---|---|---|
| **Financial — turnover** | "Avg. annual turnover ≥ ₹15 Cr in last 3 FYs" | CA-certified turnover statement; year-by-year; standalone vs consolidated; FY alignment |
| **Financial — net worth** | "Positive net worth ≥ ₹3 Cr" | Audited balance sheet of immediately preceding FY |
| **Financial — solvency** | "Bank solvency certificate ≥ ₹X" | Banker's letter, on letterhead, dated within validity window |
| **Statutory — GST** | "Valid GST registration" | GSTIN format match (15-char), live status, current validity |
| **Statutory — PAN** | "Valid PAN" | PAN format match (AAAAA9999A), 4th char encodes entity type |
| **Statutory — incorporation** | "Registered under Companies Act / Partnership Act" | Certificate of Incorporation, MoA/AoA |
| **Quality — ISO** | "ISO 9001:2015 from NABCB-accredited body" | Certificate authenticity; accreditation body match |
| **Experience — past projects** | "3 similar projects in last 5/7 years" | Completion certificates from ordering authority; date, value, scope match |
| **Capacity — manufacturing** | "Adequate manufacturing capacity for stated quantity" | Plant capacity, employee count, supply order history |
| **Make-in-India / MSME** | Class I / Class II local supplier; Udyam | UDYAM-XX-99-9999999 format; manufacturing percentage declaration |
| **Composite** | A single clause bundling several requirements | Each sub-criterion independently |
| **Authorization** | "OEM authorization for branded product" | OEM letter on letterhead; valid for the tender period |
| **Bid capacity** | "Available bid capacity ≥ tender value" | Computed formula (e.g. *2.5 × N × A* − B) |
| **Negative list** | "Not blacklisted by GeM / CVC / department" | CVC debarred entities list, GeM blacklist, internal department list |

**Source for typical criteria:** Tata Nexarc procurement guides; CPWD and
MES tender notices; Civil Mentor blog; Scribd preliminary-examination
templates; Construction World *MES Mhow Solar tender* (Oct 2025).

The TEC must evaluate each criterion for each bidder. For 8 criteria and 5
bidders that's 40 cells. Each cell requires reading documents, comparing
against the criterion text, deciding pass/fail/review. Each takes between
**2 and 30 minutes** of officer time depending on complexity.

### 3.6 The TEC report
Output of the technical-evaluation stage. Contains:
- The committee's constitution and signatures
- For each bidder: a tabulated comparison against each criterion
- A summary list of "technically qualified bidders"
- A summary list of bidders rejected, with reasons
- Recommendation to open financial bids for qualified bidders

This is the artefact our product should generate. Officers sign the PDF
and it becomes the basis for the next step.

### 3.7 Financial bid opening, L1 determination, AOC

For tenders qualifying for our product but ending in our scope only with
the TEC report:

- **L1**: Lowest financial bid (for goods/works)
- **H1**: Highest revenue (for revenue contracts like leasing)
- **QCBS** (Quality- and Cost-Based Selection): typical for consultancy —
  technical score (60–80%) + financial score (20–40%) combined per a
  pre-declared formula. World Bank QCBS template common.
- **Acceptance of Tender (AOC)** issued; contract signed; performance
  security deposited.

### 3.8 Post-award (out of scope)
Performance security, contract execution, payments, dispute resolution.
VerdictAI may be referenced years later in a CVC inquiry but does not
operate post-award.

---

## 4. The pain points — why this takes weeks

Synthesised from procurement guides, NDTV/ToI/News18 coverage of CRPF/CAPF
delays, the LEAP Journal study on tender modifications, ICLG India 2026,
and forum discussions on Quora / Lexology / Tata Nexarc.

### 4.1 Volume
A single tender attracts 5–50 bids. Each bidder's package can be 200–1000
pages of mixed-quality PDFs, photocopies, scanned images, and digital
forms. **One officer reads 10,000+ pages per tender.**

### 4.2 Heterogeneous document quality
Real submissions include:
- Native digital PDFs with selectable text
- Scans of photocopies of photocopies (multi-generational copying)
- Phone photographs taken at angles, with skew, glare, and stamps
- Faxed documents with horizontal banding
- Documents in Hindi or regional languages alongside English
- Hand-stamped certificates where the rubber stamp partly covers the figure

GeM and CPPP do not enforce a fixed document format. The officer absorbs
all of this variance.

### 4.3 Corrigendum drift
The LEAP Journal analysis of public-procurement modifications (2020)
found that **a large proportion of tenders see at least one modification,
especially high-value tenders**. By the time the TEC sits, the
"specification" the bidders responded to may differ from the original
NIT. The officer must mentally apply the right corrigendum to the right
clause for the right bidder.

### 4.4 Ambiguous language
Phrases like *"similar work"*, *"adequate capacity"*, *"reputed organisation"*
are routinely interpreted differently by different evaluators on the same
committee. There is no formal record of how a phrase was resolved in
prior tenders from the same department — institutional memory is lost
when officers rotate.

### 4.5 Cognitive load and burnout
Officers report (in industry surveys quoted by IASPoint and ETInfra) that
processes which previously took weeks now stretch to months due to
volume + scrutiny pressure. Manual cross-checking causes well-documented
attention drift errors after 30–45 minutes of continuous review.

### 4.6 Fraud vectors

The TEC must defend against deliberate fraud as well as honest mistakes.
Documented patterns from public CCI/ED/CVC cases:

| Pattern | Example case | Detectable how |
|---|---|---|
| **Bid rigging / cartel** | ONGC cement tender 2025 — 5-yr probe found Dalmia Bharat / India Cements / Shree Digvijay colluded; bid prices used "lucky numbers" | Identical/parallel pricing; sequential DDs; same IP; near-identical timestamps |
| **Police-tender bid rigging** | CCI 2025 — common IP and sequentially numbered demand drafts among "competing" bidders | IP / DD-number proximity |
| **Fake bank guarantees** | Reliance Power barred 3 yrs by SECI (Nov 2024); ED chargesheet in battery storage project | Verify guarantee with issuer; format checks |
| **Parent-company financial substitution** | Smaller bidder submits parent's audited statements as their own | Entity-name fuzzy match between bidder name and figures source |
| **Address collision** | Two "competing" bidders share a registered address | String-normalised comparison |
| **Document recycling** | Identical scanned pages submitted by two bidders | Byte-level (sha256) document compare |
| **Date-of-modification clustering** | Multiple bidders' files have modification timestamps within minutes | PDF metadata mtime cluster |
| **Round-number anomaly** | Turnover figures rounded to the nearest crore implausibly often | Statistical: trailing-zero density |
| **Forged certificates** | ISO certificates from non-accredited bodies; stamps photoshopped | Accreditation body lookup; visual stamp anomaly check |
| **Subsidiary earnings management** | Private subsidiaries of listed firms manipulate earnings to qualify | Cross-check with consolidated financials of parent |

Source: KS&K *Public Procurement Cartel India* (2025); Business Standard
*Lucky Numbers and Collusion: Cement Cartel Targeting ONGC* (Mar 2026);
TaxGuru *CCI Finds Bid Rigging in Police Tenders via Common IP & Sequential
DDs* (Apr 2026); Financial Express *SECI bars Reliance Power for 3 years*
(Nov 2024); SSRN *Earnings Management in Private Subsidiaries of Public
Firms* (Feb 2025).

### 4.7 Defensibility against future inquiry

The officer's deepest fear is a CVC inquiry **3–7 years after** the award.
The CVC has flagged 23 cases of non-compliance by government departments
in its latest annual report (Business World, Mar 2026). When an officer is
asked "why did you decide this?", they must produce:

- The exact criterion text as it stood at decision time (which version of
  the NIT, which corrigenda applied)
- The exact document and page they were looking at
- The reasoning they applied
- Any second-officer concurrence
- The audit timestamp

**Today this evidence does not exist in retrievable form.** TEC minutes are
narrative, not criterion-level. This is the gap our Decision Memory Vault
fills.

### 4.8 Legal constraints we must respect
- *State of MP v Suresh Mehra (12 Sep 2025)*: post-bid corrections are not
  permissible. We cannot let the system "fix" a missing document after
  bid submission.
- *Calcutta HC Dec 2023*: post-submission tender alterations violate
  Article 14. We cannot retroactively change criterion text after a
  bidder has responded.
- *Patna HC Mar 2026*: a bidder has no enforceable right after the bid
  validity period expires. Disqualification challenges have a hard
  time-window.
- **No GeM / CPPP API for direct tender ingestion**: tenders must be
  manually uploaded by the officer or pulled from CPPP HTML / PDF.

---

## 5. Document inventory by criterion type

What documents typically support each criterion category — the TEC's
mental map:

### Financial / turnover / net worth
- Audited balance sheets for last 3–5 financial years
- CA certificate of turnover (with FRN + UDIN)
- IT returns acknowledgements
- Bank solvency certificate (on bank letterhead, ≤ 6 months old)

### Statutory / regulatory
- GST registration certificate (certificate of registration in Form GST REG-06)
- PAN card
- TAN allotment letter
- Certificate of Incorporation (Form INC-11) / Partnership deed
- MoA / AoA
- ESI / EPF registration (if applicable)
- Professional Tax registration (state-specific)

### Quality / certification
- ISO 9001:2015 (with NABCB or equivalent accreditation)
- BIS / IS marking (for goods)
- BEE star rating (for energy)
- CE / FCC / equivalent (for electronics imports)

### Experience
- Completion certificates from ordering authorities
- Purchase orders with proof of supply
- Performance certificates from clients
- For consultancies: work-order acceptance + completion proof

### Authorization
- OEM authorization letters
- Manufacturer authorisation certificate (MAF)
- Power of attorney (if signatory ≠ director)
- Board resolution authorising the signatory to bid

### MSME / preferential
- Udyam registration certificate
- Make-in-India self-declaration (Class-I / Class-II)
- Local-content certificate
- DPIIT startup recognition (if claiming startup relaxations)

### Bidder identity
- Cover letter on letterhead
- Bidder profile / company brochure
- Contact details (designated point of contact)

### Bid security and tender fee
- DD / e-payment / bank guarantee for EMD
- DD / e-payment for tender fee (if not exempt)
- MSE exemption certificate (if claiming exemption)

### Affidavits and undertakings
- Non-blacklisting affidavit (notarised, on stamp paper)
- Conflict-of-interest declaration
- Integrity pact (for tenders ≥ ₹10 Cr typically)

This list is the **superset**. A given tender selects 8–20 of these.

---

## 6. The seven officer personas we serve

Synthesised from public CRPF / CAPF / MoD / state-PWD job descriptions and
forum discussions on Quora / LinkedIn:

### 6.1 The TEC Chair (senior officer, e.g. DIG / DC)
Signs the final report. Spent 25+ years in service. Bifocals, large-screen,
prefers paper for final reading. Most concerned about **defensibility**.

### 6.2 The TEC Member-Secretary (mid officer, e.g. Commandant / SP)
Does the actual cross-checking. Sits with Excel + 10 PDFs open. Most
concerned about **speed and not missing anything**.

### 6.3 The TEC Technical Member
Subject-matter expert — for vehicles, the MT officer; for IT, the IT
officer. Most concerned about **technical correctness of specs**.

### 6.4 The TEC Finance Member
From accounts / finance. Most concerned about **arithmetic and FY
alignment** of financial figures.

### 6.5 The CVO (Chief Vigilance Officer)
Reviews high-value tenders for vigilance angle. Most concerned about
**conflict of interest, single-source justifications, and audit trail
gaps**.

### 6.6 The Cell Operator (clerk / JE)
Uploads tenders, downloads bids, prints copies. Most concerned about
**speed and getting credit**.

### 6.7 The future inquiry officer (CVC / CAG / court)
Not present at decision time. **The product must satisfy this person 3–7
years later.**

---

## 7. The states a tender passes through

| State | Triggered by | Officer action |
|---|---|---|
| `DRAFT` | Tender created | Fill basic metadata |
| `DOCUMENTS_PENDING` | Saved | Upload NIT |
| `DOCUMENTS_PROCESSING` | Upload | Wait for OCR + extraction |
| `DOCUMENTS_READY` | OCR complete | Click "Extract criteria" |
| `CRITERIA_EXTRACTING` | Extract clicked | Wait for L2 |
| `CRITERIA_PENDING_REVIEW` | L2 complete | Review extracted criteria, edit, approve |
| `CRITERIA_APPROVED` | Approve all | (system) checklist matching begins |
| `CHECKLIST_PENDING` | Bidders registered | Resolve missing-doc cases |
| `PRELIMINARY_DONE` | Preliminary finalised | (system) evaluation eligible to run |
| `EVALUATING` | Evaluate clicked | Wait |
| `EVALUATIONS_COMPUTED` | L4 complete | Open the matrix |
| `HITL_PENDING` | Items routed | Decide each cell |
| `EVALUATION_COMPLETE` | Last cell decided | Generate report |
| `REPORT_GENERATED` | Report PDF made | Sign & file |
| `FINALIZED` | Officer signed | Locked |

This sequence is enforced by `backend/core/state_machine.py`.

---

## 8. Where AI helps and where it does not

### Where AI is a multiplier
- Reading 10,000 pages and surfacing the relevant 50
- Cross-checking format compliance (PAN regex, GSTIN format)
- Aligning a clause's text with a bidder's verbatim quote
- Surfacing anomalies the officer would catch on their best day
- Producing a draft report the officer can edit

### Where AI must NOT decide
- Whether to disqualify a bidder for a missing document — the officer signs
  that off
- Whether ambiguous experience qualifies as "similar work" — the officer
  interprets that, with AI showing precedent
- Whether to override a mandatory criterion FAIL — GFR rule must be
  applied by the officer, with second-officer concurrence
- Whether a stamp/signature is genuine — visual judgement remains human

This is the **decision-support framing**. The product is the officer's
instrument. Every output reads as *"here's what I see, you decide"*.

---

## 9. The seven design principles that follow

1. **Decision-support, not decision-making.** The product surfaces evidence
   and confidence; the officer decides. AI never asserts a verdict bare —
   only "I am 87% confident this satisfies clause X."

2. **Source-click everything.** Every AI claim must trace to a specific
   document, page and bbox. Two clicks from claim to evidence.

3. **Preserve every version of every artefact.** NIT, corrigenda,
   bidder docs, criterion text, officer decisions — all versioned. No
   destructive edits.

4. **Hash-chain the audit trail.** Append-only, byte-identical
   reproducible. The TEC report must survive a CVC inquiry 5 years later.

5. **Two branches must agree.** Rule-based + LLM run in parallel; high
   confidence requires both branches. Disagreement = officer review.

6. **Never silently disqualify.** Every disqualification routes through
   an officer who confirms it, with a structured reason captured.

7. **The form follows the law.** Mandatory criteria cannot be auto-
   committed. Override of mandatory FAIL requires a second-officer.
   GFR rule numbers render in the UI where they apply.

---

## 10. Open questions / **[gap]** in public sources

These need either a CRPF SME interview or a careful reading of internal
manuals to answer:

- Exact threshold values that distinguish open / limited / single tender
  for CRPF in 2026 (the GFR thresholds are public; CRPF-specific
  delegations are not).
- Standard CRPF document checklist for a goods tender vs a services
  tender.
- The internal SLA the TEC must meet (time from technical-bid opening
  to TEC report submission).
- Internal vigilance escalation path within CRPF.
- Specific GFR rule numbers used in CRPF NIT clauses (Rule 173-178 series
  is generic).
- Whether the MoH / DG-level office requires PKCS#7 signed PDFs or
  e-Office integration for the TEC report.

These are documented here so we know what we're assuming.

---

## 11. Sources (compliance attribution)

All snippets in this document have been paraphrased to comply with
licensing restrictions. Direct verbatim quotes ≤ 30 words per source.

Primary public sources consulted:

- [ICLG India Public Procurement 2026](https://iclg.com/practice-areas/public-procurement-laws-and-regulations/india)
- [Chambers India Public Procurement 2026 Practice Guide](https://practiceguides.chambers.com/practice-guides/public-procurement-2026/india)
- [eProcurement System (CPPP)](https://etenders.gov.in/eprocure/app)
- [NIC Government eProcurement System](https://www.nic.gov.in/project/government-eprocurement-system/)
- [Procurement disputes with the Indian Government — Lexology, 2021](https://www.lexology.com/library/detail.aspx?g=89ac0368-bdb0-4eb2-8ec8-159f530d9a5b)
- [Tata Nexarc — Eligibility criteria for government tenders in India](https://blog.tatanexarc.com/tenders/government-tender-eligibility/)
- [Tata Nexarc — EPC tender process](https://blog.tatanexarc.com/da/epc-tender-process/)
- [Tata Nexarc — Extension of time / corrigenda](https://blog.tatanexarc.com/tenders/extension-of-time/)
- [Civil Mentor — Bid documents checklist](https://ecivilmentor.blogspot.com/)
- [LEAP Journal — Tender modifications analysis, 2020](https://blog.theleapjournal.org/2020/11/what-ails-public-procurement-analysis.html)
- [IASPoint — AI in tender evaluation, Sep 2025](https://iaspoint.com/ai-revolutionises-government-tender-evaluation-process/)
- [ToI — MHA finance powers to DGs of CRPF/BSF/NIA, Sep 2017](https://timesofindia.indiatimes.com/india/mha-gives-more-finance-powers-to-dgs-of-crpf-bsf-nia/articleshow/60394866.cms)
- [News18 — MHA powers for CAPF procurement, Jul 2022](https://www.news18.com/news/india/home-ministry-issues-fresh-guidelines-for-procurement-by-capfs-from-defence-psus-strengthens-hands-of-dgs-5581375.html)
- [NDTV — Rajnath Singh restoration of DG powers, Oct 2015](https://www.ndtv.com/india-news/rajnath-singh-restores-dgs-powers-to-transfers-top-officers-1232765)
- [LiveLaw — Patna HC bid validity ruling, Mar 2026](https://www.livelaw.in/amp/high-court/patna-high-court/patna-high-court-enforceable-right-survives-expiry-bid-validity-period-tender-process-534198)
- [Chambers — No post-bid corrections, Sep 2025](https://chambers.com/articles/no-post-bid-corrections-permissible-supreme-court-reaffirms-sanctity-of-tender-process)
- [SCC Online — Calcutta HC tender alterations, Dec 2023](https://www.scconline.com/blog/post/2023/12/14/tender-alterations-post-bid-submission-deems-arbitrary-and-violative-of-article-14-calcutta-high-court-scc-blog/)
- [Prime Legal — Sunshine Caterers v UoI, Apr 2024](https://blog.primelegal.in/dismissed-and-disqualified-the-high-court-of-delhi-upholds-bid-disqualification-over-documentation-discrepancies/)
- [KS&K — Public Procurement Cartel India, Aug 2025](https://ksandk.com/competition/public-procurement-cartel-india-call-for-enforcement-reform/)
- [Business Standard — Cement cartel targeting ONGC, Mar 2026](https://www.business-standard.com/industry/news/lucky-numbers-and-collusion-how-cement-cartel-targeting-ongc-came-unstuck-126030900490_1.html)
- [TaxGuru — CCI bid rigging via common IP / sequential DDs, Apr 2026](https://taxguru.in/corporate-law/cci-finds-bid-rigging-police-tenders-common-ip-sequential-dds.html)
- [Financial Express — SECI bars Reliance Power, Nov 2024](https://www.financialexpress.com/business/industry-seci-bars-reliance-power-for-3-years-citing-fake-tender-document-3659269/)
- [Business World — ED chargesheet on Reliance Power, May 2026](https://www.businessworld.in/article/ed-charges-reliance-power-for-alleged-fake-guarantees-in-seci-battery-project-582617)
- [Business World — CVC flags 23 cases of non-compliance, Mar 2026](https://www.businessworld.in/article/cvc-flags-23-cases-of-non-compliance-by-govt-departments-569854)
- [SSRN — Earnings Management in Private Subsidiaries, Feb 2025](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5162030)
- [Construction World — MES Mhow Solar tender, Oct 2025](https://www.constructionworld.in/energy-infrastructure/power-and-renewable-energy/military-engineer-services-floats-tender-for-five-mw-solar-om-at-mhow/91408)
- [Lexology — Bid Rigging in Public Procurement: An Indian Perspective, 2022](https://www.lexology.com/library/detail.aspx?g=3d4feacc-c6e2-48cf-bbdc-d9036e725763)
- [Lexology — Public-Private Partnerships procurement process](https://www.lexology.com/library/detail.aspx?g=6026618c-265d-4582-93bf-3eba4e1244df)
- [PRSIndia — Public Procurement Bill 2012](https://prsindia.org/billtrack/the-public-procurement-bill-2012)
- [Wire — India's tortuous defence procurement, Jan 2026](https://m.thewire.in/article/government/indias-tortuous-defence-procurement-process-delay-not-delivery-is-the-only-constant)

> Content from these sources was rephrased for compliance with licensing
> restrictions. Where a single sentence was quoted verbatim it is shown
> in italics with quotation marks and is under 30 consecutive words from
> any single source.
