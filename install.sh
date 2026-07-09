#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
target="${1:-all}"
python3 scripts/agent_token_saver.py install --target "$target"
cat <<'MSG'

Installed agent-token-saver-skill-router.
Restart the target agent or start a fresh session so prompt caches rebuild.
MSG
