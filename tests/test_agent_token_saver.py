import importlib.util
import json
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

    def test_reduce_save_trim_verbs_pass_the_workflow_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "token-saver",
                "Reduce tokens and save context by trimming large logs before "
                "they reach the model.",
                tags="tokens, context, log",
            )
            write_skill(root, "copywriting", "Use when writing sales copy.")

            for intent in (
                "reduce tokens for a large log file",
                "save context by trimming this log",
            ):
                result = mod.route(intent, roots=[root])
                self.assertEqual(
                    [s.name for s in result.selected],
                    ["token-saver"],
                    msg=f"intent={intent!r}",
                )

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

            result = mod.route(
                "review and release this repo", roots=[root], strict=True
            )

            self.assertEqual(result.selected, [])
            self.assertEqual(
                [candidate["name"] for candidate in result.alternatives],
                ["release-a", "release-b"],
            )

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

    def test_natural_named_stack_selects_five_skills_in_mention_order(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            names = [
                "clear-thought",
                "systematic-debugging",
                "agent-efficiency-orchestrator",
                "verification-loop",
                "security-review",
            ]
            for name in names:
                write_skill(root, name, f"Use {name} for its dedicated workflow.")

            result = mod.route(
                "Nutze Clear Thought, Systematic Debugging, "
                "Agent Efficiency Orchestrator, Verification Loop und "
                "Security Review gemeinsam.",
                roots=[root],
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual([skill.name for skill in result.selected], names)
            self.assertEqual(result.decision, "explicit")
            self.assertEqual(result.selection_roles[names[0]], "primary")
            self.assertTrue(
                all(result.selection_roles[name] == "support" for name in names[1:])
            )

    def test_exact_and_natural_names_do_not_add_overlapping_subskill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "computer-use", "Operate a computer interface.")
            write_skill(root, "macos-computer-use", "Operate the macOS interface.")

            exact = mod.route("macos-computer-use", roots=[root], strict=True)
            natural = mod.route(
                "Nutze macos-computer-use für diese Aufgabe.",
                roots=[root],
                strict=True,
            )

            self.assertEqual(
                [skill.name for skill in exact.selected], ["macos-computer-use"]
            )
            self.assertEqual(
                [skill.name for skill in natural.selected], ["macos-computer-use"]
            )

    def test_natural_named_support_does_not_displace_underlying_primary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "clear-thought",
                "Apply structured reasoning and mental models.",
                "structured, reasoning, thinking",
            )
            write_skill(
                root,
                "skill-fleet-audit",
                "Audit and optimize skill router quality and routing accuracy.",
                "audit, optimize, skill, router, route, quality, accuracy",
            )
            write_skill(
                root,
                "fetch-router",
                "Route HTTP fetch requests.",
                "fetch, request, route",
            )

            result = mod.route(
                "Warum fand der Skill Router nichts? Verwende vielleicht Clear "
                "Thought und verbessere die Treffergenauigkeit des Skill Routers.",
                roots=[root],
                strict=True,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(
                [skill.name for skill in result.selected],
                ["skill-fleet-audit", "clear-thought"],
            )
            self.assertEqual(result.decision, "mixed-explicit")
            self.assertEqual(result.selection_roles["skill-fleet-audit"], "primary")
            self.assertEqual(result.selection_roles["clear-thought"], "support")

    def test_multiclause_route_combines_five_complementary_skills(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "source-research",
                "Research current sources and collect evidence.",
                "research, current, sources, evidence",
            )
            write_skill(
                root,
                "pdf-report",
                "Create a polished PDF report document.",
                "create, pdf, report, document",
            )
            write_skill(
                root,
                "email-delivery",
                "Send an email message to a recipient.",
                "send, email, message, recipient",
            )
            write_skill(
                root,
                "security-review",
                "Review security risks and vulnerabilities.",
                "review, security, risk, vulnerabilities",
            )
            write_skill(
                root,
                "verification-loop",
                "Verify the final output and tests.",
                "verify, output, test, final",
            )

            result = mod.route(
                "Research current sources; create a PDF report; send it by email; "
                "review security risks; verify the final output.",
                roots=[root],
                strict=True,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(len(result.selected), 5)
            self.assertEqual(
                [skill.name for skill in result.selected],
                [
                    "source-research",
                    "pdf-report",
                    "email-delivery",
                    "security-review",
                    "verification-loop",
                ],
            )
            self.assertEqual(
                list(result.selection_roles.values()).count("primary"), 1
            )
            self.assertEqual(
                list(result.selection_roles.values()).count("support"), 4
            )

    def test_german_prompt_discovery_and_evaluation_combine(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "prompt-library-navigator",
                "Browse and search prompt libraries for source selection.",
                "prompt, library, browse, search, select, source",
            )
            write_skill(
                root,
                "prompt-evaluation",
                "Test prompts reproducibly against fixed test cases and metrics.",
                "prompt, test, reproducible, fixed, cases, metrics",
            )
            write_skill(
                root,
                "python-testing",
                "Test Python code with unit and integration tests.",
                "python, code, test",
            )

            result = mod.route(
                "Durchsuche unsere Prompt-Bibliotheken; wähle einen Prompt; "
                "teste ihn reproduzierbar gegen feste Testfälle.",
                roots=[root],
                strict=True,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(
                [skill.name for skill in result.selected],
                ["prompt-library-navigator", "prompt-evaluation"],
            )

    def test_german_prompt_discovery_and_evidence_synthesis_combine(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "prompt-library-navigator",
                "Find and search prompt libraries and prompt sources.",
                "find, search, prompt, library, source",
            )
            write_skill(
                root,
                "evidence-synthesis-patterns",
                "Synthesize multiple documents into claims and traceable evidence.",
                "synthesis, documents, claims, evidence",
            )

            result = mod.route(
                "Finde eine Promptquelle; synthetisiere mehrere Dokumente mit "
                "Claims und Belegen.",
                roots=[root],
                strict=True,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(len(result.selected), 2)
            self.assertEqual(
                {skill.name for skill in result.selected},
                {"prompt-library-navigator", "evidence-synthesis-patterns"},
            )

    def test_text_research_bundle_excludes_audio_only_briefing_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "prompt-library-navigator",
                "Find and search finance prompt libraries.",
                "find, search, finance, prompt, library",
            )
            write_skill(
                root,
                "finance-thesis-invalidation",
                "Invalidate an investment thesis with counterevidence.",
                "invalidate, investment, thesis, counterevidence",
            )
            write_skill(
                root,
                "equity-research-artifact",
                "Create an auditable equity research brief.",
                "create, equity, research, brief",
            )
            write_skill(
                root,
                "daily-briefing",
                "Generate and play an audio briefing with TTS as an MP3.",
                "generate, play, audio, briefing, tts, mp3",
            )

            result = mod.route(
                "Finde Finance-Prompt-Bibliotheken; widerlege die Investment-These; "
                "erstelle ein Equity-Research-Briefing.",
                roots=[root],
                strict=True,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(
                [skill.name for skill in result.selected],
                [
                    "prompt-library-navigator",
                    "finance-thesis-invalidation",
                    "equity-research-artifact",
                ],
            )

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

    def test_context_mode_is_explicit_only_for_automatic_routes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "context-mode",
                "Use context-mode tools instead of Bash when running tests and "
                "processing large command output.",
            )
            automatic = mod.route("test output and inspect this change", roots=[root])
            explicit = mod.route("$context-mode", roots=[root])

            self.assertEqual(automatic.selected, [])
            self.assertEqual(
                [skill.name for skill in explicit.selected], ["context-mode"]
            )

    def test_plain_test_verification_does_not_load_an_unrelated_debugger(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            software = root / "software-development"
            write_skill(
                software,
                "python-debugpy",
                "Debug Python programs with pdb and debugpy.",
                "debugging, python, pdb",
            )

            result = mod.route("test output and verify this change", roots=[root])

            self.assertEqual(result.selected, [])

    def test_run_tests_is_plain_verification_and_loads_no_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root, "test-driven-development", "Use red-green-refactor for tests."
            )

            result = mod.route("run tests", roots=[root], strict=True)

            self.assertEqual(result.selected, [])

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

            self.assertEqual(result.selected[0].name, "python-debugpy")
            self.assertNotIn(
                "node-inspect-debugger", [skill.name for skill in result.selected]
            )

    def test_security_review_beats_generic_web_api_match(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "web-fetcher",
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
            favorites.write_text("web-fetcher=8\n", encoding="utf-8")

            with patch.dict(os.environ, {"AGENT_SKILL_FAVORITES_FILE": str(favorites)}):
                result = mod.route(
                    "review Python API auth bug for security and regressions",
                    max_selected=2,
                    roots=[root],
                )

            names = [skill.name for skill in result.selected]
            self.assertCountEqual(
                names[:2], ["security-hardening", "requesting-code-review"]
            )
            self.assertNotIn("web-fetcher", names)

    def test_german_pull_request_review_beats_pr_check_distractors(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "antislop",
                "Check text and code before a GitHub pull request.",
                "github, pull request, test",
            )
            write_skill(
                root,
                "gh-address-comments",
                "Address comments on an open GitHub pull request.",
                "github, pull request, comments",
            )
            write_skill(
                root,
                "github-code-review",
                "Review a GitHub pull request for code quality and defects.",
                "github, pull request, code review",
            )

            result = mod.route(
                "prüfe den pull request auf github",
                max_selected=1,
                roots=[root],
                strict=True,
            )

            self.assertEqual([skill.name for skill in result.selected], ["github-code-review"])

    def test_german_landing_page_load_time_routes_web_performance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "ad-creative",
                "Optimize landing page advertising creative performance.",
                "landing, page, ads, performance",
            )
            write_skill(
                root,
                "performance",
                "Improve page speed, load time, and web performance.",
                "page, speed, performance",
            )

            result = mod.route(
                "optimiere die ladezeit meiner landing page",
                max_selected=1,
                roots=[root],
                strict=True,
            )

            self.assertEqual([skill.name for skill in result.selected], ["performance"])

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
            write_skill(root / "backups", "backup-skill", "Backup only.")
            write_skill(root / "_skill-packages", "package-skill", "Package only.")
            write_skill(root / "related-skills", "related-skill", "Reference only.")

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
                "Audit token-saving and context-saving stacks across Codex. Covers noisy tool output, local artifacts, skills, and agent teams.",
                "tokens, context, artifacts, routing, teams",
            )
            write_skill(
                root,
                "codex",
                "Delegate coding to OpenAI Codex CLI for features and PRs.",
                "coding, codex",
            )
            write_skill(
                root,
                "simulation-orchestrator",
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
            fav.write_text("simulation-orchestrator=8\n", encoding="utf-8")

            with patch.dict(os.environ, {"AGENT_SKILL_FAVORITES_FILE": str(fav)}):
                result = mod.route(
                    "optimize Codex agent teams, token context, and noisy tool outputs",
                    roots=[root],
                )

            self.assertEqual(result.selected[0].name, "token-stack-operations")
            self.assertNotIn("codex", [s.name for s in result.selected])
            self.assertNotEqual(result.selected[0].name, "simulation-orchestrator")
            self.assertNotIn("peft-fine-tuning", [s.name for s in result.selected])

    def test_coding_agent_team_beats_microsoft_teams_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "agent-token-saver",
                "Use compact capsules and machine oracles for cheap coding agent teams.",
                "tokens, context, agent-teams, capsule, subagent",
            )
            write_skill(
                root,
                "teams-meeting-pipeline",
                "Operate Microsoft Teams meeting summaries and Graph subscriptions.",
                "microsoft, teams, meetings, graph",
            )
            write_skill(
                root,
                "token-context-optimization",
                "Optimize agent token context and session memory.",
                "tokens, context, agent",
            )

            result = mod.route(
                "optimize coding agent teams with compact capsules and token context",
                roots=[root],
                strict=True,
            )

            self.assertEqual(
                [skill.name for skill in result.selected], ["agent-token-saver"]
            )

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
                "Audit token-saving context stacks across Codex with routing, local artifacts, and lean MCP defaults.",
                "token, saving, stack, context, routing, artifacts",
            )

            result = mod.route("audit Codex token saving stack", roots=[root])

            self.assertEqual(result.selected[0].name, "token-stack-operations")

    def test_legacy_skill_autopilot_is_explicit_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "skill-autopilot",
                "Self-training skill router with usage logging and better selection.",
                "skills, router, logging, selection",
            )
            write_skill(
                root,
                "agent-token-saver",
                "Optimize skill routing, usage logging, and token context safely.",
                "skills, router, logging, tokens",
            )

            automatic = mod.route(
                "build smart skill router logging and improve selection",
                roots=[root],
                usage_data=mod.UsageData(signals={}),
            )
            explicit = mod.route("$skill-autopilot", roots=[root])

            self.assertEqual(automatic.selected[0].name, "agent-token-saver")
            self.assertEqual(explicit.selected[0].name, "skill-autopilot")

    def test_german_workflow_verbs_reach_routing_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "agent-token-saver",
                "Optimize skill router logging, usage, and selection.",
                "skills, router, logging, tokens",
            )
            write_skill(
                root,
                "friction-audit",
                "Optimieren von UX Friction und Zeitverlust in Workflows.",
            )
            favorites = Path(td) / "favorites.txt"
            favorites.write_text("friction-audit=6\n", encoding="utf-8")

            with patch.dict(os.environ, {"AGENT_SKILL_FAVORITES_FILE": str(favorites)}):
                result = mod.route(
                    "wie kannst du selbstlernend sein und skills automatisch "
                    "optimieren bei nutzung auch vom skill router",
                    roots=[root],
                    strict=True,
                    usage_data=mod.UsageData(signals={}),
                )

            self.assertEqual(result.decision, "selected")
            self.assertEqual(result.selected[0].name, "agent-token-saver")

    def test_german_repeated_local_dashboard_routes_generic_root_cause_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            software = root / "software-development"
            write_skill(
                software,
                "systematic-debugging",
                "Find root causes with systematic debugging and troubleshooting.",
                "debugging, troubleshooting, root cause, investigation",
            )
            write_skill(
                software,
                "node-inspect-debugger",
                "Debug Node.js with inspect and Chrome DevTools Protocol.",
                "debugging, nodejs, inspect, cdp",
            )
            write_skill(
                software,
                "python-debugpy",
                "Debug Python with pdb and debugpy.",
                "debugging, python, pdb, debugpy",
            )
            write_skill(
                root,
                "analytics-dashboard",
                "Create an analytics dashboard with charts and revenue KPIs.",
                "dashboard, analytics, charts, revenue",
            )

            result = mod.route(
                "Wofür war noch mal Serena und warum öffnet es sich die ganze "
                "Zeit? Brauch ich das wirklich?",
                roots=[root],
                strict=True,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(result.decision, "selected")
            self.assertEqual(
                [skill.name for skill in result.selected], ["systematic-debugging"]
            )

    def test_natural_german_router_optimization_reaches_skill_governance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "skill-fleet-audit",
                "Audit and improve a multilingual skill router fleet, routing "
                "accuracy, reachability, and safe skill combinations.",
                "skills, router, routing, multilingual, accuracy, combinations",
            )
            write_skill(
                root,
                "fetch-router",
                "Route HTTP fetch requests between web transports.",
                "fetch, http, web, routing",
            )

            result = mod.route(
                "Maximiere natürliches mehrsprachiges Skill-Routing und kombiniere "
                "bei Bedarf bis zu fünf ergänzende Skills.",
                roots=[root],
                strict=True,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(result.decision, "selected")
            self.assertEqual(result.selected[0].name, "skill-fleet-audit")

    def test_adaptive_feedback_breaks_relevant_tie_without_creating_relevance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "alpha-api", "Build and deploy a Python API.")
            write_skill(root, "beta-api", "Build and deploy a Python API.")
            write_skill(root, "sales-copy", "Write high-converting sales copy.")
            usage = mod.UsageData(
                signals={
                    "alpha-api": mod.UsageSignal(failure=4),
                    "beta-api": mod.UsageSignal(success=4),
                    "sales-copy": mod.UsageSignal(success=100, applied=100),
                }
            )

            result = mod.route(
                "build and deploy a Python API",
                roots=[root],
                strict=True,
                usage_data=usage,
            )

            self.assertEqual(result.selected[0].name, "beta-api")
            ranked = mod.rank_candidates(
                "build and deploy a Python API", mod.scan([root]), {}, usage
            )
            sales = next(item for item in ranked if item[3].name == "sales-copy")
            self.assertEqual(sales[0], 0)
            self.assertEqual(sales[2], 0)

    def test_route_telemetry_hashes_prompt_and_stats_merge_real_loads(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            root = home / "skills"
            state = home / "state"
            write_skill(root, "python-testing", "Debug failing Python tests.")
            write_skill(root, "copywriting", "Write sales copy.")
            usage_log = home / ".gg" / "skill-usage.jsonl"
            usage_log.parent.mkdir(parents=True)
            usage_log.write_text(
                '{"event":"skill_loaded","skill_name":"SKILL",'
                '"skill_path":"/tmp/python-testing/SKILL.md","ts":"2026-07-14T10:00:00"}\n',
                encoding="utf-8",
            )
            secret_prompt = "debug failing pytest for private customer acme"
            env = {
                "HOME": td,
                "AGENT_SKILL_ROUTER_STATE_DIR": str(state),
            }
            with patch.dict(os.environ, env):
                result = mod.route(
                    secret_prompt,
                    roots=[root],
                    usage_data=mod.UsageData(signals={}),
                )
                mod.record_route(result, strict=True)
                data = mod.load_usage_data(include_routes=True)
                catalog = mod.load_catalog([root], use_index=False)
                report = mod.usage_report(catalog, data, include_rows=True)
                raw_log = mod.route_events_file().read_text(encoding="utf-8")

            self.assertNotIn(secret_prompt, raw_log)
            self.assertIn("intent_hash", raw_log)
            rows = {row["name"]: row for row in report["rows"]}
            self.assertEqual(rows["python-testing"]["routed"], 1)
            self.assertEqual(rows["python-testing"]["applied"], 1)
            self.assertEqual(rows["copywriting"]["applied"], 0)
            self.assertFalse(report["raw_prompts_stored"])

    def test_alias_usage_rolls_up_without_double_counting(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "agent-token-saver-skill-router",
                "Select zero or one skill for a task.",
            )
            catalog = mod.load_catalog([root], use_index=False)
            data = mod.UsageData(
                signals={
                    "agent-token-saver-skill-router": mod.UsageSignal(applied=2),
                    "just-in-time-skill-router": mod.UsageSignal(applied=12),
                    "allskills": mod.UsageSignal(applied=1),
                }
            )

            report = mod.usage_report(catalog, data, include_rows=True)
            canonical = {row["name"]: row for row in report["canonical_usage"]}

            self.assertEqual(report["total_applied"], 15)
            self.assertEqual(canonical["agent-token-saver-skill-router"]["applied"], 15)
            self.assertEqual(
                canonical["agent-token-saver-skill-router"]["aliases"],
                ["allskills", "just-in-time-skill-router"],
            )
            self.assertEqual(
                canonical["agent-token-saver-skill-router"]["adaptive_adjustment"],
                2,
            )
            self.assertNotIn(
                "just-in-time-skill-router", report["unknown_observed_skills"]
            )

    def test_aliases_are_explicit_only_and_canonical_resolution_is_available(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "skill-portfolio-governance",
                "Audit weekly skill health reports and internal ranking.",
            )
            catalog = mod.load_catalog([root], use_index=False)

            alias_rows = mod.skill_alias_report(catalog)
            governance = mod.route(
                "weekly skill health report and internal ranking",
                roots=[root],
                strict=False,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(mod.canonical_skill_name("$sm"), mod.SKILL_NAME)
            self.assertEqual(governance.selected[0].name, "skill-portfolio-governance")
            self.assertNotIn(
                "agent-efficiency-orchestrator",
                {row["alias"] for row in alias_rows},
            )

    def test_web_suite_component_keeps_exact_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "superweb",
                "Search, fetch, crawl, research, and extract current web pages.",
            )
            write_skill(
                root,
                "superscrape",
                "Legacy compatibility shim for web fetching.",
            )

            result = mod.route(
                "$superscrape",
                roots=[root],
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual([skill.name for skill in result.selected], ["superscrape"])
            self.assertEqual(mod.canonical_skill_name("scrape-deep"), "scrape-deep")
            self.assertEqual(mod.canonical_skill_name("scrapedeep"), "scrape-deep")

    def test_web_suite_component_history_stays_independent(self):
        data = mod.UsageData(
            signals={
                "superweb": mod.UsageSignal(applied=1),
                "superscrape": mod.UsageSignal(applied=7, success=4),
                "stealth-research": mod.UsageSignal(failure=1),
            }
        )

        signal = mod.canonical_skill_signal(data, "superweb")

        self.assertEqual(signal.applied, 1)
        self.assertEqual((signal.success, signal.failure), (0, 0))
        superscrape = mod.canonical_skill_signal(data, "superscrape")
        self.assertEqual(superscrape.applied, 7)
        self.assertEqual((superscrape.success, superscrape.failure), (4, 0))

    def test_german_skill_improvement_prompt_reaches_governance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "skill-portfolio-governance",
                "Audit skill usage, overlap, internal ranking, merge, and cleanup candidates.",
                "skills, improvement, ranking, cleanup",
            )

            result = mod.route(
                "überlege welche skills verbessert und vorsichtig aufgeräumt werden müssen",
                roots=[root],
                strict=True,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(result.decision, "selected")
            self.assertEqual(result.selected[0].name, "skill-portfolio-governance")

    def test_german_full_fleet_repair_beats_domain_best_practices(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "skill-fleet-audit",
                "Audit and safely repair all skills with Agent Skills best practices. "
                "Use for die ganzen Skills, stabil, SkillIndexer, and aufrufbar.",
            )
            write_skill(
                root,
                "vercel-react-best-practices",
                "React and Next.js performance best practices for components and pages.",
            )

            result = mod.route(
                "fix bitte die ganzen skills nach best practices, jeder skill stabil "
                "und im skillindexer aufrufbar",
                roots=[root],
                strict=True,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(result.decision, "selected")
            self.assertEqual(result.selected[0].name, "skill-fleet-audit")

    def test_portfolio_verification_does_not_route_to_tdd(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "skill-portfolio-governance",
                "Audit skill usage, merge, update, cleanup, and drift candidates.",
                "skill, merge, update, cleanup, drift",
            )
            write_skill(
                root / "software-development",
                "test-driven-development",
                "Test code with red-green-refactor.",
                "test, tdd, code",
            )

            result = mod.route(
                "aktualisiere alle skills, prüfe merge-kandidaten und räume vorsichtig auf",
                roots=[root],
                strict=True,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(result.decision, "selected")
            self.assertEqual(result.selected[0].name, "skill-portfolio-governance")

    def test_agent_efficiency_orchestrator_is_independent_and_routable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "agent-efficiency-orchestrator",
                "Optimize agent tool workflows for lower tokens latency compute and coordination cost.",
            )
            write_skill(
                root,
                "metareview",
                "Review code diffs for correctness and grounded defects.",
            )
            catalog = mod.load_catalog([root], use_index=False)

            result = mod.route(
                "optimize agent tool workflow token latency and coordination cost",
                roots=[root],
                strict=False,
                usage_data=mod.UsageData(signals={}),
            )

            self.assertEqual(
                mod.canonical_skill_name("agent-efficiency-orchestrator"),
                "agent-efficiency-orchestrator",
            )
            self.assertEqual(
                mod.resolve_skill("agent-efficiency-orchestrator", catalog.skills).name,
                "agent-efficiency-orchestrator",
            )
            self.assertEqual(result.selected[0].name, "agent-efficiency-orchestrator")

    def test_restored_meta_skills_keep_independent_responsibilities(self):
        self.assertEqual(
            mod.canonical_skill_name("meta-skill-evolution-diary-weekly"),
            "meta-skill-evolution-diary-weekly",
        )
        self.assertEqual(
            mod.canonical_skill_name("meta-skill-token-efficiency-optimizer"),
            "meta-skill-token-efficiency-optimizer",
        )
        self.assertEqual(
            mod.canonical_skill_name("skill-autopilot"),
            "skill-autopilot",
        )
        self.assertNotIn("meta-skill-evolution-diary-weekly", mod.AUTO_ROUTE_EXCLUDED)
        self.assertNotIn(
            "meta-skill-token-efficiency-optimizer", mod.AUTO_ROUTE_EXCLUDED
        )
        self.assertIn("skill-autopilot", mod.AUTO_ROUTE_EXCLUDED)

    def test_feedback_is_compact_and_changes_bounded_adjustment(self):
        with tempfile.TemporaryDirectory() as td:
            env = {"HOME": td, "AGENT_SKILL_ROUTER_STATE_DIR": str(Path(td) / "state")}
            with patch.dict(os.environ, env):
                mod.record_feedback("python-testing", "success", "route-1")
                mod.record_feedback("python-testing", "failure", "route-2")
                data = mod.load_usage_data(include_routes=True)

            signal = data.signals["python-testing"]
            self.assertEqual((signal.success, signal.failure), (1, 1))
            self.assertLessEqual(abs(mod.learned_adjustment(signal)), 8)
            self.assertEqual(data.feedback_events, 2)

    def test_suite_component_feedback_keeps_component_name(self):
        with tempfile.TemporaryDirectory() as td:
            env = {"HOME": td, "AGENT_SKILL_ROUTER_STATE_DIR": str(Path(td) / "state")}
            with patch.dict(os.environ, env):
                event = mod.record_feedback("superscrape", "success", "route-web")
                data = mod.load_usage_data(include_routes=True)

            self.assertEqual(event["skill"], "superscrape")
            self.assertEqual(data.signals["superscrape"].success, 1)
            self.assertNotIn("superweb", data.signals)

    def test_explicit_ghmax_routes_a_tool_not_a_fuzzy_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "grep-app", "Search code with grep patterns.")
            with patch.object(
                mod.shutil,
                "which",
                side_effect=lambda name: f"/bin/{name}" if name == "ghmax" else None,
            ):
                result = mod.route(
                    "search GitHub code with ghmax",
                    roots=[root],
                    usage_data=mod.UsageData(signals={}),
                )

            self.assertEqual(result.decision, "explicit-tool")
            self.assertEqual(result.selected, [])
            self.assertEqual(result.recommended_tools[0].name, "ghmax")
            self.assertEqual(result.recommended_tools[0].path, "/bin/ghmax")

    def test_ghgrep_alias_canonicalizes_to_ghmax(self):
        with patch.object(
            mod.shutil,
            "which",
            side_effect=lambda name: f"/bin/{name}" if name == "ghgrep" else None,
        ):
            ranked = mod.rank_tools(
                "find current implementation with ghgrep",
                mod.UsageData(signals={}),
            )

        self.assertEqual(ranked[0].name, "ghmax")
        self.assertTrue(ranked[0].explicit)
        self.assertEqual(mod.canonical_tool_name("/tmp/ghgrep"), "ghmax")

    def test_web_command_aliases_canonicalize_to_superweb(self):
        with patch.object(
            mod.shutil,
            "which",
            side_effect=lambda name: f"/bin/{name}" if name == "superweb" else None,
        ):
            ranked = mod.rank_tools(
                "fetch this page with smart-fetch",
                mod.UsageData(signals={}),
            )

        self.assertEqual(ranked[0].name, "superweb")
        self.assertTrue(ranked[0].explicit)
        self.assertEqual(mod.canonical_tool_name("/tmp/superscrape"), "superweb")
        self.assertEqual(mod.canonical_tool_name("/tmp/superfetch"), "superweb")

    def test_german_multisource_web_workflow_selects_superweb(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(
                root,
                "superweb",
                "Search current web sources and produce cited multi-source research.",
                tags="web, search, research, cited, current",
            )
            write_skill(
                root,
                "citation-formatting",
                "Format citations already present in a local document.",
            )
            with patch.object(
                mod.shutil,
                "which",
                side_effect=lambda name: f"/bin/{name}" if name == "superweb" else None,
            ):
                result = mod.route(
                    "Recherchiere mehrere aktuelle Webquellen und fasse sie "
                    "mit Zitaten zusammen.",
                    roots=[root],
                    strict=True,
                    usage_data=mod.UsageData(signals={}),
                )

        self.assertEqual(result.decision, "selected")
        self.assertEqual([skill.name for skill in result.selected], ["superweb"])
        self.assertEqual(result.recommended_tools[0].name, "superweb")

    def test_decisive_pure_tool_route_suppresses_fuzzy_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "web-perf", "Search current web documentation.")
            with patch.object(
                mod.shutil,
                "which",
                side_effect=lambda name: f"/bin/{name}" if name == "superweb" else None,
            ):
                result = mod.route(
                    "search current web documentation",
                    roots=[root],
                    usage_data=mod.UsageData(signals={}),
                )

            self.assertEqual(result.decision, "tool-selected")
            self.assertEqual(result.selected, [])
            self.assertEqual(result.recommended_tools[0].name, "superweb")

    def test_tool_learning_is_bounded_and_cannot_create_relevance(self):
        usage = mod.UsageData(
            signals={},
            tool_signals={
                "ghmax": mod.ToolSignal(used=20, success=18, failure=2),
                "run-guard": mod.ToolSignal(used=100, success=100),
            },
        )
        with patch.object(mod.shutil, "which", side_effect=lambda name: f"/bin/{name}"):
            ranked = mod.rank_tools("search GitHub repository code", usage)

        self.assertEqual(ranked[0].name, "ghmax")
        self.assertNotIn("run-guard", [candidate.name for candidate in ranked])
        self.assertLessEqual(abs(ranked[0].adaptive_adjustment), 8)

    def test_observer_logs_only_canonical_tool_outcomes(self):
        with tempfile.TemporaryDirectory() as td:
            env = {
                "HOME": td,
                "AGENT_SKILL_ROUTER_STATE_DIR": str(Path(td) / "state"),
            }
            payload = {
                "tool_input": {
                    "command": "python3 -V\nghmax --smart 'private query' && "
                    "rtk tilth --budget 4000 src"
                },
                "tool_response": {"exit_code": 0, "duration_ms": 125},
            }
            with patch.dict(os.environ, env):
                events = mod.observe_hook_payload(payload)
                data = mod.load_usage_data(include_routes=True)
                raw = mod.route_events_file().read_text(encoding="utf-8")

            self.assertEqual(
                [event["tool"] for event in events], ["ghmax", "rtk", "tilth"]
            )
            self.assertEqual(data.tool_signals["ghmax"].success, 1)
            self.assertNotIn("private query", raw)
            self.assertNotIn("--budget", raw)
            self.assertEqual(
                mod._hook_outcome({"extra": {"status": "error"}}), "failure"
            )
            self.assertEqual(mod._hook_latency_ms({"extra": {"duration_ms": 77}}), 77)

    def test_hook_install_is_append_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            codex = Path(td) / ".codex" / "hooks.json"
            claude = Path(td) / ".claude" / "settings.json"
            hermes = Path(td) / ".hermes" / "config.yaml"
            existing = {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "existing"}],
                        }
                    ]
                }
            }
            for path in (codex, claude):
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(existing), encoding="utf-8")
            hermes.parent.mkdir(parents=True)
            hermes.write_text(
                "hooks: null\nhooks_auto_accept: false\n", encoding="utf-8"
            )
            with patch.dict(os.environ, {"HOME": td}):
                first = mod.install_hooks("all")
                second = mod.install_hooks("all")
                status = [
                    mod.hook_has_observer(name)
                    for name in ("codex", "claude", "hermes")
                ]

            self.assertTrue(all(item["changed"] for item in first))
            self.assertFalse(any(item["changed"] for item in second))
            self.assertEqual(status, [True, True, True])
            payload = json.loads(codex.read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for entry in payload["hooks"]["PostToolUse"]
                for hook in entry["hooks"]
            ]
            self.assertIn("existing", commands)
            self.assertEqual(
                commands.count(str(Path(td) / ".local/bin/si") + " observe"), 1
            )
            hermes_text = hermes.read_text(encoding="utf-8")
            self.assertIn("  post_tool_call:", hermes_text)
            self.assertIn("hooks_auto_accept: false", hermes_text)

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

    def test_drift_report_separates_identical_and_divergent_copies(self):
        with tempfile.TemporaryDirectory() as td:
            root_a = Path(td) / "a"
            root_b = Path(td) / "b"
            root_c = Path(td) / "c"
            write_skill(root_a, "shared", "First responsibility.")
            write_skill(root_b, "shared", "Second responsibility.")
            write_skill(root_a, "stable", "Same responsibility.")
            write_skill(root_c, "stable", "Same responsibility.")

            report = mod.skill_drift_report([root_a, root_b, root_c], include_rows=True)
            rows = {row["name"]: row for row in report["rows"]}

            self.assertEqual(report["duplicate_groups"], 2)
            self.assertEqual(report["divergent_groups"], 1)
            self.assertTrue(rows["shared"]["divergent"])
            self.assertFalse(rows["stable"]["divergent"])

    def test_repair_moves_embedded_frontmatter_and_quotes_yaml_scalars(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = Path(td) / "browser-audit"
            skill_dir.mkdir()
            path = skill_dir / "SKILL.md"
            original = (
                "<!-- injected preamble -->\n"
                "Read local context first.\n"
                "---\n"
                "name: browser-audit\n"
                "description: Audit browser state: inspect, change, verify.\n"
                "argument-hint: [url] [--strict]\n"
                "---\n\n"
                "# Browser audit\n"
            )

            repaired, fixes = mod.repair_skill_text(path, original)
            path.write_text(repaired, encoding="utf-8")
            issues = mod.validate_skill_file(path)

            self.assertTrue(repaired.startswith("---\nname: browser-audit\n"))
            self.assertIn("<!-- injected preamble -->", repaired)
            self.assertIn("frontmatter-moved-to-start", fixes)
            self.assertIn("quoted-description", fixes)
            self.assertIn("quoted-argument-hint", fixes)
            self.assertFalse([issue for issue in issues if issue.severity == "error"])

    def test_repair_adds_frontmatter_to_plain_skill(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = Path(td) / "canvas"
            skill_dir.mkdir()
            path = skill_dir / "SKILL.md"
            original = "# Canvas\n\nDisplay HTML on connected nodes.\n"

            repaired, fixes = mod.repair_skill_text(path, original)
            path.write_text(repaired, encoding="utf-8")
            document = mod.parse_frontmatter_document(path)

            self.assertIn("frontmatter-added", fixes)
            self.assertEqual(document.fields["name"], "canvas")
            self.assertIn("Display HTML", document.fields["description"])
            self.assertFalse(
                [
                    issue
                    for issue in mod.validate_skill_file(path)
                    if issue.severity == "error"
                ]
            )

    def test_scan_prefers_shallow_canonical_copy_within_same_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root / "superskills", "zeta", "Nested mirror copy.")
            write_skill(root, "zeta", "Canonical shallow copy.")

            skills = mod.scan([root])

            self.assertEqual(len(skills), 1)
            self.assertIn("Canonical shallow", skills[0].description)
            self.assertEqual(Path(skills[0].path), root / "zeta" / "SKILL.md")

    def test_validation_checks_script_syntax_without_executing_script(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "broken-script", "Use when checking a broken script.")
            script = root / "broken-script" / "scripts" / "broken.py"
            script.parent.mkdir()
            script.write_text("def broken(:\n    pass\n", encoding="utf-8")

            issues = mod.validate_skill_file(
                root / "broken-script" / "SKILL.md", check_scripts=True
            )

            self.assertIn("script-syntax", [issue.code for issue in issues])

    def test_smoke_resolves_and_invokes_every_indexed_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "python-testing", "Use when debugging Python tests.")
            write_skill(root, "copywriting", "Use when writing product copy.")
            catalog = mod.Catalog(
                skills=mod.scan([root]),
                roots=[root],
                source="scan",
                index_path=Path(td) / "index.json",
            )

            report = mod.skill_smoke_report(catalog)

            self.assertTrue(report["ok"])
            self.assertEqual(report["resolved"], 2)
            self.assertEqual(report["invoked"], 2)

    def test_repair_apply_creates_private_backup_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "skills"
            skill_dir = root / "plain-skill"
            skill_dir.mkdir(parents=True)
            path = skill_dir / "SKILL.md"
            path.write_text("# Plain\n\nUse this plain workflow.\n", encoding="utf-8")
            state = base / "state"

            with patch.dict(os.environ, {"AGENT_SKILL_ROUTER_STATE_DIR": str(state)}):
                report = mod.repair_report([path], apply=True)

            backup = Path(report["backup_dir"])
            self.assertEqual(report["changed"], 1)
            self.assertTrue((backup / "manifest.json").is_file())
            self.assertTrue(mod.parse_frontmatter_document(path))

    def test_learning_observation_labels_sparse_and_mature_windows(self):
        sparse = mod.UsageData(
            signals={"superweb": mod.UsageSignal(success=1)},
            route_events=50,
        )
        mature = mod.UsageData(
            signals={"superweb": mod.UsageSignal(success=20)},
            route_events=20,
        )

        self.assertEqual(mod.learning_observation(sparse)["confidence"], "low")
        self.assertEqual(mod.learning_observation(mature)["confidence"], "high")


if __name__ == "__main__":
    unittest.main()
