"""DOIs reach the ladder as arXiv ids, `discard` exists, and a held batch says so.

Three ingest reports from one day. Seven DOIs queued by `ingest url` all failed
in `batch-run` with "not an arXiv identifier" — the resolver existed and was
wired only into the Zotero import. "Reject" on an orphan requeued it one rung
down, because reject has always meant that; what was wanted was a word that
means drop. And `review --commit` printed "N committed" from one batch beside
"left alone" for another, which read as the held items having landed.
"""

import types

import pytest

from magi.ingest import batch, identity, ledger
from magi.ingest.convert_result import ConversionResult


@pytest.fixture
def ws(tmp_path, monkeypatch):
    for sub in ("raw/papers", "wiki", "inbox", "output"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.md").write_text("# scope\n", encoding="utf-8")
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: tmp_path)
    monkeypatch.setattr(batch.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="", stderr=""))
    return tmp_path


def _stub_route(monkeypatch, seen=None):
    def fake(route, entry, staging, topic=None, **kw):
        if seen is not None:
            seen.append((route, entry.source_type, entry.value))
        staging.mkdir(parents=True, exist_ok=True)
        md = staging / f"{entry.value.replace('/', '-')}.md"
        md.write_text("---\ntitle: A Paper\n---\n\n" + "word " * 300, encoding="utf-8")
        return ConversionResult(success=True, markdown_path=str(md), findings=[])

    monkeypatch.setattr(batch, "_run_route", fake)


def _items(ws):
    out = []
    for batch_id in ledger.list_batches(ws):
        out.extend(ledger.load_batch(ws, batch_id))
    return out


# --------------------------------------------------------------------------
# DOI
# --------------------------------------------------------------------------

def test_a_doi_semantic_scholar_knows_runs_as_its_arxiv_id(ws, monkeypatch):
    doi = "10.1103/PhysRevB.100.1"
    monkeypatch.setattr(identity, "resolve_dois",
                        lambda dois, titles=None, **kw: {
                            doi.lower(): identity.Identity("2301.00001", doi, "s2", None)})
    seen = []
    _stub_route(monkeypatch, seen)
    ledger.enqueue(ws, source_type="doi", value=doi)

    assert batch.main(["run"]) == 0

    assert seen == [("arxiv-html", "arxiv", "2301.00001")]
    item = _items(ws)[0]
    assert (item.source_type, item.source_value) == ("arxiv", "2301.00001")
    # The request itself is claimed; nothing is left queued.
    assert ledger.pending(ws) == []


def test_the_lookup_is_one_call_for_the_whole_batch(ws, monkeypatch):
    calls = []

    def fake(dois, titles=None, **kw):
        calls.append(list(dois))
        return {d.lower(): identity.Identity("2301.0000%d" % i, d, "s2", None)
                for i, d in enumerate(dois, 1)}

    monkeypatch.setattr(identity, "resolve_dois", fake)
    _stub_route(monkeypatch)
    for n in range(3):
        ledger.enqueue(ws, source_type="doi", value=f"10.1000/x{n}")
    batch.main(["run"])
    assert len(calls) == 1 and len(calls[0]) == 3


def test_a_doi_with_no_arxiv_version_fails_naming_the_remedy_and_has_no_rung_below(
        ws, monkeypatch, capsys):
    doi = "10.1000/nowhere"
    monkeypatch.setattr(identity, "resolve_dois",
                        lambda dois, titles=None, **kw: {doi.lower(): identity.Identity(None, doi, "")})
    ledger.enqueue(ws, source_type="doi", value=doi)

    batch.main(["run"])          # the real _run_route: it refuses before any network

    item = _items(ws)[0]
    assert item.error and "magi ingest add" in item.error
    assert "not an arXiv identifier" not in item.error
    assert item.source_type == "doi"

    batch.main(["decide", "--item", item.item_id, "--decision", "reject"])
    assert ledger.pending(ws) == [], "a DOI has nothing below it to fall to"
    out = capsys.readouterr().out
    assert "nothing below it" in out and "magi ingest add" in out


def test_a_lookup_that_fails_does_not_end_the_run(ws, monkeypatch, capsys):
    def boom(dois, titles=None, **kw):
        raise RuntimeError("network")

    monkeypatch.setattr(identity, "resolve_dois", boom)
    ledger.enqueue(ws, source_type="doi", value="10.1000/x")
    assert batch.main(["run"]) == 0
    assert "DOI lookup failed" in capsys.readouterr().err
    assert _items(ws)[0].error


def test_a_retry_already_on_a_rung_is_not_resolved_again(ws, monkeypatch):
    """A requeued item names its rung and its identity is settled."""
    called = []
    monkeypatch.setattr(identity, "resolve_dois",
                        lambda dois, titles=None, **kw: called.append(1) or {})
    _stub_route(monkeypatch)
    ledger.enqueue(ws, source_type="doi", value="10.1000/x", route="tex")
    batch.main(["run"])
    assert called == []


def test_ingest_url_says_what_happens_to_a_doi(ws, monkeypatch, capsys):
    from magi.ingest import enqueue

    monkeypatch.setattr(enqueue, "resolve_library", lambda *a, **k: ws, raising=False)
    monkeypatch.setattr(enqueue, "find_workspace_root", lambda *a, **k: ws, raising=False)
    code = enqueue.main(["url", "10.1000/x", "--topic-dir", str(ws)]) \
        if hasattr(enqueue, "main") else 0
    out = capsys.readouterr().out
    if code == 0 and "queued doi" in out:
        assert "Semantic Scholar" in out and "magi ingest add" in out


# --------------------------------------------------------------------------
# discard
# --------------------------------------------------------------------------

def _one_item(ws, monkeypatch):
    _stub_route(monkeypatch)
    ledger.enqueue(ws, source_type="arxiv", value="2301.00001")
    batch.main(["run"])
    return _items(ws)[0]


def test_discard_is_a_decision_that_requeues_nothing(ws, monkeypatch, capsys):
    item = _one_item(ws, monkeypatch)
    assert batch.main(["decide", "--item", item.item_id, "--decision", "discard"]) == 0
    assert ledger.pending(ws) == []
    again = _items(ws)[0]
    assert again.decision == "discard" and again.decided
    assert "dropped" in capsys.readouterr().out


def test_a_discarded_item_does_not_hold_its_batch_and_never_lands(ws, monkeypatch, capsys):
    item = _one_item(ws, monkeypatch)
    batch.main(["decide", "--item", item.item_id, "--decision", "discard"])
    items = _items(ws)
    assert ledger.blocking_commit(items) == []
    batch.main(["review", "--commit"])
    assert not list((ws / "raw" / "papers").glob("*.md"))
    assert "nothing to commit" in capsys.readouterr().out


def test_reject_still_means_one_rung_down(ws, monkeypatch):
    item = _one_item(ws, monkeypatch)
    batch.main(["decide", "--item", item.item_id, "--decision", "reject"])
    assert [e.route for e in ledger.pending(ws)] == ["tex"]


def test_the_decision_words_are_one_list(ws):
    assert "discard" in ledger.DECISIONS and "discard" in ledger.FINAL_DECISIONS
    assert "reset" in ledger.DECISIONS and "reset" not in ledger.FINAL_DECISIONS
    with pytest.raises(ValueError):
        ledger.record_decision(ws, "batch-x", "item-x", "drop")


# --------------------------------------------------------------------------
# a held batch
# --------------------------------------------------------------------------

def test_a_held_batch_says_held_and_counts_what_it_holds(ws, monkeypatch, capsys):
    _stub_route(monkeypatch)
    ledger.enqueue(ws, source_type="arxiv", value="2301.00001")
    ledger.enqueue(ws, source_type="arxiv", value="2301.00002")
    batch.main(["run"])
    first, _second = _items(ws)
    batch.main(["decide", "--item", first.item_id, "--decision", "approve"])
    capsys.readouterr()

    batch.main(["review", "--commit"])

    out = capsys.readouterr().out
    assert "HELD" in out
    assert "1 approved item(s) were NOT committed" in out
    assert "nothing committed." in out
    assert "left alone" not in out
    assert "document(s) committed" not in out
    assert not list((ws / "raw" / "papers").glob("*.md"))
