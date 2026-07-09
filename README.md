# Save Your Skill Tokens

**Keep one tiny router hot. Load the right skill only when it actually helps.**

`agent-token-saver-skill-router` is a universal skill router for Hermes, Claude Code, Codex CLI, GG Coder, OpenCode, Cursor, Windsurf, and repo-local agents. It stops the most common skill-system tax: dumping every `SKILL.md` into every prompt before the agent knows what it needs.

Instead, your agent starts with one small routing skill, scans cheap metadata, and lazy-loads only the 0–3 skills that materially improve the current task.

Repo: https://github.com/Supersynergy/agent-token-saver-skill-router

---

## Why people love it

Agents feel smarter when they are not drowning in context.

This router makes skill systems feel fast, calm, and under control:

- **Less anxiety:** no mystery 30k-token skill blob hidden in every run.
- **More agency:** you can see exactly which skills were selected and why.
- **Faster first win:** the agent starts light, then loads only the useful procedure.
- **More trust:** built-in `bench` shows before/after token cost with real local skills.
- **No lock-in:** one `SKILL.md`, one stdlib Python helper, portable paths.

Humanlove principle: users do not love more features. They love software that reduces uncertainty, gives control, creates progress, and preserves identity. This router does that for agents.

---

## Measured impact

### Hermes hot-prompt measurement

Measured on Maxim's Hermes profile, 2026-07-09:

| Mode | Chars | Est. tokens (`chars/4`) | Lines |
|---|---:|---:|---:|
| Full Hermes skills prompt | 55,216 | 13,804 | 936 |
| Router-only block | 392 | 98 | 7 |
| Saved | 54,824 | 13,706 | 929 |

**Reduction: 99.29% of the Hermes skills prompt.**

### Universal local skill-library benchmark

Measured with 422 installed skills:

| Mode | Chars | Est. tokens (`chars/4`) |
|---|---:|---:|
| Full skill catalog | 135,475 | 33,868 |
| Router result | 908 | 227 |
| Saved | 134,567 | 33,641 |

**Reduction: 99.33% of the routed skill context.**

> Token estimate uses `chars / 4`. It is intentionally simple, transparent, and model-agnostic.

---

## What it does

1. Scans common skill folders.
2. Reads only frontmatter metadata first.
3. Scores skills against the current intent.
4. Selects the smallest useful set.
5. Prints a tiny router block.
6. Lets the agent lazy-load those skills with its native loader.
7. Benchmarks full-catalog vs router-only cost.

Default policy:

- keep exactly **one** router skill hot
- load **0–3** skills normally
- allow **5 max** when the task is broad
- use tools for cheap facts
- use skills only when procedure changes execution
- preserve prompt-cache stability

---

## Best features

### 1. Universal install targets

```bash
./install.sh hermes
./install.sh claude
./install.sh codex
./install.sh ggcoder
./install.sh opencode
./install.sh repo
./install.sh all
```

Manual locations:

```text
Hermes:      ~/.hermes/skills/metaskills/agent-token-saver-skill-router/SKILL.md
Claude Code: ~/.claude/skills/agent-token-saver-skill-router/SKILL.md
Codex CLI:   ~/.codex/skills/agent-token-saver-skill-router/SKILL.md
GG Coder:    ~/.gg/skills/agent-token-saver-skill-router.md
OpenCode:    ~/.opencode/skills/agent-token-saver-skill-router/SKILL.md
Repo-local:  .agents/skills/agent-token-saver-skill-router/SKILL.md
```

### 2. Stdlib-only helper

No package manager. No npm. No node_modules. No Cargo build. No venv.

```bash
python3 scripts/agent_token_saver.py route "debug failing pytest in Hermes prompt builder"
python3 scripts/agent_token_saver.py bench "debug failing pytest in Hermes prompt builder"
python3 scripts/agent_token_saver.py scan --json
```

Tested with:

```text
Python 3.14.4
```

### 3. Supports folder skills and flat GG Coder skills

Recognizes:

```text
some-skill/SKILL.md
agent-token-saver-skill-router.md
```

That matters because not every agent stores skills the same way.

### 4. Transparent routing output

Example:

```text
router: agent-token-saver-skill-router
intent: debug failing pytest in Hermes prompt builder
scanned: 417
load:
- hermes-agent: Configure, extend, or contribute to Hermes Agent. (.../SKILL.md)
- ad-hoc-verification: Use when code was changed but no canonical test command is available. (.../SKILL.md)
```

No hidden magic. The agent sees the shortlist and loads only what helps.

### 5. Built-in proof

Run:

```bash
python3 scripts/agent_token_saver.py bench "your task here"
```

You get:

```json
{
  "skills_scanned": 422,
  "full_est_tokens": 33868,
  "router_est_tokens": 227,
  "saved_est_tokens": 33641,
  "reduction_pct": 99.33
}
```

---

## Install

```bash
git clone https://github.com/Supersynergy/agent-token-saver-skill-router.git
cd agent-token-saver-skill-router
./install.sh all
```

Or use the Python helper directly:

```bash
python3 scripts/agent_token_saver.py install --target all
```

Dry-run first:

```bash
python3 scripts/agent_token_saver.py install --target all --dry-run
```

---

## Hermes setup

Hermes can keep only this router in the hot system prompt:

```bash
hermes config set skills.prompt_router_only true
hermes config set skills.router_skill agent-token-saver-skill-router
```

Then start a new session:

```text
/new
```

The other skills stay enabled and searchable. They are just not injected into every prompt.

That is the point:

```text
enabled != hot
```

Enabled means available for lazy loading.
Hot means paid for on every request.

---

## Claude Code / Codex / GG Coder usage

Put the skill where your agent expects skills, then use this policy:

```text
Start with agent-token-saver-skill-router.
Scan skill metadata cheaply.
Load only the 0–3 skills that materially help this task.
Use tools for cheap facts.
Do not load the full skill catalog into the prompt.
```

For repo-local projects:

```bash
python3 scripts/agent_token_saver.py install --target repo
```

That writes:

```text
.agents/skills/agent-token-saver-skill-router/SKILL.md
```

---

## Example routes from real local skills

These are the kind of selections the router produces from a large local skill library:

| Intent | Expected selected skill type |
|---|---|
| `make this README lovable and high-converting` | `humanlove`, copy/product UX skills |
| `debug failing pytest in Hermes prompt builder` | Hermes + verification skills |
| `prepare GitHub release with changelog and tag` | release workflow skills |
| `audit desktop markdown rendering bug` | frontend/testing/debugging skills |
| `route a task with too many possible skills` | metaskill/router skills |

The goal is not to always pick the same skill. The goal is to stop paying for every skill when only a few are useful.

---

## Design principles

### Via negativa

Do not load what you do not need.

### Zero friction

One file, one tiny helper, no dependencies.

### Force multiplier

Works across agent ecosystems instead of solving the same problem five times.

### Compounding

Every benchmark teaches you how expensive your skill library really is.

### Trust

Selection is visible. Token savings are measurable. Install paths are explicit.

---

## Development

```bash
python3 -m py_compile scripts/agent_token_saver.py
python3 -m unittest discover -s tests -v
python3 scripts/agent_token_saver.py bench "debug failing pytest in Hermes prompt builder"
```

With `just`:

```bash
just test
just bench
```

---

## FAQ

### Does this delete or disable my other skills?

No.

It keeps them available and lazy-loadable. It only prevents the full catalog from being injected into every prompt.

### Why Python?

Because this tool should be boring and universal.

- stdlib only
- no build step
- no dependency supply chain
- easy for agents to inspect and patch
- available on almost every developer machine

Go or Rust may be useful for a future single-binary v2. For this v1 router, Python is the lowest-friction correct choice.

### Is this a tokenizer?

No.

It uses `chars / 4` as a stable estimate. The point is not exact billing. The point is comparing full catalog vs router block under the same estimate.

### Will this work with thousands of skills?

Yes for metadata-first routing. For very large libraries, add a cached index later. Keep the hot prompt unchanged.

---

## License

MIT
