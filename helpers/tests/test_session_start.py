"""Tests for digital_brain_helpers.session_start."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from digital_brain_helpers import session_start


def test_no_config_silent_exit(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = session_start.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_missing_vault_emits_build_prompt(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: digital-brain/\n"
    )
    rc = session_start.main()
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "Build brain" in ctx or "/refresh-digital-brain" in ctx


def test_small_index_emitted_in_full(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    index_content = "# Index\n\nSmall content under 1k chars."
    (vault / "_INDEX.md").write_text(index_content)

    rc = session_start.main()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["hookSpecificOutput"]["additionalContext"] == index_content


def test_large_index_truncated_with_pointer(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    big = "X" * 12000
    (vault / "_INDEX.md").write_text(big)

    rc = session_start.main()
    payload = json.loads(capsys.readouterr().out)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert len(ctx) < len(big)
    assert "truncated" in ctx
    assert "_INDEX.md" in ctx


def test_finds_config_in_parent_dir(tmp_path, capsys, monkeypatch):
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)

    rc = session_start.main()
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "Build brain" in ctx or "/refresh-digital-brain" in ctx
