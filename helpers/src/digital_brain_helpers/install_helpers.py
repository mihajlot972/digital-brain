"""Helpers for install.sh — invoked as `python -m digital_brain_helpers.install_helpers patch <settings_path> <install_root>`."""
from __future__ import annotations
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path


def patch_settings(settings_path: Path, install_root: Path) -> None:
    install_root = Path(install_root)
    if settings_path.exists():
        data = json.loads(settings_path.read_text() or "{}")
    else:
        data = {}
    hooks = data.setdefault("hooks", {})

    targets = {
        "SessionStart": str(install_root / "hooks" / "session_start.sh"),
        "Stop": str(install_root / "hooks" / "stale_check.sh"),
    }
    for event, command in targets.items():
        entries = hooks.setdefault(event, [])
        existing_cmds = [
            h.get("command")
            for entry in entries
            if isinstance(entry, dict)
            for h in entry.get("hooks", [])
            if isinstance(h, dict)
        ]
        if command in existing_cmds:
            continue
        entries.append({
            "matcher": "*",
            "hooks": [{"type": "command", "command": command}],
        })

    _atomic_write(settings_path, json.dumps(data, indent=2))


def write_install_json(install_json_path: Path, install_root: Path, version: str) -> None:
    payload = {
        "install_root": str(install_root.resolve()),
        "installed_at": datetime.datetime.now(datetime.timezone.utc)
            .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "version": version,
    }
    install_json_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(install_json_path, json.dumps(payload, indent=2))


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode="w", dir=str(path.parent), delete=False, suffix=".tmp"
    )
    try:
        tmp.write(content)
        tmp.close()
        os.replace(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass
        raise


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: install_helpers {patch,install-json} ...", file=sys.stderr)
        return 2
    cmd, *rest = argv
    if cmd == "patch" and len(rest) == 2:
        patch_settings(Path(rest[0]), Path(rest[1]))
        return 0
    if cmd == "install-json" and len(rest) == 3:
        write_install_json(Path(rest[0]), Path(rest[1]), rest[2])
        return 0
    print(f"unknown invocation: {argv}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
