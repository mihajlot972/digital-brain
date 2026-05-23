"""Tests for digital_brain_helpers.obsidian_register."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from digital_brain_helpers import obsidian_register
from digital_brain_helpers.obsidian_register import register_vault, RegisterResult


@pytest.fixture
def fake_obsidian_config(tmp_path: Path, monkeypatch) -> Path:
    """Create a fake obsidian.json under tmp_path and monkeypatch the resolver to return it."""
    cfg_dir = tmp_path / "obsidian"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "obsidian.json"
    monkeypatch.setattr(obsidian_register, "_obsidian_config_path", lambda: cfg_path)
    return cfg_path


def test_register_into_empty_config_creates_vaults_section(fake_obsidian_config, tmp_path):
    fake_obsidian_config.write_text("{}")
    vault = tmp_path / "myvault"
    vault.mkdir()

    result = register_vault(vault)

    assert result.status == "registered"
    data = json.loads(fake_obsidian_config.read_text())
    assert "vaults" in data
    assert len(data["vaults"]) == 1
    entry = next(iter(data["vaults"].values()))
    assert entry["path"] == str(vault.resolve())
    assert "ts" in entry
    assert isinstance(entry["ts"], int)
    # ts is epoch ms — must be in a sane range (after year 2020, before year 2050)
    assert 1_577_836_800_000 < entry["ts"] < 2_524_608_000_000
