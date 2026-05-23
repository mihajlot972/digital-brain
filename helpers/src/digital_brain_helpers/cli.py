"""digital-brain CLI: per-project `remove` and global `uninstall`."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import List, Optional


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
