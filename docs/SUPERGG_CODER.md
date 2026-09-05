# SuperGG Coder: compact skills and measured output

This page covers the `sgg` CLI launcher. The desktop `.app` starts its own
bundled Node sidecar and does not run that launcher. See
[GG and SuperGG desktop](GG_DESKTOP.md) for the native app observer and tests.

SuperGG's `sgg` launcher can keep a large skill catalog out of the model request.
The existing native `skill` tool gains a local search convention:

- `{"skill":"?debug a failing pytest"}` returns zero or one routing result.
- `{"skill":"known-skill-name"}` loads the complete skill as before.
- A result outside GG's catalog provides its file path for an allowed read tool.

Both copies of the descriptions (system prompt and skill-tool schema) become a
short pointer when the catalog exceeds 2,048 characters. Small catalogs stay
native. The tool set and existing tool execution rules remain in place.
Project `.gg/skills` participates in routing before global roots. Bundled skills
under the runtime's `assets/skills` or `dist/skills` are also indexed.

## Install into an existing sgg launcher

Requires an installed SuperGG runtime, Node.js with `module.registerHooks`
(22.15+; validated on 24 and 26), and Python 3.9+. From this router checkout:

```bash
python3 scripts/install_superggcoder.py --dry-run
python3 scripts/install_superggcoder.py
si index --refresh
```

Use `--launcher /path/to/sgg` for another location. The installer recognizes the
existing `exec node $V8_FLAGS "$REAL" "$@"` launcher and refuses unknown shapes.
It installs the native observer, copies the runtime helper, saves a hash-named
launcher backup and adds one managed block. Repeating it is idempotent.

The helper changes the two modules in memory. It never edits GG's `dist` files.
It verifies both source anchors before activation. Unsupported versions retain
their native catalog and print a diagnostic. Other loader transformations are
preserved; a later conflicting transform also produces a diagnostic.

`SGG_TOKEN_SAVER=0 sgg` disables compact skills for a run. To remove the launcher
integration, restore the backup path printed by the installer. The native GG
observer remains independently controlled by `AGENT_SKILL_ROUTER_TELEMETRY=0`.
Existing sessions must be restarted to pick up the new module and tool schema.

## Hooks and savings are separate

The native observer records successful skill loads with `source: superggcoder`.
Failed loads and search-only calls do not count as applied skills. It sends
bounded metadata to the local router and never inserts a prompt message.
Observer failures do not reject or alter tool execution.

Use `ats-verify -- <check>` through the native Bash tool for long check output.
It retains a passing verdict and the full log path; a failing check keeps its
exit code and diagnostics. That command belongs to the companion ATS package.
Installing this router does not silently install ATS.

## Reproduce the runtime check

```bash
node scripts/superggcoder_runtime_smoke.mjs /path/to/sgg /path/to/superggcoder /path/to/router /path/to/agent-token-saver
```

The test copies the real launcher into two temporary HOME directories and runs
its installed, patched GG runtime. A deterministic in-process provider sends
native tool calls. No external model is called. Autopatching and the user's
separate adapter are disabled inside the fixture; existing runtime patches are
still present. This does not test the interactive UI or a paid model's choices.

With 100 fixture skills, the baseline sent 81,878 characters on its first request
and the compact arm sent 35,942. Across the whole fixture it sent 170,551 versus
115,853 characters, including the compact arm's extra search request: 32.1%
less request text. The skill search result itself was 403 characters. The native
Bash result for a 400-line passing check fell from 3,233 to 199 characters.
Exact lengths can vary with temporary paths and platform.

The oracle checks full skill content, one successful observed load, exclusion of
a failed load, the same native tool set, a retained passing summary and a failing
check's exit code 7 plus decisive diagnostic. These are local character measures.
They do not establish provider-token, billing, model-quality or latency savings.
An additional routing request can cost time; already-known skill names need no
search. Compare the entire task before claiming a net saving.
