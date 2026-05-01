#!/usr/bin/env bash
# Claude Code Stop hook — emit reminder if private-brain vault stale.
#
# Stale signals:
#   - last_refresh_commit not in git history (pre-rebase orphan)
#   - HEAD diverged from last_refresh_commit by >= STALE_COMMITS commits
#   - last_refresh older than STALE_DAYS days
#
# Quiet (exit 0, no output) when fresh.
# When stale: emit JSON to stdout with `systemMessage` (UI) AND
# `hookSpecificOutput.additionalContext` (Claude's next-turn context),
# so the model knows to suggest /refresh-brain.

emit_stale() {
    local msg="$1"
    # JSON-encode message safely
    local json_msg
    json_msg=$(printf '%s' "$msg" | sed 's/\\/\\\\/g; s/"/\\"/g')
    cat <<EOF
{"systemMessage": "$json_msg", "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": "$json_msg"}}
EOF
    exit 0
}

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$REPO_ROOT"

# Resolve this script's real location (follow symlinks) → private-brain dir
SCRIPT_PATH="$(readlink -f "$0" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$0")"
PRIVATE_BRAIN_DIR="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
HELPERS_PY="$PRIVATE_BRAIN_DIR/helpers/.venv/bin/python"

STALE_COMMITS="${STALE_COMMITS:-5}"
STALE_DAYS="${STALE_DAYS:-7}"

[ -f .brain-config.yaml ] || exit 0
[ -x "$HELPERS_PY" ] || exit 0
VAULT_DIR=$("$HELPERS_PY" -c "
import sys; sys.path.insert(0, '$PRIVATE_BRAIN_DIR/helpers')
from pathlib import Path
from config import load_config
print(load_config(Path('.').resolve()).resolved_vault_dir())
" 2>/dev/null) || exit 0

INDEX="$VAULT_DIR/_INDEX.md"
[ -f "$INDEX" ] || exit 0

REFRESH_SHA=$(awk -F': ' '/^last_refresh_commit:/ {print $2; exit}' "$INDEX" | tr -d ' ')
HEAD_SHA=$(git rev-parse --short HEAD 2>/dev/null) || exit 0

[ -n "$REFRESH_SHA" ] || exit 0

# Same commit → fresh
[ "$REFRESH_SHA" = "$HEAD_SHA" ] && exit 0

# Commit gone (rebased away)?
if ! git cat-file -e "$REFRESH_SHA" 2>/dev/null; then
    emit_stale "[private-brain] vault refresh commit $REFRESH_SHA not in git history — suggest user run /refresh-brain"
fi

# Distance check
DISTANCE=$(git rev-list --count "${REFRESH_SHA}..HEAD" 2>/dev/null || echo 0)
if [ "$DISTANCE" -ge "$STALE_COMMITS" ]; then
    emit_stale "[private-brain] vault is $DISTANCE commits behind HEAD — suggest user run /refresh-brain"
fi

# Age check (mtime of _INDEX.md)
AGE_DAYS=$(( ( $(date +%s) - $(stat -f %m "$INDEX" 2>/dev/null || stat -c %Y "$INDEX") ) / 86400 ))
if [ "$AGE_DAYS" -ge "$STALE_DAYS" ]; then
    emit_stale "[private-brain] vault refresh is $AGE_DAYS days old — suggest user run /refresh-brain"
fi

exit 0
