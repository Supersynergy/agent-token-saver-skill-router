# Save Your Skill Tokens

**Route outside model context. Load zero or one skill only when it helps.**

`agent-token-saver-skill-router` is a universal skill router for Hermes, Claude Code, Codex CLI, GG Coder, OpenCode, Cursor, Windsurf, and repo-local agents. It stops the most common skill-system tax: dumping every `SKILL.md` into every prompt before the agent knows what it needs.

On hook-capable hosts, routing runs outside model context and injects only the
single winning skill pointer. On other hosts, keep one tiny router hot. A
canonical disk index keeps every other skill cold and dynamically resolvable.
Explicit multi-phase workflows may request more paths, but still read one phase
at a time.

Repo: https://github.com/Supersynergy/agent-token-saver-skill-router

Need the complete stack—shell-output compression, deterministic projections,
agent hooks, profiles and end-to-end benchmarks? Use the companion full-stack
repository: https://github.com/Supersynergy/agent-token-saver

---

## Instant install (60 seconds)

Claude Code:

```bash
curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver-skill-router/main/install.sh | bash -s -- claude
```

Codex CLI:

```bash
curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver-skill-router/main/install.sh | bash -s -- codex
```

Everything (Hermes, Claude Code, Codex, GG Coder, OpenCode, repo-local):

```bash
curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver-skill-router/main/install.sh | bash -s -- all
```

Python 3 stdlib only. No package manager, no build step. Uninstall = delete the skill folder.

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

Measured with 459 installed skills (2026-07-13):

| Mode | Chars | Est. tokens (`chars/4`) |
|---|---:|---:|
| Full skill catalog | 148,308 | 37,077 |
| Router result | 357 | 89 |
| Saved | 147,951 | 36,988 |

**Reduction: 99.76% of the routed skill context.** Warm index routing averaged
48.1 ms over 30 runs; forced rebuild averaged 111.9 ms over 10 runs.

> Token estimate uses `chars / 4`. It is intentionally simple, transparent, and model-agnostic.

### Prove it on your machine

These numbers come from one large local skill library. The claim only matters if it survives contact with *your* catalog:

```bash
python3 scripts/agent_token_saver.py bench "your typical task here"
```

Post your `bench` JSON (skills scanned, reduction %, agent used) as a
[benchmark issue](https://github.com/Supersynergy/agent-token-saver-skill-router/issues/new) —
third-party numbers are the proof asset this project wants most.

---

## What it does

1. Reuses a five-minute canonical metadata index when fresh.
2. Streams only bounded `SKILL.md` frontmatter when rebuilding it.
3. Scores skills against the current intent.
4. Returns zero on trivial/ambiguous work, otherwise one winner by default.
5. Lets the agent read only that winning `SKILL.md`.
6. Benchmarks full-catalog vs routed context.

Default policy:

- hook-capable hosts keep the router **outside model context**
- hosts without hooks keep exactly **one** tiny router hot
- load **0–1** skills automatically
- ambiguous routes return **zero**
- keep legacy in-context skill managers explicit-only to avoid router recursion
- allow a **10-path ceiling** only for broad controller stacks
- give each subagent/process only its own **one primary skill** by default
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
si index --refresh
si route "debug failing pytest in Hermes prompt builder" --strict --json
si find "pytest debug" --limit 5
si resolve python-debugpy
si bench "debug failing pytest in Hermes prompt builder"
si route '$security-hardening $release-excellence' --max 2
```

`si` and `agent-skill-route` are the same stdlib CLI. The installer creates
`si` only when that command is free or already belongs to this router.

Tested with:

```text
Python 3.14.6
```

### 3. Canonical cold index

```text
~/.cache/agent-token-saver/skills-index.json
~/.cache/agent-token-saver/skills.idx
```

The JSON file is the machine-readable cache. The TSV file is the grep-friendly
index (`name`, `description`, `path`). Cache TTL defaults to 300 seconds.

```bash
si index                  # reuse if fresh
si index --refresh        # after installing/editing skills
si find "privacy report"  # candidates, no skill body loaded
si resolve dsgvo-shield   # exact path only
```

Overrides: `AGENT_SKILL_INDEX`, `AGENT_SKILL_INDEX_TSV`, and
`AGENT_SKILL_INDEX_TTL`.

### 4. Supports folder skills and flat GG Coder skills

Recognizes:

```text
some-skill/SKILL.md
agent-token-saver-skill-router.md
```

That matters because not every agent stores skills the same way.

### 5. Transparent routing output

Example:

```text
router: agent-token-saver-skill-router
intent: debug failing pytest in Hermes prompt builder
scanned: 459
load:
- python-debugpy: Debug Python programs and failing test runs. (.../SKILL.md)
```

No hidden magic. Automatic routing returns at most one primary skill.

### 6. Built-in proof

Run:

```bash
python3 scripts/agent_token_saver.py bench "your task here"
```

You get:

```json
{
  "skills_scanned": 459,
  "full_est_tokens": 37077,
  "router_est_tokens": 89,
  "saved_est_tokens": 36988,
  "reduction_pct": 99.76
}
```

---

## Install

One-liner (no checkout needed):

```bash
curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver-skill-router/main/install.sh | bash -s -- claude   # or codex / hermes / ggcoder / opencode / repo / all
```

From a checkout:

```bash
git clone https://github.com/Supersynergy/agent-token-saver-skill-router.git
cd agent-token-saver-skill-router
./install.sh all
```

Or use the Python helper directly:

```bash
python3 scripts/agent_token_saver.py install --target all
```

Every target also receives `~/.local/bin/agent-skill-route`. If `si` is free,
it also receives the shorter `~/.local/bin/si` entrypoint.

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
Run the router outside model context when hooks are available.
Use the canonical metadata index.
Load zero or one primary skill automatically.
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

It keeps them available and lazy-loadable. On hosts with router-only mode it
prevents a full catalog from being injected. Codex already exposes skill
metadata progressively; there the strict router is an optional selector, not a
claim that Codex otherwise sends every skill body.

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

Yes. Routes reuse the canonical disk index for 300 seconds by default. Rebuild
with `si index --refresh` after large skill changes; keep the hot prompt
unchanged.

---

## License

MIT
