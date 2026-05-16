# VerdictAI v2 — Adversarial Design Review

**Reviewer:** Senior backend architect, adversarial mode
**Files reviewed:** `PRODUCT_VISION_V2.md`, `.kiro/specs/verdict-ai-v2/backend-design.md`, `backend/database/schema.py`, `backend/main.py`, `backend/services/bedrock_client.py`
**Time budget under review:** ~24 hours to demo

---

## 1. Overall verdict

The design is ambitious and the narrative ("protect the officer, not evaluate the tender") is genuinely strong. But the design document is a *vision*, not an *architecture* — it lists 17 tables and ~50 endpoints with state machines, hash chains, dual-branch LLM calls, dissent agents, smell tests, two-officer locks, vernacular translation, and "byte-identical reproducibility" all in the same breath. None of those features have enforceable invariants in the schema; the reproducibility story has a silent break in three places (model params, prompt template version, OCR version); the streaming chat endpoint has not been validated against FastAPI + boto3 in this codebase; and the cache layer that makes the cost story work is *not actually implemented* in `bedrock_client.py`. With 24 hours, building all 12 concepts is not realistic. Pick the three that carry the pitch — Confidence Veil, Smell Test, and Source-Click → Replay — and treat the rest as set dressing.

---

## 2. Critical issues (must fix before building)

1. **The Bedrock cache is not implemented.** `backend/services/bedrock_client.py` has no `cache_lookup` parameter and no read path against `llm_invocations`/`llm_stub_log`. The design (§"Reproducibility Architecture") and the comment block in `invoke()` both *describe* a cache; the code does not have one. Without it: every reproduce call costs money, every demo run is non-deterministic, and the "byte-identical replay" claim is a lie. Ship a `cached_invocation.py` wrapper before anything else.

2. **Prompt hash is incomplete → silent reproducibility break.** `_compute_prompt_hash()` (`bedrock_client.py:64–71`) hashes only `system + messages`. It does **not** hash `model_id`, `max_tokens`, `temperature`, the JSON instruction suffix added by `bedrock_structured` (`bedrock_client.py:135–141`), or the prompt template version. Change `BEDROCK_TEMPERATURE` env var → cache hits the old response, producing a *different* answer than the next live run. This is exactly the failure mode reproducibility is supposed to prevent.

3. **`temperature=0.1` is not deterministic.** `bedrock_client.py:32`. Two live calls with the same prompt produce slightly different responses. Reproducibility relies *entirely* on the cache being hit. Combined with #1, the system is non-reproducible by default. Set `temperature=0` and document that reproducibility is "cache-or-equivalent", not "deterministic-on-Bedrock."

4. **Schema in `backend/database/schema.py` does not match the v2 design.** Existing tables use `status`, `evaluation_method`, `officer_decision_timestamp`; v2 design uses `state`, `route`, `decided_at`. There is no migration plan in the design doc. If the team starts coding to the v2 design without dropping/migrating the old DB, every API handler will break against the running schema.

5. **Append-only audit triggers create a hash-chain race.** `audit_events` (`schema.py:170` and v2 design table 11) chains `prev_hash → entry_hash` per row. With WAL mode and `check_same_thread=False` (`connection.py:21`), two concurrent inserts can both read the same `prev_hash` from the previous row and produce a fork. The triggers prevent UPDATE/DELETE, but they do not serialize INSERT. You need either `BEGIN IMMEDIATE` around (read tail, compute hash, insert) or a global mutex.

6. **Auth is "hardcoded officer ID" — concept #7 (Two-Officer Lock) is unbuildable.** A demo with one identity cannot enforce "two different officer logins." `evaluations.requires_second_officer` and `second_officer_id` become theater. Either ship a 30-line officer picker (a header you can change in the UI) or drop concept #7 from the demo claims.

7. **CORS config is too permissive and accepts credentials.** `main.py:62–73`: `allow_origin_regex=r"https://.*\.vercel\.app"` + `allow_credentials=True`. Anyone deploying a preview to `*.vercel.app` can hit the production API with cookies/Authorization headers. For a govt-procurement-themed pitch, judges may notice. Tighten to a known set, or set `allow_credentials=False` while you are still on hardcoded auth.

8. **`POST /api/v1/translate` is unscoped and uncached.** Backend-design API section, Translation. No `tender_id`, no auth, no rate limit. A loop on the frontend could rack up Bedrock cost in minutes. Add a per-clause cache keyed by `(text_hash, target_lang)`.

9. **No idempotency on long-running POSTs.** `POST /tenders/:id/process`, `/extract-criteria`, `/extract-checklist`, `/evaluate`, `/anomalies/run` — none specify what happens on double-click. Either return 409 if already running, or accept an `Idempotency-Key` header. Right now the design implies "fire and forget", which means a refresh during processing fires a second pipeline.

10. **SSE streaming chat has not been proven against FastAPI + sync boto3.** `bedrock_client.py` has no streaming method at all. Design §"Concerns / open questions" admits this is open. `invoke_model_with_response_stream` returns a synchronous iterator over `EventStream`; wrapping that in FastAPI's `StreamingResponse` requires running it in `anyio.to_thread.run_sync` per chunk, otherwise it blocks the event loop and breaks every other request during a chat. Build and time-box this *first*, before promising it in the demo.

---

## 3. Schema-specific issues

### Forward-reference and FK gaps (v2 design SQL)

| Issue | Location | Impact |
|---|---|---|
| `documents.bidder_id REFERENCES bidders(id)` declared before `bidders` table | v2 design table 2 | Cosmetic in SQLite (FKs validated at runtime), but trips schema-comparison tools. |
| `audit_events.tender_id` no FK | v2 design table 11 | Audit can reference deleted/non-existent tenders. |
| `checklist_responses.tender_id`, `anomaly_flags.tender_id`, `decision_replays.officer_id`, `tender_chats.officer_id`, `precedents.officer_id`, `officer_endorsements.officer_ids[]` — none have FKs | v2 design tables 8, 14, 12, 16, 13, 15 | Orphan rows are silent. |
| `tenders.created_by` is a free-text officer ID with no `officers` table at all | v2 design table 1 | "Two-Officer Lock," "Officer Endorsement Trail," and the Decision Memory Vault all assume a stable officer identity that doesn't exist. |
| No `ON DELETE` clauses anywhere | All tables | API claims "soft-delete" for tenders/documents but there is no `deleted_at` column, no view filter, nothing. Hard delete will violate FKs; soft delete is unimplemented. |

### State columns are not enforced

`tenders.state`, `bidders.state`, `bidders.debarment_state`, `criteria.state`, `documents.processing_state`, `evaluations.state`, `checklist_responses.state`, `anomaly_flags.state` — all `TEXT NOT NULL` with **no `CHECK` constraints**. The state machines in the design (lines under "State Machines") are documentation, not invariants. Anyone with a typo can write `state = 'pendng_reviw'` and break every downstream filter. Add `CHECK(state IN (...))` per column.

The evaluation state machine is also internally inconsistent: the diagram shows `pending_second_officer` as a state, but the column comment lists `pending_review | auto_committed | resolved` only.

### JSON columns with no validation

The schema relies heavily on stringly-typed JSON: `metadata`, `confidence_breakdown`, `extracted_value`, `rules_branch`, `llm_branch`, `dissent_branch`, `explanation`, `anomalies`, `threshold_value`, `amendment_history`, `acceptable_evidence`, `source_bbox`, `evidence_data`, `event_data`, `snapshot`, `citations`. SQLite has `json_valid()` but the design doesn't use it.

Bare minimum: add `CHECK(json_valid(column))` on every JSON column. You will catch 80% of bugs in the first hour of integration testing.

For typed contracts (e.g., `confidence_breakdown` is the Mosaic), define a Pydantic model in `backend/schemas/` and validate at the service layer before write. Otherwise the Mosaic UI breaks the first time a key is missing.

### Append-only triggers vs ORM tools

The triggers `audit_no_update` and `audit_no_delete` are global. Consequences:

- SQLAlchemy ORM `session.merge()` issues UPDATE on identity-mapped rows; will fail.
- Alembic migrations that try to `ALTER TABLE audit_events RENAME COLUMN ...` may issue DELETE+INSERT on SQLite (table rebuild). Will fail.
- Any future fix-up migration (e.g., re-hash after a chain repair) is impossible without dropping the trigger.

Document a "break-glass" runbook: drop trigger → migrate → restore trigger, signed off by a named role. Right now the trigger is silently brittle.

### `word_objects` is going to be slow

A 100-page bidder PDF with ~500 words/page = 50,000 rows; 10 bidders = 500,000 rows; 50 tenders = 25M rows. Single index on `page_id`. Source-highlighting queries that look up "the word at this bbox" do a page-scan. Add a compound index on `(page_id, x_min, y_min)` or store a per-page R-tree. For the demo this won't bite, but call it out.

### `precedents.embedding BLOB` has no vector index

SQLite cannot do efficient nearest-neighbor without `sqlite-vss` or `sqlite-vec`. Doing it in Python = full scan per query. For the finale, this is fine (precedents table is empty or seeded with <100 rows), but the Precedent Constellation feature (concept #5) will not scale and the design doc should say so explicitly.

### `evaluations.llm_prompt_hash` is singular but L4 makes ≥3 calls

L3 evidence extract + L4 verdict + L6 dissent are three separate Bedrock calls. The schema has one `llm_prompt_hash` column. Which one? You need either a per-branch hash (`extraction_prompt_hash`, `verdict_prompt_hash`, `dissent_prompt_hash`) or a 1:N table `evaluation_invocations(evaluation_id, role, llm_invocation_id)`. The latter is cleaner and makes the audit trail accurate.

### `pipeline_version` is too coarse

One column on `evaluations` covers OCR version + criterion-extraction prompt + verdict prompt + dissent prompt + smell-test rules. If you bump the dissent prompt, every evaluation appears as "v2.0.0" but is no longer reproducible. Split into `ocr_version`, `extraction_prompt_version`, `verdict_prompt_version`, `dissent_prompt_version`, or compute a composite hash from the loaded `prompts.py` and store *that*.

### Soft delete is undefined

API has `DELETE /tenders/:id` (soft) and `DELETE /documents/:id` (soft) but neither table has a `deleted_at TIMESTAMP NULL` column or an active-only view. Either model it or change the verb.

### `officer_endorsements` is a denormalization smell

A `TEXT JSON array of officer_ids` keyed by `criterion_text_hash`. This is a cache; recompute from `precedents` on demand. Maintaining cache consistency manually will eat hours and one bug will silently mis-attribute decisions. Drop the table and compute live for the demo.

---

## 4. API-specific issues

### REST consistency

- `POST /tenders/:id/bidders` (nested) but `PATCH /bidders/:id` (flat). Pick one. Convention: nested for create/list under parent, flat for read/update of a specific resource — the design *does* this but should make it explicit.
- `POST /api/v1/evaluations/:id/decide` vs `POST /api/v1/checklist-responses/:id/decide` vs `POST /api/v1/anomalies/:id/dismiss` — three verbs for three "I made a decision" actions. Either use `PATCH /evaluations/:id { state, decision }` consistently, or accept the verb-suffix style and document it.
- `POST /tenders/:id/transition` has no body schema described. What states are valid targets? What if the transition is illegal?

### Missing endpoints

- No `GET /api/v1/officers` or `GET /api/v1/me`. Frontend has no way to list possible officers for the two-officer mock.
- No `GET /api/v1/evaluations/:id/dissent` (POST is defined, but there's no idempotent read for re-displaying it).
- No `GET /api/v1/llm-invocations/:id` for the audit drilldown ("show me the exact prompt that produced this verdict").
- No bulk endpoint for the matrix view; `GET /tenders/:id/matrix` is the only one but its response shape isn't defined. With 10 bidders × 30 criteria = 300 evaluation cells, returning all of them inline plus their explanations is a 1–2 MB JSON. Define a slim shape and a separate "expand evaluation" call.
- No `POST /api/v1/tenders/:id/cancel` for an in-flight pipeline. A stuck OCR job is unkillable.

### Pagination, idempotency, rate limits

- No pagination contract. The design says `GET /tenders/:id/audit` is "paginated" but doesn't specify cursor vs offset, page size, or response envelope.
- No `Idempotency-Key` header (see critical #9).
- No rate limit shape. `POST /translate` and `POST /chat` are LLM-cost endpoints; without per-officer or per-tender limits, a misbehaving frontend can burn the demo budget.

### Error contract is shallow

`main.py:79–98` has handlers for `ValueError` (422) and `Exception` (500) only. There is no contract for:
- 404 (tender not found)
- 409 (state machine violation, double-process)
- 422 with field-level errors (FastAPI's default validation already produces these — make sure your handler doesn't override them)
- 503 (Bedrock unavailable / throttled)

Right now any state-violation, FK-violation, or Bedrock failure becomes a 500 with `"An unexpected error occurred"`. The officer cannot be told *why* a decision can't be saved.

### SSE specifics

- `POST /tenders/:id/chat` returning SSE: browsers' `EventSource` only supports GET. Either switch to GET with the message in a query param (ugly, length-limited) or `fetch` with a `ReadableStream` reader (works but no auto-reconnect). Document which.
- `GET /tenders/:id/process/status` SSE: how is "done" signaled? `event: done` then close? What happens on disconnect? The design is silent.
- SSE behind Vercel/ngrok/cloudfront: buffering can hold events for 30s. Test in the actual deploy target before the demo.

### Auth attacks enabled by hardcoded officer ID

With `officer_id` as a free string in request bodies (or a header):

1. **Identity spoofing**: any client can claim any officer. The `decision_replays.officer_id` is a self-attestation — useless in court.
2. **Audit forgery**: `audit_events.actor` is whatever the request says. The hash chain proves *order*, not *who*.
3. **Two-Officer Lock bypass**: the same browser can `POST /evaluations/:id/decide` as Officer A, then as Officer B, and it will be accepted.
4. **Tender access**: no `created_by` filter on `GET /tenders` means every officer sees every tender. If the demo is multi-tenant in any sense, this leaks.
5. **CSRF**: with `allow_credentials=True` and the lax CORS (see critical #7), any malicious site the officer visits can issue authenticated state-changing POSTs.

Mitigation for the demo: keep auth hardcoded but prefix every state-changing action with a server-side `X-Officer-Id` header *that is not user-controlled* (set by a thin middleware that reads from a server-side dropdown selection). Better: a 30-line login page with a list of seeded officers and a session cookie.

### `GET /documents/:id/serve`

Says "auth-gated" in the design. With hardcoded auth, "auth-gated" is misleading; document as "exposed to anyone who knows the document ID." UUIDs are guessable in bulk if you don't rate-limit.

### `PATCH /tenders/:id`

No `If-Match` / ETag. Two officers editing tender metadata at the same time → last write wins, silently. Add `updated_at` as an optimistic-lock token.

---

## 5. Bedrock-specific issues

### Failure modes not handled

`bedrock_chat` (`bedrock_client.py:74–124`) catches `Exception` and returns a `BedrockResponse` with `error=str(exc)`. That's the only failure path.

| Failure | Current behavior | What's needed |
|---|---|---|
| `ThrottlingException` | Generic error string | Exponential retry with jitter, surface as 503 |
| `ModelTimeoutException` | Generic error string | Retry once; otherwise 504 |
| Empty `content` array (model refused) | Returns `text=""`, no error | Treat as error explicitly |
| Malformed JSON in `bedrock_structured` | Returns `data=None, error=...` | OK, but caller code likely doesn't check `error` before reading `data` |
| `"```json\n...\n```"` wrapped output | Stripped (line 142–148) | Works, but only if fence is on its own line; ` ```json{...}``` ` inline breaks it |
| Response is a JSON array `[...]` | `find('{') ... rfind('}')` misses it | `bedrock_structured` is documented as returning `dict | list` but the recovery path only finds objects |
| Connection drop mid-stream | (no streaming code yet) | Define partial-response policy: discard and retry, or persist as `error="partial"` |
| ADA/STS credential expiry mid-demo | Generic 500 | Detect `ExpiredTokenException` and show a banner |

Add a `botocore.config.Config(retries={"max_attempts": 3, "mode": "adaptive"})` to the client. Don't let demo throttling kill you.

### Prompt-hash fragility

Beyond the missing fields (critical #2), these silently change the hash:

- Trailing whitespace in OCR'd text (`\r\n` vs `\n`, BOMs, zero-width spaces).
- Float formatting in prompts (`f"{value}"` is locale-independent in Python, but `f"{value:.2f}"` is not under non-C locales — make sure you're never depending on locale).
- Any `datetime.now()` or `time.time()` interpolated into the prompt (e.g., "Today is 2025-01-15"). Audit `prompts.py` for this — it's the easiest way to silently break replay.
- Dictionary ordering: `json.dumps(..., sort_keys=True)` is good, but if the prompt itself contains a Python dict serialized without `sort_keys`, hash drifts.

Add a unit test: build the prompt twice with the same inputs, assert hash equality. Add another: build with whitespace-perturbed input, assert *what should happen* (currently: hash changes; you may want to canonicalize OCR output before hashing).

### Prompt-hash collision across tenders

`prompt_hash` is keyed only on `system + messages`. If two tenders share an identical clause text passed to `extract_criterion`, they share the same hash and the same cached response — which is *correct* (it's the same prompt). The risk is the *opposite*: an officer running the same NIT in two tenders sees identical AI output, which the audit trail truthfully records, but the officer perceives as a bug ("why is the AI saying the same thing?"). Document this; it's a feature, not a bug.

A real collision (different prompt → same hash) is `~2^-256`. Don't waste time on it.

### Cost: how many calls per tender?

Rough back-of-envelope from the design's pipeline (L1–L7) and the API:

| Stage | Calls | Where |
|---|---|---|
| L2 criterion extraction | 1 per NIT chunk (~3–5 for a 50-page NIT) | `/extract-criteria` |
| L2 checklist extraction | 1–2 | `/extract-checklist` |
| L3 evidence extraction | 1 per (bidder × criterion) | `/evaluate` |
| L4 verdict (qualitative) | 1 per (bidder × criterion) for non-deterministic types | `/evaluate` |
| L6 dissent | 1 per evaluation | `/evaluate` |
| L7 post-checks | 1 per evaluation (LLM-driven flavor) | `/evaluate` |
| L5 anomaly smell (LLM-driven) | 1 per bidder | `/anomalies/run` |
| Chat | n per officer query | `/chat` |
| Translate | n per clause toggled | `/translate` |

For a demo with 5 bidders × 15 criteria = 75 evaluations:
- L3+L4+L6+L7 ≈ 4 × 75 = 300 calls
- L2 ≈ 5 calls
- L5 ≈ 5 calls
- Chat/translate during demo ≈ 10–30

≈ **350 Bedrock calls per demo run**. At ~3000 input tokens + 500 output tokens average for Claude 3.5 Sonnet (`$3/MTok in, $15/MTok out`), that's ≈ `$3.15 + $2.63 ≈ $6` per cold run, plus chat. Three rehearsal runs without cache = ~$20.

This is fine for the finale, **but only if the cache works**. Without it (critical #1), every reload during rehearsal repeats the full bill.

### Streaming + reproducibility don't compose

If chat streams tokens to the UI and you also want the response in `llm_invocations.response_content`, you must accumulate the full text on the server before writing the row. If the connection drops at token N, you must decide: write the partial, or write nothing. Design says nothing. Recommendation: persist the full concatenated stream at end-of-stream only, and on disconnect persist with `error="client_disconnected"` and the partial text — this keeps the audit honest.

### `is_bedrock_configured()` calls STS on every check

`bedrock_client.py:178`: `sts.get_caller_identity()` is a network round-trip. If used in a request hot path (e.g., a healthcheck on every API call), it's a latency floor. Cache the result for the process lifetime.

### `MAX_TOKENS = 4096` may truncate

`bedrock_client.py:31`. NITs are often 50–100 pages. If `extract-criteria` puts the full text in the user message and asks for an array of criteria back, output may exceed 4096 tokens and silently truncate to malformed JSON. Bump to 8192 for extraction calls, or chunk the NIT.

### Region

Hardcoded `us-east-1`. For a procurement-themed demo to government judges, mention data residency. Out of scope to fix in 24h, but acknowledge.

---

## 6. Concept feasibility table (12 concepts × buildable / impact / effort)

| # | Concept | Buildable as written (24h)? | What's missing | Impact | Effort | Score (impact/effort) |
|---|---|---|---|---|---|---|
| 1 | Decision Memory Vault | Partially | DOM snapshot is heavy; capture *backend state* + page image URLs only | High (defensibility narrative) | M | High |
| 2 | Confidence Veil | **Yes** | Just routing thresholds + UI labels | High (differentiator) | S | **Highest** |
| 3 | Dissent Mode | Yes (cost) | Doubles evaluation Bedrock calls; cache aggressively | High (visible wow) | M | High |
| 4 | Question I Should Have Asked | Yes | Pre-canned per `criterion_type`; LLM-generated is a stretch | M | S | High |
| 5 | Precedent Constellation | Partially | Cold-start: empty `precedents` table = "0 similar cases"; seed it | M | M | M |
| 6 | Quiet/Loud Mode | Yes | Frontend toggle + a few backend flags | Low (no demo wow) | S | Low |
| 7 | Two-Officer Lock | **No** (auth gap) | Real officer identities; ship a stub picker if you want to show it | M (theatre) | S | Low without auth |
| 8 | Smell Test | **Yes** | Rule-based heuristics; LLM optional | High (visible chips, novel) | S | **High** |
| 9 | Time Capsule Replay | Partially | "Replay" = render stored snapshot, not a live re-execution | High (closing wow) | M | High |
| 10 | Vernacular Mode | Yes | Per-clause translate + cache | M | S | M |
| 11 | Evidence Confidence Mosaic | Yes | `confidence_breakdown` JSON exists; just compute and render | M | S | High |
| 12 | Officer Endorsement Trail | Partially | Cold-start; without history, shows "0 endorsements" — embarrassing | Low | M | Low |

**Top 3 highest impact-per-effort:**

1. **Confidence Veil (#2)** — pure framing change. Half a day. Carries the entire pitch line.
2. **Smell Test (#8)** — rule-based for known patterns (round numbers, address collisions, PAN/GSTIN format, date proximity), LLM only on novel cases. One day. Highly visible.
3. **Source-Click → Time Capsule Replay (#1 + #9 + Wow #1)** — these are the same engine: capture deterministic state at decision time, render it on replay. One and a half days. This is the defensibility narrative.

**Three to cut (over-engineered for the time):**

1. **Quiet/Loud Mode (#6)** — pure UX with no demo wow. Skip.
2. **Officer Endorsement Trail (#12)** — cold-start kills it; "endorsed by 0 officers" is worse than not showing it.
3. **Two-Officer Lock (#7)** — unenforceable without real auth. Skip in the demo claims; mention in "production roadmap" slide.

---

## 7. Recommended cut list for the next 24 hours

| Cut | Why | What replaces it |
|---|---|---|
| Quiet/Loud Mode | UX nicety, no wow | Default to "Loud" — proactive AI |
| Officer Endorsement Trail | Cold-start | Roll into Precedent Constellation |
| Two-Officer Lock | Unenforceable | Show on a "production" slide |
| Vernacular Mode (live) | Adds Bedrock latency in demo | Pre-translate one demo clause; show as a static toggle |
| Multi-officer auth | Out of scope | Officer picker in the header (3 seeded officers in a dropdown) |
| `precedents.embedding` semantic search | sqlite-vss not in stack | Use FTS5 (already in `schema.py:194`) — keyword match is fine for demo |
| `POST /tenders/:id/transition` body validation | Time sink | State changes happen as side effects of the actual action endpoints; no explicit transition endpoint |
| `officer_endorsements` table | Cache without a source | Drop; compute live from `precedents` |
| L7 LLM-driven post-checks | Yet another Bedrock call | Pre-canned questions keyed off `criterion_type` |
| Streaming SSE for `/process/status` and `/evaluate/status` | Buffering surprises in deploy | Polling endpoint at 1s; chat keeps SSE |
| `decision_replays.snapshot` as full DOM | Heavy + non-deterministic | Snapshot = `{evaluation_id, page_image_url, bbox, ai_response_id, criterion_text}` |

---

## 8. Recommended additions

These are missing from the design and should be in before coding starts.

### Schema

1. `CHECK(state IN (...))` constraints on every `state` column.
2. `CHECK(json_valid(col))` on every JSON column.
3. `deleted_at TIMESTAMP NULL` on `tenders`, `documents`, `bidders` if soft-delete is real.
4. `officers(id, name, department, role, created_at)` table — even with two seeded rows, it makes the rest of the schema honest.
5. Per-branch hash columns on `evaluations`: `extraction_prompt_hash`, `verdict_prompt_hash`, `dissent_prompt_hash`, OR a 1:N `evaluation_invocations` join table.
6. `ocr_version`, `extraction_prompt_version`, `verdict_prompt_version`, `dissent_prompt_version` (or one composite `pipeline_signature_hash`).
7. Compound index `(page_id, x_min, y_min)` on `word_objects` for source-click lookup.

### Bedrock client

1. `cache_lookup` actually implemented against `llm_invocations`.
2. `temperature=0` for any cached path.
3. Hash function includes `model_id`, `max_tokens`, `temperature`, prompt template version.
4. `botocore.Config(retries={"max_attempts": 3, "mode": "adaptive"})`.
5. Streaming wrapper: `bedrock_stream(...)` that yields chunks AND accumulates the full text for post-write to `llm_invocations`.
6. `bedrock_structured` recovery handles top-level arrays.
7. Unit test: hash stability under whitespace perturbation; hash *changes* when model_id changes.

### API

1. `Idempotency-Key` header support on all long-running POSTs.
2. Pagination contract: `?cursor=…&limit=…`, response envelope `{items, next_cursor}`.
3. `If-Match`/`ETag` on `PATCH` endpoints that mutate metadata.
4. Per-tender Bedrock call budget (e.g., 500 calls) with a 429 when exceeded — protects the demo wallet.
5. Granular error codes: `STATE_VIOLATION`, `LLM_THROTTLED`, `LLM_PARTIAL`, `OCR_FAILED`, `NOT_FOUND`.
6. `GET /api/v1/me` returning the currently selected officer.
7. `GET /api/v1/llm-invocations/:id` for audit drilldown.
8. `POST /api/v1/tenders/:id/cancel` to kill a stuck pipeline.

### Demo-day risks (and what to pre-build)

1. **Bedrock throttling mid-demo.** Pre-warm the cache: run the full demo flow once, save `llm_invocations` rows; demo reads from cache. Live calls only for the chat wow moment.
2. **AWS credentials expire.** ADA tokens are ~12h. Refresh at the start of the day; have a backup laptop with refreshed creds.
3. **Network from venue.** Bedrock is `us-east-1` ~250ms RTT from India. Streaming will *feel* slow. Pre-cache; live only for chat.
4. **SSE through Vercel/proxies.** Test in the actual deploy. If it buffers, fall back to polling.
5. **SQLite WAL contention** when seeding + serving simultaneously. Seed before the demo and put the file in read-mostly mode during.
6. **The reproduce-replay animation.** This is the closing wow. If it's flaky, the pitch dies. Build it on cached responses *only*, animate from local data, no live Bedrock.
7. **Source-click highlight misalignment.** OCR bboxes vs PDF render coordinates often differ by a few pixels per DPI. Test on the *exact* PDFs you'll demo with.
8. **State machine deadlock.** A tender stuck in `EVALUATING` because one Bedrock call failed silently. Add a "force unstuck" admin endpoint behind a flag.

### Smallest viable subset that still wins

If everything else slips, ship this and you still win on narrative:

1. Tender create → upload NIT + 2 bidder PDFs → OCR.
2. Criteria extraction (cached Bedrock) → Confidence Veil display ("I'm 91% confident this passes").
3. Per-bidder evaluation → Evidence Confidence Mosaic + Source-Click to PDF.
4. Smell Test chips on the matrix.
5. Officer "Confirm" on three evaluations → audit hash chain visible.
6. **Reproduce Replay** of one evaluation (closing wow) — animate from cached `llm_invocations`.

That's six features. Concepts #2, #8, #11, #1+#9, plus the source-click. It carries the pitch:

> *"Every other team built AI that evaluates tenders. We built a system that protects the officer who has to defend the decision in front of CVC three years later."*

Everything else is bonus.

---

## TL;DR for the team

- **Critical #1: build the cache before anything else, or the cost story collapses.**
- Tighten the prompt hash, set `temperature=0`, version the prompt templates.
- Drop the auth pretense or build a 30-line officer picker — concept #7 is unenforceable as written.
- Add CHECK constraints and `json_valid()` — your state machines and JSON contracts are documentation, not invariants.
- Resolve the schema drift between `backend/database/schema.py` (current) and the v2 design before any handler is written.
- Test SSE through your actual deploy target *today*, not at 2 AM tomorrow.
- Pre-warm the Bedrock cache; live calls only for the chat wow.
- Cut #6, #7, #12 from the demo claims. Lean into #2, #8, #1+#9.
