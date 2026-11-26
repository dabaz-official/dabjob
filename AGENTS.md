# AGENTS.md — DabJob

Instructions for coding agents working in this repository. Read [`ROADMAP.md`](ROADMAP.md) for what the project is, [`GOVERNANCE.md`](GOVERNANCE.md) for what will be merged, and [`CONTRIBUTING.md`](CONTRIBUTING.md) for how work is done.

**Status:** pre-M0. No application code yet.

## One canonical home per rule

This file does not restate the project. If a fact lives somewhere else, link to it:

| Question | Answer lives in |
|---|---|
| What is this product? | `ROADMAP.md` §0 |
| What is in and out of scope? | `ROADMAP.md` §1 |
| Stack, versions, commands | `ROADMAP.md` §2 and §7 |
| Why a design decision was made | `ROADMAP.md` §3 |
| What gets merged, what never does | `GOVERNANCE.md` |
| How to contribute, test, and report | `CONTRIBUTING.md` |

If a change makes one of those documents wrong, update that document in the same commit. Never fork a rule into a second place.

## The DabAZ web stack does not apply here

- **Rule:** the "DabAZ web stack" section of the user-level agent instructions (`~/.config/opencode/AGENTS.md`).
- **Decision:** not applied. This repository is an explicit opt-out.
- **Reason:** DabJob is a standalone open-source product, not a DabAZ surface. It has no DabAZ brand, deployment, or content surface, and pinning DabAgents / DabDesign / DabFonts would couple its release cadence and its design vocabulary to repositories it does not depend on.
- **Owner:** DabAZ
- **Review:** 2027-05-27, or earlier if DabJob becomes a DabAZ surface.

Consequences, stated so they are not rediscovered later:

- **No three-repo pins.** Do not fetch or pin DabAgents, DabDesign, or DabFonts. Do not copy their tokens, font files, breakpoints, or component specs into this repository.
- **Design decisions are `D` entries in `ROADMAP.md` §3**, not `DEC-` entries in DabDesign's governance. This project's decision log is its roadmap.
- **Visual and typographic choices are local and owned here.** Typography, spacing, and component rules live in the frontend once M0 lands; until then they are simply undecided, and undecided is the correct state to represent.
- **The project templates are not used.** Do not copy `templates/AGENTS.md`, `templates/README.md`, or `templates/ci.yml` from DabAgents.

## Non-negotiables for any change

These are enforced in review and are not preferences:

1. **No personal data in the repository.** No real résumés, recruiter threads, email addresses, or phone numbers — not in fixtures, not in tests, not in examples. Invent every fixture.
2. **Every ingest path runs the integrity gate.** Job postings are untrusted input. Do not bypass the gate, and do not replace it with an LLM call.
3. **No outbound request the user did not configure.** No telemetry, no phone-home, no default remote endpoint.
4. **The zero-LLM path stays green.** `manual` is the default provider and the app must be fully usable with nothing configured.
5. **Adapters stay pure.** A capture adapter maps DOM to `CaptureItem` and does nothing else — no fetch, no navigation, no storage.
6. **No unattended third-party code.** Nothing is fetched and executed at runtime.

## Working rules

- Run `make lint` and `make test` before claiming a change works. If they do not exist yet, say so rather than inventing a substitute.
- Do not add scope. If a task seems to require something outside `ROADMAP.md` §1, say that and propose a roadmap change instead of building it.
- Do not reformat code you are not changing.
- Documentation is written in English. User-facing UI copy is `zh-CN` first and goes through `t()`.
- Commit messages follow Conventional Commits because the PR title becomes the release note (`CONTRIBUTING.md`).
