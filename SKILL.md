---
name: agent-token-saver-skill-router
description: Use when an agent has many skills/tools/prompts and must cut prompt tokens by routing adaptively. Runs routing outside model context when possible, indexes metadata on disk, lazy-loads one primary plus up to four complementary support skills, and benchmarks savings across agents.
license: MIT
metadata:
  version: 1.7.0
  author: Supersynergy
  hermes:
    tags: [tokens, skills, router, prompt-cache, agent-teams, capsule, claude-code, codex, hermes]
    related_skills: [just-in-time-skill-router, token-budget-advisor]
---

# Agent Token Saver Skill Router

## Overview

Run the helper outside model context when the host supports prompt hooks. Load
this router skill itself only on hosts without that mechanism or when changing
router behavior.

Goal: keep the system prompt tiny, preserve prefix-cache stability, and load only the skills that actually change the next action.

For native hooks, shell-output compression, deterministic projections and the
full measured stack, see https://github.com/Supersynergy/agent-token-saver.
This router is a separate optional skill/CLI; the full-stack installer never
downloads or updates it implicitly.

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

Keep the router out of context when possible. Load everything lazily.

Default load budget:

| Task | Skills to load |
|---|---:|
| Automatic single-phase route | 0-1 |
| Automatic multi-phase route | one primary plus up to four complementary supports |
| Explicit named stack | up to 10 in mention order |
| Production/security/release | one primary skill per phase |
| Broad controller manifest | `--max 10` only when explicitly named |

Stop loading once the next concrete action is clear.

Automatic fuzzy routing stops at five. `10` is the hard ceiling for an explicit
named stack, not a fuzzy-routing default. Keep one primary skill active in a
worker; the controller may reserve support paths for a distinct phase or blocker.
Legacy in-context routing controllers are explicit-only so automatic routing
cannot recurse into another skill loader.

`context-mode` is also explicit-only: it is a heavy session layer, not a
default for ordinary test, log or file tasks. Use `$context-mode` or start a
dedicated heavy session only after deterministic projection is insufficient.
Plain test verification also stays zero-skill; a debugger is selected only
when the request itself asks to debug a failure.

## Universal Discovery Order

Check the cheapest available source first:

1. Explicit `$SkillName` from the user.
2. Canonical cache (`~/.cache/agent-token-saver/skills-index.json`).
3. Grep-friendly `skills.idx` or bounded `SKILL.md` frontmatter.
4. Full `SKILL.md` bodies only for the selected primary/support set.
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
~/.gg/skills
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
   - Frontmatter tags participate in scoring; for debugging/testing work, skills
     under `software-development` outrank unrelated domain tutorials.
5. **Select** zero or one primary workflow skill, then add a support only when
   an independently confident task clause contributes new concrete evidence.
6. **Load** at most five automatic selections. Preserve mention order for a
   pure named stack. In a mixed request, infer the task primary first and append
   naturally named skills as supports.
7. **Execute** with tools.
8. **Benchmark** token savings when changing router behavior.

## Self-Learning Without an Echo Chamber

Every CLI/hook route records a compact event under
`~/.local/state/agent-skill-router/`. The event contains a one-way intent hash,
selected skill names, decision, score, margin and timestamp—never the raw
prompt. `si stats` merges those route counts with actual load/use telemetry
from Claude/Codex `~/.gg/skill-usage*.jsonl` and Hermes
`~/.hermes/skills/.usage.json`.

Automatic learning uses actual application only as a tiny familiarity signal
(maximum +2). Explicit `si feedback <skill> success|failure` is stronger, but
the total adaptive adjustment stays between -6 and +8 and applies only after a
skill already has a positive deterministic content match. Route frequency
itself never improves rank, preventing self-reinforcing popularity loops.
Alias history is aggregated into its canonical skill before ranking, and every
report labels the current evidence window `low`, `medium`, or `high` confidence.

Operational telemetry stays in sidecars. The router never rewrites, archives,
or deletes `SKILL.md` files automatically. Use `si doctor`, `si drift`, and the
complete `si stats --all` report to select review-gated metadata/content
improvements.

Tools use a separate registry and ranking surface. `ghmax` (alias `ghgrep`),
`tilth`, canonical `superweb` (including the old `superscrape`, `smart-fetch`,
`hyperfetch`, `superfetch`, `supersearch`, `feeds-pull`, `batch-md-rs`, and `bulkfetch`
commands), `synxp` (alias `synx`), `rtk`, `grepgod`, `rg`, `just`,
`git`, and other high-leverage local CLIs are never counted as skill loads.
Exact tool names win deterministically; strong pure-tool requests return zero
skills. Codex/Claude PostToolUse and Hermes `post_tool_call` observers store
only canonical tool name, outcome, bounded
latency and timestamp—never the command, arguments, output, or raw prompt. Tool
learning is bounded and cannot create semantic relevance.

Skill suites are not alias maps. The Superweb component skills
`superscrape`, `stealth-research`, `stealth-scraper`, and `scrape-deep` keep
their own exact-name telemetry and feedback while generic multi-step web work
selects `superweb`. Only equivalent executable modes share the canonical tool
ranking.

## Stacks, Subagents, and Processes

- Default: `route "<task>"` returns zero, one primary, or a complementary bundle
  of one primary plus at most four supports.
- Explicit names: `$skill-name` syntax or natural “use A, B, and C” wording
  preserves mention order. `--max 10` permits a named 10-skill manifest; fuzzy
  routing remains capped at five.
- Controller: load only the primary skill needed for its next decision. Hand a
  subagent only its own primary path plus a compact task contract; do not forward
  the controller's full stack or raw catalog.
- Reserve the remaining paths for phase changes (for example implementation →
  release → security review). Load a reserve skill only when it changes the
  next action.
- Explicit references retain their order and can fill all 10 slots. Fuzzy
  support results must cover a distinct phase; score-near alternatives are
  exposed under `consider` and are not loaded.

## Agent teams

Use a controller, not a broad prompt broadcast. Before spawning, define one
independent closed objective and one machine oracle for each lane. A worker
receives a 300–700-token capsule containing evidence paths/hashes, constraints,
one routed skill path at most, three tries at most and a <=500-token return.

Start with no worker for a small overlapping check. Otherwise use at most three
independent workers. The controller receives claim, evidence reference, command
and oracle result—not raw logs or the parent transcript—and totals parent,
children, retries, fallbacks and compactions before accepting the result.

## CLI Helper

If this repo is installed, use the helper:

```bash
si index --refresh
si route "<task>" --strict --json
si find "<keywords>" --limit 8
si resolve <exact-skill-name>
si resolve <legacy-name> --canonical
si aliases --json
si drift --all --json --output /tmp/skill-drift.json
si explain "<task>"
si stats --all --output /tmp/skill-usage.tsv
si feedback <exact-skill-name> success
si tools --all --output /tmp/tool-usage.tsv
si inventory --output /tmp/skill-tool-inventory.json
si tool-feedback ghmax success --latency-ms 850
si install-hooks --target all
si hook-status
si doctor --json
si bench "<task>"
```

Hermes preserves its consent gate: with `hooks_auto_accept: false`, approve the
new observer once on first use. The installer never weakens that global gate.

`si` and `agent-skill-route` are identical entrypoints. No dependencies.
Python stdlib only. The cache TTL defaults to 300 seconds; rebuild after skill
installs or frontmatter edits.

Historical names remain compatibility shims. `si aliases` shows their canonical
responsibility; explicit aliases resolve directly to the canonical skill when
it is installed, and `si stats` aggregates historical applied usage into that
name without double-counting events. Aliases and umbrella routers stay excluded
from automatic fuzzy selection. `si drift` separately reports identical and
divergent active same-name copies without modifying them.

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

- [ ] Router runs outside model context when hooks are available.
- [ ] Full skills remain loadable on demand.
- [ ] `bench` shows before/after token counts.
- [ ] No more than one skill is auto-loaded per normal task or subagent.
- [ ] Team workers are independent, capped at three, and have a machine oracle.
- [ ] Broad controller stacks use at most 10 paths and lazy-load by phase.
- [ ] Production/security/release phase changes still route to the right gate skill.
- [ ] New session/restart confirms prompt-size reduction.
- [ ] Route logs contain hashes and scores, never raw prompts.
- [ ] Learned adjustments cannot create relevance or exceed the bounded range.
