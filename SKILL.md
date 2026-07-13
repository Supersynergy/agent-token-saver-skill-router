---
name: agent-token-saver-skill-router
description: Use when an agent has many skills/tools/prompts and must cut prompt tokens by routing adaptively. Runs routing outside model context when possible, indexes metadata on disk, lazy-loads zero or one primary skill by default, and benchmarks savings across agents.
version: 1.2.0
author: Supersynergy
license: MIT
metadata:
  hermes:
    tags: [tokens, skills, router, prompt-cache, claude-code, codex, hermes]
    related_skills: [just-in-time-skill-router, token-budget-advisor]
---

# Agent Token Saver Skill Router

## Overview

Run the helper outside model context when the host supports prompt hooks. Load
this router skill itself only on hosts without that mechanism or when changing
router behavior.

Goal: keep the system prompt tiny, preserve prefix-cache stability, and load only the skills that actually change the next action.

For native hooks, shell-output compression, deterministic projections and the
full measured stack, see https://github.com/Supersynergy/agent-token-saver.

## When to Use

Use when:

- The agent has a large `SKILL.md` library.
- Startup/system prompts include long skill catalogs.
- The user asks to save tokens, reduce context bloat, route skills, or make skills work across agents.
- You are in Hermes, Claude Code, Codex CLI, OpenCode, Cursor, Windsurf, or a repo-local `.agents/skills` setup.

Do not use for:

- A one-line factual answer where no skill is needed.
- Security/approval gates. Keep those explicit and separate.
- Hiding required safety/compliance instructions.

## Operating Rule

Keep the router out of context when possible. Load everything lazily.

Default load budget:

| Task | Skills to load |
|---|---:|
| Automatic route | 0-1 |
| Explicit multi-domain task | one primary; extra paths stay cold until their phase |
| Production/security/release | one primary skill per phase |
| Broad controller manifest | 4-10 cold paths |

Stop loading once the next concrete action is clear.

`10` is a hard ceiling, not a default. Keep one primary skill active in a
worker; the controller may reserve cold paths for a distinct phase or blocker.
Legacy in-context routing controllers are explicit-only so automatic routing
cannot recurse into another skill loader.

## Universal Discovery Order

Check the cheapest available source first:

1. Explicit `$SkillName` from the user.
2. Canonical cache (`~/.cache/agent-token-saver/skills-index.json`).
3. Grep-friendly `skills.idx` or bounded `SKILL.md` frontmatter.
4. Full `SKILL.md` body only for the single selected winner.
5. External search only if local discovery misses.

Common roots:

```text
./.agents/skills
./.claude/skills
./.codex/skills
~/.agents/skills
~/.hermes/skills
~/.claude/skills
~/.claude/cts/skills
~/.codex/skills
~/.codex/plugins/cache
~/.gg/skills
~/.opencode/skills
~/.cursor/skills
~/.windsurf/skills
```

## Adaptive Routing Loop

1. **Classify** the request: objective, domain, risk, output.
2. **Resolve explicit names first**: `$SkillName` must exact-match before fuzzy scoring, including plugin-cache skills.
3. **Search** candidate skill names/descriptions with 2-5 specific keywords.
4. **Score** candidates:
   - 3 = directly required
   - 2 = materially improves quality/safety
   - 1 = maybe useful later
   - 0 = skip
   - User favorites win close calls; generic tokens (matching many skills) are down-weighted.
   - Frontmatter tags participate in scoring; for debugging/testing work, skills
     under `software-development` outrank unrelated domain tutorials.
5. **Select** zero or one primary workflow skill automatically.
6. **Load** only that winner. Resolve extra paths only after an explicit phase
   change, blocker, or user-named stack.
7. **Execute** with tools.
8. **Benchmark** token savings when changing router behavior.

## Stacks, Subagents, and Processes

- Default: `route "<task>"` returns at most one active skill.
- Broad task: `route "<task>" --max 10` permits an explicit 10-skill manifest.
- Controller: load only the primary skill needed for its next decision. Hand a
  subagent only its own primary path plus a compact task contract; do not forward
  the controller's full stack or raw catalog.
- Reserve the remaining paths for phase changes (for example implementation →
  release → security review). Load a reserve skill only when it changes the
  next action.
- Explicit `$skill-name` references retain their order and can fill all 10
  slots. Fuzzy results remain a shortlist, not an instruction to read ten
  bodies immediately.

## CLI Helper

If this repo is installed, use the helper:

```bash
si index --refresh
si route "<task>" --strict --json
si find "<keywords>" --limit 8
si resolve <exact-skill-name>
si bench "<task>"
```

`si` and `agent-skill-route` are identical entrypoints. No dependencies.
Python stdlib only. The cache TTL defaults to 300 seconds; rebuild after skill
installs or frontmatter edits.

## Favorites & Noise Filter

- **Favorites**: pin your go-to skills in `~/.agents/skill-favorites.txt` — one `name` or `name=weight` per line (default weight 6, `#` comments). Pinned skills get a boost and win close calls, marked `★` in router output. The boost applies only when the skill already matches the intent, so favorites never surface for unrelated tasks. Override the file path with `AGENT_SKILL_FAVORITES_FILE`.
- **Noise filter**: scan skips backup/stale skill copies automatically — dir or flat-file names matching `*.bak*`, `*-backup`, `*.old`, `*.disabled`, `*-deprecated`.
- **Specific beats generic**: intent tokens that match many skills (e.g. `cli`, `app`) are down-weighted by document frequency; rare, specific tokens dominate the ranking.

## Agent-Specific Notes

### Hermes

Best config:

```bash
hermes config set skills.prompt_router_only true
hermes config set skills.router_skill agent-token-saver-skill-router
```

Restart or start a new session so the cached system prompt rebuilds.

### Claude Code

Install to:

```text
~/.claude/skills/agent-token-saver-skill-router/SKILL.md
```

Keep bulky skill families in cold storage when possible. Search indexes first, read full skills only after routing.

### Codex CLI

Install to:

```text
~/.codex/skills/agent-token-saver-skill-router/SKILL.md
```

For repos that prefer portable instructions, also add a short pointer in `AGENTS.md`:

```text
Use agent-token-saver-skill-router first. Do not load broad skill catalogs; route by local SKILL.md frontmatter and lazy-load only selected skills.
```

### GG Coder

Install globally to:

```text
~/.gg/skills/agent-token-saver-skill-router.md
```

For project-local GG Coder use, copy the same file to:

```text
.gg/skills/agent-token-saver-skill-router.md
```

### Repo-local agents

Install to:

```text
.agents/skills/agent-token-saver-skill-router/SKILL.md
```

This makes the router travel with the repository.

## Benchmark Protocol

Use chars/4 as the portable estimate unless a tokenizer is installed.

Report:

- full catalog chars/tokens/lines
- router block chars/tokens/lines
- absolute tokens saved
- percent reduction
- command used

## Pitfalls

1. **Loading umbrella skills for curiosity.** Load only when the task needs the procedure.
2. **Breaking prompt cache mid-session.** Change router config, then start a new session.
3. **Deleting skills instead of de-hotting them.** Cold skills should remain discoverable and loadable.
4. **Routing by names only.** Descriptions catch domain-specific skills with generic names.
5. **Compressing safety away.** Approval, privacy, destructive-command, and outreach gates remain hot when required by policy.

## Verification Checklist

- [ ] Router runs outside model context when hooks are available.
- [ ] Full skills remain loadable on demand.
- [ ] `bench` shows before/after token counts.
- [ ] No more than one skill is auto-loaded per normal task or subagent.
- [ ] Broad controller stacks use at most 10 paths and lazy-load by phase.
- [ ] Production/security/release phase changes still route to the right gate skill.
- [ ] New session/restart confirms prompt-size reduction.
