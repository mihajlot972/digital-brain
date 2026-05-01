"""Generate _INDEX.md from vault contents."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List
import re

from frontmatter import split_document


INDEX_FILENAME = "_INDEX.md"


@dataclass
class NoteEntry:
    path: Path
    slug: str
    title: str
    summary: str = ""


@dataclass
class CommunityEntry:
    path: Path
    label: str
    node_count: int = 0
    top_members: List[str] = field(default_factory=list)


@dataclass
class VaultScan:
    concepts: List[NoteEntry] = field(default_factory=list)
    extracted: List[NoteEntry] = field(default_factory=list)
    communities: List[CommunityEntry] = field(default_factory=list)


def _extract_title(body: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def _extract_summary(body: str) -> str:
    """First non-heading paragraph."""
    paragraphs = [
        p.strip()
        for p in body.split("\n\n")
        if p.strip() and not p.lstrip().startswith("#")
    ]
    if not paragraphs:
        return ""
    first = paragraphs[0].replace("\n", " ")
    return first[:200]


def scan_vault(vault: Path) -> VaultScan:
    scan = VaultScan()
    for md in sorted(vault.glob("*.md")):
        if md.name == INDEX_FILENAME:
            continue
        fm, body = split_document(md)
        layer = fm.get("layer")
        ftype = fm.get("type")
        slug = fm.get("slug", md.stem)
        title = _extract_title(body, fallback=md.stem)

        if layer == "concept":
            scan.concepts.append(NoteEntry(
                path=md,
                slug=slug,
                title=title,
                summary=_extract_summary(body),
            ))
        elif layer == "community" or ftype == "community" or md.name.startswith("_COMMUNITY_"):
            label = fm.get("label", md.stem.replace("_COMMUNITY_", ""))
            # graphify uses `members:` (int); our original schema used `node_count:` — accept either.
            node_count_raw = fm.get("node_count") or fm.get("members") or 0
            # Extract top member names from the body (graphify community notes list members
            # as bullet points like "- [[NodeName]] - code - <path>"). Take first 3 for INDEX hints.
            top_members: List[str] = []
            for line in body.splitlines():
                m_match = re.match(r"^\s*-\s*\[\[([^\]]+)\]\]", line)
                if m_match:
                    name = m_match.group(1).strip()
                    # Skip obvious noise like dunder method labels
                    if name.startswith(".") or name.startswith("__"):
                        continue
                    top_members.append(name)
                    if len(top_members) >= 3:
                        break
            scan.communities.append(CommunityEntry(
                path=md,
                label=label,
                node_count=int(node_count_raw) if node_count_raw else 0,
                top_members=top_members,
            ))
        elif layer == "extracted" or ftype == "code":
            # graphify-extracted notes use `type: code` without a `layer` field;
            # our original schema uses `layer: extracted`. Accept either.
            scan.extracted.append(NoteEntry(
                path=md, slug=slug, title=title,
            ))
    return scan


def write_index(
    vault: Path,
    source_paths: List[str],
    commit_sha: str,
) -> Path:
    scan = scan_vault(vault)
    code_concepts = [c for c in scan.concepts]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines: List[str] = []
    lines.append("---")
    lines.append("layer: index")
    lines.append(f"last_refresh: {timestamp}")
    lines.append(f"last_refresh_commit: {commit_sha}")
    lines.append("---")
    lines.append("")
    lines.append("# Project Brain Index")
    lines.append("")
    lines.append(f"Last refresh: {timestamp} (commit {commit_sha})")
    lines.append(f"Source: {', '.join(source_paths)}")
    lines.append(
        f"Vault stats: {len(scan.extracted)} extracted, "
        f"{len(code_concepts)} code-concept, "
        f"0 business, "
        f"{len(scan.communities)} communities"
    )
    lines.append("")

    if scan.communities:
        # Sort communities by member count descending so the meaty ones surface first.
        sorted_communities = sorted(
            scan.communities, key=lambda c: c.node_count, reverse=True
        )
        lines.append("## Communities (graphify)")
        for c in sorted_communities:
            hint = ""
            if c.top_members:
                hint = f" — e.g. {', '.join(c.top_members)}"
            lines.append(
                f"- [[_COMMUNITY_{c.label}]] ({c.node_count} nodes){hint}"
            )
        lines.append("")

    if code_concepts:
        lines.append("## Code concepts")
        for n in code_concepts:
            summary = n.summary or "(no summary)"
            lines.append(f"- [[{n.slug}]] — {summary}")
        lines.append("")

    lines.append("## How to use")
    lines.append("- Concept-level question → start with code-concept")
    lines.append('- "Gde tačno živi X?" → otvori extracted note')
    lines.append('- "Ko zove ovu klasu?" → graphify-out/graph.json')
    lines.append("")

    out = vault / INDEX_FILENAME
    out.write_text("\n".join(lines))
    return out
