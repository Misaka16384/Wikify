"""magi migrate — upgrade a pre-magi (Wikify-era) workspace in place.

Non-destructive: existing content (raw/, wiki/, config.md, log.md) is
never touched. The command only ADDS what the magi era introduced —
CLAUDE.md / AGENTS.md (agent entry protocol), config.yaml (workspace
config), scratch/ — then rebuilds the graph and _index tables, and
prints the remaining manual steps (pm init, index).

Old installations copied skills/ + bin/ into agent directories
(~/.claude, .agents); those copies are obsolete and should be deleted —
see the README migration section.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from magi.core.wiki_common import parse_frontmatter
from magi.core.workspace import find_workspace_root, is_hub_root


def _migrate_hub(hub: Path) -> int:
    """Hub mode: migrate every active topic under <hub>/topics/."""
    topics = sorted(
        d for d in (hub / "topics").iterdir()
        if d.is_dir() and d.name != ".archive" and ((d / "wiki").is_dir() or (d / "raw").is_dir())
    )
    if not topics:
        print(f"Hub detected at {hub} but no topics found under topics/.")
        return 0
    print(f"Hub detected at {hub} — migrating {len(topics)} topic(s):\n")
    failures = 0
    for t in topics:
        rc = _migrate_topic(t)
        failures += 1 if rc else 0
        print()
    print(f"Hub migration complete: {len(topics) - failures}/{len(topics)} topics migrated.")
    print("Next: magi pm init   # provision beads once, at this hub root")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi migrate", description=__doc__)
    parser.add_argument("path", nargs="?", help="Workspace or hub to migrate (default: discovered from cwd)")
    args = parser.parse_args(argv)

    base = Path(args.path).resolve() if args.path else Path.cwd()
    if is_hub_root(base):
        return _migrate_hub(base)

    root = find_workspace_root(args.path) if args.path else find_workspace_root()
    if root is None:
        # Legacy workspaces predate the marker-file requirement: accept a
        # bare wiki/ or raw/ dir at the given path (or cwd) directly.
        if (base / "wiki").is_dir() or (base / "raw").is_dir():
            root = base
        else:
            print("No workspace found here. Run inside a topic directory "
                  "(a folder containing wiki/ or raw/), at a hub root, or pass a path.",
                  file=sys.stderr)
            return 1

    rc = _migrate_topic(root)
    if rc == 0:
        print("\nRecommended next steps:")
        print("  magi pm init        # provision beads at the hub root (work-state tracking)")
        print("  magi index          # build the hybrid retrieval index (needs Ollama for vectors)")
        print("  magi sync           # check the sync ratio")
        print("\nIf you installed the old Wikify skills by copying skills/+bin/ into "
              "~/.claude or .agents/, remove them: magi setup --remove-legacy")
    return rc


def _migrate_topic(root: Path) -> int:
    # Carry the legacy identity into the new scaffolding.
    name, scope = root.name, "A topic wiki."
    config_md = root / "config.md"
    if config_md.is_file():
        fm = parse_frontmatter(config_md.read_text(encoding="utf-8", errors="replace"))
        name = str(fm.get("title") or name)
        scope = str(fm.get("scope") or scope)

    missing = [f for f in ("CLAUDE.md", "AGENTS.md", "config.yaml") if not (root / f).is_file()]
    print(f"Migrating workspace: {root}")
    print(f"  identity: {name!r} — {scope!r}")
    if missing:
        print(f"  adding: {', '.join(missing)} (+ scratch/, missing _index.md files)")
    else:
        print("  scaffolding already present — refreshing indexes only")

    # init is non-destructive without --force: it only creates what is absent.
    from magi.hub.init_workspace import main as init_main

    rc = init_main(["--topic-dir", str(root), "--name", name, "--scope", scope])
    if rc not in (0, None):
        print("warning: scaffolding step reported an error; continuing", file=sys.stderr)

    for step in (["graph", "build", str(root)], ["wiki", "reindex", str(root)]):
        proc = subprocess.run([sys.executable, "-m", "magi", *step],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        status = "ok" if proc.returncode == 0 else f"FAILED ({proc.stderr.strip()[-200:]})"
        print(f"  magi {' '.join(step[:2])}: {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
