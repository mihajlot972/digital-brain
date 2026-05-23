---
name: refresh-digital-brain
description: Build or rebuild the digital-brain Obsidian vault from configured source_paths. v0 = full rebuild only, code-concept notes only.
---

# /refresh-digital-brain

Build the `<vault_dir>` Obsidian vault from `source_paths` defined in `.digital-brain-config.yaml`. v0 MVP: full rebuild every time, code-concept notes only, no inventory gate.

## Usage

```
/refresh-digital-brain
```

No arguments. Reads `.digital-brain-config.yaml` from the current working directory (must be repo root).

## What you (Claude) do when invoked

### Step 0 — Verify prerequisites

Run:
```bash
INSTALL_ROOT="$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.digital-brain/install.json')))['install_root'])")"
HELPERS_VENV="$INSTALL_ROOT/helpers/.venv/bin/python"
test -f .digital-brain-config.yaml || { echo "ERROR: .digital-brain-config.yaml not found. Create it manually for v0."; exit 1; }
test -x "$HELPERS_VENV" || { echo "ERROR: helpers venv missing. Run: cd $INSTALL_ROOT/helpers && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"; exit 1; }
"$HELPERS_VENV" -c "import yaml, digital_brain_helpers.config, digital_brain_helpers.frontmatter, digital_brain_helpers.index_writer" || { echo "ERROR: helper imports failed"; exit 1; }
"$HELPERS_VENV" -c "import graphify" 2>/dev/null || { echo "ERROR: graphify Python module not found. Run: pip install graphifyy"; exit 1; }
```

Note: `graphify` is a Python library (we call its modules directly), not a CLI command for the build pipeline. The `graphify` binary on PATH only handles install/query/hooks; the actual build uses `graphify.extract`, `graphify.build`, `graphify.cluster`, `graphify.export`.

If any check fails, stop with the error message and ask user to fix.

### Step 1 — Load config

```bash
"$HELPERS_VENV" -c "
import json
import sys
sys.path.insert(0, '$INSTALL_ROOT/helpers/src')
from pathlib import Path
from digital_brain_helpers.config import load_config
cfg = load_config(Path('.').resolve())
print(json.dumps({
    'source_paths_resolved': [str(p) for p in cfg.resolved_source_paths()],
    'vault_dir': str(cfg.resolved_vault_dir()),
    'source_paths_raw': cfg.source_paths,
}))
" > /tmp/brain_cfg.json
```

Read `/tmp/brain_cfg.json` to know `source_paths` and `vault_dir` for next steps.

### Step 2 — Prepare vault directory

```bash
VAULT_DIR=$(jq -r '.vault_dir' /tmp/brain_cfg.json)
mkdir -p "$VAULT_DIR/.history"
```

If `$VAULT_DIR/_INDEX.md` already exists, back up the entire vault content first:
```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$VAULT_DIR/.history/$TIMESTAMP"
find "$VAULT_DIR" -maxdepth 1 -name "*.md" ! -name "_INDEX.md" -exec cp {} "$VAULT_DIR/.history/$TIMESTAMP/" \;
cp "$VAULT_DIR/_INDEX.md" "$VAULT_DIR/.history/$TIMESTAMP/" 2>/dev/null || true
```

This is strategy Z: if the user manually edited any note, the previous version is preserved in `.history/<timestamp>/`.

### Step 3 — Run graphify pipeline (AST-only for v0, with filtering)

For v0 we use AST extraction only (deterministic, fast, free — no LLM subagents). This produces the extracted-node layer: per-class/function notes, community clustering, and the Obsidian canvas. Semantic extraction (which infers richer cross-document relationships via Claude subagents) is deferred to v1.

We apply two filters BEFORE export to keep the vault usable:

1. **Drop noisy AST nodes**: docstring/comment "rationale" pseudo-nodes, dunder-only labels (`__init__`, `__exit__`, etc.), auto-disambiguated variants like `.__init__()_42`, and labels longer than 80 chars (usually mis-extracted docstrings).
2. **Drop tiny communities** (< 5 members): Leiden clustering produces lots of single-node "communities" that are pure noise.

```bash
mkdir -p "$VAULT_DIR/graphify-out"
python3 - <<PYEOF
import json
from pathlib import Path
from graphify.extract import collect_files, extract
from graphify.build import build as build_graph
from graphify.cluster import cluster, score_all
from graphify.export import to_obsidian, to_canvas, to_json

MIN_COMMUNITY_SIZE = 5

cfg = json.loads(Path('/tmp/brain_cfg.json').read_text())
vault_dir = Path(cfg['vault_dir'])
source_paths_resolved = [Path(p) for p in cfg['source_paths_resolved']]

# --- Stage 1: AST extraction ---
all_files = []
for src in source_paths_resolved:
    if src.is_dir():
        all_files.extend(collect_files(src))
    elif src.is_file():
        all_files.append(src)
print(f"Collected {len(all_files)} files for AST extraction")

ast = extract(all_files)
print(f"Raw AST: {len(ast['nodes'])} nodes, {len(ast['edges'])} edges")

# --- Stage 2: Pre-build node filtering ---
def is_useful_node(n):
    if n.get('file_type') == 'rationale':
        return False
    label = (n.get('label') or '').strip()
    if not label or len(label) > 80:
        return False
    if label.startswith('.') and label.endswith(')') and '_' in label:
        return False
    if label.startswith('__') and label.endswith('__'):
        return False
    return True

kept_nodes = [n for n in ast['nodes'] if is_useful_node(n)]
kept_ids = {n['id'] for n in kept_nodes}
kept_edges = [e for e in ast['edges'] if e['source'] in kept_ids and e['target'] in kept_ids]
print(f"Filtered AST: {len(kept_nodes)} nodes, {len(kept_edges)} edges (dropped {len(ast['nodes']) - len(kept_nodes)} noisy nodes)")

filtered_ast = dict(ast)
filtered_ast['nodes'] = kept_nodes
filtered_ast['edges'] = kept_edges

# --- Stage 3: Build + cluster ---
# graphify.cluster() returns dict[community_id, list[node_ids]] — NOT dict[node_id, community_id].
G = build_graph([filtered_ast])
communities = cluster(G)
print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities")

# --- Stage 4: Drop tiny communities ---
big_communities = {cid: nodes for cid, nodes in communities.items() if len(nodes) >= MIN_COMMUNITY_SIZE}
print(f"Communities >= {MIN_COMMUNITY_SIZE} members: {len(big_communities)} (dropped {len(communities) - len(big_communities)} micro-clusters)")

keep_node_ids = set()
for nodes in big_communities.values():
    keep_node_ids.update(nodes)
H = G.subgraph(keep_node_ids).copy()
print(f"After community filter: {H.number_of_nodes()} nodes, {H.number_of_edges()} edges")

# --- Stage 5: Cohesion + export ---
cohesion = score_all(H, big_communities)

n = to_obsidian(H, big_communities, str(vault_dir), community_labels=None, cohesion=cohesion)
print(f"Wrote {n} Obsidian notes")

to_canvas(H, big_communities, str(vault_dir / 'graph.canvas'), community_labels=None)
to_json(H, big_communities, str(vault_dir / 'graphify-out' / 'graph.json'))
print(f"Wrote graph.canvas and graphify-out/graph.json")
PYEOF
```

After this, `$VAULT_DIR/` contains:
- One `<NodeName>.md` per kept AST node (clean class/function names)
- `_COMMUNITY_*.md` overview notes for communities with >= 5 members (with cohesion score)
- `graph.canvas` for Obsidian graph view
- `graphify-out/graph.json` for programmatic queries

If the Python block fails (import error, AST extraction error, etc.), stop and report. Common failures: `pip install graphifyy` not done, or graphify version mismatch — check `python3 -c "import graphify; print(graphify.__file__)"`.

**Note on `cluster()` return type**: graphify's clustering returns `dict[community_id, list[node_ids]]`. Older versions or other docs may suggest the inverse mapping — if you see `TypeError: unhashable type: 'list'` while iterating, that's the symptom.

**Note on `to_json()` signature**: `to_json(G, communities, output_path)` — only 3 positional arguments, no kwargs like `community_labels` or `cohesion`.

### Step 4 — Write code-concept notes

You will now write ~10–20 code-concept notes that synthesize across the extracted nodes.

**For v0 (no stop point):** read graphify's output to ground yourself, then write notes directly. No inventory review with the user — that's a v1 feature.

**Process:**

1. Check what graphify produced:
   ```bash
   ls "$VAULT_DIR/graphify-out/"
   ```
   If `GRAPH_REPORT.md` exists, read it for the plain-language summary. If not, fall back to reading `graphify-out/graph.json` (top-level keys: `nodes`, `edges`, `communities`) and `_COMMUNITY_*.md` files for grounding.
2. Read each `$VAULT_DIR/_COMMUNITY_*.md` to learn the labels and member nodes
3. For each community, decide on 2–4 concept slugs that capture distinct ideas (e.g., `manticore-retrieval`, `hybrid-rerank`, `chunking-pipeline`)
4. For each chosen concept, identify which source files (from `source_paths`) implement it. Read them with the Read tool — only the parts you need (don't dump whole files into context)
5. Write the concept note to `$VAULT_DIR/<slug>.md` using the Write tool, with this structure:

```markdown
---
layer: concept
type: code
slug: <kebab-case-slug>
source_paths:
  - <relative/path/in/source>
  - <relative/path/in/source>
extracted_refs:
  - "[[<NodeName1>]]"
  - "[[<NodeName2>]]"
related_concepts:
  - "[[<other-slug>]]"
tags: [<tag1>, <tag2>]
last_written: <ISO timestamp now>
---

# <Title>

(150–300 words. Plain language. Cover: what this is, how it works at a high level, what code drives it, key interactions with other concepts. Avoid jargon dump. Avoid line-by-line code paraphrase — explain the IDEA.)
```

**Note count target:** 10–20 concept notes for the whole codebase. If you find yourself writing more than 25, you're being too granular — merge similar slugs.

**Quality bar:** if a future Claude session reads only this concept note and doesn't open the source code, can it make sensible recommendations about the area? If not, the note is too vague — add the missing detail.

### Step 5 — Write _INDEX.md

```bash
COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "no-commit")
SOURCE_RAW=$(jq -r '.source_paths_raw | join(",")' /tmp/brain_cfg.json)
"$HELPERS_VENV" -c "
import sys
sys.path.insert(0, '$INSTALL_ROOT/helpers/src')
from pathlib import Path
from digital_brain_helpers.index_writer import write_index
write_index(
    vault=Path('$VAULT_DIR'),
    source_paths='$SOURCE_RAW'.split(','),
    commit_sha='$COMMIT_SHA',
)
print('INDEX written')
"
```

### Step 6 — Print summary

Show the user:
```
Vault built: <vault_dir>/
- N extracted nodes (graphify)
- M code-concept notes (Claude)
- K communities (graphify)
- Last refresh: <timestamp> (commit <sha>)

Open <vault_dir>/ in Obsidian (File → Open Vault → Browse → <vault_dir>) to explore.
Run /load-digital-brain in your next session to use this vault as Claude context.
```

### Step 7 — Cleanup

```bash
rm -f /tmp/brain_cfg.json
```

## Errors

If any step fails, stop and report the error verbatim. Do NOT try to recover by skipping steps — a partial vault is worse than no vault. The user can re-run `/refresh-digital-brain` after fixing the issue.

## Out of scope (v1+)

- Incremental refresh (always full rebuild in v0)
- Inventory stop point (Claude writes notes auto in v0)
- Business notes (`type: business`) — only `type: code`
- `last_source_hash` for stale detection
- `.last-refresh-diff.md` generation
