# Changelog

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
