"""Run every mutation and require its guard to go red.

    python -m tests.mutations              # all
    python -m tests.mutations layout cli   # only those areas
    python -m tests.mutations --list       # what is covered

Refuses to start on a dirty working tree. It edits source files and restores
them in a `finally`, and an interrupted run must never be mistaken for
somebody's unsaved work — so the safe state is the one it insists on before
touching anything.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .cases import CASES

ROOT = Path(__file__).resolve().parents[2]


def _dirty() -> list:
    done = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                          capture_output=True, text=True)
    if done.returncode != 0:
        return []
    return [line for line in done.stdout.splitlines()
            if line[:2] != "??" and line.strip()]


def _run_target(target: str) -> subprocess.CompletedProcess:
    head, _, expr = target.partition(" -k ")
    argv = [sys.executable, "-m", "pytest", "-q", "--no-header",
            "-p", "no:cacheprovider", head]
    if expr:
        argv += ["-k", expr]
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)


def main(argv: list | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--list" in argv:
        for case in CASES:
            print(f"  {case.area:<10} {case.label}")
        print(f"\n{len(CASES)} case(s) across "
              f"{len({c.area for c in CASES})} area(s)")
        return 0

    areas = [a for a in argv if not a.startswith("-")]
    cases = [c for c in CASES if not areas or c.area in areas]
    if not cases:
        print(f"no cases for {areas} — try --list", file=sys.stderr)
        return 2

    dirty = _dirty()
    if dirty:
        print("refusing to run with uncommitted changes:", file=sys.stderr)
        for line in dirty[:10]:
            print(f"  {line}", file=sys.stderr)
        print("\nThis rewrites source files and restores them afterwards; a run "
              "interrupted here would be indistinguishable from your own work.",
              file=sys.stderr)
        return 2

    missed = []
    for case in cases:
        path = ROOT / case.path
        original = path.read_text(encoding="utf-8")
        if case.fixed not in original:
            print(f"  ANCHOR?  [{case.area}] {case.label}")
            missed.append(case)
            continue
        path.write_text(original.replace(case.fixed, case.broken, 1), encoding="utf-8")
        try:
            done = _run_target(case.target)
        finally:
            path.write_text(original, encoding="utf-8")
        # 5 is "nothing collected", which is the skip-shaped false green this
        # exists to rule out: a guard that stops running is not a guard.
        caught = done.returncode not in (0, 5)
        print(("  caught   " if caught else "  MISSED   ")
              + f"[{case.area}] {case.label}")
        if not caught:
            missed.append(case)
            print(f"           rc={done.returncode} {done.stdout.strip()[-160:]}")

    still_dirty = _dirty()
    if still_dirty:
        print("\nWARNING: the tree did not come back clean:", file=sys.stderr)
        for line in still_dirty[:10]:
            print(f"  {line}", file=sys.stderr)
        return 3

    print(f"\n{len(cases) - len(missed)}/{len(cases)} guards bite")
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
