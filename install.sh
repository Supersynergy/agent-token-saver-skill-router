#!/usr/bin/env bash
set -euo pipefail
# Works from a checkout AND piped:
#   curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver-skill-router/main/install.sh | bash -s -- claude
target="${1:-all}"

command -v python3 >/dev/null 2>&1 || {
  echo "agent-token-saver-skill-router: python3 is required (3.11+)" >&2
  exit 1
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$script_dir" ] && [ -f "$script_dir/scripts/agent_token_saver.py" ]; then
  repo="$script_dir"
else
  # Piped install: fetch a shallow copy and always clean it up, so a repeated
  # curl | bash never leaves clones behind in the temp directory.
  command -v git >/dev/null 2>&1 || {
    echo "agent-token-saver-skill-router: git is required for the piped install" >&2
    exit 1
  }
  tmp_root="$(mktemp -d)"
  trap 'rm -rf "$tmp_root"' EXIT INT TERM
  repo="$tmp_root/agent-token-saver-skill-router"
  repo_url="${ATSR_REPO_URL:-https://github.com/Supersynergy/agent-token-saver-skill-router.git}"
  git clone --quiet --depth 1 "$repo_url" "$repo"
fi

python3 "$repo/scripts/agent_token_saver.py" install --target "$target"
printf '\n%s\n%s\n' \
  'Installed agent-token-saver-skill-router.' \
  'Restart the target agent or start a fresh session so prompt caches rebuild.'
