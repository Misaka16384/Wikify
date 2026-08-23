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


def test_queueing_writes_nothing_outside_the_queue(ws):
    """Everything it creates lives under output/ingest/, and raw/ and wiki/ are
    untouched. That, not a single-file count, is the promise: the queue
    directory also holds a lock file, because two writers at once is ordinary
    here — the CLI, the WebUI job, and the extension all append to it."""
    before = {p for p in ws.rglob("*") if p.is_file()}
    enqueue.main(["2608.16520"])
    after = {p for p in ws.rglob("*") if p.is_file()}

    new = after - before
    assert ledger.queue_path(ws) in new

    ingest_dir = ledger.ingest_dir(ws).resolve()
    for path in new:
        assert path.resolve().is_relative_to(ingest_dir), f"escaped the queue: {path}"


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

def test_a_named_library_routes_there_not_to_the_current_directory(ws, tmp_path,
                                                                   monkeypatch):
    """--library is what both the extension's picker and the inbox skill set.

    It used to be recorded and then ignored, so everything landed in whatever
    directory you happened to be standing in.
    """
    other = tmp_path / "other-kb"
    (other / "raw" / "papers").mkdir(parents=True)
    monkeypatch.setattr("magi.kb_registry.load_registry",
                        lambda: {"kbs": {"Physics": {"path": str(other)}}})

    enqueue.main(["2608.16520", "--library", "Physics"])

    assert ledger.pending(other)[0].value == "2608.16520"
    assert ledger.pending(ws) == []


def test_the_library_name_is_matched_forgivingly(ws, tmp_path, monkeypatch):
    other = tmp_path / "kb"
    other.mkdir()
    monkeypatch.setattr("magi.kb_registry.load_registry",
                        lambda: {"kbs": {"My-Physics": {"path": str(other)}}})

    assert enqueue.main(["2608.16520", "--library", "my_physics"]) == 0
    assert len(ledger.pending(other)) == 1


def test_an_unknown_library_fails_and_names_the_real_ones(ws, monkeypatch, capsys):
    """A closed world: you pick from what exists, you do not invent a destination."""
    monkeypatch.setattr("magi.kb_registry.load_registry",
                        lambda: {"kbs": {"Physics": {"path": "/tmp/x"}}})

    assert enqueue.main(["2608.16520", "--library", "Nope"]) == 1
    assert "Physics" in capsys.readouterr().err
    assert ledger.pending(ws) == []


def test_several_targets_are_queued_in_one_call(ws):
    """An agent that just found eight papers should not shell out eight times."""
    enqueue.main(["2608.16520", "10.1103/PhysRevB.108.014301",
                  "https://example.com/paper"])

    kinds = [e.source_type for e in ledger.pending(ws)]
    assert kinds == ["arxiv", "doi", "url"]


def test_a_known_title_is_carried_through(ws):
    enqueue.main(["2608.16520", "--title", "Maximal Torus Entropy"])
    assert ledger.pending(ws)[0].title == "Maximal Torus Entropy"


def test_json_output_reports_what_was_queued(ws, capsys):
    """The shape a skill reads back to tell the user what it did."""
    enqueue.main(["2608.16520", "cond-mat/0506438", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert data["pending"] == 2
    assert [q["value"] for q in data["queued"]] == ["2608.16520", "cond-mat/0506438"]
    assert all(q["req_id"].startswith("req-") for q in data["queued"])
    assert data["workspace"]


def test_queueing_the_same_paper_twice_collapses_and_says_so(ws, capsys):
    """This used to assert the opposite, for a reason worth preserving:
    "deduplication is a decision for the reviewer, not a silent drop here."

    The objection was to the *silence*, not to the collapsing — and clicking
    the browser button three times really did produce three conversions of one
    paper and three rows to approve. So the request is now collapsed and the
    fact is reported: the reviewer still learns what happened, without having
    to notice three identical rows to learn it.
    """
    enqueue.main(["2608.16520"])
    capsys.readouterr()
    enqueue.main(["2608.16520"])
    out = capsys.readouterr().out

    assert len(ledger.pending(ws)) == 1
    assert "already queued" in out          # collapsed, and not quietly


def test_no_workspace_is_an_error_not_a_crash(monkeypatch):
    monkeypatch.setattr(enqueue, "_resolve_topic", lambda explicit: None)
    assert enqueue.main(["2608.16520"]) == 1
