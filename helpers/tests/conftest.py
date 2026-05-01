"""Shared pytest fixtures."""
import pytest
from pathlib import Path


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """A fresh temp dir simulating a project root."""
    return tmp_path
