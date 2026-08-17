#!/usr/bin/env python3
"""Execute SQL queries against the wiki SQLite graph database.

Usage:
    magi graph query "SELECT * FROM nodes LIMIT 5" [--db output/graph.db]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi graph query", description="Query the wiki knowledge graph.")
    parser.add_argument("query", help="SQL query to execute.")
    parser.add_argument("--db", default=None,
                        help="Path to the SQLite database (default: <workspace>/output/graph.db, "
                             "workspace discovered by walking up from cwd).")
    args = parser.parse_args(argv)

    if args.db:
        db_path = Path(args.db).resolve()
    else:
        # Anchor the default to the discovered workspace, not the cwd:
        # sessions often start at the hub root, and a stale graph.db at
        # the wrong level must never be silently queried.
        from magi.core.workspace import find_workspace_root

        root = find_workspace_root()
        if root is None:
            print(json.dumps({"error": "No workspace found from cwd. Run inside a topic "
                                       "directory or pass --db <path>."}))
            sys.exit(1)
        db_path = root / "output" / "graph.db"
    if not db_path.exists():
        print(json.dumps({"error": f"Database not found at {db_path}. Please run 'magi graph build' first."}))
        sys.exit(1)

    try:
        # Open database in read-only mode to prevent accidental writes
        conn = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA query_only = ON")

        # SQL injection protection: allow SELECT, WITH (for recursive CTEs)
        query_stripped = args.query.strip()
        query_upper = query_stripped.upper()
        if not (query_upper.startswith("SELECT") or query_upper.startswith("WITH") or query_upper.startswith("PRAGMA")):
            print(json.dumps({"error": "Only SELECT, WITH, or PRAGMA queries are allowed"}))
            sys.exit(1)

        cursor.execute(query_stripped)
        rows = [dict(row) for row in cursor.fetchall()]
        print(json.dumps({"results": rows}, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    sys.exit(main())
