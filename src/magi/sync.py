"""magi sync — workspace onboarding and sync ratio.

M0 stub: reports workspace identity only. M1 implements the full sync
ratio (index freshness + Beads queue health + backlog + claim coverage)
and the three-core (Melchior/Balthasar/Casper) status readout.
"""

from __future__ import annotations

import argparse
import json

from magi.core.workspace import find_hub_root, find_workspace_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi sync", description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    workspace = find_workspace_root()
    hub = find_hub_root()
    payload = {
        "workspace": str(workspace) if workspace else None,
        "hub": str(hub) if hub else None,
        "sync_ratio": None,
        "note": "M0 stub — full sync ratio lands in M1",
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print("MAGI SYSTEM — M0 stub")
        print(f"  workspace: {payload['workspace'] or '(none found — run magi init)'}")
        print(f"  hub:       {payload['hub'] or '(none found)'}")
    return 0
