#!/usr/bin/env bash
# Claude Code Stop hook — emit reminder if digital-brain vault stale.
#
# Stale signals:
#   - last_refresh_commit not in git history (pre-rebase orphan)
#   - HEAD diverged from last_refresh_commit by >= DIGITAL_BRAIN_STALE_COMMITS commits
#   - last_refresh older than DIGITAL_BRAIN_STALE_DAYS days
#
# Quiet (exit 0, no output) when fresh.
# When stale: emit JSON to stdout with `systemMessage` (UI) AND
# `hookSpecificOutput.additionalContext` (Claude's next-turn context),
# so the model knows to suggest /refresh-digital-brain.

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

# Resolve this script's real location (follow symlinks) → digital-brain dir
SCRIPT_PATH="$(readlink -f "$0" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$0")"
INSTALL_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
HELPERS_PY="$INSTALL_ROOT/helpers/.venv/bin/python"

DIGITAL_BRAIN_STALE_COMMITS="${DIGITAL_BRAIN_STALE_COMMITS:-5}"
DIGITAL_BRAIN_STALE_DAYS="${DIGITAL_BRAIN_STALE_DAYS:-7}"

[ -f .digital-brain-config.yaml ] || exit 0
[ -x "$HELPERS_PY" ] || exit 0
VAULT_DIR=$("$HELPERS_PY" -c "
import sys; sys.path.insert(0, '$INSTALL_ROOT/helpers/src')
from pathlib import Path
from digital_brain_helpers.config import load_config
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
    emit_stale "[digital-brain] vault refresh commit $REFRESH_SHA not in git history — suggest user run /refresh-digital-brain"
fi

# Distance check
DISTANCE=$(git rev-list --count "${REFRESH_SHA}..HEAD" 2>/dev/null || echo 0)
if [ "$DISTANCE" -ge "$DIGITAL_BRAIN_STALE_COMMITS" ]; then
    emit_stale "[digital-brain] vault is $DISTANCE commits behind HEAD — suggest user run /refresh-digital-brain"
fi

# Age check (mtime of _INDEX.md)
AGE_DAYS=$(( ( $(date +%s) - $(stat -f %m "$INDEX" 2>/dev/null || stat -c %Y "$INDEX") ) / 86400 ))
if [ "$AGE_DAYS" -ge "$DIGITAL_BRAIN_STALE_DAYS" ]; then
    emit_stale "[digital-brain] vault refresh is $AGE_DAYS days old — suggest user run /refresh-digital-brain"
fi

exit 0
