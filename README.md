# digital-brain

A gitignored Obsidian vault that gives Claude Code a "second brain" for any project. Claude reads concise concept notes + an auto-generated code graph instead of grep-ing through source.

**Status: v0.1.0 (2026-05-23).** Standalone repo. 57 unit tests, 82% coverage.

---

## How it helps

**The problem.** Every new Claude session starts blind. To answer "where does retrieval happen?" or "what calls this class?", Claude reads dozens of source files. Big tokens, slow start, easy to miss context, often answers from stale assumptions.

**The fix.** A small vault next to your project, built once, refreshed on every commit. It contains:

- One short note per class/function (auto, from AST)
- Cluster notes grouping related code (auto, via graph clustering)
- 150-300 word concept summaries of subsystems (you or Claude write these)
- A 2k-token INDEX that maps it all together

When you open `claude` in the project, the INDEX is loaded into Claude's context automatically. Claude orients in seconds instead of minutes. Token usage on orientation questions drops **8-15×** because Claude reads concept summaries instead of raw source. Concept notes you write survive every refresh, so design decisions persist across sessions.

**Concrete payoff:**

| Without digital-brain | With digital-brain |
|----------------------|--------------------|
| "Where is auth?" → Claude greps 40 files, reads 12, answers | Claude reads INDEX + 1 concept note, answers in 1 turn |
| Pasting "remember that we decided X" every session | Concept note `auth-decisions.md` always loaded |
| Stale assumptions after a refactor | Post-commit hook rebuilds extracted layer in ~3 sec |
| Manual vault management | Build prompted automatically; removed via one command |

---

## Install (one-time, global)

```bash
git clone <repo> ~/Projects/digital-brain
cd ~/Projects/digital-brain/helpers
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -v          # expect: 57 passed
cd ..
bash hooks/install.sh
```

What `install.sh` does:

- Symlinks `refresh-digital-brain` + `load-digital-brain` skills into `~/.claude/skills/`
- Symlinks `digital-brain` CLI into `~/.local/bin/`
- Patches `~/.claude/settings.json` with SessionStart + Stop hooks (preserves your other hooks — never clobbers)
- Writes `~/.digital-brain/install.json` so the CLI can find itself later
- Warns if `~/.local/bin` is missing from `$PATH` and tells you exactly what line to add

Idempotent — re-run any time after updating the source repo.

---

## Use

### Add the brain to a project (one-time, per project)

```bash
cd <your-project>

# 1. Config (commit this)
cat > .digital-brain-config.yaml <<'EOF'
source_paths:
  - src/                    # adjust to your source dir(s)
vault_dir: digital-brain/
EOF

# 2. Gitignore the vault
echo "digital-brain/" >> .gitignore

# 3. Link the post-commit hook
INSTALL_ROOT="$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.digital-brain/install.json')))['install_root'])")"
ln -sf "$INSTALL_ROOT/hooks/post-commit" .git/hooks/post-commit
```

Multi-source example:

```yaml
source_paths:
  - packages/api/src/
  - packages/worker/src/
vault_dir: digital-brain/
```

### First use

Open Claude in the project:

```bash
cd <your-project> && claude
```

Claude greets you with:

> "No digital-brain vault detected for this project. Run `/refresh-digital-brain` to build it (~1-3 min)."

Run `/refresh-digital-brain`. It will:

1. Extract every class/function via AST
2. Cluster them by import graph
3. Write one Obsidian note per node + per cluster
4. Ask Claude to write 10-20 concept notes for the main subsystems
5. Register the vault with Obsidian (one click to open in the Obsidian app)
6. Load the INDEX into the current session so you can use it immediately

### Every session after that

Just `claude`. The SessionStart hook auto-loads the INDEX (~2k tokens). Claude is oriented before you type anything.

### Reference a node mid-chat

Type `[[NodeName]]` in your message. The skill resolves it to the vault file and Claude reads it before answering.

### When Claude cites a node in chat

You get clickable links in both directions:

```
[[HybridRetriever]] ([source](src/retrieval.py#L42), [vault](obsidian://open?vault=...))
```

Click `source` → opens in your IDE. Click `vault` → opens in Obsidian.

### On commit

If the commit touched `source_paths`, the post-commit hook rebuilds the extracted layer in ~3 sec (no LLM, free). Concept notes are preserved. If you want fresh concept notes after a big refactor, run `/refresh-digital-brain` manually.

---

## Daily workflow

| When | What you do | What happens | Cost |
|------|-------------|--------------|------|
| Open `claude` in a brain project, vault exists | Nothing | INDEX auto-loaded by SessionStart hook | ~2k tok |
| Open `claude`, vault missing | Run `/refresh-digital-brain` | Full build + auto-register + INDEX load | ~1-3 min |
| Ask about a node mid-chat | Type `[[NodeName]]` | Skill reads the vault file before answering | 1 file read |
| `git commit` touching source | Nothing | Post-commit fires `auto_refresh.py` in background | ~3 sec, free |
| Big refactor done | Run `/refresh-digital-brain` | Rebuilds extracted layer + Claude rewrites concept notes | ~1-3 min |
| Stop hook warns "vault behind" | Run `/refresh-digital-brain` | Same | ~1-3 min |
| Mid-session INDEX reload | Run `/load-digital-brain` | Re-injects INDEX | ~2k tok |

---

## What's inside the vault

Four layers, each with a clear job:

| Layer | Source | Editable? | Survives refresh? |
|-------|--------|-----------|-------------------|
| Extracted (`type: code`) | graphify AST | NO | NO — copied to `.history/` |
| Community (`_COMMUNITY_N.md`) | Leiden clustering | NO | NO |
| Concept (`layer: concept`) | You or Claude | YES — write freely | YES |
| Index (`_INDEX.md`) | Auto-generated | NO | NO |

Concept notes are where the value lives. Write them when you make a decision worth remembering ("we chose BM25 over vector for sparse queries because…") and they stay loaded forever.

If you edit an extracted note by accident and a refresh wipes it, look in `<vault>/.history/<timestamp>/`.

---

## What fires automatically

**SessionStart hook** — walks up the directory tree for `.digital-brain-config.yaml`. If found and the vault exists, injects `_INDEX.md` into Claude's session context. If config exists but vault is missing, prompts to build. Silent for non-brain projects. Zero overhead in unrelated dirs.

**Post-commit hook** — symlinked into `.git/hooks/post-commit`. Only runs if the commit touched paths under `source_paths`. Runs `auto_refresh.py` in the background — AST extract → filter (drops `__init__`, dunders, docstring noise, single-node "communities") → re-cluster → Obsidian export → INDEX rewrite. Concept notes preserved to `.history/`.

**Stop hook** — runs after each Claude turn. Warns when the vault is ≥5 commits behind HEAD, has a refresh commit no longer in git history (rebased away), or is ≥7 days old. Tunable: `DIGITAL_BRAIN_STALE_COMMITS=N DIGITAL_BRAIN_STALE_DAYS=N`.

---

## Removal

**Per-project:**

```bash
cd <your-project>
digital-brain remove
```

Confirms, then:
1. Copies concept notes to `~/.digital-brain-graveyard/<project>-<timestamp>/` (so they aren't lost)
2. Deletes the vault dir
3. Deletes `.digital-brain-config.yaml`
4. Removes `.git/hooks/post-commit` (only if it points at our hook — foreign hooks are left alone)
5. Unregisters the vault from Obsidian

Use `--yes` to skip confirmation.

**Global:**

```bash
digital-brain uninstall
```

Removes the global symlinks + scrubs digital-brain entries from `~/.claude/settings.json` (preserves your other hooks) + removes the install metadata. Per-project vaults are NOT touched — run `digital-brain remove` in each project first if you want them gone.

The source repo at `~/Projects/digital-brain` is left intact. `rm -rf` it manually if you want it gone too.

---

## Repo layout

```
digital-brain/
├── README.md
├── skills/
│   ├── refresh-digital-brain/SKILL.md
│   └── load-digital-brain/SKILL.md
├── helpers/
│   ├── pyproject.toml                                   # name = "digital-brain-helpers"
│   ├── src/digital_brain_helpers/
│   │   ├── config.py
│   │   ├── frontmatter.py
│   │   ├── index_writer.py
│   │   ├── obsidian_register.py                         # auto-registers vault in Obsidian
│   │   ├── session_start.py                             # load-vs-prompt logic
│   │   ├── install_helpers.py                           # settings.json + install.json writers
│   │   └── cli.py                                       # remove + uninstall subcommands
│   └── tests/                                           # 57 unit tests, 82% coverage
└── hooks/
    ├── install.sh                                       # one-time global installer
    ├── post-commit                                      # git hook → auto_refresh.py
    ├── auto_refresh.py                                  # AST-only, ~3 sec, no LLM
    ├── stale_check.sh                                   # Stop hook
    └── session_start.sh                                 # SessionStart hook
```

After install (set once by `install.sh`):

```
~/.claude/skills/refresh-digital-brain → <install_root>/skills/refresh-digital-brain
~/.claude/skills/load-digital-brain    → <install_root>/skills/load-digital-brain
~/.claude/settings.json                # SessionStart + Stop hooks merged in
~/.local/bin/digital-brain             → helpers venv console script
~/.digital-brain/install.json          # install metadata for CLI discovery
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/refresh-digital-brain` or `/load-digital-brain` not in skill list | Re-run `bash hooks/install.sh` |
| `ModuleNotFoundError: digital_brain_helpers` | `cd <install_root>/helpers && rm -rf .venv && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"` |
| `.digital-brain-config.yaml not found` | Write one at repo root (see Use → Add the brain to a project) |
| Post-commit didn't fire | `ls .git/hooks/post-commit` should be a symlink; re-do step 3 of per-project setup |
| SessionStart shows "Build brain" every session | Vault or `_INDEX.md` missing; run `/refresh-digital-brain` |
| Stop hook fires every turn | Raise thresholds: `export DIGITAL_BRAIN_STALE_COMMITS=20 DIGITAL_BRAIN_STALE_DAYS=30` |
| `digital-brain: command not found` | `~/.local/bin` not on `$PATH`; add `export PATH="$HOME/.local/bin:$PATH"` to `~/.zshrc` or `~/.bashrc` |
| Vault has 0 concept notes after refresh | First run writes extracted layer only; concept notes need Claude (interactive `/refresh-digital-brain`) |
| `cli.py` can't find install root | Re-run `bash hooks/install.sh` to rewrite `~/.digital-brain/install.json` |
| Moved the repo dir? | Re-run `bash hooks/install.sh` from the new location to update symlinks + install.json |
| Obsidian doesn't show the new vault | Quit + reopen Obsidian (it reads `obsidian.json` at startup) |

---

## v0 limits / v1 roadmap

See `docs/plan-v1-full.md` for the upgrade path.

- No `/init-digital-brain` — config written by hand.
- Concept-note refresh is full-rebuild (no incremental diff).
- No `type: business` notes, no inventory stop-point.
- `/load-digital-brain` loads full INDEX only (no keyword-focused subset).
- Community labels are `Community 0/1/2…` — no LLM-driven names.
- No `.last-refresh-diff.md` for code-review flow.
- AST-only extraction — graphify semantic subagent pass deferred.
- No lockfile for concurrent refresh + uninstall.
- Windows: `obsidian_register` no-ops with a warning; macOS + Linux supported.

---

## License

(TBD — add a LICENSE file.)
