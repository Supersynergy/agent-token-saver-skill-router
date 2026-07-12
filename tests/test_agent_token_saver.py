import importlib.util
import os
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


def write_skill(base: Path, name: str, desc: str):
    d = base / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8"
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

    def test_install_dry_run_lists_targets(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"HOME": td}):
                written = mod.install("all", dry_run=True)

            self.assertTrue(any(".hermes" in p for p in written))
            self.assertTrue(any(".claude" in p for p in written))
            self.assertTrue(any(".codex" in p for p in written))
            self.assertTrue(any(".gg" in p for p in written))


if __name__ == "__main__":
    unittest.main()
