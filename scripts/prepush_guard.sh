#!/bin/bash
# pre-push guard: block any push whose tracked content matches a secret pattern
# or a banned term. Banned terms live in .guard/banned_patterns.txt, which is
# gitignored ON PURPOSE - the list itself must never ship with the repo.
# Scans the TRACKED TREE AT HEAD (what a push actually publishes), not the
# working directory.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

fail=0
scan() {  # scan <label> <grep-args...>
  local label="$1"; shift
  # git grep --cached searches tracked blobs at HEAD; returns 1 when clean.
  if git grep -nI --cached "$@" -- . 2>/dev/null; then
    echo "BLOCKED: $label found in tracked content (above)." >&2
    fail=1
  fi
}

# Secret patterns (see ~/.claude/CLAUDE.md checklist)
GH='gh[ops]_[A-Za-z0-9]{20,}|github_''pat_'   # split: never match this script
scan "GitHub token"        -E "$GH"
scan "API key (sk-)"       -E 'sk-(ant-)?[A-Za-z0-9_-]{20,}'
scan "AWS key"             -E 'AKIA[A-Z0-9]{16}|ASIA[A-Z0-9]{16}'
scan "Slack token"         -E 'xox[baprs]-[A-Za-z0-9-]{10,}'
scan "Google key"          -E 'AIza[A-Za-z0-9_-]{30,}'
PK="-----""BEGIN"   # split so this script never matches itself
scan "Private key block"   -F -- "$PK"
scan "JWT"                 -E 'eyJ[A-Za-z0-9_-]{10,}\.eyJ'

# Banned terms (employer/vendor names, personal paths) - untracked list
if [ -f .guard/banned_patterns.txt ]; then
  while IFS= read -r pat; do
    [ -z "$pat" ] && continue
    scan "banned term '$pat'" -i -F -- "$pat"
  done < .guard/banned_patterns.txt
else
  echo "WARNING: .guard/banned_patterns.txt missing - banned-term scan skipped." >&2
fi

if [ "$fail" -ne 0 ]; then
  echo "Push blocked by prepush_guard. Remove the flagged content and re-commit." >&2
  exit 1
fi
echo "prepush_guard: clean."
