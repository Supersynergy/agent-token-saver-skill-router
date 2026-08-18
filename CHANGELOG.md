# Changelog

## Unreleased

- Correct the documented Python floor from 3.11+ to **3.9+**, and prove it: the
  code carries `from __future__ import annotations` and uses no 3.10+ syntax, so
  it runs on macOS's built-in `/usr/bin/python3` (3.9.6). CI now runs the suite
  on 3.9 and 3.13 across Linux and macOS, so the claim is verified rather than
  asserted. The previous requirement would have pushed users to install a Python
  they do not need.

- Respect refusal in natural-language routing. "do not use the taste skill"
  carries the same cue (`use`) and the same phrase as a request to load it, so
  the router loaded exactly what the user had just declined — and `--strict`
  did not help, because a natural name takes the explicit path that skips the
  score and margin gates. Negation is now checked at two levels: mention
  detection, and `rank_candidates` as the single choke point for every scoring
  path, so a refused skill cannot return via content score. A cue only negates
  inside its own clause, so "use best practices, not the old approach" still
  loads. Only the refused phrase is dropped, never the surrounding task. A
  `$name` sigil stays a deliberate invocation and is still honoured.
  Verified: labeled 28-case benchmark holds at 28/28 P@1 and jury at 12/12.

## 1.7.0 — 2026-08-18

- `install.sh`: the piped `curl | bash` path cloned into `mktemp -d` and never
  removed it, leaving a full clone behind on every install. It now cleans up on
  exit and fails with a clear message when `python3` or `git` is missing
  instead of erroring out mid-clone. `ATSR_REPO_URL` allows a local source for
  testing.
- CI runs tests and the neutral install on macOS as well as Linux, and covers
  the piped install path from the README, which no job exercised before.
- README states supported OS and runtime requirements, and shows license/CI
  badges.
- Add natural exact-name routing without `$` syntax and automatic bundles of
  one primary plus up to four confidence-gated complementary support skills;
  mixed requests retain the inferred task primary ahead of named supports.
- Add visible `primary`/`support` roles and scored `alternatives` for rejected
  ambiguous routes; keep explicit named stacks capped at 10.
- Expand German normalization and phrase intent for router governance, generic
  runtime diagnosis, GitHub PR review, and landing-page load performance.
- Raise the live 28-case labeled routing benchmark from 26/28 to 28/28 at P@1
  while retaining zero-skill ambiguity gates.
- Add `scripts/si_autotune.py`: hill-climb tuner for the ten scoring weights
  against the labeled eval set; persists only strictly better winners and
  restores previous state otherwise (referenced by `TUNED_DEFAULTS`, now real).
- Routing-quality pass 2026-08-14: eval ground truth repaired and skill tag
  fixes lifted precision@1 from 0.75 to 0.93 and precision@3 to 1.00 on the
  977-skill fleet at unchanged 14.6 ms median latency.
- Add dependency-free `si validate`, `si repair`, and `si smoke` gates based on
  the open Agent Skills format plus the local exact-resolution contract.
- Add atomic safe frontmatter repair with private content backups and dry-run by
  default; no skill scripts are executed during repair.
- Prefer shallow portable copies inside a skill root so nested mirrors cannot
  shadow canonical top-level skills.
- Add optional static Python, shell, and JavaScript syntax checks and document
  the boundary between structural proof and skill-specific live verification.
- Include the canonical runtime-quality gate in `si doctor` and add a German
  full-fleet repair regression to the deterministic routing jury.

## 1.6.2 — 2026-07-15

- Normalize common German web-research verbs, sources, recency, citations,
  crawling, extraction, and download terms before skill and tool scoring.
- Treat summarization as a workflow signal and teach the canonical Superweb
  tool surface about cited source synthesis.
- Add a strict regression proving that a German multi-source research request
  selects the top-level Superweb suite while explicit legacy skill names keep
  their own identity.

## 1.6.1 — 2026-07-15

- Correct Superweb from a flattened skill-alias group to a real suite model:
  `superscrape`, `stealth-research`, `stealth-scraper`, and `scrape-deep` now
  keep independent exact-name routing, usage, and feedback. Only the observed
  `scrapedeep` spelling remains an alias to `scrape-deep`.
- Keep canonical tool aggregation for the eight executable names that really
  delegate to the same Superweb runtime, including the restored `superfetch`
  compatibility command.
- Exclude `backup/`, `backups/`, `_skill-packages/`, and nested
  `related-skills/` trees from discovery so readable suite snapshots and
  packaged references cannot become accidental active skills.

## 1.6.0 — 2026-07-15

- Consolidate `superscrape`, `stealth-research`, `stealth-scraper`,
  `scrape-deep`, and the observed `scrapedeep` spelling into canonical
  `superweb`; exact legacy names now resolve to the canonical skill when it is
  installed.
- Consolidate the old web executables (`superscrape`, `smart-fetch`,
  `hyperfetch`, `supersearch`, `feeds-pull`, `batch-md-rs`, and `bulkfetch`)
  into one truthful `superweb` tool ranking and outcome stream.
- Aggregate alias outcomes before adaptive ranking, while keeping deterministic
  relevance first and the existing bounded tie-breaker.
- Add evidence-window confidence to skill/tool reports and `doctor` so sparse
  telemetry is never presented as mature self-learning.
- Add read-only `si drift` hashing for identical versus divergent active skill
  copies; cleanup stays archive-first and review-gated.
- Improve German/English normalization for diagnose, improvement, update,
  cleanup, merge, and portfolio-review requests.
- Restrict the software-test bonus to debug/failure or platform-specific test
  work, so a portfolio request containing `prüfe` cannot route to TDD.
- Add regressions for canonical web routing, alias learning, command aliases,
  German governance routing, drift classification, and learning confidence.

## 1.5.0 — 2026-07-15

- Keep `agent-efficiency-orchestrator` as an independent, routable workflow-
  efficiency skill instead of canonicalizing it to code-review behavior.
- Preserve independent responsibilities for the weekly skill diary, per-skill
  token optimizer, and explicit offline `skill-autopilot` laboratory.
- Add an auditable skill-alias map plus `aliases` and canonical `resolve`
  surfaces; compatibility shims remain explicit while fuzzy routing selects
  the canonical responsibility.
- Aggregate historical alias telemetry into canonical usage without counting
  events twice or flagging known archived aliases as unknown.
- Exclude deprecated umbrella/domain routers from automatic selection and add
  regressions for canonical usage and explicit-only aliases.

## 1.4.0 — 2026-07-14

- Add a separate installed-tool registry and ranking surface for the lean local
  stack, including canonical aliases such as `ghgrep` → `ghmax` and `synx` →
  `synxp`; tool use never inflates skill application counts.
- Add privacy-safe PostToolUse observation for Codex/Claude and native
  `post_tool_call` observation for Hermes. Logging stores
  canonical tool name, outcome, bounded latency, and timestamp only—never raw
  commands, arguments, output, or prompts.
- Add `tools`, `inventory`, `tool-feedback`, `observe`, `install-hooks`, and `hook-status`.
  Hook installation is append-only, idempotent, preserves existing hooks, and
  does not weaken Hermes consent settings.
- Add bounded outcome/latency learning that cannot create relevance. Exact tool
  names win; decisive pure-tool operations load zero fuzzy skills.
- Add regressions for `ghmax`, aliasing, bounded learning, log privacy, and hook
  preservation/idempotency.

## 1.3.0 — 2026-07-14

- Add privacy-safe route telemetry with one-way intent hashes and no raw prompts.
- Add `stats`, `explain`, `feedback`, and `doctor` commands; merge route counts,
  Claude/Codex skill loads, Hermes usage counters, and explicit outcomes while
  keeping legacy predictions separate from real application.
- Add bounded adaptive ranking: usage is a small tie-breaker, success/failure is
  stronger, and learning can never create relevance for an unrelated skill.
- Keep `skill-autopilot` explicit-only to prevent recursive meta-router routes.
- Add regressions for privacy, complete usage reporting, bounded feedback, and
  the meta-router collision.

## 1.2.4 — 2026-07-14

- Route plain `run tests` verification to zero skills, matching the existing
  zero-skill policy for ordinary test checks.
- Normalize agent-team wording and prefer controller/worker skills over
  Microsoft Teams meeting/calendar integrations for coding-agent intents.
- Add regressions for both routing collisions.

## 1.2.3 — 2026-07-14

- Position the router as a separate optional skill/CLI; the full token-saver
  installer remains independently inspectable and never installs this package.
- Add controller/worker guidance: compact capsules, one routed skill per
  worker, closed oracle, total accounting and a default maximum of three
  independent workers.
- Clarify that `--max 10` is an explicit broad-manifest ceiling, not an
  agent-team default.

## 1.2.2 — 2026-07-14

- Stop the software-development test bonus from selecting a debugger for plain
  test verification. Debug/failure requests retain their relevant boost.
- Add a regression test for zero-skill plain test verification.

## 1.2.1 — 2026-07-14

- Keep `context-mode` explicit-only during fuzzy routing. Its broad trigger
  text no longer loads a full heavy-session handbook for ordinary tests or
  small verification work.
- Add a regression test for automatic rejection plus exact `$context-mode`
  resolution.

## 1.2.0 — 2026-07-13

- Changed automatic routing from three candidates to zero or one primary skill.
- Added a canonical JSON cache plus grep-friendly `skills.idx`, with a 300-second TTL and atomic rebuilds.
- Added `si index`, `si find`, and `si resolve`; preserved unrelated existing `si` commands.
- Streamed bounded frontmatter instead of reading complete skill bodies during discovery.
- Replaced per-skill regex compilation with a bounded string matcher and cached tokenization.
- Reused one catalog snapshot inside `bench` instead of scanning twice.
- Made legacy in-context skill controllers explicit-only to prevent recursive multi-skill routing.
- Changed the Codex prompt hook to parse structured JSON and inject only one compact skill pointer.

## 1.1.0 — 2026-07-13

- Split hyphenated metadata into meaningful routing tokens.
- Added a zero-skill gate for factual and arithmetic prompts.
- Added strict fuzzy routing with an absolute score and ambiguity margin.
- Prevented generic one-word platform names and unrelated favorites from dominating.
- Installed the portable `agent-skill-route` CLI for every target, including GG Coder.
- Added regression coverage for token-stack routing, irrelevant ML/simulation matches, and GG CLI installation.

## 1.0.7 — 2026-07-13

- Prefer security/review skills over a generic web/API match for security-review intents; added a regression test.
- Cross-linked the measured `agent-token-saver` full stack while keeping this router dependency-free.

## 1.0.6 — 2026-07-13

- Fixed live pytest/debug routing: scanner now includes frontmatter tags, normalizes common test/debug inflections, and uses additive coverage rather than an explosive multiplier.
- Demoted generic `builder` noise and added a regression fixture proving Python/testing skills beat unrelated builder and Node-debugger skills.

## 1.0.5 — 2026-07-13

- Raised the explicit stack ceiling from 5 to 10 (`route` and `bench`), while retaining a 3-skill default and enforcing the ceiling inside the Python API as well as the CLI.
- Documented staged controller stacks: keep 1-3 skills active per worker/subagent and reserve the rest for distinct phases or blockers; never broadcast a 10-skill body bundle.
- Added a regression test for ordered explicit 10-skill stacks and out-of-range clamping.

## 1.0.4 — 2026-07-12

- Fixed routing regression: a skill matching several intent tokens now outranks a skill that hit one lucky rare name token (coverage multiplier in `score`; red/green regression test added).
- Made `install.sh` curl-pipeable: `curl -fsSL .../install.sh | bash -s -- claude` clones a shallow temp checkout when run outside the repo.
- README: instant-install one-liners for Claude Code/Codex, fresh 458-skill benchmark (99.39% catalog reduction, 2026-07-12), and a "prove it on your machine" section inviting third-party benchmark issues.

## 1.0.3 — 2026-07-09

- Added user favorites: `~/.agents/skill-favorites.txt` (`name` or `name=weight`) boosts pinned skills on matching intents and marks them `★` in router output; override path via `AGENT_SKILL_FAVORITES_FILE`. Favorites never surface for irrelevant intents.
- Skipped backup/stale skill copies during scan (`*.bak*`, `*-backup`, `*.old`, `*.disabled`, `*-deprecated`) — fixes routing to `.bak-` snapshot dirs.
- Down-weighted generic intent tokens by document frequency so specific matches outrank catalog-wide noise like `cli`.
- Resolved explicit `$SkillName` references exact-match-first, including Codex plugin-cache skills.
- Added `~/.agents/skills` and `~/.codex/plugins/cache` discovery roots; excluded `_archive` and `runs` audit dirs from scan.

## 1.0.2 — 2026-07-09

- Rewrote the GitHub README around the core promise: save skill tokens while keeping skills lazy-loadable.
- Added Humanlove-driven product framing, clearer proof tables, install paths, Hermes setup, FAQ, and development verification.
- Added GG Coder flat `.md` skill discovery to the helper scan path (`~/.gg/skills/*.md`).

## 1.0.1 — 2026-07-09

- Added a native GG Coder install target: `~/.gg/skills/agent-token-saver-skill-router.md`.
- Removed the local Python 3.11 mise pin; the helper is stdlib-only and tested with Python 3.14.

## 1.0.0 — 2026-07-09

- Released `agent-token-saver-skill-router` as a universal adaptive router skill.
- Added Python-stdlib helper for scan, route, install, and benchmark workflows.
- Added install targets for Hermes, Claude Code, Codex CLI, GG Coder, OpenCode, and repo-local `.agents/skills`.
- Added tests and project docs.
