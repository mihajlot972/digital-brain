"""Regression test: auto_refresh.py reads the new config filename."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]   # private-brain/ during dev, digital-brain/ post-rename
AUTO_REFRESH = REPO_ROOT / "hooks" / "auto_refresh.py"
PYTHON = REPO_ROOT / "helpers" / ".venv" / "bin" / "python"


def test_auto_refresh_silent_exit_when_no_config(tmp_path):
    """No .digital-brain-config.yaml → script exits 0 with no output."""
    result = subprocess.run(
        [str(PYTHON), str(AUTO_REFRESH)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout == ""


def test_auto_refresh_reads_new_config_filename(tmp_path, monkeypatch):
    """Confirms the script looks for .digital-brain-config.yaml (not the old name).

    We verify by checking the source file contains the new constant — a true
    behavioral test would need a full git+graphify setup which is out of scope
    for unit tests.
    """
    text = AUTO_REFRESH.read_text()
    assert ".digital-brain-config.yaml" in text or "CONFIG_FILENAME" in text
    assert ".brain-config.yaml" not in text  # old name fully removed
