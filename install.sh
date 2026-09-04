#!/usr/bin/env bash
set -euo pipefail
# Works from a checkout AND piped:
#   curl -fsSL https://raw.githubusercontent.com/Supersynergy/agent-token-saver-skill-router/main/install.sh | bash -s -- claude
target="${1:-all}"

find_python() {
  local candidate resolved
  for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    resolved="$(command -v "$candidate" 2>/dev/null || true)"
    [[ -n "$resolved" ]] || continue
    case "$resolved" in */shims/*) continue ;; esac
    if "$resolved" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done
  resolved="$(command -v python3 2>/dev/null || true)"
  if [[ -n "$resolved" ]] && "$resolved" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    printf '%s\n' "$resolved"
    return 0
  fi
  return 1
}

router_python="$(find_python || true)"
[[ -n "$router_python" ]] || {
  echo "agent-token-saver-skill-router: Python 3.9+ is required on PATH (python3 or python3.X)" >&2
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

"$router_python" "$repo/scripts/agent_token_saver.py" install --target "$target"
printf '\n%s\n%s\n' \
  'Installed agent-token-saver-skill-router.' \
  'Restart the target agent or start a fresh session so prompt caches rebuild.'
