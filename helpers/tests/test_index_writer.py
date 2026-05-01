"""Tests for _INDEX.md generation."""
from pathlib import Path
import pytest
from frontmatter import write_frontmatter
from index_writer import write_index, scan_vault


def make_concept(vault: Path, slug: str, title: str, summary: str = "Summary.") -> None:
    write_frontmatter(
        vault / f"{slug}.md",
        frontmatter={"layer": "concept", "type": "code", "slug": slug},
        body=f"# {title}\n\n{summary}\n",
    )


def make_extracted(vault: Path, name: str) -> None:
    write_frontmatter(
        vault / f"{name}.md",
        frontmatter={"layer": "extracted", "type": "code", "node_id": name},
        body=f"# {name}\n",
    )


def make_community(vault: Path, label: str, node_count: int = 5) -> None:
    write_frontmatter(
        vault / f"_COMMUNITY_{label}.md",
        frontmatter={"layer": "community", "label": label, "node_count": node_count},
        body=f"# Community: {label}\n",
    )


def test_scan_classifies_notes(tmp_path: Path):
    vault = tmp_path / "v"
    vault.mkdir()
    make_concept(vault, "manticore-retrieval", "Manticore Retrieval")
    make_extracted(vault, "ChatRouter")
    make_community(vault, "Retrieval")
    result = scan_vault(vault)
    assert len(result.concepts) == 1
    assert len(result.extracted) == 1
    assert len(result.communities) == 1
    assert result.concepts[0].slug == "manticore-retrieval"


def test_scan_extracts_first_heading_as_title(tmp_path: Path):
    vault = tmp_path / "v"
    vault.mkdir()
    make_concept(vault, "foo", "Foo Title")
    result = scan_vault(vault)
    assert result.concepts[0].title == "Foo Title"


def test_scan_extracts_first_paragraph_as_summary(tmp_path: Path):
    vault = tmp_path / "v"
    vault.mkdir()
    make_concept(vault, "foo", "Foo", "First sentence describing it.")
    result = scan_vault(vault)
    assert result.concepts[0].summary == "First sentence describing it."


def test_write_index_includes_all_sections(tmp_path: Path):
    vault = tmp_path / "v"
    vault.mkdir()
    make_concept(vault, "manticore-retrieval", "Manticore Retrieval", "Hybrid search.")
    make_concept(vault, "chunking-pipeline", "Chunking Pipeline", "Multi-stage chunks.")
    make_extracted(vault, "ChatRouter")
    make_community(vault, "Retrieval")
    write_index(vault, source_paths=["src/"], commit_sha="abc1234")

    index = (vault / "_INDEX.md").read_text()
    assert "# Project Brain Index" in index
    assert "abc1234" in index
    assert "src/" in index
    assert "Vault stats: 1 extracted, 2 code-concept" in index
    assert "[[manticore-retrieval]]" in index
    assert "Hybrid search." in index
    assert "[[_COMMUNITY_Retrieval]]" in index


def test_write_index_handles_empty_vault(tmp_path: Path):
    vault = tmp_path / "v"
    vault.mkdir()
    write_index(vault, source_paths=["src/"], commit_sha="abc1234")
    index = (vault / "_INDEX.md").read_text()
    assert "0 extracted, 0 code-concept" in index


def test_write_index_skips_index_itself(tmp_path: Path):
    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "_INDEX.md").write_text("---\nlayer: index\n---\n\n# Old\n")
    make_concept(vault, "foo", "Foo")
    write_index(vault, source_paths=["src/"], commit_sha="abc")
    result = scan_vault(vault)
    assert len(result.concepts) == 1  # _INDEX.md not counted
