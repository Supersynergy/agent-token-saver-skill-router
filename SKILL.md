---
name: agent-token-saver-skill-router
description: Use when an agent has many skills/tools/prompts and must cut prompt tokens by routing adaptively. Keeps one tiny router hot, discovers candidate skills cheaply, lazy-loads only the smallest useful set, and benchmarks savings across Hermes, Claude Code, Codex CLI, OpenCode, Cursor, Windsurf, and repo-local agents.
version: 1.0.4
author: Supersynergy
license: MIT
metadata:
  hermes:
    tags: [tokens, skills, router, prompt-cache, claude-code, codex, hermes]
    related_skills: [just-in-time-skill-router, token-budget-advisor]
---

# Agent Token Saver Skill Router

## Overview

Use this skill as the always-hot router when the agent can see many skills, tools, prompts, MCP schemas, or command references.

Goal: keep the system prompt tiny, preserve prefix-cache stability, and load only the skills that actually change the next action.

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

Keep one router hot. Load everything else lazily.

Default load budget:

| Task | Skills to load |
|---|---:|
| Simple | 0-1 |
| Normal implementation/debug | 1-3 |
| Production/security/release | 2-4 |
| Maximum | 5 |

Stop loading once the next concrete action is clear.

## Universal Discovery Order

Check the cheapest available source first:

1. Visible hot router metadata.
2. Local index files (`skills.idx`, `skills-catalog.md`, `.usage.json`).
3. `SKILL.md` frontmatter only.
4. Full `SKILL.md` body only for the selected winner(s).
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
5. **Select** the smallest set:
   - 1 primary workflow skill
   - 0-2 domain boosters
   - 0-1 verification/release skill
   - 0-1 safety/compliance skill when risk exists
6. **Load** only selected skills.
7. **Execute** with tools.
8. **Benchmark** token savings when changing router behavior.

## CLI Helper

If this repo is installed, use the helper:

```bash
python3 scripts/agent_token_saver.py route "<task>"
python3 scripts/agent_token_saver.py bench "<task>"
python3 scripts/agent_token_saver.py install --target all
```

No dependencies. Python stdlib only.

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

- [ ] Router is the only hot skill/catalog entry.
- [ ] Full skills remain loadable on demand.
- [ ] `bench` shows before/after token counts.
- [ ] No more than 3 skills are loaded for normal tasks.
- [ ] Production/security/release tasks still load verification/safety skills.
- [ ] New session/restart confirms prompt-size reduction.
