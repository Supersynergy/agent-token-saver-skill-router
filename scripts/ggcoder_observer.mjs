import { spawnSync } from "node:child_process";

const MAX_PENDING = 256;
const MAX_INPUT_CHARS = 32768;

function projectCall(event) {
  if (!event || typeof event.toolCallId !== "string") return null;
  const args = event.args;
  if (!args || typeof args !== "object" || Array.isArray(args)) return null;
  if (event.name === "bash" && typeof args.command === "string") {
    if (args.command.length > MAX_INPUT_CHARS) return null;
    return { tool_name: "bash", tool_input: { command: args.command } };
  }
  if (event.name === "skill" && typeof args.skill === "string") {
    if (!/^[a-z0-9][a-z0-9._-]{0,127}$/i.test(args.skill)) return null;
    return { tool_name: "skill", tool_input: { skill: args.skill } };
  }
  if (event.name === "read" && typeof args.file_path === "string") {
    if (args.file_path.length > MAX_INPUT_CHARS) return null;
    if (!/(?:^|\/)SKILL\.md$|(?:^|\/)skills\/[^/]+\.md$/.test(args.file_path)) return null;
    return { tool_name: "read", tool_input: { file_path: args.file_path } };
  }
  return null;
}

export default function createObserver({ python, launcher, run = spawnSync }) {
  const pending = new Map();
  let unsubscribe = [];
  let warned = false;

  function warn() {
    if (!warned) console.error("[agent-skill-router] GG observer unavailable; tool execution continues.");
    warned = true;
  }

  return {
    name: "agent-skill-router",
    version: "1.0.0",
    activate({ eventBus }) {
      if (unsubscribe.length || /^(0|false|no|off)$/i.test(process.env.AGENT_SKILL_ROUTER_TELEMETRY ?? "")) return;
      unsubscribe = [
        eventBus.on("tool_call_start", (event) => {
          const call = projectCall(event);
          if (!call) return;
          if (pending.size >= MAX_PENDING) pending.delete(pending.keys().next().value);
          pending.set(event.toolCallId, { call, started: performance.now() });
        }),
        eventBus.on("tool_call_end", (event) => {
          if (!event || typeof event.toolCallId !== "string") return;
          const item = pending.get(event.toolCallId);
          pending.delete(event.toolCallId);
          if (!item) return;
          const result = typeof event.result === "string" ? event.result : "";
          const exit = /^Exit code: ([^\n]+)/.exec(result);
          const failed = event.isError === true || /^Error:/.test(result) || (exit && exit[1].trim() !== "0");
          const payload = {
            ...item.call,
            source: process.env.AGENT_SKILL_ROUTER_HOST === "superggcoder" ? "superggcoder" : "ggcoder",
            tool_response: { status: failed ? "error" : "success" },
            duration_ms: Math.round(performance.now() - item.started),
          };
          try {
            // Synchronous, bounded delivery also survives GG's one-shot JSON exit.
            const observed = run(python, [launcher, "observe"], {
              input: JSON.stringify(payload), encoding: "utf8", timeout: 1000,
              maxBuffer: 8192, windowsHide: true,
            });
            if (observed.error || observed.status !== 0) warn();
          } catch {
            warn();
          }
        }),
        eventBus.on("agent_done", () => pending.clear()),
      ];
    },
    deactivate() {
      for (const off of unsubscribe) off();
      unsubscribe = [];
      pending.clear();
    },
  };
}
