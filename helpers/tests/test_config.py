"""Tests for .brain-config.yaml parsing."""
from pathlib import Path
import pytest
import yaml
from digital_brain_helpers.config import (
    load_config,
    BrainConfig,
    ConfigNotFoundError,
    ConfigSchemaError,
)


def write_config(repo_root: Path, content: str) -> Path:
    cfg = repo_root / ".brain-config.yaml"
    cfg.write_text(content)
    return cfg


def test_loads_minimal_valid_config(tmp_repo: Path):
    write_config(tmp_repo, """
source_paths:
  - src/
vault_dir: project-brain/
""")
    cfg = load_config(tmp_repo)
    assert isinstance(cfg, BrainConfig)
    assert cfg.source_paths == ["src/"]
    assert cfg.vault_dir == "project-brain/"
    assert cfg.repo_root == tmp_repo


def test_supports_multiple_source_paths(tmp_repo: Path):
    write_config(tmp_repo, """
source_paths:
  - packages/api/src/
  - packages/worker/src/
vault_dir: .brain/
""")
    cfg = load_config(tmp_repo)
    assert cfg.source_paths == ["packages/api/src/", "packages/worker/src/"]


def test_missing_config_raises(tmp_repo: Path):
    with pytest.raises(ConfigNotFoundError) as exc:
        load_config(tmp_repo)
    assert ".brain-config.yaml" in str(exc.value)


def test_missing_source_paths_raises(tmp_repo: Path):
    write_config(tmp_repo, "vault_dir: project-brain/\n")
    with pytest.raises(ConfigSchemaError, match="source_paths"):
        load_config(tmp_repo)


def test_empty_source_paths_raises(tmp_repo: Path):
    write_config(tmp_repo, """
source_paths: []
vault_dir: project-brain/
""")
    with pytest.raises(ConfigSchemaError, match="source_paths.*empty"):
        load_config(tmp_repo)


def test_missing_vault_dir_uses_default(tmp_repo: Path):
    write_config(tmp_repo, """
source_paths:
  - src/
""")
    cfg = load_config(tmp_repo)
    assert cfg.vault_dir == "project-brain/"


def test_malformed_yaml_raises(tmp_repo: Path):
    write_config(tmp_repo, "source_paths: [unclosed")
    with pytest.raises(ConfigSchemaError, match="YAML"):
        load_config(tmp_repo)


def test_resolved_source_paths_are_absolute(tmp_repo: Path):
    (tmp_repo / "src").mkdir()
    write_config(tmp_repo, """
source_paths:
  - src/
""")
    cfg = load_config(tmp_repo)
    resolved = cfg.resolved_source_paths()
    assert len(resolved) == 1
    assert resolved[0].is_absolute()
    assert resolved[0] == tmp_repo / "src"


def test_resolved_source_path_missing_raises(tmp_repo: Path):
    write_config(tmp_repo, """
source_paths:
  - nonexistent/
""")
    cfg = load_config(tmp_repo)
    with pytest.raises(ConfigSchemaError, match="does not exist"):
        cfg.resolved_source_paths()
