#!/usr/bin/env bash
set -euo pipefail
# Works from a checkout AND piped:
#   curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver-skill-router/main/install.sh | bash -s -- claude
target="${1:-all}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$script_dir" ] && [ -f "$script_dir/scripts/agent_token_saver.py" ]; then
  repo="$script_dir"
else
  repo="$(mktemp -d)/agent-token-saver-skill-router"
  git clone --quiet --depth 1 https://github.com/Supersynergy/agent-token-saver-skill-router.git "$repo"
fi
python3 "$repo/scripts/agent_token_saver.py" install --target "$target"
printf '\n%s\n%s\n' \
  'Installed agent-token-saver-skill-router.' \
  'Restart the target agent or start a fresh session so prompt caches rebuild.'
