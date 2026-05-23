# digital-brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `private-brain` into a standalone `digital-brain` repo, full identifier rename, plus three auto behaviors: SessionStart auto-prompt-to-build / auto-load, bidirectional node references, auto-registration with Obsidian on first build.

**Architecture:** Pure refactor + additive new components. No behavioral change to the existing post-commit auto-refresh pipeline. New Python modules (`obsidian_register`, `session_start`, `cli`) live in a relocated `src/digital_brain_helpers/` package. New `hooks/session_start.sh` thin wrapper invokes the helpers venv. Skill instructions extend with citation-format + wikilink-resolver conventions. `install.sh` rewritten to set up global symlinks + write a discovery metadata file.

**Tech Stack:** Python 3.10+, PyYAML, graphifyy, pytest + pytest-cov, bash 4+, Claude Code hook protocol (SessionStart + Stop), Obsidian URL scheme (`obsidian://open?...`).

**Reference docs:**
- Spec: `docs/superpowers/specs/2026-05-23-digital-brain-design.md` (read first — answers the why)
- v0 design: `docs/plan-v0-mvp.md` (for `layer: concept` frontmatter schema, vault structure conventions)

---

## File structure (post-implementation)

```
~/Projects/digital-brain/                                       # repo (renamed)
├── README.md                                                    # rewritten
├── docs/
│   ├── plan-v0-mvp.md                                          # scrubbed of private-gpt refs
│   ├── plan-v1-full.md                                          # scrubbed
│   ├── superpowers/specs/2026-05-23-digital-brain-design.md     # already written
│   └── superpowers/plans/2026-05-23-digital-brain.md            # this file
├── skills/
│   ├── refresh-digital-brain/SKILL.md                          # renamed + extended (citation + INDEX read at end)
│   └── load-digital-brain/SKILL.md                             # renamed + extended (citation + wikilink resolver)
├── helpers/
│   ├── pyproject.toml                                           # name=digital-brain-helpers, console script, pytest-cov
│   └── src/digital_brain_helpers/                              # NEW src/ layout
│       ├── __init__.py
│       ├── config.py                                            # moved + CONFIG_FILENAME renamed
│       ├── frontmatter.py                                       # moved unchanged
│       ├── index_writer.py                                      # moved + import path fix
│       ├── obsidian_register.py                                 # NEW
│       ├── session_start.py                                     # NEW
│       └── cli.py                                               # NEW
│   └── tests/
│       ├── conftest.py                                          # unchanged
│       ├── test_config.py                                       # imports renamed
│       ├── test_frontmatter.py                                  # imports renamed
│       ├── test_index_writer.py                                 # imports renamed
│       ├── test_obsidian_register.py                            # NEW
│       ├── test_session_start.py                                # NEW
│       └── test_cli.py                                          # NEW
└── hooks/
    ├── install.sh                                               # rewritten
    ├── post-commit                                              # paths updated (refs config filename)
    ├── auto_refresh.py                                          # config filename + import paths + log prefix
    ├── stale_check.sh                                           # env vars + log prefix + config filename
    └── session_start.sh                                         # NEW thin wrapper
```

**Per-project (consumer repo) layout (unchanged structure, just filenames):**

```
<host-repo>/
├── .digital-brain-config.yaml              # renamed from .brain-config.yaml
├── digital-brain/                          # renamed from project-brain/  (default; user-configurable)
└── .git/hooks/post-commit → <install_root>/hooks/post-commit
```

**Global (user-level):**

```
~/.claude/skills/refresh-digital-brain → <install_root>/skills/refresh-digital-brain
~/.claude/skills/load-digital-brain    → <install_root>/skills/load-digital-brain
~/.claude/settings.json                # gains SessionStart + Stop hook entries
~/.local/bin/digital-brain             → <install_root>/helpers/.venv/bin/digital-brain
~/.digital-brain/install.json          # discovery metadata
```

---

## Phase 0 — Pre-flight

### Task 0.1: Verify clean working tree + branch

**Files:** none (state check only)

- [ ] **Step 1: Confirm clean tree**

```bash
cd ~/Projects/private-brain
git status
```

Expected: `nothing to commit, working tree clean`. If dirty, stash or commit first. Do not start work in a dirty tree — the rename touches everything and you must be able to roll back via `git reset --hard`.

- [ ] **Step 2: Create implementation branch**

```bash
git checkout -b digital-brain-rename
```

Expected: `Switched to a new branch 'digital-brain-rename'`. All work lands here; the rename to `digital-brain` dir happens on this branch and gets squash-merged or PR'd to main at the end.

- [ ] **Step 3: Verify existing test suite is green BEFORE any changes**

```bash
cd helpers
.venv/bin/pytest -v
```

Expected: `23 passed`. If anything fails, fix that first — you need a green baseline so future failures are clearly caused by your work.

- [ ] **Step 4: Commit a marker (intentional empty commit)**

```bash
cd ..
git commit --allow-empty -m "chore: baseline before digital-brain rename"
```

This gives you a `git reset --hard` target if Phase 1 goes sideways.

---

## Phase 1 — Mechanical rename (no behavior change)

Phase 1 is pure rename. Existing 23 tests must stay green at the end. No new features. Commit after each task so each rename is isolated and revertable.

### Task 1.1: Refactor `helpers/` to `src/digital_brain_helpers/` layout

**Files:**
- Modify: `helpers/pyproject.toml`
- Move: `helpers/config.py` → `helpers/src/digital_brain_helpers/config.py`
- Move: `helpers/frontmatter.py` → `helpers/src/digital_brain_helpers/frontmatter.py`
- Move: `helpers/index_writer.py` → `helpers/src/digital_brain_helpers/index_writer.py`
- Create: `helpers/src/digital_brain_helpers/__init__.py` (empty)

- [ ] **Step 1: Create new src layout**

```bash
cd ~/Projects/private-brain/helpers
mkdir -p src/digital_brain_helpers
touch src/digital_brain_helpers/__init__.py
# Track the new __init__.py BEFORE the git mv so the destination dir is known to git.
git add src/digital_brain_helpers/__init__.py
git mv config.py src/digital_brain_helpers/config.py
git mv frontmatter.py src/digital_brain_helpers/frontmatter.py
git mv index_writer.py src/digital_brain_helpers/index_writer.py
```

- [ ] **Step 2: Fix `index_writer.py` import**

`index_writer.py` line 9 currently reads `from frontmatter import split_document`. After the move that's wrong — it's a sibling import now. Open the file and change to:

```python
from .frontmatter import split_document
```

- [ ] **Step 3: Rewrite `helpers/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "digital-brain-helpers"
version = "0.1.0"
description = "Helpers for digital-brain Claude Code skills"
requires-python = ">=3.10"
dependencies = [
    "PyYAML>=6.0",
    "graphifyy>=0.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]

[project.scripts]
digital-brain = "digital_brain_helpers.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=digital_brain_helpers --cov-fail-under=80"
```

Removed `[tool.setuptools] py-modules = [...]` block — the `find` directive now handles discovery. Added pytest-cov + console script per spec.

- [ ] **Step 4: Recreate venv from scratch + clean editable-install metadata**

The old venv has `brain-helpers` installed as an editable package. Also clean up `*.egg-info` dirs left over from the prior layout — they confuse setuptools' editable mode under the new src/ layout.

```bash
cd ~/Projects/private-brain/helpers
rm -rf .venv
rm -rf *.egg-info src/*.egg-info
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Expected last line: `Successfully installed ... digital-brain-helpers-0.1.0 ...` Also expect `pytest-cov` in the list.

- [ ] **Step 5: Update test imports**

Edit `tests/test_config.py`, `tests/test_frontmatter.py`, `tests/test_index_writer.py`. Replace every bare import:

```python
from config import ...           →   from digital_brain_helpers.config import ...
from frontmatter import ...      →   from digital_brain_helpers.frontmatter import ...
from index_writer import ...     →   from digital_brain_helpers.index_writer import ...
```

Find them with: `grep -nE "^from (config|frontmatter|index_writer)" tests/*.py`

- [ ] **Step 6: Run tests — expect green**

```bash
cd ~/Projects/private-brain/helpers
.venv/bin/pytest -v
```

Expected: `23 passed`. Coverage report will print but **the --cov-fail-under=80 gate fires only on the digital_brain_helpers package**, which currently covers ~100% of the moved modules so this should pass too.

If coverage fails (e.g. new code arrives in Phase 2-5 before its tests do, mid-implementation), temporarily lower the threshold in `helpers/pyproject.toml`:

```toml
addopts = "--cov=digital_brain_helpers --cov-fail-under=0"
```

**Re-enable to 80 in Task 4.7 Step 1 before declaring Phase 4 complete.** That task already runs coverage; verify the threshold is set back to 80 there.

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/private-brain
git add helpers/
git commit -m "refactor: move helpers to src/digital_brain_helpers/ layout"
```

### Task 1.2: Rename config filename and default vault dir constants

**Files:**
- Modify: `helpers/src/digital_brain_helpers/config.py:9-10`
- Modify: `helpers/tests/test_config.py` (any string literal `.brain-config.yaml` or `project-brain`)

- [ ] **Step 1: Update config constants**

In `helpers/src/digital_brain_helpers/config.py`:

```python
CONFIG_FILENAME = ".digital-brain-config.yaml"
DEFAULT_VAULT_DIR = "digital-brain/"
```

Also update the error message in `load_config` if it references `.brain-config.yaml` literal anywhere. Use `CONFIG_FILENAME` constant in error messages rather than re-hardcoding.

- [ ] **Step 2: Update tests**

```bash
grep -n "\.brain-config\.yaml\|project-brain" helpers/tests/*.py
```

For each match, replace `.brain-config.yaml` → `.digital-brain-config.yaml` and `project-brain` → `digital-brain` (the latter only when used as a vault dir default, not as a generic project name in test fixture content).

- [ ] **Step 3: Run tests — expect green**

```bash
.venv/bin/pytest -v
```

Expected: `23 passed`.

- [ ] **Step 4: Commit**

```bash
git add -u helpers/
git commit -m "refactor: rename config filename to .digital-brain-config.yaml, vault default to digital-brain/"
```

### Task 1.3: Update `hooks/auto_refresh.py` for new import paths + config filename

**Files:**
- Modify: `hooks/auto_refresh.py` (sys.path, imports, config filename literal, log prefix)

- [ ] **Step 1: Update imports + paths**

The current file at line 17-19 inserts `helpers/` on sys.path and imports bare names. New approach: import from the proper package.

Replace lines 17-19:

```python
PRIVATE_BRAIN_DIR = Path(__file__).resolve().parent.parent
HELPERS_DIR = PRIVATE_BRAIN_DIR / "helpers"
sys.path.insert(0, str(HELPERS_DIR))
```

With:

```python
INSTALL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(INSTALL_ROOT / "helpers" / "src"))
```

(Constant renamed `PRIVATE_BRAIN_DIR` → `INSTALL_ROOT` to match spec terminology. Find all uses with `grep -n PRIVATE_BRAIN_DIR hooks/auto_refresh.py` and rename.)

Then update the lazy imports inside `main()` (currently lines 45-46):

```python
from digital_brain_helpers.config import load_config
from digital_brain_helpers.index_writer import write_index
```

- [ ] **Step 2: Update config filename literal**

Line 40 currently reads:

```python
cfg_path = REPO_ROOT / ".brain-config.yaml"
```

Replace with:

```python
from digital_brain_helpers.config import CONFIG_FILENAME
cfg_path = REPO_ROOT / CONFIG_FILENAME
```

(Move the import to the top of `main()` or to module level — wherever the other helper imports land.)

- [ ] **Step 3: Update log prefix**

Find every `[private-brain]` literal in the file:

```bash
grep -n "private-brain" hooks/auto_refresh.py
```

Replace with `[digital-brain]`. Also replace any `private-brain` in module docstring with `digital-brain`.

- [ ] **Step 4: Smoke-test the script in isolation**

```bash
cd ~/Projects/private-brain
helpers/.venv/bin/python hooks/auto_refresh.py
```

Expected: exits 0 with no output (no `.digital-brain-config.yaml` in repo root yet — that's the "not initialized" silent-exit path). If you see `ImportError` or `FileNotFoundError`, fix it before committing.

- [ ] **Step 5: Commit**

```bash
git add hooks/auto_refresh.py
git commit -m "refactor: update auto_refresh.py for new package layout + config filename"
```

### Task 1.3.5: Add config-filename regression test for auto_refresh.py

Spec §6 mandates an explicit assertion that `auto_refresh.py` reads `.digital-brain-config.yaml` (not the old name). No prior test for this script exists. Add one.

**Files:**
- Create: `helpers/tests/test_auto_refresh.py`

- [ ] **Step 1: Write the test**

```python
"""Regression test: auto_refresh.py reads the new config filename."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]   # private-brain/ during dev, digital-brain/ post-rename
AUTO_REFRESH = REPO_ROOT / "hooks" / "auto_refresh.py"
PYTHON = REPO_ROOT / "helpers" / ".venv" / "bin" / "python"


def test_auto_refresh_silent_exit_when_no_config(tmp_path):
    """No .digital-brain-config.yaml → script exits 0 with no output."""
    result = subprocess.run(
        [str(PYTHON), str(AUTO_REFRESH)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout == ""


def test_auto_refresh_reads_new_config_filename(tmp_path, monkeypatch):
    """Confirms the script looks for .digital-brain-config.yaml (not the old name).

    We verify by checking the source file contains the new constant — a true
    behavioral test would need a full git+graphify setup which is out of scope
    for unit tests.
    """
    text = AUTO_REFRESH.read_text()
    assert ".digital-brain-config.yaml" in text or "CONFIG_FILENAME" in text
    assert ".brain-config.yaml" not in text  # old name fully removed
```

- [ ] **Step 2: Run — expect PASS (Task 1.3 already updated the file)**

```bash
cd ~/Projects/private-brain/helpers
.venv/bin/pytest tests/test_auto_refresh.py -v
```

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/private-brain
git add helpers/tests/test_auto_refresh.py
git commit -m "test(auto_refresh): regression test for new config filename"
```

### Task 1.4: Update `hooks/stale_check.sh` (env vars, config filename, log prefix, helpers path)

**Files:**
- Modify: `hooks/stale_check.sh`

- [ ] **Step 1: Rename env vars**

Find every `STALE_COMMITS` and `STALE_DAYS` reference:

```bash
grep -n "STALE_COMMITS\|STALE_DAYS" hooks/stale_check.sh
```

Replace `STALE_COMMITS` → `DIGITAL_BRAIN_STALE_COMMITS`, `STALE_DAYS` → `DIGITAL_BRAIN_STALE_DAYS`. Apply only to the env-var name itself (e.g. `"${STALE_COMMITS:-5}"` → `"${DIGITAL_BRAIN_STALE_COMMITS:-5}"`). The local variable name inside the script (`STALE_COMMITS=...`) can stay or also rename — your call; renaming locals too is cleaner.

- [ ] **Step 2: Rename config filename literal**

Line 38:

```bash
[ -f .brain-config.yaml ] || exit 0
```

Replace with:

```bash
[ -f .digital-brain-config.yaml ] || exit 0
```

- [ ] **Step 3: Update helpers Python import path + invocation**

Lines 40-45 use `sys.path.insert(0, '$PRIVATE_BRAIN_DIR/helpers')` and bare `from config import load_config`. Update to use the new src layout + package import:

```bash
VAULT_DIR=$("$HELPERS_PY" -c "
import sys; sys.path.insert(0, '$INSTALL_ROOT/helpers/src')
from pathlib import Path
from digital_brain_helpers.config import load_config
print(load_config(Path('.').resolve()).resolved_vault_dir())
" 2>/dev/null) || exit 0
```

Rename the bash variable `PRIVATE_BRAIN_DIR` → `INSTALL_ROOT` everywhere in the file (matches spec terminology).

- [ ] **Step 4: Update log prefix in `emit_stale` strings**

Find every `[private-brain]` literal and the user-facing message `/refresh-brain`:

```bash
grep -nE "private-brain|/refresh-brain" hooks/stale_check.sh
```

Replace `[private-brain]` → `[digital-brain]` and `/refresh-brain` → `/refresh-digital-brain`.

- [ ] **Step 5: Smoke-test**

```bash
cd /tmp && mkdir stale-test && cd stale-test && git init -q && touch dummy && git add . && git -c user.email=t@t -c user.name=T commit -qm init
~/Projects/private-brain/hooks/stale_check.sh
```

Expected: exits 0 with no output (no `.digital-brain-config.yaml` → silent exit at line 38 check). Confirms script doesn't crash on the rename.

```bash
cd ~/Projects/private-brain && rm -rf /tmp/stale-test
```

- [ ] **Step 6: Commit**

```bash
git add hooks/stale_check.sh
git commit -m "refactor: rename env vars + paths in stale_check.sh"
```

### Task 1.5: Rename skill directories

**Files:**
- Move: `skills/refresh-brain/` → `skills/refresh-digital-brain/`
- Move: `skills/load-brain/` → `skills/load-digital-brain/`
- Modify: both `SKILL.md` files — `name:` field, references to `/refresh-brain` / `/load-brain` slash commands, references to `.brain-config.yaml`, references to `private-brain/helpers`, references to `project-brain/`

- [ ] **Step 1: Rename dirs**

```bash
cd ~/Projects/private-brain
git mv skills/refresh-brain skills/refresh-digital-brain
git mv skills/load-brain skills/load-digital-brain
```

- [ ] **Step 2: Update `skills/refresh-digital-brain/SKILL.md` `name:` field**

Line 2:

```yaml
name: refresh-digital-brain
```

Also update the description to remove `private-brain` / `project-brain` references and reflect new naming.

- [ ] **Step 3: Update all path + slash command references in `refresh-digital-brain/SKILL.md`**

Search-and-replace pass:

```bash
grep -nE "private-brain|project-brain|/refresh-brain|/load-brain|\.brain-config\.yaml|brain-config|brain_helpers" skills/refresh-digital-brain/SKILL.md
```

For each match, replace:
- `private-brain/helpers` → `<install_root>/helpers` (the skill will need to resolve `<install_root>` from `~/.digital-brain/install.json` — add a Step 0.5 in the SKILL that does so via the python3 one-liner from the spec §5)
- `/refresh-brain` → `/refresh-digital-brain`
- `/load-brain` → `/load-digital-brain`
- `.brain-config.yaml` → `.digital-brain-config.yaml`
- `project-brain` → `digital-brain` (in vault path context only)
- `from config import` / `from frontmatter import` / `from index_writer import` (in embedded Python heredocs) → `from digital_brain_helpers.config import` etc.
- `sys.path.insert(0, 'private-brain/helpers')` → resolve from `~/.digital-brain/install.json` at runtime

For the `sys.path` line specifically, replace embedded shell heredocs that hardcode `private-brain/helpers` with:

```bash
INSTALL_ROOT="$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.digital-brain/install.json')))['install_root'])")"
HELPERS_VENV="$INSTALL_ROOT/helpers/.venv/bin/python"
```

at the top of Step 0 (prerequisite check). Then all subsequent `"$HELPERS_VENV"` calls work without further path edits, and the embedded Python uses `sys.path.insert(0, '$INSTALL_ROOT/helpers/src')`.

- [ ] **Step 4: Same pass on `skills/load-digital-brain/SKILL.md`**

Repeat Step 3 for `load-digital-brain/SKILL.md`. Same find-and-replace patterns.

- [ ] **Step 5: Verify no stale references**

```bash
grep -rnE "private-brain|project-brain|/refresh-brain|/load-brain|\.brain-config\.yaml" skills/
```

Expected: zero matches.

- [ ] **Step 6: Commit**

```bash
git add skills/
git commit -m "refactor: rename skills to digital-brain and update embedded paths"
```

### Task 1.6: Update remaining mentions in plan docs + hooks/post-commit

**Files:**
- Modify: `docs/plan-v0-mvp.md`, `docs/plan-v1-full.md` — replace `private-gpt-fork` / `private_gpt/` with `<host-repo>` / `<src-dir>` worked examples, replace `private-brain` with `digital-brain`, replace `.brain-config.yaml` with `.digital-brain-config.yaml`
- Modify: `hooks/post-commit` (shell script) — if it references the old names

- [ ] **Step 1: Find all stale refs**

```bash
cd ~/Projects/private-brain
grep -rnE "private-gpt|private_gpt|private-brain|project-brain|\.brain-config\.yaml" docs/ hooks/ --include="*.md" --include="post-commit" --include="*.sh" 2>/dev/null | grep -v ".history"
```

Capture the list. There will be many in the plan docs.

- [ ] **Step 2: Scrub plan docs**

For `docs/plan-v0-mvp.md` and `docs/plan-v1-full.md`:
- Replace `private-gpt-fork` → `<host-repo>` everywhere.
- Replace `private_gpt/` (when used as the example source dir) → `<src-dir>/`.
- Replace `private-brain` (referring to this project) → `digital-brain`.
- Replace `.brain-config.yaml` → `.digital-brain-config.yaml`.
- Replace `project-brain` → `digital-brain` (default vault dir).
- Leave references to graphify, retrieval-pipeline names, etc. alone unless they are private-gpt-specific concept examples that no longer make sense in a generic project. If they are private-gpt-specific examples (e.g. `BgeReranker`, `HybridRetriever`), wrap them in framing like "for example, in the codebase the original v0 was developed against, `BgeReranker` and `HybridRetriever`…".

Do this in a single editor pass per file. Use sed only if you've manually previewed the substitution list — sed can clobber things you didn't expect.

- [ ] **Step 3: Check `hooks/post-commit`**

```bash
cat hooks/post-commit
```

If it references the old config filename or path, update. If it doesn't (likely just a thin wrapper that execs `auto_refresh.py`), no change needed.

- [ ] **Step 4: Verify**

```bash
grep -rnE "private-gpt|private_gpt|\.brain-config\.yaml" docs/ hooks/ skills/ helpers/src/ --include="*.md" --include="*.py" --include="*.sh" --include="*.toml" --include="post-commit"
```

Expected: zero matches (excluding `docs/superpowers/` spec/plan files — those legitimately quote the rename trail).

- [ ] **Step 5: Commit**

```bash
git add -u docs/ hooks/
git commit -m "docs: scrub private-gpt and old-name references from plan docs"
```

### Task 1.7: Full test sweep + commit checkpoint

- [ ] **Step 1: Run helpers tests**

```bash
cd ~/Projects/private-brain/helpers
.venv/bin/pytest -v
```

Expected: `23 passed`.

- [ ] **Step 2: Verify auto_refresh + stale_check still run cleanly**

```bash
cd ~/Projects/private-brain
helpers/.venv/bin/python hooks/auto_refresh.py
bash hooks/stale_check.sh
```

Both should exit 0 with no output (no config file in this dir yet).

- [ ] **Step 3: Tag the rename checkpoint**

```bash
git tag rename-complete-iter-0
```

Lets you `git diff rename-complete-iter-0` after new-feature phases to see only the additive work.

---

## Phase 2 — `obsidian_register.py` (TDD)

### Task 2.1: Write failing test for `register_vault` on empty obsidian.json

**Files:**
- Create: `helpers/tests/test_obsidian_register.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for digital_brain_helpers.obsidian_register."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from digital_brain_helpers import obsidian_register
from digital_brain_helpers.obsidian_register import register_vault, RegisterResult


@pytest.fixture
def fake_obsidian_config(tmp_path: Path, monkeypatch) -> Path:
    """Create a fake obsidian.json under tmp_path and monkeypatch the resolver to return it."""
    cfg_dir = tmp_path / "obsidian"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "obsidian.json"
    monkeypatch.setattr(obsidian_register, "_obsidian_config_path", lambda: cfg_path)
    return cfg_path


def test_register_into_empty_config_creates_vaults_section(fake_obsidian_config, tmp_path):
    fake_obsidian_config.write_text("{}")
    vault = tmp_path / "myvault"
    vault.mkdir()

    result = register_vault(vault)

    assert result.status == "registered"
    data = json.loads(fake_obsidian_config.read_text())
    assert "vaults" in data
    assert len(data["vaults"]) == 1
    entry = next(iter(data["vaults"].values()))
    assert entry["path"] == str(vault.resolve())
    assert "ts" in entry
    assert isinstance(entry["ts"], int)
    # ts is epoch ms — must be in a sane range (after year 2020, before year 2050)
    assert 1_577_836_800_000 < entry["ts"] < 2_524_608_000_000
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd ~/Projects/private-brain/helpers
.venv/bin/pytest tests/test_obsidian_register.py -v
```

Expected: `ImportError` or `ModuleNotFoundError: digital_brain_helpers.obsidian_register`. That's the desired failure.

### Task 2.2: Implement minimal `register_vault` to pass test 2.1

**Files:**
- Create: `helpers/src/digital_brain_helpers/obsidian_register.py`

- [ ] **Step 1: Write minimal implementation**

```python
"""Register/unregister a vault path with the user's Obsidian app via obsidian.json."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json
import os
import sys
import tempfile
import time
import uuid


@dataclass
class RegisterResult:
    status: str
    message: str = ""


def _obsidian_config_path() -> Optional[Path]:
    """Return platform-specific obsidian.json path, or None on unsupported platform."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "obsidian" / "obsidian.json"
    if sys.platform.startswith("linux"):
        return home / ".config" / "obsidian" / "obsidian.json"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "obsidian" / "obsidian.json"
    return None


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", dir=str(path.parent), delete=False, suffix=".tmp"
    )
    try:
        json.dump(data, tmp, indent=2)
        tmp.close()
        os.replace(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass
        raise


def register_vault(vault_path: Path) -> RegisterResult:
    cfg = _obsidian_config_path()
    if cfg is None:
        return RegisterResult(status="unsupported_platform")
    if not cfg.parent.exists():
        return RegisterResult(status="obsidian_not_installed",
                              message=f"{cfg.parent} not found")
    if not cfg.exists():
        return RegisterResult(status="obsidian_not_installed",
                              message=f"{cfg} not found")

    try:
        data = json.loads(cfg.read_text() or "{}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed obsidian.json at {cfg}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"obsidian.json at {cfg} is not a JSON object")

    vaults = data.setdefault("vaults", {})
    target = str(vault_path.resolve())

    for entry in vaults.values():
        if isinstance(entry, dict) and entry.get("path") == target:
            return RegisterResult(status="already_present")

    vault_id = uuid.uuid4().hex[:16]
    vaults[vault_id] = {
        "path": target,
        "ts": int(time.time() * 1000),
        "open": False,
    }

    _atomic_write_json(cfg, data)
    return RegisterResult(status="registered")
```

- [ ] **Step 2: Run test — expect PASS**

```bash
.venv/bin/pytest tests/test_obsidian_register.py -v
```

Expected: `1 passed`.

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/private-brain
git add helpers/src/digital_brain_helpers/obsidian_register.py helpers/tests/test_obsidian_register.py
git commit -m "feat(obsidian_register): register vault into empty obsidian.json"
```

### Task 2.3: Test + implement — preserves existing vaults

- [ ] **Step 1: Add test**

Append to `test_obsidian_register.py`:

```python
def test_register_preserves_other_vaults(fake_obsidian_config, tmp_path):
    existing = {
        "vaults": {
            "abc123": {"path": "/other/vault", "ts": 1234567890, "open": True}
        }
    }
    fake_obsidian_config.write_text(json.dumps(existing))
    vault = tmp_path / "newvault"
    vault.mkdir()

    register_vault(vault)

    data = json.loads(fake_obsidian_config.read_text())
    assert "abc123" in data["vaults"]
    assert data["vaults"]["abc123"]["path"] == "/other/vault"
    assert data["vaults"]["abc123"]["open"] is True
    assert len(data["vaults"]) == 2
```

- [ ] **Step 2: Run — expect PASS**

```bash
.venv/bin/pytest tests/test_obsidian_register.py::test_register_preserves_other_vaults -v
```

Expected: `1 passed` (implementation from 2.2 already handles this via `setdefault` + adding a new key).

- [ ] **Step 3: Commit**

```bash
git add helpers/tests/test_obsidian_register.py
git commit -m "test(obsidian_register): preserve existing vaults on register"
```

### Task 2.4: Test + implement — re-registration is idempotent

- [ ] **Step 1: Add test**

```python
def test_register_same_path_twice_is_noop(fake_obsidian_config, tmp_path):
    fake_obsidian_config.write_text("{}")
    vault = tmp_path / "vault"
    vault.mkdir()

    first = register_vault(vault)
    second = register_vault(vault)

    assert first.status == "registered"
    assert second.status == "already_present"
    data = json.loads(fake_obsidian_config.read_text())
    assert len(data["vaults"]) == 1
```

- [ ] **Step 2: Run — expect PASS**

(Idempotency is already implemented via the path-equality check loop.)

- [ ] **Step 3: Commit**

```bash
git add helpers/tests/test_obsidian_register.py
git commit -m "test(obsidian_register): re-register is idempotent"
```

### Task 2.5: Test — missing obsidian.json returns clean result

- [ ] **Step 1: Add test**

```python
def test_register_missing_obsidian_config_no_error(tmp_path, monkeypatch):
    cfg = tmp_path / "nonexistent" / "obsidian.json"
    monkeypatch.setattr(obsidian_register, "_obsidian_config_path", lambda: cfg)
    vault = tmp_path / "vault"
    vault.mkdir()

    result = register_vault(vault)
    assert result.status == "obsidian_not_installed"
    assert not cfg.exists()  # never created
```

- [ ] **Step 2: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_obsidian_register.py -v
git add helpers/tests/test_obsidian_register.py
git commit -m "test(obsidian_register): missing obsidian.json returns clean result"
```

### Task 2.6: Test — malformed obsidian.json raises clear error without truncating

- [ ] **Step 1: Add test**

```python
def test_register_malformed_json_raises(fake_obsidian_config, tmp_path):
    fake_obsidian_config.write_text("{not valid json")
    vault = tmp_path / "vault"
    vault.mkdir()

    with pytest.raises(ValueError, match="Malformed"):
        register_vault(vault)

    # file should be untouched (not zeroed)
    assert fake_obsidian_config.read_text() == "{not valid json"
```

- [ ] **Step 2: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_obsidian_register.py -v
git add helpers/tests/test_obsidian_register.py
git commit -m "test(obsidian_register): malformed JSON raises without truncating"
```

### Task 2.7: Test — vault id is uuid4 hex[:16]

- [ ] **Step 1: Add test**

```python
def test_register_generates_valid_vault_id(fake_obsidian_config, tmp_path):
    fake_obsidian_config.write_text("{}")
    vault = tmp_path / "vault"
    vault.mkdir()

    register_vault(vault)
    data = json.loads(fake_obsidian_config.read_text())
    vault_id = next(iter(data["vaults"].keys()))
    assert len(vault_id) == 16
    assert all(c in "0123456789abcdef" for c in vault_id)
```

- [ ] **Step 2: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_obsidian_register.py -v
git add helpers/tests/test_obsidian_register.py
git commit -m "test(obsidian_register): vault id is 16-char hex"
```

### Task 2.8: Implement + test `unregister_vault`

- [ ] **Step 1: Add tests first**

```python
def test_unregister_removes_matching_path(fake_obsidian_config, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    register_vault(vault)
    assert len(json.loads(fake_obsidian_config.read_text())["vaults"]) == 1

    result = obsidian_register.unregister_vault(vault)

    assert result.status == "unregistered"
    assert json.loads(fake_obsidian_config.read_text())["vaults"] == {}


def test_unregister_not_present_is_noop(fake_obsidian_config, tmp_path):
    fake_obsidian_config.write_text(json.dumps({"vaults": {}}))
    vault = tmp_path / "vault"
    vault.mkdir()

    result = obsidian_register.unregister_vault(vault)
    assert result.status == "not_present"


def test_unregister_missing_config_is_noop(tmp_path, monkeypatch):
    cfg = tmp_path / "nope" / "obsidian.json"
    monkeypatch.setattr(obsidian_register, "_obsidian_config_path", lambda: cfg)
    vault = tmp_path / "vault"
    vault.mkdir()

    result = obsidian_register.unregister_vault(vault)
    assert result.status == "obsidian_not_installed"
```

- [ ] **Step 2: Run — expect FAIL (`unregister_vault` doesn't exist yet)**

```bash
.venv/bin/pytest tests/test_obsidian_register.py -v
```

- [ ] **Step 3: Implement `unregister_vault`**

Append to `obsidian_register.py`:

```python
def unregister_vault(vault_path: Path) -> RegisterResult:
    cfg = _obsidian_config_path()
    if cfg is None:
        return RegisterResult(status="unsupported_platform")
    if not cfg.exists():
        return RegisterResult(status="obsidian_not_installed")

    try:
        data = json.loads(cfg.read_text() or "{}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed obsidian.json at {cfg}: {e}") from e

    vaults = data.get("vaults", {}) or {}
    target = str(vault_path.resolve())
    to_remove = [vid for vid, entry in vaults.items()
                 if isinstance(entry, dict) and entry.get("path") == target]

    if not to_remove:
        return RegisterResult(status="not_present")

    for vid in to_remove:
        del vaults[vid]
    data["vaults"] = vaults
    _atomic_write_json(cfg, data)
    return RegisterResult(status="unregistered")
```

- [ ] **Step 4: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_obsidian_register.py -v
git add helpers/src/digital_brain_helpers/obsidian_register.py helpers/tests/test_obsidian_register.py
git commit -m "feat(obsidian_register): add unregister_vault inverse"
```

---

## Phase 3 — `session_start.py` + shell wrapper (TDD)

### Task 3.1: Test — no config file → silent exit, empty output

**Files:**
- Create: `helpers/tests/test_session_start.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for digital_brain_helpers.session_start."""
from __future__ import annotations
import io
import json
from pathlib import Path

import pytest

from digital_brain_helpers import session_start


def test_no_config_silent_exit(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = session_start.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
```

- [ ] **Step 2: Run — expect FAIL (module doesn't exist)**

```bash
.venv/bin/pytest tests/test_session_start.py -v
```

### Task 3.2: Implement minimal `session_start.main()`

**Files:**
- Create: `helpers/src/digital_brain_helpers/session_start.py`

- [ ] **Step 1: Minimal impl**

```python
"""Claude Code SessionStart hook: auto-load INDEX or prompt to build."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Optional

from .config import CONFIG_FILENAME, load_config, ConfigNotFoundError, ConfigSchemaError

INDEX_FILENAME = "_INDEX.md"
ADDITIONAL_CONTEXT_LIMIT = 9500  # leave headroom under Claude Code's 10k cap


def _find_config_root(start: Path) -> Optional[Path]:
    """Walk up from `start` until we find a dir containing CONFIG_FILENAME, or hit FS root."""
    cur = start.resolve()
    while True:
        if (cur / CONFIG_FILENAME).exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def _emit(additional_context: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": additional_context,
        }
    }
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")


def main() -> int:
    repo_root = _find_config_root(Path.cwd())
    if repo_root is None:
        return 0

    try:
        cfg = load_config(repo_root)
    except (ConfigNotFoundError, ConfigSchemaError):
        return 0

    vault = cfg.resolved_vault_dir()
    index = vault / INDEX_FILENAME

    if not vault.exists() or not index.exists():
        _emit(
            "No digital-brain vault detected for this project. "
            "Run /refresh-digital-brain to build it (~1-3 min, will write to "
            f"{vault})."
        )
        return 0

    text = index.read_text(errors="replace")
    if len(text) > ADDITIONAL_CONTEXT_LIMIT:
        head = text[:ADDITIONAL_CONTEXT_LIMIT]
        text = (
            head
            + "\n\n…[INDEX truncated — full file at "
            + str(index)
            + ", read it to see all entries]"
        )
    _emit(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run — expect PASS**

```bash
.venv/bin/pytest tests/test_session_start.py::test_no_config_silent_exit -v
```

- [ ] **Step 3: Commit**

```bash
git add helpers/src/digital_brain_helpers/session_start.py helpers/tests/test_session_start.py
git commit -m "feat(session_start): silent exit when no config found"
```

### Task 3.3: Test — config + missing vault → "Build brain" context

- [ ] **Step 1: Add test**

```python
def test_missing_vault_emits_build_prompt(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: digital-brain/\n"
    )
    rc = session_start.main()
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Build brain" in payload["hookSpecificOutput"]["additionalContext"] \
        or "/refresh-digital-brain" in payload["hookSpecificOutput"]["additionalContext"]
```

- [ ] **Step 2: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_session_start.py -v
git add helpers/tests/test_session_start.py
git commit -m "test(session_start): missing vault triggers build prompt"
```

### Task 3.4: Test — config + vault + small INDEX → full INDEX in context

- [ ] **Step 1: Add test**

```python
def test_small_index_emitted_in_full(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    index_content = "# Index\n\nSmall content under 1k chars."
    (vault / "_INDEX.md").write_text(index_content)

    rc = session_start.main()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["hookSpecificOutput"]["additionalContext"] == index_content
```

- [ ] **Step 2: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_session_start.py -v
git add helpers/tests/test_session_start.py
git commit -m "test(session_start): small INDEX emitted in full"
```

### Task 3.5: Test — large INDEX truncated with pointer

- [ ] **Step 1: Add test**

```python
def test_large_index_truncated_with_pointer(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    big = "X" * 12000
    (vault / "_INDEX.md").write_text(big)

    rc = session_start.main()
    payload = json.loads(capsys.readouterr().out)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert len(ctx) < len(big)
    assert "truncated" in ctx
    assert "_INDEX.md" in ctx
```

- [ ] **Step 2: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_session_start.py -v
git add helpers/tests/test_session_start.py
git commit -m "test(session_start): large INDEX truncated with pointer line"
```

### Task 3.6: Test — walks up dirs to find config

- [ ] **Step 1: Add test**

```python
def test_finds_config_in_parent_dir(tmp_path, capsys, monkeypatch):
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)

    rc = session_start.main()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "Build brain" in payload["hookSpecificOutput"]["additionalContext"] \
        or "/refresh-digital-brain" in payload["hookSpecificOutput"]["additionalContext"]
```

- [ ] **Step 2: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_session_start.py -v
git add helpers/tests/test_session_start.py
git commit -m "test(session_start): walks up dirs to find config"
```

### Task 3.7: Create `hooks/session_start.sh` shell wrapper

**Files:**
- Create: `hooks/session_start.sh`

- [ ] **Step 1: Write the wrapper**

```bash
#!/usr/bin/env bash
# digital-brain SessionStart hook: auto-load INDEX or prompt to build.
# Resolves its own install location so the script is install-path-agnostic.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
INSTALL_ROOT="$(cd "$HERE/.." && pwd)"
PYTHON="$INSTALL_ROOT/helpers/.venv/bin/python"
# Guard: if venv was deleted, exit cleanly so the hook doesn't error every session.
[[ -x "$PYTHON" ]] || exit 0
exec "$PYTHON" -m digital_brain_helpers.session_start "$@"
```

- [ ] **Step 2: Make executable + smoke-test**

```bash
chmod +x hooks/session_start.sh
cd /tmp && rm -rf brain-st && mkdir brain-st && cd brain-st
~/Projects/private-brain/hooks/session_start.sh
```

Expected: no output (no config in /tmp/brain-st). Exit code 0.

```bash
echo "source_paths: [.]
vault_dir: vault/" > .digital-brain-config.yaml
~/Projects/private-brain/hooks/session_start.sh
```

Expected: JSON with `hookEventName: "SessionStart"` and `additionalContext` mentioning "Build brain".

```bash
cd ~/Projects/private-brain && rm -rf /tmp/brain-st
```

- [ ] **Step 3: Commit**

```bash
git add hooks/session_start.sh
git commit -m "feat(session_start): add bash wrapper invoking helpers venv"
```

---

## Phase 4 — `cli.py` with `remove` + `uninstall` (TDD)

### Task 4.1: Skeleton `cli.py` + `--help` test

**Files:**
- Create: `helpers/src/digital_brain_helpers/cli.py`
- Create: `helpers/tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for digital_brain_helpers.cli."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from digital_brain_helpers import cli


def test_main_no_args_prints_help_and_exits_nonzero(capsys):
    rc = cli.main([])
    captured = capsys.readouterr()
    assert rc != 0
    assert "remove" in captured.out or "remove" in captured.err
    assert "uninstall" in captured.out or "uninstall" in captured.err
```

- [ ] **Step 2: Run — expect FAIL (module doesn't exist)**

```bash
.venv/bin/pytest tests/test_cli.py -v
```

- [ ] **Step 3: Write minimal skeleton**

```python
"""digital-brain CLI: per-project `remove` and global `uninstall`."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import List, Optional


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="digital-brain")
    sub = p.add_subparsers(dest="command")

    p_remove = sub.add_parser("remove", help="Remove digital-brain from current project")
    p_remove.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    p_uninstall = sub.add_parser("uninstall", help="Uninstall digital-brain globally")
    p_uninstall.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = _build_parser()
    if not argv:
        parser.print_help()
        return 2
    args = parser.parse_args(argv)
    if args.command == "remove":
        return cmd_remove(args)
    if args.command == "uninstall":
        return cmd_uninstall(args)
    parser.print_help()
    return 2


def cmd_remove(args) -> int:
    raise NotImplementedError


def cmd_uninstall(args) -> int:
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/pytest tests/test_cli.py::test_main_no_args_prints_help_and_exits_nonzero -v
```

- [ ] **Step 5: Commit**

```bash
git add helpers/src/digital_brain_helpers/cli.py helpers/tests/test_cli.py
git commit -m "feat(cli): skeleton with remove + uninstall subcommands"
```

### Task 4.2: Install-root discovery helper + tests

The install root layout discriminator is `helpers/pyproject.toml` + `hooks/` + `skills/` — all three present means we've found a real install. Tests must create that full triple.

- [ ] **Step 1: Add a helper for the test fixtures (DRY)**

Append to `tests/test_cli.py`:

```python
def _make_install_root(root: Path) -> Path:
    """Create the minimum layout that `_looks_like_install_root` accepts."""
    (root / "helpers").mkdir(parents=True, exist_ok=True)
    (root / "helpers" / "pyproject.toml").write_text("[project]\nname='x'\n")
    (root / "hooks").mkdir(exist_ok=True)
    (root / "skills").mkdir(exist_ok=True)
    return root
```

- [ ] **Step 2: Add tests for discovery**

```python
def test_resolve_install_root_from_install_json(tmp_path, monkeypatch):
    install_root = _make_install_root(tmp_path / "install")

    db_dir = tmp_path / "dot_digital_brain"
    db_dir.mkdir()
    (db_dir / "install.json").write_text(
        json.dumps({"install_root": str(install_root)})
    )
    monkeypatch.setattr(cli, "_install_json_path", lambda: db_dir / "install.json")

    resolved = cli.resolve_install_root()
    assert resolved == install_root.resolve()


def test_resolve_install_root_falls_back_when_install_json_points_at_deleted_dir(
    tmp_path, monkeypatch
):
    db_dir = tmp_path / "dot_digital_brain"
    db_dir.mkdir()
    (db_dir / "install.json").write_text(
        json.dumps({"install_root": "/definitely/not/here"})
    )
    monkeypatch.setattr(cli, "_install_json_path", lambda: db_dir / "install.json")
    monkeypatch.setattr(cli, "_console_script_symlink", lambda: None)

    with pytest.raises(cli.InstallRootNotFound):
        cli.resolve_install_root()


def test_resolve_install_root_recovers_when_install_json_dir_deleted_but_symlink_works(
    tmp_path, monkeypatch
):
    """install.json points at a deleted dir, but the console symlink reveals the real install."""
    install_root = _make_install_root(tmp_path / "real_install")
    venv_bin = install_root / "helpers" / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    target_script = venv_bin / "digital-brain"
    target_script.write_text("#!/bin/sh\n")
    target_script.chmod(0o755)
    link = tmp_path / "link_digital_brain"
    link.symlink_to(target_script)

    db_dir = tmp_path / "dot_digital_brain"
    db_dir.mkdir()
    (db_dir / "install.json").write_text(
        json.dumps({"install_root": "/definitely/not/here"})
    )
    monkeypatch.setattr(cli, "_install_json_path", lambda: db_dir / "install.json")
    monkeypatch.setattr(cli, "_console_script_symlink", lambda: link)

    resolved = cli.resolve_install_root()
    assert resolved == install_root.resolve()


def test_resolve_install_root_uses_symlink_fallback(tmp_path, monkeypatch):
    install_root = _make_install_root(tmp_path / "fallback_root")
    venv_bin = install_root / "helpers" / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    target_script = venv_bin / "digital-brain"
    target_script.write_text("#!/bin/sh\n")
    target_script.chmod(0o755)

    link = tmp_path / "link_digital_brain"
    link.symlink_to(target_script)

    monkeypatch.setattr(cli, "_install_json_path", lambda: tmp_path / "nonexistent.json")
    monkeypatch.setattr(cli, "_console_script_symlink", lambda: link)

    resolved = cli.resolve_install_root()
    assert resolved == install_root.resolve()
```

- [ ] **Step 3: Run — expect FAIL (helpers don't exist)**

```bash
.venv/bin/pytest tests/test_cli.py -v
```

- [ ] **Step 4: Implement discovery**

Add to `cli.py`:

```python
import json
import os


DEFAULT_INSTALL_JSON = "~/.digital-brain/install.json"
DEFAULT_CONSOLE_SCRIPT = "~/.local/bin/digital-brain"


class InstallRootNotFound(RuntimeError):
    pass


def _install_json_path() -> Path:
    return Path(os.path.expanduser(DEFAULT_INSTALL_JSON))


def _console_script_symlink() -> Optional[Path]:
    p = Path(os.path.expanduser(DEFAULT_CONSOLE_SCRIPT))
    return p if p.is_symlink() else None


def _looks_like_install_root(p: Path) -> bool:
    """Discriminator: a real install always has helpers/pyproject.toml + hooks/ + skills/."""
    return (
        (p / "helpers" / "pyproject.toml").is_file()
        and (p / "hooks").is_dir()
        and (p / "skills").is_dir()
    )


def resolve_install_root() -> Path:
    """Discover install_root via install.json then symlink fallback."""
    ij = _install_json_path()
    if ij.is_file():
        try:
            data = json.loads(ij.read_text())
            candidate = Path(data["install_root"]).resolve()
            if candidate.is_dir() and _looks_like_install_root(candidate):
                return candidate
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    link = _console_script_symlink()
    if link is not None:
        try:
            target = Path(os.readlink(link)).resolve()
            # Walk up looking for install root layout
            for ancestor in [target.parent, *target.parents]:
                if _looks_like_install_root(ancestor):
                    return ancestor.resolve()
        except OSError:
            pass

    raise InstallRootNotFound(
        "Cannot locate digital-brain install root. "
        "Reinstall via `bash <repo>/hooks/install.sh` or remove manually."
    )
```

- [ ] **Step 5: Run — expect PASS**

```bash
.venv/bin/pytest tests/test_cli.py -v
```

- [ ] **Step 6: Commit**

```bash
git add helpers/src/digital_brain_helpers/cli.py helpers/tests/test_cli.py
git commit -m "feat(cli): install root discovery via install.json + symlink fallback"
```

### Task 4.3: `cmd_remove` — exits 1 in non-brain dir

- [ ] **Step 1: Add test**

```python
def test_remove_exits_1_in_non_brain_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["remove", "--yes"])
    captured = capsys.readouterr()
    assert rc == 1
    assert ".digital-brain-config.yaml" in (captured.err or captured.out)
```

- [ ] **Step 2: Run — expect FAIL (NotImplementedError)**

- [ ] **Step 3: Implement minimal `cmd_remove`**

Replace the `cmd_remove` stub:

```python
def cmd_remove(args) -> int:
    repo_root = Path.cwd()
    cfg_path = repo_root / ".digital-brain-config.yaml"
    if not cfg_path.exists():
        print(
            f"ERROR: .digital-brain-config.yaml not found in {repo_root}. "
            "Not a digital-brain project.",
            file=sys.stderr,
        )
        return 1
    # full implementation comes next task
    return 0
```

- [ ] **Step 4: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_cli.py -v
git add helpers/src/digital_brain_helpers/cli.py helpers/tests/test_cli.py
git commit -m "feat(cli): remove exits 1 outside brain project"
```

### Task 4.4: `cmd_remove --yes` — deletes vault, config, copies concept notes to graveyard

- [ ] **Step 1: Add test**

```python
def test_remove_yes_deletes_vault_and_config_preserves_concept_notes(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    # set up brain project
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Concept1.md").write_text(
        "---\nlayer: concept\n---\n\n# Concept 1\nBody.\n"
    )
    (vault / "Extracted.md").write_text(
        "---\ntype: code\n---\n\n# Extracted\nBody.\n"
    )

    # redirect graveyard + obsidian register + install root
    graveyard = tmp_path / "graveyard"
    monkeypatch.setattr(cli, "_graveyard_root", lambda: graveyard)
    monkeypatch.setattr(cli, "unregister_vault_safe", lambda p: None)
    # no install.json — _remove_hook_symlink should still no-op cleanly
    monkeypatch.setattr(cli, "resolve_install_root",
                        lambda: (_ for _ in ()).throw(cli.InstallRootNotFound("no")))

    rc = cli.main(["remove", "--yes"])
    assert rc == 0
    assert not (tmp_path / ".digital-brain-config.yaml").exists()
    assert not vault.exists()
    # graveyard copy of concept note exists; extracted note NOT copied
    grav_files = list(graveyard.rglob("*.md"))
    assert any(f.name == "Concept1.md" for f in grav_files)
    assert not any(f.name == "Extracted.md" for f in grav_files)
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement remove**

Replace `cmd_remove` with full version:

```python
import shutil
import datetime
import re

from .config import load_config, ConfigSchemaError, ConfigNotFoundError
from .frontmatter import read_frontmatter
from .obsidian_register import unregister_vault


def _graveyard_root() -> Path:
    return Path.home() / ".digital-brain-graveyard"


def unregister_vault_safe(vault_path: Path) -> None:
    """Wrap unregister so callers don't need to import obsidian_register directly."""
    try:
        unregister_vault(vault_path)
    except (ValueError, OSError):
        pass


def _project_slug(repo_root: Path) -> str:
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        name = Path(out.stdout.strip()).name
    except (subprocess.CalledProcessError, FileNotFoundError):
        name = repo_root.name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _copy_concepts_to_graveyard(vault: Path, dest: Path) -> int:
    if not vault.exists():
        return 0
    n = 0
    for md in vault.rglob("*.md"):
        try:
            fm = read_frontmatter(md)
        except Exception:
            continue
        if fm.get("layer") == "concept":
            target = dest / md.relative_to(vault)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md, target)
            n += 1
    return n


def _remove_hook_symlink(repo_root: Path) -> None:
    hook = repo_root / ".git" / "hooks" / "post-commit"
    if not hook.is_symlink():
        return
    try:
        install_root = resolve_install_root()
    except InstallRootNotFound:
        print(
            "  warn: cannot resolve install_root, leaving .git/hooks/post-commit in place",
            file=sys.stderr,
        )
        return
    target = Path(os.readlink(hook)).resolve()
    expected_prefix = (install_root / "hooks").resolve()
    try:
        target.relative_to(expected_prefix)
    except ValueError:
        print(
            "  info: .git/hooks/post-commit is not ours, leaving in place",
            file=sys.stderr,
        )
        return
    hook.unlink()


def cmd_remove(args) -> int:
    repo_root = Path.cwd()
    cfg_path = repo_root / ".digital-brain-config.yaml"
    if not cfg_path.exists():
        print(
            f"ERROR: .digital-brain-config.yaml not found in {repo_root}. "
            "Not a digital-brain project.",
            file=sys.stderr,
        )
        return 1

    try:
        cfg = load_config(repo_root)
        vault = cfg.resolved_vault_dir()
    except (ConfigNotFoundError, ConfigSchemaError) as e:
        print(f"ERROR loading config: {e}", file=sys.stderr)
        return 1

    if not args.yes:
        print(f"Remove digital-brain from {repo_root}?")
        print(f"  - delete {vault}/ (concept notes copied to graveyard first)")
        print(f"  - delete {cfg_path}")
        print(f"  - remove .git/hooks/post-commit (only if it's ours)")
        print(f"  - unregister vault from Obsidian")
        resp = input("Continue? (y/N) ").strip().lower()
        if resp not in ("y", "yes"):
            print("Aborted.")
            return 0

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    grave = _graveyard_root() / f"{_project_slug(repo_root)}-{timestamp}"
    n_preserved = _copy_concepts_to_graveyard(vault, grave)
    if n_preserved > 0:
        print(f"  preserved {n_preserved} concept notes to {grave}")

    if vault.exists():
        shutil.rmtree(vault)
        print(f"  deleted {vault}/")
    cfg_path.unlink()
    print(f"  deleted {cfg_path}")

    _remove_hook_symlink(repo_root)
    unregister_vault_safe(vault)

    print(f"digital-brain removed from {repo_root}.")
    return 0
```

- [ ] **Step 4: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_cli.py -v
git add helpers/src/digital_brain_helpers/cli.py helpers/tests/test_cli.py
git commit -m "feat(cli): remove deletes vault + config, preserves concept notes"
```

### Task 4.5: `cmd_remove` — only removes post-commit symlink if ours

- [ ] **Step 1: Add tests**

```python
def test_remove_preserves_foreign_post_commit_hook(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    (tmp_path / "vault").mkdir()
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    foreign_target = tmp_path / "foreign_script.sh"
    foreign_target.write_text("#!/bin/sh\necho foreign\n")
    foreign_target.chmod(0o755)
    hook = tmp_path / ".git" / "hooks" / "post-commit"
    hook.symlink_to(foreign_target)

    monkeypatch.setattr(cli, "_graveyard_root", lambda: tmp_path / "grave")
    monkeypatch.setattr(cli, "unregister_vault_safe", lambda p: None)
    # Fake an install root that does NOT contain the foreign hook
    install_root = tmp_path / "install"
    (install_root / "helpers").mkdir(parents=True)
    (install_root / "helpers" / "pyproject.toml").write_text("[project]\n")
    (install_root / "hooks").mkdir()
    (install_root / "skills").mkdir()
    monkeypatch.setattr(cli, "resolve_install_root", lambda: install_root)

    rc = cli.main(["remove", "--yes"])
    assert rc == 0
    # Foreign hook should still be present
    assert hook.exists() and hook.is_symlink()
    assert Path(os.readlink(hook)) == foreign_target


def test_remove_removes_our_post_commit_hook(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    (tmp_path / "vault").mkdir()
    (tmp_path / ".git" / "hooks").mkdir(parents=True)

    install_root = tmp_path / "install"
    (install_root / "helpers").mkdir(parents=True)
    (install_root / "helpers" / "pyproject.toml").write_text("[project]\n")
    (install_root / "hooks").mkdir()
    (install_root / "skills").mkdir()
    our_hook = install_root / "hooks" / "post-commit"
    our_hook.write_text("#!/bin/sh\n")
    our_hook.chmod(0o755)
    hook_link = tmp_path / ".git" / "hooks" / "post-commit"
    hook_link.symlink_to(our_hook)

    monkeypatch.setattr(cli, "_graveyard_root", lambda: tmp_path / "grave")
    monkeypatch.setattr(cli, "unregister_vault_safe", lambda p: None)
    monkeypatch.setattr(cli, "resolve_install_root", lambda: install_root)

    rc = cli.main(["remove", "--yes"])
    assert rc == 0
    assert not hook_link.exists()
```

- [ ] **Step 2: Run — both should PASS (logic already implemented in 4.4)**

```bash
.venv/bin/pytest tests/test_cli.py -v
```

If a test fails because of subtle path resolution, debug. Commit on green.

- [ ] **Step 3: Commit**

```bash
git add helpers/tests/test_cli.py
git commit -m "test(cli): remove respects foreign post-commit hooks"
```

### Task 4.6: `cmd_uninstall --yes` — removes only our entries from settings.json

- [ ] **Step 1: Add test**

```python
def test_uninstall_removes_only_our_hook_entries(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".claude").mkdir()
    settings = fake_home / ".claude" / "settings.json"

    install_root = tmp_path / "install"
    (install_root / "helpers").mkdir(parents=True)
    (install_root / "helpers" / "pyproject.toml").write_text("[project]\n")
    (install_root / "hooks").mkdir()
    (install_root / "skills").mkdir()
    (install_root / "skills" / "refresh-digital-brain").mkdir()
    (install_root / "skills" / "load-digital-brain").mkdir()

    settings.write_text(json.dumps({
        "hooks": {
            "SessionStart": [
                {"matcher": "*", "hooks": [
                    {"type": "command", "command": str(install_root / "hooks" / "session_start.sh")}
                ]},
                {"matcher": "*", "hooks": [
                    {"type": "command", "command": "/usr/local/bin/other-hook.sh"}
                ]},
            ]
        }
    }))

    (fake_home / ".claude" / "skills").mkdir()
    skill_link_refresh = fake_home / ".claude" / "skills" / "refresh-digital-brain"
    skill_link_load = fake_home / ".claude" / "skills" / "load-digital-brain"
    skill_link_refresh.symlink_to(install_root / "skills" / "refresh-digital-brain")
    skill_link_load.symlink_to(install_root / "skills" / "load-digital-brain")

    (fake_home / ".local" / "bin").mkdir(parents=True)
    console_link = fake_home / ".local" / "bin" / "digital-brain"
    console_target = install_root / "helpers" / ".venv" / "bin" / "digital-brain"
    console_target.parent.mkdir(parents=True)
    console_target.write_text("#!/bin/sh\n")
    console_target.chmod(0o755)
    console_link.symlink_to(console_target)

    (fake_home / ".digital-brain").mkdir()
    (fake_home / ".digital-brain" / "install.json").write_text(
        json.dumps({"install_root": str(install_root)})
    )

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(cli, "resolve_install_root", lambda: install_root)

    rc = cli.main(["uninstall", "--yes"])
    assert rc == 0

    new_settings = json.loads(settings.read_text())
    sessionstart = new_settings["hooks"]["SessionStart"]
    assert len(sessionstart) == 1
    assert sessionstart[0]["hooks"][0]["command"] == "/usr/local/bin/other-hook.sh"

    assert not skill_link_refresh.exists()
    assert not skill_link_load.exists()
    assert not console_link.exists()
    assert not (fake_home / ".digital-brain" / "install.json").exists()
```

- [ ] **Step 2: Run — expect FAIL (`cmd_uninstall` is NotImplementedError)**

- [ ] **Step 3: Implement `cmd_uninstall`**

```python
def _matches_our_command(cmd: str, install_root: Path) -> bool:
    if not cmd:
        return False
    try:
        cmd_path = Path(os.path.expanduser(cmd)).resolve()
        return cmd_path.is_relative_to((install_root / "hooks").resolve())
    except (ValueError, OSError):
        return False


def _scrub_settings(settings_path: Path, install_root: Path) -> None:
    if not settings_path.exists():
        return
    data = json.loads(settings_path.read_text() or "{}")
    hooks = data.get("hooks", {})
    for event_name, entries in list(hooks.items()):
        if not isinstance(entries, list):
            continue
        kept = []
        for entry in entries:
            sub = entry.get("hooks", []) if isinstance(entry, dict) else []
            sub_kept = [
                s for s in sub
                if not (
                    isinstance(s, dict)
                    and s.get("type") == "command"
                    and _matches_our_command(s.get("command", ""), install_root)
                )
            ]
            if sub_kept:
                kept.append({**entry, "hooks": sub_kept})
        if kept:
            hooks[event_name] = kept
        else:
            del hooks[event_name]
    if hooks:
        data["hooks"] = hooks
    elif "hooks" in data:
        del data["hooks"]
    settings_path.write_text(json.dumps(data, indent=2))


def cmd_uninstall(args) -> int:
    try:
        install_root = resolve_install_root()
    except InstallRootNotFound as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not args.yes:
        print("Uninstall digital-brain globally?")
        print("  - remove ~/.claude/skills/{refresh,load}-digital-brain symlinks")
        print("  - remove SessionStart + Stop hook entries from ~/.claude/settings.json")
        print("  - remove ~/.local/bin/digital-brain symlink")
        print("  - remove ~/.digital-brain/install.json")
        print("  Per-project brains NOT removed.")
        resp = input("Continue? (y/N) ").strip().lower()
        if resp not in ("y", "yes"):
            print("Aborted.")
            return 0

    home = Path.home()
    for skill in ("refresh-digital-brain", "load-digital-brain"):
        link = home / ".claude" / "skills" / skill
        if link.is_symlink():
            try:
                target = Path(os.readlink(link)).resolve()
                if target.is_relative_to(install_root.resolve()):
                    link.unlink()
                    print(f"  removed {link}")
            except (ValueError, OSError):
                pass

    _scrub_settings(home / ".claude" / "settings.json", install_root)
    print(f"  scrubbed digital-brain entries from ~/.claude/settings.json")

    console = home / ".local" / "bin" / "digital-brain"
    if console.is_symlink():
        try:
            target = Path(os.readlink(console)).resolve()
            if target.is_relative_to(install_root.resolve()):
                console.unlink()
                print(f"  removed {console}")
        except (ValueError, OSError):
            pass

    install_json = home / ".digital-brain" / "install.json"
    if install_json.exists():
        install_json.unlink()
        try:
            install_json.parent.rmdir()
        except OSError:
            pass
        print(f"  removed {install_json}")

    print(
        f"\nGlobal uninstall complete. Source repo at {install_root} left intact. "
        "Per-project brains not removed — run `digital-brain remove` inside each project first."
    )
    return 0
```

- [ ] **Step 4: Run — expect PASS, commit**

```bash
.venv/bin/pytest tests/test_cli.py -v
git add helpers/src/digital_brain_helpers/cli.py helpers/tests/test_cli.py
git commit -m "feat(cli): uninstall scrubs our entries, preserves others"
```

### Task 4.7: Coverage check + console script smoke test

- [ ] **Step 1: Re-enable coverage gate if it was lowered**

Open `helpers/pyproject.toml` and verify:

```toml
addopts = "--cov=digital_brain_helpers --cov-fail-under=80"
```

If you lowered `--cov-fail-under` during Task 1.1 Step 6, set it back to 80 now.

- [ ] **Step 2: Full pytest run**

```bash
cd ~/Projects/private-brain/helpers
.venv/bin/pytest -v --cov-report=term-missing
```

Expected: all tests pass, coverage ≥80% for `obsidian_register`, `session_start`, `cli`. If below 80% on any module, add tests for uncovered branches before continuing. The `--cov-fail-under=80` from pyproject will fail the suite if below.

- [ ] **Step 3: Verify the `digital-brain` console script is callable**

```bash
.venv/bin/digital-brain --help
```

Expected: argparse help text listing `remove` and `uninstall`.

- [ ] **Step 4: Commit any coverage-driven test additions**

```bash
cd ~/Projects/private-brain
git add helpers/
git commit -m "test: add coverage for cli + session_start edge cases" --allow-empty
```

---

## Phase 5 — Rewrite `install.sh`

### Task 5.1: Settings.json patcher (Python helper)

**Files:**
- Create: `helpers/src/digital_brain_helpers/install_helpers.py`
- Create: `helpers/tests/test_install_helpers.py`

**Spec deviation note:** Spec §4 lists three new Python modules (`obsidian_register`, `session_start`, `cli`). This task introduces a fourth — `install_helpers` — to keep the settings.json patching + install.json write logic out of bash and inside testable Python. Reasoning: spec §5 install.sh step 7 says "Implemented as a Python helper invoked from the shell script, doing a deep merge" but does not name the helper. Treating it as a small new module rather than stuffing the logic into `cli.py` keeps `cli.py` user-facing and `install_helpers.py` install-time-only — cleaner boundary. Spec should be amended to acknowledge this fourth module on next revision.

- [ ] **Step 1: Write failing test**

```python
"""Tests for install_helpers."""
import json
from pathlib import Path

import pytest

from digital_brain_helpers import install_helpers


def test_patch_empty_settings_adds_hooks(tmp_path):
    settings = tmp_path / "settings.json"
    install_root = tmp_path / "install"
    install_helpers.patch_settings(settings, install_root)

    data = json.loads(settings.read_text())
    assert "SessionStart" in data["hooks"]
    assert "Stop" in data["hooks"]
    ss_cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert ss_cmd == str(install_root / "hooks" / "session_start.sh")


def test_patch_preserves_existing_hooks(tmp_path):
    settings = tmp_path / "settings.json"
    install_root = tmp_path / "install"
    settings.write_text(json.dumps({
        "hooks": {
            "SessionStart": [
                {"matcher": "*", "hooks": [
                    {"type": "command", "command": "/other/hook.sh"}
                ]}
            ]
        }
    }))
    install_helpers.patch_settings(settings, install_root)

    data = json.loads(settings.read_text())
    cmds = [
        h["command"]
        for entry in data["hooks"]["SessionStart"]
        for h in entry["hooks"]
    ]
    assert "/other/hook.sh" in cmds
    assert str(install_root / "hooks" / "session_start.sh") in cmds


def test_patch_is_idempotent(tmp_path):
    settings = tmp_path / "settings.json"
    install_root = tmp_path / "install"
    install_helpers.patch_settings(settings, install_root)
    install_helpers.patch_settings(settings, install_root)

    data = json.loads(settings.read_text())
    ss = data["hooks"]["SessionStart"]
    cmds = [h["command"] for entry in ss for h in entry["hooks"]]
    assert cmds.count(str(install_root / "hooks" / "session_start.sh")) == 1
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
"""Helpers for install.sh — invoked as `python -m digital_brain_helpers.install_helpers patch <settings_path> <install_root>`."""
from __future__ import annotations
import json
import os
import sys
import tempfile
from pathlib import Path


def patch_settings(settings_path: Path, install_root: Path) -> None:
    install_root = Path(install_root)
    if settings_path.exists():
        data = json.loads(settings_path.read_text() or "{}")
    else:
        data = {}
    hooks = data.setdefault("hooks", {})

    targets = {
        "SessionStart": str(install_root / "hooks" / "session_start.sh"),
        "Stop": str(install_root / "hooks" / "stale_check.sh"),
    }
    for event, command in targets.items():
        entries = hooks.setdefault(event, [])
        existing_cmds = [
            h.get("command")
            for entry in entries
            if isinstance(entry, dict)
            for h in entry.get("hooks", [])
            if isinstance(h, dict)
        ]
        if command in existing_cmds:
            continue
        entries.append({
            "matcher": "*",
            "hooks": [{"type": "command", "command": command}],
        })

    _atomic_write(settings_path, json.dumps(data, indent=2))


def write_install_json(install_json_path: Path, install_root: Path, version: str) -> None:
    import datetime
    payload = {
        "install_root": str(install_root.resolve()),
        "installed_at": datetime.datetime.now(datetime.timezone.utc)
            .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "version": version,
    }
    install_json_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(install_json_path, json.dumps(payload, indent=2))


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode="w", dir=str(path.parent), delete=False, suffix=".tmp"
    )
    try:
        tmp.write(content)
        tmp.close()
        os.replace(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass
        raise


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: install_helpers {patch,install-json} ...", file=sys.stderr)
        return 2
    cmd, *rest = argv
    if cmd == "patch" and len(rest) == 2:
        patch_settings(Path(rest[0]), Path(rest[1]))
        return 0
    if cmd == "install-json" and len(rest) == 3:
        write_install_json(Path(rest[0]), Path(rest[1]), rest[2])
        return 0
    print(f"unknown invocation: {argv}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/pytest tests/test_install_helpers.py -v
```

- [ ] **Step 5: Commit**

```bash
git add helpers/src/digital_brain_helpers/install_helpers.py helpers/tests/test_install_helpers.py
git commit -m "feat(install_helpers): patch settings + write install.json with idempotent merge"
```

### Task 5.2: Rewrite `hooks/install.sh`

**Files:**
- Modify: `hooks/install.sh` (full rewrite)

- [ ] **Step 1: Replace `install.sh` content**

```bash
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

# 7. Write install.json — LAST step so its presence is a "fully installed" signal
# (Read version via the helpers module so we don't depend on tomllib, which is 3.11+.)
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
```

- [ ] **Step 2: Dry-run install in a clean fake-home env**

```bash
cd ~/Projects/private-brain
FAKE_HOME=$(mktemp -d)
HOME="$FAKE_HOME" bash hooks/install.sh
echo "---"
ls -la "$FAKE_HOME/.claude/skills/"
cat "$FAKE_HOME/.digital-brain/install.json"
echo "---"
cat "$FAKE_HOME/.claude/settings.json"
rm -rf "$FAKE_HOME"
```

Expected:
- Two skill symlinks listed.
- `install.json` shows `install_root` = `~/Projects/private-brain` (current dir, since you haven't renamed yet).
- `settings.json` shows SessionStart + Stop entries.

The console-script symlink will fail this test because `$FAKE_HOME/.local/bin/digital-brain` is overwritten in the real venv; that's fine for the dry-run. The PATH warning may or may not fire depending on the test env.

- [ ] **Step 3: Commit**

```bash
git add hooks/install.sh
git commit -m "refactor(install): rewrite for global symlinks + install.json discovery"
```

---

## Phase 6 — Skill prompt updates (citation + wikilink + post-build INDEX read)

### Task 6.1: Extend `refresh-digital-brain/SKILL.md` with Obsidian register + post-build INDEX read + citation format

**Files:**
- Modify: `skills/refresh-digital-brain/SKILL.md`

- [ ] **Step 1: Add a new step after the existing Step 6 (or wherever the build success summary lives)**

Insert a new "Step 7 — Register vault with Obsidian and load INDEX into context".

Write exactly this block into the SKILL.md (no alternatives — use the Python `-c` form because `obsidian_register` exposes only the module-level `register_vault(Path)` function in v0, not a CLI flag):

````markdown
### Step 7 — Register vault with Obsidian + load INDEX

After the vault is built, register it with Obsidian and read the freshly-written INDEX into your context so the user can use it immediately without running `/load-digital-brain` separately.

```bash
"$HELPERS_VENV" -c "
from pathlib import Path
from digital_brain_helpers.obsidian_register import register_vault
result = register_vault(Path('$VAULT_DIR').resolve())
print(f'[obsidian-register] {result.status}: {result.message}')
"
```

(If Obsidian is not installed, the helper returns `status=obsidian_not_installed` and the build succeeds anyway.)

Then use the Read tool on `$VAULT_DIR/_INDEX.md` and tell the user:

```
Brain built and registered with Obsidian. INDEX loaded into context. Ready to use.
```
````

- [ ] **Step 2: Add the citation format convention**

Near the top of the SKILL.md (after the `## Usage` block), add a new section:

````markdown
## Citation format for vault nodes

When you reference a vault node in chat (during or after this skill runs), format the first mention per turn as:

```
[[NodeName]] ([source](src/path.py#L42), [vault](obsidian://open?vault=<vault-name>&file=NodeName.md))
```

Subsequent mentions in the same turn can use bare `[[NodeName]]`. Use `urllib.parse.quote` (or shell `python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "<name>"`) to encode the vault name and file name if they contain spaces or reserved characters.
````

- [ ] **Step 3: Verify the SKILL still passes the prerequisite checks** (manual eyeball — no automated test for skill files)

```bash
grep -nE "private-brain|project-brain|/refresh-brain|/load-brain|\.brain-config\.yaml" skills/refresh-digital-brain/SKILL.md
```

Expected: zero matches.

- [ ] **Step 4: Commit**

```bash
git add skills/refresh-digital-brain/SKILL.md
git commit -m "feat(refresh-skill): register Obsidian + load INDEX + citation format"
```

### Task 6.2: Extend `load-digital-brain/SKILL.md` with citation format + wikilink resolver

**Files:**
- Modify: `skills/load-digital-brain/SKILL.md`

- [ ] **Step 1: Add citation format section (same as refresh skill)**

Copy the "Citation format for vault nodes" section from Task 6.1 Step 2 into this SKILL.md as well (above the `## Errors` section).

- [ ] **Step 2: Add wikilink resolver instruction**

Add a new section after "Step 3 — Set the working principle":

````markdown
### Wikilink resolver

If a user message contains `[[NodeName]]`, resolve `NodeName` to `<vault_dir>/<NodeName>.md`. If the exact filename does not exist, glob for `<vault_dir>/**/<NodeName>.md` (handles community-level filenames or nested layout). Read the resolved file using the Read tool before responding. If no match found, say so explicitly rather than guessing.

This convention is always on while the brain is loaded. It lets the user reference any vault node in chat without typing a full file path.
````

- [ ] **Step 3: Verify no stale refs + commit**

```bash
grep -nE "private-brain|project-brain|/refresh-brain|/load-brain|\.brain-config\.yaml" skills/load-digital-brain/SKILL.md
git add skills/load-digital-brain/SKILL.md
git commit -m "feat(load-skill): citation format + wikilink resolver convention"
```

---

## Phase 7 — README rewrite + repo dir rename

### Task 7.1: Rewrite `README.md` for digital-brain

**Files:**
- Modify: `README.md` (full rewrite — current content is private-gpt-specific)

- [ ] **Step 1: Replace README content**

Write a new README following the structure of the original but with:
- Title: `# digital-brain`
- Status line: `**Status: v0 MVP (2026-05-23).**` (or current date)
- All references to `private-gpt-fork`, `private_gpt/`, retrieval-pipeline examples removed or genericized.
- Quickstart section reflects the new install flow: `git clone`, `pip install -e ".[dev]"`, `bash hooks/install.sh`.
- "Per-project setup" section reflects new `.digital-brain-config.yaml` + the auto-prompt-to-build flow (no manual `/refresh-digital-brain` call needed first session — just `claude` and Claude asks).
- Daily workflow table: same shape but updated slash command names.
- Removal section added: `digital-brain remove` per-project, `digital-brain uninstall` global.
- Mentions the new SessionStart auto-load + auto-build-prompt and Obsidian auto-registration features.

The exact content is left to the implementer's judgment; aim for ~150 lines. Use the original README's structure as a guide.

- [ ] **Step 2: Verify no stale refs**

```bash
grep -nE "private-gpt|private_gpt|private-brain|project-brain|\.brain-config\.yaml" README.md
```

Expected: zero matches.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for digital-brain v0"
```

### Task 7.2: Rename repo dir `~/Projects/private-brain` → `~/Projects/digital-brain`

**Files:** the directory itself.

- [ ] **Step 1: Stop any running services that might hold file handles**

If Obsidian has the old vault open, close it. Any editor with files open in this dir — close them.

- [ ] **Step 2: Rename dir + verify git remote still works**

```bash
cd ~/Projects
mv private-brain digital-brain
cd digital-brain
git status
```

Expected: `git status` works (git stores no absolute paths in `.git/`). Branch should still be `digital-brain-rename`.

- [ ] **Step 3: Recreate venv (its shebangs point at the old path)**

```bash
cd ~/Projects/digital-brain/helpers
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Update CLAUDE.md / shell aliases / shortcuts** (if any reference `~/Projects/private-brain`)

```bash
grep -rn "~/Projects/private-brain\|Projects/private-brain" ~/.zshrc ~/.bashrc ~/.config 2>/dev/null
```

If any matches, update manually.

- [ ] **Step 5: Re-run install.sh from the new location**

Any earlier non-dry-run install (during Phase 5 or local testing) would have written `~/.digital-brain/install.json` pointing at the OLD `~/Projects/private-brain` path, and put `~/.claude/skills/*` symlinks pointing there too. After the dir rename those targets are dangling. Re-run install.sh so all of that is rewritten to the new path:

```bash
cd ~/Projects/digital-brain
bash hooks/install.sh
```

Expected: success messages; `cat ~/.digital-brain/install.json` now shows `install_root: ~/Projects/digital-brain`.

If no real install ever happened (only the FAKE_HOME dry-run in Task 5.2), this re-run is the FIRST real install — same command, same expected outcome.

- [ ] **Step 6: Verify git status + tag the rename**

```bash
git status
```

Expected: clean. The dir rename is filesystem-only — git does not track parent dir names.

```bash
git tag repo-dir-renamed
```

Gives a checkpoint to revert to if Phase 8 surfaces issues with venv shebangs or install paths.

---

## Phase 8 — Manual smoke test

### Task 8.1: End-to-end manual verification (per spec §6)

This is not automated. Run through each step and confirm the observed behavior matches the expected behavior. Take notes on anything that surprises you.

- [ ] **Step 1: Run global install (real environment)**

```bash
cd ~/Projects/digital-brain
bash hooks/install.sh
```

Expected: success messages for each step, final "Install complete" block. Check:
- `ls -la ~/.claude/skills/refresh-digital-brain ~/.claude/skills/load-digital-brain` — two symlinks
- `cat ~/.digital-brain/install.json` — install_root + timestamp + version
- `cat ~/.claude/settings.json | python3 -m json.tool` — hooks present
- `which digital-brain` — resolves (if `~/.local/bin` is on PATH)

- [ ] **Step 2: Create a fresh test project**

```bash
mkdir /tmp/dbtest && cd /tmp/dbtest
git init
echo "def foo(): pass" > main.py
git add . && git -c user.email=t@t -c user.name=T commit -m init
echo "source_paths: [.]
vault_dir: digital-brain/" > .digital-brain-config.yaml
echo "digital-brain/" >> .gitignore
ln -sf ~/Projects/digital-brain/hooks/post-commit .git/hooks/post-commit
```

- [ ] **Step 3: Open a new Claude Code session in `/tmp/dbtest`**

```bash
cd /tmp/dbtest && claude
```

Expected: SessionStart hook fires. Note that Claude Code injects the hook's `additionalContext` into the system context — Claude is NOT obligated to surface it verbatim in its first reply. To verify the hook actually fired, do one of:

- Run the hook standalone first to confirm it produces JSON:
  ```bash
  cd /tmp/dbtest && ~/Projects/digital-brain/hooks/session_start.sh | python3 -m json.tool
  ```
  Expected: JSON with `"hookEventName": "SessionStart"` and `additionalContext` containing "Build brain" or `/refresh-digital-brain`.

- Then start Claude and prompt it directly: "Is there a digital-brain vault loaded in your context?" — Claude should mention the build prompt or recognize the brain context is missing.

Either signal is acceptable confirmation.

- [ ] **Step 4: Run `/refresh-digital-brain` in that Claude session**

Expected: vault built, Obsidian auto-registered, INDEX loaded into context. Verify:
- `ls /tmp/dbtest/digital-brain/` — has `.md` files + `_INDEX.md`
- Open Obsidian → vault list should show `dbtest` (or similar path)
- Claude says "Brain built and registered with Obsidian. INDEX loaded."

- [ ] **Step 5: Quit Claude. Re-open in same dir**

Expected: SessionStart auto-loads INDEX (not the "Build brain" prompt this time).

- [ ] **Step 6: Edit a file + commit. Watch post-commit hook**

```bash
cd /tmp/dbtest
echo "def bar(): pass" >> main.py
git commit -am "add bar"
```

Expected: post-commit hook fires, ~3 sec delay, `digital-brain/_INDEX.md` `last_refresh_commit` field updates to new SHA.

- [ ] **Step 7: Run `digital-brain remove` in the test project**

```bash
cd /tmp/dbtest
digital-brain remove
# answer 'y' to confirm
```

Expected: vault deleted, config deleted, post-commit symlink removed. Concept notes (if any) copied to `~/.digital-brain-graveyard/dbtest-<timestamp>/`.

- [ ] **Step 8: Run `digital-brain uninstall`**

```bash
digital-brain uninstall
# answer 'y' to confirm
```

Expected: skill symlinks gone, settings.json scrubbed of digital-brain entries, console script symlink gone, install.json removed. `~/Projects/digital-brain/` source repo untouched.

- [ ] **Step 9: Cleanup**

```bash
rm -rf /tmp/dbtest ~/.digital-brain-graveyard
```

- [ ] **Step 10: Record outcomes**

For any step that didn't behave as expected, file an issue (or note inline if running solo) before declaring the work complete.

---

## Phase 9 — Finalize

### Task 9.1: Squash + merge to main

- [ ] **Step 1: Verify everything is green**

```bash
cd ~/Projects/digital-brain/helpers
.venv/bin/pytest -v
```

- [ ] **Step 2: Push branch + open PR (or fast-forward merge to main if solo)**

```bash
cd ~/Projects/digital-brain
git log --oneline rename-complete-iter-0..HEAD
```

Confirm the commit history is the set of phases above. Decide squash vs merge.

For solo merge:

```bash
git checkout main
git merge --ff-only digital-brain-rename
git branch -d digital-brain-rename
git tag v0.1.0
```

- [ ] **Step 3: Delete the baseline tag**

```bash
git tag -d rename-complete-iter-0
```

- [ ] **Step 4: (Optional) Push to GitHub**

If publishing as a public/private repo:

```bash
gh repo create digital-brain --private
git remote add origin git@github.com:<user>/digital-brain.git
git push -u origin main --tags
```

---

## Out of scope (deferred to v1)

These are explicitly NOT implemented in this plan. See spec §1 for the full deferred list:

- `/init-digital-brain` auto-bootstrap of `.digital-brain-config.yaml`
- Incremental refresh
- LLM-driven community labels
- `type: business` notes
- Focused `/load-digital-brain <keyword>`
- File-watcher daemon
- Backward-compat shim for old `.brain-config.yaml` (hard break per spec)
- Windows support for `obsidian_register`
- Lockfile coordination between concurrent refresh + uninstall

If a future requirement surfaces any of these, write a separate spec + plan rather than bolting onto this work.
