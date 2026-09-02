"""A route that half-worked must not reach a reviewer looking whole.

The OCR route converts page by page, so one page failing leaves the rest of
the document intact. Keeping those pages is right. Recording the run as clean
is not, and that is what happened: ``agent.py`` returned ``success=True``
unconditionally, ``batch.py`` gated the ledger's error field on ``success``,
and no finding was raised for a failed page either. A forty-page paper missing
five pages appeared in the review queue as **successful, zero errors, zero
flags** — and ``ledger.review_order`` sorts on exactly the signal that was
being zeroed, so the queue put it last.

Three layers are tested here, because the fix is three layers:

* ``ConversionResult.silent_about`` — the invariant itself,
* ``batch`` — the net under every route, which turns a silent result into a
  finding at the one seam every route passes through,
* ``_finalize`` — the other end of the same shape, where a failed subprocess
  was swallowed by ``capture_output=True`` and never read.
"""

import types

import pytest

from magi.ingest import batch, ledger
from magi.ingest.convert_result import ConversionResult, Finding


# --------------------------------------------------------------------------
# the invariant
# --------------------------------------------------------------------------

def test_success_with_errors_and_no_finding_is_silent():
    r = ConversionResult(success=True, markdown_path="x.md", errors=["page 2 died"])
    assert r.silent_about == ["page 2 died"]


def test_a_loud_finding_carries_the_errors():
    r = ConversionResult(success=True, markdown_path="x.md", errors=["page 2 died"])
    r.flag("pages-failed", "1 page did not convert")
    assert r.silent_about == []


def test_an_info_finding_does_not_count_as_speaking_up():
    """`ledger.loud_findings` skips severity="info", so it cannot carry this."""
    r = ConversionResult(success=True, markdown_path="x.md", errors=["page 2 died"])
    r.flag("page-repaired", "one page was re-read", severity="info")
    assert r.silent_about == ["page 2 died"]


def test_an_outright_failure_is_visible_on_its_own():
    assert ConversionResult.failed("everything died").silent_about == []


def test_a_clean_result_is_not_silent_about_anything():
    assert ConversionResult(success=True, markdown_path="x.md").silent_about == []


# --------------------------------------------------------------------------
# the net under every route
# --------------------------------------------------------------------------

def _partial_route(monkeypatch, ws, *, findings=()):
    """A route that writes a real document and admits a page went missing."""
    def fake(route, entry, staging, topic=None, **kw):
        staging.mkdir(parents=True, exist_ok=True)
        md = staging / "2026-08-21-a-paper.md"
        md.write_text("---\ntitle: A Paper\n---\n\n" + "word " * 300,
                      encoding="utf-8")
        return ConversionResult(success=True, markdown_path=str(md),
                                pages_processed=40,
                                errors=["第 7 页 OCR 失败: out of memory"],
                                findings=list(findings))

    monkeypatch.setattr(batch, "_run_route", fake)
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    monkeypatch.setattr(batch.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            returncode=0, stdout="", stderr=""))


@pytest.fixture
def ws(tmp_path):
    for sub in ("raw/papers", "wiki", "inbox", "output"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.md").write_text("# scope\n", encoding="utf-8")
    return tmp_path


def _run(ws):
    args = types.SimpleNamespace(topic_dir=None, batch=None, item=None,
                                 decision=None, limit=None, json=False)
    batch.cmd_run(args)
    batch_id = ledger.list_batches(ws)[-1]
    return ledger.load_batch(ws, batch_id)


def test_a_forgotten_page_reaches_the_ledger(ws, monkeypatch):
    _partial_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="file", value="paper.pdf", route="ocr")

    item, = _run(ws)
    assert item.error and "第 7 页" in item.error


def test_a_forgotten_page_becomes_a_loud_finding(ws, monkeypatch):
    """The route said nothing, so the seam says it — this is the net."""
    _partial_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="file", value="paper.pdf", route="ocr")

    item, = _run(ws)
    codes = [f["code"] for f in item.findings]
    assert "route-errors-unreported" in codes
    assert ledger.loud_findings(item) >= 1


def test_the_route_speaking_up_is_not_reported_twice(ws, monkeypatch):
    """A route that raises its own finding must not also trip the net."""
    _partial_route(monkeypatch, ws, findings=[
        Finding("pages-failed", "1 of 40 page(s) did not convert")])
    ledger.enqueue(ws, source_type="file", value="paper.pdf", route="ocr")

    item, = _run(ws)
    codes = [f["code"] for f in item.findings]
    assert "pages-failed" in codes
    assert "route-errors-unreported" not in codes


def test_the_pages_that_did_convert_are_kept(ws, monkeypatch):
    """Thirty-nine good pages are worth more than a tidy failure."""
    _partial_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="file", value="paper.pdf", route="ocr")

    item, = _run(ws)
    assert item.staged_md and item.staged_md.endswith(".md")


def test_a_half_converted_document_sorts_ahead_of_a_clean_one(ws, monkeypatch):
    """The point of the whole fix: review_order can only rank what it is told."""
    _partial_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="file", value="broken.pdf", route="ocr")
    items = _run(ws)

    clean = ledger.BatchItem(item_id="zz", req_id="r2", route="ocr",
                             source_type="file", source_value="clean.pdf",
                             title=None, arxiv_id=None, staged_md="clean.md",
                             findings=[], error=None, decision=None,
                             committed_path=None, retry_of=None)
    order = ledger.review_order(list(items) + [clean])
    assert order[0].source_value == "broken.pdf"


# --------------------------------------------------------------------------
# the same shape at the other end: a swallowed subprocess
# --------------------------------------------------------------------------

def test_finalize_failure_is_reported(monkeypatch, capsys):
    monkeypatch.setattr(batch.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            returncode=1, stdout="", stderr="database is locked"))
    assert batch._finalize(["magi"], what="a-paper.md") is False
    err = capsys.readouterr().err
    assert "finalize failed" in err
    assert "database is locked" in err
    assert "raw/" in err          # says what it does and does not mean


def test_the_ocr_cli_does_not_exit_zero_on_a_missing_page(monkeypatch, tmp_path):
    """A caller that only reads the exit code must not read 0 as "all of it"."""
    from magi.ingest.ocr import agent as ocr_agent

    class _Stub:
        def __init__(self, config_path=None):
            pass

        def convert(self, **kw):
            return ConversionResult(success=True, markdown_path="out.md",
                                    pages_processed=40,
                                    errors=["第 7 页 OCR 失败: out of memory"])

    monkeypatch.setattr(ocr_agent, "PDF2MarkdownAgent", _Stub)
    assert ocr_agent.main([str(tmp_path / "paper.pdf")]) == 1


def test_the_ocr_cli_still_exits_zero_when_every_page_converted(monkeypatch, tmp_path):
    from magi.ingest.ocr import agent as ocr_agent

    class _Stub:
        def __init__(self, config_path=None):
            pass

        def convert(self, **kw):
            return ConversionResult(success=True, markdown_path="out.md",
                                    pages_processed=40)

    monkeypatch.setattr(ocr_agent, "PDF2MarkdownAgent", _Stub)
    assert ocr_agent.main([str(tmp_path / "paper.pdf")]) == 0


def test_finalize_success_says_nothing(monkeypatch, capsys):
    monkeypatch.setattr(batch.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            returncode=0, stdout="", stderr=""))
    assert batch._finalize(["magi"], what="a-paper.md") is True
    assert capsys.readouterr().err == ""
