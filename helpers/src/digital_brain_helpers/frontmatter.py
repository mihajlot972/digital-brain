"""Read and write YAML frontmatter in markdown files. Tolerant to malformed input."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Tuple
import yaml


FRONTMATTER_DELIM = "---"


def split_document(path: Path) -> Tuple[Dict[str, Any], str]:
    """Return (frontmatter_dict, body_str). Empty dict if no/malformed frontmatter."""
    if not path.exists():
        return {}, ""
    text = path.read_text()
    if not text.strip():
        return {}, ""

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip() != FRONTMATTER_DELIM:
        return {}, text

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == FRONTMATTER_DELIM:
            end_idx = i
            break
    if end_idx is None:
        return {}, text

    fm_block = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1:])
    body = body.lstrip("\n")

    try:
        fm = yaml.safe_load(fm_block) or {}
    except yaml.YAMLError:
        return {}, body
    if not isinstance(fm, dict):
        return {}, body
    return fm, body


def read_frontmatter(path: Path) -> Dict[str, Any]:
    fm, _ = split_document(path)
    return fm


def write_frontmatter(path: Path, frontmatter: Dict[str, Any], body: str) -> None:
    """Write `body` with `frontmatter` block prepended. Overwrites file."""
    fm_yaml = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    out = f"{FRONTMATTER_DELIM}\n{fm_yaml}{FRONTMATTER_DELIM}\n\n{body}"
    if not out.endswith("\n"):
        out += "\n"
    path.write_text(out)


def update_frontmatter(path: Path, updates: Dict[str, Any]) -> None:
    """Merge `updates` into existing frontmatter; preserve body."""
    fm, body = split_document(path)
    fm.update(updates)
    write_frontmatter(path, fm, body)
