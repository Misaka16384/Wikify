"""magi pm — Beads (bd) bridge: work/intent state (the Balthasar core).

MAGI does not implement task tracking. Beads owns the work graph; this
module only (1) provisions a hub-level beads database with research issue
types, (2) exposes a JSON status summary for `magi sync`, and (3) syncs
the deterministic compile backlog into bd issues. Agents interact with
`bd` directly (see `bd prime` / `bd --help`); skills teach when.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from magi.core.workspace import find_hub_root, find_workspace_root

RESEARCH_TYPES = ["question", "survey", "derivation", "computation", "experiment", "review"]

_TYPES_BLOCK = (
    "\n# MAGI research issue types (added by 'magi pm init')\n"
    "types:\n  custom:\n" + "".join(f"    - {t}\n" for t in RESEARCH_TYPES)
)


def bd_available() -> bool:
    return shutil.which("bd") is not None


def _run_bd(args: list[str], cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bd", *args], cwd=cwd, capture_output=True, text=True,
        timeout=timeout, encoding="utf-8", errors="replace",
    )


def find_beads_root(start: Path | None = None) -> Path | None:
    """Nearest ancestor (of start or cwd) containing a workspace .beads db.

    A workspace database has ``.beads/metadata.json`` (written by ``bd
    init``); this distinguishes it from bd's user-level data directory
    ``~/.beads`` (eventsData etc.), which must not match.
    """
    current = (start or Path.cwd()).resolve()
    for _ in range(30):
        if (current / ".beads" / "metadata.json").is_file():
            return current
        if current.parent == current:
            return None
        current = current.parent
    return None


def bd_status_summary(cwd: Path) -> dict | None:
    """Parse `bd status --json` summary; None when bd/db unavailable."""
    if not bd_available():
        return None
    try:
        proc = _run_bd(["status", "--json"], cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout).get("summary")
    except json.JSONDecodeError:
        return None


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve() if args.path else (find_hub_root() or find_workspace_root() or Path.cwd())
    if not bd_available():
        print("bd (Beads) is not installed. See https://github.com/gastownhall/beads — "
              "on Windows: irm https://raw.githubusercontent.com/gastownhall/beads/main/install.ps1 | iex",
              file=sys.stderr)
        return 1

    beads_dir = root / ".beads"
    if (beads_dir / "metadata.json").is_file():
        print(f"beads already initialized at {root}")
    else:
        init_args = ["init"]
        if args.prefix:
            init_args += ["--prefix", args.prefix]
        proc = _run_bd(init_args, cwd=root, timeout=300)
        sys.stdout.write(proc.stdout[-800:])
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr[-800:])
            return proc.returncode

    config = beads_dir / "config.yaml"
    text = config.read_text(encoding="utf-8") if config.is_file() else ""
    if "types:" in text:
        print("custom types already configured in .beads/config.yaml")
    else:
        with open(config, "a", encoding="utf-8") as f:
            f.write(_TYPES_BLOCK)
        print(f"research issue types configured: {', '.join(RESEARCH_TYPES)}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = find_beads_root()
    payload: dict = {
        "bd_installed": bd_available(),
        "beads_root": str(root) if root else None,
        "summary": None,
    }
    if root:
        payload["summary"] = bd_status_summary(root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if not payload["bd_installed"]:
            print("bd not installed")
        elif not root:
            print("no beads database found (run 'magi pm init' at the hub root)")
        else:
            s = payload["summary"] or {}
            print(f"beads @ {root}: {s.get('ready_issues', '?')} ready, "
                  f"{s.get('in_progress_issues', '?')} in progress, "
                  f"{s.get('blocked_issues', '?')} blocked, "
                  f"{s.get('open_issues', '?')} open")
    return 0


def cmd_backlog_sync(args: argparse.Namespace) -> int:
    """Create a bd issue (type: task, label: magi-compile) per uncompiled raw source."""
    topic = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1
    beads_root = find_beads_root(topic)
    if beads_root is None or not bd_available():
        print("bd/beads database not available (run 'magi pm init' first)", file=sys.stderr)
        return 1

    from magi.kb.detect_uncompiled import find_uncompiled

    uncompiled = find_uncompiled(topic)
    if not uncompiled:
        print("backlog clean: no uncompiled sources")
        return 0

    # Idempotence: skip sources whose issue title already exists. --all
    # includes CLOSED issues, so a wontfix'd compile task stays dead
    # instead of resurrecting on every backlog-sync.
    existing = ""
    proc = _run_bd(["list", "--json", "--all", "--label", "magi-compile", "--limit", "1000"], cwd=beads_root)
    if proc.returncode == 0:
        existing = proc.stdout

    created = skipped = 0
    for rel in uncompiled:
        title = f"Compile raw source: {rel}"
        if title in existing:
            skipped += 1
            continue
        proc = _run_bd(
            ["create", "-t", "task", title, "--label", "magi-compile",
             "-d", f"Run the wiki_compile skill for {rel} in {topic}"],
            cwd=beads_root,
        )
        if proc.returncode == 0:
            created += 1
        else:
            print(f"warning: bd create failed for {rel}: {proc.stderr[-200:]}", file=sys.stderr)
    print(f"backlog sync: {created} created, {skipped} already tracked")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi pm", description=__doc__)
    sub = parser.add_subparsers(dest="pm_command", required=True)

    p_init = sub.add_parser("init", help="Initialize beads (hub-level) with research issue types")
    p_init.add_argument("path", nargs="?", help="Directory for the beads db (default: hub root from cwd)")
    p_init.add_argument("--prefix", help="Issue id prefix (default: bd auto-detects)")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="Beads availability + issue counts")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_backlog = sub.add_parser("backlog-sync", help="Create bd issues for uncompiled raw sources")
    p_backlog.add_argument("--topic-dir", help="Topic workspace (default: discovered from cwd)")
    p_backlog.set_defaults(func=cmd_backlog_sync)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
