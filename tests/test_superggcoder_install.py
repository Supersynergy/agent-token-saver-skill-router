import importlib.util
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sgg_install", ROOT / "scripts/install_superggcoder.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class SuperGGInstallTests(unittest.TestCase):
    def test_launcher_block_is_idempotent_and_quotes_paths(self):
        text = "#!/bin/bash\n" + mod.ANCHOR + "\n"
        module = Path("/test home/lib/superggcoder.mjs")
        updated = mod.launcher_text(text, module)
        self.assertEqual(updated, mod.launcher_text(updated, module))
        self.assertIn("test%20home", updated)
        self.assertIn("SGG_TOKEN_SAVER:-1", updated)
        self.assertTrue(updated.endswith(mod.ANCHOR + "\n"))
        subprocess.run(["bash", "-n"], input=updated, text=True, check=True)

    def test_unknown_or_malformed_launcher_refused(self):
        for text in [
            "exec something-else",
            mod.START + "\n" + mod.ANCHOR,
            mod.END + mod.START + mod.ANCHOR,
        ]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                mod.launcher_text(text, Path("/module.mjs"))

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_node_contract(self):
        result = subprocess.run(
            ["node", "--test", str(ROOT / "tests/test_superggcoder.mjs")],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
