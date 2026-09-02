"""A failed graph rebuild must leave the graph it had, not an empty one.

`graph build` clears every table and then walks `wiki/` to refill them. The
clear used `cursor.executescript(...)`, and executescript commits before it
runs and performs no transaction control of its own — so the deletes were
durable the instant they executed, while the refill was still ~200 lines and
one whole directory walk away.

Measured before the fix, on a scratch database: three rows, `executescript`
a DELETE, close the connection without committing, reopen — zero rows. With
plain `execute` per table the same sequence puts all three back, because
`execute` joins the implicit transaction that `commit()` at the end closes.

`output/graph.db` is derived and can be rebuilt, so this is not lost research.
It is worse than it sounds anyway: the rebuild that failed is exactly the one
nobody watched, and an empty graph answers queries with silence rather than an
error.
"""

from __future__ import annotations

import sqlite3

import pytest

from magi.kb import llmwiki


def _nodes(db) -> int:
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT count(*) FROM nodes").fetchone()[0]


@pytest.fixture
def built(tmp_path):
    from magi import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    (concepts / "alpha.md").write_text(
        "---\ntitle: Alpha\n---\n\n# Alpha\n\nSee [[Beta]].\n", encoding="utf-8")
    (concepts / "beta.md").write_text(
        "---\ntitle: Beta\n---\n\n# Beta\n", encoding="utf-8")

    import argparse

    llmwiki.run_graph(argparse.Namespace(path=str(tmp_path), local=False, wiki=None))
    return tmp_path


def test_the_graph_is_built_to_begin_with(built):
    assert _nodes(built / "output" / "graph.db") >= 2


def test_a_rebuild_that_dies_mid_scan_leaves_the_old_graph(built, monkeypatch):
    """The scan raises after the tables were cleared. Nothing was committed,
    so every row has to come back."""
    import argparse

    db = built / "output" / "graph.db"
    before = _nodes(db)

    def boom(*a, **k):
        raise RuntimeError("an unreadable card, halfway through the walk")

    monkeypatch.setattr(llmwiki, "parse_frontmatter_block", boom)

    with pytest.raises(RuntimeError):
        llmwiki.run_graph(argparse.Namespace(path=str(built), local=False, wiki=None))

    assert _nodes(db) == before, "the failed rebuild emptied the graph"
