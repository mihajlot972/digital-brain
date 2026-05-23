---
name: load-digital-brain
description: Load digital-brain INDEX into context as orientation for the current session. v0 = Scenario A only (default orientation).
---

# /load-digital-brain

Load `<vault_dir>/_INDEX.md` and inject it as a system reminder so subsequent steps in this session use the vault instead of reading source code first.

## Usage

```
/load-digital-brain
```

No arguments in v0. (Scenarios B and C — focused load and status — are v1.)

## What you (Claude) do when invoked

### Step 1 — Verify config and vault exist

```bash
INSTALL_ROOT="$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.digital-brain/install.json')))['install_root'])")"
HELPERS_VENV="$INSTALL_ROOT/helpers/.venv/bin/python"
test -f .digital-brain-config.yaml || { echo "ERROR: .digital-brain-config.yaml not found. Run /refresh-digital-brain after creating it."; exit 1; }
VAULT_DIR=$("$HELPERS_VENV" -c "
import sys; sys.path.insert(0, '$INSTALL_ROOT/helpers/src')
from pathlib import Path
from digital_brain_helpers.config import load_config
cfg = load_config(Path('.').resolve())
print(cfg.resolved_vault_dir())
")
test -d "$VAULT_DIR" || { echo "ERROR: vault dir $VAULT_DIR not found. Run /refresh-digital-brain first."; exit 1; }
test -f "$VAULT_DIR/_INDEX.md" || { echo "ERROR: $VAULT_DIR/_INDEX.md not found. Run /refresh-digital-brain first."; exit 1; }
```

### Step 2 — Read INDEX

Use Read tool on `$VAULT_DIR/_INDEX.md`. Inject the content into your context. Tell the user:

```
Brain loaded from <vault_dir>/.
- N extracted nodes
- M code-concept notes
- K communities
- Last refresh: <timestamp> (commit <sha>)
```

(Numbers come from the INDEX `Vault stats:` line.)

### Step 3 — Set the working principle for the rest of the session

For the rest of this session, follow this principle:

```
PROJECT BRAIN ACTIVE

Before reading raw source code from <source_paths>, check:
1. _INDEX.md (already loaded above)
2. Concept note (Read tool on <vault_dir>/<slug>.md) — short, concept-level
3. Extracted note (Read tool on <vault_dir>/<NodeName>.md) — if you need
   detail about a specific class/function
4. graphify-out/graph.json — for structural questions ("who calls X")

Read raw source code only if (a) the vault doesn't cover the question, or
(b) you're making an implementation change (vault is orientation, code is truth).

If the INDEX last_refresh is older than ~7 days OR the commit hash doesn't
match the current HEAD, suggest /refresh-digital-brain to the user.
```

After loading, briefly tell the user what you understand about the current vault state and ask what they want to work on.

## Errors

- `.digital-brain-config.yaml` not found → "Create config first; v1 will provide /init-digital-brain"
- Vault dir not found → "Run /refresh-digital-brain first"
- INDEX not found → "Run /refresh-digital-brain first"

Do not try to load anything if checks fail — proceed without vault context.

## Out of scope (v1+)

- Scenario B: `/load-digital-brain <keyword>` for focused note loading
- Scenario C: `/load-digital-brain --status` for stale check
- Auto-load via SessionStart hook
- MCP server integration (`graphify --mcp`)
