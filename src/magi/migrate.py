"""magi migrate — one-time migration of a pre-magi (Wikify) workspace.

M0 stub: validates that the target looks like a legacy workspace and
reports what a migration will do. Implemented incrementally as workspace
formats actually change (M1: beads init; M2: retrieval index).
"""

from __future__ import annotations

import argparse

from magi.core.workspace import find_workspace_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi migrate", description=__doc__)
    parser.add_argument("path", nargs="?", help="Workspace to migrate (default: discovered from cwd)")
    args = parser.parse_args(argv)

    root = find_workspace_root(args.path) if args.path else find_workspace_root()
    if root is None:
        print("No workspace found. Nothing to migrate.")
        return 1
    print(f"Workspace detected: {root}")
    print("M0 stub — nothing to migrate yet. Future steps: beads init (M1), retrieval index (M2).")
    return 0
