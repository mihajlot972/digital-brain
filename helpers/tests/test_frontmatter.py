"""Tests for YAML frontmatter read/write in markdown files."""
from pathlib import Path
import pytest
from digital_brain_helpers.frontmatter import (
    read_frontmatter,
    write_frontmatter,
    update_frontmatter,
    split_document,
)


def test_split_document_with_frontmatter(tmp_path: Path):
    f = tmp_path / "note.md"
    f.write_text("---\nkey: value\n---\n\n# Body\n\nText.\n")
    fm, body = split_document(f)
    assert fm == {"key": "value"}
    assert body.startswith("# Body")


def test_split_document_without_frontmatter(tmp_path: Path):
    f = tmp_path / "plain.md"
    f.write_text("# Just a heading\n\nNo frontmatter here.\n")
    fm, body = split_document(f)
    assert fm == {}
    assert body.startswith("# Just")


def test_split_document_empty_file(tmp_path: Path):
    f = tmp_path / "empty.md"
    f.write_text("")
    fm, body = split_document(f)
    assert fm == {}
    assert body == ""


def test_read_frontmatter_returns_dict(tmp_path: Path):
    f = tmp_path / "note.md"
    f.write_text("---\nlayer: concept\ntype: code\n---\n\nBody.\n")
    fm = read_frontmatter(f)
    assert fm["layer"] == "concept"
    assert fm["type"] == "code"


def test_read_malformed_frontmatter_returns_empty(tmp_path: Path):
    """We're tolerant — broken YAML returns {} so refresh can recover."""
    f = tmp_path / "note.md"
    f.write_text("---\n[unclosed\n---\n\nBody.\n")
    fm = read_frontmatter(f)
    assert fm == {}


def test_write_frontmatter_creates_new_file(tmp_path: Path):
    f = tmp_path / "new.md"
    write_frontmatter(
        f,
        frontmatter={"layer": "concept", "type": "code", "slug": "foo"},
        body="# Foo\n\nA concept.\n",
    )
    text = f.read_text()
    assert text.startswith("---\n")
    assert "layer: concept" in text
    assert "# Foo" in text
    # Frontmatter terminator before body
    assert text.index("---\n", 4) < text.index("# Foo")


def test_write_preserves_list_values(tmp_path: Path):
    f = tmp_path / "list.md"
    write_frontmatter(
        f,
        frontmatter={"source_paths": ["a/b.py", "c/d.py"]},
        body="body",
    )
    text = f.read_text()
    assert "- a/b.py" in text
    assert "- c/d.py" in text


def test_update_frontmatter_overwrites_keys(tmp_path: Path):
    f = tmp_path / "note.md"
    f.write_text("---\nlayer: concept\nslug: old\n---\n\nBody\n")
    update_frontmatter(f, {"slug": "new", "tags": ["a", "b"]})
    fm = read_frontmatter(f)
    assert fm["layer"] == "concept"   # preserved
    assert fm["slug"] == "new"        # overwritten
    assert fm["tags"] == ["a", "b"]   # added
    assert "Body" in f.read_text()    # body preserved
