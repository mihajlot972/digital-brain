"""digital-brain CLI: per-project `remove` and global `uninstall`."""
from __future__ import annotations
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .config import load_config, ConfigSchemaError, ConfigNotFoundError
from .frontmatter import read_frontmatter
from .obsidian_register import unregister_vault


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


def _graveyard_root() -> Path:
    return Path.home() / ".digital-brain-graveyard"


def unregister_vault_safe(vault_path: Path) -> None:
    """Wrap unregister so callers don't need to import obsidian_register directly."""
    try:
        unregister_vault(vault_path)
    except (ValueError, OSError):
        pass


def _project_slug(repo_root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        name = Path(out.stdout.strip()).name
    except (subprocess.CalledProcessError, FileNotFoundError):
        name = repo_root.name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _copy_concepts_to_graveyard(vault: Path, dest: Path) -> int:
    if not vault.exists():
        return 0
    n = 0
    for md in vault.rglob("*.md"):
        try:
            fm = read_frontmatter(md)
        except Exception:
            continue
        if fm.get("layer") == "concept":
            target = dest / md.relative_to(vault)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md, target)
            n += 1
    return n


def _remove_hook_symlink(repo_root: Path) -> None:
    hook = repo_root / ".git" / "hooks" / "post-commit"
    if not hook.is_symlink():
        return
    try:
        install_root = resolve_install_root()
    except InstallRootNotFound:
        print(
            "  warn: cannot resolve install_root, leaving .git/hooks/post-commit in place",
            file=sys.stderr,
        )
        return
    target = Path(os.readlink(hook)).resolve()
    expected_prefix = (install_root / "hooks").resolve()
    try:
        target.relative_to(expected_prefix)
    except ValueError:
        print(
            "  info: .git/hooks/post-commit is not ours, leaving in place",
            file=sys.stderr,
        )
        return
    hook.unlink()


def cmd_remove(args) -> int:
    repo_root = Path.cwd()
    cfg_path = repo_root / ".digital-brain-config.yaml"
    if not cfg_path.exists():
        print(
            f"ERROR: .digital-brain-config.yaml not found in {repo_root}. "
            "Not a digital-brain project.",
            file=sys.stderr,
        )
        return 1

    try:
        cfg = load_config(repo_root)
        vault = cfg.resolved_vault_dir()
    except (ConfigNotFoundError, ConfigSchemaError) as e:
        print(f"ERROR loading config: {e}", file=sys.stderr)
        return 1

    if not args.yes:
        print(f"Remove digital-brain from {repo_root}?")
        print(f"  - delete {vault}/ (concept notes copied to graveyard first)")
        print(f"  - delete {cfg_path}")
        print(f"  - remove .git/hooks/post-commit (only if it's ours)")
        print(f"  - unregister vault from Obsidian")
        resp = input("Continue? (y/N) ").strip().lower()
        if resp not in ("y", "yes"):
            print("Aborted.")
            return 0

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    grave = _graveyard_root() / f"{_project_slug(repo_root)}-{timestamp}"
    n_preserved = _copy_concepts_to_graveyard(vault, grave)
    if n_preserved > 0:
        print(f"  preserved {n_preserved} concept notes to {grave}")

    if vault.exists():
        shutil.rmtree(vault)
        print(f"  deleted {vault}/")
    cfg_path.unlink()
    print(f"  deleted {cfg_path}")

    _remove_hook_symlink(repo_root)
    unregister_vault_safe(vault)

    print(f"digital-brain removed from {repo_root}.")
    return 0


def _matches_our_command(cmd: str, install_root: Path) -> bool:
    if not cmd:
        return False
    try:
        cmd_path = Path(os.path.expanduser(cmd)).resolve()
        return cmd_path.is_relative_to((install_root / "hooks").resolve())
    except (ValueError, OSError):
        return False


def _scrub_settings(settings_path: Path, install_root: Path) -> None:
    if not settings_path.exists():
        return
    data = json.loads(settings_path.read_text() or "{}")
    hooks = data.get("hooks", {})
    for event_name, entries in list(hooks.items()):
        if not isinstance(entries, list):
            continue
        kept = []
        for entry in entries:
            sub = entry.get("hooks", []) if isinstance(entry, dict) else []
            sub_kept = [
                s for s in sub
                if not (
                    isinstance(s, dict)
                    and s.get("type") == "command"
                    and _matches_our_command(s.get("command", ""), install_root)
                )
            ]
            if sub_kept:
                kept.append({**entry, "hooks": sub_kept})
        if kept:
            hooks[event_name] = kept
        else:
            del hooks[event_name]
    if hooks:
        data["hooks"] = hooks
    elif "hooks" in data:
        del data["hooks"]
    settings_path.write_text(json.dumps(data, indent=2))


def cmd_uninstall(args) -> int:
    try:
        install_root = resolve_install_root()
    except InstallRootNotFound as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not args.yes:
        print("Uninstall digital-brain globally?")
        print("  - remove ~/.claude/skills/{refresh,load}-digital-brain symlinks")
        print("  - remove SessionStart + Stop hook entries from ~/.claude/settings.json")
        print("  - remove ~/.local/bin/digital-brain symlink")
        print("  - remove ~/.digital-brain/install.json")
        print("  Per-project brains NOT removed.")
        resp = input("Continue? (y/N) ").strip().lower()
        if resp not in ("y", "yes"):
            print("Aborted.")
            return 0

    home = Path.home()
    for skill in ("refresh-digital-brain", "load-digital-brain"):
        link = home / ".claude" / "skills" / skill
        if link.is_symlink():
            try:
                target = Path(os.readlink(link)).resolve()
                if target.is_relative_to(install_root.resolve()):
                    link.unlink()
                    print(f"  removed {link}")
            except (ValueError, OSError):
                pass

    _scrub_settings(home / ".claude" / "settings.json", install_root)
    print(f"  scrubbed digital-brain entries from ~/.claude/settings.json")

    console = home / ".local" / "bin" / "digital-brain"
    if console.is_symlink():
        try:
            target = Path(os.readlink(console)).resolve()
            if target.is_relative_to(install_root.resolve()):
                console.unlink()
                print(f"  removed {console}")
        except (ValueError, OSError):
            pass

    install_json = home / ".digital-brain" / "install.json"
    if install_json.exists():
        install_json.unlink()
        try:
            install_json.parent.rmdir()
        except OSError:
            pass
        print(f"  removed {install_json}")

    print(
        f"\nGlobal uninstall complete. Source repo at {install_root} left intact. "
        "Per-project brains not removed — run `digital-brain remove` inside each project first."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
