# ROADMAP — DabJob

**Status:** M3 complete (2026-11-27). Data layer, ingest, search, the profile and a working model transport are in place; M4 starts the capture adapters.
**What it is:** the local state layer for a job search — a job-search CRM that an AI agent can operate, not a document generator.
**Scope:** single local user, `localhost`, no auth, no telemetry. zh-CN UI shipped first, i18n-ready from day zero. English repository artifacts.
**Positioning:** open source, multi-platform, interoperable. BOSS直聘 (`zhipin.com`) is the first capture adapter, not the product.
**Supersedes:** `~/Downloads/ai_job-plan.md` (2026-11-01 draft), the single-platform revision of 2026-11-26, and the "workbench" framing of 2026-11-26.

## 0. Positioning

Job search data lives in five disconnected places: the résumé, BOSS/脉脉 listings, chat threads, a spreadsheet of applications, and memory. Nothing is comparable, nothing is searchable, and follow-ups get dropped.

DabJob turns that into one local database plus a web UI. It is the place where the pipeline lives, and it is built so an agent can act on that pipeline on your behalf.

### What this is not

`ai-job-search-dev/ai-job-search` (MIT, ~73k stars as of Nov 2026) turns Claude Code into a document factory: it scrapes portals, ranks postings, writes tailored CVs and cover letters, and preps interviews. It is good at that, and DabJob does not compete with it.

It also deliberately does not hold state. Its tracker is a CSV in git, its dashboard is a regenerated snapshot, and its maintainer declined a local web console as *"a product of its own."*

**DabJob is that product.** It does not write your CV. It holds the pipeline: every posting you considered, every application you sent, every reply, every follow-up you owe — in one queryable database, with a board, a timeline, and reminders.

The two compose. If you already run a document workflow, DabJob imports its state and gives it a board. If you do not, DabJob works on its own with paste and CSV.

**Document generation stays out of scope permanently.** This was decided on 2026-11-27 after considering it: adding it would mean rebuilding a mature competing project, and it would turn a state layer into a document pipeline with no principled stopping point.

### Where AI sits

AI is central to this product but it is not the product. It appears in exactly two directions:

| Direction | Who calls whom | What it does |
|---|---|---|
| **Outbound** | DabJob calls a model or an agent | Reads text that rules cannot parse: a résumé, an unmatched skill term, a posting, a recruiter message |
| **Inbound** | An agent calls DabJob | Operates the CRM through typed tools: query, filter, record an event, propose a status change |

Both directions share one rule: **the agent proposes, the human decides, the database remembers.** AI never becomes the only way to do something, and never becomes the thing that decides a score.

Concretely, that means:

- **No AI is required to run the app.** With nothing configured, every screen works and every score is computed by rules.
- **AI never replaces the rule score.** It annotates and may adjust by at most ±10 points with a written reason.
- **The analytical differentiator is deterministic.** The gap matrix is arithmetic over captured postings, not a model's opinion, because it is the one thing the user is meant to argue with.

### Four claims, each structural rather than promotional

1. **State in a database, not in git.** Your résumé, salary floor and recruiter threads are the most sensitive documents you own. A SQLite file under `DABJOB_DATA_DIR`, excluded from version control, with no account and no telemetry, is a different risk profile from "personal data written into tracked files and warned about in a fork notice."
2. **Queryable.** FTS5 across every JD, dedupe across platforms, per-city salary aggregation, and a follow-up query that answers "what have I left hanging." A spreadsheet and a JSON blob cannot do this; a regenerated report can only re-render what it already knows.
3. **Agent-operable.** A typed tool surface means an agent can answer "which companies asked for Kubernetes and then went quiet?" against real rows, instead of guessing from a prompt. That is a different capability from asking a chatbot to summarize a pasted spreadsheet.
4. **No paid dependency.** Zero-agent operation is the default and stays green in CI. A local model is optional. The barrier is `docker compose up`.

### Interoperability is a feature, not a migration path

Importing from an existing workflow is a first-class input, not a concession. Any tool that holds job-search state is a candidate importer, and export is always available. A user must never have to abandon their current setup to try DabJob, and must never have to ask permission to leave.

```
  four input paths
  ├─ bookmarklet adapter   (the signed-in tab, human-triggered)
  ├─ paste a JD            (no browser, no extension)
  ├─ CSV / JSON            (an existing spreadsheet)
  └─ import a workflow     (ai-job-search, and others)
            │
            ▼  integrity gate → normalize → dedupe
      one SQLite database (FTS5, WAL)
            │
      ├─ gap matrix        (market demand × your level, deterministic)
      ├─ ranked jobs       (rules first, model annotates and is capped)
      └─ pipeline board    (status, timeline, follow-ups)
            │
            ├──► web UI
            ├──► typed tool API  ──► an agent (MCP or HTTP)
            └──► export anytime (CSV / JSON) — no lock-in
```

## 1. Scope

**In scope**
- Four ingest paths: adapters, paste, tabular import, and importers for existing job-search tools.
- An integrity gate for untrusted input: job postings are hostile documents and are treated as such before display or before reaching any provider.
- Normalize skills, compare against the profile, produce a ranked gap matrix.
- Score jobs on rules first, model second; every score is explainable.
- Track applications, communication events, and follow-ups.
- **A typed tool surface** so an external agent can read the pipeline freely and propose changes that a human confirms.
- **Natural-language query over the pipeline**, answered through those tools and citing the rows it used.
- One-command install for newcomers (Docker) and a demo dataset so the app is never empty on first run.
- Export in a documented format at any time.

**Out of scope — the never-merge list**
These are refused in review, not deferred:

- Multi-user, auth, cloud sync, hosted SaaS.
- Auto-applying to jobs on any platform.
- Captcha/slider bypass, proxy pools, parallel scraping, headless mass crawling.
- Dynamic loading of third-party plugin code at runtime.
- **Document generation: tailored CVs, cover letters, interview coaching.** A different product, and a good one exists. DabJob links to it, imports its state, and stops there.
- **Autonomous agents.** Nothing runs on a timer, nothing applies without a person, and no agent may mutate the database without confirmation.
- Recruiter-side features.

**Terms of service.** This tool does not automate access to any platform. Every capture is triggered by a human on a page they are already authorized to view. Users are responsible for complying with the terms of the platforms they use. The guardrails in §9 are load-bearing project policy, not defaults: a PR that relaxes them is rejected.

## 2. Stack

| Layer | Choice | Note |
|---|---|---|
| Backend | Python `>=3.11`, FastAPI, SQLAlchemy 2.0, Pydantic v2 | CI matrix 3.11–3.15 |
| Database | SQLite, WAL, `foreign_keys=ON` | path from `DABJOB_DATA_DIR`, default `data/app.db` |
| Search | SQLite FTS5 (`job_fts`, external content) | prefix search + `snippet()`/`highlight()` |
| Background jobs | Huey + `SqliteHuey` | `data/queue.db`; no Redis; every agent call runs here |
| Frontend | React + TypeScript + Vite + Tailwind, TanStack Query, React Router, dnd-kit, Recharts | Node LTS pinned in `.nvmrc` at M0 |
| i18n | flat `locales/*.json` + a ~20-line `t()` helper | `zh-CN` shipped; `en` is a contribution |
| Capture (primary) | Browser bookmarklet → local ingest endpoint | runs in the user's own signed-in tab |
| Capture (alternative) | Unpacked Chrome extension, tested in the M4 spike | `host_permissions` may avoid Local Network Access limits |
| Ingest (paste) | Raw JD text → parsed fields | works with no browser at all |
| Ingest (tabular) | CSV/JSON with a column-mapping preview | the spreadsheet migration path |
| Ingest (importers) | Per-tool readers for existing job-search state | `ai-job-search` first; see §3 D9 |
| Integrity gate | Deterministic Python, no model | strips hidden text, flags instruction-shaped lines |
| Analysis (outbound) | `ManualProvider` → `HttpTransport` (OpenAI-compatible) → `CliTransport` (any agent CLI) | one task envelope, three transports |
| Agent access (inbound) | Typed tools over HTTP and MCP, read and write split | see §3 D11 |
| Migrations | Alembic | `make migrate` |
| Distribution | `docker compose up` for users; `make setup` for contributors | plus `make demo` |
| License | MIT | see `LICENSE` |

## 3. Decisions

**D1 — Adapter registry with an externally droppable contract.** Capture is not one file of selectors. It is a registry of small adapters sharing one output schema:

```
capture/
  schema.json          # CaptureItem — the only contract, versioned
  adapters/
    boss-search.js
    boss-detail.js
    <platform>-<page>.js
```

An adapter is a pure DOM → `CaptureItem` mapping. It does not fetch, dedupe, store, or log. Dedupe, persistence and the run log live in the backend, which is why an adapter can be tested against a static HTML file.

The launch adapters live in-tree. The contract is designed so an out-of-tree adapter can be dropped in and validated, and the tree splits into a community repository once three external adapters exist.

**D2 — One task envelope, three transports.** Outbound analysis is defined as a JSON task, not as a vendor call:

```json
{ "task": "analyze_job", "schema_version": 1,
  "input": { "…": "…" },
  "constraints": { "tools": "none", "max_output_tokens": 4000 } }
```

| Transport | Reaches | When |
|---|---|---|
| `ManualProvider` | nothing | default; returns an editable template |
| `HttpTransport` | any OpenAI-compatible endpoint | Ollama, LM Studio, vLLM, OpenRouter, DeepSeek |
| `CliTransport` | any binary honoring the stdin/stdout contract | `hermes chat --query-file -`, `claude -p`, `codex exec` |

Consequences:

- The response is validated against a per-task JSON schema. Invalid output is retried once, then stored raw in `agent_task.raw_output` and shown as a failure. Unvalidated prose never enters the database.
- `CliTransport` passes the envelope on stdin so page text is never shell-interpreted. Adapter command templates are configured, not hardcoded per tool.
- The agent protocol is defined in M1 and implemented progressively. Every milestone stays fully usable with `ManualProvider`.

**D3 — FTS5 instead of `LIKE`.** One virtual table over `job` plus triggers keeps full-text search instant with zero new services. Search API uses `snippet()` for result previews.

**D4 — Huey with SQLite storage instead of a hand-rolled worker.** Tasks survive restarts, retries are built in, and there is no Redis to install. Worker is a second process (`make worker`). Agent calls are long, so they are always background tasks with visible status, never a synchronous request.

**D5 — Rules score, model explains.** Hard filters (city, salary floor, seniority) run first; then:

```
score = 0.55 * skill_coverage
      + 0.20 * salary_fit
      + 0.15 * city_fit
      + 0.10 * seniority_fit
      (+ optional model adjustment, capped at ±10, with a written rationale)

skill_coverage = Σ w(skill) * level(profile, skill) / Σ w(skill)
level ∈ {1.0 met, 0.5 partial, 0.0 missing};  w = JD frequency, required skills ×2
```

Weights live in `setting` and are editable from the UI. A model never replaces the rule score; it can only annotate it.

**D6 — Local-first is a constraint, not a limitation.** No accounts, no telemetry, no hosted mode. Binding fails closed: the server refuses to start on a non-loopback address unless `DABJOB_ALLOW_REMOTE=1` is set explicitly. Privacy is the pitch, so it is enforced in code rather than promised in a README.

**D7 — i18n from day zero, one locale shipped.** All UI copy goes through `t()` from M0. Retrofitting i18n later costs an order of magnitude more, and shipping only `zh-CN` costs nothing now.

**D8 — Explainability over a better number.** When the rule score and the model disagree, both are shown. When a score changes, the reason is recorded. A user must always be able to answer "why is this job ranked here."

**D9 — Interoperability over lock-in.** Importers and exporters are first-class and permanent:

- Each importer is a small reader from a known external state format into the internal model, with a fixture snapshot in the test suite.
- Import never destroys: every imported row records its source and importer version, and a re-import is idempotent.
- Export is always available. A feature that only works because the data cannot leave is rejected.
- An importer may not become load-bearing. If a tool changes its format, the importer fails loudly and the rest of the app is unaffected.

First importer: `ai-job-search` — `job_search_tracker.csv`, `job_scraper/seen_jobs.json`, `documents/applications/<company>_<role>/outcome.md`, and the `--format json` output of its portal skills.

**D10 — Untrusted input is a first-class threat.** A job posting is not a document; it is an attacker-controlled document. Postings carry hidden text, zero-width characters, white-on-white keywords, and lines shaped like instructions to an agent. Before a JD is displayed, indexed, or handed to a transport, it passes a deterministic integrity gate: hidden text stripped, invisible characters removed, instruction-shaped lines flagged and shown to the user, hidden links neutered. The gate is plain Python, runs on every ingest path, and is tested with hostile fixtures.

**D11 — AI is bidirectional, and the tool surface is the contract.** An agent reaches DabJob through typed tools, not through SQL and not through a prompt that describes the schema.

- Read tools (`search_jobs`, `get_application`, `list_followups`, `stats_by_city`, …) are open.
- Write tools (`add_event`, `update_status`, …) only ever create a proposal in `agent_action`; a human confirms it in the UI, and only then does the row change.
- Tools are exposed over HTTP and MCP. The web UI is one client of this API; an agent is another.
- Every agent run is an `agent_task` row with transport, status, token count, cost and raw output, so a bad answer is auditable after the fact.
- **A posting's text and a write tool may never share a context.** Analysis tasks declare `"tools": "none"`; operational tasks are not given unsanitized external text.

**D12 — No autonomous agents, ever.** Nothing schedules itself. Nothing runs on a timer. No agent may apply, send, delete or bulk-update. A batch operation is proposed, estimated, shown, and confirmed by a person. This is why the project can give an agent write access at all.

## 4. Data model

| Table | Purpose |
|---|---|
| `profile` | Single row: years, target roles, target cities, salary floor, strengths, gaps |
| `profile_document` | Résumé (PDF/DOCX/MD), self-intro, target statement; extracted text kept |
| `company` | Name, industry, size, funding stage, notes |
| `job` | Raw JD, platform, URL, external id, city, salary range, seniority, fingerprint |
| `job_fts` | FTS5 index over title, company, JD text |
| `skill` | Canonical name + aliases (normalization dictionary) |
| `job_skill` | Job ↔ skill, required flag, weight |
| `job_analysis` | Dimension scores, composite score, summary, outlook, provider, model |
| `application` | Status, channel, résumé version, next follow-up date |
| `application_event` | Timeline: applied / replied / screened / interview / rejected + pasted text |
| `ingest_run` | One ingest batch: source, adapter or importer, counts, status, error |
| `ingest_item` | Per-record outcome, raw payload, and flags raised by the integrity gate |
| `agent_task` | One model or agent run: kind, transport, status, tokens, cost, raw output, error |
| `agent_action` | A proposed mutation awaiting confirmation: tool, arguments, decided_by, applied_at |
| `setting` | Scoring weights, ingest limits, transport config, column mappings |

Pipeline states: `saved → applied → chatted → screening → interview → offer | rejected | ghosted | dropped`.

Three schema notes:

- `ingest_run.source` is an enum (`bookmarklet`, `paste`, `tabular`, `importer`) and `ingest_run.adapter` names the specific reader. Every record answers "where did this come from."
- `ingest_item` keeps the raw payload and the integrity-gate flags. A parsing bug is reproducible from the row that caused it.
- `agent_task` and `agent_action` are the audit trail for D11 and D12. Nothing an agent did is invisible, and nothing it proposed is applied without a `decided_by`.

## 5. Extension points

Four contribution surfaces, each a documented seam with a fixture or example:

| Surface | Language | Contract | Test |
|---|---|---|---|
| Capture adapter | JS | `CaptureItem` in `capture/schema.json` | HTML fixture → expected JSON |
| Importer | Python | external format → internal model | fixture snapshot of the external format |
| Analysis transport | Python | task envelope → schema-valid JSON | recorded transcript, no network |
| Skill dictionary, scoring presets | data | `skill`, `setting` schemas | fixture jobs with expected rankings |

Tools are core, not an extension point: they mutate state and are reviewed against §1 before they are reviewed for quality. Anything else outside this table is core too, which is what keeps an open-source project from becoming a committee.

## 6. Milestones

M0–M3 are complete. M4–M8 are not started; each acceptance line below is the contract for calling its milestone done.

### M0 — Scaffold, distribution, project policy · S — **done 2026-11-27**
`backend/` FastAPI app with `/api/health`, SQLAlchemy session, settings, and fail-closed binding; `frontend/` Vite app with router, one empty Dashboard page, all copy behind `t()`; `locales/zh-CN.json`; `Makefile` (`setup`, `dev`, `test`, `lint`); `.env.example`; `.nvmrc`; `Dockerfile` + `compose.yml`; `.github/workflows/ci.yml` running lint, the full test matrix, the production build, the private-data guard, and a container smoke test. (`LICENSE`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `AGENTS.md`, `README.md`, `.gitignore` already landed.)

**Accept:** `make setup && make dev` serves the UI on Vite with `/api/health` returning `{"ok": true}`; `make test` runs an empty-but-green pytest suite; `make lint` passes; `docker compose up` serves the same UI from a clean machine with no host Python or Node, proven by the container job in CI; starting with `HOST=0.0.0.0` and no `DABJOB_ALLOW_REMOTE` exits non-zero with an explanatory message; no user-facing string is hardcoded in a component; the private-data guard fails on a tracked database, a tracked `.env`, or a fixture containing a real phone number or ID number.

### M1 — Data layer, search, agent protocol · M — **done 2026-11-27**
Models for every table in §4; Alembic initial revision; FTS5 table + triggers; CRUD endpoints for jobs and applications; the task envelope and transport protocol (§3 D2) with `ManualProvider` only; `make demo` seeding five invented fixture jobs.

**Accept:** `make demo && make dev` renders five jobs; `GET /api/jobs?q=FastAPI` returns FTS-ranked matches with snippets; editing a job title updates the index without a rebuild; the protocol is exercised by a contract test that any transport must pass, and `manual` passes it; no seed or fixture row contains a real person, company contact, or address.

### M2 — Ingest, integrity gate, importer · L — **done 2026-11-27**
Paste-import endpoint parsing title/company/city/salary from raw JD; the integrity gate wired into every ingest path, with a hostile fixture corpus; CSV/JSON import with a column-mapping preview; JD-parsing fixture corpus and `make parse-jd`; the `ai-job-search` importer reading `job_search_tracker.csv` and `job_scraper/seen_jobs.json` with source tracking.

**Accept:** paste 5 real JDs, list renders them with parsed fields editable; importing a 100-row spreadsheet creates 100 applications linked to jobs; importing a real `ai-job-search` checkout produces the same application count as its tracker, and a second import adds nothing; a posting with hidden text is stripped and one with instruction-shaped lines is flagged before it can reach any transport; every hostile fixture asserts on both the stripped output and the flags raised.

### M3 — Profile, self-assessment, first transport · M — **done 2026-11-27**
Résumé upload (PDF/DOCX/MD) with text extraction; self-intro and target fields; `HttpTransport` implementing the three methods against an OpenAI-compatible endpoint; assessment stored and versioned by transport and model; `AGENT_PROVIDER` selection with `manual` as the default.

**Accept:** upload a real résumé, see extracted text, save an edited assessment that survives reload; `AGENT_PROVIDER=manual` is idempotent; with a local Ollama model the same action returns a schema-valid assessment; a misconfigured endpoint reports `not_configured` and the manual path still works; a schema-invalid response is retried once, then stored raw and surfaced as a failure; a scanned/image-only PDF fails with an explicit message rather than an empty document.

### M4 — Capture adapters · M
Ingest endpoint (`POST /api/ingest/browser`) with token + Origin allow-list, tolerant of `text/plain` bodies; adapter registry and versioned `capture/schema.json`; two BOSS adapters (search results, detail page); fuzzy dedupe on `platform|external_id`, else `company|title|city`; ingest run log showing accepted / duplicate / failed per adapter; the external-adapter path validated by a test adapter that is not shipped.

**Spike first (≤2h):** confirm a `https://www.zhipin.com` page can POST to `127.0.0.1` under current Chrome Local Network Access rules, and in the same session test an unpacked extension with `host_permissions: http://127.0.0.1/*`. Prefer the bookmarklet; take the extension only if it is demonstrably more reliable. If both are blocked, fall back to clipboard-JSON → paste panel. Do not build a workaround that weakens the guardrails.

**Accept:** clicking the bookmarklet on 10 listings lands 10 structured jobs, re-clicking the same page reports duplicates, and the run log lists both outcomes with the adapter name; each shipped adapter passes a fixture test; an adapter placed outside the tree is validated against `capture/schema.json` and rejected with a clear message when stale.

### M5 — Skill synthesis and gap matrix · M
Alias dictionary seeded from public tech-tag lists; extraction from JD with dictionary matching; unmatched terms go to a review queue where the user classifies them, and a configured transport may suggest a mapping that the user accepts; frequency ranking; per-skill profile level (met / partial / missing); gap matrix ordered by market demand × missing level, presented as a primary view.

**Accept:** over ≥20 captured jobs, the gap view shows a Top-30 frequency ranking and an ordered "what to learn next" list computed with no transport configured; correcting a skill alias re-maps existing `job_skill` rows without re-extraction; an unmatched term stays in the queue until a human resolves it; the gap view is the default landing view when ≥20 jobs exist.

### M6 — Scoring, charts, pipeline board · L
Hard filters + D5 scoring; sortable job list; salary-by-city chart (Recharts); outlook card per job; one-click `add to pipeline`; kanban board with drag-to-change status; communication timeline; follow-up reminders for stale states.

**Accept:** a job promoted from the list appears on the board, survives a drag to `interview`, and a recorded communication event appears in its timeline; scores recompute after the profile changes; every displayed score exposes its breakdown; "what have I left hanging" returns every application past its follow-up date in one query.

### M7 — Agent tool layer and natural-language query · L
Typed read and write tools over §3 D11; HTTP and MCP servers; `agent_action` confirmation queue in the UI; the query box: a question goes to the configured transport as a background `agent_task`, the agent calls tools, and the answer cites the rows it used; token and cost shown per task.

**Accept:** "which companies asked for Kubernetes and then went quiet?" is answered from real rows with links to each job and application; an agent cannot mutate anything — a write attempt appears as a pending `agent_action` and nothing changes until it is confirmed; a hostile posting's text is never present in a context that also has write tools; with no transport configured the query box is hidden and every other screen still works; a failed or timed-out task reports its status and does not leave a partial answer.

### M8 — Agent runtimes, export, backup · S
`CliTransport` honoring the envelope contract on stdin/stdout, with configured command templates rather than per-tool code (validated against `hermes chat --query-file -` and one other CLI); transport comparison view (same job, two transports); CSV/JSON export; `make backup` producing a consistent SQLite copy.

**Accept:** `CliTransport` runs a real agent and returns a schema-valid result; a bad command template fails with a message naming the executable and exit code; with `AGENT_PROVIDER=manual` the comparison view explains why there is nothing to compare; an export re-imports into an empty database without loss; backup restores into a working database.

## 7. Commands

```
make setup        # venv, pip install -e backend, npm install
make dev          # uvicorn + vite (concurrently)
make worker       # huey consumer on data/queue.db
make migrate      # alembic upgrade head
make db-reset     # drop + recreate + seed demo rows
make demo         # seed the invented fixture dataset
make test         # pytest
make lint         # ruff + mypy + tsc, the CI gate
make parse-jd     # parse a JD file on the CLI, print structured output
make import       # run an importer against an external state directory
make export       # write jobs and applications to CSV/JSON
make ask          # ask the pipeline a question through the configured transport
make mcp          # run the agent tool server on stdio
make debug-bundle # redacted ingest archive for issue reports
make backup       # sqlite .backup into data/backups/

docker compose up # the newcomer path: no host Python or Node
```

## 8. Verification

- `pytest` covers JD field extraction, dedupe fingerprint, skill normalization, scoring arithmetic, FTS query building, importers, and the integrity gate.
- The integrity gate has a hostile fixture corpus: hidden text, zero-width characters, white-on-white keywords, instruction-shaped lines, hidden links. Each fixture asserts on the stripped output *and* the flags raised.
- Every capture adapter has an HTML fixture and an expected-output test, so a DOM change is a failing test rather than a user bug report.
- Every importer has a snapshot of the external format it reads, so upstream drift is a failing test rather than a silent partial import.
- Every transport has a recorded transcript. No test calls a network endpoint, spawns a real agent, or costs money.
- The transport contract test is shared: `manual`, `http`, and `cli` either satisfy it or report `not_configured`.
- Write-tool tests assert that nothing changes until a confirmation exists, and that a rejected proposal leaves no trace in the domain tables.
- Injection isolation test: a posting containing instruction-shaped text, handed to a task that has write tools available, cannot produce a write.
- Export round-trip: export, wipe, import, compare. No loss is a test, not a promise.
- No-network check: with no transport configured, the full app works offline.
- No-PII check: fixtures and `data/` are scanned in CI.

## 9. Risks and guardrails

| Risk | Guardrail |
|---|---|
| Platform ToS / account risk | Human-driven capture only; no automation, no captcha bypass, no proxies, no concurrency; Playwright off by default; ToS statement in `README` and `GOVERNANCE.md` |
| Platform takedown or legal pressure | Adapters are reviewed and do not automate access; no hosted service; the project ships without any single adapter |
| Perceived as a clone of an existing project | Positioning in the first paragraph of the README; the contrast is factual and credited; the boundary (no document generation) is published in §1 and in `GOVERNANCE.md` |
| An agent corrupts the pipeline | Read tools open, write tools proposal-only, `agent_action` confirmed by a human; no batch mutation without review (D11, D12) |
| Prompt injection via a job posting | Deterministic integrity gate on every ingest path; analysis tasks run with no tools; posting text never shares a context with a write tool (D10, D11) |
| Agent cost or latency surprises | Every call is a background `agent_task` with tokens and cost recorded; batches are estimated and never run automatically; `manual` remains the default |
| Agent CLI drift (`hermes`, `claude`, `codex`) | One envelope contract, one shared contract test, recorded transcripts; a broken CLI fails loudly instead of degrading silently |
| Non-deterministic output | Schema validation, one repair retry, raw output retained; nothing unvalidated enters the domain tables |
| Upstream `ai-job-search` format drift | Importer fixture snapshot; version detection; loud failure; the rest of the app is unaffected (D9) |
| Local Network Access blocks bookmarklet POST | M4 spike tests bookmarklet and unpacked extension; clipboard-JSON fallback; never relax to a public listener |
| Ingest endpoint exposed | Bind `127.0.0.1` only, fail closed on non-loopback; per-install token; Origin allow-list; body size cap; no CORS `*` |
| PII committed to the repository | `data/` excluded; CI scan for personal data in fixtures; debug bundles redacted by default |
| BOSS DOM changes break the mapper | Selectors isolated per adapter; raw payloads kept in `ingest_item`; fixture test fails loudly |
| Adapter maintenance outpaces maintainers | Small fixture-tested contract; per-adapter ownership documented; a dead adapter is deleted rather than half-maintained |
| Users expect every platform on day one | README states "BOSS直聘 first; adapters welcome" plainly; no roadmap promises for specific platforms |
| Résumé / chat data sensitivity | Local SQLite under `DABJOB_DATA_DIR`; nothing leaves the machine except a transport the user configured; debug bundles redacted |

## 10. Open questions

**Resolved 2026-11-26 — license.** MIT.
**Resolved 2026-11-27 — positioning.** Independent product that imports from adjacent tools, not a layer of one. Name: DabJob.
**Resolved 2026-11-27 — DabAZ web stack.** Opted out. Independent design: no three-repo pins, design decisions live in §3 as `D` entries. See `AGENTS.md`.
**Resolved 2026-11-27 — document generation.** Excluded permanently. AI is analysis and operation, not authoring.
**Resolved 2026-11-27 — AI integration.** Bidirectional: outbound task envelope with three transports, inbound typed tools with confirmation-gated writes (D11, D12).

1. **Second platform** — LinkedIn (widest reach, hardest DOM and legal surface), or 脉脉 (small JD text, but adjacent to BOSS users)? Decide after M4, based on which adapter the first outside contributor attempts.
2. **Adapter repository split** — stay in-tree until three external adapters exist, then split? The trigger is written down; the mechanics are not.
3. **Tool transport order** — MCP first, or plain HTTP first? MCP is the better fit for `hermes` and `claude`; HTTP needs no client support but every agent has to speak it specially.
4. **Default transport when several are configured** — first matching, or an explicit priority list in `setting`?
5. **Scanned résumés** — declare image-only PDFs unsupported, or add optional OCR behind a flag? M3 must at least fail explicitly.
6. **Résumé language** — zh-CN only, or zh + en variants feeding different profile rows?
7. **Docker topology** — one image running API + worker + static frontend, or three services in `compose.yml`?
8. **Outcome proof** — the README needs a concrete before/after, not a feature list. Maintainer's own search, or early users?
