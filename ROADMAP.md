# ROADMAP — DabJob

**Status:** planning. No application code yet.
**What it is:** the local state layer for a job search — a job-search CRM, not a document generator.
**Scope:** single local user, `localhost`, no auth, no telemetry. zh-CN UI shipped first, i18n-ready from day zero. English repository artifacts.
**Positioning:** open source, multi-platform, interoperable. BOSS直聘 (`zhipin.com`) is the first capture adapter, not the product.
**Supersedes:** `~/Downloads/ai_job-plan.md` (2026-11-01 draft), the single-platform revision of 2026-11-26, and the "workbench" framing of 2026-11-26.

## 0. Positioning

Job search data lives in five disconnected places: the résumé, BOSS/脉脉 listings, chat threads, a spreadsheet of applications, and memory. Nothing is comparable, nothing is searchable, and follow-ups get dropped.

DabJob turns that into one local database plus a web UI. It is the place where the pipeline lives.

### What this is not

`ai-job-search-dev/ai-job-search` (MIT, ~73k stars as of Nov 2026) turns Claude Code into a document factory: it scrapes portals, ranks postings, writes tailored CVs and cover letters, and preps interviews. It is good at that, and DabJob does not compete with it.

It also deliberately does not hold state. Its tracker is a CSV in git, its dashboard is a regenerated snapshot, and its maintainer declined a local web console as *"a product of its own."*

**DabJob is that product.** It does not write your CV. It holds the pipeline: every posting you considered, every application you sent, every reply, every follow-up you owe — in one queryable database, with a board, a timeline, and reminders.

The two compose. If you already run a document workflow, DabJob imports its state and gives it a board. If you do not, DabJob works on its own with paste and CSV.

### Four claims, each structural rather than promotional

1. **State in a database, not in git.** Your résumé, salary floor and recruiter threads are the most sensitive documents you own. A SQLite file under `DABJOB_DATA_DIR`, excluded from version control, with no account and no telemetry, is a different risk profile from "personal data written into tracked files and warned about in a fork notice."
2. **Queryable.** FTS5 across every JD, dedupe across platforms, per-city salary aggregation, and a follow-up query that answers "what have I left hanging." A spreadsheet and a JSON blob cannot do this; a regenerated report can only re-render what it already knows.
3. **No paid dependency.** Zero-LLM operation is the default and stays green in CI. A local model is optional. The barrier is `docker compose up`.
4. **Conservative capture.** Adapters run in the tab you are already signed into, triggered by you. No CLI that fetches boards on a schedule, no header spoofing to defeat a 403.

The analytical differentiator is the **gap matrix**: market demand × your own level, per skill, telling you what to learn next. Job boards rank listings; DabJob tells you what the market is asking for and where you are short.

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
      ├─ gap matrix        (market demand × your level)
      ├─ ranked jobs       (rules first, LLM optional and capped)
      └─ pipeline board    (status, timeline, follow-ups)
            │
            ▼  export anytime (CSV / JSON) — no lock-in
```

## 1. Scope

**In scope**
- Four ingest paths: adapters, paste, tabular import, and importers for existing job-search tools.
- An integrity gate for untrusted input: job postings are hostile documents and are treated as such before display or before reaching any provider.
- Normalize skills, compare against the profile, produce a ranked gap matrix.
- Score jobs on rules first, LLM second; every score is explainable.
- Track applications, communication events, and follow-ups.
- One-command install for newcomers (Docker) and a demo dataset so the app is never empty on first run.
- Export in a documented format at any time.

**Out of scope — the never-merge list**
These are refused in review, not deferred:

- Multi-user, auth, cloud sync, hosted SaaS.
- Auto-applying to jobs on any platform.
- Captcha/slider bypass, proxy pools, parallel scraping, headless mass crawling.
- Dynamic loading of third-party plugin code at runtime.
- **Document generation: tailored CVs, cover letters, interview coaching.** That is a different product, and a good one already exists. DabJob links to it; it does not rebuild it.
- Recruiter-side features.

**Terms of service.** This tool does not automate access to any platform. Every capture is triggered by a human on a page they are already authorized to view. Users are responsible for complying with the terms of the platforms they use. The guardrails in §9 are load-bearing project policy, not defaults: a PR that relaxes them is rejected.

## 2. Stack

| Layer | Choice | Note |
|---|---|---|
| Backend | Python `>=3.11`, FastAPI, SQLAlchemy 2.0, Pydantic v2 | CI matrix 3.11–3.15 |
| Database | SQLite, WAL, `foreign_keys=ON` | path from `DABJOB_DATA_DIR`, default `data/app.db` |
| Search | SQLite FTS5 (`job_fts`, external content) | prefix search + `snippet()`/`highlight()` |
| Background jobs | Huey + `SqliteHuey` | `data/queue.db`; no Redis |
| Frontend | React + TypeScript + Vite + Tailwind, TanStack Query, React Router, dnd-kit, Recharts | Node LTS pinned in `.nvmrc` at M0 |
| i18n | flat `locales/*.json` + a ~20-line `t()` helper | `zh-CN` shipped; `en` is a contribution |
| Capture (primary) | Browser bookmarklet → local ingest endpoint | runs in the user's own signed-in tab |
| Capture (alternative) | Unpacked Chrome extension, tested in the M3 spike | `host_permissions` may avoid Local Network Access limits |
| Ingest (paste) | Raw JD text → parsed fields | works with no browser at all |
| Ingest (tabular) | CSV/JSON with a column-mapping preview | the spreadsheet migration path |
| Ingest (importers) | Per-tool readers for existing job-search state | `ai-job-search` first; see §3 D9 |
| Integrity gate | Deterministic Python, no LLM | strips hidden text, flags injection-shaped lines |
| Analysis | Pluggable `AgentProvider`: `manual` → `openai-compat` | provider chosen by env var |
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

The launch adapters live in-tree. The contract is designed so an out-of-tree adapter can be dropped in and validated, and the tree splits into a community repository once three external adapters exist. There is precedent for both shapes and no need to choose before the third one arrives.

**D2 — Analysis is a provider, and the provider is not vendor-locked.** `AgentProvider` defines `analyze_profile`, `analyze_job`, `synthesize_skills`.

- `ManualProvider` ships first and returns editable drafts. It is the default.
- `OpenAICompatProvider` takes `base_url`, `api_key`, `model`, covering Ollama, LM Studio, vLLM, OpenRouter, DeepSeek, and any compatible gateway.
- Private providers live in `examples/`, not in the milestone plan.

Consequence: every milestone up to M6 works with no LLM at all.

**D3 — FTS5 instead of `LIKE`.** One virtual table over `job` plus triggers keeps full-text search instant with zero new services. Search API uses `snippet()` for result previews.

**D4 — Huey with SQLite storage instead of a hand-rolled worker.** Tasks survive restarts, retries are built in, and there is no Redis to install. Worker is a second process (`make worker`).

**D5 — Rules score, LLM explains.** Hard filters (city, salary floor, seniority) run first; then:

```
score = 0.55 * skill_coverage
      + 0.20 * salary_fit
      + 0.15 * city_fit
      + 0.10 * seniority_fit
      (+ optional LLM adjustment, capped at ±10, with a written rationale)

skill_coverage = Σ w(skill) * level(profile, skill) / Σ w(skill)
level ∈ {1.0 met, 0.5 partial, 0.0 missing};  w = JD frequency, required skills ×2
```

Weights live in `setting` and are editable from the UI. The LLM never replaces the rule score; it can only annotate it.

**D6 — Local-first is a constraint, not a limitation.** No accounts, no telemetry, no hosted mode. Binding fails closed: the server refuses to start on a non-loopback address unless `DABJOB_ALLOW_REMOTE=1` is set explicitly. Privacy is the pitch, so it is enforced in code rather than promised in a README.

**D7 — i18n from day zero, one locale shipped.** All UI copy goes through `t()` from M0. Retrofitting i18n later costs an order of magnitude more, and shipping only `zh-CN` costs nothing now.

**D8 — Explainability over a better number.** When the rule score and the LLM disagree, both are shown. When a score changes, the reason is recorded. A user must always be able to answer "why is this job ranked here."

**D9 — Interoperability over lock-in.** Importers and exporters are first-class and permanent. Concretely:

- Each importer is a small reader from a known external state format into the internal model, with a fixture snapshot of that format in the test suite.
- Import never destroys: every imported row records its source and importer version, and a re-import is idempotent.
- Export is always available in a documented format. A feature that only works because the data cannot leave is rejected.
- An importer may not become load-bearing. If a tool changes its format, the importer fails loudly and the rest of the app is unaffected.

First importer: `ai-job-search`. Its state is readable and documented — `job_search_tracker.csv`, `job_scraper/seen_jobs.json`, `documents/applications/<company>_<role>/outcome.md`, and the `--format json` output of its portal skills.

**D10 — Untrusted input is a first-class threat.** A job posting is not a document; it is an attacker-controlled document. Postings routinely carry hidden text, zero-width characters, white-on-white keywords, and lines shaped like instructions to an agent. Before a JD is displayed, indexed, or handed to a provider, it passes a deterministic integrity gate: hidden text stripped, invisible characters removed, instruction-shaped lines flagged and shown to the user, hidden links neutered. The gate is plain Python, runs on every ingest path, and is tested with hostile fixtures. It is not optional and it is not an LLM call.

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
| `setting` | Scoring weights, ingest limits, provider config, column mappings |

Pipeline states: `saved → applied → chatted → screening → interview → offer | rejected | ghosted | dropped`.

Two schema notes:

- `ingest_run.source` is an enum (`bookmarklet`, `paste`, `tabular`, `importer`) and `ingest_run.adapter` names the specific reader. Every record answers "where did this come from."
- `ingest_item` keeps the raw payload and the integrity-gate flags. A parsing bug is reproducible from the row that caused it, and a flagged posting stays flagged.

## 5. Extension points

Four contribution surfaces, each a documented seam with a fixture or example:

| Surface | Language | Contract | Test |
|---|---|---|---|
| Capture adapter | JS | `CaptureItem` in `capture/schema.json` | HTML fixture → expected JSON |
| Importer | Python | external format → internal model | fixture snapshot of the external format |
| Agent provider | Python | `AgentProvider` protocol | provider matrix check (§8) |
| Skill dictionary, scoring presets | data | `skill`, `setting` schemas | fixture jobs with expected rankings |

Anything outside these is core and is reviewed for scope against §1 before quality. This is what keeps an open-source project from becoming a committee.

## 6. Milestones

### M0 — Scaffold, distribution, project policy · S
`backend/` FastAPI app with `/api/health`, SQLAlchemy session, settings; `frontend/` Vite app with router, one empty Dashboard page, all copy behind `t()`; `README.md` with the positioning statement, a contrast paragraph, a screenshot, and the Docker quickstart; `Makefile`; `.env.example`; `.nvmrc`; `.gitignore`; `data/` excluded from git; `Dockerfile` + `compose.yml`; `make demo` seed script. (`LICENSE`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `AGENTS.md` already landed.)

**Accept:** `make setup && make dev` serves the UI on Vite with `/api/health` returning `{"ok": true}`; `make test` runs an empty-but-green pytest suite; `docker compose up` serves the same UI from a clean machine with no host Python or Node; no user-facing string is hardcoded in a component; a CI check fails if anything under `data/` or any fixture looks like real personal data.

### M1 — Data layer, ingest, search · L
Models for `profile`, `company`, `job`, `skill`, `job_skill`, `application`, `application_event`, `setting`, `ingest_run`, `ingest_item`; Alembic initial revision; FTS5 table + triggers; CRUD endpoints for jobs and applications; paste-import endpoint parsing title/company/city/salary from raw JD; the integrity gate wired into every ingest path with hostile fixtures; CSV/JSON import with a column-mapping preview; JD-parsing fixture corpus and `make parse-jd`; **the `ai-job-search` importer**, reading `job_search_tracker.csv` and `job_scraper/seen_jobs.json` into jobs and applications with source tracking.

**Accept:** paste 5 real JDs, list renders them with parsed fields editable; `GET /api/jobs?q=FastAPI` returns FTS-ranked matches with snippets; changing a job's title updates the index; importing a 100-row spreadsheet creates 100 applications linked to jobs; importing a real `ai-job-search` checkout produces the same application count as its tracker, and a second import adds nothing; a posting with hidden text is stripped and a posting with instruction-shaped lines is flagged before it can reach a provider; every entry in the parsing fixture corpus has a regression test.

### M2 — Profile and self-assessment · M
Résumé upload (PDF/DOCX/MD) with text extraction; self-intro and target fields; `ManualProvider` produces an editable assessment draft (strengths / gaps / target fit / positioning); assessment is stored and versioned by provider.

**Accept:** upload a real résumé, see extracted text, save an edited assessment that survives reload; re-running with `AGENT_PROVIDER=manual` is idempotent; a scanned/image-only PDF fails with an explicit message rather than an empty document.

### M3 — Capture adapters and adapter contract · M
Ingest endpoint (`POST /api/ingest/browser`) with token + Origin allow-list, tolerant of `text/plain` bodies; adapter registry and versioned `capture/schema.json`; two BOSS adapters (search results, detail page); fuzzy dedupe on `platform|external_id`, else `company|title|city`; ingest run log showing accepted / duplicate / failed per adapter; the documented external-adapter path validated by a test adapter that is not shipped.

**Spike first (≤2h):** confirm a `https://www.zhipin.com` page can POST to `127.0.0.1` under current Chrome Local Network Access rules, and in the same session test an unpacked extension with `host_permissions: http://127.0.0.1/*`. Prefer the bookmarklet; take the extension only if it is demonstrably more reliable. If both are blocked, fall back to clipboard-JSON → paste panel. Do not build a workaround that weakens the guardrails.

**Accept:** clicking the bookmarklet on 10 listings lands 10 structured jobs, re-clicking the same page reports duplicates, and the run log lists both outcomes with the adapter name; each shipped adapter passes a fixture test; an adapter placed outside the tree is validated against `capture/schema.json` and rejected with a clear message when it is stale; `make debug-bundle` produces a redacted archive suitable for an issue report.

### M4 — Skill synthesis and gap matrix · M
Alias dictionary seeded from public tech-tag lists; extraction from JD with dictionary matching, LLM reserved for unmatched terms; frequency ranking; per-skill profile level (met / partial / missing); **gap matrix ordered by market demand × missing level**, presented as the app's primary view rather than a secondary report; manual correction of skill mappings.

**Accept:** over ≥20 captured jobs, the gap view shows a Top-30 frequency ranking and an ordered "what to learn next" list; correcting a skill alias re-maps existing `job_skill` rows without re-extraction; the gap view is reachable in one click from the dashboard and is the default landing view when ≥20 jobs exist.

### M5 — Scoring, charts, pipeline · L
Hard filters + D5 scoring; sortable job list; salary-by-city chart (Recharts); outlook card per job; one-click `add to pipeline`; kanban board with drag-to-change status; communication timeline; follow-up reminders for stale states.

**Accept:** a job promoted from the list appears on the board, survives a drag to `interview`, and a recorded communication event appears in its timeline; scores recompute after the profile changes; every displayed score exposes its breakdown; "what have I left hanging" returns every application past its follow-up date in one query.

### M6 — Providers, export, backup · S
`OpenAICompatProvider` implementing the three methods, configured by `AGENT_PROVIDER=openai-compat` plus `base_url`/`api_key`/`model`; provider comparison view (same job, two providers); CSV/JSON export; `make backup` producing a consistent SQLite copy.

**Accept:** `AGENT_PROVIDER=openai-compat` against a local Ollama model re-analyzes a job and both results are visible side by side; with a misconfigured provider the app reports `not_configured` and degrades to rules instead of failing; an export re-imports into an empty database without loss; backup restores into a working database.

## 7. Commands

```
make setup        # venv, pip install -e backend, npm install
make dev          # uvicorn + vite (concurrently)
make worker       # huey consumer on data/queue.db
make migrate      # alembic upgrade head
make db-reset     # drop + recreate + seed demo rows
make demo         # seed the M1–M5 fixture dataset
make test         # pytest
make lint         # ruff + mypy + tsc, the CI gate
make parse-jd     # parse a JD file on the CLI, print structured output
make import       # run an importer against an external state directory
make export       # write jobs and applications to CSV/JSON
make debug-bundle # redacted ingest archive for issue reports
make backup       # sqlite .backup into data/backups/

docker compose up # the newcomer path: no host Python or Node
```

## 8. Verification

- `pytest` covers JD field extraction, dedupe fingerprint, skill normalization, scoring arithmetic, FTS query building, importers, and the integrity gate.
- The integrity gate has a hostile fixture corpus: hidden text, zero-width characters, white-on-white keywords, instruction-shaped lines, hidden links. Each fixture asserts on the stripped output *and* the flags raised.
- Every capture adapter has an HTML fixture and an expected-output test, so a DOM change is a failing test rather than a user bug report.
- Every importer has a snapshot of the external format it reads, so upstream drift is a failing test rather than a silent partial import.
- Export round-trip: export, wipe, import, compare. No loss is a test, not a promise.
- Seed script inserts 5 fixture jobs so M1–M5 are testable without capturing anything.
- One live capture session per milestone that touches capture; record accepted/duplicate/failed counts.
- Provider matrix check: `manual` and `openai-compat` both return valid analysis payloads, or explicitly `not_configured`.
- No-network check: with no provider configured, the full app works offline.
- No-PII check: fixtures and `data/` are scanned in CI.

## 9. Risks and guardrails

| Risk | Guardrail |
|---|---|
| Platform ToS / account risk | Human-driven capture only; no automation, no captcha bypass, no proxies, no concurrency; Playwright off by default; ToS statement in `README` and `GOVERNANCE.md` |
| Platform takedown or legal pressure | Adapters are reviewed, in-tree or explicitly user-vetted, and do not automate access; no hosted service; the project ships without any single adapter |
| Perceived as a clone of an existing project | Positioning is stated in the first paragraph of the README; the contrast is factual and credited; the product boundary (no document generation) is published in §1 |
| Adjacency caps the project's identity | DabJob ships standalone paths (paste, CSV, own adapters) so it is not dependent on any single upstream; the importer is one feature among several |
| Upstream `ai-job-search` format drift | Importer fixture snapshot; version detection; loud failure; the rest of the app is unaffected (D9) |
| Prompt injection via a job posting | Deterministic integrity gate on every ingest path; postings are never instructions; flags are visible to the user (D10) |
| Local Network Access blocks bookmarklet POST | M3 spike tests bookmarklet and unpacked extension; clipboard-JSON fallback; never relax to a public listener |
| Ingest endpoint exposed | Bind `127.0.0.1` only, fail closed on non-loopback; per-install token; Origin allow-list; body size cap; no CORS `*` |
| PII committed to the repository | `data/` excluded; CI scan for personal data in fixtures; debug bundles redacted by default |
| BOSS DOM changes break the mapper | Selectors isolated per adapter; raw payloads kept in `ingest_item`; fixture test fails loudly |
| Adapter maintenance outpaces maintainers | Small fixture-tested contract; per-adapter ownership documented; a dead adapter is deleted rather than half-maintained |
| Users expect every platform on day one | README states "BOSS直聘 first; adapters welcome" plainly; no roadmap promises for specific platforms |
| LLM unavailable or wrong | `manual` provider is the default; analysis is always editable; scores degrade to rules |
| Résumé / chat data sensitivity | Local SQLite under `DABJOB_DATA_DIR`; nothing leaves the machine except an explicitly configured provider |

## 10. Open questions

**Resolved 2026-11-26 — license.** MIT.
**Resolved 2026-11-27 — positioning.** Independent product that imports from adjacent tools, not a layer of one (option B). Name: DabJob.
**Resolved 2026-11-27 — DabAZ web stack.** Opted out. Independent design: no three-repo pins, design decisions live in §3 as `D` entries. See `AGENTS.md`.

1. **Second platform** — LinkedIn (widest reach, hardest DOM and legal surface), or 脉脉 (small JD text, but adjacent to BOSS users)? Decide after M3, based on which adapter the first outside contributor attempts.
2. **Adapter repository split** — stay in-tree until three external adapters exist, then split? The trigger is written down; the mechanics are not.
3. **Scanned résumés** — declare image-only PDFs unsupported, or add optional OCR behind a flag? M2 must at least fail explicitly.
4. **Résumé language** — zh-CN only, or zh + en variants feeding different profile rows?
5. **Docker topology** — one image running API + worker + static frontend, or three services in `compose.yml`?
6. **Outcome proof** — the README needs a concrete before/after, not a feature list. Does that come from the maintainer's own search, or from early users willing to describe theirs?
