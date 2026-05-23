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
