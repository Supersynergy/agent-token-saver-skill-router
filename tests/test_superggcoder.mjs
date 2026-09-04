import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { compactCatalog, enable, routeSkill, transform } from "../scripts/superggcoder.mjs";

test("small catalogs remain native to avoid routing overhead", () => {
  assert.equal(compactCatalog([]), false);
  assert.equal(compactCatalog([{ name: "one", description: "short" }]), false);
  assert.equal(compactCatalog([{ name: "one", description: "x".repeat(3000) }]), true);
});

test("routing is bounded, shell-free and returns only the projected block", () => {
  let calls = 0;
  const run = (file, args, options) => {
    calls++;
    assert.deepEqual(args, ["route", "a task $(no-shell)", "--strict", "--max", "1", "--json"]);
    assert.equal(options.cwd, "/test cwd");
    assert.equal(options.timeout, 4000);
    assert.ok(!options.shell);
    return { status: 0, stdout: JSON.stringify({ router_block: "zero skills", catalog: "private" }) };
  };
  assert.equal(routeSkill("a task $(no-shell)", "/test cwd", run), "zero skills");
  assert.match(routeSkill(" ", "/", run), /^Error:/);
  assert.match(routeSkill("x".repeat(4097), "/", run), /^Error:/);
  assert.equal(calls, 1);
  for (const result of [{ status: 1 }, { status: 0, stdout: "oops" }, { status: 0, stdout: '{"router_block":true}' }]) {
    assert.match(routeSkill("test", "/", () => result), /routing unavailable/);
  }
});

test("only recognized source is transformed and direct skill loading is preserved", () => {
  const tool = 'function generateSkillDescription(skills) { return "catalog"; }\nconst tool = { async execute(input) { return "original " + input.skill; } };';
  const patched = transform(tool, "tool");
  assert.ok(patched.includes('return "original " + input.skill'));
  assert.ok(patched.includes('startsWith("?")'));
  assert.throws(() => transform("drift", "tool"));
  assert.throws(() => transform(tool + tool, "tool"));
  assert.throws(() => transform(patched, "tool"));
});

test("preflight fails before registering either surface when one anchor drifts", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "sgg-ats-test-"));
  try {
    fs.mkdirSync(path.join(root, "dist/tools"), { recursive: true });
    fs.mkdirSync(path.join(root, "dist/core"), { recursive: true });
    fs.writeFileSync(path.join(root, "dist/tools/skill.js"), "async execute(input) { }\nfunction generateSkillDescription(skills) { }");
    fs.writeFileSync(path.join(root, "dist/core/skills.js"), "unsupported changed export");
    let called = false;
    assert.throws(() => enable(root, () => { called = true; }), /unsupported prompt/);
    assert.equal(called, false);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
