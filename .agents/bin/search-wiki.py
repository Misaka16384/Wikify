#!/usr/bin/env python3
"""Search for regex patterns or keywords within markdown files (Python replacement for grep).

Usage:
    python .agents/bin/search-wiki.py "query" file1.md file2.md
"""
import argparse
import json
import re
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Search for regex patterns in files.")
    parser.add_argument("query", help="Regex pattern to search for.")
    parser.add_argument("files", nargs="+", help="Files to search.")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="Ignore case.")
    args = parser.parse_args()

    flags = re.IGNORECASE if args.ignore_case else 0
    try:
        pattern = re.compile(args.query, flags)
    except re.error as e:
        print(json.dumps({"error": f"Invalid regex: {e}"}))
        sys.exit(1)

    results = []
    for file_path_str in args.files:
        path = Path(file_path_str)
        if not path.is_file():
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    if pattern.search(line):
                        results.append({
                            "file": str(path),
                            "line": i,
                            "content": line.rstrip("\n")
                        })
        except Exception:
            # Skip unreadable files
            pass

    print(json.dumps({"matches": results}, indent=2))

if __name__ == "__main__":
    main()
