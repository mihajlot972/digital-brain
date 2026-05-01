# Project Brain v1 — Full Production Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`). This plan builds on v0 MVP (`2026-05-01-project-brain-v0-mvp.md`) — execute v0 first.

**Goal:** Production-ready system per `docs/project-brain-instruction.md` spec. Adds `/init-brain`, incremental refresh, business notes, inventory stop point, `/load-brain` Scenarios B/C, code-review trail, and extraction to a standalone `project-brain` git repo for cross-project use.

**Architecture:** Same as v0 (Bash + Python helpers + Claude prompts in SKILL.md), extended with: a third skill (`/init-brain`), additional helpers (`git_diff.py`, `stale_detection.py`, `inventory.py`, `business_writer.py`), and a one-time extraction phase that moves everything to a standalone repo with symlinks back into projects.

**Tech Stack:** Same as v0 + `gitpython` (for richer diff parsing) — install via existing helpers venv.

**Prereq:** v0 MVP plan implemented and validated end-to-end on `private-gpt-fork`.

**Reference spec:** `docs/project-brain-instruction.md`

---

## What changes from v0

| Area | v0 | v1 |
|------|----|----|
| Skills | `/refresh-brain`, `/load-brain` | + `/init-brain` |
| Refresh mode | Full rebuild only | + Incremental (git diff) |
| Note types | `type: code` only | + `type: business` with cross-links |
| Stop points | None | + Inventory gate (first-run), refresh-candidate gate (incremental) |
| `/load-brain` | Scenario A only | + B (focused), + C (status) |
| Stale detection | None | `last_source_hash` per concept note |
| Code review | None | `.last-refresh-diff.md` generated each refresh |
| Repo location | `.claude/skills/` of host repo | Standalone `project-brain` repo, symlinked into `~/.claude/skills/` |

---

## File Structure (additions over v0)

```
.claude/skills/init-brain/SKILL.md                          # NEW
.claude/skills/_brain_helpers/git_diff.py                   # NEW
.claude/skills/_brain_helpers/stale_detection.py            # NEW
.claude/skills/_brain_helpers/inventory.py                  # NEW
.claude/skills/_brain_helpers/project_detect.py             # NEW (for /init-brain heuristics)
.claude/skills/_brain_helpers/diff_report.py                # NEW (.last-refresh-diff.md writer)
.claude/skills/_brain_helpers/tests/test_git_diff.py        # NEW
.claude/skills/_brain_helpers/tests/test_stale_detection.py # NEW
.claude/skills/_brain_helpers/tests/test_inventory.py       # NEW
.claude/skills/_brain_helpers/tests/test_project_detect.py  # NEW
.claude/skills/_brain_helpers/tests/test_diff_report.py     # NEW
```

Modified:
- `.claude/skills/refresh-brain/SKILL.md` — gain incremental mode + inventory gate + business notes
- `.claude/skills/load-brain/SKILL.md` — gain Scenarios B and C
- `.claude/skills/_brain_helpers/index_writer.py` — count business notes, surface staleness

After Phase N (extraction), all of the above plus `_brain_helpers/` move to `~/dev/project-brain/`. Host repos keep only `.brain-config.yaml`.

---

## Phase H: `/init-brain` skill

**Goal:** Bootstrap a new project — detect structure, propose `.brain-config.yaml`, write it, modify `.gitignore`.

### Task H1: project_detect helper (TDD)

**Files:** `_brain_helpers/project_detect.py`, `tests/test_project_detect.py`

- [ ] **Test cases:**
  - Python project (presence of `pyproject.toml`/`setup.py`) → suggest top-level package dir or `src/`
  - Python project with `src/` layout → suggest `src/`
  - Node monorepo (`packages/` with multiple subdirs) → suggest `packages/<largest>/src/`
  - Node single (`package.json` + `src/`) → suggest `src/`
  - Go project (`go.mod` + `cmd/` or `internal/`) → suggest those
  - Unknown → suggest `.`
- [ ] **Implementation:** `detect_project(repo_root: Path) -> ProjectGuess` returns `ProjectGuess(language: str, suggested_source_paths: List[str], confidence: str)`
- [ ] **Commit:** `feat(brain): add project structure detection`

### Task H2: `/init-brain` SKILL.md

**Files:** `.claude/skills/init-brain/SKILL.md`

- [ ] Pre-checks: `.brain-config.yaml` doesn't already exist; `graphify` installed
- [ ] Run `project_detect` → propose config
- [ ] **STOP POINT:** show user proposed config (in plain language) — "I think your sources are X based on Y; vault dir will be `project-brain/`. Edit anything before I save?"
- [ ] On user confirm: write `.brain-config.yaml`, append `<vault_dir>/` to `.gitignore` (idempotent — check first)
- [ ] Print: "Initialized. Run /refresh-brain next."
- [ ] **Commit:** `feat(brain): add /init-brain skill with structure detection`

### Task H3: e2e on a fresh test repo

- [ ] Create `/tmp/test-init-repo/` with a small Python project structure
- [ ] Run `/init-brain` from inside it
- [ ] Verify `.brain-config.yaml` matches expectation
- [ ] Verify `.gitignore` updated
- [ ] **Commit:** `test(brain): verify /init-brain on synthetic repo`

---

## Phase I: Incremental refresh + stale detection

**Goal:** `/refresh-brain` second run only refreshes affected notes (not full rebuild). Adds `last_source_hash` for stale detection.

### Task I1: git_diff helper (TDD)

**Files:** `_brain_helpers/git_diff.py`, `tests/test_git_diff.py`

- [ ] **Test cases:**
  - `changed_files_since(repo, commit_sha, paths)` returns list of paths that changed in `paths` between `commit_sha` and HEAD
  - Handles uncommitted changes (warn, do not include in diff)
  - Handles `commit_sha` not found (raise clear error)
  - Empty diff → empty list
- [ ] **Implementation:** wrap `git diff --name-only` via subprocess; or use `gitpython` if available
- [ ] **Commit:** `feat(brain): add git_diff helper`

### Task I2: stale_detection helper (TDD)

**Files:** `_brain_helpers/stale_detection.py`, `tests/test_stale_detection.py`

- [ ] **Test cases:**
  - Compute `current_source_hash(source_paths) -> str` = short SHA of last commit touching any file in source_paths
  - Detect stale concept notes: iterate vault, for each concept note check if `last_source_hash` matches `current_source_hash(note.source_paths)`
  - Returns `StaleReport(stale: List[Path], fresh: List[Path])`
- [ ] **Implementation:** uses `git_diff` + `frontmatter` helpers
- [ ] **Commit:** `feat(brain): add stale detection helper`

### Task I3: Wire incremental mode into `/refresh-brain`

**Files:** `.claude/skills/refresh-brain/SKILL.md` (modify)

- [ ] If `_INDEX.md` exists: read `last_refresh_commit` → diff source_paths → if empty, exit "Nothing to refresh"
- [ ] Run `graphify --update` (instead of full extraction)
- [ ] Compute stale concept notes via `stale_detection.detect_stale(vault, source_paths)`
- [ ] **STOP POINT:** show user list: "These N concept notes are stale (changed source files). Refresh them? [Y/edit/skip]"
- [ ] On confirm: rewrite each affected note, update `last_source_hash` to current
- [ ] Update `_INDEX.md` `last_refresh_commit` to current HEAD
- [ ] **Commit:** `feat(brain): add incremental refresh mode`

### Task I4: Add `last_source_hash` to first-run note generation

- [ ] When writing concept notes (first-run or refresh), set `last_source_hash` = current SHA of source_paths at write time
- [ ] **Commit:** `feat(brain): emit last_source_hash on concept notes`

### Task I5: e2e test of incremental flow

- [ ] Run `/refresh-brain` (already done from v0)
- [ ] Make a small change in `private_gpt/components/retrieval/` and commit
- [ ] Run `/refresh-brain` again — verify only retrieval-related concept notes are flagged stale
- [ ] **Commit:** `test(brain): verify incremental refresh detects only affected notes`

---

## Phase J: Inventory stop point (first-run only)

**Goal:** First-run, before writing concept notes, Claude proposes a 10–20 item "concept inventory" that user reviews and edits. Prevents Claude from inventing irrelevant concepts.

### Task J1: inventory helper (TDD)

**Files:** `_brain_helpers/inventory.py`, `tests/test_inventory.py`

- [ ] `Inventory` dataclass: `entries: List[InventoryEntry]` where each entry has `slug`, `title`, `source_paths`, `tentative_summary`
- [ ] `write_inventory(vault, inventory)` saves to `<vault>/.inventory.yaml` (gitignored within vault, used as scratch)
- [ ] `read_inventory(vault)` parses it back; allows user edits between Claude write and Claude read
- [ ] **Commit:** `feat(brain): add inventory persistence helper`

### Task J2: Wire inventory gate into first-run

**Files:** `.claude/skills/refresh-brain/SKILL.md` (modify)

- [ ] Between graphify run and concept-writing, Claude generates `Inventory` from graphify communities + sample source files
- [ ] Save `inventory.yaml` to vault dir
- [ ] **STOP POINT:** print "I propose these N concepts. Edit `<vault>/.inventory.yaml` then say 'go'. Or 'auto' to skip review."
- [ ] On user 'go': read back inventory, proceed to write notes from approved entries
- [ ] On 'auto': proceed without changes (matches v0 behavior — useful escape hatch)
- [ ] **Commit:** `feat(brain): add inventory stop point to first-run`

---

## Phase K: Business notes layer

**Goal:** Generate `type: business` notes that describe WHY code exists (use cases, problems solved). Cross-link to code concepts via `business_refs` ↔ `solves_for`.

### Task K1: Business note generation (extend refresh-brain)

**Files:** `.claude/skills/refresh-brain/SKILL.md` (modify)

- [ ] After all `type: code` concepts are written, Claude proposes 5–10 business case slugs by reading code concepts and inferring "what user-facing problem does this solve"
- [ ] **STOP POINT:** user reviews proposed business inventory (reuses inventory helper from Phase J)
- [ ] Claude writes `type: business` notes with frontmatter:
  - `solves_for: [[code-concept-1]], [[code-concept-2]]`
  - body: 150–300 words, plain-language, user-perspective ("Users uploading multilingual docs need...")
- [ ] After business notes written, Claude updates `business_refs` field on referenced code-concept notes (parent-child link both ways)
- [ ] **Commit:** `feat(brain): add type:business note generation`

### Task K2: Update `_INDEX.md` writer for business notes

**Files:** `_brain_helpers/index_writer.py` (modify), `tests/test_index_writer.py` (extend)

- [ ] Distinguish `type: code` vs `type: business` in concepts list
- [ ] Add separate "Business cases" section to INDEX
- [ ] Update vault-stats line to show real business count (no longer hardcoded "0")
- [ ] **Commit:** `feat(brain): index business notes separately`

### Task K3: Business note refresh on incremental

**Files:** `.claude/skills/refresh-brain/SKILL.md` (modify)

- [ ] Incremental mode: after refreshing stale code-concept notes, find business notes whose `solves_for` references any refreshed code-concept → flag them as stale-by-association
- [ ] Add to refresh-candidate list with reason "linked code-concept changed"
- [ ] **Commit:** `feat(brain): cascade staleness from code to business notes`

---

## Phase L: `/load-brain` Scenarios B and C

### Task L1: Scenario B — focused load

**Files:** `.claude/skills/load-brain/SKILL.md` (modify)

- [ ] If args present (`/load-brain manticore`): treat first arg as keyword
- [ ] Search `_INDEX.md` text + each note's frontmatter `tags` and `slug` for keyword matches (case-insensitive substring)
- [ ] Rank: exact slug match > tag match > title match > body summary match
- [ ] Top 3 matches: Read tool inject all three into context (not just INDEX)
- [ ] Print: "Loaded for '<keyword>': [[match1]], [[match2]], [[match3]]"
- [ ] If no matches: "No notes match '<keyword>'. Showing INDEX only." → fall back to Scenario A
- [ ] **Commit:** `feat(brain): add /load-brain Scenario B (focused load)`

### Task L2: Scenario C — status

**Files:** `.claude/skills/load-brain/SKILL.md` (modify)

- [ ] If `--status` flag: do NOT inject context. Print only:
  - `last_refresh` time and commit SHA
  - Total note counts
  - Stale concept notes (use stale_detection helper)
  - Diff: HEAD vs last_refresh_commit (number of source files changed since refresh)
  - Recommendation: "Run /refresh-brain" if stale > 0
- [ ] **Commit:** `feat(brain): add /load-brain Scenario C (status)`

---

## Phase M: Code review trail

### Task M1: diff_report helper (TDD)

**Files:** `_brain_helpers/diff_report.py`, `tests/test_diff_report.py`

- [ ] `write_diff_report(vault, source_changes, vault_changes, mapping)` writes `.last-refresh-diff.md`
- [ ] Mapping format: `{ source_file: [vault_notes_that_reference_it] }`
- [ ] Output sections: "Source files changed", "Vault notes updated", "Source→Vault traceability"
- [ ] **Commit:** `feat(brain): add refresh diff report helper`

### Task M2: Wire into `/refresh-brain`

**Files:** `.claude/skills/refresh-brain/SKILL.md` (modify)

- [ ] After incremental refresh, build mapping from refreshed notes' `source_paths` back to `source_changes`
- [ ] Call `write_diff_report` → save to `<vault>/.last-refresh-diff.md`
- [ ] Print summary line referencing the file: "Diff report: <vault>/.last-refresh-diff.md"
- [ ] **Commit:** `feat(brain): emit .last-refresh-diff.md on each refresh`

---

## Phase N: Extract to standalone `project-brain` repo

**Goal:** Move skills + helpers to a standalone repo so the system is reusable across projects.

### Task N1: Initialize new repo

- [ ] `mkdir ~/dev/project-brain && cd ~/dev/project-brain`
- [ ] `git init`
- [ ] Create README.md (copy + adapt `docs/project-brain-instruction.md`)
- [ ] Create LICENSE (MIT)
- [ ] Create `.gitignore` (Python defaults)
- [ ] **Commit:** `chore: initial repo`

### Task N2: Move helpers and skills

- [ ] Copy `private-gpt-fork/.claude/skills/_brain_helpers/` → `~/dev/project-brain/helpers/`
- [ ] Copy `.claude/skills/{init-brain,refresh-brain,load-brain}/` → `~/dev/project-brain/skills/`
- [ ] Update bash in SKILL.md files: change `HELPERS_VENV=.claude/skills/_brain_helpers/.venv/bin/python` to `HELPERS_VENV=$HOME/dev/project-brain/helpers/.venv/bin/python`
- [ ] Update sys.path inserts: change `'.claude/skills/_brain_helpers'` to `os.path.expanduser('~/dev/project-brain/helpers')`
- [ ] Set up venv in new location: `cd ~/dev/project-brain/helpers && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`
- [ ] Run tests: `.venv/bin/pytest -v` — all pass
- [ ] **Commit:** `feat: extract project-brain into standalone repo`

### Task N3: Symlink install in user-level skills

- [ ] `ln -s ~/dev/project-brain/skills/init-brain ~/.claude/skills/init-brain`
- [ ] `ln -s ~/dev/project-brain/skills/refresh-brain ~/.claude/skills/refresh-brain`
- [ ] `ln -s ~/dev/project-brain/skills/load-brain ~/.claude/skills/load-brain`
- [ ] Verify Claude Code recognizes them: list available skills

### Task N4: Remove from `private-gpt-fork`

- [ ] `rm -rf .claude/skills/{init-brain,refresh-brain,load-brain,_brain_helpers}`
- [ ] Update `.gitignore` — remove the brain-helpers entries (no longer in repo)
- [ ] Verify `.brain-config.yaml` is the ONLY brain-related file in this repo
- [ ] Re-run `/refresh-brain` (now using user-level symlinks): produces same vault as before extraction
- [ ] Re-run `/load-brain`: works
- [ ] **Commit:** `chore(brain): remove skills from this repo (now installed at user level)`

### Task N5: Push standalone repo to GitHub

- [ ] Create empty GitHub repo `project-brain`
- [ ] `cd ~/dev/project-brain && git remote add origin git@github.com:<user>/project-brain.git && git push -u origin main`
- [ ] Update README install instructions to use `git clone https://github.com/<user>/project-brain`

### Task N6: Test on a second project

- [ ] Pick any other project (or create a small test repo)
- [ ] `cd <other-project>`
- [ ] Run `/init-brain` → creates `.brain-config.yaml`
- [ ] Run `/refresh-brain` → creates vault
- [ ] Run `/load-brain` → loads INDEX
- [ ] If all three work without changes, system is portable
- [ ] If issues found, file them as v1.1 follow-up tasks

---

## Verification checklist (end of v1)

- [ ] `/init-brain` works on a fresh repo without any pre-existing config
- [ ] `/refresh-brain` first-run includes inventory stop point with edit option
- [ ] `/refresh-brain` second-run is incremental — only stale notes refreshed
- [ ] `last_source_hash` correctly identifies stale notes
- [ ] Business notes generate with `solves_for` ↔ `business_refs` cross-links
- [ ] `/load-brain manticore` injects 3 most relevant notes
- [ ] `/load-brain --status` reports staleness without context injection
- [ ] `.last-refresh-diff.md` written on each refresh with source-vault mapping
- [ ] Skills moved to standalone repo work via `~/.claude/skills/` symlinks
- [ ] Same skills work on a second, unrelated project (proves portability)
- [ ] All v0 tests still pass after extraction
- [ ] Total test count: ~50+ (adds ~25 new tests on top of v0's 23)

---

## Estimated effort

- Phase H (init-brain): ~2h
- Phase I (incremental + stale): ~3h
- Phase J (inventory gate): ~1.5h
- Phase K (business notes): ~2.5h
- Phase L (load-brain B/C): ~1.5h
- Phase M (diff report): ~1h
- Phase N (extraction + portability test): ~2h

**Total: ~13–14h** of focused dev time. Half-week if treated as a focus item, longer if interleaved with other work.

---

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| Inventory stop point feels heavy in practice (Claude proposes 20 items, user clicks through each) | Inventory is YAML — user can edit en masse, not click-by-click. `auto` escape hatch always available. |
| `last_source_hash` mismatch on legitimate non-changes (formatting commits, whitespace) | Use git's `--diff-filter=M` and ignore whitespace-only diffs (`-w` flag) |
| Business notes are vague / generic ("this serves users") | Provide examples in the SKILL.md prompt; require at least one concrete user persona/scenario per note |
| Extraction breaks paths in unforeseen ways | Phase N4 explicitly re-tests both refresh and load post-extraction; rollback is `mv` back |
| Second-project test reveals language-specific assumptions | Phase N6 deliberately scopes failures as v1.1 — don't try to make the system universal in v1 |
| Helpers package duplication (sys.path inserts in SKILL.md vs pip install) | Standardize on pip install -e in the helpers repo; remove sys.path hacks during extraction |
