# Changelog

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
