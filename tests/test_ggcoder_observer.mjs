import { test } from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import createObserver from "../scripts/ggcoder_observer.mjs";

function fixture(run) {
  const bus = new EventEmitter();
  const context = { eventBus: { on(name, fn) { bus.on(name, fn); return () => bus.off(name, fn); } } };
  const calls = [];
  const extension = createObserver({ python: "/python with spaces", launcher: "/router path", run: run ?? ((...args) => { calls.push(args); return { status: 0 }; }) });
  extension.activate(context);
  return { bus, calls, extension, context };
}

test("pairs starts and ends once, forwards bounded metadata and exit status", () => {
  const { bus, calls, extension } = fixture();
  bus.emit("tool_call_start", { toolCallId: "1", name: "bash", args: { command: "si route test", ignored: "secret" } });
  bus.emit("tool_call_end", { toolCallId: "1", result: "Exit code: 7\nprivate output", isError: false });
  bus.emit("tool_call_end", { toolCallId: "1", result: "duplicate" });
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].slice(0, 2), ["/python with spaces", ["/router path", "observe"]]);
  const payload = JSON.parse(calls[0][2].input);
  assert.equal(payload.tool_response.status, "error");
  assert.equal(calls[0][2].timeout, 1000);
  assert.ok(!calls[0][2].input.includes("private output"));
  assert.ok(!calls[0][2].input.includes("secret"));
  extension.deactivate();
});

test("native skill calls and skill reads are observed, unrelated reads skipped", () => {
  const { bus, calls, extension } = fixture();
  for (const [id, name, args] of [
    ["1", "read", { file_path: "/src/main.py" }],
    ["2", "read", { file_path: "/skills/a/SKILL.md" }],
    ["3", "skill", { skill: "audit" }],
    ["4", "skill", { skill: "missing" }],
  ]) {
    bus.emit("tool_call_start", { toolCallId: id, name, args });
    bus.emit("tool_call_end", { toolCallId: id, result: id === "4" ? "Error: missing" : "ok" });
  }
  assert.equal(calls.length, 3);
  assert.equal(JSON.parse(calls[2][2].input).tool_response.status, "error");
  extension.deactivate();
});

test("SuperGG host is reported explicitly without counting routing as a loaded skill", () => {
  const previous = process.env.AGENT_SKILL_ROUTER_HOST;
  process.env.AGENT_SKILL_ROUTER_HOST = "superggcoder";
  const { bus, calls, extension } = fixture();
  try {
    for (const [id, skill] of [["r", "?find skill"], ["s", "audit"]]) {
      bus.emit("tool_call_start", { toolCallId: id, name: "skill", args: { skill } });
      bus.emit("tool_call_end", { toolCallId: id, result: "ok" });
    }
    assert.equal(calls.length, 1);
    assert.equal(JSON.parse(calls[0][2].input).source, "superggcoder");
  } finally {
    extension.deactivate();
    if (previous === undefined) delete process.env.AGENT_SKILL_ROUTER_HOST;
    else process.env.AGENT_SKILL_ROUTER_HOST = previous;
  }
});

test("activation is idempotent, deactivation unsubscribes, broken observer stays fail-open", () => {
  const { bus, extension, context } = fixture(() => { throw new Error("fixture"); });
  extension.activate(context);
  assert.equal(bus.listenerCount("tool_call_start"), 1);
  bus.emit("tool_call_start", { toolCallId: "a", name: "skill", args: { skill: "audit" } });
  assert.doesNotThrow(() => bus.emit("tool_call_end", { toolCallId: "a", result: "ok" }));
  extension.deactivate();
  assert.equal(bus.listenerCount("tool_call_end"), 0);
});

test("invalid and oversized input is ignored, unfinished calls are bounded", () => {
  const { bus, calls, extension } = fixture();
  for (const event of [null, {}, { toolCallId: "bad", name: "bash", args: [] }, { toolCallId: "long", name: "bash", args: { command: "x".repeat(32769) } }]) {
    assert.doesNotThrow(() => bus.emit("tool_call_start", event));
  }
  for (let i = 0; i < 300; i++) bus.emit("tool_call_start", { toolCallId: String(i), name: "skill", args: { skill: "audit" } });
  bus.emit("tool_call_end", { toolCallId: "0", result: "evicted" });
  assert.equal(calls.length, 0);
  bus.emit("agent_done", {});
  bus.emit("tool_call_end", { toolCallId: "299", result: "cleared" });
  assert.equal(calls.length, 0);
  extension.deactivate();
});
