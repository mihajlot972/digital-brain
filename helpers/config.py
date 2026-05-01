"""Parse and validate .brain-config.yaml."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List
import yaml


CONFIG_FILENAME = ".brain-config.yaml"
DEFAULT_VAULT_DIR = "project-brain/"


class ConfigNotFoundError(FileNotFoundError):
    pass


class ConfigSchemaError(ValueError):
    pass


@dataclass
class BrainConfig:
    source_paths: List[str]
    vault_dir: str
    repo_root: Path

    def resolved_source_paths(self) -> List[Path]:
        """Return absolute paths; raise if any missing."""
        out: List[Path] = []
        for rel in self.source_paths:
            abs_path = (self.repo_root / rel).resolve()
            if not abs_path.exists():
                raise ConfigSchemaError(
                    f"source_paths entry '{rel}' does not exist "
                    f"(resolved to {abs_path})"
                )
            out.append(abs_path)
        return out

    def resolved_vault_dir(self) -> Path:
        return (self.repo_root / self.vault_dir).resolve()


def load_config(repo_root: Path) -> BrainConfig:
    cfg_path = repo_root / CONFIG_FILENAME
    if not cfg_path.exists():
        raise ConfigNotFoundError(
            f"{CONFIG_FILENAME} not found in {repo_root}. "
            f"(In v0, create it manually. In v1, run /init-brain.)"
        )
    try:
        raw = yaml.safe_load(cfg_path.read_text()) or {}
    except yaml.YAMLError as e:
        raise ConfigSchemaError(f"Invalid YAML in {CONFIG_FILENAME}: {e}") from e

    source_paths = raw.get("source_paths")
    if source_paths is None:
        raise ConfigSchemaError(
            f"{CONFIG_FILENAME} missing required field: source_paths"
        )
    if not isinstance(source_paths, list):
        raise ConfigSchemaError(
            f"{CONFIG_FILENAME}: source_paths must be a list, got {type(source_paths).__name__}"
        )
    if len(source_paths) == 0:
        raise ConfigSchemaError(f"{CONFIG_FILENAME}: source_paths is empty")

    vault_dir = raw.get("vault_dir", DEFAULT_VAULT_DIR)
    if not isinstance(vault_dir, str):
        raise ConfigSchemaError(
            f"{CONFIG_FILENAME}: vault_dir must be a string"
        )

    return BrainConfig(
        source_paths=[str(p) for p in source_paths],
        vault_dir=vault_dir,
        repo_root=repo_root,
    )
