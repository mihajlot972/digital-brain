"""Claude Code SessionStart hook: auto-load INDEX or prompt to build."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Optional

from .config import CONFIG_FILENAME, load_config, ConfigNotFoundError, ConfigSchemaError

INDEX_FILENAME = "_INDEX.md"
ADDITIONAL_CONTEXT_LIMIT = 9500


def _find_config_root(start: Path) -> Optional[Path]:
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
