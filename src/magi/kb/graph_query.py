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
    parser = argparse.ArgumentParser(
        prog="magi graph query", description="Query the wiki knowledge graph.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "schema:\n"
            "  nodes(id, path, title, type, category, summary, created, updated)\n"
            "  edges(source_id, target_id, type: wikilink|has_tag|has_claim|supported_by)\n"
            "  tags(node_id, tag)\n"
            "  aliases(node_id, alias)\n"
            "  claims(id, doc_id, text, status)\n"
            "  evidence(claim_id, source_type, source, quote)\n"
            "\n"
            "example:\n"
            "  magi graph query \"SELECT n.title FROM nodes n JOIN edges e "
            "ON n.id = e.target_id WHERE e.type = 'wikilink' LIMIT 10\"\n"
        ))
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
                                       "directory or pass --db <path>."}, ensure_ascii=False))
            sys.exit(1)
        db_path = root / "output" / "graph.db"
    if not db_path.exists():
        print(json.dumps({"error": f"Database not found at {db_path}. Please run 'magi graph build' first."},
                         ensure_ascii=False))
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
        print(json.dumps({"results": rows}, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    sys.exit(main())
