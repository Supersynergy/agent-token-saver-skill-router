# Skill quality framework

`si` uses two contracts:

1. **Portable format:** the open Agent Skills specification. A portable skill is
   `<name>/SKILL.md` with first-position YAML frontmatter, a valid `name`, a
   non-empty `description`, and optional `scripts/`, `references/`, and `assets/`.
2. **Local runtime:** every indexed name must resolve to one readable canonical
   path and explicit invocation must return that skill or its declared alias.

The checks are mechanical. They do not score a skill's politics, ethics, tone,
business model, or domain opinion.

## Gates

```bash
# Runtime-compatible validation of the canonical catalog
si validate

# Full portable-spec report for every active copy
si validate --all-copies --strict --json

# Also parse Python and syntax-check shell/JavaScript under scripts/
si validate --all-copies --scripts --json

# Preview or apply only deterministic frontmatter repairs
si repair --all-copies
si repair --all-copies --apply

# Rebuild, exact-resolve, and explicitly invoke every canonical indexed skill
si index --refresh
si smoke --refresh-index
si doctor --refresh-index --json
```

`doctor` includes a compact canonical quality summary and fails when the
runtime contract has an error.

`repair` is dry-run by default. `--apply` writes atomically, preserves each
file's mode, and creates a private backup plus manifest under
`~/.local/state/agent-skill-router/skill-repair-backups/`.

## Safe automatic repairs

- move a valid embedded frontmatter block to byte zero while preserving its
  preamble in the body;
- add minimal frontmatter to a plain Markdown skill;
- add a missing name from the directory or flat-file name;
- add a missing description from the first useful body paragraph;
- quote YAML scalars whose colons or argument-hint syntax make them invalid.

The repair command does not rename directories, merge divergent skills, split
long manuals, rewrite procedures, install dependencies, or execute skill
scripts. Those operations need a separate reviewed change.

## Severity

Default validation is the local runtime gate. Legacy flat files, name-directory
mismatches, cross-skill links, and non-portable names remain visible warnings if
the indexer can still resolve them. `--strict` promotes specification violations
to errors. Missing frontmatter, missing required metadata, unreadable files,
broken declared `scripts/`/`references/`/`assets/` paths, and syntax failures are
errors in both modes.

Static validation proves structure and parseability. It does not prove that an
external API is available, credentials are valid, a browser session is logged
in, or a domain workflow produces a correct real-world result. Those require
skill-specific fixtures or live smoke tests.
