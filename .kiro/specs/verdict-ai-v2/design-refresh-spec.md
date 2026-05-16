# VerdictAI — Design Refresh Spec (v2)

> Internal design brief for a single, opinionated UI refresh.
> Audience: 1999-batch IPS senior juror. Vibe target: **State Bank of warmth**, not "birthday party". Translate the *elegance and breath* of the reference image, not the playfulness.

---

## 1. Design philosophy

VerdictAI is a sovereign, evidence-grade workspace for officers who decide who gets a public-procurement contract. The new look reads **premium, warm, and alive** — a quiet government chamber lit by late-afternoon sun, not a courtroom under fluorescent tubes. We keep the audit-blue brand at the centre of trust (every signature, every primary action), and we add a *single warm signature note* — a hand-mixed peach-cream — that appears only in human moments: the page hero, an empty case-file, a soft decorative blur in a corner, the pill that recognises a citation. Surfaces stop being clinical white and pick up an almost-imperceptible warm-cream paper tone, so the eye relaxes. Type is split: a confident serif (Fraunces, italic, optical-size aware) carries page titles and the wordmark; a tight sans (Inter Tight) handles UI. The result is the difference between a *lobby* and a *waiting room* — same building, same authority, but you can feel the architect cared.

---

## 2. Tokens

All values are CSS custom properties on `:root`. Existing names are preserved; new names extend the system.

### 2.1 Surfaces — warm-paper, not blue-paper

The page no longer carries a 3% blue tint. It carries a **2% warm-cream tint** so the eye reads "vellum" instead of "spreadsheet". Recessed surfaces deepen the warmth slightly so containment is felt without losing brand temperature.

| Token | Value | Role |
|---|---|---|
| `--bg` | `#FBF8F4` | Page background — cream paper |
| `--bg-soft` | `#F5F1EA` | Section backgrounds, hover surfaces |
| `--bg-sunk` | `#EDE7DC` | Sunken surfaces (inputs, code, scroll wells) |
| `--bg-tint` | `#F0EAFE` *(unused — see `--accent-soft` and `--primary-soft`)* | reserved |
| `--paper` | `#FFFFFF` | Card / panel surface — pure white still reads as "document" against cream bg |

### 2.2 Ink — slate with a barely-perceptible warm undertone

We pull ink one notch off pure-slate so it doesn't fight the cream. Still WCAG AAA on `--paper`.

| Token | Value | Role |
|---|---|---|
| `--ink` | `#1B1F2A` | Primary text (slate-900 with +2% warm) |
| `--ink-muted` | `#3A3F4D` | Secondary text |
| `--ink-soft` | `#6A6F7D` | Tertiary, captions |
| `--ink-faint` | `#9A9FAB` | Disabled, placeholders |
| `--ink-on-color` | `#FFFFFF` | Text on dark/coloured fills |

### 2.3 Lines — warm hairlines

Borders are warm-grey, not blue-grey. They stay visible on cream without looking like ruled-paper.

| Token | Value |
|---|---|
| `--line` | `#E4DCCD` |
| `--line-strong` | `#C9BFAB` |

### 2.4 Primary — blue stays. Refined.

Brand blue is the colour of the State, of evidence, of audit. It does not move. We refine the tints so they sit on cream without clashing.

| Token | Value | Role |
|---|---|---|
| `--primary` | `#2563EB` | Brand blue (unchanged) |
| `--primary-hover` | `#1D4ED8` | unchanged |
| `--primary-soft` | `#E1EAFB` | Re-toned (was `#DBEAFE`, now slightly warmer to sit on cream) |
| `--primary-ring` | `color-mix(in oklab, #2563EB 30%, transparent)` | Focus ring |

### 2.5 Accent — NEW: warm signature

A single, hand-mixed terracotta-coral. Used **only** for: hero moments, empty-state illustrations, decorative gradient blobs, source-citation pill highlights, the secondary CTA (e.g. "Open dossier"). **Never** the primary "Decide" / "Sign" / "Mark FAIL" action — those stay blue / red / green by semantic.

| Token | Value | Role |
|---|---|---|
| `--accent` | `#C8553D` | Terracotta-coral. Reads sovereign-warm, never candy. |
| `--accent-hover` | `#A8412C` | Pressed / hover state |
| `--accent-soft` | `#F6E4DC` | Tinted background |
| `--accent-ring` | `color-mix(in oklab, #C8553D 28%, transparent)` |

> Why `#C8553D` and not a pastel peach? Pastel peach reads consumer / wedding-stationery. A muted terracotta reads *Lutyens-era seal-wax* — exactly the vibe a 1999-batch IPS officer registers as "serious".

### 2.6 Status families — re-toned for cream

| Token | Value |
|---|---|
| `--success` | `#0F8A5F` |
| `--success-hover` | `#0B6E4B` |
| `--success-soft` | `#DDF1E6` |
| `--danger` | `#C8362C` |
| `--danger-hover` | `#A52A22` |
| `--danger-soft` | `#F7DDD9` |
| `--warning` | `#B8761F` |
| `--warning-hover` | `#8F5C18` |
| `--warning-soft` | `#F6E7CD` |

(Saturation pulled ~10% so they sit on `--bg` without screaming. Contrast on `--paper` still passes AA at 4.5:1.)

### 2.7 Shadows — temperature-mixed

Existing shadows used pure brand-blue umbra. New shadows blend brand-blue and warm-amber so the lift feels *lived-in*. The eye reads "cream paper resting on a darker cream desk", not "blue card hovering over blue grid".

```css
--shadow-1:
  0 1px 2px rgba(40, 30, 20, 0.04),
  0 0 0 1px rgba(40, 30, 20, 0.04);

--shadow-2:
  0 2px 8px rgba(40, 30, 20, 0.06),
  0 1px 3px rgba(37, 99, 235, 0.05),
  0 0 0 1px rgba(40, 30, 20, 0.05);

--shadow-3:
  0 12px 28px rgba(40, 30, 20, 0.10),
  0 3px 8px rgba(37, 99, 235, 0.06),
  0 0 0 1px rgba(40, 30, 20, 0.05);
```

The first layer is warm umbra (gives the cream-paper feel), the second is brand-blue (keeps the product feeling like *our* product), the third is a hairline ring.

---

## 3. Typography

All Google Fonts. All free for commercial / government use.

| Role | Family | Weight / style | Justification |
|---|---|---|---|
| **Display / page titles** | **Fraunces** | 400 italic, 500 italic, 600 | Variable-axis serif with optical-size and SOFT axes. The italic at display sizes has the calligraphic warmth the reference has, but Fraunces itself was designed for *legal and editorial* use — not weddings. It already sits in the project; we just promote it from "headline only" to "page hero italic". |
| **UI sans (body, controls, tables)** | **Inter Tight** | 400, 500, 600, 700 | Tighter horizontal metrics than Inter; numbers tabular; pairs cleanly with Fraunces. |
| **Mono** | **JetBrains Mono** | 400, 600 | Unchanged. Hashes, citation IDs, audit deltas. |
| **Wordmark** | **Fraunces** 700, optical-size 144, SOFT axis 100, italic | Same family as display, but cranked: max optical size, max softness, italic. Reads as a *masthead*, not a logotype. No second font needed. |

> Joti One is rejected (looks like a 7-year-old's birthday card). Bricolage Grotesque (currently used) is fine but tonally cold for the wordmark. Fraunces at high optical size + soft axis gives the "perfect namings premium feel" — think *Penguin Modern Classics* spine.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link
  href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght,SOFT@0,9..144,400..700,0..100;1,9..144,400..700,0..100&family=Inter+Tight:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap"
  rel="stylesheet"
>
```

---

## 4. Wordmark + footer

### Wordmark
**Pure type, no glyph.** The dot of the `i` is replaced by a 4×4 px terracotta square — the only mark of warmth in the brand lockup.

```
Verdict AI
^^^^^^^^^^
Fraunces 700 italic, opsz 144, SOFT 100, letter-spacing -0.015em.
"Verdict" in --ink. "AI" in --primary, slightly smaller cap-height.
The dot on the 'i' in "Verdict" → 4px terracotta square (--accent).
```

### Footer caption
Replace **"v1.0 · pencil edition"** with:

> **"Sealed by Bedrock · Sovereign-grade evidence engine"**

Set in Inter Tight 500, 11px, `--ink-soft`, letter-spaced 0.06em, with a 4px terracotta square preceding it. The phrase deliberately echoes physical seal-and-wax, the literal Bedrock model name, and the "sovereign" register the juror responds to.

A shorter variant for tight rails:
> **"Sealed by Bedrock"** (drop the subtitle).

---

## 5. Workspace naming

Current: **"Tender Space"** — reads SaaS. Three candidates considered:

| Candidate | Verdict |
|---|---|
| Tender Dossier | Strong. "Dossier" carries case-file gravitas; used in MEA, MoD, intelligence. |
| Tender Casefile | Acceptable but slightly American-procedural ("CSI"). |
| Procurement Atelier | Rejected — reads luxury-fashion. |

**Pick: "Tender Dossier"** (workspace), and "Dossier" alone in the breadcrumb when it's already obvious. Officers already say *"file/dossier"* in vernacular; a 1999-batch IPS officer parses *dossier* in <50 ms because they have literally handled hundreds of them. SaaS-y term retired.

Change in copy:
- "Open Tender Space" → "Open Dossier"
- "New Tender Space" → "New Dossier"
- Sidebar section heading "Spaces" → "Dossiers"

---

## 6. Card design

The card is the single most-repeated surface in the product (tender list, bidder list, criterion list, citations). It must be the place the warmth lives.

```
┌─────────────────────────────────────────────────┐
│ ░░░  ← 1px top-edge: gradient from --accent     │
│       30% → transparent over 40% of width       │
│                                                 │
│   Tender title                       PASS       │
│   Cormorant·like serif italic        pill       │
│                                                 │
│   ₹2.4 Cr · 12 bidders · closed 2 d ago         │
│                                                 │
└─────────────────────────────────────────────────┘
   warm shadow, subtle. lifts on hover.
```

Specifics:
- **Surface**: `--paper` (#FFF) on `--bg` (cream) — the white card visibly stands above the cream bg.
- **Border**: `1px solid var(--line)`.
- **Top-edge accent**: a `::before` pseudo, 1px tall, 40% wide, `linear-gradient(90deg, var(--accent) 0%, transparent 100%)`, opacity 0.6 — the "subtle teal stroke" idea from the reference, but warm.
- **Radius**: `--r-lg` (10px) — slightly softer than current. Not pillowy.
- **Shadow**: `--shadow-1` resting, `--shadow-2` on hover.
- **Hover**: `transform: translateY(-2px)` + shadow lift + the top-edge gradient extends to 70% width (length grows, not opacity — quieter).
- **Status edge**: when the card represents a verdict, the top-edge gradient swaps colour:
  - PASS → `--success`
  - FAIL → `--danger`
  - REVIEW → `--warning`
  - default / informational → `--accent`

This gives the user a peripheral-vision read of the verdict mix without reading any text — the row of cards looks like a row of file-tabs with coloured edges.

---

## 7. Sidebar

The user complained about coloured dots and "triple dots" (offset shadows on the active item). Remove all of it.

```
┌───────────────────────┐
│  Verdict AI▪          │   ← wordmark + 4px accent square
│  ─────────────────    │
│  DOSSIERS             │   ← section, micro-caps
│  │ Active             │   ← active: 3px terracotta bar at left edge,
│  │ ░ light cream tint │     bg = --accent-soft, ink = --ink, weight 600
│    Archived           │
│    Drafts             │
│                       │
│  REFERENCE            │
│    Wiki & Help        │
│    Audit log          │
│    Settings           │
└───────────────────────┘
```

Rules:
- Rest pose: transparent bg, `--ink-muted`, weight 500, no border.
- Hover: bg `--bg-soft`, ink `--ink`. Nothing else. No transform, no shadow.
- Active: 3px solid `--accent` bar on the left edge (inside the rail, not a border that shifts the layout), bg `--accent-soft`, ink `--ink`, weight 600.
- **No** coloured dots, **no** offset shadow, **no** chevrons unless the item is expandable.
- Section headers: 10px uppercase, `--ink-faint`, letter-spacing 0.12em.
- Wordmark area at top has a single 1px hairline divider in `--line` underneath. No dashed border (current code uses dashed; replace).

---

## 8. Hero / dashboard treatment

Current: an `<h1>Tenders</h1>` that does nothing. Replace with a *quietly cinematic* hero that occupies the top ~220px of the dashboard, then drops into the card grid.

```
                                              ░░░░░░░░░░
                                            ░░░ warm   ░░░
                                              ░ blob ░░░░
                                              ░░░░░░░░
   Welcome back, Inspector.
   ─────────────────────
   Five  dossiers   are  waiting  on  your  decision.   ← Fraunces 600 italic
                                                            48px desktop
                                                            color: --ink

   12 dossiers · 3 awaiting concurrence · 1 overdue       ← Inter Tight 14px
                                                            --ink-soft

   [  Open new dossier  ]   [  Review queue  ]              two CTAs
       primary-blue            ghost button
```

Components:
- **Greeting strip** (Inter Tight 13px uppercase, 0.1em tracking, `--ink-soft`): "Welcome back, Inspector."
- **Headline** (Fraunces italic 600, opsz auto, 40–52px responsive): a *sentence*, not a noun. Examples:
  - "Five dossiers are waiting on your decision."
  - "All clear. The queue is empty."
  - "Three concurrences are due today."
- **Sub-line**: tabular numbers in Inter Tight, separated by `·`.
- **Primary CTA** = blue (unchanged: this is the action of the State).
- **Secondary CTA** = ghost.
- **Decorative blob**: a single CSS radial gradient anchored to the top-right corner of the hero container. **No raster image. No body-wide gradient.**

```css
.hero-gradient::before {
  content: '';
  position: absolute;
  top: -120px; right: -120px;
  width: 520px; height: 520px;
  background: radial-gradient(
    closest-side,
    color-mix(in oklab, var(--accent) 22%, transparent) 0%,
    color-mix(in oklab, var(--accent) 8%, transparent) 40%,
    transparent 75%
  );
  filter: blur(8px);
  pointer-events: none;
  z-index: 0;
}
```

The blob is contained in the hero — it never bleeds into the card grid.

### Empty-state copy

Current: "No tenders yet." Replace by intent:

| State | Headline | Subline | CTA |
|---|---|---|---|
| No dossiers | *"The desk is clear."* | "When a tender lands, it will appear here as a dossier." | "Open new dossier" |
| No bidders in dossier | *"No bids on the table yet."* | "Upload bidder submissions to begin evaluation." | "Add bidder" |
| No verdict yet | *"Awaiting your verdict."* | "Three criteria still need a call." | "Review criteria" |
| No corrigenda | *"Nothing has been amended."* | — | — |

Headlines all in Fraunces italic. Sublines in Inter Tight `--ink-soft`. The illustrations slot, if any, is one terracotta circle with a hairline — never an emoji, never a stock illustration.

---

## 9. Tender (Dossier) header

Current: a rainbow stripe gradient at the top. **Killed.** That gradient reads like a children's-product banner.

Replacement:

```
┌──────────────────────────────────────────────────────────┐
│ ░ 1px terracotta hairline, full width, opacity 0.4 ──    │
│                                                          │
│  Crumb › Dossier #CRPF-2024-117                          │
│                                                          │
│  Supply  of  Tactical  Boots  for  CRPF                  │   ← Fraunces italic 600, 28px
│                                                          │
│  ⛪ 2024-08-12 · ₹2.4 Cr · 12 bidders                   │   ← Inter Tight 13px, --ink-soft
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │   ← step indicator (sec 10)
└──────────────────────────────────────────────────────────┘
```

The only "graphic" is the 1px terracotta hairline at the very top — it tells the eye "you are inside a dossier" without any banner real-estate. The serif italic title carries the gravitas. No Indian flag tricolour stripe (was kitsch).

---

## 10. Step indicator

Current pills wrap. New: a **connected horizontal rail with active fill**, inspired by Linear's PR status track.

```
●━━━━━●━━━━━●━━━━━○━━━━━○
Intake  Brief  Evaluate  Verdict  Sign
 done    done   here       —       —
```

Specifics:
- One horizontal flex line, never wraps. On narrow viewports the labels truncate to first 4 characters with a tooltip; the dots remain.
- Connector: 2px line, `--line` between pending, `--accent` between completed/active.
- Dot states:
  - Done: filled `--accent`, white tick inside.
  - Current: filled `--paper` with 2px `--accent` ring, plus a soft 6px `--accent-ring` halo.
  - Pending: filled `--paper` with 2px `--line-strong` ring.
- Click: navigate to that step.
- The label sits *under* the dot, not next to it. Inter Tight 11px uppercase, 0.08em tracking, `--ink-muted` (current) / `--ink-soft` (else).
- Total height fits in 56px including labels. No wrapping, no chrome.

Why terracotta and not blue here? Because the step rail is *narrative* (where am I in this story), not *action*. Blue is reserved for "click this and the State acts".

---

## 11. Buttons

Three variants, premium register, Linear/Stripe-like.

### `.btn-primary` — the State acts (blue)

- Rest: `--primary` fill, `--ink-on-color`, no border, `--shadow-1` (warm).
- Hover: `--primary-hover` fill, `--shadow-2`, `translateY(-1px)`.
- Active: `translateY(0)`, `--shadow-1`, momentary `box-shadow: inset 0 1px 0 rgba(0,0,0,0.1)`.
- Disabled: `--bg-sunk`, `--ink-faint`, no shadow.
- Focus-visible: 3px `--primary-ring` outer ring, no offset.

### `.btn-accent` — warm secondary CTA (terracotta)

- Used on hero, empty-state, marketing surfaces. Never for irreversible actions.
- Rest: `--accent` fill, `--ink-on-color`, `--shadow-1`.
- Hover: `--accent-hover`, `--shadow-2`, lift 1px.
- Active: as primary.

### `.btn-ghost` — neutral, framed

- Rest: transparent, `--ink`, 1px `--line-strong`.
- Hover: `--bg-soft`, `--line-strong` → `--ink-muted`, no transform.
- Active: `--bg-sunk`.

### `.btn-link` — inline

- Rest: transparent, `--primary`, no border.
- Hover: `--primary-soft` background, no underline (premium products underline only on text inside running prose, not on buttons).

All buttons:
- min-height 38px (lg: 46, sm: 30).
- font: Inter Tight 500 / 600 (primary uses 600).
- radius `--r-md` (6px) — *not* fully rounded. Pill buttons read consumer.
- transition: `transform 120ms cubic-bezier(.2,.8,.2,1), box-shadow 150ms, background 150ms`.

---

## 12. Help / Wiki page (`/help`)

A new in-app page rendering the markdown docs the user demanded. Layout:

```
┌─────────┬──────────────────────────────────┬────────────┐
│  RAIL   │ ┌────────────────────────────┐   │   ON-PAGE  │
│         │ │   ⌕  Search the manual     │   │   TOC      │
│  …      │ └────────────────────────────┘   │            │
│         │                                   │  • Intro   │
│         │   The VerdictAI Manual            │  • Dossier │
│         │   ───────────────                 │    lifecyc.│
│         │   Fraunces italic 600 · 36px     │  • Verdicts│
│         │                                   │  • Audit   │
│         │   Long-form markdown content,     │  • FAQ     │
│         │   max-width 720px, line-height    │            │
│         │   1.7, Inter Tight 16px, drop-    │  ─────     │
│         │   caps on first paragraph of      │  Was this  │
│         │   each section.                   │  helpful?  │
│         │                                   │            │
└─────────┴──────────────────────────────────┴────────────┘
```

Components:
1. **Search bar** — sticky at top of the content column. Inter Tight, `cmd-K` shortcut surfaces a global palette. Searches headings + body across all `.md` files. Match highlight uses `--accent-soft` background.
2. **Sticky TOC** — right column, 240px wide, sticks at `top: 80px`. Lists `h2` and `h3` headings of current page. Active heading is detected via `IntersectionObserver`; active style is left 2px terracotta bar + `--ink` text.
3. **Content column** — max-width 720px (60–70 chars/line), centred. Body in Inter Tight 16px / line-height 1.7. `h1` Fraunces italic 600 36px. `h2` Fraunces italic 600 24px with a 1px `--line` underline that runs full column width. `h3` Inter Tight 700 16px uppercase tracking 0.06em.
4. **Drop-cap** on first paragraph of each section: first letter set in Fraunces 600, 64px, `--accent`, `float: left`, line-height 0.95, padding-right 8px. Adds editorial warmth.
5. **Callout blocks** — four flavours rendered from `> [!NOTE]`, `> [!WARNING]`, `> [!TIP]`, `> [!SOVEREIGN]`. Last one is custom: terracotta border-left, `--accent-soft` bg, used to flag CRPF-specific procedure citations.
6. **"Was this helpful?"** widget at end of page; logs to audit table for product analytics. Two buttons: "Yes" (ghost) / "Needs work" (ghost). On "Needs work" → opens a 1-field form.
7. **Breadcrumb** above the title: `Help › Dossier lifecycle`.
8. **Edit-on-Bedrock** small link at the bottom (admin-only) — sends to the markdown source.

Routes:
- `/help` → index page, Fraunces hero ("The VerdictAI Manual"), 6 cards (Quickstart, Dossier lifecycle, Verdicts & evidence, Audit & seal, Officer roles, FAQ).
- `/help/:slug` → markdown render.

---

## 13. Concrete CSS — paste-ready

Drop this **inside** `frontend/src/index.css`, replacing the current `:root` block and the matching component blocks. Every existing class name is preserved; new tokens are additive.

```css
/* ─── Tokens (v2, warm-paper) ─────────────────────────────────────── */

:root {
  /* Warm-paper surfaces. The page now reads "vellum", not "spreadsheet". */
  --bg:        #FBF8F4;            /* cream paper */
  --bg-soft:   #F5F1EA;            /* recessed sections */
  --bg-sunk:   #EDE7DC;            /* inputs, code blocks, scroll wells */
  --bg-tint:   #F0EAFE;            /* reserved */
  --paper:     #FFFFFF;            /* card / panel surface */

  /* Ink — slate with a barely-perceptible warm undertone */
  --ink-base:  #1B1F2A;
  --ink-muted: #3A3F4D;
  --ink-soft:  #6A6F7D;
  --ink-faint: #9A9FAB;
  --ink-on-color: #FFFFFF;

  /* Warm hairlines (replace blue-grey) */
  --line-base:        #E4DCCD;
  --line-strong-base: #C9BFAB;

  /* Continuous contrast amplifier (kept) */
  --contrast-amp: 0;
  --ink:        color-mix(in oklab, var(--ink-base)  calc(100% - 100% * var(--contrast-amp)), #000 calc(100% * var(--contrast-amp)));
  --line:       color-mix(in oklab, var(--line-base) calc(100% - 100% * var(--contrast-amp)), var(--ink-base) calc(100% * var(--contrast-amp)));
  --line-strong:color-mix(in oklab, var(--line-strong-base) calc(100% - 100% * var(--contrast-amp)), #000 calc(100% * var(--contrast-amp)));

  /* Brand blue — unchanged primary, re-toned soft */
  --primary:        #2563EB;
  --primary-hover:  #1D4ED8;
  --primary-soft:   #E1EAFB;
  --primary-ring:   color-mix(in oklab, #2563EB 30%, transparent);

  /* NEW — warm signature accent (terracotta-coral) */
  --accent:         #C8553D;
  --accent-hover:   #A8412C;
  --accent-soft:    #F6E4DC;
  --accent-ring:    color-mix(in oklab, #C8553D 28%, transparent);

  /* Status families — re-saturated for cream */
  --success:        #0F8A5F;
  --success-hover:  #0B6E4B;
  --success-soft:   #DDF1E6;

  --danger:         #C8362C;
  --danger-hover:   #A52A22;
  --danger-soft:    #F7DDD9;

  --warning:        #B8761F;
  --warning-hover:  #8F5C18;
  --warning-soft:   #F6E7CD;

  --neutral:        #4A4F5C;
  --neutral-hover:  #2F3340;
  --neutral-soft:   #EFEAE0;

  /* Shadows — warm umbra + brand-blue undertone */
  --shadow-1:
    0 1px 2px rgba(40, 30, 20, 0.04),
    0 0 0 1px rgba(40, 30, 20, 0.04);
  --shadow-2:
    0 2px 8px rgba(40, 30, 20, 0.06),
    0 1px 3px rgba(37, 99, 235, 0.05),
    0 0 0 1px rgba(40, 30, 20, 0.05);
  --shadow-3:
    0 12px 28px rgba(40, 30, 20, 0.10),
    0 3px 8px rgba(37, 99, 235, 0.06),
    0 0 0 1px rgba(40, 30, 20, 0.05);

  /* Radii */
  --r-sm: 4px;
  --r-md: 6px;
  --r-lg: 10px;
  --r-xl: 14px;

  /* Type — Fraunces (display + wordmark), Inter Tight (sans), JetBrains (mono) */
  --font-wordmark: 'Fraunces', Georgia, serif;
  --font-display:  'Fraunces', Georgia, serif;
  --font-sans:     'Inter Tight', -apple-system, 'Segoe UI', Roboto, sans-serif;
  --font-mono:     'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;

  --fs-xs:   12px;
  --fs-sm:   13px;
  --fs-base: 15px;
  --fs-md:   16px;
  --fs-lg:   18px;
  --fs-xl:   22px;
  --fs-2xl:  28px;
  --fs-3xl:  36px;
  --fs-hero: 48px;

  --line-height: 1.6;
}

html, body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-sans);
  font-feature-settings: 'ss01', 'cv11';   /* Inter Tight: clean digits, single-storey 'a' */
}

/* ─── Wordmark ────────────────────────────────────────────────────── */

.wordmark {
  font-family: var(--font-wordmark);
  font-weight: 700;
  font-style: italic;
  font-size: calc(var(--fs-md) * 1.55);
  font-variation-settings: 'opsz' 144, 'SOFT' 100;
  letter-spacing: -0.015em;
  color: var(--ink);
  white-space: nowrap;
  display: inline-flex;
  align-items: baseline;
  gap: 0.18em;
}
.wordmark::after {
  content: '';
  display: inline-block;
  width: 6px; height: 6px;
  background: var(--accent);
  margin-left: 0.1em;
  align-self: center;
}
.wordmark .ai {
  color: var(--primary);
  font-style: italic;
  font-size: 0.78em;
}

/* ─── Cards (premium, warm-edge) ──────────────────────────────────── */

.card {
  position: relative;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-1);
  transition:
    transform .2s cubic-bezier(.2,.8,.2,1),
    box-shadow .2s ease,
    border-color .2s ease;
  isolation: isolate;
}
.card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  height: 1px;
  width: 40%;
  background: linear-gradient(90deg,
    color-mix(in oklab, var(--accent) 60%, transparent) 0%,
    transparent 100%);
  border-top-left-radius: var(--r-lg);
  transition: width .3s ease;
  z-index: 1;
}
.card:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-2);
  transform: translateY(-2px);
}
.card:hover::before { width: 70%; }

/* Status edge — overrides accent colour */
.card.is-pass::before   { background: linear-gradient(90deg, var(--success) 0%, transparent 100%); }
.card.is-fail::before   { background: linear-gradient(90deg, var(--danger)  0%, transparent 100%); }
.card.is-review::before { background: linear-gradient(90deg, var(--warning) 0%, transparent 100%); }

/* ─── Nav rail items ──────────────────────────────────────────────── */

.nav-item {
  position: relative;
  display: flex; align-items: center; gap: 10px;
  padding: 9px 14px;
  border-radius: var(--r-md);
  font-family: var(--font-sans);
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--ink-muted);
  cursor: pointer;
  transition: background .15s ease, color .15s ease;
  border: 0;
  text-decoration: none;
}
.nav-item:hover {
  background: var(--bg-soft);
  color: var(--ink);
}
.nav-item.is-active {
  background: var(--accent-soft);
  color: var(--ink);
  font-weight: 600;
}
.nav-item.is-active::before {
  content: '';
  position: absolute;
  left: 0; top: 6px; bottom: 6px;
  width: 3px;
  background: var(--accent);
  border-radius: 2px;
}

/* ─── Step rail (connected, no wrap) ──────────────────────────────── */

.step-row {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 8px 0 24px;
}
.step {
  position: relative;
  display: inline-flex; flex-direction: column; align-items: center;
  flex: 1 1 0;
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-soft);
  cursor: pointer;
  background: transparent;
  border: 0;
  padding: 0;
  white-space: nowrap;
}
.step::before {
  content: '';
  width: 14px; height: 14px;
  border-radius: 999px;
  background: var(--paper);
  border: 2px solid var(--line-strong);
  margin-bottom: 8px;
  z-index: 1;
  transition: background .2s, border-color .2s, box-shadow .2s;
}
.step + .step::after {
  content: '';
  position: absolute;
  top: 6px;
  left: -50%;
  width: 100%;
  height: 2px;
  background: var(--line);
  z-index: 0;
}
.step.is-complete::before {
  background: var(--accent);
  border-color: var(--accent);
}
.step.is-complete + .step::after,
.step.is-current  + .step::after {
  background: var(--accent);
}
.step.is-current::before {
  background: var(--paper);
  border-color: var(--accent);
  box-shadow: 0 0 0 6px var(--accent-ring);
}
.step.is-current { color: var(--ink); }
.step:hover::before { border-color: var(--accent); }

/* ─── Buttons ─────────────────────────────────────────────────────── */

.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 9px 16px;
  font-family: var(--font-sans);
  font-size: var(--fs-sm);
  font-weight: 600;
  line-height: 1.2;
  min-height: 38px;
  border-radius: var(--r-md);
  border: 1px solid transparent;
  cursor: pointer;
  user-select: none;
  transition:
    transform .12s cubic-bezier(.2,.8,.2,1),
    box-shadow .15s, background .15s, border-color .15s, color .15s;
  white-space: nowrap;
}
.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-2);
}
.btn:active:not(:disabled) { transform: translateY(0); box-shadow: var(--shadow-1); }
.btn:disabled { opacity: .55; cursor: not-allowed; transform: none; box-shadow: none; }

.btn-primary { background: var(--primary); color: var(--ink-on-color); }
.btn-primary:hover:not(:disabled) { background: var(--primary-hover); }

.btn-accent  { background: var(--accent); color: var(--ink-on-color); }
.btn-accent:hover:not(:disabled)  { background: var(--accent-hover); }

.btn-success { background: var(--success); color: var(--ink-on-color); }
.btn-danger  { background: var(--danger);  color: var(--ink-on-color); }
.btn-warning { background: var(--warning); color: var(--ink-on-color); }

.btn-ghost {
  background: transparent;
  color: var(--ink);
  border-color: var(--line-strong);
}
.btn-ghost:hover:not(:disabled) {
  background: var(--bg-soft);
  border-color: var(--ink-muted);
  transform: none;
  box-shadow: none;
}

.btn-link {
  background: transparent;
  color: var(--primary);
  padding: 4px 6px;
  min-height: 0;
  border: 0;
}
.btn-link:hover:not(:disabled) {
  background: var(--primary-soft);
  transform: none; box-shadow: none;
}

.btn:focus-visible {
  outline: 0;
  box-shadow: 0 0 0 3px var(--primary-ring), var(--shadow-2);
}
.btn-accent:focus-visible {
  box-shadow: 0 0 0 3px var(--accent-ring), var(--shadow-2);
}

/* ─── Hero gradient blob (decorative, contained) ──────────────────── */

.hero {
  position: relative;
  overflow: hidden;
  padding: 32px 32px 24px;
  isolation: isolate;
}
.hero-gradient {
  position: relative;
}
.hero-gradient::before {
  content: '';
  position: absolute;
  top: -140px; right: -140px;
  width: 540px; height: 540px;
  background: radial-gradient(
    closest-side,
    color-mix(in oklab, var(--accent) 22%, transparent) 0%,
    color-mix(in oklab, var(--accent) 8%, transparent)  40%,
    transparent 75%
  );
  filter: blur(8px);
  pointer-events: none;
  z-index: 0;
}
.hero-gradient > * { position: relative; z-index: 1; }

.hero-eyebrow {
  font-family: var(--font-sans);
  font-size: var(--fs-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink-soft);
  margin-bottom: 10px;
}
.hero-title {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 600;
  font-variation-settings: 'opsz' 144, 'SOFT' 50;
  font-size: clamp(28px, 4vw, var(--fs-hero));
  line-height: 1.1;
  letter-spacing: -0.015em;
  color: var(--ink);
  max-width: 22ch;
  margin: 0 0 12px;
}
.hero-sub {
  font-size: var(--fs-md);
  color: var(--ink-soft);
  margin-bottom: 20px;
  font-variant-numeric: tabular-nums;
}

/* ─── Source-citation pill (warm highlight) ───────────────────────── */

.source-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 9px;
  border-radius: var(--r-sm);
  font-family: var(--font-mono);
  font-size: var(--fs-xs);
  color: var(--accent-hover);
  background: var(--accent-soft);
  border: 1px solid color-mix(in oklab, var(--accent) 40%, transparent);
  cursor: pointer;
  transition: transform .12s, background .12s;
  user-select: none;
}
.source-pill:hover {
  background: color-mix(in oklab, var(--accent) 18%, var(--paper));
  transform: translateY(-1px);
}

/* ─── Footer caption ──────────────────────────────────────────────── */

.app-footer-caption {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--ink-soft);
  text-transform: none;
}
.app-footer-caption::before {
  content: '';
  width: 6px; height: 6px;
  background: var(--accent);
  display: inline-block;
}
```

Use the new tokens by extending Tailwind in `tailwind.config.js`:

```js
// extend.colors
accent: 'var(--accent)',
'accent-soft': 'var(--accent-soft)',
'accent-hover': 'var(--accent-hover)',
paper: 'var(--paper)',
```

---

## Migration checklist (out of scope for this spec, listed for the implementing agent)

- [ ] Swap `--bg` family + `--line` family in `:root`. Verify body & topbar still pass contrast.
- [ ] Replace `Bricolage Grotesque` font import with the Fraunces+Inter-Tight `<link>`.
- [ ] Update `.wordmark` (drop italic span hack, use the new structure).
- [ ] Update `.nav-item.is-active` (remove blue tint + border-left-shift; use `::before` bar).
- [ ] Replace step-pill row with connected step rail.
- [ ] Add `.hero-gradient` to the dashboard h1 container.
- [ ] Replace dashboard h1 "Tenders" with the sentence-style hero copy.
- [ ] Rename "Tender Space" → "Dossier" everywhere (search route names, tab labels, copy strings).
- [ ] Add `/help` route + sticky-TOC layout.
- [ ] Replace footer caption "v1.0 · pencil edition" with `<span class="app-footer-caption">Sealed by Bedrock · Sovereign-grade evidence engine</span>`.
- [ ] Kill the rainbow stripe at the top of Tender (now Dossier) header; replace with 1px terracotta hairline.
- [ ] QA in dark / high-contrast mode; verify `--contrast-amp` still amplifies correctly.
