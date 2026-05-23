#!/usr/bin/env bash
# digital-brain SessionStart hook: auto-load INDEX or prompt to build.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
INSTALL_ROOT="$(cd "$HERE/.." && pwd)"
PYTHON="$INSTALL_ROOT/helpers/.venv/bin/python"
[[ -x "$PYTHON" ]] || exit 0
exec "$PYTHON" -m digital_brain_helpers.session_start "$@"
