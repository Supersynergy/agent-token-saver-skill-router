# Spec — Agent Token Saver Skill Router

## Problem

Agents with hundreds of skills often inject the full skill catalog into every fresh system prompt. This burns context, costs money, distracts the model, and weakens prompt-cache efficiency.

## Contract

Given a task intent and local skill roots, the router returns:

1. a compact selected skill set,
2. a visible router block,
3. a benchmark comparing full-catalog vs router-token estimates.

The default selected set is at most 3. The CLI permits up to 10 paths via
`--max 10` for a broad controller stack; 10 is a hard ceiling. A controller
loads skills lazily by phase and gives each subagent only its own 1-3 active
skill paths, never the whole stack by default.

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
