"""CJK tokenization regression tests for the retrieval index.

FTS5's default unicode61 tokenizer treats a whole CJK run as one token,
which made Chinese BM25 queries return zero hits. The index now segments
CJK into overlapping bigrams on both the index and query side.
"""

from __future__ import annotations

import argparse
import sqlite3

import pytest

from magi import retrieval


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    # cmd_index auto-registers the workspace; keep that out of the real registry
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "cfg"))


def _make_workspace(tmp_path):
    ws = tmp_path / "topic"
    (ws / "wiki" / "concepts").mkdir(parents=True)
    (ws / "config.yaml").write_text("topic: cjk-test\n", encoding="utf-8")
    (ws / "wiki" / "concepts" / "sparse-attention.md").write_text(
        "---\ntitle: sparse-attention\ntype: concept\n---\n\n"
        "稀疏注意力通过限制可达集合把复杂度降到近线性。\n\n"
        "FlashAttention is an IO-aware exact attention kernel.\n",
        encoding="utf-8",
    )
    return ws


def test_fts_text_segments_cjk_and_keeps_latin():
    out = retrieval.fts_text("注意力机制 attention kernel")
    assert "注意 意力 力机 机制" in out
    assert "attention kernel" in out
    # single CJK char survives as itself
    assert "序" in retrieval.fts_text("序")


def test_chinese_and_english_bm25_hit(tmp_path):
    ws = _make_workspace(tmp_path)
    args = argparse.Namespace(topic_dir=str(ws), no_vectors=True)
    assert retrieval.cmd_index(args) == 0

    opened = retrieval.open_db(ws / "output" / "index.db")
    assert opened is not None
    conn, vec_loaded = opened
    try:
        zh = argparse.Namespace(collection=None, mode="bm25",
                                query="注意力如何降低复杂度", k=5)
        _, zh_hits, _, _, _ = retrieval._search_one_db(conn, vec_loaded, zh, None, 10)
        assert zh_hits >= 1, "Chinese BM25 query must hit the Chinese card"

        en = argparse.Namespace(collection=None, mode="bm25",
                                query="attention kernel", k=5)
        _, en_hits, _, _, _ = retrieval._search_one_db(conn, vec_loaded, en, None, 10)
        assert en_hits >= 1, "English BM25 behaviour must be unchanged"
    finally:
        conn.close()


def test_path_glob_filter_and_boilerplate_skip(tmp_path):
    ws = _make_workspace(tmp_path)
    # a second card whose only mention of "attention" is in a See Also list
    (ws / "wiki" / "concepts" / "other-card.md").write_text(
        "---\ntitle: other\ntype: concept\n---\n\n无关内容。\n\n## See Also\n\n- [[attention kernel notes]]\n",
        encoding="utf-8",
    )
    args = argparse.Namespace(topic_dir=str(ws), no_vectors=True)
    assert retrieval.cmd_index(args) == 0

    opened = retrieval.open_db(ws / "output" / "index.db")
    conn, vec_loaded = opened
    try:
        # --path narrows to one file
        q = argparse.Namespace(collection=None, mode="bm25", query="attention",
                               k=5, path="wiki/concepts/sparse-*")
        ranks, hits, _, _, _ = retrieval._search_one_db(conn, vec_loaded, q, None, 10)
        paths = {conn.execute("SELECT path FROM chunks WHERE id=?", (cid,)).fetchone()[0]
                 for cid in ranks}
        assert hits >= 1
        assert all(p.startswith("wiki/concepts/sparse-") for p in paths)

        # boilerplate See Also section must not be indexed at all
        n = conn.execute(
            "SELECT count(*) FROM chunks WHERE path='wiki/concepts/other-card.md' "
            "AND heading='See Also'").fetchone()[0]
        assert n == 0
    finally:
        conn.close()


def test_legacy_index_is_migrated_in_place(tmp_path):
    db = tmp_path / "index.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE files(path TEXT PRIMARY KEY, hash TEXT, mtime REAL);
        CREATE TABLE chunks(
            id INTEGER PRIMARY KEY, path TEXT, collection TEXT, heading TEXT,
            start_line INT, end_line INT, content TEXT);
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            content, content='chunks', content_rowid='id');
        CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END;
        CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES('delete', old.id, old.content);
        END;
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO chunks(path, collection, heading, start_line, end_line, content)
            VALUES('wiki/concepts/a.md', 'concepts', 'a', 1, 3,
                   '拓扑序的基态简并度依赖于流形的亏格。');
        """
    )
    conn.commit()

    # sanity: legacy tokenization cannot match a rephrased Chinese query
    legacy = conn.execute(
        "SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH ?",
        [retrieval._fts_query("基态简并度")],
    ).fetchone()[0]
    assert legacy == 0

    retrieval.ensure_schema(conn, None, vec_loaded=False)
    assert retrieval._fts_schema_version(conn) == retrieval.FTS_VERSION

    hits = conn.execute(
        "SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH ?",
        [retrieval._fts_query("基态简并度")],
    ).fetchone()[0]
    assert hits == 1, "migrated legacy rows must be searchable in Chinese"
    conn.close()


def test_a_schemaless_index_reads_as_no_index(tmp_path):
    """An interrupted `magi index` leaves a file with no tables in it.

    SQLite creates the file on connect; the schema only lands at the first
    commit. Such a file used to open cleanly and then explode on the first
    query — and because search is federated, ONE of them anywhere in the
    registry made every other library on the machine unsearchable with a raw
    `no such table: chunks_fts`.
    """
    import sqlite3

    from magi import retrieval

    db = tmp_path / "index.db"
    sqlite3.connect(db).close()          # exactly what an interrupted run leaves
    assert db.is_file()
    assert retrieval.open_db(db) is None

    # ...while a real index still opens.
    conn, _ = retrieval.open_db(db, create=True)
    retrieval.ensure_schema(conn, None, False)
    conn.commit()
    conn.close()
    assert retrieval.open_db(db) is not None
