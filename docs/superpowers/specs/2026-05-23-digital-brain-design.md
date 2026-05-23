---
title: digital-brain — standalone rename + auto-load/build/connect
date: 2026-05-23
status: approved
---

# digital-brain — standalone rename + auto-load/build/connect

## 1. Goals + Scope

### Goal

Extract the existing `private-brain` project into a standalone repo named `digital-brain`. Scrub every reference to `private-gpt` / `private-gpt-fork` / `private-brain` from code, configs, and docs. Add three frictionless behaviors so the tool feels seamless:

1. On every new Claude session in a brain-enabled project, either auto-load the brain INDEX (if vault exists) or prompt the user to build it (if vault missing).
2. On every `git commit` that touches source paths, auto-refresh the extracted node layer.
3. On first successful build, auto-register the vault with Obsidian so it appears in the vault picker.

Bidirectional node references: when Claude cites a node it emits both an Obsidian deep link and a `source:line` reference; when the user pastes `[[NodeName]]` in chat, the skill resolves it to a vault file and Claude reads it.

### In scope

1. Rename directory `~/Projects/private-brain` → `~/Projects/digital-brain`.
2. Full identifier rename — package, modules, env vars, config file, skill ids — to `digital_brain` / `digital-brain` prefix. Internal helper function names (e.g. `load_config`) stay unchanged where they don't carry the old prefix; only the namespace is rebadged.
3. Strip every `private-gpt` / `private-gpt-fork` mention from README and plan docs.
4. New `hooks/session_start.sh` (delegates to `digital_brain_helpers.session_start`): SessionStart hook that auto-loads INDEX or prompts to build.
5. New `helpers/src/digital_brain_helpers/obsidian_register.py`: writes vault path into Obsidian's `obsidian.json` so vault appears in app.
6. New citation format convention: Claude emits `[[NodeName]] ([source](path#Lline), [vault](obsidian://...))` on first reference per turn.
7. New wikilink resolver convention: user `[[NodeName]]` in chat triggers vault file read.
8. New `helpers/src/digital_brain_helpers/cli.py` with subcommands `remove` (per-project) and `uninstall` (global), exposed as `digital-brain` console script.
9. Refactor `helpers/` flat layout to `src/digital_brain_helpers/` layout to avoid import shadowing after rename.
10. Concept-note preservation on `digital-brain remove` via `~/.digital-brain-graveyard/` copies.

### Out of scope (deferred to v1)

- `/init-brain` auto-bootstrap of `.digital-brain-config.yaml`.
- Incremental refresh.
- LLM-driven community labels.
- `type: business` notes.
- Focused `/load-brain <keyword>`.
- File-watcher daemon (rejected — commit trigger is cheaper and batches changes).
- Backward compat with old `.brain-config.yaml` (hard break — clean rename).
- Windows support for `obsidian_register` (logs warning, no-op).
- Lockfile coordination between concurrent refresh + uninstall.

### Hard break

Existing host repo (`private-gpt-fork`) will not work after extraction without manual rename of its `.brain-config.yaml` → `.digital-brain-config.yaml` and re-symlinking its post-commit hook. Acceptable per user direction ("I want this separate").

## 2. Rename Map

### Project-wide rename table

| Old | New | Where |
|-----|-----|-------|
| `private-brain` (dir, repo, project name) | `digital-brain` | dir, README, docs |
| `brain-helpers` (pyproject `name`) | `digital-brain-helpers` | `helpers/pyproject.toml` |
| `brain_helpers` (import name) | `digital_brain_helpers` | imports in tests + hooks |
| `.brain-config.yaml` (per-project config file) | `.digital-brain-config.yaml` | hooks, skills, README |
| skill id `refresh-brain` | `refresh-digital-brain` | `skills/<id>/SKILL.md` `name:` field + dir name |
| skill id `load-brain` | `load-digital-brain` | same |
| `/refresh-brain`, `/load-brain` slash invocations | `/refresh-digital-brain`, `/load-digital-brain` | all docs |
| `project-brain/` (default vault dir) | `digital-brain/` | default in `helpers/config.py`, README examples |
| `STALE_COMMITS`, `STALE_DAYS` env vars | `DIGITAL_BRAIN_STALE_COMMITS`, `DIGITAL_BRAIN_STALE_DAYS` | `hooks/stale_check.sh`, docs |
| Any other `BRAIN_*` env var | `DIGITAL_BRAIN_*` | grep audit |
| `private-gpt-fork`, `private_gpt/` (host repo refs in examples) | `<host-repo>/`, `<src-dir>/` | README, plan docs |
| Concept-note examples mentioning private-gpt internals | replaced with generic placeholders | plan docs only — README example section deleted |
| `last_refresh_commit` (INDEX frontmatter key) | unchanged | already neutral |

### Identifier interpretation

Package namespace is rebadged with `digital_brain` prefix. Internal function/method names (`load_config`, `write_index`, etc.) are not renamed because they don't carry the old `brain` prefix. Goal is to make `from digital_brain_helpers import config` work, not to mechanically prefix every function name.

Hook script names (`auto_refresh.py`, `stale_check.sh`, `install.sh`) stay neutral. Their *contents* get the rename pass for strings and paths.

## 3. New Components

Four new pieces, each with a single purpose and a well-defined interface.

### 3.1 SessionStart hook — `hooks/session_start.py` + `hooks/session_start.sh`

**Purpose:** decide between auto-load vs build-prompt at session start.

**Inputs:** reads `.digital-brain-config.yaml` at cwd, walking up the tree until found or root reached.

**Logic:**

```
if no .digital-brain-config.yaml found:
    exit 0 (silent — not a brain project)
elif vault_dir missing OR vault_dir/_INDEX.md missing:
    emit additionalContext:
        "No digital-brain vault detected for this project.
         Run /refresh-digital-brain to build it (~1-3 min, will write to <vault_dir>)."
else:
    emit additionalContext: <contents of _INDEX.md>   (~2k tok auto-load)
exit 0
```

**Output:** Claude Code SessionStart hook JSON. Both `hookEventName` and `hookSpecificOutput.additionalContext` are required by the Claude Code hook protocol:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "..."
  }
}
```

**Size cap:** `additionalContext` is capped at 10,000 characters by Claude Code. `_INDEX.md` is targeted at ~2k tokens (~8-10k chars). `session_start.py` checks length; if `_INDEX.md` exceeds 9,500 chars it injects a truncated head + a one-line pointer ("INDEX truncated — full file at `<vault_dir>/_INDEX.md`, read it to see all entries") so Claude can pull the full file on demand.

**Implementation split:** the Python module lives at `helpers/src/digital_brain_helpers/session_start.py` (so pytest can import it as `from digital_brain_helpers.session_start import main`). `hooks/session_start.sh` is a small wrapper that resolves its own location and invokes the helpers venv — making it install-location-agnostic:

```bash
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
INSTALL_ROOT="$(cd "$HERE/.." && pwd)"
PYTHON="$INSTALL_ROOT/helpers/.venv/bin/python"
# Guard: if venv was deleted, exit cleanly so the hook doesn't error in every
# Claude session. User will see no brain context but normal sessions still work.
[[ -x "$PYTHON" ]] || exit 0
exec "$PYTHON" -m digital_brain_helpers.session_start "$@"
```

The hook file in `hooks/` is therefore a thin shell wrapper only; all logic + tests live in the helpers package. No hardcoded install path.

**Why a hook instead of skill auto-invoke:** skills only run when the user invokes them. SessionStart hook is the only Claude Code mechanism that can inject context before the user's first message of a session.

### 3.2 Obsidian register helper — `helpers/src/digital_brain_helpers/obsidian_register.py`

**Purpose:** add vault path to Obsidian's vault list so the user can open the vault with one click from Obsidian's launcher.

**Interface:**

```python
def register_vault(vault_path: Path) -> RegisterResult:
    """Add vault_path to platform-specific obsidian.json.

    No-op if already registered, if obsidian.json missing (Obsidian not
    installed), or on unsupported platform. Returns RegisterResult with
    .status in {"registered", "already_present", "obsidian_not_installed",
    "unsupported_platform"} and .message for the caller to log/display.
    """

def unregister_vault(vault_path: Path) -> RegisterResult:
    """Remove vault_path from platform-specific obsidian.json.

    Removes the entry whose `path` field equals str(vault_path.resolve()).
    No-op if not registered or obsidian.json missing. Returns RegisterResult
    with .status in {"unregistered", "not_present", "obsidian_not_installed",
    "unsupported_platform"}.
    """
```

**Platform paths:**

| Platform | obsidian.json path |
|----------|--------------------|
| macOS | `~/Library/Application Support/obsidian/obsidian.json` |
| Linux | `~/.config/obsidian/obsidian.json` |
| Windows | `%APPDATA%/obsidian/obsidian.json` (v0: no-op + warning) |

**File format:** Obsidian stores vaults as:

```json
{
  "vaults": {
    "<uuid>": {
      "path": "/absolute/vault/path",
      "ts": 1716422400000,
      "open": false
    }
  }
}
```

`register_vault` generates the vault id as `uuid.uuid4().hex[:16]` (first 16 hex chars of a uuid4 — matches Obsidian's stored format), generates `ts` as `int(time.time() * 1000)`, adds the entry, and atomically writes back via `tempfile.NamedTemporaryFile` in the same dir + `os.replace`.

**Called from:** final step of `/refresh-digital-brain` skill (after vault build completes). Not from `install.sh` — at install time the vault doesn't exist yet.

**Failure behavior:** never raises on missing config. Raises on malformed JSON with a clear message; does not truncate the file. Logs a warning if Obsidian is open at write time (user should quit + reopen to pick up the new vault entry).

### 3.3 Citation formatter — built into both skills (prompt convention)

**Purpose:** when Claude cites a vault node, output both an Obsidian deep link and a source `file:line` reference so the user can click either.

**Format Claude must emit on first reference per turn:**

```
[[NodeName]] ([source](src/path.py#L42), [vault](obsidian://open?vault=<vault-name>&file=NodeName.md))
```

Subsequent mentions in the same turn may use bare `[[NodeName]]` to reduce noise.

**Implementation:** two-line instruction added to `load-digital-brain/SKILL.md` and `refresh-digital-brain/SKILL.md` telling Claude the format and the noise-reduction rule. No new code.

**URL encoding:** vault names and file names with spaces or other reserved chars must be percent-encoded (use `urllib.parse.quote`). The skills' instructions will note this; the citation format example uses a representative safe name. The `.md` file extension in the `file=` query param is optional for Obsidian's URL scheme but always emitted for clarity.

### 3.4 Wikilink resolver — built into `load-digital-brain` skill (prompt convention)

**Purpose:** when the user types `[[NodeName]]` in chat, the skill knows to Read the corresponding vault file before answering, without grep.

**Instruction added to `load-digital-brain/SKILL.md`:**

> If a user message contains `[[NodeName]]`, resolve `NodeName` to `<vault_dir>/<NodeName>.md`. If the exact filename does not exist, glob for `<vault_dir>/**/<NodeName>.md` (handles community-level filenames). Read the resolved file before responding. If no match found, say so explicitly rather than guessing.

No new code — pure prompt-level convention enforced by the skill.

### Boundary check

| Unit | What it does | How you use it | What it depends on |
|------|--------------|----------------|--------------------|
| `session_start.py` | Decides load vs prompt at session start | Invoked by `session_start.sh` wrapper via Claude Code hook | `.digital-brain-config.yaml` schema + vault `_INDEX.md` existence |
| `obsidian_register.py` | Writes vault path into Obsidian config | Called from refresh skill final step | OS config dir + `obsidian.json` JSON format |
| Citation format | Tells Claude how to cite nodes | Always-on convention | Skill prompts only |
| Wikilink resolver | Tells Claude how to read user-pasted `[[X]]` | Always-on convention | Skill prompts only |

Each unit can be reasoned about and tested in isolation.

## 4. File Layout

### `~/Projects/digital-brain/` (post-rename — `<install_root>` in examples below; user may clone anywhere)

```
~/Projects/digital-brain/
├── README.md                                              # rewritten — no private-gpt refs
├── docs/
│   ├── plan-v0-mvp.md                                     # scrubbed
│   ├── plan-v1-full.md                                    # scrubbed
│   └── superpowers/specs/2026-05-23-digital-brain-design.md
├── skills/
│   ├── refresh-digital-brain/SKILL.md
│   └── load-digital-brain/SKILL.md
├── helpers/
│   ├── pyproject.toml                                     # name = "digital-brain-helpers"
│   ├── src/digital_brain_helpers/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── frontmatter.py
│   │   ├── index_writer.py
│   │   ├── obsidian_register.py                           # NEW (3.2)
│   │   ├── session_start.py                               # NEW (3.1) — testable logic, invoked by hooks/session_start.sh
│   │   └── cli.py                                         # NEW (4.5)
│   └── tests/
│       ├── conftest.py
│       ├── test_config.py
│       ├── test_frontmatter.py
│       ├── test_index_writer.py
│       ├── test_obsidian_register.py                      # NEW
│       ├── test_cli.py                                    # NEW
│       └── test_session_start.py                          # NEW (tests digital_brain_helpers.session_start)
└── hooks/
    ├── install.sh                                         # rewritten — global symlinks + JSON merge
    ├── post-commit                                        # unchanged behavior, paths updated
    ├── auto_refresh.py                                    # paths + config filename updated
    ├── stale_check.sh                                     # PRE-EXISTING, behavior unchanged; only env var names renamed
    └── session_start.sh                                   # NEW (3.1) — 4-line wrapper to digital_brain_helpers.session_start
```

### Why `src/` layout for helpers

The flat layout (`helpers/config.py`) works with `pip install -e .` but can shadow installed packages and makes the import name ambiguous. Standard packaging guidance is `src/<package_name>/` layout. Moving while renaming is the cheapest moment to refactor; the alternative is doing it later as a separate churn.

### Per-project (consumer repo) layout

```
<host-repo>/
├── .digital-brain-config.yaml          # COMMIT — source_paths, vault_dir
├── digital-brain/                      # GITIGNORED — generated vault
├── .claude/settings.local.json         # optional per-project overrides
└── .git/hooks/post-commit              # symlink → <install_root>/hooks/post-commit
```

### Global (user-level, set once by `install.sh`)

```
~/.claude/skills/refresh-digital-brain  →  <install_root>/skills/refresh-digital-brain
~/.claude/skills/load-digital-brain     →  <install_root>/skills/load-digital-brain
~/.claude/settings.json                 # SessionStart + Stop hooks registered globally
~/.local/bin/digital-brain              →  wrapper that invokes helpers venv `digital-brain` console script
~/.digital-brain/install.json           # install metadata (see "Install metadata" below)
```

**Settings file policy:** `install.sh` writes only to `~/.claude/settings.json`. The user's `~/.claude/settings.local.json` (and any project-level `.claude/settings.local.json`) is never touched, never read, never validated. If the user has SessionStart or Stop entries in `settings.local.json` they will coexist with ours — Claude Code merges hook arrays from both files, and our entries are uniquely identified by the `command` path resolving under `<install_root>/hooks/` so removal can later target only ours.

**Install metadata** (`~/.digital-brain/install.json`):

```json
{
  "install_root": "/Users/<user>/Projects/digital-brain",
  "installed_at": "2026-05-23T14:30:00Z",
  "version": "0.1.0"
}
```

Written by `install.sh` as its final step on success (see §5 ordering). Read by `cli.py` (`remove` + `uninstall` subcommands) to discover where digital-brain is installed instead of hardcoding any path. Lets the user `git clone` to any path.

**Discovery fallback chain (`cli.py` resolves `install_root`):**

1. Read `~/.digital-brain/install.json`. If present and parses cleanly and `install_root` field exists **and `Path(install_root).is_dir()` is true**, use it.
2. If `install.json` is missing, unparseable, lacks the field, **or points at a deleted/moved dir**, fall back to `os.readlink("~/.local/bin/digital-brain")`. Walk up to the dir containing `pyproject.toml` and `hooks/` — that's the install root. Use it.
3. If that also fails (symlink missing or doesn't resolve to a recognizable install layout), print clear error: "Cannot locate digital-brain install root. Reinstall via `bash <repo>/hooks/install.sh` or remove manually." Exit 1 with non-destructive behavior.

Because `install.sh` writes `install.json` last (after all symlinks + settings.json patch succeed), the presence of `install.json` is a reliable signal of a fully-installed state; absence indicates either a clean machine or a partial install.

Global symlinks mean any project with `.digital-brain-config.yaml` works without additional setup — install once, every project benefits.

## 4.5. Removal

Two scopes of removal — different mechanisms, both invoked via the `digital-brain` console script.

### Per-project — `digital-brain remove`

Run from inside the host repo.

**Logic:**

1. Verify cwd has `.digital-brain-config.yaml`. Exit 1 with clear message if not.
2. Print plan and confirm:

   ```
   Remove digital-brain from <cwd>?
   This will:
     - delete <vault_dir>/  (preserves concept notes to ~/.digital-brain-graveyard/<project>-<timestamp>/ first)
     - delete .digital-brain-config.yaml
     - delete .git/hooks/post-commit symlink (only if it resolves to our hook)
     - unregister vault from Obsidian
   Continue? (y/N)
   ```

3. If confirmed:
   - Walk `<vault_dir>` for files with `layer: concept` frontmatter (schema unchanged from v0 — defined in `digital_brain_helpers.frontmatter` and consumed by `index_writer.py`; see existing `helpers/src/digital_brain_helpers/index_writer.py` for the discriminator check), copy them to the graveyard dir.
   - `rm -rf <vault_dir>/`.
   - `rm .digital-brain-config.yaml`.
   - If `.git/hooks/post-commit` is a symlink and resolves under `<install_root>/hooks/` (from `install.json`), remove it. Otherwise leave alone and print "post-commit hook is not ours, leaving in place."
   - Remove vault entry from `obsidian.json` via `obsidian_register.unregister_vault(vault_path)` (inverse of `register_vault` — see §3.2 interface).
4. Print summary of what was removed and where graveyard copy lives.

**Flags (v0, shared by both `remove` and `uninstall`):**

- `--yes` / `-y` — skip confirmation (intended for tests and scripting). Both subcommands accept it.
- No `--force` flag in v0. If the user wants a no-graveyard removal, they can `rm -rf` the vault first then run `remove`; we'll see the vault is gone and skip the graveyard step.

**Project name derivation (for graveyard path `~/.digital-brain-graveyard/<project>-<timestamp>/`):**

1. If cwd is inside a git repo, use the basename of the git toplevel (`git rev-parse --show-toplevel | xargs basename`).
2. Else, use the basename of cwd.
3. Sanitize: replace any char not in `[A-Za-z0-9._-]` with `_`.
4. Timestamp is `YYYYMMDD-HHMMSS` (UTC). Sub-second collisions impossible at human pace; if they ever occur, fall back to appending a 4-char uuid suffix.

### Global — `digital-brain uninstall`

Run from anywhere.

**Logic:**

1. Confirm: "Uninstall digital-brain globally? This removes skill symlinks and hook entries from ~/.claude/. Per-project brains (vault, config, post-commit) are NOT removed."
2. Remove `~/.claude/skills/refresh-digital-brain` and `~/.claude/skills/load-digital-brain` symlinks (only if they resolve under `<install_root>/`, read from `~/.digital-brain/install.json`).
3. Patch `~/.claude/settings.json`: remove only hook entries whose `command` path resolves under `<install_root>/hooks/`. Leave all other hooks intact. `~/.claude/settings.local.json` is not touched.
4. Remove `~/.local/bin/digital-brain` symlink (only if it resolves under `<install_root>/`).
5. Remove `~/.digital-brain/install.json` (and the `~/.digital-brain/` dir if empty).
6. Print: "Source repo at `<install_root>` left intact. `rm -rf` manually if you want it gone. Per-project brains not removed — run `digital-brain remove` inside each project first."

Two-step on purpose: global uninstall must not silently nuke every project's concept notes.

### New CLI entry point

`helpers/pyproject.toml`:

```toml
[project.scripts]
digital-brain = "digital_brain_helpers.cli:main"
```

`cli.py` is a thin argparse dispatcher with subcommands `remove` and `uninstall`. Each subcommand lives in its own function (`cmd_remove`, `cmd_uninstall`) so the dispatcher stays small and unit tests target the functions directly.

### `install.sh` final message

After install completes, print (with `$INSTALL_ROOT` substituted in by the script — not left as a literal placeholder):

```
Install complete. Installed at: $INSTALL_ROOT

  Per-project setup (run inside a host repo):
    echo "source_paths: [src/]
    vault_dir: digital-brain/" > .digital-brain-config.yaml
    echo "digital-brain/" >> .gitignore
    ln -sf "$INSTALL_ROOT/hooks/post-commit" .git/hooks/post-commit

  Then run `claude` in that repo — you will be prompted to build the brain.

  Removal:
    digital-brain remove       # remove from current project (preserves concept notes)
    digital-brain uninstall    # remove global install
```

## 5. Install + Uninstall Flow (end-to-end)

### One-time global install

```bash
git clone <repo> ~/Projects/digital-brain
cd ~/Projects/digital-brain/helpers
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -v                              # expect green
cd ..
bash hooks/install.sh
```

`install.sh` performs (`<install_root>` = absolute path to the directory containing `install.sh` itself, resolved via `cd "$(dirname "$0")/.." && pwd`):

Script uses `set -euo pipefail` so any failed step aborts the install before subsequent steps run. The `install.json` write is deliberately the **last state-mutating step** (only `print` follows), so its presence on disk is a true "fully installed" signal — exactly how `cli.py` uses it for discovery (§4).

1. `mkdir -p ~/.claude/skills ~/.local/bin ~/.digital-brain`.
2. `ln -sf <install_root>/skills/refresh-digital-brain ~/.claude/skills/refresh-digital-brain`.
3. `ln -sf <install_root>/skills/load-digital-brain ~/.claude/skills/load-digital-brain`.
4. Symlink the console script: `ln -sf <install_root>/helpers/.venv/bin/digital-brain ~/.local/bin/digital-brain`.
5. Check if `~/.local/bin` is on `$PATH`. If not, print a one-line warning with the exact shell-rc snippet to add (`export PATH="$HOME/.local/bin:$PATH"`) and which file to add it to based on `$SHELL` (`~/.zshrc` for zsh, `~/.bashrc` for bash). Install still succeeds.
6. Patch `~/.claude/settings.json` (only — not `settings.local.json`) to add SessionStart + Stop hook entries. Implemented as a Python helper invoked from the shell script, doing a deep merge:
   - Read existing JSON (create empty `{}` if absent).
   - Ensure `hooks.SessionStart` and `hooks.Stop` arrays exist.
   - Append our entries if not already present (idempotent — detect by exact `command` path match).
   - Write back atomically via tempfile + `os.replace`.
7. **(Last step.)** Write `~/.digital-brain/install.json` with `{ "install_root": "<install_root>", "installed_at": "<ISO timestamp>", "version": "<pyproject version>" }`. Atomic write (tempfile + `os.replace`).
8. Print the post-install message from section 4.5.

**Settings to be added:**

```json
{
  "hooks": {
    "SessionStart": [
      { "matcher": "*", "hooks": [{ "type": "command", "command": "<install_root>/hooks/session_start.sh" }] }
    ],
    "Stop": [
      { "matcher": "*", "hooks": [{ "type": "command", "command": "<install_root>/hooks/stale_check.sh" }] }
    ]
  }
}
```

### Per-project adoption (new brain project)

```bash
cd <host-repo>
cat > .digital-brain-config.yaml <<'EOF'
source_paths:
  - src/
vault_dir: digital-brain/
EOF
echo "digital-brain/" >> .gitignore
INSTALL_ROOT="$(python3 -c "import json; print(json.load(open(__import__('os').path.expanduser('~/.digital-brain/install.json')))['install_root'])")"
ln -sf "$INSTALL_ROOT/hooks/post-commit" .git/hooks/post-commit
```

That is the full per-project setup. The next `claude` session in this dir picks up the SessionStart hook, sees the missing vault, and prompts the user to build it.

### Per-project removal

```bash
cd <host-repo>
digital-brain remove
```

### Global uninstall

```bash
digital-brain uninstall
rm -rf ~/Projects/digital-brain     # optional, only if you want the source gone too
```

### Session lifecycle flow

```
claude (new session in <host-repo>)
        │
        ▼
SessionStart hook (session_start.sh → session_start.py)
        │
        ├─ no .digital-brain-config.yaml ──> silent exit (not a brain project)
        │
        ├─ config exists, vault missing ───> inject: "Build brain? Run /refresh-digital-brain"
        │                                            │
        │                                            ▼  (user invokes skill)
        │                                    refresh-digital-brain skill
        │                                            │
        │                                            ├─ graphify AST extract
        │                                            ├─ filter + cluster
        │                                            ├─ Obsidian export → <vault_dir>/
        │                                            ├─ Claude writes concept notes
        │                                            ├─ obsidian_register.register_vault()
        │                                            └─ read _INDEX.md into context  (Gap 1 fix)
        │
        └─ config + vault both exist ──────> inject: <vault>/_INDEX.md contents (~2k tok)
                                                     │
                                                     ▼
                                             Claude has brain loaded; conversation begins.

(during conversation)
user: "explain [[HybridRetriever]]"
        │
        ▼
load-digital-brain skill instruction → Claude reads <vault>/HybridRetriever.md
        │
        ▼
Claude reply: "HybridRetriever ([source](src/retrieval.py#L42), [vault](obsidian://open?vault=<v>&file=HybridRetriever.md)) does X..."

(later, user runs `git commit`)
        │
        ▼
post-commit hook (auto_refresh.py)
        │
        ├─ commit touched source_paths? no  ──> silent exit
        └─                              yes ──> background AST rebuild (~3 sec)
                                                 → _INDEX.md updated, last_refresh_commit bumped
```

## 6. Testing

### Existing tests (must stay green after rename)

`helpers/tests/` currently holds 23 tests across `test_config.py`, `test_frontmatter.py`, `test_index_writer.py`. The rename pass updates imports:

```python
from brain_helpers import config        →  from digital_brain_helpers import config
```

Plus any test fixtures with `.brain-config.yaml` string literals. Tests verify functional behavior, not names — the rename should be mechanical with no logic changes. Pass rate must not regress.

### New tests required

**`test_obsidian_register.py`** (~6 tests):

- Registers a vault into empty `obsidian.json` (uses `tmp_path`, no real Obsidian).
- Registers into existing `obsidian.json` with other vaults — preserves them.
- Re-registering same path is no-op (idempotent — same `path` field already present).
- Missing `obsidian.json` → returns `RegisterResult(status="obsidian_not_installed")`, no exception, file not created.
- Malformed `obsidian.json` → raises clear error, file untouched.
- Generates valid uuid4 hex and epoch_ms timestamp for new vault entry.

Monkeypatch the OS-config-dir resolver so tests never touch the user's real Obsidian config.

**`test_cli.py`** (~4 tests):

- `digital-brain remove` in dir without `.digital-brain-config.yaml` exits 1 with clear error.
- `digital-brain remove --yes` deletes config + vault + post-commit symlink. Graveyard copy created with concept-note files.
- `digital-brain remove --yes` only removes `.git/hooks/post-commit` if it points at our hook; preserves it otherwise.
- `digital-brain uninstall --yes` removes only our entries from `~/.claude/settings.json`, preserves others.

Use `tmp_path` plus monkeypatched `HOME` so tests never touch the real `~/.claude/` or real graveyard dir.

**`test_session_start.py`** (~5 tests, targets `digital_brain_helpers.session_start`):

- No config in cwd or any parent → exits 0, no output.
- Config + missing vault → emits JSON with `hookEventName: "SessionStart"` and `additionalContext` containing "Build brain".
- Config + vault + `_INDEX.md` (small) → emits JSON with full INDEX in `additionalContext`.
- Config + vault + `_INDEX.md` > 9500 chars → emits truncated head + pointer line in `additionalContext`.
- Walks up dirs to find config (runs from a deep subdir).

**`test_auto_refresh.py`** (note): existing `auto_refresh.py` keeps its existing test coverage. The only changes in this work are string replacements (`.brain-config.yaml` → `.digital-brain-config.yaml`, `project-brain` → `digital-brain`). Existing tests cover all behavioral paths; if a constant for the config filename did not previously exist as a test fixture, add one assertion that `auto_refresh.py` reads `.digital-brain-config.yaml` (not the old name).

### Manual smoke test (post-implementation, run once)

Not automated — documented in the implementation plan's verification checklist:

1. Fresh dir: `mkdir /tmp/brain-test && cd /tmp/brain-test && git init && echo "def foo(): pass" > main.py && git add . && git commit -m init`
2. Add config: `printf 'source_paths: [.]\nvault_dir: digital-brain/\n' > .digital-brain-config.yaml`
3. Symlink post-commit hook: `ln -sf "$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.digital-brain/install.json')))['install_root'])")/hooks/post-commit" .git/hooks/post-commit` (or paste the install path printed by `install.sh`'s final message — the python3 form here is for cases where that output is no longer scrolled back).
4. Run `claude` — verify SessionStart message says "Build brain".
5. `/refresh-digital-brain` — verify vault built, INDEX read into context, vault registered in Obsidian (open Obsidian, see it in the vault list).
6. Quit Claude. Re-run `claude` — verify INDEX auto-loaded into next session.
7. Edit `main.py`, commit — verify post-commit triggers, `_INDEX.md` `last_refresh_commit` bumped.
8. `digital-brain remove` — verify clean removal, graveyard populated.
9. `digital-brain uninstall` — verify global cleanup.

### Coverage target

≥80% line coverage on new Python (`obsidian_register.py`, `cli.py`, `session_start.py`). Existing modules: no regression from current pass rate.

**Enforcement:** `helpers/pyproject.toml` adds a pytest-cov config block:

```toml
[tool.pytest.ini_options]
addopts = "--cov=digital_brain_helpers --cov-fail-under=80"
```

Running `pytest` in `helpers/` therefore fails the suite if coverage drops below 80%. The `[dev]` extra in `pyproject.toml` includes `pytest-cov`.

## 7. Risks + Edge Cases

| Risk | Mitigation |
|------|------------|
| User has existing `~/.claude/settings.json` with custom hooks | `install.sh` deep-merges digital-brain entries into `hooks.SessionStart` + `hooks.Stop` arrays. Never clobbers. Uninstall removes only entries whose `command` path resolves under `<install_root>/hooks/`. |
| Obsidian is open when `obsidian_register` writes | Obsidian reads `obsidian.json` on startup; writes when the app is open may be overwritten on quit. Mitigation: log warning at write time advising user to quit + reopen Obsidian. |
| Obsidian not installed at all | `obsidian_register` detects missing parent dir → returns `RegisterResult(status="obsidian_not_installed")`. Build still succeeds. |
| Cross-platform paths (macOS vs Linux vs Windows) | `obsidian_register` switches on `sys.platform`. v0 supports macOS + Linux. Windows logs warning and is a no-op. |
| Multiple projects share a vault dir name (`digital-brain/`) | Obsidian disambiguates by absolute path. Two entries are fine. |
| `~/.claude/skills/refresh-digital-brain` already exists from elsewhere | `install.sh` uses `ln -sf` which overwrites. Print warning naming the previous target before clobbering. |
| `digital-brain remove` runs in a dir whose post-commit hook is not ours | Read `.git/hooks/post-commit`; if it is a symlink and resolves under `<install_root>/hooks/` (discovered via `install.json`), remove it. Otherwise leave in place with a printed note. |
| `digital-brain uninstall` runs during an active refresh | No locking in v0. Documented in README: don't run uninstall during active refresh. Future v1 can add a lockfile. |
| SessionStart hook fires in every `claude` session, even non-brain projects | Hook does a cheap config-file check and exits silently if absent. ~5 ms overhead. Acceptable. |
| User edits `_INDEX.md` by hand | Documented as auto-generated. Post-commit hook rewrites it. Loss is user error; README warns. |
| Citation format clutters chat with verbose `[[X]] ([source], [vault])` | Skill rule: full format only on first mention of a node per turn; bare `[[X]]` afterwards. Signal/noise stays reasonable. |
| Vault path contains spaces, breaks `obsidian://open?vault=...` URL | Use `urllib.parse.quote` when generating Obsidian URLs in citations and in the register step. |
| Git hook symlink does not transfer on `git clone` | Documented in per-project setup. Future v1 can add a bootstrap script. |
| `.digital-brain-config.yaml` malformed YAML | `helpers/config.py` already raises a clear error. Same path post-rename. |
| Vault grows huge (10k+ extracted notes), INDEX exceeds 2k tok budget | `index_writer.py` already truncates communities above a threshold. Document the threshold. Larger budget tuning deferred to v1. |
| INDEX exceeds 10,000 char `additionalContext` cap | `session_start.py` truncates to first 9,500 chars and appends pointer line so Claude can read full file via the Read tool. Documented in §3.1. |
| Live Claude session sees stale INDEX after a commit | Stop hook nags ("vault behind") after each turn. User runs `/refresh-digital-brain` or restarts session to reload. Documented limitation, acceptable for v0. |
| Concept-note graveyard accumulates forever | No retention policy in v0. Documented; user can `rm -rf ~/.digital-brain-graveyard/<old>` manually. |
| User runs multiple concurrent `claude` sessions in same project | SessionStart fires per-session; INDEX gets injected into each. Independent contexts — no de-dup needed. Acceptable. |
| `_INDEX.md` contains non-UTF-8 bytes | `session_start.py` reads with `errors="replace"` so JSON serialization never crashes. Replacement chars are visible in the injected context — user sees them and re-runs refresh. |
| `.digital-brain-config.yaml` has empty `source_paths` | `helpers/config.py` validates `source_paths` is non-empty list; refresh skill raises clear error. No silent no-op. |
| Post-commit hook fires during rebase / cherry-pick / amend | Hook checks `git rev-parse --is-rebasing` (and equivalent for cherry-pick) and exits silently during in-progress operations to avoid refresh loops. |
| User deletes `helpers/.venv` after install | `digital-brain` console script symlink resolves to nothing → `bash: command not found` style error. `cli.py` cannot run to clean up. Documented recovery: `cd <install_root>/helpers && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"` then re-run `bash hooks/install.sh`. |
| Install path discovery fallback chain fails (no `install.json`, broken symlink) | `cli.py remove` / `uninstall` prints clear error: "Cannot locate digital-brain install root. Reinstall via `bash <repo>/hooks/install.sh` or remove manually." Exits 1 with non-destructive behavior. |
