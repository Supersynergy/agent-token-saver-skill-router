import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "agent_token_saver", ROOT / "scripts" / "agent_token_saver.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def write_skill(base: Path, name: str, desc: str, tags: str = ""):
    d = base / name
    d.mkdir(parents=True)
    metadata = f"\nmetadata:\n  hermes:\n    tags: [{tags}]" if tags else ""
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}{metadata}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def write_flat_skill(base: Path, name: str, desc: str):
    base.mkdir(parents=True, exist_ok=True)
    (base / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8"
    )


class AgentTokenSaverTests(unittest.TestCase):
    def test_route_selects_relevant_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "python-testing",
                "Use when running pytest and debugging failing Python tests.",
            )
            write_skill(root, "copywriting", "Use when writing sales copy.")

            result = mod.route("debug failing pytest", roots=[root])

            self.assertEqual(result.scanned, 2)
            self.assertEqual([s.name for s in result.selected], ["python-testing"])
            self.assertIn("python-testing", result.router_block)

    def test_simple_factual_or_arithmetic_prompt_loads_no_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "plus-pro", "Build advanced plus workflows.")
            write_skill(root, "fact-search", "Search facts on the web.")

            arithmetic = mod.route("What is 2 plus 2?", roots=[root])
            factual = mod.route("Capital of France?", roots=[root])

            self.assertEqual(arithmetic.selected, [])
            self.assertEqual(factual.selected, [])

    def test_strict_route_rejects_ambiguous_top_scores(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "release-a", "Review and release a repository.")
            write_skill(root, "release-b", "Review and release a repository.")

            result = mod.route("review and release this repo", roots=[root], strict=True)

            self.assertEqual(result.selected, [])

    def test_multi_token_match_beats_single_rare_name_token(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "freedom-builder",
                "Builder for cooperative wealth vehicles.",
            )
            write_skill(
                root,
                "python-testing",
                "Debug failing pytest runs and flaky tests.",
            )

            result = mod.route("debug failing pytest in prompt builder", roots=[root])

            self.assertEqual(result.selected[0].name, "python-testing")

    def test_route_ignores_stopwords_and_substring_name_hits(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "si", "Skill Indexer for searching and managing skills.")
            write_skill(
                root,
                "humanlove",
                "Use for human psychology, lovable product UX, conversion, onboarding, trust, and retention.",
            )

            result = mod.route(
                "make this README lovable and high converting using human psychology",
                roots=[root],
            )

            self.assertEqual(result.selected[0].name, "humanlove")
            self.assertNotEqual(result.selected[0].name, "si")

    def test_explicit_skill_name_beats_fuzzy_matches(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "pdf", "Read, create, and verify PDF files.")
            write_skill(
                root,
                "md2report",
                "Convert markdown reports into interactive PDF reports.",
            )
            write_skill(
                root, "dsgvo-report", "Create privacy-safe business reports and PDFs."
            )

            result = mod.route("$pdf", roots=[root])

            self.assertEqual([s.name for s in result.selected], ["pdf"])

    def test_stack_allows_ten_explicit_skills_but_caps_higher_requests(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            names = [f"skill-{i}" for i in range(12)]
            for name in names:
                write_skill(root, name, f"Use {name} for this workflow.")

            prompt = " ".join(f"${name}" for name in names)
            result = mod.route(prompt, max_selected=99, roots=[root])

            self.assertEqual([s.name for s in result.selected], names[:10])
            self.assertEqual(mod.selection_limit(0), 1)
            self.assertEqual(mod.selection_limit(99), 10)

    def test_legacy_meta_routers_are_explicit_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "just-in-time-skill-router",
                "Route and combine skills for debugging failing Python tests.",
            )
            write_skill(
                root,
                "sm",
                "Skill manager that routes debugging and failing Python tests.",
            )
            write_skill(root, "python-debug", "Debug failing Python tests.")

            automatic = mod.route("debug failing Python tests", roots=[root])
            explicit = mod.route(
                "$just-in-time-skill-router $sm", max_selected=2, roots=[root]
            )

            self.assertEqual([s.name for s in automatic.selected], ["python-debug"])
            self.assertEqual(
                [s.name for s in explicit.selected],
                ["just-in-time-skill-router", "sm"],
            )

    def test_tags_and_normalized_testing_terms_beat_generic_builder(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            software = root / "software-development"
            write_skill(
                root,
                "wealth-builder",
                "Build cooperative wealth vehicles for friends.",
            )
            write_skill(
                root,
                "hermes-atropos-environments",
                "Build, test, and debug Hermes RL environments.",
                "atropos, rl, training",
            )
            write_skill(
                software,
                "python-debugpy",
                "Debug Python programs with pdb.",
                "debugging, python",
            )
            write_skill(
                software,
                "test-driven-development",
                "Use red-green-refactor before code.",
                "testing, tdd",
            )
            write_skill(
                software,
                "systematic-debugging",
                "Find root causes before fixing bugs.",
                "debugging, troubleshooting",
            )
            write_skill(
                software,
                "node-inspect-debugger",
                "Debug Node.js programs.",
                "debugging, nodejs",
            )

            result = mod.route(
                "debug failing pytest in Hermes prompt builder",
                max_selected=3,
                roots=[root],
            )

            self.assertCountEqual(
                [s.name for s in result.selected],
                ["python-debugpy", "systematic-debugging", "test-driven-development"],
            )

    def test_security_review_beats_generic_web_api_match(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "superweb",
                "Search and scrape web APIs and current documentation.",
                "web, search, api",
            )
            write_skill(
                root,
                "requesting-code-review",
                "Review code changes, security, and regression risk before release.",
                "review, regression",
            )
            write_skill(
                root,
                "security-hardening",
                "Audit authentication and authorization for OWASP vulnerabilities.",
                "security, auth, owasp",
            )
            favorites = Path(td) / "favorites.txt"
            favorites.write_text("superweb=8\n", encoding="utf-8")

            with patch.dict(
                os.environ, {"AGENT_SKILL_FAVORITES_FILE": str(favorites)}
            ):
                result = mod.route(
                    "review Python API auth bug for security and regressions",
                    max_selected=2,
                    roots=[root],
                )

            names = [skill.name for skill in result.selected]
            self.assertCountEqual(
                names[:2], ["security-hardening", "requesting-code-review"]
            )
            self.assertNotIn("superweb", names)

    def test_common_roots_include_codex_plugin_cache(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            plugin_root = (
                home
                / ".codex"
                / "plugins"
                / "cache"
                / "runtime"
                / "pdf"
                / "1"
                / "skills"
            )
            write_skill(plugin_root, "pdf", "Read, create, and verify PDF files.")
            with patch.dict(os.environ, {"HOME": str(home)}):
                roots = mod.common_roots(Path(td) / "cwd")
                skills = mod.scan(roots)

            self.assertIn((home / ".codex" / "plugins" / "cache").resolve(), roots)
            self.assertIn("pdf", [skill.name for skill in skills])

    def test_common_roots_include_global_agents_skills(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            agents_root = home / ".agents" / "skills"
            write_skill(
                agents_root, "frontend-design", "Create production frontend interfaces."
            )
            with patch.dict(os.environ, {"HOME": str(home)}):
                roots = mod.common_roots(Path(td) / "cwd")
                result = mod.route("$frontend-design", roots=roots)

            self.assertIn(agents_root.resolve(), roots)
            self.assertEqual(
                [skill.name for skill in result.selected], ["frontend-design"]
            )

    def test_scan_skips_audit_runs_and_archives(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "live-skill", "Use this live skill.")
            write_skill(
                root / "metareview" / "runs", "snapshot-skill", "Audit snapshot only."
            )
            write_skill(root / "_archive", "archived-skill", "Archived skill only.")

            names = [skill.name for skill in mod.scan([root])]

            self.assertEqual(names, ["live-skill"])

    def test_bench_reports_reduction_with_temp_home(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            home = base / "home"
            cwd = base / "cwd"
            cwd.mkdir()
            root = home / ".claude" / "skills"
            gg_root = home / ".gg" / "skills"
            write_skill(
                root,
                "python-testing",
                "Use when running pytest and debugging failing Python tests.",
            )
            write_skill(root, "copywriting", "Use when writing sales copy.")
            write_flat_skill(
                gg_root,
                "humanlove",
                "Use when making software lovable, trustworthy, and easy to keep using.",
            )
            old_cwd = Path.cwd()
            try:
                os.chdir(cwd)
                with patch.dict(os.environ, {"HOME": str(home)}):
                    report = mod.bench("debug pytest")
                    names = [s.name for s in mod.scan()]
            finally:
                os.chdir(old_cwd)

            self.assertEqual(report["skills_scanned"], 3)
            self.assertIn("humanlove", names)
            self.assertGreater(report["full_est_tokens"], 0)
            self.assertGreater(report["router_est_tokens"], 0)
            self.assertEqual(report["selected"][0]["name"], "python-testing")

    def test_default_fuzzy_route_loads_exactly_one_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "python-debug", "Debug failing Python tests.")
            write_skill(root, "test-workflow", "Test and debug Python code.")

            result = mod.route("debug failing Python tests", roots=[root])

            self.assertEqual(len(result.selected), 1)

    def test_index_cache_is_reused_until_refresh(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "skills"
            index = base / "cache" / "skills-index.json"
            write_skill(root, "python-testing", "First description for Python tests.")

            with patch.dict(
                os.environ,
                {
                    "AGENT_SKILL_INDEX": str(index),
                    "AGENT_SKILL_INDEX_TTL": "3600",
                },
            ):
                first = mod.load_catalog([root], use_index=True)
                (root / "python-testing" / "SKILL.md").write_text(
                    "---\nname: python-testing\n"
                    "description: Second description after refresh.\n---\n",
                    encoding="utf-8",
                )
                cached = mod.load_catalog([root], use_index=True)
                refreshed = mod.load_catalog([root], use_index=True, refresh=True)

            self.assertEqual(first.source, "rebuilt")
            self.assertEqual(cached.source, "cache")
            self.assertIn("First description", cached.skills[0].description)
            self.assertEqual(refreshed.source, "rebuilt")
            self.assertIn("Second description", refreshed.skills[0].description)
            self.assertTrue(index.is_file())
            self.assertTrue((index.parent / "skills.idx").is_file())

    def test_malformed_index_fails_open_and_rebuilds(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "skills"
            index = base / "skills-index.json"
            write_skill(root, "release-pro", "Release repositories safely.")
            index.write_text("{broken", encoding="utf-8")

            with patch.dict(os.environ, {"AGENT_SKILL_INDEX": str(index)}):
                catalog = mod.load_catalog([root], use_index=True)

            self.assertEqual(catalog.source, "rebuilt")
            self.assertEqual([skill.name for skill in catalog.skills], ["release-pro"])

    def test_find_and_resolve_use_metadata_without_loading_skill_body(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "python-testing", "Debug failing pytest suites.")
            write_skill(root, "copywriting", "Write sales copy.")
            skills = mod.scan([root])

            matches = mod.find_skills("pytest debug", skills, limit=1)
            resolved = mod.resolve_skill("$python-testing", skills)

            self.assertEqual(matches[0][1].name, "python-testing")
            self.assertEqual(resolved.name, "python-testing")

    def test_scan_skips_backup_and_bak_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "release-pro", "Use when releasing repos.")
            for noise in (
                "release-pro.bak-2026-06-06",
                "scraper-0.1.7-backup",
                "helper.old",
            ):
                d = root / noise
                d.mkdir(parents=True)
                (d / "SKILL.md").write_text(
                    f"---\nname: {noise}\ndescription: stale copy\n---\n",
                    encoding="utf-8",
                )

            names = [skill.name for skill in mod.scan([root])]

            self.assertEqual(names, ["release-pro"])

    def test_favorites_win_close_calls_but_never_surface_irrelevant(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "generic-release", "Publish repos and releases.")
            write_skill(root, "repo-release-excellence", "Publish repos and releases.")
            write_skill(root, "suno-creator", "Create songs with suno.")
            fav = Path(td) / "favs.txt"
            fav.write_text(
                "repo-release-excellence=8\nsuno-creator=8\n", encoding="utf-8"
            )

            with patch.dict(os.environ, {"AGENT_SKILL_FAVORITES_FILE": str(fav)}):
                result = mod.route("release this repo", roots=[root])

            self.assertEqual(result.selected[0].name, "repo-release-excellence")
            self.assertIn("repo-release-excellence ★", result.router_block)
            self.assertNotIn("suno-creator", [s.name for s in result.selected])

    def test_generic_tokens_downweighted_by_doc_frequency(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root, "rust-release", "Release Rust binaries with readme polish."
            )
            for i in range(9):
                write_skill(root, f"cli-tool-{i}", "A cli helper for anything.")
            fav = Path(td) / "no-favs.txt"

            with patch.dict(os.environ, {"AGENT_SKILL_FAVORITES_FILE": str(fav)}):
                result = mod.route("release rust cli with readme polish", roots=[root])

            self.assertEqual(result.selected[0].name, "rust-release")

    def test_token_stack_beats_platform_and_unrelated_favorite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "token-stack-operations",
                "Audit token-saving and context-saving stacks across Codex. Covers noisy tool output, Synapse memory, skills, and subagents.",
                "tokens, context, memory, synapse, routing",
            )
            write_skill(
                root,
                "codex",
                "Delegate coding to OpenAI Codex CLI for features and PRs.",
                "coding, codex",
            )
            write_skill(
                root,
                "swarmfish",
                "Run prediction simulations with many Codex subagents and produce output.",
                "simulation, forecast",
            )
            write_skill(
                root,
                "peft-fine-tuning",
                "Optimize model memory and accuracy with parameter-efficient fine tuning.",
                "memory, optimization, training",
            )
            fav = Path(td) / "favs.txt"
            fav.write_text("swarmfish=8\n", encoding="utf-8")

            with patch.dict(os.environ, {"AGENT_SKILL_FAVORITES_FILE": str(fav)}):
                result = mod.route(
                    "optimize Codex subagents, Synapse memory, token context, and noisy tool outputs",
                    roots=[root],
                )

            self.assertEqual(result.selected[0].name, "token-stack-operations")
            self.assertNotIn("codex", [s.name for s in result.selected])
            self.assertNotEqual(result.selected[0].name, "swarmfish")
            self.assertNotIn("peft-fine-tuning", [s.name for s in result.selected])

    def test_token_stack_audit_beats_generic_goal_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "goalmaster",
                "Formulate, refine, audit, and run long-running goals.",
                "goal, audit, planning",
            )
            write_skill(
                root,
                "token-stack-operations",
                "Audit token-saving context stacks across Codex with routing, Synapse, and lean MCP defaults.",
                "token, saving, stack, context, routing, synapse",
            )

            result = mod.route("audit Codex token saving stack", roots=[root])

            self.assertEqual(result.selected[0].name, "token-stack-operations")

    def test_install_dry_run_lists_targets(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"HOME": td}):
                written = mod.install("all", dry_run=True)

            self.assertTrue(any(".hermes" in p for p in written))
            self.assertTrue(any(".claude" in p for p in written))
            self.assertTrue(any(".codex" in p for p in written))
            self.assertTrue(any(".gg" in p for p in written))
            self.assertTrue(any(p.endswith("agent-skill-route") for p in written))
            self.assertTrue(any(p.endswith("/si") for p in written))

    def test_ggcoder_install_also_writes_global_router_cli(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"HOME": td}):
                written = mod.install("ggcoder")

            launcher = Path(td) / ".local" / "bin" / "agent-skill-route"
            indexer = Path(td) / ".local" / "bin" / "si"
            self.assertIn(str(launcher), written)
            self.assertTrue(launcher.is_file())
            self.assertTrue(os.access(launcher, os.X_OK))
            self.assertIn(str(indexer), written)
            self.assertTrue(os.access(indexer, os.X_OK))

    def test_install_never_overwrites_an_unrelated_si_command(self):
        with tempfile.TemporaryDirectory() as td:
            indexer = Path(td) / ".local" / "bin" / "si"
            indexer.parent.mkdir(parents=True)
            indexer.write_text("foreign command\n", encoding="utf-8")

            with patch.dict(os.environ, {"HOME": td}):
                written = mod.install("ggcoder")

            self.assertNotIn(str(indexer), written)
            self.assertEqual(indexer.read_text(encoding="utf-8"), "foreign command\n")

    def test_installed_cli_can_install_another_target(self):
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env["HOME"] = td
            with patch.dict(os.environ, {"HOME": td}):
                mod.install("ggcoder")
            launcher = Path(td) / ".local" / "bin" / "agent-skill-route"

            result = subprocess.run(
                [str(launcher), "install", "--target", "codex"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (
                    Path(td)
                    / ".codex"
                    / "skills"
                    / "agent-token-saver-skill-router"
                    / "SKILL.md"
                ).is_file()
            )


if __name__ == "__main__":
    unittest.main()
