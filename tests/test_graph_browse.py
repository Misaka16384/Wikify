"""Tests for magi graph browse (SQL-free graph views)."""

from __future__ import annotations

import json
import sqlite3

import pytest

from magi.kb.graph_browse import (
    browse_broken,
    browse_claims,
    browse_hubs,
    browse_links,
    browse_map,
    browse_nodes,
    browse_overview,
    browse_tags,
    main,
    open_ro,
)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "graph.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE nodes(id TEXT PRIMARY KEY, path TEXT, title TEXT, type TEXT, category TEXT, summary TEXT, created TEXT, updated TEXT);
        CREATE TABLE edges(source_id TEXT, target_id TEXT, type TEXT, UNIQUE(source_id, target_id, type));
        CREATE TABLE tags(node_id TEXT, tag TEXT);
        CREATE TABLE aliases(node_id TEXT, alias TEXT);
        CREATE TABLE claims(id TEXT PRIMARY KEY, doc_id TEXT, text TEXT, status TEXT);
        CREATE TABLE evidence(claim_id TEXT, source_type TEXT, source TEXT, quote TEXT);

        INSERT INTO nodes VALUES('wiki/concepts/alpha', 'wiki/concepts/alpha.md', 'Alpha Concept', 'concept', NULL, 'A', '2026-08-18', '2026-08-18');
        INSERT INTO nodes VALUES('wiki/concepts/beta', 'wiki/concepts/beta.md', 'Beta Concept', 'concept', NULL, 'B', '2026-08-18', '2026-08-18');
        INSERT INTO nodes VALUES('wiki/references/paper-one', 'wiki/references/paper-one.md', 'Paper One', 'reference', NULL, 'P', '2026-08-18', '2026-08-18');
        INSERT INTO nodes VALUES('claim:abc', NULL, 'Alpha scales linearly', 'claim', NULL, NULL, '2026-08-18', '2026-08-18');

        INSERT INTO edges VALUES('wiki/concepts/alpha', 'wiki/concepts/beta', 'wikilink');
        INSERT INTO edges VALUES('wiki/references/paper-one', 'wiki/concepts/alpha', 'wikilink');
        INSERT INTO edges VALUES('wiki/concepts/alpha', 'Nonexistent Page', 'wikilink');
        INSERT INTO edges VALUES('wiki/concepts/alpha', 'tag:physics', 'has_tag');
        INSERT INTO edges VALUES('wiki/references/paper-one', 'claim:abc', 'has_claim');
        INSERT INTO edges VALUES('claim:abc', 'wiki/references/paper-one', 'supported_by');

        INSERT INTO tags VALUES('wiki/concepts/alpha', 'physics');
        INSERT INTO tags VALUES('wiki/concepts/beta', 'physics');
        INSERT INTO tags VALUES('wiki/references/paper-one', 'methods');

        INSERT INTO claims VALUES('claim:abc', 'wiki/references/paper-one.md', 'Alpha scales linearly with beta.', 'verified');
        INSERT INTO evidence VALUES('claim:abc', 'local_wiki', 'wiki/references/paper-one.md', 'quote');
        """
    )
    conn.close()
    return path


@pytest.fixture
def conn(db_path):
    c = open_ro(db_path)
    yield c
    c.close()


def test_open_ro_rejects_writes(conn):
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO tags VALUES('x', 'y')")


def test_overview(conn):
    ov = browse_overview(conn)
    assert ov["nodes_by_type"] == {"concept": 2, "reference": 1, "claim": 1}
    assert ov["edges_by_type"]["wikilink"] == 3
    assert ov["edges_by_type"]["has_tag"] == 1
    assert ov["tags"] == 2
    assert ov["claims_by_status"] == {"verified": 1}
    assert ov["broken_links"] == 1


def test_nodes_degree_and_order(conn):
    rows = browse_nodes(conn)
    assert rows[0]["id"] == "wiki/concepts/alpha"
    assert rows[0]["degree"] == 3
    by_id = {r["id"]: r for r in rows}
    assert by_id["wiki/concepts/beta"]["degree"] == 1
    assert by_id["claim:abc"]["degree"] == 0


def test_nodes_filters(conn):
    concepts = browse_nodes(conn, node_type="concept")
    assert {r["id"] for r in concepts} == {"wiki/concepts/alpha", "wiki/concepts/beta"}

    hits = browse_nodes(conn, q="ALPHA")
    ids = {r["id"] for r in hits}
    assert "wiki/concepts/alpha" in ids
    assert "wiki/concepts/beta" not in ids

    assert len(browse_nodes(conn, limit=2)) == 2


def test_links_out_and_in(conn):
    res = browse_links(conn, "wiki/concepts/alpha")
    assert res["node"]["title"] == "Alpha Concept"

    out = {e["target_id"]: e for e in res["outgoing"]}
    assert out["wiki/concepts/beta"]["title"] == "Beta Concept"
    assert out["Nonexistent Page"]["title"] is None
    assert "tag:physics" not in out  # has_tag excluded

    inc = {e["source_id"] for e in res["incoming"]}
    assert inc == {"wiki/references/paper-one"}


def test_links_resolves_title_case_insensitive(conn):
    res = browse_links(conn, "alpha concept")
    assert res["node"]["id"] == "wiki/concepts/alpha"


def test_links_unknown_node(conn):
    res = browse_links(conn, "no-such-node")
    assert res == {"node": None, "outgoing": [], "incoming": []}


def test_hubs(conn):
    hubs = browse_hubs(conn, limit=2)
    assert len(hubs) == 2
    assert hubs[0]["id"] == "wiki/concepts/alpha"
    assert hubs[0]["degree"] == 3


def test_claims(conn):
    rows = browse_claims(conn)
    assert rows == [{"id": "claim:abc", "doc_id": "wiki/references/paper-one.md",
                     "status": "verified", "text": "Alpha scales linearly with beta."}]
    assert browse_claims(conn, status="rejected") == []
    assert len(browse_claims(conn, q="SCALES")) == 1
    assert browse_claims(conn, q="gamma") == []


def test_tags(conn):
    rows = browse_tags(conn)
    assert rows[0] == {"tag": "physics", "count": 2}
    assert {"tag": "methods", "count": 1} in rows
    assert browse_tags(conn, q="meth") == [{"tag": "methods", "count": 1}]


def test_broken(conn):
    rows = browse_broken(conn)
    assert rows == [{"source_id": "wiki/concepts/alpha", "source_title": "Alpha Concept",
                     "target_text": "Nonexistent Page", "type": "wikilink"}]


@pytest.fixture
def tag_db_path(tmp_path):
    # Separate fixture: the shared one has no tag-typed nodes, and the map
    # tag rules need a real tag node plus an isolated page.
    path = tmp_path / "map-graph.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE nodes(id TEXT PRIMARY KEY, path TEXT, title TEXT, type TEXT, category TEXT, summary TEXT, created TEXT, updated TEXT);
        CREATE TABLE edges(source_id TEXT, target_id TEXT, type TEXT, UNIQUE(source_id, target_id, type));

        INSERT INTO nodes VALUES('page-a', 'a.md', 'Page A', 'concept', NULL, NULL, '2026-08-18', '2026-08-18');
        INSERT INTO nodes VALUES('page-b', 'b.md', 'Page B', 'concept', NULL, NULL, '2026-08-18', '2026-08-18');
        INSERT INTO nodes VALUES('page-c', 'c.md', 'Page C', 'concept', NULL, NULL, '2026-08-18', '2026-08-18');
        INSERT INTO nodes VALUES('tag:physics', NULL, 'physics', 'tag', NULL, NULL, '2026-08-18', '2026-08-18');

        INSERT INTO edges VALUES('page-a', 'page-b', 'wikilink');
        INSERT INTO edges VALUES('page-a', 'tag:physics', 'has_tag');
        INSERT INTO edges VALUES('page-b', 'tag:physics', 'has_tag');
        """
    )
    conn.close()
    return path


@pytest.fixture
def tag_conn(tag_db_path):
    c = open_ro(tag_db_path)
    yield c
    c.close()


def test_map_ghost_synthesis_and_degrees(conn):
    res = browse_map(conn)
    assert res["truncated"] is False
    by_id = {n["id"]: n for n in res["nodes"]}
    assert set(by_id) == {"wiki/concepts/alpha", "wiki/concepts/beta",
                          "wiki/references/paper-one", "claim:abc",
                          "Nonexistent Page"}

    ghost = by_id["Nonexistent Page"]
    assert ghost["type"] == "ghost"
    assert ghost["title"] == "Nonexistent Page"
    assert ghost["degree"] == 1

    # has_tag edges never count toward real-node degree.
    assert by_id["wiki/concepts/alpha"]["degree"] == 3
    assert by_id["wiki/references/paper-one"]["degree"] == 3
    assert by_id["claim:abc"]["degree"] == 2
    assert by_id["wiki/concepts/beta"]["degree"] == 1

    triples = {(e["source"], e["target"], e["type"]) for e in res["edges"]}
    assert ("wiki/concepts/alpha", "Nonexistent Page", "wikilink") in triples
    assert ("wiki/references/paper-one", "claim:abc", "has_claim") in triples
    assert ("claim:abc", "wiki/references/paper-one", "supported_by") in triples
    assert not any(t == "has_tag" for _, _, t in triples)


def test_map_excludes_tags_by_default(tag_conn):
    res = browse_map(tag_conn)
    ids = {n["id"] for n in res["nodes"]}
    # Tag node excluded, and no ghost is faked for it: the has_tag target
    # matches a real nodes.id.
    assert ids == {"page-a", "page-b", "page-c"}
    assert all(e["type"] != "has_tag" for e in res["edges"])


def test_map_includes_tags_on_request(tag_conn):
    res = browse_map(tag_conn, include_tags=True)
    by_id = {n["id"]: n for n in res["nodes"]}
    assert by_id["tag:physics"]["type"] == "tag"
    assert by_id["tag:physics"]["degree"] == 2  # has_tag count
    assert by_id["page-a"]["degree"] == 1  # still excludes has_tag
    assert sum(1 for e in res["edges"] if e["type"] == "has_tag") == 2


def test_map_isolated_node_included(tag_conn):
    res = browse_map(tag_conn)
    by_id = {n["id"]: n for n in res["nodes"]}
    assert by_id["page-c"]["degree"] == 0


def test_map_limit_drops_lowest_degree_first(conn):
    res = browse_map(conn, limit=3)
    assert res["truncated"] is True
    ids = {n["id"] for n in res["nodes"]}
    assert ids == {"wiki/concepts/alpha", "wiki/references/paper-one", "claim:abc"}
    # Edges touching dropped nodes are gone too.
    for e in res["edges"]:
        assert e["source"] in ids and e["target"] in ids


def test_map_ghost_drops_before_real_at_equal_degree(conn):
    # beta and the ghost both have degree 1; id order alone would keep the
    # ghost ("Nonexistent Page" < "wiki/concepts/beta"), so this pins the
    # ghosts-drop-first rule.
    res = browse_map(conn, limit=4)
    assert res["truncated"] is True
    ids = {n["id"] for n in res["nodes"]}
    assert "wiki/concepts/beta" in ids
    assert "Nonexistent Page" not in ids


def test_main_map_json(db_path, capsys):
    rc = main(["map", "--db", str(db_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["view"] == "map"
    assert payload["results"]["truncated"] is False
    ids = {n["id"] for n in payload["results"]["nodes"]}
    assert "Nonexistent Page" in ids


def test_main_map_tags_flag(tag_db_path, capsys):
    rc = main(["map", "--db", str(tag_db_path), "--tags", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    ids = {n["id"] for n in payload["results"]["nodes"]}
    assert "tag:physics" in ids


def test_main_map_human_output(db_path, capsys):
    rc = main(["map", "--db", str(db_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ghost" in out
    assert "wikilink" in out
    assert "--json" in out


def test_main_json_overview(db_path, capsys):
    rc = main(["overview", "--db", str(db_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["view"] == "overview"
    assert payload["results"]["broken_links"] == 1


def test_main_json_nodes_filtered(db_path, capsys):
    rc = main(["nodes", "--db", str(db_path), "--type", "concept", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["view"] == "nodes"
    assert {r["id"] for r in payload["results"]} == {
        "wiki/concepts/alpha", "wiki/concepts/beta"}


def test_main_links_falls_back_to_hubs(db_path, capsys):
    rc = main(["links", "--db", str(db_path), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["view"] == "hubs"
    assert payload["results"][0]["id"] == "wiki/concepts/alpha"


def test_main_human_output(db_path, capsys):
    rc = main(["broken", "--db", str(db_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Nonexistent Page" in out


def test_main_missing_db(tmp_path, capsys):
    rc = main(["overview", "--db", str(tmp_path / "absent.db")])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert "error" in payload
