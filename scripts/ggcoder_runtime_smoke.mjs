// Exercise GG's actual session, extension loader and tools using a local test provider.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";

const [ggRoot, routerRoot, atsRoot] = process.argv.slice(2);
if (!ggRoot || !routerRoot || !atsRoot) {
  throw new Error("Usage: node ggcoder_runtime_smoke.mjs <installed-ggcoder-root> <router-root> <ats-root>");
}
const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "ats-ggcoder-smoke-"));
const home = path.join(temporary, "home");
const cwd = path.join(temporary, "project");
await fs.mkdir(home);
await fs.mkdir(cwd);
process.env.HOME = home;
process.env.AGENT_SKILL_ROUTER_STATE_DIR = path.join(home, "router-state");
delete process.env.NODE_OPTIONS;
const python = process.env.ROUTER_PYTHON || "python3";
let session;
let server;
try {
  execFileSync(python, [path.join(routerRoot, "scripts/agent_token_saver.py"), "install", "--target", "ggcoder"], { cwd, stdio: "pipe" });
  const fixtureSkill = path.join(home, ".gg/skills/ats-hook-fixture.md");
  await fs.writeFile(fixtureSkill, "---\nname: ats-hook-fixture\ndescription: Isolated hook test.\n---\nFixture content.\n");
  const fixture = path.join(cwd, "fixture.py");
  await fs.writeFile(fixture, "print('case ok\\n' * 400, end='')\nprint('400 passed in 0.01s')\n");
  const quote = (value) => `'${value.replaceAll("'", `'"'"'`)}'`;
  const rawCommand = `${quote(python)} ${quote(fixture)}`;
  const compactCommand = `${quote(python)} ${quote(path.join(atsRoot, "integration/cli/ats-verify"))} -- ${rawCommand}`;
  const planned = [
    ["skill-ok", "skill", { skill: "ats-hook-fixture" }],
    ["skill-missing", "skill", { skill: "missing-hook-fixture" }],
    ["raw", "bash", { command: rawCommand }],
    ["compact", "bash", { command: compactCommand }],
  ];
  let requests = 0;
  server = createServer(async (req, res) => {
    let body = "";
    for await (const chunk of req) {
      body += chunk;
      if (body.length > 2_000_000) { res.writeHead(413).end(); return; }
    }
    JSON.parse(body);
    requests++;
    const tools = requests === 1 ? planned.map(([id, name, args], index) => ({ index, id, type: "function", function: { name, arguments: JSON.stringify(args) } })) : null;
    const delta = tools ? { role: "assistant", tool_calls: tools } : { role: "assistant", content: "Fixture complete." };
    res.writeHead(200, { "Content-Type": "text/event-stream" });
    for (const [piece, stop] of [[delta, null], [{}, tools ? "tool_calls" : "stop"]]) {
      res.write(`data: ${JSON.stringify({ id: "fixture", object: "chat.completion.chunk", model: "fixture", choices: [{ index: 0, delta: piece, finish_reason: stop }] })}\n\n`);
    }
    res.end("data: [DONE]\n\n");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const baseUrl = `http://127.0.0.1:${server.address().port}/v1`;
  const nativeFetch = globalThis.fetch;
  globalThis.fetch = (input, options) => {
    const url = new URL(typeof input === "string" || input instanceof URL ? input : input.url);
    assert.equal(url.origin, new URL(baseUrl).origin, "test may contact only its local provider");
    return nativeFetch(input, options);
  };
  const { getAppPaths } = await import(pathToFileURL(path.join(ggRoot, "dist/config.js")));
  assert.ok(getAppPaths().agentDir.startsWith(home + path.sep), "GG paths must stay inside the test HOME");
  const { AgentSession } = await import(pathToFileURL(path.join(ggRoot, "dist/core/agent-session.js")));
  const ends = [];
  session = new AgentSession({ provider: "openrouter", model: "fixture", cwd, baseUrl, systemPrompt: "Run the local fixture.", allowedTools: ["skill", "bash"], transient: true, maxTurns: 3, maxTurnExtensions: 0, signal: AbortSignal.timeout(30000) });
  session.eventBus.on("tool_call_end", (event) => ends.push(event));
  await session.initialize();
  assert.ok(session.extensionLoader.getLoaded().some((ext) => ext.name === "agent-skill-router"));
  session.authStorage.resolveCredentials = async () => ({ accessToken: "local-fixture-only", baseUrl });
  await session.prompt("Run the fixture.");
  const events = (await fs.readFile(path.join(home, "router-state/events.jsonl"), "utf8")).trim().split("\n").map(JSON.parse);
  const applied = events.filter((event) => event.event === "skill_applied");
  assert.equal(applied.filter((event) => event.skill === "ats-hook-fixture").length, 1);
  assert.equal(applied.find((event) => event.skill === "ats-hook-fixture").source, "ggcoder");
  assert.equal(applied.filter((event) => event.skill === "missing-hook-fixture").length, 0);
  const raw = ends.find((event) => event.toolCallId === "raw");
  const compact = ends.find((event) => event.toolCallId === "compact");
  assert.ok(raw && compact, "GG must execute both bash arms");
  assert.match(compact.result, /400 passed/);
  assert.ok(compact.result.length < raw.result.length);
  console.log(JSON.stringify({ gg_version: JSON.parse(await fs.readFile(path.join(ggRoot, "package.json"), "utf8")).version, extension_loaded_by_native_session: true, native_tool_ends: ends.length, successful_skill_observed_once: true, failed_skill_not_counted: true, raw_result_chars: raw.result.length, ats_result_chars: compact.result.length, local_provider_requests: requests, external_provider_calls: 0, provider_savings_measured: false }));
} finally {
  await session?.dispose();
  if (server) await new Promise((resolve) => server.close(resolve));
  await fs.rm(temporary, { recursive: true, force: true });
}
