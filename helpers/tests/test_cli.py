"""Tests for digital_brain_helpers.cli."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from digital_brain_helpers import cli


def test_main_no_args_prints_help_and_exits_nonzero(capsys):
    rc = cli.main([])
    captured = capsys.readouterr()
    assert rc != 0
    assert "remove" in captured.out or "remove" in captured.err
    assert "uninstall" in captured.out or "uninstall" in captured.err


def _make_install_root(root: Path) -> Path:
    """Create the minimum layout that `_looks_like_install_root` accepts."""
    (root / "helpers").mkdir(parents=True, exist_ok=True)
    (root / "helpers" / "pyproject.toml").write_text("[project]\nname='x'\n")
    (root / "hooks").mkdir(exist_ok=True)
    (root / "skills").mkdir(exist_ok=True)
    return root


def test_resolve_install_root_from_install_json(tmp_path, monkeypatch):
    install_root = _make_install_root(tmp_path / "install")

    db_dir = tmp_path / "dot_digital_brain"
    db_dir.mkdir()
    (db_dir / "install.json").write_text(
        json.dumps({"install_root": str(install_root)})
    )
    monkeypatch.setattr(cli, "_install_json_path", lambda: db_dir / "install.json")

    resolved = cli.resolve_install_root()
    assert resolved == install_root.resolve()


def test_resolve_install_root_falls_back_when_install_json_points_at_deleted_dir(
    tmp_path, monkeypatch
):
    db_dir = tmp_path / "dot_digital_brain"
    db_dir.mkdir()
    (db_dir / "install.json").write_text(
        json.dumps({"install_root": "/definitely/not/here"})
    )
    monkeypatch.setattr(cli, "_install_json_path", lambda: db_dir / "install.json")
    monkeypatch.setattr(cli, "_console_script_symlink", lambda: None)

    with pytest.raises(cli.InstallRootNotFound):
        cli.resolve_install_root()


def test_resolve_install_root_recovers_when_install_json_dir_deleted_but_symlink_works(
    tmp_path, monkeypatch
):
    """install.json points at a deleted dir, but the console symlink reveals the real install."""
    install_root = _make_install_root(tmp_path / "real_install")
    venv_bin = install_root / "helpers" / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    target_script = venv_bin / "digital-brain"
    target_script.write_text("#!/bin/sh\n")
    target_script.chmod(0o755)
    link = tmp_path / "link_digital_brain"
    link.symlink_to(target_script)

    db_dir = tmp_path / "dot_digital_brain"
    db_dir.mkdir()
    (db_dir / "install.json").write_text(
        json.dumps({"install_root": "/definitely/not/here"})
    )
    monkeypatch.setattr(cli, "_install_json_path", lambda: db_dir / "install.json")
    monkeypatch.setattr(cli, "_console_script_symlink", lambda: link)

    resolved = cli.resolve_install_root()
    assert resolved == install_root.resolve()


def test_remove_yes_deletes_vault_and_config_preserves_concept_notes(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    # set up brain project
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Concept1.md").write_text(
        "---\nlayer: concept\n---\n\n# Concept 1\nBody.\n"
    )
    (vault / "Extracted.md").write_text(
        "---\ntype: code\n---\n\n# Extracted\nBody.\n"
    )

    # redirect graveyard + obsidian register + install root
    graveyard = tmp_path / "graveyard"
    monkeypatch.setattr(cli, "_graveyard_root", lambda: graveyard)
    monkeypatch.setattr(cli, "unregister_vault_safe", lambda p: None)
    # no install.json — _remove_hook_symlink should still no-op cleanly
    monkeypatch.setattr(cli, "resolve_install_root",
                        lambda: (_ for _ in ()).throw(cli.InstallRootNotFound("no")))

    rc = cli.main(["remove", "--yes"])
    assert rc == 0
    assert not (tmp_path / ".digital-brain-config.yaml").exists()
    assert not vault.exists()
    # graveyard copy of concept note exists; extracted note NOT copied
    grav_files = list(graveyard.rglob("*.md"))
    assert any(f.name == "Concept1.md" for f in grav_files)
    assert not any(f.name == "Extracted.md" for f in grav_files)


def test_remove_exits_1_in_non_brain_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["remove", "--yes"])
    captured = capsys.readouterr()
    assert rc == 1
    assert ".digital-brain-config.yaml" in (captured.err or captured.out)


def test_resolve_install_root_uses_symlink_fallback(tmp_path, monkeypatch):
    install_root = _make_install_root(tmp_path / "fallback_root")
    venv_bin = install_root / "helpers" / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    target_script = venv_bin / "digital-brain"
    target_script.write_text("#!/bin/sh\n")
    target_script.chmod(0o755)

    link = tmp_path / "link_digital_brain"
    link.symlink_to(target_script)

    monkeypatch.setattr(cli, "_install_json_path", lambda: tmp_path / "nonexistent.json")
    monkeypatch.setattr(cli, "_console_script_symlink", lambda: link)

    resolved = cli.resolve_install_root()
    assert resolved == install_root.resolve()
