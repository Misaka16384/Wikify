"""magi kb — the global knowledge-base registry.

Every workspace can register itself in a user-global registry
(``~/.config/magi/registry.json``). ``magi search`` then federates over
the CURRENT workspace plus every *enabled* registered KB, tagging each
result with its KB name. The current workspace is always searchable;
other KBs are opt-in via their ``enabled`` flag.

Registration is automatic on ``magi index`` (and available manually via
``magi kb register``); automatic registrations default to enabled.
Disable noisy KBs with ``magi kb disable <name>``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from magi.core.workspace import find_workspace_root


def _config_home() -> Path:
    """User-global magi config dir. MAGI_CONFIG_HOME overrides (tests).

    One implementation, in `core.workspace`, because the config loader needs
    the same answer — and when it had its own, `find_config_yaml` looked in
    the real home directory while the registry looked in the isolated one.
    """
    from magi.core.workspace import config_home

    return config_home()


def registry_path() -> Path:
    return _config_home() / "registry.json"


def settings_path() -> Path:
    return _config_home() / "settings.json"


# --------------------------------------------------------------------------
# storage
# --------------------------------------------------------------------------

def _load_json(path: Path) -> dict | None:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_registry() -> dict:
    data = _load_json(registry_path())
    if data is not None and isinstance(data.get("kbs"), dict):
        return data
    return {"kbs": {}}


def save_registry(data: dict) -> None:
    _save_json(registry_path(), data)


def load_settings() -> dict:
    return _load_json(settings_path()) or {}


def save_settings(data: dict) -> None:
    _save_json(settings_path(), data)


# --------------------------------------------------------------------------
# operations (importable API)
# --------------------------------------------------------------------------

def register_kb(path: Path, name: str | None = None, enabled: bool = True, quiet: bool = False) -> str:
    """Idempotent: same resolved path keeps its entry (and enabled flag)."""
    path = path.resolve()
    data = load_registry()
    for existing_name, entry in data["kbs"].items():
        if Path(entry["path"]).resolve() == path:
            return existing_name
    base = name or path.name
    candidate, i = base, 2
    while candidate in data["kbs"]:
        candidate, i = f"{base}-{i}", i + 1
    data["kbs"][candidate] = {
        "path": str(path),
        "enabled": enabled,
        "registered": dt.date.today().isoformat(),
    }
    save_registry(data)
    if not quiet:
        print(f"registered KB '{candidate}' ({path}) — searchable: {enabled}")
    return candidate


def searchable_kbs(exclude: Path | None = None) -> list[tuple[str, Path]]:
    """(name, path) of enabled KBs with an existing index, minus `exclude`."""
    out: list[tuple[str, Path]] = []
    excl = exclude.resolve() if exclude else None
    for name, entry in load_registry()["kbs"].items():
        p = Path(entry["path"])
        if not entry.get("enabled", False):
            continue
        if excl and p.resolve() == excl:
            continue
        if (p / "output" / "index.db").is_file():
            out.append((name, p))
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def cmd_register(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve() if args.path else find_workspace_root()
    if root is None:
        print("no workspace found (run inside a topic directory or pass a path)", file=sys.stderr)
        return 1
    register_kb(root, name=args.name, enabled=not args.disabled)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    data = load_registry()
    current = find_workspace_root()
    rows = []
    for name, entry in sorted(data["kbs"].items()):
        p = Path(entry["path"])
        idx = p / "output" / "index.db"
        rows.append({
            "name": name,
            "path": entry["path"],
            "enabled": bool(entry.get("enabled", False)),
            "indexed": idx.is_file(),
            "exists": p.is_dir(),
            "current": current is not None and p.resolve() == current.resolve(),
        })
    if args.json:
        print(json.dumps({"kbs": rows}, ensure_ascii=False))
        return 0
    if not rows:
        print("no KBs registered ('magi index' auto-registers; or 'magi kb register <path>')")
        return 0
    for r in rows:
        flags = []
        flags.append("searchable" if r["enabled"] else "disabled")
        if not r["exists"]:
            flags.append("MISSING")
        elif not r["indexed"]:
            flags.append("no index — run 'magi index' there")
        if r["current"]:
            flags.append("current")
        print(f"  {r['name']:<24} {r['path']}  [{', '.join(flags)}]")
    return 0


def _set_enabled(name: str, enabled: bool) -> int:
    data = load_registry()
    if name not in data["kbs"]:
        print(f"unknown KB '{name}' — see 'magi kb list'", file=sys.stderr)
        return 1
    data["kbs"][name]["enabled"] = enabled
    save_registry(data)
    print(f"KB '{name}' is now {'searchable' if enabled else 'disabled'}")
    return 0


def cmd_unregister(args: argparse.Namespace) -> int:
    data = load_registry()
    if args.name not in data["kbs"]:
        print(f"unknown KB '{args.name}'", file=sys.stderr)
        return 1
    del data["kbs"][args.name]
    save_registry(data)
    print(f"unregistered '{args.name}' (workspace files untouched)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi kb", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="kb_command", required=True)

    p_reg = sub.add_parser("register", help="Register a workspace in the global registry")
    p_reg.add_argument("path", nargs="?", help="Workspace path (default: discovered from cwd)")
    p_reg.add_argument("--name", help="Registry name (default: directory name)")
    p_reg.add_argument("--disabled", action="store_true", help="Register but keep out of global search")
    p_reg.set_defaults(func=cmd_register)

    p_list = sub.add_parser("list", help="List registered KBs")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_en = sub.add_parser("enable", help="Include a KB in global search")
    p_en.add_argument("name")
    p_en.set_defaults(func=lambda a: _set_enabled(a.name, True))

    p_dis = sub.add_parser("disable", help="Exclude a KB from global search")
    p_dis.add_argument("name")
    p_dis.set_defaults(func=lambda a: _set_enabled(a.name, False))

    p_un = sub.add_parser("unregister", help="Remove a KB from the registry (files untouched)")
    p_un.add_argument("name")
    p_un.set_defaults(func=cmd_unregister)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
