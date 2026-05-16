# Jury Research — CRPF Hackathon, Theme 3 (AI-Based Tender Evaluation)

> Open-source research only. Where the public record is thin, that is stated explicitly rather than guessed.

---

## 1. Dr. Vipul Kumar, IPS — Inspector General, CRPF (senior-most)

### Background

1999-batch IPS, Karnataka cadre. New Indian Express names him as one of two IGP-rank Karnataka-cadre officers on Central deputation in mid-2024 ([source](https://www.newindianexpress.com/states/karnataka/2024/Jun/13/number-of-ips-officers-of-karnataka-cadre-in-centre-more-than-before)). CRPF's KK-Sector page confirms current posting: "Dr. Vipul Kumar IPS, IG KKS" — Inspector General, Karnataka–Kerala Sector, GC Campus, Bengaluru ([source](https://crpf.gov.in/Dte/Zone/Southern-Zone/KK-Sector)). The "Dr." prefix suggests a doctorate. Earlier postings: Director, Karnataka Police Academy; Commissioner of Police, Mangaluru City (2018, an EC-driven transfer) ([The Hindu](https://www.thehindu.com/news/cities/Mangalore/vipul-kumar-takes-charge-as-police-commissioner/article23591030.ece); [TOI](https://timesofindia.indiatimes.com/city/mangaluru/new-city-police-chief-is-no-stranger-to-poll-exigencies/articleshow/63838776.cms)).

### What he visibly cares about

- **Procurement governance.** The KK-Sector page he heads publishes the Annual Procurement Plan and live tenders (e.g. polymer pistol tender) — he signs off on CAPF procurement at sector scale.
- **Legal defensibility.** That same page records him chairing a 23 May 2025 coordination meeting with the Additional and Deputy Solicitor General for Karnataka High Court — an officer who lives inside the writ-petition zone.
- **Election-grade impartiality.** Reporting calls him "no stranger to poll exigencies."
- No public op-ed, LinkedIn post, or interview by him on AI was found. AI views are inferred from his procurement and judicial footprint, not quoted.

### Likely evaluation lens

A sector-IG who signs procurement plans and meets law officers wants one thing: **it must not lose him a writ petition.** GFR 2017, Manual for Procurement of Goods 2024, CVC guidelines and the GeM workflow are the artefact he is judged on.

### What he will probe

1. "If a disqualified L1 challenges this in CAT or High Court, what record do you produce?"
2. "Where does this sit relative to GFR Rule 173 and CVC's reasonable-and-uniform-criteria guidance?"
3. "On what page of the bid did the model find this fact, and can the officer click to it?"
4. "When the model is wrong — who is accountable?"
5. "Does this work on a scanned, stamped, signed, re-photocopied PDF?"
6. "Show me the audit log. Can it be tampered with after the fact?"
7. "Has CVC / GeM debarment been actually checked, or just claimed?"
8. "Will Section Officer staff and a Commandant agree on the same output?"

### How to win him

| What he wants | What we shipped |
|---|---|
| Legal defensibility | **Append-only audit chain** — every extraction, score, officer action hash-linked, replayable in court |
| GFR/CVC compliance | **Real CVC / GeM debarment registry** integration, not a stub |
| No-hallucination guarantee | **Confidence Veil** + **dual-branch extraction** — every claim carries page+bbox citation; low-confidence cells veiled, not guessed |
| Two-officer concurrence | **Real second-officer concurrence inbox** — mirrors existing two-signature CRPF file-noting practice |
| Reproducibility before a court | **Byte-identical reproducibility** — same tender re-run yields the same verdict |
| Pre-decision risk surfacing | **Pre-Mortem Brief** — "before you sign, here are the three reasons this could be challenged" |

Pitch line: *"Sir, this is not an AI that decides. It is an AI that prepares a defensible file."*

---

## 2. Chinmay Shekar, Assistant Commandant, CRPF (junior officer voice)

### Background — honest disclosure

We could not find a public profile (LinkedIn, news, CRPF directory) for an AC named Chinmay Shekar via open web search. The CRPF Academy's "Making of an Officer" page describes the AC role generally — tactical, physical, professional competency, decision-making in all situations ([source](https://crpf.gov.in/Training/CRPF-Academy/Making-of-an-officer)) — but does not list him.

The rest is **role-based inference**. The AC is the entry-level Group A rank; ACs typically have ~0–7 years of service, lead a company on the ground, and rotate through anti-Naxal, J&K, and admin postings.

### Likely evaluation lens

The panel's reality check. He has personally handled file-notings, GeM rate contracts at unit level, store-purchase committees, and small-procurement misery the IG never sees. He'll test whether the tool actually helps the officer who has to use it on a Tuesday afternoon between a parade and a court appearance.

### What he will probe

1. "How long from PDF upload to a usable summary? Be honest."
2. "Can I run this on the unit's machine, or does it need a stable pipe in Bastar?"
3. "Walk me through the screen a Section Officer sees at 11:55 PM on closing day."
4. "What does it look like when OCR fails? Crash, or tell me?"
5. "How many clicks from 'open tender' to 'I can sign the noting'?"
6. "If I disagree with the model's ranking, can I override, and is my reason recorded?"
7. "Does this remove my work, or just move it earlier in the day?"
8. "Will my Commandant trust this enough to actually look at it?"

### How to win him

| What he wants | What we shipped |
|---|---|
| Speed on real, ugly scans | **Dual-branch extraction** (text + vision) handles photocopied, stamped, skewed pages |
| Officer-friendly UX | Single-screen verdict view; click any number, see the page |
| No silent failure | **Confidence Veil** — when unsure, says so visibly instead of hallucinating |
| Override with dignity | **Concurrence inbox** captures the officer's reason; audit chain preserves it |
| Real-world doc quality | Demo on degraded scan, CA-stamped certificate, corrigendum bundle (already in `backend/demo_data`) |
| Pre-Mortem Brief | A two-paragraph "what could go wrong" he can paste into a noting |

Pitch line: *"The goal isn't to replace the dealing officer. It's to make sure he can finish the noting before the file goes upstairs."*

---

## 3. Rakesh Agarwal, Founder, PDG Partners (industry/strategy voice)

### Background — honest disclosure

A "PDG Partners" exists at [pdginvestments.com](https://pdginvestments.com/), self-describing as an investment and advisory firm with $1–20M direct equity cheques, headquartered London. **The site does not name a "Rakesh Agarwal" as founder.** Open web search could not definitively tie our jury member to that firm — "Rakesh Agarwal" is a common name and several distinct people surface (KPMG Singapore tech-consulting partner, GenXAI / ACG India founder, SnapStream's Rakesh Agrawal).

The rest treats him as **a strategy/advisory founder evaluating a govt-tech prototype**, without attributing specific quotes.

### Likely evaluation lens

A founder on a CAPF hackathon panel isn't there to grade compliance — the IG covers that. He asks: *is this a product, or a one-off prototype that dies on Monday?* He compresses on commercial logic and technical novelty.

### What he will probe

1. "What's the wedge vs. a generic GenAI document tool?"
2. "Where's the moat — data, distribution, or workflow lock-in?"
3. "How does this scale beyond CRPF — BSF, ITBP, state police, PSU procurement, GeM itself?"
4. "Unit economics — what does one tender cost end-to-end on this stack?"
5. "What's genuinely novel vs. a thin LLM wrapper around a PDF parser?"
6. "How do you avoid pilot purgatory — what's the path from demo to a Rate Contract?"
7. "Who owns the data, the fine-tunes, the audit chain? Where's the IP?"
8. "If a competitor copies the front page tomorrow, what part is hard to replicate?"

### How to win him

| What he wants | What we shipped |
|---|---|
| Defensible technical moat | **Defence Vault** (officer-isolated tenant + key management) and **byte-identical reproducibility** — not weekend features |
| Verifiable trust layer (the actual product) | **Append-only audit chain + Confidence Veil + dual-branch extraction** — a generic GenAI tool will hallucinate and lose |
| Workflow lock-in | **Real second-officer concurrence inbox** mirrors the actual file-noting flow; ripping it out breaks the noting habit |
| Compliance as a feature | **Real CVC / GeM debarment registry** integration is a concrete API a competitor must recreate |
| Scale story | Same architecture works for any CAPF, any GFR-bound buyer; CRPF is the beachhead |
| Product maturity signal | **Pre-Mortem Brief** is unusual for a hackathon prototype |

Pitch line: *"The defensible product isn't the AI — it's the chain of evidence the AI produces. That chain survives audit, court, and the next vendor."*

---

## Cross-cutting takeaway

All three converge from different angles on one demand: **the verdict must be auditable, reproducible, and survivable.** The IG wants survivability in court, the AC on a Tuesday, the founder against a competitor. Every winning feature above is the same evidence chain framed for a different reader.

### Sources

- New Indian Express, 13 Jun 2024 — Karnataka cadre IPS at Centre, lists Vipul Kumar (1999 batch) as IGP rank: https://www.newindianexpress.com/states/karnataka/2024/Jun/13/number-of-ips-officers-of-karnataka-cadre-in-centre-more-than-before
- CRPF KK-Sector page — confirms "Dr. Vipul Kumar IPS, IG KKS": https://crpf.gov.in/Dte/Zone/Southern-Zone/KK-Sector
- The Hindu, 18 Apr 2018 — Mangaluru Police Commissioner posting: https://www.thehindu.com/news/cities/Mangalore/vipul-kumar-takes-charge-as-police-commissioner/article23591030.ece
- Times of India, 19 Apr 2018 — career background: https://timesofindia.indiatimes.com/city/mangaluru/new-city-police-chief-is-no-stranger-to-poll-exigencies/articleshow/63838776.cms
- CRPF Academy, "Making of an Officer": https://crpf.gov.in/Training/CRPF-Academy/Making-of-an-officer
- PDG Partners firm site: https://pdginvestments.com/
- GFR/CVC AI procurement (background, not authored by jurors): https://jhana.ai/blog/procurement-guidance/

Sources paraphrased for licensing compliance.
