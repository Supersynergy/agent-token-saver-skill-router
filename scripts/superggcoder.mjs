import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import Module from "node:module";
import { pathToFileURL, fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

export const skillHint = 'Load a skill with skill="name". To find one, use skill="?task description" (local search, zero or one result). Read a returned SKILL.md path if the name is outside this host. No catalog preloading.';
const marker = "/* agent-skill-router:superggcoder */";
const toolAnchors = ["async execute(input) {", "function generateSkillDescription(skills) {"];
const promptAnchor = "export function formatSkillsForPrompt(skills) {";

export function compactCatalog(skills) {
  return skills.reduce((chars, skill) => chars + skill.name.length + (skill.description || "").length + 12, 0) > 2048;
}

export function routeSkill(query, cwd = process.cwd(), run = spawnSync) {
  if (!query.trim() || query.length > 4096) return "Error: give a task description of 1–4096 characters after ?.";
  const launcher = process.env.AGENT_SKILL_ROUTER_LAUNCHER || path.join(os.homedir(), ".local/bin/agent-skill-route");
  try {
    const result = run(launcher, ["route", query, "--strict", "--max", "1", "--json"], {
      cwd, encoding: "utf8", timeout: 4000, maxBuffer: 262144, windowsHide: true,
    });
    if (result.error || result.status !== 0) throw new Error("router unavailable");
    const payload = JSON.parse(result.stdout);
    if (typeof payload.router_block !== "string" || payload.router_block.length > 8192) throw new Error("invalid route");
    return payload.router_block;
  } catch {
    return "Error: local skill routing unavailable. Invoke a known skill name or search local skill files with permitted tools.";
  }
}

export function transform(source, kind, moduleUrl = import.meta.url) {
  const anchors = kind === "tool" ? toolAnchors : [promptAnchor];
  if (source.includes(marker) || anchors.some((anchor) => source.split(anchor).length !== 2)) {
    throw new Error(`unsupported ${kind} source; keeping the native skill catalog`);
  }
  if (kind === "prompt") {
    return `import { compactCatalog as __atsCompact } from ${JSON.stringify(moduleUrl)};\n` + source.replace(promptAnchor, `${promptAnchor}\n    ${marker}\n    if (__atsCompact(skills)) return ${JSON.stringify("## Skills\n\n" + skillHint)};`);
  }
  return `import { routeSkill as __atsRoute, compactCatalog as __atsCompact } from ${JSON.stringify(moduleUrl)};\n` + source
    .replace(toolAnchors[0], `${toolAnchors[0]}\n            ${marker}\n            if (typeof input.skill === "string" && input.skill.startsWith("?")) return __atsRoute(input.skill.slice(1));`)
    .replace(toolAnchors[1], `${toolAnchors[1]}\n    if (__atsCompact(skills)) return ${JSON.stringify(skillHint)};`);
}

export function enable(root, register = Module.registerHooks) {
  if (typeof register !== "function") throw new Error("Node.js 22.15+ with registerHooks is required");
  const realRoot = fs.realpathSync(root);
  const files = new Map([
    [path.join(realRoot, "dist/tools/skill.js"), "tool"],
    [path.join(realRoot, "dist/core/skills.js"), "prompt"],
  ]);
  // Check both surfaces before reducing either catalog. No dist files are written.
  for (const [file, kind] of files) transform(fs.readFileSync(file, "utf8"), kind);
  fs.accessSync(process.env.AGENT_SKILL_ROUTER_LAUNCHER || path.join(os.homedir(), ".local/bin/agent-skill-route"), fs.constants.X_OK);
  const bundled = [path.join(realRoot, "assets/skills"), path.join(realRoot, "dist/skills")].filter((dir) => fs.existsSync(dir));
  if (bundled.length) process.env.AGENT_SKILL_DIRS = [...new Set([...(process.env.AGENT_SKILL_DIRS || "").split(path.delimiter).filter(Boolean), ...bundled])].join(path.delimiter);
  const state = { active: true, root: realRoot, loaded: [] };
  register({
    load(url, context, nextLoad) {
      const result = nextLoad(url, context);
      if (!url.startsWith("file:")) return result;
      const file = fileURLToPath(url);
      const kind = files.get(file);
      if (!kind) return result;
      const source = typeof result.source === "string" ? result.source : Buffer.from(result.source).toString("utf8");
      try {
        const transformed = transform(source, kind, pathToFileURL(fileURLToPath(import.meta.url)).href);
        state.loaded.push(kind);
        return { ...result, source: transformed };
      } catch (error) {
        state.active = false;
        console.error(`[agent-skill-router] ${error.message}`);
        return result;
      }
    },
  });
  return state;
}

if (process.env.SGG_TOKEN_SAVER_ROOT && process.env.SGG_TOKEN_SAVER !== "0" && !globalThis.__SGG_TOKEN_SAVER__) {
  try {
    globalThis.__SGG_TOKEN_SAVER__ = enable(process.env.SGG_TOKEN_SAVER_ROOT);
  } catch (error) {
    console.error(`[agent-skill-router] SuperGG compact catalog disabled: ${error.message}`);
  }
}
