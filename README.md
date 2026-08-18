# Save Your Skill Tokens

**Your agent reads the few skills the task needs, not forty.**

[![MIT](https://img.shields.io/badge/license-MIT-1c7c54.svg)](LICENSE)
[![CI](https://github.com/Supersynergy/agent-token-saver-skill-router/actions/workflows/ci.yml/badge.svg)](https://github.com/Supersynergy/agent-token-saver-skill-router/actions/workflows/ci.yml)
![Agents](https://img.shields.io/badge/agents-Claude%20%7C%20Codex%20%7C%20Hermes%20%7C%20GG%20Coder%20%7C%20OpenCode-5b5bd6)

Skill systems paste every `SKILL.md` into the prompt before the agent has any idea
which one it needs. You pay for all of them, on every turn.

This router returns none for trivial or ambiguous work, one primary skill for a
single workflow, or up to four complementary support skills for distinct task
phases. The rest stay on disk. Natural requests such as “use Clear Thought and
Systematic Debugging” resolve exact skill names without `$` syntax. In a mixed
request, the task's inferred primary stays first and naturally named skills are
added as supports. Where the host supports hooks, selection happens before the
model is called.

Works with Hermes, Claude Code, Codex CLI, GG Coder, OpenCode, Cursor and Windsurf.
A job with several phases can ask for more, but still reads one phase at a time.

Repo: https://github.com/Supersynergy/agent-token-saver-skill-router

Need the complete stack—shell-output compression, deterministic projections,
agent hooks, profiles and end-to-end benchmarks? Use the companion full-stack
repository: https://github.com/Supersynergy/agent-token-saver

This repository is the optional skill/tool router CLI. It owns local skill
indexing, complementary 0–5 skill routing, compact tool ranking, and its own optional
privacy-safe usage observer. The companion repository owns the broader hook,
ledger, compression, and measured context-saving stack. Neither installer
silently installs the other package.

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

### Requirements

| | |
|---|---|
| **Required** | Python **3.9+**, so macOS's built-in `/usr/bin/python3` is enough. `git` too, but only for the piped `curl \| bash` install above. |
| **OS** | Linux and macOS on Python 3.9 and 3.13, all covered by CI on every push. On Windows use WSL2; the installer is POSIX shell. |
| **Dependencies** | None. Standard library only — no package manager, no build step, no daemon. |

Uninstall = delete the skill folder.

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

Measured with 453 active skill names (2026-07-15):

| Mode | Chars | Est. tokens (`chars/4`) |
|---|---:|---:|
| Full skill catalog | 143,955 | 35,988 |
| Router result | 237 | 59 |
| Saved | 143,718 | 35,929 |

**Reduction: 99.84% of the routed skill context.** Warm index routing averaged
66.5 ms over 20 runs; forced rebuild averaged 134.5 ms over 10 runs. `si drift`
reports physical copy counts separately, while routing indexes one canonical
metadata record per active name.

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
4. Returns zero on trivial/ambiguous work, one primary for a single phase, or a
   confidence-gated bundle for distinct phases.
5. Labels every selected path as `primary` or `support` and caps automatic
   bundles at five.
6. Benchmarks full-catalog vs routed context.
7. Logs privacy-safe route decisions and learns only from bounded usage/outcome signals.
8. Ranks installed high-leverage CLIs separately from skills and observes real
   tool outcomes without storing commands, arguments, output, or prompts.

Default policy:

- hook-capable hosts keep the router **outside model context**
- hosts without hooks keep exactly **one** tiny router hot
- load **0–5** skills automatically: one primary plus only complementary support
- ambiguous routes return **zero**
- keep legacy in-context skill managers explicit-only to avoid router recursion
- allow a **10-path ceiling** only for explicitly named controller stacks
- give each subagent/process only its own **one primary skill** by default
- use tools for cheap facts
- use skills only when procedure changes execution
- preserve prompt-cache stability

### Agent teams: one role per worker

Do not turn a wide task into ten hot skills or ten copies of a parent prompt.
The controller first defines independent lanes and exact PASS/FAIL oracles.
Each worker gets one 300–700-token capsule, path/hash evidence, zero or one
routed skill, at most three tries and a <=500-token evidence-by-reference
result. Start with zero workers for overlapping checks; otherwise cap the team
at three independent workers and account for parent, children, retries,
fallbacks and compactions together.

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
si resolve just-in-time-skill-router --canonical
si aliases --json
si drift --all --json --output /tmp/skill-drift.json
si explain "debug failing pytest in Hermes prompt builder"
si stats --all --output /tmp/skill-usage.tsv
si feedback python-debugpy success
si tools --all --output /tmp/tool-usage.tsv
si inventory --output /tmp/skill-tool-inventory.json
si tool-feedback ghmax success --latency-ms 850
si install-hooks --target all
si hook-status
si doctor --json
si bench "debug failing pytest in Hermes prompt builder"
si route '$security-hardening $release-excellence' --max 2
si route 'Use Clear Thought, Systematic Debugging, Verification Loop, Security Review, and Agent Efficiency Orchestrator' --strict --json
si route 'Research current sources; create a PDF; send it by email; review security; verify the result' --max 5 --strict --json
```

`si` and `agent-skill-route` are the same stdlib CLI. The installer creates
`si` only when that command is free or already belongs to this router.

Tested with:

```text
Python 3.14.6
```

### 3. Privacy-safe self-learning

`si route` stores only an intent hash, selected names, score/margin, decision,
timestamp and route ID. It does not persist raw prompt text. `si stats` merges
router counts with actual Claude/Codex skill-load telemetry and Hermes usage
counters, while keeping legacy ML suggestions separate from real application.

Applied use supplies at most a +2 tie-breaker. Historical alias use is first
rolled into the canonical responsibility. Explicit success/failure feedback
has more weight, but the combined adjustment is clamped to -6…+8 and is ignored
when deterministic metadata has no positive match. Mere route frequency never
trains the router. This prevents a popular wrong skill from training itself to
become more popular.

The router does not auto-edit or auto-delete skills. `si doctor` flags coverage,
malformed telemetry, missing descriptions, unknown observed skills, evidence
confidence, and active copy drift. `si drift --all` distinguishes identical
copies from divergent same-name bodies; content changes remain review-gated.

True compatibility aliases resolve to the canonical skill when it is installed,
while automatic routing chooses that same domain responsibility. Suite
membership alone is not an alias: distinct component procedures keep their own
exact-name usage and outcomes. `si aliases` audits the actual alias map and
`si stats` rolls historical alias usage into canonical totals without counting
one event twice. This preserves evidence when a large legacy skill becomes a
small shim or is archived.

### 4. Separate tool ranking and learning

Skills are procedures; tools are executables. The router keeps their counts
separate. Its bounded registry covers the lean default stack and common local
workhorses, including `ghmax`/`ghgrep`, canonical `superweb` plus its legacy
command aliases (`superscrape`, `smart-fetch`, `hyperfetch`, `superfetch`,
`supersearch`, `feeds-pull`, `batch-md-rs`, `bulkfetch`), `tilth`, `grepgod`,
`synxp`/`synx`, `rtk`, `graphify`, `codegraph`, `freshdocs`, `rg`, `just`,
`git`, `jq`, SQLite, DuckDB, and guarded token-stack helpers.

`si install-hooks --target all` appends idempotent Codex/Claude PostToolUse and
Hermes `post_tool_call` observers without replacing existing hooks. It records only
canonical name, success/failure/unknown, bounded latency, and timestamp. Exact
tool mentions always win; semantic selection requires a confidence floor and
margin. Route frequency never trains rank, and adaptive signals apply only
after deterministic relevance exists.

Hermes keeps its native consent model. If `hooks_auto_accept: false`, approve
the observer once on first use; this installer does not weaken the global gate.

### 5. Canonical cold index

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

### 6. Supports folder skills and flat GG Coder skills

Recognizes:

```text
some-skill/SKILL.md
agent-token-saver-skill-router.md
```

That matters because not every agent stores skills the same way.

### 7. Transparent routing output

Example:

```text
router: agent-token-saver-skill-router
intent: debug failing pytest in Hermes prompt builder
scanned: 459
load:
- python-debugpy: Debug Python programs and failing test runs. (.../SKILL.md)
```

No hidden magic. Automatic routing returns one primary and, only when separate
clauses add confident new work, up to four `support` skills. Weak alternatives
are shown under `consider` instead of being loaded.

### 8. Built-in proof

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
Load zero or one primary skill for a single-phase task. For a genuine
multi-phase task, allow up to four confidence-gated complementary support skills.
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

### Validate and repair the complete skill catalog

```bash
si validate                         # canonical runtime contract
si validate --all-copies --strict   # portable Agent Skills specification
si validate --all-copies --scripts  # static script syntax checks
si repair --all-copies              # dry-run
si repair --all-copies --apply      # atomic edits plus private backups
si index --refresh
si smoke --refresh-index            # exact resolve/invoke for every skill
si doctor --refresh-index --json    # catalog health includes the runtime gate
```

See [`docs/SKILL-QUALITY-FRAMEWORK.md`](docs/SKILL-QUALITY-FRAMEWORK.md) for
the guarantees, severities, and safe-fix boundary.

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
