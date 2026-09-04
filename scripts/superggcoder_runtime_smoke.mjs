// Run the real sgg launcher and native tool loop with an in-process test provider.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const [launcher, superRoot, routerRoot, atsRoot] = process.argv.slice(2);
if (!atsRoot) throw new Error("Usage: node superggcoder_runtime_smoke.mjs <sgg-launcher> <supergg-root> <router-root> <ats-root>");
const temporary = await fs.mkdtemp(path.join(os.tmpdir(), "ats-supergg-smoke-"));
const python = process.env.ROUTER_PYTHON || "python3";
const quote = (value) => `'${value.replaceAll("'", `'"'"'`)}'`;
const results = [];
try {
  for (const lean of [false, true]) {
    const home = path.join(temporary, lean ? "lean" : "baseline");
    const cwd = path.join(home, "project");
    const localLauncher = path.join(home, ".local/bin/sgg");
    await fs.mkdir(path.dirname(localLauncher), { recursive: true });
    await fs.mkdir(cwd);
    await fs.mkdir(path.join(home, "projects"));
    await fs.symlink(superRoot, path.join(home, "projects/superggcoder"));
    await fs.copyFile(launcher, localLauncher);
    await fs.chmod(localLauncher, 0o755);
    const env = { ...process.env, HOME: home, NODE_OPTIONS: "", SGG_NOPATCH: "1", SGG_NOSHIELD: "1", GGCODER_HEAP_MB: "4096", SGG_TOKEN_SAVER: lean ? "1" : "0", AGENT_SKILL_ROUTER_TELEMETRY: "1", AGENT_SKILL_ROUTER_STATE_DIR: path.join(home, "state") };
    env.PATH = path.dirname(process.execPath) + path.delimiter + (process.env.PATH || "");
    delete env.AGENT_SKILL_ROUTER_LAUNCHER;
    execFileSync(python, [path.join(routerRoot, "scripts/install_superggcoder.py"), "--launcher", localLauncher], { cwd, env, stdio: "pipe" });
    await fs.writeFile(path.join(home, ".gg/auth.json"), JSON.stringify({ openrouter: { accessToken: "local-fixture-only" } }));
    for (let i = 0; i < 100; i++) {
      const name = i === 0 ? "ats-hook-fixture" : `fixture-${i}`;
      await fs.writeFile(path.join(home, `.gg/skills/${name}.md`), `---\nname: ${name}\ndescription: Catalog sentinel ${i}. ${"Targeted local verification fixture. ".repeat(5)}\n---\nFULL-SKILL-BODY-${i}\n`);
    }
    execFileSync(path.join(home, ".local/bin/agent-skill-route"), ["index", "--refresh", "--json"], { cwd, env, stdio: "pipe" });
    const fixture = path.join(cwd, "fixture.py");
    await fs.writeFile(fixture, "print('case ok\\n' * 400, end='')\nprint('400 passed in 0.01s')\n");
    const raw = `${quote(python)} ${quote(fixture)}`;
    const compact = `${quote(python)} ${quote(path.join(atsRoot, "integration/cli/ats-verify"))} -- ${raw}`;
    const planned = [
      ["skill-ok", "skill", { skill: "ats-hook-fixture" }],
      ["skill-missing", "skill", { skill: "missing-hook-fixture" }],
      ["raw", "bash", { command: raw }],
      ["compact", "bash", { command: compact }],
      ["failed-check", "bash", { command: `${quote(python)} ${quote(path.join(atsRoot, "integration/cli/ats-verify"))} -- ${quote(python)} -c 'print("decisive failure"); exit(7)'` }],
    ];
    const traceFile = path.join(home, "requests.json");
    const preload = path.join(home, "fixture-provider.mjs");
    await fs.writeFile(preload, `
import fs from "node:fs";
const requests = [];
const planned = ${JSON.stringify(planned)};
globalThis.fetch = async (input, options) => {
  const body = JSON.parse(options.body);
  if (!body.messages || !body.tools) throw new Error("Unexpected fixture transport request");
  const n = requests.length;
  const skill = body.tools.find(t => t.function.name === "skill");
  requests.push({ skill_description_chars: skill.function.description.length,
    system_chars: JSON.stringify(body.messages.filter(m => m.role === "system")).length,
    request_chars: JSON.stringify(body).length,
    catalog_present: JSON.stringify(body).includes("Catalog sentinel"),
    tool_names: body.tools.map(t => t.function.name), state: globalThis.__SGG_TOKEN_SAVER__ ?? null });
  fs.writeFileSync(${JSON.stringify(traceFile)}, JSON.stringify(requests));
  const route = [["route", "skill", {skill:"?ats-hook-fixture"}]];
  const calls = ${lean} && n === 0 ? route : n === (${lean} ? 1 : 0) ? planned : null;
  const delta = calls ? {role:"assistant",tool_calls:calls.map(([id,name,args],index)=>({index,id,type:"function",function:{name,arguments:JSON.stringify(args)}}))} : {role:"assistant",content:"Fixture complete."};
  const chunks = [[delta,null],[{},calls?"tool_calls":"stop"]].map(([piece,stop]) => "data: " + JSON.stringify({id:"fixture",object:"chat.completion.chunk",model:"fixture",choices:[{index:0,delta:piece,finish_reason:stop}]}) + "\\n\\n").join("");
  return new Response(chunks + "data: [DONE]\\n\\n", {headers:{"Content-Type":"text/event-stream"}});
};
`);
    env.NODE_OPTIONS = `--import ${pathToFileURL(preload).href}`;
    const output = execFileSync(localLauncher, ["--json", "Run the fixture.", "--provider", "openrouter", "--model", "fixture"], { cwd, env, encoding: "utf8", timeout: 45000, maxBuffer: 2000000 });
    const native = output.trim().split("\n").filter((line) => line.startsWith("{")).map(JSON.parse);
    const ends = native.filter((event) => event.type === "tool_call_end");
    const byId = (id) => ends.find((event) => event.toolCallId === id);
    assert.match(byId("skill-ok").result, /FULL-SKILL-BODY-0/);
    assert.match(byId("compact").result, /400 passed/);
    assert.match(byId("failed-check").result, /^Exit code: 7/);
    assert.match(byId("failed-check").result, /decisive failure/);
    const telemetry = (await fs.readFile(path.join(home, "state/events.jsonl"), "utf8")).trim().split("\n").map(JSON.parse);
    const applied = telemetry.filter((event) => event.event === "skill_applied");
    assert.equal(applied.filter((event) => event.skill === "ats-hook-fixture").length, 1);
    assert.equal(applied.find((event) => event.skill === "ats-hook-fixture").source, "superggcoder");
    assert.equal(applied.filter((event) => event.skill === "missing-hook-fixture").length, 0);
    const requests = JSON.parse(await fs.readFile(traceFile, "utf8"));
    assert.equal(requests[0].catalog_present, !lean);
    if (lean) {
      assert.ok(requests[0].state.loaded.includes("tool") && requests[0].state.loaded.includes("prompt"));
      assert.match(byId("route").result, /ats-hook-fixture/);
    }
    results.push({ lean, requests: requests.length, first_request: requests[0], total_request_chars: requests.reduce((sum, req) => sum + req.request_chars, 0), raw_result_chars: byId("raw").result.length, ats_result_chars: byId("compact").result.length, route_result_chars: lean ? byId("route").result.length : 0, native_tool_ends: ends.length });
  }
  assert.deepEqual(results[0].first_request.tool_names, results[1].first_request.tool_names);
  assert.ok(results[1].first_request.request_chars < results[0].first_request.request_chars);
  assert.ok(results[1].total_request_chars < results[0].total_request_chars);
  for (const result of results) { delete result.first_request.tool_names; if (result.first_request.state) delete result.first_request.state.root; }
  console.log(JSON.stringify({ native_sgg_launcher: true, fixture_skills: 100, preserved_native_tool_set: true, skill_success_once: true, failed_skill_not_counted: true, failed_check_exit_preserved: true, external_provider_calls: 0, provider_savings_measured: false, arms: results }));
} finally {
  await fs.rm(temporary, { recursive: true, force: true });
}
