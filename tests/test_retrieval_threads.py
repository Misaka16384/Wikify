"""`threads/` in retrieval: searchable, never rewritten, and ranked below what
the library actually knows.

Two decisions are encoded here and both are easy to undo by accident.

**Indexed, not maintained.** `threads/` is walked by the indexer but is
deliberately not in `wiki_common.CORPUS_DIRS`, because that tuple drives the
passes that *rewrite* files — maths reformatting, tag rewriting. A discussion
is append-only: nothing reflows somebody's post to fix a dollar sign.

**Down-weighted in a query that did not ask for it.** A proposition in
`threads/` is a claim in progress. Letting an untested conjecture outrank a
concept card is how a guess gets read back as knowledge two weeks later.
Asking for the collection by name is a filter rather than a ranking, so the
penalty lifts — otherwise `--collection threads` would be quietly re-sorted
against itself for no reason.
"""

import sqlite3
from pathlib import Path

import pytest

from magi import retrieval
from magi.core import wiki_common


@pytest.mark.parametrize("rel,collection", [
    ("threads/p-gap.md", "threads"),
    ("drafts/argument.md", "drafts"),
    ("raw/papers/x.md", "raw"),
    ("wiki/concepts/toric-code.md", "concepts"),
])
def test_a_path_lands_in_its_collection(rel, collection):
    assert retrieval._collection_of(Path(rel)) == collection


def test_thread_notes_are_indexed(tmp_path):
    (tmp_path / "threads").mkdir()
    (tmp_path / "threads" / "p-gap.md").write_text("# Gap\n", encoding="utf-8")
    (tmp_path / "threads" / "_index.md").write_text("# Threads\n", encoding="utf-8")

    found = {p.name for p in retrieval._iter_corpus(tmp_path)}
    assert found == {"p-gap.md"}


def test_thread_notes_are_not_in_the_rewriting_corpus():
    """`corpus_files` feeds the passes that edit files in place. A post is
    somebody's argument; nothing reformats it."""
    assert "threads" not in wiki_common.CORPUS_DIRS


def _conn(rows):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, collection TEXT)")
    conn.executemany("INSERT INTO chunks (id, collection) VALUES (?, ?)", rows)
    return conn


def test_a_proposition_is_ranked_below_a_concept_card():
    conns = {"kb": _conn([(1, "threads"), (2, "concepts")])}
    merged = {("kb", 1): {"bm25": 0}, ("kb", 2): {"bm25": 0}}

    weights = retrieval._collection_weights(conns, merged)

    assert weights[("kb", 1)] < 1.0
    assert ("kb", 2) not in weights, "only the down-weighted collections carry an entry"


class _Counting:
    """A connection that records the SQL it was asked to run.

    `sqlite3.Connection.execute` cannot be reassigned, so counting queries
    needs a wrapper rather than a monkeypatch.
    """

    def __init__(self, conn):
        self._conn = conn
        self.calls = []

    def execute(self, sql, *args):
        self.calls.append(sql)
        return self._conn.execute(sql, *args)


def test_the_lookup_is_one_query_per_knowledge_base():
    """A per-chunk query would turn a search into a few hundred round trips."""
    counting = _Counting(_conn([(n, "threads") for n in range(50)]))
    merged = {("kb", n): {"bm25": n} for n in range(50)}

    weights = retrieval._collection_weights({"kb": counting}, merged)

    assert len(counting.calls) == 1
    assert len(weights) == 50


def test_a_collection_nobody_penalises_has_no_entry():
    conns = {"kb": _conn([(1, "raw"), (2, "drafts"), (3, "topics")])}
    merged = {("kb", n): {"bm25": n} for n in (1, 2, 3)}

    assert retrieval._collection_weights(conns, merged) == {}


def test_a_line_boosts_what_it_is_looking_at_without_hiding_the_rest():
    """A boost and not a filter: the answer to a question asked from inside a
    line is often in a paper the line has never cited, and filtering to the
    focus set would hide exactly that."""
    conns = {"kb": _conn_paths([(1, "wiki/concepts/toric-code.md"),
                                (2, "raw/papers/unrelated.md")])}
    merged = {("kb", 1): {"bm25": 0}, ("kb", 2): {"bm25": 0}}
    weights = {}

    retrieval._apply_focus(conns, merged, {"wiki/concepts/toric-code.md"}, weights)

    assert weights[("kb", 1)] == retrieval.FOCUS_BOOST
    assert ("kb", 2) not in weights, "everything else still competes"


def test_the_focus_boost_stacks_with_the_collection_weight():
    """A proposition the line points at should not lose its down-weight; the
    two are answering different questions."""
    conns = {"kb": _conn_paths([(1, "threads/p-gap.md")])}
    merged = {("kb", 1): {"bm25": 0}}
    weights = {("kb", 1): retrieval._COLLECTION_WEIGHT["threads"]}

    retrieval._apply_focus(conns, merged, {"threads/p-gap.md"}, weights)

    assert weights[("kb", 1)] == retrieval._COLLECTION_WEIGHT["threads"] * retrieval.FOCUS_BOOST


def test_windows_separators_match_the_same_file():
    conns = {"kb": _conn_paths([(1, "wiki\\concepts\\toric-code.md")])}
    merged = {("kb", 1): {"bm25": 0}}
    weights = {}

    retrieval._apply_focus(conns, merged, {"wiki/concepts/toric-code.md"}, weights)

    assert ("kb", 1) in weights


def _conn_paths(rows):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, path TEXT, collection TEXT)")
    conn.executemany("INSERT INTO chunks (id, path) VALUES (?, ?)", rows)
    return conn
