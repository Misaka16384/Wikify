"""magi each — run one command in every topic of the hub.

Most maintenance is per-workspace (`magi index`, `magi lint --fix`,
`magi skills install`), which turns routine upkeep of a multi-topic hub into
a cd-loop. This runs the same command in each active topic and reports one
summary, instead of adding an `--all` flag to a dozen subcommands.

    magi each index
    magi each lint --fix
    magi each skills install --host codex
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from magi.core.workspace import find_hub_root, is_topic_root

USAGE = """usage: magi each [--stop-on-error] [--json] <command> [args...]

Runs `magi <command> [args...]` in every active topic of the hub.

  magi each index                      # (re)build every topic's retrieval index
  magi each lint --fix                 # structural pass over the whole hub
  magi each skills install --host codex
  magi each sync --fix                 # bring every topic back to green
"""


def active_topics(hub: Path) -> List[Path]:
    """Registered active topics, falling back to what is on disk."""
    registry = hub / "wikis.json"
    out: List[Path] = []
    if registry.is_file():
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
            for slug, entry in (data.get("wikis") or {}).items():
                if not isinstance(entry, dict) or entry.get("status") == "archived":
                    continue
                path = hub / (entry.get("path") or f"topics/{slug}")
                if is_topic_root(path):
                    out.append(path)
        except (OSError, ValueError):
            out = []
    if out:
        return sorted(set(out))

    topics_dir = hub / "topics"
    if topics_dir.is_dir():
        out = [d for d in sorted(topics_dir.iterdir())
               if d.is_dir() and d.name != ".archive" and is_topic_root(d)]
    return out


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    stop_on_error = False
    as_json = False
    while args and args[0] in ("--stop-on-error", "--json", "-h", "--help"):
        flag = args.pop(0)
        if flag in ("-h", "--help"):
            print(USAGE)
            return 0
        if flag == "--stop-on-error":
            stop_on_error = True
        else:
            as_json = True

    if not args:
        print(USAGE, file=sys.stderr)
        return 2

    hub = find_hub_root()
    if hub is None:
        print("no hub found from here. 'magi each' runs a command across a hub's "
              "topics — cd to the hub root (the directory with wikis.json).",
              file=sys.stderr)
        return 1

    topics = active_topics(hub)
    if not topics:
        print(f"hub at {hub} has no active topics.", file=sys.stderr)
        return 1

    label = " ".join(args)
    if not as_json:
        print(f"magi each: '{label}' across {len(topics)} topic(s) in {hub}\n")

    results = []
    failed = 0
    for topic in topics:
        proc = subprocess.run([sys.executable, "-m", "magi", *args], cwd=str(topic),
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        ok = proc.returncode == 0
        failed += 0 if ok else 1
        tail = (proc.stdout or proc.stderr or "").strip().splitlines()
        results.append({"topic": topic.name, "path": str(topic), "ok": ok,
                        "returncode": proc.returncode,
                        "output": (proc.stdout or "") + (proc.stderr or "")})
        if not as_json:
            mark = "+" if ok else "!"
            print(f"[{mark}] {topic.name}")
            for line in tail[-3:]:
                print(f"      {line}")
            if not ok and proc.stderr.strip():
                print(f"      exit {proc.returncode}")
            print()
        if not ok and stop_on_error:
            break

    if as_json:
        print(json.dumps({"hub": str(hub), "command": args,
                          "topics": len(topics), "failed": failed,
                          "results": results}, ensure_ascii=False))
    else:
        done = len(results) - failed
        print(f"{done}/{len(topics)} ok" + (f", {failed} failed" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
