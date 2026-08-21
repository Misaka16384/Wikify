"""Contracts for the batch commands — the human gate itself.

The two that matter most:

* nothing reaches ``raw/`` while any item in its batch is undecided, and
* rejecting an item requeues it one rung down without anyone re-submitting it.

Nothing else in this repo has either shape, so nothing else covers them.
"""

import types

import pytest

from magi.ingest import batch, ledger
from magi.ingest.convert_result import ConversionResult, Finding


@pytest.fixture
def ws(tmp_path):
    """A workspace skeleton — enough for commit to have somewhere to land."""
    for sub in ("raw/papers", "wiki", "inbox", "output"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.md").write_text("# scope\n", encoding="utf-8")
    return tmp_path


def _args(**kw):
    base = dict(topic_dir=None, batch=None, item=None, decision=None,
                limit=None, json=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


def _stub_route(monkeypatch, ws, *, success=True, findings=(), error="boom"):
    """Replace conversion with something that writes a plausible document."""
    def fake(route, entry, staging):
        if not success:
            return ConversionResult.failed(error)
        staging.mkdir(parents=True, exist_ok=True)
        md = staging / "2026-08-21-a-paper.md"
        md.write_text("---\ntitle: A Paper\narxiv_id: '2608.16520'\n---\n\n"
                      + "word " * 300, encoding="utf-8")
        return ConversionResult(success=True, markdown_path=str(md),
                                findings=list(findings))

    monkeypatch.setattr(batch, "_run_route", fake)
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    monkeypatch.setattr(batch.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="", stderr=""))


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def test_running_an_empty_queue_is_a_no_op(ws, monkeypatch, capsys):
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    assert batch.main(["run"]) == 0
    assert "nothing queued" in capsys.readouterr().out


def test_a_run_stages_but_writes_nothing_into_the_library(ws, monkeypatch):
    """Conversion output belongs to the batch, not to raw/, until approved."""
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="2608.16520")

    batch.main(["run"])

    assert list((ws / "raw" / "papers").iterdir()) == []


def test_each_queued_item_becomes_a_batch_item(ws, monkeypatch):
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="a")
    ledger.enqueue(ws, source_type="arxiv", value="b")

    batch.main(["run"])
    items = ledger.load_batch(ws, ledger.list_batches(ws)[0])

    assert {i.source_value for i in items} == {"a", "b"}


def test_a_failing_item_does_not_end_the_run(ws, monkeypatch):
    """One bad paper must not cost the other ninety-nine."""
    calls = {"n": 0}

    def fake(route, entry, staging):
        calls["n"] += 1
        if entry.value == "bad":
            raise RuntimeError("network exploded")
        staging.mkdir(parents=True, exist_ok=True)
        md = staging / "ok.md"
        md.write_text("---\ntitle: T\n---\n\n" + "word " * 300, encoding="utf-8")
        return ConversionResult(success=True, markdown_path=str(md))

    monkeypatch.setattr(batch, "_run_route", fake)
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    ledger.enqueue(ws, source_type="arxiv", value="bad")
    ledger.enqueue(ws, source_type="arxiv", value="good")

    batch.main(["run"])
    items = {i.source_value: i for i in ledger.load_batch(ws, ledger.list_batches(ws)[0])}

    assert calls["n"] == 2
    assert items["bad"].error and not items["bad"].ok
    assert items["good"].ok


def test_gate_findings_are_attached_to_the_item(ws, monkeypatch):
    _stub_route(monkeypatch, ws,
                findings=[Finding("route-arxiv-html", "767 formulas", "info")])
    ledger.enqueue(ws, source_type="arxiv", value="2608.16520")

    batch.main(["run"])
    item = ledger.load_batch(ws, ledger.list_batches(ws)[0])[0]

    assert any(f["code"] == "route-arxiv-html" for f in item.findings)


def test_limit_leaves_the_rest_queued(ws, monkeypatch):
    _stub_route(monkeypatch, ws)
    for i in range(3):
        ledger.enqueue(ws, source_type="arxiv", value=f"p{i}")

    batch.main(["run", "--limit", "2"])

    assert len(ledger.pending(ws)) == 1


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

def test_commit_refuses_a_batch_with_anything_undecided(ws, monkeypatch, capsys):
    """The whole point: one unreviewed item holds its own batch, not the library."""
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="a")
    batch.main(["run"])

    batch.main(["commit"])

    assert list((ws / "raw" / "papers").iterdir()) == []
    assert "still undecided" in capsys.readouterr().out


def test_an_approved_item_reaches_the_library(ws, monkeypatch):
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="a")
    batch.main(["run"])
    item = ledger.load_batch(ws, ledger.list_batches(ws)[0])[0]

    batch.main(["decide", "--item", item.item_id, "--decision", "approve"])
    batch.main(["commit"])

    assert [p.name for p in (ws / "raw" / "papers").glob("*.md")] == \
        ["2026-08-21-a-paper.md"]


def test_a_rejected_item_never_reaches_the_library(ws, monkeypatch):
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="a")
    batch.main(["run"])
    item = ledger.load_batch(ws, ledger.list_batches(ws)[0])[0]

    batch.main(["decide", "--item", item.item_id, "--decision", "reject"])
    batch.main(["commit"])

    assert list((ws / "raw" / "papers").glob("*.md")) == []


def test_committing_twice_does_not_duplicate(ws, monkeypatch):
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="a")
    batch.main(["run"])
    item = ledger.load_batch(ws, ledger.list_batches(ws)[0])[0]
    batch.main(["decide", "--item", item.item_id, "--decision", "approve"])

    batch.main(["commit"])
    batch.main(["commit"])

    assert len(list((ws / "raw" / "papers").glob("*.md"))) == 1


def test_the_commit_is_recorded_against_the_item(ws, monkeypatch):
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="a")
    batch.main(["run"])
    batch_id = ledger.list_batches(ws)[0]
    item = ledger.load_batch(ws, batch_id)[0]
    batch.main(["decide", "--item", item.item_id, "--decision", "approve"])
    batch.main(["commit"])

    assert ledger.load_batch(ws, batch_id)[0].committed_path


def test_staged_images_travel_with_the_document(ws, monkeypatch):
    """A committed page whose figures stayed in staging is a page of broken links."""
    def fake(route, entry, staging):
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "images").mkdir()
        (staging / "images" / "fig.png").write_bytes(b"PNG")
        md = staging / "doc.md"
        md.write_text('---\ntitle: T\n---\n\n<img src="images/fig.png"/>\n'
                      + "word " * 300, encoding="utf-8")
        return ConversionResult(success=True, markdown_path=str(md),
                                images_dir=str(staging / "images"))

    monkeypatch.setattr(batch, "_run_route", fake)
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    monkeypatch.setattr(batch.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="", stderr=""))

    ledger.enqueue(ws, source_type="arxiv", value="a")
    batch.main(["run"])
    item = ledger.load_batch(ws, ledger.list_batches(ws)[0])[0]
    batch.main(["decide", "--item", item.item_id, "--decision", "approve"])
    batch.main(["commit"])

    assert (ws / "raw" / "papers" / "images" / "fig.png").read_bytes() == b"PNG"


# --------------------------------------------------------------------------
# Reject means "try the next rung down"
# --------------------------------------------------------------------------

def test_rejecting_requeues_one_rung_down(ws, monkeypatch, capsys):
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="2608.16520")
    batch.main(["run"])
    item = ledger.load_batch(ws, ledger.list_batches(ws)[0])[0]
    assert item.route == "arxiv-html"

    batch.main(["decide", "--item", item.item_id, "--decision", "reject"])

    requeued = ledger.pending(ws)
    assert len(requeued) == 1
    assert requeued[0].route == "tex"
    assert requeued[0].retry_of == item.item_id
    assert "next route down" in capsys.readouterr().out


def test_the_requeued_item_runs_on_the_new_route(ws, monkeypatch):
    """End to end: reject, run again, and it really is on the next rung."""
    seen = []

    def fake(route, entry, staging):
        seen.append(route)
        staging.mkdir(parents=True, exist_ok=True)
        md = staging / "d.md"
        md.write_text("---\ntitle: T\n---\n\n" + "word " * 300, encoding="utf-8")
        return ConversionResult(success=True, markdown_path=str(md))

    monkeypatch.setattr(batch, "_run_route", fake)
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)

    ledger.enqueue(ws, source_type="arxiv", value="x")
    batch.main(["run"])
    item = ledger.load_batch(ws, ledger.list_batches(ws)[0])[0]
    batch.main(["decide", "--item", item.item_id, "--decision", "reject"])
    batch.main(["run"])

    assert seen == ["arxiv-html", "tex"]


def test_rejecting_at_the_bottom_stops_rather_than_escalating(ws, monkeypatch, capsys):
    """The last rung must not fall into the per-page vision fan-out on its own —
    that is precisely the failure this pipeline was built to prevent."""
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="x", route="ocr")
    batch.main(["run"])
    item = ledger.load_batch(ws, ledger.list_batches(ws)[0])[0]

    batch.main(["decide", "--item", item.item_id, "--decision", "reject"])

    out = capsys.readouterr().out
    assert ledger.pending(ws) == []
    assert "last automatic route" in out
    assert "one subagent call per page" in out


def test_undo_puts_an_item_back_in_play(ws, monkeypatch):
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="a")
    batch.main(["run"])
    batch_id = ledger.list_batches(ws)[0]
    item = ledger.load_batch(ws, batch_id)[0]

    batch.main(["decide", "--item", item.item_id, "--decision", "approve"])
    batch.main(["decide", "--item", item.item_id, "--decision", "reset"])

    assert ledger.load_batch(ws, batch_id)[0].decision is None


def test_deciding_an_unknown_item_fails_loudly(ws, monkeypatch):
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    assert batch.main(["decide", "--item", "item-nope", "--decision", "approve"]) == 1


def test_decide_requires_both_arguments(ws, monkeypatch):
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    with pytest.raises(SystemExit):
        batch.main(["decide", "--item", "x"])


# --------------------------------------------------------------------------
# list
# --------------------------------------------------------------------------

def test_listing_nothing_says_how_to_start(ws, monkeypatch, capsys):
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    batch.main(["list"])
    assert "magi ingest url" in capsys.readouterr().out


def test_json_output_is_machine_readable(ws, monkeypatch, capsys):
    import json
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="a")
    batch.main(["run"])
    capsys.readouterr()

    batch.main(["list", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert data["batches"][0]["undecided"] == 1
    assert data["batches"][0]["items"][0]["route"] == "arxiv-html"


def test_no_workspace_is_an_error_not_a_crash(monkeypatch):
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: None)
    assert batch.main(["run"]) == 1
    assert batch.main(["list"]) == 1
    assert batch.main(["commit"]) == 1
