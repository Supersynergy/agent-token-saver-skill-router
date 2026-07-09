# agent-token-saver-skill-router

Universal adaptive skill router for Hermes, Claude Code, Codex CLI, OpenCode, Cursor, Windsurf, and repo-local agents.

It solves one expensive failure mode: loading every available `SKILL.md` into the system prompt. Instead, the agent keeps one tiny router skill hot, scans skill indexes/files cheaply, and lazy-loads only the 0-3 skills that materially help the current task.

## Measured impact

On Maxim's Hermes profile on 2026-07-09:

| Mode | Chars | Est. tokens (`chars/4`) | Lines |
|---|---:|---:|---:|
| Full skill catalog | 74,499 | 18,624 | 1,222 |
| Router-only block | 387 | 96 | 7 |
| Saved | 74,112 | 18,528 | 1,215 |

Reduction: **99.48%** of the skills prompt.

## Install

```bash
git clone https://github.com/Supersynergy/agent-token-saver-skill-router.git
cd agent-token-saver-skill-router
./install.sh all
```

Or one target:

```bash
./install.sh hermes
./install.sh claude
./install.sh codex
```

Manual install locations:

```text
Hermes:      ~/.hermes/skills/metaskills/agent-token-saver-skill-router/SKILL.md
Claude Code: ~/.claude/skills/agent-token-saver-skill-router/SKILL.md
Codex CLI:   ~/.codex/skills/agent-token-saver-skill-router/SKILL.md
Repo-local:  .agents/skills/agent-token-saver-skill-router/SKILL.md
```

## Use

```bash
python3 scripts/agent_token_saver.py route "debug failing pytest in Hermes prompt builder"
python3 scripts/agent_token_saver.py bench "debug failing pytest in Hermes prompt builder"
python3 scripts/agent_token_saver.py install --target all
```

## Adaptive routing policy

1. Keep exactly one router skill hot.
2. Discover candidate skills from cheap metadata first.
3. Score by task words, exact name hits, description hits, and path hints.
4. Show/load at most 3 by default, 5 max.
5. Use native tools for cheap facts; skills only when procedure changes execution.
6. Preserve prompt-cache stability: do not mutate the hot prompt mid-session.
7. Benchmark before/after with the built-in `bench` command.

## Compatibility

The root `SKILL.md` follows the common skill directory shape used by Claude Code, Codex CLI-compatible skill loaders, Hermes, and repo-local `.agents/skills` setups. The script is Python-stdlib only.

## Development

```bash
just test
just bench
```
