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
    parser.add_argument("--db", default="output/graph.db", help="Path to the SQLite database (default: output/graph.db).")
    args = parser.parse_args(argv)

    db_path = Path(args.db).resolve()
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
