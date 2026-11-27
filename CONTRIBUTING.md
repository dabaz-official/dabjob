# Contributing

**DabJob** is the local state layer for a job search: it holds the pipeline, and it does not generate documents. Read [`GOVERNANCE.md`](GOVERNANCE.md) before your first pull request — it is short, and it is the document that decides whether your work gets merged.

**Status:** the repository is pre-M0, so the setup commands below describe the target contract and land with M0. Everything in `GOVERNANCE.md` is in force now.

## Ways to contribute, in rough order of value

1. **A capture adapter** for a platform you actually use. This is the project's scarcest resource.
2. **An importer** for a job-search tool you already use. Small, self-contained, and immediately useful to everyone leaving that tool.
3. **A JD parsing fixture** that currently parses wrong. Almost always merges.
4. **A provider** for a model or gateway the existing ones do not reach.
5. **Skill aliases and scoring presets** — data, not code.
6. **A UI locale.** The app ships `zh-CN`; every other language is a pure addition.
7. **Bug reports with a debug bundle.** Reproducible bug reports are worth more than most patches.

## Ground rules

- The never-merge list in `GOVERNANCE.md` is not negotiable. PRs against it are closed, politely.
- One concern per pull request. A refactor and a feature in the same PR will be asked to split.
- Every bug fix ships with a regression test. Every parser change ships with a fixture.
- **Show the failure on the real path.** A test that fails before your fix and passes after is necessary but not sufficient; the input must be one the application actually produces. See *Review standards* in `GOVERNANCE.md`.
- No hardcoded user-facing strings. All UI copy goes through `t()` and lives in `locales/`.
- Nothing in this repository may contain real personal data — no real résumés, no real recruiter threads, no real email addresses. Invent fixtures.
- Any code that displays or forwards a job posting must go through the integrity gate. Do not bypass it "for testing."
- Commits carry `Signed-off-by` (`git commit -s`). No CLA, no copyright assignment.

## Development setup

Requirements: Python `>=3.11`, Node LTS (see `.nvmrc`), `make`.

```
make setup        # venv, editable install, npm install
make dev          # uvicorn + vite
make test         # pytest
make lint         # ruff + mypy + tsc — the same gate CI runs
make demo         # seed the fixture dataset so the UI is not empty
make import       # run an importer against an external state directory
make export       # write jobs and applications to CSV/JSON
```

Newcomers who only want to run the app should use Docker instead and never touch a local toolchain:

```
docker compose up
```

Data lives under `DABJOB_DATA_DIR` (default `data/`). Set it if you want an isolated database per experiment.

## The four extension points

Everything outside this table is core, and is reviewed for scope before it is reviewed for quality.

| Surface | Language | Contract | Required test |
|---|---|---|---|
| Capture adapter | JavaScript | `CaptureItem` in `capture/schema.json` | HTML fixture → expected JSON |
| Importer | Python | external format → internal model | snapshot fixture of the external format |
| Analysis transport | Python | task envelope → schema-valid JSON | recorded transcript, no network, no cost |
| Skill dictionary, scoring presets | data | `skill` and `setting` schemas | fixture jobs with expected rankings |

### Writing a capture adapter

1. Copy the adapter template under `capture/adapters/`.
2. Implement the platform + page-kind metadata and a single `extract(document) -> CaptureItem` function.
3. Keep it pure: read the DOM, return an object, do nothing else.
4. Drop a saved copy of the page next to your test as an HTML fixture.
5. Add the expected-output test. `make test` must fail before you fix it, and pass after.
6. Comment the selector assumptions at the top of the file — what the page looked like when you wrote it.

`CaptureItem` carries: `platform`, `pageKind`, `url`, `externalId` (may be absent), `title`, `company`, `city`, `salaryText`, `seniority`, `jdText`, `capturedAt`, `adapterVersion`.

Adapters do not fetch, dedupe, store, or log. Deduplication, persistence, and the ingest run log are backend responsibilities, which is exactly why an adapter can be tested against a static file.

`capture/schema.json` is versioned. An adapter you maintain outside this repository can be validated against it and dropped in without a core change; you are not required to donate it upstream to have it supported.

### Writing an importer

An importer reads another tool's job-search state into ours. This is a first-class contribution, not a migration hack — see *Importer policy* in `GOVERNANCE.md`.

1. Create a reader under `ingest/importers/<tool>/`.
2. Read only files the external tool documents as its own state. Do not scrape its UI and do not call its API if a file will do.
3. Map into the internal model, recording `source` and `importerVersion` on every row.
4. Ship a snapshot fixture of the external format, with invented data — never a real user's export.
5. Make it idempotent: importing the same directory twice must create nothing the second time.
6. Fail loudly on a field you cannot read, naming the file and the field. A silent partial import is worse than a refusal.

### Writing a transport

A transport turns a task envelope into schema-valid JSON. The envelope and the per-task schemas are fixed; a transport only moves bytes.

- Implement the shared contract test — it is the same test `manual`, `http`, and `cli` must pass.
- Return `not_configured` rather than raising when credentials or an executable are missing.
- Never become load-bearing: the app must keep working, on rules alone, when you are absent.
- Do not require a paid account to run your tests. Mock the transport and assert on the payload shape.
- Ship a recorded transcript so the suite runs offline and costs nothing.

### Adding a tool

Tools are core, not an extension point — they touch state. Read the *Tool policy* in `GOVERNANCE.md` first. A read tool needs a test that proves it cannot mutate. A write tool needs a test that proves nothing changes until a `decided_by` exists.

### Contributing data

Skill aliases and scoring weights are reviewed as data, not code. Show the effect: include a fixture job set and the ranking before and after your change, so the diff is arguable.

## Code standards

- **Python:** `ruff format`, `ruff check`, `mypy` clean. Type hints on public functions.
- **TypeScript:** `tsc --noEmit` clean. Avoid `any`; prefer a narrow type or a `unknown` + guard.
- **Tests:** pytest for backend, Vitest for frontend logic. UI-only changes may ship without new tests if the change is visually verifiable and the PR says how.
- **Untrusted input:** any code that displays, indexes, or forwards a job posting goes through the integrity gate. When you touch the gate, add a hostile fixture with it.
- **Comments:** explain why, not what. A comment restating the code is deleted in review.

## Reporting a bug

Run:

```
make debug-bundle
```

It produces a redacted archive — emails, phone numbers, messaging IDs and tokens removed — suitable for attaching to a public issue. Include with it:

- OS, Python or Docker version, and the app version or commit,
- which ingest path was involved: adapter, paste, tabular, or importer,
- the platform and adapter name, if capture is involved,
- what you expected and what happened,
- the redacted ingest item, if the bug is in parsing or the integrity gate.

**Never paste your résumé, recruiter chat logs, or an unredacted database into an issue.** If the redaction misses something, say so instead of posting the raw data.

For adapter breakage, the most useful issue is: the fixture, the selector that stopped matching, and the page shape you now see.

For importer breakage, attach the upstream version and the field the importer named when it refused.

## Pull requests

A PR is merged when all of the following hold:

- CI is green (`make lint` and `make test`).
- It does one thing, and the description says what changes for the user.
- It touches only the extension points it claims to touch.
- It does not relax a guardrail in `GOVERNANCE.md`.
- It includes the tests its surface requires (see the table above).
- Its title is a Conventional Commits message — the title becomes the release note (below).

Closed without review:

- anything on the never-merge list,
- reformat-only or rename-only diffs with no functional change,
- dependency bumps that are not explained,
- PRs that bundle an unrelated refactor with a feature.

Read *Review standards* in `GOVERNANCE.md` before arguing with a review: rule fit is judged before execution quality, claims are verified on the real path, and an invited PR is reserved for its invitee for seven days.

## Commit messages

PRs are squash-merged and the title becomes the whole commit message, then the release note. Use Conventional Commits:

```
feat(capture): match BOSS detail page company block
fix(backend): dedupe on external id before title fuzzy match
feat(ingest): import ai-job-search tracker and seen jobs
docs: record the positioning decision
```

Scopes: `backend`, `frontend`, `capture`, `ingest`, `providers`, `data`, `docs`, `ci`.

`feat` produces a minor release, `type!:` a major one, and `fix`/`perf`/`refactor` a patch. A week of only `docs`, `chore`, and `ci` ships nothing. Do not edit the changelog by hand — it is generated from merged titles.

## Localization

- Keys are flat and dotted: `dashboard.empty.title`.
- `zh-CN` is the source locale. Adding `en` means adding `locales/en.json` and nothing else.
- A PR that adds a string must add it to every existing locale file, or mark it explicitly as untranslated.

## Conduct

This project follows the Contributor Covenant. Be direct about code and generous about people. Harassment, or pressuring someone to share personal job-search data, is grounds for removal from the project.
