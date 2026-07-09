# ADR: Universal router as a portable SKILL.md + stdlib helper

Date: 2026-07-09

## Decision

Ship `agent-token-saver-skill-router` as a root `SKILL.md` plus a Python-stdlib CLI helper.

## Rationale

- `SKILL.md` is the widest common denominator across Hermes, Claude Code, Codex-style loaders, and repo-local agents.
- Stdlib Python avoids dependency ownership.
- The helper gives measurable before/after token estimates instead of relying on prose claims.

## Consequences

- Exact tokenizer counts are optional; default estimates use `chars/4`.
- Agent-specific deep integration remains configuration, not core code.
