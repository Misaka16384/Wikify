#!/usr/bin/env python3
"""Browse the wiki knowledge graph without writing SQL.

Usage:
    magi graph browse [overview|nodes|links|claims|tags|broken|map]
        [--type T] [--q TEXT] [--node ID] [--status S] [--tags]
        [--limit N] [--json] [--db output/graph.db]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Edge types that carry navigational meaning; has_tag edges duplicate the
# tags table and would drown the links view.
_LINK_TYPES = ("wikilink", "supported_by", "has_claim")

# Unresolved wikilinks are stored as edges whose target_id is the raw link
# text, so a broken link is any edge target missing from nodes.
_BROKEN_TYPES = ("wikilink", "supported_by")

_DEGREE_SQL = ("(SELECT COUNT(*) FROM edges e WHERE e.type = 'wikilink' "
               "AND (e.source_id = n.id OR e.target_id = n.id))")


def open_ro(db_path):
    conn = sqlite3.connect(f"{Path(db_path).as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    # SQLite's built-in LOWER() folds ASCII only, so 'Ω-Background' or 'Néel'
    # would never match a case-insensitive query. All case folding below goes
    # through this Unicode-aware function paired with Python-side casefold().
    conn.create_function(
        "ulower", 1,
        lambda s: s.casefold() if isinstance(s, str) else s,
        deterministic=True,
    )
    return conn


def browse_overview(conn):
    nodes_by_type = {r["type"]: r["n"] for r in conn.execute(
        "SELECT type, COUNT(*) AS n FROM nodes GROUP BY type ORDER BY n DESC")}
    edges_by_type = {r["type"]: r["n"] for r in conn.execute(
        "SELECT type, COUNT(*) AS n FROM edges GROUP BY type ORDER BY n DESC")}
    tags = conn.execute("SELECT COUNT(DISTINCT tag) AS n FROM tags").fetchone()["n"]
    claims_by_status = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM claims GROUP BY status ORDER BY n DESC")}
    placeholders = ",".join("?" * len(_BROKEN_TYPES))
    broken = conn.execute(
        f"SELECT COUNT(*) AS n FROM edges e LEFT JOIN nodes n ON n.id = e.target_id "
        f"WHERE n.id IS NULL AND e.type IN ({placeholders})", _BROKEN_TYPES).fetchone()["n"]
    return {"nodes_by_type": nodes_by_type, "edges_by_type": edges_by_type,
            "tags": tags, "claims_by_status": claims_by_status, "broken_links": broken}


def browse_nodes(conn, node_type=None, q=None, limit=50):
    where, params = [], []
    if node_type:
        where.append("n.type = ?")
        params.append(node_type)
    if q:
        where.append("(ulower(n.title) LIKE ? OR ulower(n.id) LIKE ?)")
        pat = f"%{q.casefold()}%"
        params.extend([pat, pat])
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = conn.execute(
        f"SELECT n.id, n.title, n.type, n.category, n.updated, {_DEGREE_SQL} AS degree "
        f"FROM nodes n {clause} ORDER BY degree DESC, n.id LIMIT ?",
        params + [limit])
    return [dict(r) for r in rows]


def _link_key(text):
    """The graph builder's link normalisation, kept identical on purpose."""
    return text.strip().casefold().replace("_", " ")


def resolve_node_id(conn, text):
    """Resolve a node id, a title, a file stem or an alias to a node id.

    `magi graph build` resolves every [[wikilink]] against all four, so a
    browser that only knew ids would report half of a card's links as broken
    when the graph itself considers them fine. First match wins, matching the
    builder's setdefault over a sorted walk.
    """
    if not text:
        return None
    row = conn.execute("SELECT id FROM nodes WHERE id = ?", (text,)).fetchone()
    if row:
        return row["id"]

    table = {}
    for r in conn.execute("SELECT id, path, title FROM nodes ORDER BY id"):
        stem = (r["path"] or r["id"]).rsplit("/", 1)[-1]
        if stem.endswith(".md"):
            stem = stem[:-3]
        for candidate in (r["title"] or "", stem):
            if candidate:
                table.setdefault(_link_key(candidate), r["id"])
    try:
        for r in conn.execute("SELECT node_id, alias FROM aliases ORDER BY node_id"):
            table.setdefault(_link_key(r["alias"]), r["node_id"])
    except sqlite3.OperationalError:
        pass   # graph.db from before aliases existed; titles and stems still work
    return table.get(_link_key(text))


def _resolve_node(conn, node_id):
    resolved = resolve_node_id(conn, node_id)
    if resolved is None:
        return None
    row = conn.execute(
        "SELECT id, title, type FROM nodes WHERE id = ?", (resolved,)).fetchone()
    return dict(row) if row else None


def browse_links(conn, node_id):
    node = _resolve_node(conn, node_id)
    if node is None:
        return {"node": None, "outgoing": [], "incoming": []}
    placeholders = ",".join("?" * len(_LINK_TYPES))
    outgoing = [dict(r) for r in conn.execute(
        f"SELECT e.target_id, n.title, e.type FROM edges e "
        f"LEFT JOIN nodes n ON n.id = e.target_id "
        f"WHERE e.source_id = ? AND e.type IN ({placeholders}) "
        f"ORDER BY e.type, e.target_id", (node["id"], *_LINK_TYPES))]
    incoming = [dict(r) for r in conn.execute(
        f"SELECT e.source_id, n.title, e.type FROM edges e "
        f"LEFT JOIN nodes n ON n.id = e.source_id "
        f"WHERE e.target_id = ? AND e.type IN ({placeholders}) "
        f"ORDER BY e.type, e.source_id", (node["id"], *_LINK_TYPES))]
    return {"node": node, "outgoing": outgoing, "incoming": incoming}


def browse_hubs(conn, limit=20):
    rows = conn.execute(
        f"SELECT n.id, n.title, n.type, {_DEGREE_SQL} AS degree "
        f"FROM nodes n ORDER BY degree DESC, n.id LIMIT ?", (limit,))
    return [dict(r) for r in rows]


def browse_claims(conn, status=None, q=None, limit=50):
    where, params = [], []
    if status:
        where.append("status = ?")
        params.append(status)
    if q:
        where.append("ulower(text) LIKE ?")
        params.append(f"%{q.casefold()}%")
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = conn.execute(
        f"SELECT id, doc_id, status, text FROM claims {clause} ORDER BY id LIMIT ?",
        params + [limit])
    return [dict(r) for r in rows]


def browse_tags(conn, q=None, limit=100):
    where, params = "", []
    if q:
        where = "WHERE ulower(tag) LIKE ?"
        params.append(f"%{q.casefold()}%")
    rows = conn.execute(
        f"SELECT tag, COUNT(*) AS count FROM tags {where} "
        f"GROUP BY tag ORDER BY count DESC, tag LIMIT ?", params + [limit])
    return [dict(r) for r in rows]


def browse_broken(conn, limit=200):
    placeholders = ",".join("?" * len(_BROKEN_TYPES))
    rows = conn.execute(
        f"SELECT e.source_id, s.title AS source_title, e.target_id AS target_text, e.type "
        f"FROM edges e LEFT JOIN nodes t ON t.id = e.target_id "
        f"LEFT JOIN nodes s ON s.id = e.source_id "
        f"WHERE t.id IS NULL AND e.type IN ({placeholders}) "
        f"ORDER BY e.source_id, e.target_id LIMIT ?", (*_BROKEN_TYPES, limit))
    return [dict(r) for r in rows]


def browse_map(conn, include_tags=False, limit=800):
    """Whole-graph snapshot for the interactive map view.

    Every non-tag node is included (tag nodes too when include_tags), with
    wikilink/has_claim/supported_by edges between them. Unresolved wikilink
    and supported_by targets become synthetic "ghost" nodes, mirroring how
    Obsidian renders links to pages that do not exist yet.
    """
    # node_types covers ALL rows so an edge to an excluded real node (e.g. a
    # tag while include_tags is off) is dropped instead of ghosted.
    node_types = {}
    nodes = {}
    for r in conn.execute("SELECT id, title, type FROM nodes"):
        node_types[r["id"]] = r["type"]
        if include_tags or r["type"] != "tag":
            nodes[r["id"]] = {"id": r["id"], "title": r["title"],
                              "type": r["type"], "degree": 0}

    edges = []
    placeholders = ",".join("?" * len(_LINK_TYPES))
    for r in conn.execute(
            f"SELECT source_id, target_id, type FROM edges "
            f"WHERE type IN ({placeholders}) "
            f"ORDER BY source_id, target_id, type", _LINK_TYPES):
        src, tgt, etype = r["source_id"], r["target_id"], r["type"]
        if src not in nodes:
            continue
        if tgt not in nodes:
            if tgt in node_types or etype not in _BROKEN_TYPES:
                continue
            nodes[tgt] = {"id": tgt, "title": tgt, "type": "ghost", "degree": 0}
        edges.append({"source": src, "target": tgt, "type": etype})
        for nid in (src, tgt):
            # Tag degree counts has_tag edges only (handled below).
            if nodes[nid]["type"] != "tag":
                nodes[nid]["degree"] += 1

    if include_tags:
        for r in conn.execute(
                "SELECT source_id, target_id FROM edges WHERE type = 'has_tag' "
                "ORDER BY source_id, target_id"):
            src, tgt = r["source_id"], r["target_id"]
            if src not in nodes or tgt not in nodes:
                continue
            edges.append({"source": src, "target": tgt, "type": "has_tag"})
            for nid in (src, tgt):
                if nodes[nid]["type"] == "tag":
                    nodes[nid]["degree"] += 1

    # Rank by degree; ghosts lose ties to real nodes so they drop first.
    def rank(n):
        return (-n["degree"], n["type"] == "ghost", n["id"])

    truncated = len(nodes) > limit
    if truncated:
        kept = {n["id"] for n in sorted(nodes.values(), key=rank)[:limit]}
        nodes = {nid: n for nid, n in nodes.items() if nid in kept}
        edges = [e for e in edges
                 if e["source"] in nodes and e["target"] in nodes]

    return {"nodes": sorted(nodes.values(), key=rank), "edges": edges,
            "truncated": truncated}


def _print_table(rows, columns, widths):
    header = "  ".join(name.ljust(w) for name, w in zip(columns, widths))
    print(header)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(str(row.get(c) if row.get(c) is not None else "-").ljust(w)
                        for c, w in zip(columns, widths)))


def _print_human(view, results):
    if view == "overview":
        print("nodes:")
        for t, n in results["nodes_by_type"].items():
            print(f"  {t:<20} {n}")
        print("edges:")
        for t, n in results["edges_by_type"].items():
            print(f"  {t:<20} {n}")
        print(f"tags: {results['tags']} distinct")
        print("claims:")
        for s, n in results["claims_by_status"].items():
            print(f"  {s:<20} {n}")
        print(f"broken links: {results['broken_links']}")
    elif view in ("nodes", "hubs"):
        _print_table(results, ["degree", "type", "id", "title"], [6, 10, 44, 40])
    elif view == "links":
        node = results["node"]
        if node is None:
            print("node not found")
            return
        print(f"{node['title']}  ({node['id']}, {node['type']})")
        print(f"outgoing ({len(results['outgoing'])}):")
        for e in results["outgoing"]:
            title = e["title"] if e["title"] is not None else "[BROKEN]"
            print(f"  -> {e['target_id']:<44} {title}  [{e['type']}]")
        print(f"incoming ({len(results['incoming'])}):")
        for e in results["incoming"]:
            print(f"  <- {e['source_id']:<44} {e['title']}  [{e['type']}]")
    elif view == "claims":
        for c in results:
            text = c["text"] if len(c["text"]) <= 100 else c["text"][:97] + "..."
            print(f"{c['id']:<14} {c['status']:<12} {c['doc_id']}")
            print(f"    {text}")
    elif view == "tags":
        _print_table(results, ["count", "tag"], [6, 40])
    elif view == "broken":
        for r in results:
            print(f"{r['source_id']} ({r['source_title']}) -> [[{r['target_text']}]]  [{r['type']}]")
    elif view == "map":
        node_counts, edge_counts = {}, {}
        for n in results["nodes"]:
            node_counts[n["type"]] = node_counts.get(n["type"], 0) + 1
        for e in results["edges"]:
            edge_counts[e["type"]] = edge_counts.get(e["type"], 0) + 1
        print(f"nodes: {len(results['nodes'])}")
        for t in sorted(node_counts, key=lambda t: (-node_counts[t], t)):
            print(f"  {t:<20} {node_counts[t]}")
        print(f"edges: {len(results['edges'])}")
        for t in sorted(edge_counts, key=lambda t: (-edge_counts[t], t)):
            print(f"  {t:<20} {edge_counts[t]}")
        if results["truncated"]:
            print("truncated: node limit reached (raise --limit to include more)")
        print("hint: use --json to emit the full node/edge lists")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="magi graph browse",
        description="Browse the knowledge graph without SQL.")
    parser.add_argument("view", nargs="?", default="overview",
                        choices=["overview", "nodes", "links", "claims", "tags", "broken", "map"],
                        help="What to list (default: overview).")
    parser.add_argument("--type", dest="node_type", default=None,
                        help="nodes: filter by node type.")
    parser.add_argument("--q", default=None,
                        help="Case-insensitive substring filter (nodes: title/id; "
                             "claims: text; tags: tag).")
    parser.add_argument("--node", default=None,
                        help="links: node id or exact title.")
    parser.add_argument("--status", default=None, help="claims: filter by status.")
    parser.add_argument("--tags", action="store_true",
                        help="map: include tag nodes and has_tag edges.")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to return.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
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
            return 1
        db_path = root / "output" / "graph.db"
    if not db_path.exists():
        print(json.dumps({"error": f"Database not found at {db_path}. Please run 'magi graph build' first."},
                         ensure_ascii=False))
        return 1

    view = args.view
    conn = None
    try:
        conn = open_ro(db_path)
        if view == "overview":
            results = browse_overview(conn)
        elif view == "nodes":
            results = browse_nodes(conn, node_type=args.node_type, q=args.q,
                                   limit=args.limit or 50)
        elif view == "links":
            if args.node:
                results = browse_links(conn, args.node)
            else:
                # Without a node to inspect, show the busiest ones instead.
                view = "hubs"
                results = browse_hubs(conn, limit=args.limit or 20)
        elif view == "claims":
            results = browse_claims(conn, status=args.status, q=args.q,
                                    limit=args.limit or 50)
        elif view == "tags":
            results = browse_tags(conn, q=args.q, limit=args.limit or 100)
        elif view == "map":
            results = browse_map(conn, include_tags=args.tags,
                                 limit=args.limit or 800)
        else:  # broken
            results = browse_broken(conn, limit=args.limit or 200)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1
    finally:
        if conn is not None:
            conn.close()

    if args.json:
        print(json.dumps({"view": view, "results": results}, indent=2, ensure_ascii=False))
    else:
        _print_human(view, results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
