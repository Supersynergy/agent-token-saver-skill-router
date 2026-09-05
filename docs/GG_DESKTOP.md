# GG and SuperGG desktop

The desktop app runs a bundled `ggnode` and `app-sidecar.mjs`. It does not start
the `sgg` CLI launcher. Install the native observer from this router checkout:

```bash
python3 scripts/agent_token_saver.py install --target ggcoder
```

GG Coder and SuperGGcoder use the same `.gg` home directory. The installer
registers the observer in `.gg/extensions` and preserves other extensions.
After updating an already loaded extension, restart the desktop app: Node caches
its imported module across new chats in the same process.

The observer records successful native skill loads once and excludes failed
loads. It adds no model context and keeps tool results intact. Events distinguish
`superggcoder-app`, `ggcoder-app`, `superggcoder` (CLI) and `ggcoder` (CLI).
App detection uses the sidecar entry path; the `SuperGGcoder.app` bundle name
identifies the custom app. A renamed custom bundle can set
`AGENT_SKILL_ROUTER_HOST=superggcoder` in its launch environment.
Set `AGENT_SKILL_ROUTER_TELEMETRY=0` there to disable observation.

Coding sessions load native extensions. Chat agents that set
`loadExtensions: false` do not load this observer. Subagent tool restrictions
still determine whether they can open skills.

## What reduces context in the app

| Use case | Mechanism | Evidence and boundary |
|---|---|---|
| Long successful test output | Run `ats-verify -- <check>` in native Bash | A 400-line fixture fell from 3,233 to about 218 characters; full log remains available. |
| Failed checks | Same wrapper | Exit code 7 and its decisive diagnostic survived the native desktop tool. No saving is promised for errors. |
| Choosing a skill | Run local `si route "task" --strict --json`, then open the selected skill | Avoids loading unrelated skill bodies when the agent follows this workflow. No desktop task-level percentage established. |
| Native skill catalog | Currently unchanged | Both packaged apps still send the catalog. The CLI's `skill="?task"` convention is unsupported in the app. |
| Observer hooks | Local metadata only | Measures usage; does not compress prompts or establish a token or billing saving. |

`ats-verify` belongs to the companion
[Agent Token Saver](https://github.com/Supersynergy/agent-token-saver) package.
Installing the router does not install ATS or force a model to use the wrapper.
The CLI's compact-catalog percentage must not be applied to desktop sessions.

## Reproduce the desktop backend check

On macOS, with Python and Node on PATH:

```bash
node scripts/ggcoder_desktop_smoke.mjs /path/to/SuperGGcoder.app /path/to/router /path/to/agent-token-saver
```

The test runs the actual packaged sidecar with its embedded Node executable,
an isolated HOME and a deterministic in-process model fixture. It creates a
coding session over HTTP and consumes the same SSE events used by the UI.
It does not open or replace the user's app, read their credentials, or call an
external model. It terminates only its own child process and removes the fixture.

The assertions cover the HTTP token gate, full skill content, one observed
successful load, excluded failed loads, the unsupported CLI query convention,
six native tool completions, retained passing summary, and exit code 7 with its
diagnostic. A changed sidecar hash during the test fails the run.

Verified on a custom SuperGGcoder 0.58.0 bundle and the published GG Coder
[0.59.1 release](https://github.com/KenKaiii/gg-framework/releases/tag/v0.59.1),
both with embedded Node 22.12.0. The JSON output identifies the exact sidecar
hash. This backend test does not automate the GUI or measure paid model quality,
provider tokens, cache accounting, latency savings or billing. Desktop packages
are supplied locally; the ordinary repository CI runs portable contract tests.
