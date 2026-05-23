#!/usr/bin/env bash
# Install digital-brain hooks into a host project's .git/hooks + skills into .claude/skills.
# Run from inside the host project.
#
# Usage:
#   bash /path/to/digital-brain/hooks/install.sh
#
# Idempotent — safe to re-run.

set -euo pipefail

# Resolve this script's real location → digital-brain dir
SCRIPT_PATH="$(readlink -f "$0" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$0")"
DIGITAL_BRAIN_DIR="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"

HOST_REPO="$(git rev-parse --show-toplevel)"
cd "$HOST_REPO"

# 1. Ensure hook scripts executable
chmod +x \
    "$DIGITAL_BRAIN_DIR/hooks/post-commit" \
    "$DIGITAL_BRAIN_DIR/hooks/auto_refresh.py" \
    "$DIGITAL_BRAIN_DIR/hooks/stale_check.sh" 2>/dev/null || true

# 2. Symlink post-commit into host's .git/hooks
mkdir -p .git/hooks
if [ -e .git/hooks/post-commit ] && [ ! -L .git/hooks/post-commit ]; then
    echo "WARNING: .git/hooks/post-commit exists and is not a symlink. Backing up to .bak."
    mv .git/hooks/post-commit .git/hooks/post-commit.bak
fi
ln -sf "$DIGITAL_BRAIN_DIR/hooks/post-commit" .git/hooks/post-commit
echo "Installed: .git/hooks/post-commit -> $DIGITAL_BRAIN_DIR/hooks/post-commit"

# 3. Symlink skills into host's .claude/skills
mkdir -p .claude/skills
for skill in refresh-brain load-brain; do
    if [ -e ".claude/skills/$skill" ] && [ ! -L ".claude/skills/$skill" ]; then
        echo "WARNING: .claude/skills/$skill exists and is not a symlink. Backing up."
        mv ".claude/skills/$skill" ".claude/skills/${skill}.bak"
    fi
    ln -sf "$DIGITAL_BRAIN_DIR/skills/$skill" ".claude/skills/$skill"
    echo "Installed: .claude/skills/$skill -> $DIGITAL_BRAIN_DIR/skills/$skill"
done

# 4. Done
echo
echo "digital-brain hooks + skills installed."
echo
echo "Next steps:"
echo "  1. Write .digital-brain-config.yaml at host repo root (see digital-brain/README.md)."
echo "  2. Add Stop hook to .claude/settings.local.json (see README — points to:"
echo "     $DIGITAL_BRAIN_DIR/hooks/stale_check.sh)"
echo "  3. Make sure helpers venv exists:"
echo "     cd $DIGITAL_BRAIN_DIR/helpers && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
echo "  4. Run /refresh-brain in a Claude session for the first vault build."
