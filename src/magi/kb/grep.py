#!/usr/bin/env python3
"""Search for regex patterns or keywords within markdown files (Python replacement for grep).

Usage:
    magi grep "query" file1.md file2.md
"""
import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

MAX_RESULTS = 200

def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi grep", description="Search for regex patterns in files.")
    parser.add_argument("query", help="Regex pattern to search for.")
    parser.add_argument("files", nargs="+", help="Files to search.")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="Ignore case.")
    args = parser.parse_args(argv)

    flags = re.IGNORECASE if args.ignore_case else 0
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(re.compile, args.query, flags)
            pattern = future.result(timeout=5)
    except TimeoutError:
        print(json.dumps({"error": "Regex compilation timed out (possible ReDoS attack)"}))
        sys.exit(1)
    except re.error as e:
        print(json.dumps({"error": f"Invalid regex: {e}"}))
        sys.exit(1)

    results = []
    for file_path_str in args.files:
        path = Path(file_path_str)
        if not path.is_file():
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read().replace('\r\n', '\n')
            for i, line in enumerate(content.split('\n'), 1):
                if pattern.search(line):
                    results.append({
                        "file": str(path),
                        "line": i,
                        "content": line
                    })
                    if len(results) >= MAX_RESULTS:
                        break
            if len(results) >= MAX_RESULTS:
                break
        except (IOError, PermissionError) as e:
            print(f"Warning: skipped {path}: {e}", file=sys.stderr)

    print(json.dumps({"matches": results}, indent=2))

if __name__ == "__main__":
    sys.exit(main())
