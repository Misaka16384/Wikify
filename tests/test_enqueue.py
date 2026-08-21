"""Contracts for `magi ingest url`.

This is the one door into the pipeline, and the browser extension will reach it
through the same function. Its blast radius — one appended line, nothing else —
is the entire reason the extension can be unauthenticated.
"""

import json
import types

import pytest

from magi.ingest import enqueue, ledger


@pytest.fixture
def ws(tmp_path):
    for sub in ("raw/papers", "wiki", "inbox", "output"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.md").write_text("# scope\n", encoding="utf-8")
    return tmp_path


@pytest.fixture(autouse=True)
def here(ws, monkeypatch):
    monkeypatch.setattr(enqueue, "_resolve_topic", lambda explicit: ws)
    return ws


# --------------------------------------------------------------------------
# What gets recognised
# --------------------------------------------------------------------------

@pytest.mark.parametrize("target,kind,value", [
    ("https://arxiv.org/abs/2608.16520", "arxiv", "2608.16520"),
    ("2608.16520", "arxiv", "2608.16520"),
    ("arXiv:cond-mat/0506438", "arxiv", "cond-mat/0506438"),
    ("https://doi.org/10.1103/PhysRevB.108.014301", "doi", "10.1103/physrevb.108.014301"),
    ("https://example.com/some/paper", "url", "https://example.com/some/paper"),
])
def test_the_target_is_classified(ws, target, kind, value):
    enqueue.main([target])
    entry = ledger.pending(ws)[0]
    assert (entry.source_type, entry.value) == (kind, value)


def test_a_journal_page_url_keeps_its_doi(ws):
    """A publisher page carrying a DOI is queued as the DOI, which is what a
    Semantic Scholar lookup can actually use."""
    enqueue.main(["https://link.aps.org/doi/10.1103/PhysRevB.108.014301"])
    assert ledger.pending(ws)[0].source_type == "doi"


def test_a_local_file_is_queued_as_a_file(ws, tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    enqueue.main([str(pdf)])

    entry = ledger.pending(ws)[0]
    assert entry.source_type == "file"
    assert entry.value.endswith("paper.pdf")


# --------------------------------------------------------------------------
# Blast radius
# --------------------------------------------------------------------------

def test_queueing_appends_exactly_one_line(ws):
    enqueue.main(["2608.16520"])
    lines = ledger.queue_path(ws).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_queueing_writes_nothing_into_the_library(ws):
    before = {p for p in ws.rglob("*") if p.is_file()}
    enqueue.main(["2608.16520"])
    after = {p for p in ws.rglob("*") if p.is_file()}

    assert after - before == {ledger.queue_path(ws)}


def test_queueing_makes_no_network_call(ws, monkeypatch):
    """The Semantic Scholar lookup belongs to batch-run, where it can be batched
    with everything queued alongside it."""
    import magi.core.http as core_http
    monkeypatch.setattr(core_http, "http_json",
                        lambda *a, **k: pytest.fail("should not call out"))
    monkeypatch.setattr(core_http, "http_get",
                        lambda *a, **k: pytest.fail("should not call out"))

    enqueue.main(["https://doi.org/10.1103/PhysRevB.108.014301"])
    assert len(ledger.pending(ws)) == 1


# --------------------------------------------------------------------------
# Details that travel
# --------------------------------------------------------------------------

def test_the_chosen_library_is_recorded(ws):
    """This is what the extension's picker sets."""
    enqueue.main(["2608.16520", "--library", "MindPalace"])
    assert ledger.pending(ws)[0].library == "MindPalace"


def test_a_known_title_is_carried_through(ws):
    enqueue.main(["2608.16520", "--title", "Maximal Torus Entropy"])
    assert ledger.pending(ws)[0].title == "Maximal Torus Entropy"


def test_json_output_reports_what_was_queued(ws, capsys):
    enqueue.main(["2608.16520", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert data["status"] == "queued"
    assert data["value"] == "2608.16520"
    assert data["req_id"].startswith("req-")


def test_queueing_the_same_paper_twice_is_allowed(ws):
    """Deduplication is a decision for the reviewer, not a silent drop here."""
    enqueue.main(["2608.16520"])
    enqueue.main(["2608.16520"])
    assert len(ledger.pending(ws)) == 2


def test_no_workspace_is_an_error_not_a_crash(monkeypatch):
    monkeypatch.setattr(enqueue, "_resolve_topic", lambda explicit: None)
    assert enqueue.main(["2608.16520"]) == 1
