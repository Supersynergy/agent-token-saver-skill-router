import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("agent_token_saver", ROOT / "scripts" / "agent_token_saver.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def write_skill(base: Path, name: str, desc: str):
    d = base / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8")


class AgentTokenSaverTests(unittest.TestCase):
    def test_route_selects_relevant_skill(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "skills"
            write_skill(root, "python-testing", "Use when running pytest and debugging failing Python tests.")
            write_skill(root, "copywriting", "Use when writing sales copy.")

            result = mod.route("debug failing pytest", roots=[root])

            self.assertEqual(result.scanned, 2)
            self.assertEqual([s.name for s in result.selected], ["python-testing"])
            self.assertIn("python-testing", result.router_block)

    def test_bench_reports_reduction_with_temp_home(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            home = base / "home"
            cwd = base / "cwd"
            cwd.mkdir()
            root = home / ".claude" / "skills"
            write_skill(root, "python-testing", "Use when running pytest and debugging failing Python tests.")
            write_skill(root, "copywriting", "Use when writing sales copy.")
            old_cwd = Path.cwd()
            try:
                os.chdir(cwd)
                with patch.dict(os.environ, {"HOME": str(home)}):
                    report = mod.bench("debug pytest")
            finally:
                os.chdir(old_cwd)

            self.assertEqual(report["skills_scanned"], 2)
            self.assertGreater(report["full_est_tokens"], 0)
            self.assertGreater(report["router_est_tokens"], 0)
            self.assertEqual(report["selected"][0]["name"], "python-testing")

    def test_install_dry_run_lists_targets(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"HOME": td}):
                written = mod.install("all", dry_run=True)

            self.assertTrue(any(".hermes" in p for p in written))
            self.assertTrue(any(".claude" in p for p in written))
            self.assertTrue(any(".codex" in p for p in written))


if __name__ == "__main__":
    unittest.main()
