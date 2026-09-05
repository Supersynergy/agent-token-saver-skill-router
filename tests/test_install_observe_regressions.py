import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_agent_token_saver import ROOT, mod


class InstallObserveRegressions(unittest.TestCase):
    def test_project_gg_skills_are_indexed_before_global_skills(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            project = Path(td) / "project"
            local = project / ".gg/skills"
            global_root = home / ".gg/skills"
            local.mkdir(parents=True)
            global_root.mkdir(parents=True)
            with patch.dict(os.environ, {"HOME": str(home)}):
                roots = mod.common_roots(project)
                self.assertLess(roots.index(local.resolve()), roots.index(global_root.resolve()))

    @unittest.skipUnless(shutil.which("node"), "GG Coder requires Node.js")
    def test_native_gg_extension_contract(self):
        result = subprocess.run(
            [shutil.which("node"), "--test", str(ROOT / "tests/test_ggcoder_observer.mjs")],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_native_skill_event_and_gg_extension_install(self):
        with tempfile.TemporaryDirectory() as td:
            env = {"HOME": td, "AGENT_SKILL_ROUTER_STATE_DIR": str(Path(td) / "state")}
            with patch.dict(os.environ, env):
                mod.install("ggcoder")
                self.assertTrue(mod.install_hooks("ggcoder")[0]["changed"])
                self.assertFalse(mod.install_hooks("ggcoder")[0]["changed"])
                self.assertTrue(mod.hook_has_observer("ggcoder"))
                events = mod.observe_hook_payload({"tool_name": "skill", "tool_input": {"skill": "audit"}})
                self.assertEqual([e["skill"] for e in events], ["audit"])
                events = mod.observe_hook_payload({"tool_name": "skill", "tool_input": {"skill": "audit"}, "source": "superggcoder"})
                self.assertEqual(events[0]["source"], "superggcoder")

    def test_desktop_hook_sources_survive_skill_and_tool_projection(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"AGENT_SKILL_ROUTER_STATE_DIR": td}):
                for source in ("ggcoder-app", "superggcoder-app"):
                    with self.subTest(source=source):
                        events = mod.observe_hook_payload({
                            "tool_name": "skill", "tool_input": {"skill": "audit"},
                            "source": source, "tool_response": {"status": "success"},
                        })
                        self.assertEqual(events[0]["source"], source)
                        events = mod.observe_hook_payload({
                            "tool_name": "bash", "tool_input": {"command": "just check"},
                            "source": source, "tool_response": {"status": "error"},
                        })
                        self.assertEqual(events[0]["source"], source)
                        self.assertEqual(events[0]["outcome"], "failure")

    def test_bootstrap_finds_versioned_python_and_rejects_unsupported_python(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            bin_dir = home / "bin"
            bin_dir.mkdir()
            stale = bin_dir / "python3"
            stale.write_text("#!/bin/sh\nexit 1\n")
            stale.chmod(0o755)
            real = bin_dir / "python3.9"
            real.symlink_to(sys.executable)
            (bin_dir / "dirname").symlink_to(shutil.which("dirname"))
            repo = home / "repo"
            (repo / "scripts").mkdir(parents=True)
            shutil.copyfile(ROOT / "install.sh", repo / "install.sh")
            (repo / "scripts" / "agent_token_saver.py").write_text(
                "import sys; print('RAN_WITH', sys.executable)\n"
            )
            command = [shutil.which("bash"), str(repo / "install.sh"), "ggcoder"]
            env = {"HOME": td, "PATH": str(bin_dir)}
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("RAN_WITH", result.stdout)
            real.unlink()
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Python 3.9+", result.stderr)
            self.assertNotIn("Installed", result.stdout)

    def test_launcher_observes_all_supported_read_payloads(self):
        with tempfile.TemporaryDirectory() as td:
            env = {**os.environ, "HOME": td, "AGENT_SKILL_ROUTER_STATE_DIR": str(Path(td) / "st")}
            with patch.dict(os.environ, env):
                mod.install("ggcoder")
            launcher = Path(td) / ".local/bin/si"
            for container in ("tool_input", "input", "arguments"):
                for field in ("file_path", "path", "target_file"):
                    name = container + "-" + field
                    with self.subTest(container=container, field=field):
                        payload = {"tool_name": "read_file", container: {field: f"/a/skills/{name}/SKILL.md"}}
                        result = subprocess.run(
                            [sys.executable, str(launcher), "observe"], input=json.dumps(payload),
                            env=env, capture_output=True, text=True,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        events = (Path(td) / "st/events.jsonl").read_text()
                        self.assertIn('"skill":"' + name + '"', events)

    def test_malformed_read_payload_is_fail_open(self):
        with tempfile.TemporaryDirectory() as td:
            env = {**os.environ, "HOME": td, "AGENT_SKILL_ROUTER_STATE_DIR": str(Path(td) / "st")}
            with patch.dict(os.environ, env):
                mod.install("ggcoder")
            payloads = [
                {"tool_name": "Read", "tool_input": value}
                for value in (["bad"], "bad", 42)
            ] + [{"tool_name": value} for value in ([], {})]
            for payload in payloads:
                result = subprocess.run(
                    [sys.executable, str(Path(td) / ".local/bin/si"), "observe"],
                    input=json.dumps(payload),
                    env=env, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout + result.stderr, "")

    def test_failed_skill_read_is_not_counted_as_applied(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"HOME": td, "AGENT_SKILL_ROUTER_STATE_DIR": td}):
                for response in ({"status": "error"}, {"is_error": True}, {"isError": True}):
                    events = mod.observe_hook_payload({
                        "tool_name": "Read", "tool_input": {"file_path": "/skills/missing/SKILL.md"},
                        "tool_response": response,
                    })
                    self.assertEqual(events, [])
                self.assertFalse(mod.feedback_state_file().exists())

    def test_hook_command_quotes_paths_and_reinstall_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="router home ") as td:
            with patch.dict(os.environ, {"HOME": td}):
                command = mod.hook_command()
                self.assertEqual(shlex.split(command), [sys.executable, str(Path(td) / ".local/bin/si"), "observe"])
                self.assertTrue(mod.is_observer_command(command))
                for host in ("claude", "codex", "hermes"):
                    self.assertTrue(mod.install_hooks(host)[0]["changed"])
                    self.assertFalse(mod.install_hooks(host)[0]["changed"])
                    self.assertTrue(mod.hook_has_observer(host))


if __name__ == "__main__":
    unittest.main()
