# GOVERNANCE

**Status:** pre-M0. Deliberately written before there is code to argue about.

This document exists for one reason: so a contributor can predict whether a pull request will be merged without having to ask a person. Everything below is a published rule, and the maintainer follows it even when a different outcome would be personally preferable.

## Model

**Benevolent dictator.** One maintainer merges. There is no committee, no vote, and no steering group. This is stated plainly rather than dressed up, because pretending otherwise wastes contributors' time.

What disciplines a single maintainer is not consensus but **published criteria**:

- Scope comes from [`ROADMAP.md`](ROADMAP.md) §1.
- Extension points come from `ROADMAP.md` §5.
- Design decisions come from `ROADMAP.md` §3.
- A PR rejected for scope is rejected against a written rule, and the rule is quoted in the rejection.

## Scope authority

`ROADMAP.md` §1 is the contract. Changing it requires a ROADMAP pull request with a rationale — never a side effect of a feature PR. A feature PR that only makes sense after a scope change is closed with a request to open the scope change first.

This ordering is intentional: scope arguments are cheap when nothing is built and expensive when a contributor has already written 800 lines.

## The never-merge list

These are refused even when well implemented, even with tests, even with an offer to maintain them. They are not deferred; they are out.

- Multi-user, auth, cloud sync, hosted SaaS.
- Auto-applying to jobs on any platform.
- Captcha/slider bypass, proxy pools, parallel scraping, headless mass crawling.
- Dynamic loading of third-party plugin code at runtime.
- **Document generation: tailored CVs, cover letters, interview coaching.** That is a different product and a good one already exists in this space. DabJob links to it and imports its state; it does not rebuild it. A PR that adds document generation is declined for scope even if it is excellent, because it turns a pipeline tool into a document factory and there is no principled stopping point.
- Recruiter-side features.

## Constitutional invariants

Non-negotiable regardless of who proposes the change or how much it would help adoption.

1. **Local-first.** No telemetry, no phone-home, no account system, no default remote endpoint. A PR that adds an outbound request the user did not explicitly configure is rejected.
2. **Fail-closed binding.** A non-loopback bind requires `DABJOB_ALLOW_REMOTE=1`. This may be made friendlier, better documented, or more prominent — it may not be removed or defaulted open.
3. **Zero-LLM operation.** The application must be fully usable with no provider configured. `manual` remains the default. No feature may require an LLM to function, and the offline path must stay green in CI.
4. **Human-driven capture.** Every capture is initiated by a human on a page that human may already view. No scheduler that navigates pages, no queue that fetches listings, no headless crawling. The Playwright adapter stays off by default.
5. **No unattended third-party code.** Adapters are reviewed code: in-tree, or a file the user deliberately placed and can read. Nothing is fetched and executed at runtime, and no installer pulls adapter code from another repository. Manual copy is the security model, not an inconvenience to be automated away.
6. **Explainable scores.** Any score shown to a user exposes its components and a written reason. A PR that replaces the rule score with an opaque number is rejected regardless of accuracy.
7. **Untrusted input.** A job posting is an attacker-controlled document. Every ingest path runs the deterministic integrity gate before a posting is displayed, indexed, or handed to a provider. The gate is plain Python, tested against hostile fixtures, and may be strengthened but never bypassed or replaced by an LLM call.
8. **Interoperability.** Import and export are permanent features, not migration incentives. A feature that only works because the user's data cannot leave is rejected, and an importer that becomes load-bearing is a regression.

## Adapter lifecycle

Adapters rot, and that is the single largest maintenance risk in this project (`ROADMAP.md` §9). They therefore have an explicit lifecycle rather than an implicit hope.

| State | Meaning | Transition |
|---|---|---|
| **Active** | Fixture tests pass; listed in the README | → Stale when its fixture test fails and no fix lands within 30 days |
| **Stale** | Known broken; moved to a "known broken" section | → Active on a passing fix; → Removed after 60 days |
| **Removed** | Deleted from the tree | Noted in `CHANGELOG.md` |

A dead adapter is deleted rather than half-maintained. Deleting a broken adapter is not a regression; leaving it in place and letting users hit silent failures is.

**Requirements for a new adapter**

- One adapter covers one platform and one page kind.
- Pure `DOM → CaptureItem` mapping. No network requests, no navigation, no timers, no storage access.
- Ships with an HTML fixture and an expected-output test.
- Documents its selector assumptions in a header comment, so the next person can tell at a glance what the page shape was.
- States its platform Terms-of-Service posture in the PR: what does capturing require beyond a human reading the page?

**External adapters.** The launch adapters live in-tree, but `capture/schema.json` is versioned so an adapter maintained outside this repository can be validated against it and dropped in without a core change. An external adapter stays external until its author donates it; nobody is required to hand over maintenance to get their adapter supported. The tree splits into a community repository once three external adapters exist, at which point the same lifecycle table applies to that repository.

## Importer policy

DabJob imports from other job-search tools because holding state and generating documents are different jobs, and a user should not have to choose one to get the other.

- An importer reads a known external format into the internal model. It ships with a snapshot fixture of that format.
- Import never destroys and never duplicates: rows record their source and importer version, and a re-import is idempotent.
- When an upstream format changes, the importer fails loudly with the field it could not read. A partial silent import is a bug.
- An importer may not become load-bearing. Removing every importer must leave a fully functional application.
- Adding an importer is welcomed; replacing the application with an adapter to one upstream is not.

A feature that exists only because data cannot leave DabJob is rejected. Export is always available.

## Provider policy

- `manual` is the default and is never removed.
- Any provider must be installable without a paid account. `openai-compat` exists precisely so users can point at a local model.
- A provider may never be required by the UI. When none is configured, the app reports `not_configured` and scores on rules alone.
- Providers are selected only by `AGENT_PROVIDER`. No silent auto-detection based on which API keys happen to be in the environment.

## Security

The ingest endpoint is the most sensitive surface in the project (`ROADMAP.md` §9).

- Report vulnerabilities through a GitHub private security advisory. Do not open a public issue.
- In scope: auth bypass, token leakage, Origin-check bypass, SSRF via job URLs, path traversal in export or backup.
- Response targets: acknowledgement within 7 days, fix or documented mitigation within 30.
- Do not test against installations that are not your own.

## Data and privacy

- `data/` holds the database and is never committed.
- Debug bundles are redacted by default: email addresses, phone numbers, messaging IDs, and tokens are stripped. A raw dump must sit behind an explicit flag and print a warning.
- No fixture, example, or test may contain real personal information. Invent it.

## Versioning and migrations

- **Pre-1.0:** breaking changes are allowed and must appear in `CHANGELOG.md`.
- **Post-1.0:** semantic versioning.
- Migrations are forward-only and non-destructive. The documented upgrade path runs `make backup` before `make migrate`.
- The ingest endpoint and `capture/schema.json` are public contracts. Changing either requires a version bump and a migration note.

## Review standards

These are the rules a reviewer applies, published so a contributor can predict the outcome.

**Rule fit first, quality second.** A contribution is judged against §1 scope and §2 invariants before it is judged on execution. Well-built but off-policy work is declined, kindly, with the rule quoted. This direction is deliberate: it is cheaper to decline excellent work for a stated reason than to reinterpret the project every time someone is persuasive.

**Claims get verified on the real path.** A failing test that passes after the fix is necessary but not sufficient — the failing input must be one the application actually produces, not a value the test hand-builds. Importer fixes must be shown against a real export. Parser fixes must be shown against a real posting. A fix whose only demonstration is a synthetic input that the real code path never receives is declined even when its test is green.

**Invited PRs are reserved.** When a maintainer explicitly invites a named contributor to file the PR for a problem that contributor diagnosed or designed, that invitation reserves the implementation for them for seven days, longer if they say they are working on it. A duplicate PR filed inside that window is closed in favour of the invitee's regardless of arrival order or polish. Reviewing, testing, and commenting on an invited PR is encouraged; racing it is not.

**The PR title is the release note.** Pull requests are squash-merged with the title as the entire commit message, and releases are generated from merged titles. Use a Conventional Commits type: `feat` is a minor bump, `type!:` a major one, `fix`/`refactor`/`perf` a patch. Do not edit the changelog by hand.

## Contribution licensing

- Inbound = outbound: all contributions are MIT.
- There is no CLA. Commits carry a `Signed-off-by` line instead (`git commit -s`), per the Developer Certificate of Origin.
- Relicensing requires consent from every contributor. This is why the license was fixed before the first external pull request rather than after.

## Decisions

Design decisions live in `ROADMAP.md` §3 as numbered `D` entries, each with a rationale and a stated consequence. A new decision is a ROADMAP PR that adds an entry.

Discussion in an issue is not a decision. A decision is a paragraph in the ROADMAP with a number. This keeps the reasoning findable two years later instead of buried in a closed thread.

## Changes to this document

Same path as scope: a pull request with a rationale. The never-merge list and the constitutional invariants are intentionally hard to change — a proposal to relax one must argue that the rule is wrong, not that it is inconvenient.
