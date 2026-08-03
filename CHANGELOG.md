# Changelog

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
