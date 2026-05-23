"""Tests for install_helpers."""
import json
from pathlib import Path

import pytest

from digital_brain_helpers import install_helpers


def test_patch_empty_settings_adds_hooks(tmp_path):
    settings = tmp_path / "settings.json"
    install_root = tmp_path / "install"
    install_helpers.patch_settings(settings, install_root)

    data = json.loads(settings.read_text())
    assert "SessionStart" in data["hooks"]
    assert "Stop" in data["hooks"]
    ss_cmd = data["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert ss_cmd == str(install_root / "hooks" / "session_start.sh")


def test_patch_preserves_existing_hooks(tmp_path):
    settings = tmp_path / "settings.json"
    install_root = tmp_path / "install"
    settings.write_text(json.dumps({
        "hooks": {
            "SessionStart": [
                {"matcher": "*", "hooks": [
                    {"type": "command", "command": "/other/hook.sh"}
                ]}
            ]
        }
    }))
    install_helpers.patch_settings(settings, install_root)

    data = json.loads(settings.read_text())
    cmds = [
        h["command"]
        for entry in data["hooks"]["SessionStart"]
        for h in entry["hooks"]
    ]
    assert "/other/hook.sh" in cmds
    assert str(install_root / "hooks" / "session_start.sh") in cmds


def test_patch_is_idempotent(tmp_path):
    settings = tmp_path / "settings.json"
    install_root = tmp_path / "install"
    install_helpers.patch_settings(settings, install_root)
    install_helpers.patch_settings(settings, install_root)

    data = json.loads(settings.read_text())
    ss = data["hooks"]["SessionStart"]
    cmds = [h["command"] for entry in ss for h in entry["hooks"]]
    assert cmds.count(str(install_root / "hooks" / "session_start.sh")) == 1


def test_write_install_json(tmp_path):
    out = tmp_path / "sub" / "install.json"
    install_root = tmp_path / "brain"
    install_helpers.write_install_json(out, install_root, "1.2.3")

    data = json.loads(out.read_text())
    assert data["version"] == "1.2.3"
    assert data["install_root"] == str(install_root.resolve())
    assert data["installed_at"].endswith("Z")


def test_main_patch(tmp_path):
    settings = tmp_path / "settings.json"
    install_root = tmp_path / "brain"
    rc = install_helpers.main(["patch", str(settings), str(install_root)])
    assert rc == 0
    assert json.loads(settings.read_text())["hooks"]["Stop"]


def test_main_install_json(tmp_path):
    out = tmp_path / "install.json"
    install_root = tmp_path / "brain"
    rc = install_helpers.main(["install-json", str(out), str(install_root), "0.9.0"])
    assert rc == 0
    assert json.loads(out.read_text())["version"] == "0.9.0"


def test_main_no_args(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", ["install_helpers"])
    rc = install_helpers.main(None)
    assert rc == 2
    assert "usage" in capsys.readouterr().err


def test_main_unknown_cmd(capsys):
    rc = install_helpers.main(["bogus"])
    assert rc == 2
    assert "unknown" in capsys.readouterr().err
