"""Register/unregister a vault path with the user's Obsidian app via obsidian.json."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json
import os
import sys
import tempfile
import time
import uuid


@dataclass
class RegisterResult:
    status: str
    message: str = ""


def _obsidian_config_path() -> Optional[Path]:
    """Return platform-specific obsidian.json path, or None on unsupported platform."""
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "obsidian" / "obsidian.json"
    if sys.platform.startswith("linux"):
        return home / ".config" / "obsidian" / "obsidian.json"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "obsidian" / "obsidian.json"
    return None


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", dir=str(path.parent), delete=False, suffix=".tmp"
    )
    try:
        json.dump(data, tmp, indent=2)
        tmp.close()
        os.replace(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass
        raise


def register_vault(vault_path: Path) -> RegisterResult:
    cfg = _obsidian_config_path()
    if cfg is None:
        return RegisterResult(status="unsupported_platform")
    if not cfg.parent.exists():
        return RegisterResult(status="obsidian_not_installed",
                              message=f"{cfg.parent} not found")
    if not cfg.exists():
        return RegisterResult(status="obsidian_not_installed",
                              message=f"{cfg} not found")

    try:
        data = json.loads(cfg.read_text() or "{}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed obsidian.json at {cfg}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"obsidian.json at {cfg} is not a JSON object")

    vaults = data.setdefault("vaults", {})
    target = str(vault_path.resolve())

    for entry in vaults.values():
        if isinstance(entry, dict) and entry.get("path") == target:
            return RegisterResult(status="already_present")

    vault_id = uuid.uuid4().hex[:16]
    vaults[vault_id] = {
        "path": target,
        "ts": int(time.time() * 1000),
        "open": False,
    }

    _atomic_write_json(cfg, data)
    return RegisterResult(status="registered")


def unregister_vault(vault_path: Path) -> RegisterResult:
    cfg = _obsidian_config_path()
    if cfg is None:
        return RegisterResult(status="unsupported_platform")
    if not cfg.exists():
        return RegisterResult(status="obsidian_not_installed")

    try:
        data = json.loads(cfg.read_text() or "{}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed obsidian.json at {cfg}: {e}") from e

    vaults = data.get("vaults", {}) or {}
    target = str(vault_path.resolve())
    to_remove = [vid for vid, entry in vaults.items()
                 if isinstance(entry, dict) and entry.get("path") == target]

    if not to_remove:
        return RegisterResult(status="not_present")

    for vid in to_remove:
        del vaults[vid]
    data["vaults"] = vaults
    _atomic_write_json(cfg, data)
    return RegisterResult(status="unregistered")
