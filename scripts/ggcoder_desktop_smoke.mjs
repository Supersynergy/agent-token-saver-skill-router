// Exercise a packaged desktop sidecar through the HTTP/SSE API used by its UI.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { randomUUID, createHash } from "node:crypto";
import { spawn, execFileSync } from "node:child_process";

const [appRoot, routerRoot, atsRoot] = process.argv.slice(2);
if (!atsRoot) throw new Error("Usage: node ggcoder_desktop_smoke.mjs <App.app> <router-root> <ats-root>");
const temp = await fs.mkdtemp(path.join(os.tmpdir(), "ats-desktop-"));
const home = path.join(temp, "home");
const cwd = path.join(home, "project");
const sidecar = path.join(appRoot, "Contents/Resources/sidecar/app-sidecar.mjs");
const node = path.join(appRoot, "Contents/MacOS/ggnode");
const python = process.env.ROUTER_PYTHON || "python3";
const quote = (value) => `'${value.replaceAll("'", `'"'"'`)}'`;
const sidecarHash = async () => createHash("sha256").update(await fs.readFile(sidecar)).digest("hex");
let child;
let stream;
let stderr = "";
const frames = [];
try {
  await fs.mkdir(cwd, { recursive: true });
  const env = { PATH: process.env.PATH, HOME: home, TMPDIR: temp, GG_APP_PORT: "0", GG_APP_CWD: cwd, GG_APP_TOKEN: randomUUID(), AGENT_SKILL_ROUTER_STATE_DIR: path.join(home, "router-state"), AGENT_SKILL_ROUTER_TELEMETRY: "1" };
  execFileSync(python, [path.join(routerRoot, "scripts/agent_token_saver.py"), "install", "--target", "ggcoder"], { cwd, env, stdio: "pipe" });
  await fs.writeFile(path.join(home, ".gg/auth.json"), JSON.stringify({ openrouter: { accessToken: "fixture-only" } }));
  await fs.writeFile(path.join(home, ".gg/settings.json"), JSON.stringify({ defaultProvider: "openrouter", defaultModel: "qwen/qwen3.6-plus", thinkingEnabled: false }));
  await fs.writeFile(path.join(home, ".gg/skills/ats-desktop-fixture.md"), "---\nname: ats-desktop-fixture\ndescription: Desktop fixture catalog sentinel.\n---\nFULL-DESKTOP-SKILL-BODY\n");
  const fixture = path.join(cwd, "fixture.py");
  await fs.writeFile(fixture, "print('case ok\\n' * 400, end='')\nprint('400 passed in 0.01s')\n");
  const raw = `${quote(python)} ${quote(fixture)}`;
  const compact = `${quote(python)} ${quote(path.join(atsRoot, "integration/cli/ats-verify"))} -- ${raw}`;
  const planned = [
    ["skill-ok", "skill", { skill: "ats-desktop-fixture" }],
    ["skill-missing", "skill", { skill: "missing-desktop-fixture" }],
    ["skill-query", "skill", { skill: "?debug local fixture" }],
    ["raw", "bash", { command: raw }],
    ["compact", "bash", { command: compact }],
    ["failed-check", "bash", { command: `${quote(python)} ${quote(path.join(atsRoot, "integration/cli/ats-verify"))} -- ${quote(python)} -c 'print("decisive failure"); exit(7)'` }],
  ];
  const capture = path.join(home, "provider.json");
  const preload = path.join(home, "fixture-provider.mjs");
  await fs.writeFile(preload, `
import fs from "node:fs";
const captured = [];
globalThis.fetch = async (input, options) => {
  const body = typeof options?.body === "string" ? JSON.parse(options.body) : null;
  if (!body?.messages) throw new Error("Fixture blocks non-model outbound fetch");
  const descriptions = body.tools?.filter(t => t.function.name === "skill") ?? [];
  captured.push({ request_chars: JSON.stringify(body).length, tool_names: body.tools?.map(t=>t.function.name), skill_description_chars: descriptions.reduce((sum,t)=>sum+t.function.description.length,0), desktop_skill_in_catalog: JSON.stringify(body).includes("Desktop fixture catalog sentinel") });
  fs.writeFileSync(${JSON.stringify(capture)}, JSON.stringify(captured));
  const calls = captured.length === 1 ? ${JSON.stringify(planned)} : null;
  const delta = calls ? {role:"assistant",tool_calls:calls.map(([id,name,args],index)=>({index,id,type:"function",function:{name,arguments:JSON.stringify(args)}}))} : {role:"assistant",content:"Desktop fixture complete."};
  const data = [[delta,null],[{},calls?"tool_calls":"stop"]].map(([piece,stop]) => "data: " + JSON.stringify({id:"fixture",object:"chat.completion.chunk",model:"fixture",choices:[{index:0,delta:piece,finish_reason:stop}]}) + "\\n\\n").join("");
  return new Response(data + "data: [DONE]\\n\\n", {headers:{"Content-Type":"text/event-stream"}});
};
`);
  env.NODE_OPTIONS = `--import ${pathToFileURL(preload).href}`;
  const testedHash = await sidecarHash();
  child = spawn(node, [sidecar], { cwd, env, stdio: ["ignore", "pipe", "pipe"] });
  child.stderr.on("data", (chunk) => { stderr = (stderr + chunk).slice(-12000); });
  const port = await new Promise((resolve, reject) => {
    let output = "";
    const timeout = setTimeout(() => reject(new Error("Desktop startup timeout: " + stderr)), 20000);
    child.once("error", (error) => { clearTimeout(timeout); reject(error); });
    child.once("exit", (code) => { clearTimeout(timeout); reject(new Error(`Desktop exit ${code}: ${stderr}`)); });
    child.stdout.on("data", (chunk) => {
      output += chunk;
      const match = /GG_APP_LISTENING (\d+) /.exec(output);
      if (match) { clearTimeout(timeout); resolve(Number(match[1])); }
    });
  });
  const base = `http://127.0.0.1:${port}`;
  const headers = { "x-gg-token": env.GG_APP_TOKEN, "content-type": "application/json" };
  assert.equal((await fetch(base + "/state", { signal: AbortSignal.timeout(10000) })).status, 401, "desktop token gate remains enforced");
  const opened = await fetch(base + "/session", { method: "POST", headers, body: JSON.stringify({ mode: "code", cwd }), signal: AbortSignal.timeout(10000) });
  const session = await opened.json();
  assert.equal(opened.status, 200, JSON.stringify(session));
  assert.equal(typeof session.sessionId, "string");
  headers["x-gg-session"] = session.sessionId;
  const response = await fetch(base + "/events", { headers, signal: AbortSignal.timeout(30000) });
  assert.equal(response.status, 200);
  stream = response.body.getReader();
  let complete;
  let fail;
  const done = new Promise((resolve, reject) => { complete = resolve; fail = reject; });
  const reading = (async () => {
    let buffer = "";
    const decoder = new TextDecoder();
    try {
      while (true) {
        const { value, done: ended } = await stream.read();
        if (ended) { fail(new Error("Desktop SSE closed before run_end")); break; }
        buffer += decoder.decode(value, { stream: true });
        let boundary;
        while ((boundary = buffer.indexOf("\n\n")) >= 0) {
          const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
          const data = /^data: (.+)$/m.exec(frame)?.[1];
          if (!data) continue;
          const parsed = JSON.parse(data);
          const type = parsed.type ?? /^event: (.+)$/m.exec(frame)?.[1];
          const payload = parsed.type ? parsed.data : parsed;
          frames.push({ type, data: payload });
          if (type === "run_end") complete();
          if (type === "error") fail(new Error(JSON.stringify(payload)));
        }
      }
    } catch (error) { fail(error); }
  })();
  const submit = async () => {
    const sent = await fetch(base + "/prompt", { method: "POST", headers, body: JSON.stringify({ text: "Run the deterministic local desktop fixture." }), signal: AbortSignal.timeout(10000) });
    assert.ok(sent.ok, await sent.text());
  };
  await Promise.all([done, submit()]);
  await stream.cancel();
  await reading;
  const ends = frames.filter((event) => event.type === "tool_call_end").map((event) => event.data);
  const byId = (id) => ends.find((event) => event.toolCallId === id);
  assert.equal(ends.length, planned.length);
  assert.match(byId("skill-ok")?.result ?? "", /FULL-DESKTOP-SKILL-BODY/);
  assert.match(byId("skill-missing")?.result ?? "", /not found/);
  assert.match(byId("skill-query")?.result ?? "", /not found/);
  assert.match(byId("compact")?.result ?? "", /400 passed/);
  assert.match(byId("failed-check")?.result ?? "", /^Exit code: 7/);
  assert.match(byId("failed-check").result, /decisive failure/);
  const events = (await fs.readFile(path.join(home, "router-state/events.jsonl"), "utf8")).trim().split("\n").map(JSON.parse);
  const applied = events.filter((event) => event.event === "skill_applied");
  assert.equal(applied.filter((event) => event.skill === "ats-desktop-fixture").length, 1);
  assert.equal(applied.filter((event) => event.skill === "missing-desktop-fixture").length, 0);
  assert.equal(applied.length, 1);
  const source = applied[0].source;
  assert.equal(source, path.basename(appRoot) === "SuperGGcoder.app" ? "superggcoder-app" : "ggcoder-app");
  const requests = JSON.parse(await fs.readFile(capture, "utf8"));
  assert.equal(await sidecarHash(), testedHash, "app changed during the test; rerun against a stable build");
  console.log(JSON.stringify({
    app: path.basename(appRoot), sidecar_sha256: testedHash,
    embedded_node: execFileSync(node, ["--version"], { encoding: "utf8" }).trim(),
    desktop_http_sse: true, token_gate_enforced: true, native_tool_ends: ends.length,
    successful_skill_once: true, failed_skill_not_counted: true, observer_source: source,
    raw_result_chars: byId("raw").result.length, compact_result_chars: byId("compact").result.length,
    native_skill_catalog_present: requests[0].desktop_skill_in_catalog,
    skill_tool_description_chars: requests[0].skill_description_chars,
    cli_skill_query_supported: false, external_model_calls: 0,
    fixture_model_requests: requests.length, provider_savings_verified: false,
  }));
} catch (error) {
  if (stderr) console.error(stderr);
  console.error("Desktop events:", JSON.stringify(frames.slice(-8)));
  throw error;
} finally {
  await stream?.cancel().catch(() => {});
  if (child && child.exitCode === null) {
    const stopped = new Promise((resolve) => child.once("exit", resolve));
    child.kill("SIGTERM");
    const fallback = setTimeout(() => child.kill("SIGKILL"), 3000);
    await stopped;
    clearTimeout(fallback);
  }
  await fs.rm(temp, { recursive: true, force: true });
}
