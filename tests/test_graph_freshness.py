"""A graph that includes `threads/` is stale when `threads/` moves, and the
WebUI rebuilds it; an index run survives one embedding timeout.

Two symptoms from one day. A proposition opened with `magi thread new` was
not on the WebUI's map and nothing said why: the map reads `graph.db`, notes
are on the graph, freshness was measured against `wiki/` alone, and nothing
but a hand-run `graph build` ever rewrote the file. And one Ollama timeout
during `magi index` switched vectors off for the rest of the run, leaving a
hundred chunks BM25-only for a hiccup the next request would have survived.
"""

import argparse
import os
import time

import pytest

from magi import retrieval, sync
from magi.core import vocab
from magi.kb import threads


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "threads").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "wiki" / "concepts" / "a.md").write_text("# A\n", encoding="utf-8")
    return tmp_path


def _stamp(path, seconds_from_now):
    when = time.time() + seconds_from_now
    os.utime(path, (when, when))


# --------------------------------------------------------------------------
# staleness
# --------------------------------------------------------------------------

def test_no_graph_and_something_to_map_is_stale(ws):
    assert sync.graph_stale(ws)


def test_a_graph_newer_than_the_wiki_is_fresh(ws):
    graph = ws / "output" / "graph.db"
    graph.write_bytes(b"")
    _stamp(ws / "wiki" / "concepts" / "a.md", -100)
    _stamp(graph, -10)
    assert not sync.graph_stale(ws)


def test_a_new_note_makes_the_graph_stale(ws):
    """Notes are nodes. A map that does not show the proposition opened this
    morning is a stale map, whatever `wiki/` says."""
    graph = ws / "output" / "graph.db"
    graph.write_bytes(b"")
    _stamp(ws / "wiki" / "concepts" / "a.md", -100)
    _stamp(graph, -10)
    path = threads.create(ws / "threads" / "p.md", vocab.PROPOSITION, "P", "Why.")
    _stamp(path, 5)
    assert sync.graph_stale(ws)


def test_melchior_reports_the_same_answer(ws):
    graph = ws / "output" / "graph.db"
    graph.write_bytes(b"")
    _stamp(ws / "wiki" / "concepts" / "a.md", -100)
    _stamp(graph, -10)
    path = threads.create(ws / "threads" / "p.md", vocab.PROPOSITION, "P", "Why.")
    _stamp(path, 5)
    assert sync.melchior_status(ws)["graph"] in ("stale", "missing") or \
        sync.melchior_status(ws).get("graph_state") == "stale" or \
        "stale" in str(sync.melchior_status(ws))


# --------------------------------------------------------------------------
# the WebUI rebuilds
# --------------------------------------------------------------------------

def test_the_graph_endpoint_rebuilds_a_stale_graph_in_process(ws, monkeypatch):
    from magi.kb import llmwiki
    from magi.ui import api

    built = []

    def fake_run_graph(args):
        assert isinstance(args, argparse.Namespace)
        assert args.path == str(ws) and args.local is False
        built.append(1)
        (ws / "output" / "graph.db").write_bytes(b"")
        _stamp(ws / "output" / "graph.db", 10)
        return 0

    monkeypatch.setattr(llmwiki, "run_graph", fake_run_graph)
    assert api._ensure_graph_fresh(ws) is True
    assert built == [1]
    assert api._ensure_graph_fresh(ws) is False, "fresh now; nothing to do"
    assert built == [1]


def test_a_failed_rebuild_serves_the_old_graph_and_does_not_raise(ws, monkeypatch):
    from magi.kb import llmwiki
    from magi.ui import api

    def boom(args):
        raise RuntimeError("locked")

    monkeypatch.setattr(llmwiki, "run_graph", boom)
    assert api._ensure_graph_fresh(ws) is False
    assert not api._GRAPH_REBUILD.locked()


# --------------------------------------------------------------------------
# the index survives a timeout
# --------------------------------------------------------------------------

def _embedder(tmp_path, monkeypatch, replies):
    emb = retrieval.Embedder(start=tmp_path)
    monkeypatch.setattr(emb, "_preflight", lambda: True)
    emb.available = True
    calls = []

    def post(payload, timeout=None):
        calls.append(timeout)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(emb, "_post_batch", post)
    return emb, calls


def test_one_timeout_on_an_index_run_is_retried_with_a_longer_ceiling(tmp_path, monkeypatch, capsys):
    import requests

    emb, calls = _embedder(tmp_path, monkeypatch,
                           [requests.exceptions.ReadTimeout(), [[0.1, 0.2]]])
    assert emb.embed_many(["x"]) == [[0.1, 0.2]]
    assert emb.available is True
    assert calls[0] is None and calls[1] == 2 * (60 + 10)
    assert "retrying once" in capsys.readouterr().err


def test_a_second_timeout_disables_as_before(tmp_path, monkeypatch):
    import requests

    emb, _calls = _embedder(tmp_path, monkeypatch,
                            [requests.exceptions.ReadTimeout(),
                             requests.exceptions.ReadTimeout()])
    assert emb.embed_many(["x"]) is None
    assert emb.available is False


def test_a_search_with_its_own_short_ceiling_is_never_retried(tmp_path, monkeypatch):
    """The 8-second ceiling is a promise to the person at the keyboard. An
    interactive search that should have given up after 8 seconds once took 17."""
    import requests

    emb, calls = _embedder(tmp_path, monkeypatch,
                           [requests.exceptions.ReadTimeout(), [[0.1]]])
    assert emb.embed_many(["x"], timeout=8.0) is None
    assert calls == [8.0]


def test_rearm_lets_the_backfill_try_once_more(tmp_path, monkeypatch):
    import requests

    emb, _calls = _embedder(tmp_path, monkeypatch,
                            [requests.exceptions.ReadTimeout(),
                             requests.exceptions.ReadTimeout(), [[0.5]]])
    assert emb.embed_many(["x"]) is None and emb.available is False
    assert emb.rearm() is True
    assert emb.embed_many(["x"]) == [[0.5]]
