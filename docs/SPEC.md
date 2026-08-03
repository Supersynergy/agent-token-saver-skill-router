# Spec — Agent Token Saver Skill Router

## Problem

Agents with hundreds of skills often inject the full skill catalog into every fresh system prompt. This burns context, costs money, distracts the model, and weakens prompt-cache efficiency.

## Contract

Given a task intent and local skill roots, the router returns:

1. a compact selected skill set,
2. a visible router block,
3. zero or one separately ranked installed tool recommendation,
4. a benchmark comparing full-catalog vs router-token estimates.

The automatic selected set is zero or one primary skill. The CLI permits up to
10 cold paths via explicit `--max 10` for a broad controller manifest; 10 is a
hard ceiling. A controller loads one skill per phase and gives each subagent
only its own primary skill path, never the whole manifest.

Every CLI/hook route appends privacy-safe decision telemetry containing an
intent hash but no raw prompt. Usage reports merge router selections with
actual Claude/Codex loads and Hermes use counters. Adaptive ranking uses only a
bounded application/outcome adjustment after deterministic relevance is
positive; selection frequency never trains selection.

Historical compatibility names map to a canonical responsibility. Exact alias
requests resolve directly to the canonical skill when it is installed; aliases
remain excluded from automatic fuzzy routing. Reports retain raw per-skill rows
and separately aggregate canonical usage, so archive/merge work preserves
history without double counting. Adaptive ranking uses the same canonical
aggregate and reports `low`, `medium`, or `high` evidence confidence.
A suite relationship is not a compatibility alias: independently useful
component procedures keep exact-name routing and outcome telemetry.

Tool routing is a separate contract. A curated registry resolves executable
availability and aliases (`ghgrep` → `ghmax`, `synx` → `synxp`, legacy web
commands → `superweb`), scores exact
mentions before semantic matches, and returns no recommendation below its
confidence/margin gates. A decisive pure-tool operation suppresses fuzzy skill
loading. Observers append to existing Codex/Claude PostToolUse and Hermes
`post_tool_call` hook config and
persist only canonical name, outcome, bounded latency, and timestamp. They
never store raw command text, arguments, output, or prompts. Actual tool use
and outcomes provide a bounded tie-breaker only after positive deterministic
relevance; recommendation frequency never trains ranking.
Hermes hook consent remains controlled by `hooks_auto_accept`; installation
does not change it.

Portfolio drift is a read-only contract. `si drift` scans every active copy,
hashes bodies, and distinguishes identical duplication from divergent same-name
skills. It never edits, archives, or deletes a skill.

For an agent team, a controller starts with zero workers and spawns at most
three independent lanes only when each has a closed machine oracle. A worker
gets a 300–700-token evidence-by-reference capsule, one primary skill at most,
three tries at most and a <=500-token result. The accounting scope is parent,
children, retries, fallbacks and compactions together.

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
- Automatically rewriting, deleting, or archiving user-authored skills.
- Inventing a SKILL.md wrapper for every executable or treating tool use as a
  skill application.

## Verification

```bash
python3 -m py_compile scripts/agent_token_saver.py
python3 -m unittest discover -s tests -v
python3 scripts/agent_token_saver.py bench "debug failing pytest"
```
