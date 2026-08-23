"""Which rung a source starts on — the decision that used to exist twice.

`magi ingest auto` and `magi ingest batch-run` both answered it, and they
disagreed: auto used a PDF's own text layer when it could, the batch ladder
sent every non-arXiv source to `mineru`, and since `textlayer` sits *above*
`mineru` a local PDF could never fall back up to it. Of the 758 items in the
library this was built for, 567 carry a stored PDF.

The test that matters most here is the last one: the two entry points are
asked about the same file and must return the same rung.
"""

import builtins
import sys

import pytest

from magi.ingest import routing


@pytest.fixture(autouse=True)
def _cold_cache():
    """Every test starts with no remembered verdicts.

    The cache keys on path+mtime+size, so real files cannot collide across
    tests — but these tests stub the gate underneath it, and a cache that
    outlives the stub would answer the next test from the last one's fiction.
    """
    routing.forget_verdicts()
    yield
    routing.forget_verdicts()


def _prose_pdf(path):
    """A born-digital, maths-free paper — the kind the text layer suits.

    Built rather than checked in, because the gate measures characters per page
    and enumerates fonts: a file that merely has a .pdf name proves nothing.
    """
    pymupdf = pytest.importorskip("pymupdf")
    prose = ("This section reviews the literature on institutional adoption "
             "and the outcomes reported across the surveyed programmes. ")
    doc = pymupdf.open()
    for page_no in range(6):
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(60, 60, 540, 700),
                            f"Section {page_no + 1}\n\n" + prose * 14, fontsize=10)
    doc.save(str(path))
    doc.close()
    return path


def _blank_pdf(path):
    """Pages with almost no text — a scan, as far as the gate can tell."""
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    for _ in range(4):
        doc.new_page().insert_text((72, 100), "x", fontsize=10)
    doc.save(str(path))
    doc.close()
    return path


# --------------------------------------------------------------------------
# first_rung
# --------------------------------------------------------------------------

@pytest.mark.parametrize("source_type,value,expected", [
    ("arxiv", "2401.00506", "arxiv-html"),
    ("arxiv", "cond-mat/0001002", "arxiv-html"),
    ("url", "https://arxiv.org/abs/2401.00506", "arxiv-html"),
    ("doi", "10.1103/PhysRevX.8.031051", "arxiv-html"),
    ("file", "/x/paper.tex", "tex"),
    ("file", "/x/2401.00506.tar.gz", "tex"),
    ("file", "/x/2401.00506.tgz", "tex"),
    ("file", "/x/notes.md", "add"),
    ("file", "/x/notes.txt", "add"),
])
def test_the_rung_follows_from_what_the_source_is(source_type, value, expected):
    route, why = routing.first_rung(source_type, value)
    assert route == expected
    assert why, "every routing decision has to be able to say why"


def test_a_prose_pdf_starts_on_the_free_route(tmp_path):
    """The whole of A4. This used to return `mineru` — and because `textlayer`
    is *above* `mineru` on the ladder, nothing could fall back up to it, so a
    local PDF spent a token or a GPU minute on something readable for free."""
    route, why = routing.first_rung("file", str(_prose_pdf(tmp_path / "survey.pdf")))
    assert route == "textlayer"
    assert "text layer" in why


def test_a_pdf_with_nothing_to_read_goes_to_a_model(tmp_path):
    route, _ = routing.first_rung("file", str(_blank_pdf(tmp_path / "scan.pdf")))
    assert route == "mineru"


def test_a_missing_file_routes_rather_than_raising(tmp_path):
    """Routing runs before anything has been fetched, so it meets absent files
    routinely. It must answer, not explode."""
    route, why = routing.first_rung("file", str(tmp_path / "not-here.pdf"))
    assert route == "mineru" and why


# --------------------------------------------------------------------------
# text_layer_verdict — the promise that routing never fails
# --------------------------------------------------------------------------

def test_an_inspection_that_raises_is_a_no_not_a_crash(tmp_path, monkeypatch):
    from magi.ingest import textlayer

    def boom(_path):
        raise RuntimeError("PyMuPDF exploded")

    monkeypatch.setattr(textlayer, "inspect", boom)
    verdict = routing.text_layer_verdict(tmp_path / "x.pdf")
    assert verdict.ok is False and "PyMuPDF exploded" in verdict.why


def test_a_missing_extractor_says_whether_it_would_have_helped(tmp_path, monkeypatch):
    """The gate is asked before the extractor is looked for, so the reason can
    say this particular file was readable. 'pymupdf4llm is not installed' on its
    own does not tell you whether installing it would change anything."""
    _stub_verdict(monkeypatch, route_here=True, reason="a real text layer, no math fonts")
    _make_import_fail(monkeypatch, ImportError("No module named 'pymupdf4llm'"))

    verdict = routing.text_layer_verdict(tmp_path / "x.pdf")
    # The document is still readable; this machine is what is missing something.
    # Folding the two together made routing depend on the environment, and the
    # same PDF then took different rungs on a developer's box and on CI.
    assert verdict.ok is True
    assert verdict.available is False
    assert "a real text layer" in verdict.why
    assert "pymupdf4llm is not installed" in verdict.why
    assert "pymupdf4llm is not installed" in verdict.unavailable_why


def test_an_import_that_fails_without_being_an_ImportError_is_caught(tmp_path, monkeypatch):
    """The measured incident: pymupdf4llm pulls onnxruntime, and an onnxruntime
    too old for the models it ships raises `Fail: Unsupported model IR version:
    10` at import. That is not an ImportError, so `except ImportError` let it
    through and one file's routing question ended the whole run."""
    _stub_verdict(monkeypatch, route_here=True, reason="a real text layer")
    _make_import_fail(monkeypatch, RuntimeError(
        "Fail: Unsupported model IR version: 10, max supported IR version: 9"))

    verdict = routing.text_layer_verdict(tmp_path / "x.pdf")
    assert verdict.ok is True          # the PDF is fine; the install is not
    assert verdict.available is False
    assert "onnxruntime" in verdict.why and "1.18" in verdict.why


def test_the_rung_is_chosen_without_asking_what_is_installed(tmp_path, monkeypatch):
    """The whole point of this module, and the thing CI caught being violated.

    A prose PDF routes to `textlayer` on a machine with the extra and on one
    without it. `batch-run` has a ladder and falls, learning the package name
    on the way; `ingest auto` has none and looks at `available` itself.
    """
    _stub_verdict(monkeypatch, route_here=True, reason="a real text layer, no math fonts")
    _make_import_fail(monkeypatch, ImportError("No module named 'pymupdf4llm'"))
    routing.forget_verdicts()

    pdf = tmp_path / "survey.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    route, why = routing.first_rung("file", str(pdf))
    assert route == "textlayer"
    assert "pymupdf4llm is not installed" in why


def test_a_maths_paper_is_refused_before_the_extractor_is_even_considered(tmp_path, monkeypatch):
    _stub_verdict(monkeypatch, route_here=False, reason="math fonts present (CMSY10)")
    verdict = routing.text_layer_verdict(tmp_path / "x.pdf")
    assert verdict.ok is False and verdict.why == "math fonts present (CMSY10)"


def _stub_verdict(monkeypatch, *, route_here, reason):
    import types as _types

    from magi.ingest import textlayer
    monkeypatch.setattr(textlayer, "inspect",
                        lambda _p: _types.SimpleNamespace(route_here=route_here,
                                                          reason=reason))


def _make_import_fail(monkeypatch, exc):
    """Make `import pymupdf4llm` raise `exc`, leaving every other import alone."""
    monkeypatch.delitem(sys.modules, "pymupdf4llm", raising=False)
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pymupdf4llm":
            raise exc
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


# --------------------------------------------------------------------------
# infer_source_type — only for records that predate the field
# --------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("https://arxiv.org/abs/2401.00506", "url"),
    ("http://example.test/p.pdf", "url"),
    ("10.1103/PhysRevX.8.031051", "doi"),
    ("doi:10.1103/PhysRevX.8.031051", "doi"),
    ("2401.00506", "arxiv"),
    ("cond-mat/0001002", "arxiv"),
    ("D:/Zotero/storage/ABC/paper.pdf", "file"),
    ("/home/x/paper.pdf", "file"),
])
def test_a_type_can_be_recovered_from_a_value(value, expected):
    """`2401.00506` has a dot and is not a file; `cond-mat/0001002` has a slash
    and is not a path. Asking the id parser is what gets both right."""
    assert routing.infer_source_type(value) == expected


# --------------------------------------------------------------------------
# The two entry points must not drift apart again
# --------------------------------------------------------------------------

def test_both_commands_route_the_same_pdf_to_the_same_rung(tmp_path):
    """A5, stated as a test. `ingest auto` and `batch-run` are separate
    commands with separate argument handling, and they used to reach separate
    conclusions about one file. Whatever else changes, this must not."""
    import types

    from magi.ingest import auto, batch

    pdf = _prose_pdf(tmp_path / "survey.pdf")

    auto_route, _ = auto.classify(pdf, {"ocr": {"mineru_api_token": "tok"}})
    # From cold, so this really re-runs the decision rather than reading back
    # the answer the first call left in the verdict cache.
    routing.forget_verdicts()
    batch_route, _ = batch._starting_route(
        types.SimpleNamespace(route=None, source_type="file", value=str(pdf)))

    assert auto_route == batch_route == "textlayer"


def test_a_pdf_is_not_inspected_twice_for_one_answer(tmp_path, monkeypatch):
    """A queued PDF is asked about twice — once to pick its rung, once by the
    rung itself, which re-checks because a retry can force a route. Inspecting
    means opening the document and enumerating its fonts: measured at 869 ms on
    a six-page file, which is nothing once and real across a whole batch."""
    from magi.ingest import textlayer

    pdf = _prose_pdf(tmp_path / "survey.pdf")
    calls = []
    real_inspect = textlayer.inspect

    def counting(path):
        calls.append(path)
        return real_inspect(path)

    monkeypatch.setattr(textlayer, "inspect", counting)
    first = routing.text_layer_verdict(pdf)
    second = routing.text_layer_verdict(pdf)

    assert first == second and len(calls) == 1


def test_a_file_replaced_under_the_same_name_is_inspected_again(tmp_path, monkeypatch):
    """Staging directories get reused. Answering from cache about a file that
    has since been replaced would be worse than not caching at all."""
    from magi.ingest import textlayer

    pdf = tmp_path / "doc.pdf"
    _prose_pdf(pdf)
    calls = []
    real_inspect = textlayer.inspect
    monkeypatch.setattr(textlayer, "inspect",
                        lambda p: (calls.append(p), real_inspect(p))[1])

    routing.text_layer_verdict(pdf)
    _blank_pdf(pdf)                      # same name, different bytes
    routing.text_layer_verdict(pdf)

    assert len(calls) == 2


def test_auto_still_answers_what_can_run_here_by_itself(tmp_path, monkeypatch):
    """The shared router says what *should* run; whether the tooling exists is
    still auto's own question, because auto has no ladder to fall down."""
    from magi.ingest import auto

    monkeypatch.setattr(auto.shutil, "which", lambda _n: None)
    route, why = auto.classify(_blank_pdf(tmp_path / "scan.pdf"), {})

    assert route == "skip"
    assert "mineru_api_token" in why and "Ollama" in why
