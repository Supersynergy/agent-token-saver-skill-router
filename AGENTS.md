# Agent Token Saver Skill Router

Use `agent-token-saver-skill-router` before loading broad skill catalogs.

Rules:
- Keep one router hot.
- Lazy-load only 0-3 task-relevant skills by default.
- Use `python3 scripts/agent_token_saver.py bench "<task>"` after router changes.
- Verify with `python3 -m unittest discover -s tests -v`.
- Keep this repo dependency-free unless a measured token-saving gain justifies ownership.
