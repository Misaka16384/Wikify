"""Three defects that were suspected from reading, then reproduced.

Each one had been written down as "this looks wrong" and left there. Chasing
them settled three as real and three as not; these are the three, and each test
is the reproduction that decided it.

The three that were closed, so nobody re-opens them from the same reading:

* `Path.resolve()` on Windows *does* canonicalise case for a path that exists
  (it goes through `GetFinalPathNameByHandle`), so the WebUI's per-workspace
  job gate cannot be split by typing a drive letter differently.
* `magi ui`'s port probe has a ~70 ms window between releasing the test socket
  and uvicorn binding, and losing it is a loud `OSError` and a non-zero exit,
  not a server that quietly fails to serve.
* Every mention of `magi mcp` in the tree — nine of them — says "future" or
  「未来」. None reads as a command to run today.
"""

import sqlite3
import subprocess
import sys

import pytest


# --------------------------------------------------------------------------
# The graph that stayed stale after being rebuilt
# --------------------------------------------------------------------------

@pytest.fixture
def graph_workspace(tmp_path):
    from magi.hub import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    for i in (1, 2, 3):
        (tmp_path / "wiki" / "concepts" / f"c{i}.md").write_text(
            f"---\ntitle: C{i}\nsummary: s\n---\n\nSee [[C{i % 3 + 1}]].\n",
            encoding="utf-8")
    return tmp_path


def _graph_build(ws):
    res = subprocess.run([sys.executable, "-m", "magi", "graph", "build", str(ws)],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace")
    assert "Traceback" not in res.stderr, res.stderr
    return res


def test_a_rebuilt_graph_is_not_reported_stale_while_something_reads_it(graph_workspace):
    """SQLite checkpoints the WAL when the *last* connection closes. With a
    reader open anywhere — the Melchior graph tab, `magi graph query` in a
    second terminal — the build's close is not the last one, so the write
    stayed in `graph.db-wal` and `graph.db`'s own mtime never moved.

    `magi sync` reads freshness from that mtime, so it called the graph stale
    immediately after a build that had just succeeded, and offered
    `magi graph build` as the cure for having run `magi graph build`.
    Rebuilding did not help; closing the other window did.
    """
    from magi.sync import melchior_status

    _graph_build(graph_workspace)
    db = graph_workspace / "output" / "graph.db"
    wal = graph_workspace / "output" / "graph.db-wal"

    reader = sqlite3.connect(str(db))
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM nodes").fetchone()

        (graph_workspace / "wiki" / "concepts" / "c1.md").write_text(
            "---\ntitle: C1\nsummary: changed\n---\n\nSee [[C2]].\n",
            encoding="utf-8")
        _graph_build(graph_workspace)

        # The write really is sitting in the WAL — that part is not fixable
        # from the build side, and measuring it here documents why: with this
        # reader holding a snapshot, PASSIVE checkpoints 0 of 16 frames and
        # FULL/TRUNCATE come back busy.
        assert wal.exists() and wal.stat().st_size > 0, (
            "this test is no longer exercising the case it was written for")

        # What must not happen is the report calling the graph stale over it.
        assert melchior_status(graph_workspace)["graph"] != "stale", (
            "sync read freshness from graph.db's mtime alone, which the WAL "
            "left behind — so it demanded a rebuild of a graph just rebuilt")
    finally:
        reader.close()


def test_with_nothing_else_reading_sqlite_folds_the_wal_back_itself(graph_workspace):
    """The ordinary case needs no help: the build's connection is the last
    one, so closing it checkpoints. This is here to keep the fix above honest
    about which case it is for."""
    _graph_build(graph_workspace)
    wal = graph_workspace / "output" / "graph.db-wal"
    assert not wal.exists() or wal.stat().st_size == 0


def test_a_build_with_a_reader_open_still_succeeds(graph_workspace):
    """The data is committed either way — an unfolded WAL is a timestamp
    problem, never a lost write."""
    import sqlite3 as _s

    reader = _s.connect(str(graph_workspace / "output" / "graph.db"))
    try:
        _graph_build(graph_workspace)
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM nodes").fetchone()
        assert _graph_build(graph_workspace).returncode == 0
    finally:
        reader.close()


# --------------------------------------------------------------------------
# --rebuild against an index something else has open
# --------------------------------------------------------------------------

def test_rebuilding_a_held_index_says_what_to_do(tmp_path, capsys):
    """Windows refuses to unlink a file another handle has open, and something
    usually does: the WebUI opens the index read-only per request, a search
    holds it for the length of a query. This surfaced as a raw traceback out
    of pathlib with no hint that closing a window would fix it."""
    import argparse

    from magi import retrieval
    from magi.hub import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    (tmp_path / "wiki" / "concepts" / "a.md").write_text(
        "---\ntitle: A\nsummary: s\n---\n\nbody\n", encoding="utf-8")
    args = argparse.Namespace(topic_dir=str(tmp_path), no_vectors=True,
                              rebuild=False, quiet=True)
    assert retrieval.cmd_index(args) == 0

    db = tmp_path / "output" / "index.db"
    holder = sqlite3.connect(str(db))
    try:
        holder.execute("SELECT 1").fetchone()
        args.rebuild = True
        rc = retrieval.cmd_index(args)
    finally:
        holder.close()

    if rc != 0:
        # Windows: the unlink is refused, and the message has to name the cure.
        assert "another process" in capsys.readouterr().err
        assert db.exists(), "the index was destroyed on the way to failing"


# --------------------------------------------------------------------------
# One title, several papers
# --------------------------------------------------------------------------

def _ingest_url(ws, *args):
    from magi.ingest import enqueue

    return enqueue.main(["--topic-dir", str(ws), *args])


@pytest.fixture
def ws(tmp_path):
    from magi.hub import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    return tmp_path


def test_one_title_cannot_describe_several_papers(ws, capsys):
    """It was applied to every entry, and downstream it *overrides* the title
    parsed from the converted document — so a review list showed every paper
    under one name. For local PDFs the staging filename is built from that
    title, so N conversions land on one path and overwrite each other before
    anyone reviews them."""
    from magi.ingest import ledger

    rc = _ingest_url(ws, "2301.00001", "2302.00002", "--title", "Attention Is All You Need")

    assert rc == 2
    assert "names one paper" in capsys.readouterr().err
    assert ledger.pending(ws) == [], "nothing should have been queued"


def test_one_target_keeps_the_override(ws):
    """Somebody naming a single paper by hand knows more than the parser, and
    that is the case the flag exists for."""
    from magi.ingest import ledger

    assert _ingest_url(ws, "2301.00001", "--title", "A Real Title") == 0
    assert [p.title for p in ledger.pending(ws)] == ["A Real Title"]


def test_several_targets_without_a_title_are_fine(ws):
    from magi.ingest import ledger

    assert _ingest_url(ws, "2301.00001", "2302.00002") == 0
    assert len(ledger.pending(ws)) == 2
