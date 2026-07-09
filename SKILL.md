---
name: agent-token-saver-skill-router
description: Use when an agent has many skills/tools/prompts and must cut prompt tokens by routing adaptively. Keeps one tiny router hot, discovers candidate skills cheaply, lazy-loads only the smallest useful set, and benchmarks savings across Hermes, Claude Code, Codex CLI, OpenCode, Cursor, Windsurf, and repo-local agents.
version: 1.0.0
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
~/.hermes/skills
~/.claude/skills
~/.claude/cts/skills
~/.codex/skills
~/.opencode/skills
~/.cursor/skills
~/.windsurf/skills
```

## Adaptive Routing Loop

1. **Classify** the request: objective, domain, risk, output.
2. **Search** candidate skill names/descriptions with 2-5 specific keywords.
3. **Score** candidates:
   - 3 = directly required
   - 2 = materially improves quality/safety
   - 1 = maybe useful later
   - 0 = skip
4. **Select** the smallest set:
   - 1 primary workflow skill
   - 0-2 domain boosters
   - 0-1 verification/release skill
   - 0-1 safety/compliance skill when risk exists
5. **Load** only selected skills.
6. **Execute** with tools.
7. **Benchmark** token savings when changing router behavior.

## CLI Helper

If this repo is installed, use the helper:

```bash
python3 scripts/agent_token_saver.py route "<task>"
python3 scripts/agent_token_saver.py bench "<task>"
python3 scripts/agent_token_saver.py install --target all
```

No dependencies. Python stdlib only.

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
