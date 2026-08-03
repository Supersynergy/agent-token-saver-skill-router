# Gitstars Radar — 2026-07-13

Decision rule: no tool enters the default Codex prompt path unless it reduces
measured context or tool calls against the existing lean stack: RTK, Synapse,
the skill router, and Tilth. Star momentum is discovery evidence, not adoption
evidence.

| Candidate | Gitstars signal | Decision | Reason |
| --- | --- | --- | --- |
| [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) | Rising Star; v0.2.0 released 2026-07-02 | Watch, then offline A/B | Its validation-gated skill evolution fits this project's test-first model. It is younger than the 14-day install gate and must never mutate live skills without held-out evals. Its deployed artifact adds no inference-time calls. |
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | Trending Today | Heavy-profile benchmark only | Promising static SQLite graph binary, but its 14 MCP tools are a permanent schema cost if globally enabled. Compare it with Graphify/CodeGraph on repeated large repositories only. |
| [TencentDB-Agent-Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) | Rising Star | Reject default | Duplicates the live Synapse socket-backed local-memory path. No replacement without a measured recall-quality and latency win. |
| [thecodacus/understory](https://github.com/thecodacus/understory) | Rising Star | Reject default | Another MCP/local-memory graph; overlaps Synapse and adds a schema/runtime surface. |
| [mattpocock/skills](https://github.com/mattpocock/skills) | Rising Star | Curate only | Useful discovery catalog, but importing it wholesale would undo adaptive routing and add a large, low-signal skill inventory. |

## Current maximum-lean state

- Default Codex MCP surface: Tilth only.
- Browser, graph, and REPL tooling: heavy/on-demand only.
- Prompt hook: strict one-skill routing for fuzzy requests; direct token-stack
  requests map to `token-stack-operations`.
- Memory: Synapse socket/CLI, not an always-on MCP.

## Next admissible experiment

After 2026-07-16, run SkillOpt only against a copied skill plus a held-out
router-evaluation fixture. Keep an optimized artifact only if it improves route
accuracy without increasing the hot prompt beyond the existing router budget.
