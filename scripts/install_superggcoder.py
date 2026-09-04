"""Install the native GG observer and an opt-out compact catalog in an existing sgg launcher."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

START = "# AGENT-SKILL-ROUTER-SUPERGG:START"
END = "# AGENT-SKILL-ROUTER-SUPERGG:END"
ANCHOR = 'exec node $V8_FLAGS "$REAL" "$@"'


def launcher_text(original, module):
    if original.count(START) != original.count(END) or original.count(START) > 1:
        raise ValueError("Malformed managed block; launcher unchanged")
    if START in original:
        start = original.index(START)
        stop = original.index(END) + len(END)
        if original.index(END) < start:
            raise ValueError("Malformed managed block; launcher unchanged")
        original = original[:start] + original[stop:].lstrip("\n")
    if original.count(ANCHOR) != 1:
        raise ValueError("Unsupported sgg launcher; expected one native exec anchor")
    block = "\n".join(
        [
            START,
            "export AGENT_SKILL_ROUTER_HOST=superggcoder",
            'export SGG_TOKEN_SAVER_ROOT="$SGG_DIST"',
            'if [ "${SGG_TOKEN_SAVER:-1}" != "0" ]; then',
            "  _ats_import=" + shlex.quote("--import " + module.as_uri()),
            '  case "${NODE_OPTIONS:-}" in',
            '    *"$_ats_import"*) ;;',
            '    *) export NODE_OPTIONS="${NODE_OPTIONS:-} $_ats_import" ;;',
            "  esac",
            "  unset _ats_import",
            "fi",
            END,
            "",
        ]
    )
    return original.replace(ANCHOR, block + ANCHOR)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path, default=Path.home() / ".local/bin/sgg")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    launcher = args.launcher.expanduser().resolve()
    original = launcher.read_text()
    module = Path.home() / ".local/lib/agent-token-saver-skill-router/superggcoder.mjs"
    updated = launcher_text(original, module)
    subprocess.run(["bash", "-n"], input=updated, text=True, check=True)
    changed = updated != original
    backup = launcher.with_name(
        launcher.name + ".before-ats-" + hashlib.sha256(original.encode()).hexdigest()[:12]
    )
    if not args.dry_run:
        source = Path(__file__).resolve().parent
        subprocess.run(
            [
                sys.executable,
                str(source / "agent_token_saver.py"),
                "install",
                "--target",
                "ggcoder",
            ],
            check=True,
            stdout=subprocess.PIPE,
        )
        shutil.copyfile(source / "superggcoder.mjs", module)
        if changed:
            if not backup.exists():
                shutil.copy2(launcher, backup)
            staged = launcher.with_name(launcher.name + ".ats-new")
            try:
                staged.write_text(updated)
                staged.chmod(launcher.stat().st_mode)
                os.replace(staged, launcher)
            finally:
                staged.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "launcher": str(launcher),
                "module": str(module),
                "changed": changed,
                "dry_run": args.dry_run,
                "backup": str(backup) if changed else None,
            }
        )
    )


if __name__ == "__main__":
    main()
