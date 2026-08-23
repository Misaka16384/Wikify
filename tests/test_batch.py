"""Contracts for the batch commands — the human gate itself.

The two that matter most:

* nothing reaches ``raw/`` while any item in its batch is undecided, and
* rejecting an item requeues it one rung down without anyone re-submitting it.

Nothing else in this repo has either shape, so nothing else covers them.
"""

import pathlib
import shutil
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


def test_two_documents_cannot_overwrite_each_others_figures(ws, monkeypatch, capsys):
    """raw/papers/images/ is shared by the library, so this copy is where a
    name collision between two papers does its damage: the second write wins,
    nothing errors, nothing goes missing, and one paper quietly starts showing
    the other's picture.

    Routes are supposed to namespace their filenames. This is the check that
    says so out loud when one of them does not — including the route nobody has
    written yet, which is the point of putting the check here rather than in
    each route."""
    bodies = {"a": b"PICTURE-A", "b": b"PICTURE-B"}

    def fake(route, entry, staging):
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "images").mkdir()
        (staging / "images" / "fig1.png").write_bytes(bodies[entry.value])
        md = staging / f"doc-{entry.value}.md"
        md.write_text('---\ntitle: T\n---\n\n![](images/fig1.png)\n' + "word " * 300,
                      encoding="utf-8")
        return ConversionResult(success=True, markdown_path=str(md),
                                images_dir=str(staging / "images"))

    monkeypatch.setattr(batch, "_run_route", fake)
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    monkeypatch.setattr(batch.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="", stderr=""))

    ledger.enqueue(ws, source_type="arxiv", value="a")
    ledger.enqueue(ws, source_type="arxiv", value="b")
    batch.main(["run"])
    for item in ledger.load_batch(ws, ledger.list_batches(ws)[0]):
        batch.main(["decide", "--item", item.item_id, "--decision", "approve"])
    batch.main(["commit"])

    # The first copy is intact — the second did not silently replace it.
    assert (ws / "raw" / "papers" / "images" / "fig1.png").read_bytes() in bodies.values()
    out = capsys.readouterr().out
    assert "fig1.png" in out and "overwritten" in out


def test_an_identical_image_from_two_documents_is_not_a_collision(ws, monkeypatch, capsys):
    """Same bytes under the same name is two documents sharing a figure, which
    is fine and must not be reported as a problem."""
    def fake(route, entry, staging):
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "images").mkdir()
        (staging / "images" / "shared.png").write_bytes(b"SAME")
        md = staging / f"doc-{entry.value}.md"
        md.write_text('---\ntitle: T\n---\n\n![](images/shared.png)\n' + "word " * 300,
                      encoding="utf-8")
        return ConversionResult(success=True, markdown_path=str(md),
                                images_dir=str(staging / "images"))

    monkeypatch.setattr(batch, "_run_route", fake)
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    monkeypatch.setattr(batch.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="", stderr=""))

    ledger.enqueue(ws, source_type="arxiv", value="a")
    ledger.enqueue(ws, source_type="arxiv", value="b")
    batch.main(["run"])
    for item in ledger.load_batch(ws, ledger.list_batches(ws)[0]):
        batch.main(["decide", "--item", item.item_id, "--decision", "approve"])
    batch.main(["commit"])

    assert (ws / "raw" / "papers" / "images" / "shared.png").read_bytes() == b"SAME"
    assert "overwritten" not in capsys.readouterr().out


# --------------------------------------------------------------------------
# The text-layer route's image references
# --------------------------------------------------------------------------

def test_textlayer_images_stop_being_absolute_staging_paths(tmp_path):
    """`pymupdf4llm.to_markdown` references each image by the directory string
    it was handed. Handing it staging — which we must, or the files land in the
    working directory — put an absolute temp path in every reference. It
    resolved right up until commit deleted staging, and then every figure in
    the document went dark."""
    images = tmp_path / "images"
    images.mkdir()
    (images / "survey.pdf-0001-01.png").write_bytes(b"PNG")
    md = f"Prose.\n\n![]({images}/survey.pdf-0001-01.png)\n"

    out = batch._localize_textlayer_images(md, images, "a-survey")

    assert "![](images/a-survey-survey.pdf-0001-01.png)" in out
    assert str(images) not in out
    assert (images / "a-survey-survey.pdf-0001-01.png").is_file()


def test_textlayer_rewriting_handles_either_separator(tmp_path):
    """The path is the machine's, not ours: `to_markdown` joins its directory
    argument with a forward slash, and on Windows that argument has backslashes
    in it, so the reference is a mix of both."""
    for n, style in enumerate(("forward", "native", "all-forward")):
        images = tmp_path / str(n) / "images"
        images.mkdir(parents=True)
        (images / "x.png").write_bytes(b"PNG")
        joined = {"forward": f"{images}/x.png",
                  "native": str(images / "x.png"),
                  "all-forward": f"{str(images).replace(chr(92), '/')}/x.png"}[style]
        out = batch._localize_textlayer_images(f"![]({joined})", images, "doc")
        assert out == "![](images/doc-x.png)", style


def test_textlayer_figures_carry_the_document_slug(tmp_path):
    """Two papers whose sources are both called paper.pdf produce the same
    `paper.pdf-0001-01.png`, and land in the same shared images directory."""
    names = []
    for slug in ("first-paper", "second-paper"):
        images = tmp_path / slug / "images"
        images.mkdir(parents=True)
        (images / "paper.pdf-0001-01.png").write_bytes(b"PNG")
        batch._localize_textlayer_images(
            f"![]({images}/paper.pdf-0001-01.png)", images, slug)
        names.append({f.name for f in images.iterdir()})
    assert names[0].isdisjoint(names[1])


def _prose_pdf_with_figures(path):
    """A born-digital, maths-free paper with two real figures.

    Deliberately built the long way rather than checked in as a fixture: the
    text-layer gate measures characters per page and enumerates fonts, so a PDF
    that merely *contains* the right bytes is not enough — it has to actually
    read like a paper or the route refuses it before any of this is reached.
    """
    pymupdf = pytest.importorskip("pymupdf")
    # Varied on purpose. An earlier version filled every page with one sentence
    # repeated fourteen times, which the repetition gate then reported — and it
    # was right to: a document that really is one paragraph eighty-four times
    # over is a converter that lost its place. Papers do not read like that, so
    # neither should the paper this pretends to be.
    prose = ("Cohort {n} diverged from the projections of the preceding year, "
             "and the discrepancy is examined against regional baseline {n}. ")
    doc = pymupdf.open()
    for page_no in range(6):
        page = doc.new_page()
        body = "".join(prose.format(n=page_no * 14 + i) for i in range(14))
        page.insert_textbox(pymupdf.Rect(60, 60, 540, 380),
                            f"Section {page_no + 1}\n\n" + body, fontsize=10)
        if page_no in (1, 3):
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 260))
            pix.set_rect(pix.irect, (30, 90 + page_no * 30, 200))
            page.insert_image(pymupdf.Rect(60, 400, 540, 700), pixmap=pix)
    doc.save(str(path))
    doc.close()
    return path


def test_a_committed_textlayer_document_still_finds_its_figures(ws, tmp_path, monkeypatch):
    """The whole defect, end to end: convert, commit, delete staging, look again.

    Every other test here calls the rewriting helper directly and so would not
    notice the route quietly ceasing to call it — which is precisely how the
    original bug looked from the outside: a route that reported success and a
    document whose figures were fine right up until the moment they were not.
    """
    pytest.importorskip("pymupdf4llm")
    from magi.ingest import gates

    pdf = _prose_pdf_with_figures(tmp_path / "survey.pdf")
    entry = types.SimpleNamespace(value=str(pdf), title="Institutional Adoption",
                                  route="textlayer", source_type="file",
                                  retry_of=None, req_id="r1")
    staging = tmp_path / "staging" / "item"
    result = batch._run_route("textlayer", entry, staging)
    assert result.success, result.errors

    md = pathlib.Path(result.markdown_path)
    assert gates.run_all(md.read_text(encoding="utf-8"),
                         images_dir=result.images_dir) == []

    # Commit: the document and its images move, and neither is rewritten.
    dest_dir = ws / "raw" / "papers"
    (dest_dir / "images").mkdir(parents=True, exist_ok=True)
    shutil.copy2(md, dest_dir / md.name)
    for image in pathlib.Path(result.images_dir).iterdir():
        shutil.copy2(image, dest_dir / "images" / image.name)
    shutil.rmtree(staging.parent)

    committed = (dest_dir / md.name).read_text(encoding="utf-8")
    assert "![](images/" in committed          # there were figures to lose
    assert gates.run_all(committed, images_dir=dest_dir / "images") == []


def test_a_textlayer_document_recovers_its_arxiv_identity(ws, tmp_path):
    """Four of the five routes recover the arXiv id from the filename and this
    one did not, which is not a cosmetic difference: the radar fingerprints a
    library by arxiv_id, so a paper ingested here was invisible to it and kept
    coming back as a fresh candidate. MinerU carries a comment about having had
    exactly this bug — fixing it in one route and not looking at the rest is
    how one bug becomes four."""
    pytest.importorskip("pymupdf4llm")

    pdf = _prose_pdf_with_figures(tmp_path / "2401.00506.pdf")
    entry = types.SimpleNamespace(value=str(pdf), title="A Survey", route="textlayer",
                                  source_type="file", retry_of=None, req_id="r1")
    result = batch._run_route("textlayer", entry, tmp_path / "staging" / "item")

    assert result.success, result.errors
    body = pathlib.Path(result.markdown_path).read_text(encoding="utf-8")
    assert "arxiv_id: '2401.00506'" in body
    assert "arxiv_url: https://arxiv.org/abs/2401.00506" in body


def test_a_textlayer_document_with_no_images_is_left_alone(tmp_path):
    md = "Prose with no figures at all.\n"
    assert batch._localize_textlayer_images(md, tmp_path / "images", "doc") == md


def test_the_ocr_route_reports_its_images_directory(ws, monkeypatch, tmp_path):
    """The OCR route crops its own figures and was the only route that never
    told the caller where it put them, so the image gates never ran on the one
    route that generates image references from scratch."""
    def fake_run(argv, **kw):
        out = pathlib.Path(argv[argv.index("-o") + 1])
        (out / "images").mkdir(parents=True, exist_ok=True)
        (out / "images" / "doc-fig_p001_1.png").write_bytes(b"PNG")
        (out / "doc.md").write_text("![](images/doc-fig_p001_1.png)", encoding="utf-8")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(batch.subprocess, "run", fake_run)
    entry = types.SimpleNamespace(value="x.pdf", title=None, route="ocr",
                                  source_type="file", retry_of=None, req_id="r")
    result = batch._run_route("ocr", entry, tmp_path / "staging")

    assert result.success and result.images_dir
    assert pathlib.Path(result.images_dir).is_dir()


# --------------------------------------------------------------------------
# Reject means "try the next rung down"
# --------------------------------------------------------------------------

def test_a_local_pdf_starts_on_the_free_route(ws, tmp_path):
    """A4. `_starting_route` sent every non-arXiv source to `mineru`, and
    because `textlayer` sits *above* `mineru` on the ladder nothing could fall
    back up to it — so a local PDF could not reach the free route at all. Of
    758 items in the library this was built for, 567 carry a stored PDF."""
    pymupdf = pytest.importorskip("pymupdf")
    prose = ("This section reviews the literature on institutional adoption "
             "and the outcomes reported across the surveyed programmes. ")
    doc = pymupdf.open()
    for n in range(6):
        doc.new_page().insert_textbox(pymupdf.Rect(60, 60, 540, 700),
                                      f"Section {n}\n\n" + prose * 14, fontsize=10)
    pdf = tmp_path / "survey.pdf"
    doc.save(str(pdf))
    doc.close()

    entry = types.SimpleNamespace(route=None, source_type="file", value=str(pdf))
    route, why = batch._starting_route(entry)

    assert route == "textlayer", why
    # And the ladder below it is intact, so a wrong guess still degrades.
    assert ledger.next_rung("textlayer") == "mineru"


def test_a_retry_keeps_the_rung_it_was_queued_for(ws):
    """A forced route is how "reject" means "try the next one down"; the
    router must not overrule it."""
    entry = types.SimpleNamespace(route="ocr", source_type="file", value="x.pdf")
    route, why = batch._starting_route(entry)
    assert route == "ocr" and why


def test_something_already_text_is_refused_with_a_usable_sentence(ws, tmp_path):
    """The ladder converts documents. A Markdown file needs filing, not
    converting, and saying so beats handing it to a PDF reader."""
    note = tmp_path / "note.md"
    note.write_text("# already text\n", encoding="utf-8")
    entry = types.SimpleNamespace(route=None, source_type="file", value=str(note),
                                  title=None, retry_of=None, req_id="r")
    route, _ = batch._starting_route(entry)
    result = batch._run_route(route, entry, tmp_path / "staging")

    assert route == "add"
    assert not result.success
    assert "ingest add" in "; ".join(result.errors)


def test_a_rejected_item_is_requeued_as_what_it_actually_is(ws, monkeypatch):
    """A7. The requeue named "arxiv" for everything, so a rejected local PDF
    came back as an arXiv paper whose identifier was a file path. Nothing broke
    — the route is passed explicitly, so nothing re-derived it — but the ledger
    recorded something untrue, and the next code to branch on source_type would
    have inherited it."""
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="file", value="D:/Zotero/storage/AB/paper.pdf",
                   route="textlayer")
    batch.main(["run"])
    item = ledger.load_batch(ws, ledger.list_batches(ws)[0])[0]
    assert item.source_type == "file"

    batch.main(["decide", "--item", item.item_id, "--decision", "reject"])

    requeued = ledger.pending(ws)
    assert len(requeued) == 1
    assert requeued[0].source_type == "file"
    assert requeued[0].route == "mineru"


def test_a_record_written_before_the_type_was_stored_is_inferred(ws, monkeypatch):
    """Old batch logs have no source_type. Inferring it is a guess; writing
    "arxiv" over a file path was a guess already made and recorded as fact."""
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="", value="D:/lib/paper.pdf", route="textlayer")
    batch.main(["run"])
    item = ledger.load_batch(ws, ledger.list_batches(ws)[0])[0]
    assert item.source_type == ""

    batch.main(["decide", "--item", item.item_id, "--decision", "reject"])

    assert ledger.pending(ws)[0].source_type == "file"


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
