#!/usr/bin/env python3
"""Auto-refresh extracted layer + INDEX without LLM.

Called by git post-commit hook (or manually). Runs the AST-only digital-brain
pipeline + regenerates _INDEX.md. Skips Claude concept-writing — that
stays a manual /refresh-brain step because it costs LLM tokens.

Safe to call when nothing relevant changed: exits with code 0 silently.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# digital-brain root = parent of hooks/ (this script's directory)
INSTALL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(INSTALL_ROOT / "helpers" / "src"))


def _host_repo_root() -> Path:
    """Host repo = wherever git is currently anchored. post-commit cd's to host root."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


REPO_ROOT = _host_repo_root()

MIN_COMMUNITY_SIZE = 5


def main() -> int:
    try:
        from digital_brain_helpers.config import load_config, CONFIG_FILENAME
        from digital_brain_helpers.index_writer import write_index
    except ImportError as e:
        print(f"[digital-brain] helpers not importable: {e}", file=sys.stderr)
        return 0

    cfg_path = REPO_ROOT / CONFIG_FILENAME
    if not cfg_path.exists():
        return 0  # not initialized; nothing to do

    try:
        from graphify.extract import collect_files, extract
        from graphify.build import build as build_graph
        from graphify.cluster import cluster, score_all
        from graphify.export import to_obsidian, to_canvas, to_json
    except ImportError:
        print("[digital-brain] graphify not installed; skipping auto-refresh", file=sys.stderr)
        return 0

    cfg = load_config(REPO_ROOT)
    vault_dir = cfg.resolved_vault_dir()
    source_paths_resolved = cfg.resolved_source_paths()

    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / ".history").mkdir(exist_ok=True)
    (vault_dir / "graphify-out").mkdir(exist_ok=True)

    # Stage 1: AST extract
    all_files: list[Path] = []
    for src in source_paths_resolved:
        if src.is_dir():
            all_files.extend(collect_files(src))
        elif src.is_file():
            all_files.append(src)
    if not all_files:
        return 0

    ast = extract(all_files)

    # Stage 2: filter noisy nodes
    def is_useful(n: dict) -> bool:
        if n.get("file_type") == "rationale":
            return False
        label = (n.get("label") or "").strip()
        if not label or len(label) > 80:
            return False
        if label.startswith(".") and label.endswith(")") and "_" in label:
            return False
        if label.startswith("__") and label.endswith("__"):
            return False
        if label.startswith("__") and label.endswith(")"):
            return False
        if (
            label.startswith("_")
            and label.endswith(")")
            and not label.startswith("__")
        ):
            return False
        return True

    kept_nodes = [n for n in ast["nodes"] if is_useful(n)]
    kept_ids = {n["id"] for n in kept_nodes}
    kept_edges = [
        e for e in ast["edges"] if e["source"] in kept_ids and e["target"] in kept_ids
    ]
    filtered = dict(ast)
    filtered["nodes"] = kept_nodes
    filtered["edges"] = kept_edges

    # Stage 3: build + cluster + drop tiny communities
    G = build_graph([filtered])
    communities = cluster(G)
    big = {
        cid: nodes
        for cid, nodes in communities.items()
        if len(nodes) >= MIN_COMMUNITY_SIZE
    }
    keep = set()
    for nodes in big.values():
        keep.update(nodes)
    H = G.subgraph(keep).copy()
    cohesion = score_all(H, big) if big else {}

    # Stage 4: clean stale extracted/community notes before re-export
    # (preserve concept layer + _INDEX backup)
    import shutil
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    history = vault_dir / ".history" / timestamp
    history.mkdir(parents=True, exist_ok=True)

    for md in vault_dir.glob("*.md"):
        # back up + delete extracted/community; preserve concept layer
        text = md.read_text() if md.exists() else ""
        is_concept = "\nlayer: concept\n" in text or text.startswith("---\nlayer: concept\n")
        is_index = md.name == "_INDEX.md"
        if is_concept or is_index:
            shutil.copy2(md, history / md.name)
            continue
        shutil.move(str(md), str(history / md.name))

    # Stage 5: export
    to_obsidian(H, big, str(vault_dir), community_labels=None, cohesion=cohesion)
    to_canvas(H, big, str(vault_dir / "graph.canvas"), community_labels=None)
    # graphify.to_json refuses to overwrite if new graph is smaller than existing
    # (safety against accidental data loss). Filtering legitimately shrinks the
    # graph each refresh, so wipe the stale file first.
    graph_json = vault_dir / "graphify-out" / "graph.json"
    if graph_json.exists():
        graph_json.unlink()
    to_json(H, big, str(graph_json))

    # Stage 6: regenerate INDEX
    sha_proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    commit_sha = sha_proc.stdout.strip() or "no-commit"
    write_index(
        vault=vault_dir,
        source_paths=cfg.source_paths,
        commit_sha=commit_sha,
    )

    print(
        f"[digital-brain] auto-refresh: {H.number_of_nodes()} nodes, "
        f"{len(big)} communities, commit {commit_sha}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
