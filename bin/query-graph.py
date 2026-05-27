#!/usr/bin/env python3
"""Execute SQL queries against the wiki SQLite graph database.

Usage:
    python .agents/bin/query-graph.py "SELECT * FROM nodes LIMIT 5" [--db output/graph.db]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Query the wiki knowledge graph.")
    parser.add_argument("query", help="SQL query to execute.")
    parser.add_argument("--db", default="output/graph.db", help="Path to the SQLite database (default: output/graph.db).")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"Database not found at {db_path}. Please run 'python .agents/bin/llm-wiki.py graph' first."}))
        sys.exit(1)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(args.query)
        rows = [dict(row) for row in cursor.fetchall()]
        print(json.dumps({"results": rows}, indent=2))
        conn.close()
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
