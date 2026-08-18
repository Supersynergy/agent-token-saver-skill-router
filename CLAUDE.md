# Agent Token Saver Skill Router

Run `si` outside model context before loading any skill body.

Rules:
- Automatic routing loads zero or one primary skill for a single phase; a
  genuine multi-phase task may add up to four complementary support skills.
- Keep only a tiny router pointer hot on hosts without prompt hooks.
- Use `si bench "<task>"` after router changes.
- Run `si index --refresh` after installing or editing skills.
- Verify with `python3 -m unittest discover -s tests -v`.
- Keep this repo dependency-free unless a measured token-saving gain justifies ownership.
