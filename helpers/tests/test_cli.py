"""Tests for digital_brain_helpers.cli."""
from __future__ import annotations
import json
import os
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


def test_remove_preserves_foreign_post_commit_hook(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    (tmp_path / "vault").mkdir()
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    foreign_target = tmp_path / "foreign_script.sh"
    foreign_target.write_text("#!/bin/sh\necho foreign\n")
    foreign_target.chmod(0o755)
    hook = tmp_path / ".git" / "hooks" / "post-commit"
    hook.symlink_to(foreign_target)

    monkeypatch.setattr(cli, "_graveyard_root", lambda: tmp_path / "grave")
    monkeypatch.setattr(cli, "unregister_vault_safe", lambda p: None)
    # Fake an install root that does NOT contain the foreign hook
    install_root = tmp_path / "install"
    (install_root / "helpers").mkdir(parents=True)
    (install_root / "helpers" / "pyproject.toml").write_text("[project]\n")
    (install_root / "hooks").mkdir()
    (install_root / "skills").mkdir()
    monkeypatch.setattr(cli, "resolve_install_root", lambda: install_root)

    rc = cli.main(["remove", "--yes"])
    assert rc == 0
    # Foreign hook should still be present
    assert hook.exists() and hook.is_symlink()
    assert Path(os.readlink(hook)) == foreign_target


def test_remove_removes_our_post_commit_hook(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".digital-brain-config.yaml").write_text(
        "source_paths: [.]\nvault_dir: vault/\n"
    )
    (tmp_path / "vault").mkdir()
    (tmp_path / ".git" / "hooks").mkdir(parents=True)

    install_root = tmp_path / "install"
    (install_root / "helpers").mkdir(parents=True)
    (install_root / "helpers" / "pyproject.toml").write_text("[project]\n")
    (install_root / "hooks").mkdir()
    (install_root / "skills").mkdir()
    our_hook = install_root / "hooks" / "post-commit"
    our_hook.write_text("#!/bin/sh\n")
    our_hook.chmod(0o755)
    hook_link = tmp_path / ".git" / "hooks" / "post-commit"
    hook_link.symlink_to(our_hook)

    monkeypatch.setattr(cli, "_graveyard_root", lambda: tmp_path / "grave")
    monkeypatch.setattr(cli, "unregister_vault_safe", lambda p: None)
    monkeypatch.setattr(cli, "resolve_install_root", lambda: install_root)

    rc = cli.main(["remove", "--yes"])
    assert rc == 0
    assert not hook_link.exists()


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


def test_uninstall_removes_only_our_hook_entries(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".claude").mkdir()
    settings = fake_home / ".claude" / "settings.json"

    install_root = tmp_path / "install"
    (install_root / "helpers").mkdir(parents=True)
    (install_root / "helpers" / "pyproject.toml").write_text("[project]\n")
    (install_root / "hooks").mkdir()
    (install_root / "skills").mkdir()
    (install_root / "skills" / "refresh-digital-brain").mkdir()
    (install_root / "skills" / "load-digital-brain").mkdir()

    settings.write_text(json.dumps({
        "hooks": {
            "SessionStart": [
                {"matcher": "*", "hooks": [
                    {"type": "command", "command": str(install_root / "hooks" / "session_start.sh")}
                ]},
                {"matcher": "*", "hooks": [
                    {"type": "command", "command": "/usr/local/bin/other-hook.sh"}
                ]},
            ]
        }
    }))

    (fake_home / ".claude" / "skills").mkdir()
    skill_link_refresh = fake_home / ".claude" / "skills" / "refresh-digital-brain"
    skill_link_load = fake_home / ".claude" / "skills" / "load-digital-brain"
    skill_link_refresh.symlink_to(install_root / "skills" / "refresh-digital-brain")
    skill_link_load.symlink_to(install_root / "skills" / "load-digital-brain")

    (fake_home / ".local" / "bin").mkdir(parents=True)
    console_link = fake_home / ".local" / "bin" / "digital-brain"
    console_target = install_root / "helpers" / ".venv" / "bin" / "digital-brain"
    console_target.parent.mkdir(parents=True)
    console_target.write_text("#!/bin/sh\n")
    console_target.chmod(0o755)
    console_link.symlink_to(console_target)

    (fake_home / ".digital-brain").mkdir()
    (fake_home / ".digital-brain" / "install.json").write_text(
        json.dumps({"install_root": str(install_root)})
    )

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(cli, "resolve_install_root", lambda: install_root)

    rc = cli.main(["uninstall", "--yes"])
    assert rc == 0

    new_settings = json.loads(settings.read_text())
    sessionstart = new_settings["hooks"]["SessionStart"]
    assert len(sessionstart) == 1
    assert sessionstart[0]["hooks"][0]["command"] == "/usr/local/bin/other-hook.sh"

    assert not skill_link_refresh.exists()
    assert not skill_link_load.exists()
    assert not console_link.exists()
    assert not (fake_home / ".digital-brain" / "install.json").exists()
