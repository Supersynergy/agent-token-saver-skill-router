# Spec — Agent Token Saver Skill Router

## Problem

Agents with hundreds of skills often inject the full skill catalog into every fresh system prompt. This burns context, costs money, and can reduce prompt-cache effectiveness.

## Contract

Given a task intent and local skill roots, the router returns a compact selected skill set and a benchmark showing full-catalog vs router-token estimates.

## Supported agents

- Hermes
- Claude Code
- Codex CLI
- OpenCode
- Cursor/Windsurf-compatible skill folders
- repo-local `.agents/skills`

## Non-goals

- Replacing native safety/approval policies.
- Running remote code.
- Requiring a Python package install.

## Verification

```bash
python3 -m py_compile scripts/agent_token_saver.py
python3 -m unittest discover -s tests -v
python3 scripts/agent_token_saver.py bench "debug failing pytest"
```
