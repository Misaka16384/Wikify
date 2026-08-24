#!/usr/bin/env python3
"""Search for regex patterns or keywords within markdown files (Python replacement for grep).

Usage:
    magi grep "query" file1.md file2.md

On the time limit, and on what it does not cover
------------------------------------------------
Python's ``re`` is a backtracking engine, so a pattern like ``(a+)+$`` costs
exponential time in the length of a *non*-matching subject: measured here, 24
``a`` characters followed by ``!`` already takes about a second, and each
further character roughly doubles it.

There used to be a five-second guard in this file, and it was on the wrong
call. ``re.compile`` is fast; the blow-up happens in ``pattern.search``, which
ran with nothing around it. So the guard could not fire, while its error
message said ``possible ReDoS attack`` — a defence that announces itself and
is not there is worse than none, because it answers the question for the next
reader.

What is here instead is a wall-clock budget, checked between lines. It bounds
the realistic case, which is an expensive pattern over a large corpus, and it
reports partial results with ``truncated`` set rather than pretending it
finished.

**It cannot interrupt a single catastrophic match.** Nothing in the standard
library can: a running ``re`` holds the GIL, so a worker thread cannot be
stopped and ``ThreadPoolExecutor.__exit__`` would block waiting for it. Cutting
that off needs an engine with a native timeout (the third-party ``regex``
module) or a killable subprocess, and neither is worth a dependency for a local
CLI where the pattern comes from the person running it. This is a way to hang
your own terminal, not a way in for anyone else — so it is bounded honestly and
documented, not defended theatrically.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

MAX_RESULTS = 200

#: Wall-clock budget for the whole search. Generous for any real query over a
#: knowledge base; short enough that a pathological one gives the terminal back.
TIME_BUDGET_S = 10.0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi grep", description="Search for regex patterns in files.")
    parser.add_argument("query", help="Regex pattern to search for.")
    parser.add_argument("files", nargs="+", help="Files to search.")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="Ignore case.")
    parser.add_argument("--timeout", type=float, default=TIME_BUDGET_S,
                        help=f"Seconds to spend searching before returning partial "
                             f"results (default: {TIME_BUDGET_S:g}; 0 disables).")
    args = parser.parse_args(argv)

    flags = re.IGNORECASE if args.ignore_case else 0
    try:
        pattern = re.compile(args.query, flags)
    except re.error as e:
        print(json.dumps({"error": f"Invalid regex: {e}"}, ensure_ascii=False))
        sys.exit(1)

    deadline = (time.monotonic() + args.timeout) if args.timeout > 0 else None
    results = []
    truncated = ""

    for file_path_str in args.files:
        path = Path(file_path_str)
        if not path.is_file():
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().replace('\r\n', '\n')
            for i, line in enumerate(content.split('\n'), 1):
                if deadline is not None and time.monotonic() > deadline:
                    truncated = (f"stopped after {args.timeout:g}s in {path} at line {i}; "
                                 "the results below are partial")
                    break
                if pattern.search(line):
                    results.append({
                        "file": str(path),
                        "line": i,
                        "content": line
                    })
                    if len(results) >= MAX_RESULTS:
                        truncated = f"stopped at the {MAX_RESULTS}-match limit"
                        break
            if truncated:
                break
        except (IOError, PermissionError) as e:
            print(f"Warning: skipped {path}: {e}", file=sys.stderr)

    payload = {"matches": results}
    if truncated:
        # Said out loud, in the JSON. A caller that reads "no more matches" out
        # of a list that was cut short draws exactly the wrong conclusion, and
        # this output is a machine contract.
        payload["truncated"] = truncated
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
