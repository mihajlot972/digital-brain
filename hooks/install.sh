#!/usr/bin/env bash
# digital-brain installer: global symlinks + Claude Code hook registration.
# Idempotent — safe to re-run.
set -euo pipefail

# Resolve install root: dir containing this script's parent (hooks/'s parent)
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
INSTALL_ROOT="$(cd "$SCRIPT_PATH/.." && pwd)"

echo "Installing digital-brain from $INSTALL_ROOT"

# 1. Ensure target dirs exist
mkdir -p "$HOME/.claude/skills" "$HOME/.local/bin" "$HOME/.digital-brain"

# 2. Symlink skills
for skill in refresh-digital-brain load-digital-brain; do
    src="$INSTALL_ROOT/skills/$skill"
    dst="$HOME/.claude/skills/$skill"
    if [ -e "$dst" ] && [ ! -L "$dst" ]; then
        echo "WARNING: $dst exists and is not a symlink. Backing up to .bak"
        mv "$dst" "$dst.bak"
    fi
    ln -sf "$src" "$dst"
    echo "  symlinked $dst -> $src"
done

# 3. Symlink console script
HELPERS_BIN="$INSTALL_ROOT/helpers/.venv/bin/digital-brain"
if [ ! -x "$HELPERS_BIN" ]; then
    echo "ERROR: helpers venv missing. Run:" >&2
    echo "  cd $INSTALL_ROOT/helpers && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
    exit 1
fi
ln -sf "$HELPERS_BIN" "$HOME/.local/bin/digital-brain"
echo "  symlinked $HOME/.local/bin/digital-brain"

# 4. PATH check
if ! echo ":$PATH:" | grep -q ":$HOME/.local/bin:"; then
    SHELL_NAME="$(basename "${SHELL:-bash}")"
    case "$SHELL_NAME" in
        zsh)  RC_FILE="$HOME/.zshrc" ;;
        bash) RC_FILE="$HOME/.bashrc" ;;
        *)    RC_FILE="your shell rc file" ;;
    esac
    echo "  WARNING: ~/.local/bin is not on \$PATH. Add this to $RC_FILE:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# 5. Make hooks executable
chmod +x \
    "$INSTALL_ROOT/hooks/post-commit" \
    "$INSTALL_ROOT/hooks/auto_refresh.py" \
    "$INSTALL_ROOT/hooks/stale_check.sh" \
    "$INSTALL_ROOT/hooks/session_start.sh"

# 6. Patch ~/.claude/settings.json (idempotent)
HELPERS_PY="$INSTALL_ROOT/helpers/.venv/bin/python"
"$HELPERS_PY" -m digital_brain_helpers.install_helpers patch \
    "$HOME/.claude/settings.json" "$INSTALL_ROOT"
echo "  patched ~/.claude/settings.json"

# 7. Write install.json — LAST state-mutating step (only print follows)
VERSION="$("$HELPERS_PY" -c "
from importlib.metadata import version
print(version('digital-brain-helpers'))
" 2>/dev/null || echo "0.1.0")"
"$HELPERS_PY" -m digital_brain_helpers.install_helpers install-json \
    "$HOME/.digital-brain/install.json" "$INSTALL_ROOT" "$VERSION"
echo "  wrote ~/.digital-brain/install.json"

# 8. Post-install message
cat <<EOF

Install complete. Installed at: $INSTALL_ROOT

  Per-project setup (run inside a host repo):
    cat > .digital-brain-config.yaml <<'CFG'
source_paths:
  - src/
vault_dir: digital-brain/
CFG
    echo "digital-brain/" >> .gitignore
    ln -sf "$INSTALL_ROOT/hooks/post-commit" .git/hooks/post-commit

  Then run \`claude\` in that repo — you will be prompted to build the brain.

  Removal:
    digital-brain remove       # remove from current project (preserves concept notes)
    digital-brain uninstall    # remove global install
EOF
