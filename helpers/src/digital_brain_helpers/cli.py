"""digital-brain CLI: per-project `remove` and global `uninstall`."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional


DEFAULT_INSTALL_JSON = "~/.digital-brain/install.json"
DEFAULT_CONSOLE_SCRIPT = "~/.local/bin/digital-brain"


class InstallRootNotFound(RuntimeError):
    pass


def _install_json_path() -> Path:
    return Path(os.path.expanduser(DEFAULT_INSTALL_JSON))


def _console_script_symlink() -> Optional[Path]:
    p = Path(os.path.expanduser(DEFAULT_CONSOLE_SCRIPT))
    return p if p.is_symlink() else None


def _looks_like_install_root(p: Path) -> bool:
    """Discriminator: a real install always has helpers/pyproject.toml + hooks/ + skills/."""
    return (
        (p / "helpers" / "pyproject.toml").is_file()
        and (p / "hooks").is_dir()
        and (p / "skills").is_dir()
    )


def resolve_install_root() -> Path:
    """Discover install_root via install.json then symlink fallback."""
    ij = _install_json_path()
    if ij.is_file():
        try:
            data = json.loads(ij.read_text())
            candidate = Path(data["install_root"]).resolve()
            if candidate.is_dir() and _looks_like_install_root(candidate):
                return candidate
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    link = _console_script_symlink()
    if link is not None:
        try:
            target = Path(os.readlink(link)).resolve()
            # Walk up looking for install root layout
            for ancestor in [target.parent, *target.parents]:
                if _looks_like_install_root(ancestor):
                    return ancestor.resolve()
        except OSError:
            pass

    raise InstallRootNotFound(
        "Cannot locate digital-brain install root. "
        "Reinstall via `bash <repo>/hooks/install.sh` or remove manually."
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="digital-brain")
    sub = p.add_subparsers(dest="command")

    p_remove = sub.add_parser("remove", help="Remove digital-brain from current project")
    p_remove.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    p_uninstall = sub.add_parser("uninstall", help="Uninstall digital-brain globally")
    p_uninstall.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = _build_parser()
    if not argv:
        parser.print_help()
        return 2
    args = parser.parse_args(argv)
    if args.command == "remove":
        return cmd_remove(args)
    if args.command == "uninstall":
        return cmd_uninstall(args)
    parser.print_help()
    return 2


def cmd_remove(args) -> int:
    raise NotImplementedError


def cmd_uninstall(args) -> int:
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
