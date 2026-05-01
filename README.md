# private-brain

Gitignored Obsidian vault as Claude's "second brain" for any project. Cuts token usage 8-15× on orientation questions: Claude reads concept summaries + code graph instead of grep-ing source.

**Status: v0 MVP implemented (2026-05-01).** Lives inside `private-gpt-fork/` for now; will be extracted to standalone git repo once stable.

What works in v0:
- `/refresh-brain` — full rebuild (AST extract + filter + cluster + Obsidian export + Claude-written concept notes)
- `/load-brain` — Scenario A: load INDEX into session context
- Auto-refresh extracted layer on `git commit` (post-commit hook, no LLM)
- Stop hook reminds Claude when vault stale (≥5 commits behind or ≥7 days old)
- Per-project config: `.brain-config.yaml` (hand-written in v0)

Deferred to v1: `/init-brain` (auto-bootstrap), incremental refresh, business notes, focused-load `/load-brain <keyword>`, semantic LLM-driven node labeling.

---

## Layout

```
private-brain/                                            # this folder
├── README.md                                             # ← you are here
├── skills/{refresh-brain,load-brain}/SKILL.md
├── helpers/                                              # Python pkg (PyYAML, graphifyy)
│   ├── pyproject.toml
│   ├── {config,frontmatter,index_writer}.py
│   └── tests/                                            # 23 unit tests
├── hooks/
│   ├── post-commit                                       # git hook → auto_refresh.py
│   ├── auto_refresh.py                                   # AST-only, no LLM, ~3 sec
│   ├── stale_check.sh                                    # Stop hook → JSON when stale
│   └── install.sh                                        # one-shot installer
└── docs/{plan-v0-mvp,plan-v1-full}.md                    # design + plan history
```

In host repo (this `private-gpt-fork`):
```
.brain-config.yaml                                        # COMMIT — source_paths, vault_dir
.claude/skills/refresh-brain → ../../private-brain/skills/refresh-brain
.claude/skills/load-brain    → ../../private-brain/skills/load-brain
.claude/settings.local.json                               # has Stop hook → stale_check.sh
.git/hooks/post-commit       → ../../private-brain/hooks/post-commit  (after install.sh)
project-brain/                                            # GITIGNORED — generated vault
```

---

## Quickstart — fresh machine

```bash
# 1. graphify in helpers venv (auto-pulled from pyproject.toml dependency)
cd private-brain/helpers
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -v                  # expect: 23 passed

# 2. install git post-commit hook (from repo root)
cd ../..
bash private-brain/hooks/install.sh

# 3. verify Claude Code sees skills
ls .claude/skills/                   # should show refresh-brain, load-brain symlinks

# 4. (optional) Obsidian: https://obsidian.md/  — open project-brain/ as vault
```

**For a brand-new project (no `.brain-config.yaml` yet):**

Write at project root:
```yaml
# .brain-config.yaml
source_paths:
  - <main-source-folder>/   # e.g. private_gpt/, src/, lib/, packages/api/src/
vault_dir: project-brain/
```

Then in Claude session: `/refresh-brain` (first run takes ~1-3 min — graphify AST + Claude writes concept notes).

---

## Daily workflow

| When | Action | Cost |
|------|--------|------|
| New Claude session | `/load-brain` | ~2k tok (loads INDEX + working principle) |
| Focused question | normal chat after `/load-brain` | minus 25-40k tok vs raw source reading |
| `git commit` touching source_paths | nothing — post-commit hook fires | ~3 sec, no LLM |
| Big refactor done, want fresh concept notes | `/refresh-brain` interactively | ~1-3 min (Claude writes) |
| Stop hook warned "vault behind" | `/refresh-brain` | same |

### Auto-refresh — what fires automatically

**Post-commit hook** (`hooks/post-commit`):
- Runs only if commit touched `source_paths`. Skips silently otherwise.
- Background `auto_refresh.py`: graphify AST extract → filter (drops `__init__()_N`, `_private_helper()`, dunders, docstring nodes >80 chars) → cluster → drop communities <5 members → Obsidian export → INDEX rewrite.
- Concept notes preserved in `<vault>/.history/<timestamp>/` before extracted layer wipes.
- Updates `_INDEX.md` `last_refresh_commit` to current HEAD.
- Does NOT refresh concept notes (needs LLM — manual `/refresh-brain` only).

**Stop hook** (`hooks/stale_check.sh`):
- Runs after each Claude turn ends.
- Compares `_INDEX.md` `last_refresh_commit` vs HEAD.
- Stale if: commit rebased away, ≥5 commits behind, OR INDEX older than 7 days.
- When stale: emits JSON with `systemMessage` (UI) + `hookSpecificOutput.additionalContext` (Claude sees in next-turn context) → Claude suggests `/refresh-brain`.
- Silent when fresh.
- Tunable: `STALE_COMMITS=N STALE_DAYS=N` env vars.

---

## Notes you can / cannot edit

| Type | Marker in frontmatter | Editable? | Survives refresh? |
|------|----------------------|-----------|-------------------|
| Concept | `layer: concept` | YES — write `# Title` + 150-300 words | YES, preserved |
| Extracted (graphify) | `type: "code"`, no `layer` | NO — auto-regenerated | NO — wiped, copy in `.history/` |
| Community | filename `_COMMUNITY_<N>.md` | NO | NO |
| Index | `_INDEX.md` | NO (auto, but commit SHA only field that changes) | NO |
| Canvas | `graph.canvas` | NO | NO |

If you accidentally edit an extracted note and a refresh wipes it, recover from `<vault>/.history/<timestamp>/`.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/refresh-brain` or `/load-brain` not in skill list | Symlinks broken: `ls -la .claude/skills/`; recreate `ln -s ../../private-brain/skills/<X> .claude/skills/<X>` |
| `graphify Python module not found` | `private-brain/helpers/.venv/bin/pip install graphifyy` |
| `.brain-config.yaml not found` | Write one at repo root (see Quickstart) |
| post-commit hook didn't fire | `ls .git/hooks/post-commit` — should be symlink; re-run `install.sh` |
| Vault has 0 concept notes after refresh | First-run only writes extracted layer in v0; concept notes need interactive `/refresh-brain` (LLM) |
| Stop hook spams every turn | Bump thresholds: `export STALE_COMMITS=20 STALE_DAYS=30` |
| Tests fail / `import config` fails | venv path drift after move: `cd private-brain/helpers && rm -rf .venv && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"` |
| graphify says "refusing to overwrite graph.json (smaller)" | `auto_refresh.py` already handles by deleting before write — if you see it from manual run, `rm project-brain/graphify-out/graph.json` first |

---

## Per-project example — this repo

```yaml
# .brain-config.yaml at repo root
source_paths:
  - private_gpt/
vault_dir: project-brain/
```

Result after `/refresh-brain`:
- ~680-770 extracted node notes (clean class/function names like `BgeReranker.md`, `HybridRetriever.md`)
- ~18-31 community notes (largest auto-labeled by top members in INDEX, e.g. `Community 1 — e.g. BM25Source, BgeReranker, ContextEnrichmentPipeline` ≈ retrieval cluster)
- 5 hand-written concept notes (retrieval-pipeline, chunking-pipeline, ingestion-flow, chat-service, context-enrichment)
- `graph.canvas` for Obsidian graph view
- `graphify-out/graph.json` for "who calls X" queries

Other project shape:
```yaml
# Node monorepo example
source_paths:
  - packages/api/src/
  - packages/worker/src/
vault_dir: .brain/
```

---

## Extraction to standalone repo (when stable)

```bash
# 1. Move private-brain/ out of host repo
mv private-brain ~/dev/private-brain
cd ~/dev/private-brain
git init && git add . && git commit -m "extract from private-gpt-fork"

# 2. Push to GitHub
gh repo create private-brain --private
git push -u origin main

# 3. In each consuming project, replace local symlinks with user-level ones
ln -s ~/dev/private-brain/skills/refresh-brain ~/.claude/skills/refresh-brain
ln -s ~/dev/private-brain/skills/load-brain    ~/.claude/skills/load-brain

# 4. Per-project: install git hook
cd /path/to/other-project
ln -s ~/dev/private-brain/hooks/post-commit .git/hooks/post-commit
```

After extraction, host repos carry only `.brain-config.yaml` + (optionally) the Stop hook entry in `.claude/settings.local.json`. Updates propagate via `git -C ~/dev/private-brain pull`.

---

## v0 limitations (deferred to v1)

See `docs/plan-v1-full.md` for upgrade path.

- No `/init-brain` skill — config written by hand
- Concept-note refresh is full-rebuild (no incremental, no Claude diff pass)
- No `type: business` notes, no inventory stop-point
- `/load-brain` only Scenario A (no `/load-brain <keyword>`, no `--status`)
- Community labels are `Community 0/1/2…` — no LLM-driven naming (auto-derived from top 3 members in INDEX)
- No `.last-refresh-diff.md` for code-review flow
- AST-only extraction — graphify semantic subagent pass deferred (would give richer cross-document edges + better node labels)
