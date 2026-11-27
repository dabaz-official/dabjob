# DabJob

**The local state layer for a job search.** One SQLite database for every posting you considered, every application you sent, every reply, and every follow-up you owe — plus a gap matrix of what the market is asking for and where you are short.

No account. No telemetry. Nothing leaves the machine except a model you configure yourself.

[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![status: planning](https://img.shields.io/badge/status-planning-lightgrey.svg)](ROADMAP.md)

> **Status: planning — no application code yet.** This repository currently holds the roadmap, the merge policy, and the contribution guide. If you are here early, the most useful thing you can do is read [`ROADMAP.md`](ROADMAP.md) and tell us what is wrong with it. Milestones M0–M6 in §6 are the build order; nothing below is runnable today.

## The problem

A job search generates state faster than anyone tracks it. A résumé in one folder. Listings on three platforms. Recruiter threads in two apps. A spreadsheet that stopped being updated in week three. And a memory that knows you were supposed to follow up with someone last Thursday.

Nothing is comparable, nothing is searchable, and the things that matter most — who owes you a reply, which posting you already applied to, what the market keeps asking for that you cannot do — are the things a spreadsheet is worst at.

## What DabJob does

- **Takes four kinds of input.** A bookmarklet that reads the page you are already signed into, a pasted job description, an imported CSV/JSON, or an importer for another job-search tool's state. No scraping on a timer, no headless crawling, no proxy.
- **Normalizes and deduplicates.** The same job seen on two platforms is one job, not two.
- **Builds a gap matrix.** Which skills the market asks for, weighted by how often they appear, against your own level: met, partial, missing. Ordered by what is worth learning next.
- **Scores explainably.** Hard filters first, then a rule score over skill coverage, salary, city and seniority. A model may annotate and adjust by at most ±10 points, and every number carries a written reason.
- **Holds the pipeline.** Board, status history, communication timeline, and a follow-up query that answers "what have I left hanging."
- **Lets an agent operate it.** A typed tool surface means an agent — Hermes, Claude Code, Codex, or a local model — can answer "which companies asked for Kubernetes and then went quiet?" against real rows. It reads freely, and every change it proposes waits for your confirmation.
- **Imports and exports.** Always, in a documented format.

```
bookmarklet · paste · CSV/JSON · existing tool
                    │
                    ▼  integrity gate → normalize → dedupe
              one SQLite database (FTS5)
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
  gap matrix    ranked jobs    pipeline board
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
      web UI            typed tool API → agent
```

## What DabJob does not do

It does not write your CV, tailor a cover letter, or run a mock interview. Those are a different product, and a good one already exists: [`ai-job-search`](https://github.com/ai-job-search-dev/ai-job-search) turns Claude Code into a document pipeline and does it well.

The two are meant to compose. That project does not hold state — its tracker is a CSV in git and its dashboard is a regenerated snapshot. DabJob holds the state, and imports its files.

| | Spreadsheet | Document pipeline | DabJob |
|---|---|---|---|
| Holds the pipeline | partly | no | **yes** |
| Cross-posting search | no | no | **yes** |
| Dedupe by platform id | manual | no | **yes** |
| Follow-up tracking | manual | draft only | **yes** |
| Agent can query and update it | no | through files | **yes, by typed tools** |
| Writes your CV | no | **yes** | no |
| Needs a paid model | no | yes | **no** |
| Where your data lives | a file | tracked in git | a local DB, untracked |

## Why local-first is a design constraint, not a feature

A résumé, a salary floor, a list of rejections and a recruiter thread are among the most sensitive documents a person owns. Any workflow that keeps that state inside a repository is one `git push` away from publishing it, and a public repository cannot have a private fork.

So the boundary is structural here: the database lives under `data/`, which `.gitignore` excludes, CI scans fixtures for personal data, and the server refuses to bind to a non-loopback address unless you explicitly allow it. There is no hosted mode and no account to create. The reasoning is recorded as `D6` in [`ROADMAP.md`](ROADMAP.md#3-decisions).

## Design decisions worth knowing before you contribute

- **Zero-agent operation.** `manual` is the default transport and the application must be fully usable with nothing configured. A model or an agent is optional; a local one works. `D2`.
- **Rules score, the model explains.** No opaque ranking. `D5`.
- **Job postings are untrusted input.** Every posting passes a deterministic gate that strips hidden text and invisible characters and flags instruction-shaped lines before anything is displayed or sent to a model. `D10`.
- **The agent proposes, the human decides.** Read tools are open; every write is a proposal you confirm. No timers, no autonomous runs, no bulk mutations. `D11`, `D12`.
- **Capture only what you can see.** A human opens the page and triggers it. No automation, no captcha bypass, no proxies, no concurrency. `D1`.
- **Interoperability over lock-in.** Import and export are permanent; a feature that only works because your data cannot leave is rejected. `D9`.

The full list, with rationale and consequences, is [`ROADMAP.md` §3](ROADMAP.md#3-decisions).

## Roadmap

| | Milestone | State |
|---|---|---|
| M0 | Scaffold, Docker, i18n, CI | not started |
| M1 | Data layer, search, agent protocol | not started |
| M2 | Ingest, integrity gate, `ai-job-search` import | not started |
| M3 | Profile, self-assessment, first transport | not started |
| M4 | Capture adapters (BOSS直聘 first) | not started |
| M5 | Skill synthesis and gap matrix | not started |
| M6 | Scoring, charts, pipeline board | not started |
| M7 | Agent tool layer and natural-language query | not started |
| M8 | Agent runtimes, export, backup | not started |

Each milestone has written acceptance criteria in [`ROADMAP.md` §6](ROADMAP.md#6-milestones).

## Getting started

**Nothing is runnable yet.** There is no `backend/`, no `frontend/`, and no database. When M0 lands, the intended newcomer path is:

```bash
docker compose up     # planned — not available yet
```

with `make setup && make dev` for contributors who want a local toolchain. If either of those commands fails today, that is expected: the code it would run does not exist.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`GOVERNANCE.md`](GOVERNANCE.md) first. This project has a short, deliberately narrow scope, and most declined pull requests are good work that did not know about it.

The short version: capture adapters, importers, analysis transports, and skill/scoring data are the extension points; translations are always welcome. Multi-user, auto-apply, captcha bypass, hosted sync, document generation, autonomous agents, and runtime plugin loading are refused in review — not deferred.

## License

MIT. See [`LICENSE`](LICENSE).
