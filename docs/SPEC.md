# Spec — Agent Token Saver Skill Router

## Problem

Agents with hundreds of skills often inject the full skill catalog into every fresh system prompt. This burns context, costs money, distracts the model, and weakens prompt-cache efficiency.

## Contract

Given a task intent and local skill roots, the router returns:

1. a compact selected skill set,
2. a visible router block,
3. a benchmark comparing full-catalog vs router-token estimates.

The automatic selected set is zero or one primary skill. The CLI permits up to
10 cold paths via explicit `--max 10` for a broad controller manifest; 10 is a
hard ceiling. A controller loads one skill per phase and gives each subagent
only its own primary skill path, never the whole manifest.

## Supported agents

- Hermes
- Claude Code
- Codex CLI
- GG Coder
- OpenCode
- Cursor/Windsurf-compatible skill folders
- repo-local `.agents/skills`

## Skill shapes

The scanner supports both common skill formats:

```text
skill-name/SKILL.md
skill-name.md
```

Flat `.md` support is required for GG Coder-style skill folders.

## Root discovery

Default scan roots:

1. repo `.agents/skills`
2. repo `.claude/skills`
3. repo `.codex/skills`
4. `~/.hermes/skills`
5. `~/.claude/skills`
6. `~/.claude/cts/skills`
7. `~/.codex/skills`
8. `~/.gg/skills`
9. `~/.opencode/skills`
10. `~/.cursor/skills`
11. `~/.windsurf/skills`
12. `AGENT_SKILL_DIRS`

## Non-goals

- Replacing native safety/approval policies.
- Running remote code.
- Requiring a Python package install.
- Exact tokenizer billing for every model.

## Verification

```bash
python3 -m py_compile scripts/agent_token_saver.py
python3 -m unittest discover -s tests -v
python3 scripts/agent_token_saver.py bench "debug failing pytest"
```
