"""Contracts for the batch commands — the human gate itself.

The two that matter most:

* nothing reaches ``raw/`` while any item in its batch is undecided, and
* rejecting an item requeues it one rung down without anyone re-submitting it.

Nothing else in this repo has either shape, so nothing else covers them.
"""

import pathlib
import re
import shutil
import types

import pytest

from magi.ingest import batch, image_refs, ledger
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
    def fake(route, entry, staging, topic=None):
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

    def fake(route, entry, staging, topic=None):
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


def test_committing_one_batch_commits_only_that_batch(ws, monkeypatch):
    """`--batch B --commit` reads as "land the batch I was just looking at".
    The flag narrowed the listing and was then dropped on the way to the
    commit, so every fully-decided batch went into `raw/` — and `raw/` is
    ORIGINAL, so doing more than was asked is the one direction this cannot
    fail in."""
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="a")
    batch.main(["run"])
    first = ledger.list_batches(ws)[0]
    ledger.enqueue(ws, source_type="arxiv", value="b")
    batch.main(["run"])
    second = [b for b in ledger.list_batches(ws) if b != first][0]

    for batch_id in (first, second):
        for item in ledger.load_batch(ws, batch_id):
            batch.main(["decide", "--item", item.item_id, "--decision", "approve"])

    batch.main(["review", "--batch", second, "--commit"])

    assert not any(i.committed_path for i in ledger.load_batch(ws, first)), \
        "a batch nobody asked about was committed"
    assert all(i.committed_path for i in ledger.load_batch(ws, second))


def test_committing_a_batch_that_is_not_there_says_so(ws, monkeypatch):
    _stub_route(monkeypatch, ws)
    ledger.enqueue(ws, source_type="arxiv", value="a")
    batch.main(["run"])

    assert batch.main(["review", "--batch", "b-nope", "--commit"]) == 1


def test_staged_images_travel_with_the_document(ws, monkeypatch):
    """A committed page whose figures stayed in staging is a page of broken links."""
    def fake(route, entry, staging, topic=None):
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

    def fake(route, entry, staging, topic=None):
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
    def fake(route, entry, staging, topic=None):
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
# The document itself, which had no collision check at all
# --------------------------------------------------------------------------

def _two_docs_one_name(ws, monkeypatch, bodies):
    """Two queued sources whose conversions land on the same filename."""
    def fake(route, entry, staging, topic=None):
        staging.mkdir(parents=True, exist_ok=True)
        md = staging / "a-paper.md"
        md.write_text(f"---\ntitle: T\n---\n\n{bodies[entry.value]}\n" + "word " * 300,
                      encoding="utf-8")
        return ConversionResult(success=True, markdown_path=str(md))

    monkeypatch.setattr(batch, "_run_route", fake)
    monkeypatch.setattr(batch, "_resolve_topic", lambda explicit: ws)
    monkeypatch.setattr(batch.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="", stderr=""))

    for value in bodies:
        ledger.enqueue(ws, source_type="arxiv", value=value)
    batch.main(["run"])
    for item in ledger.load_batch(ws, ledger.list_batches(ws)[0]):
        batch.main(["decide", "--item", item.item_id, "--decision", "approve"])
    batch.main(["commit"])


def test_a_second_document_cannot_overwrite_the_first(ws, monkeypatch, capsys):
    """The same hazard the image copy has guarded against for a while, one
    level up and far more expensive: `raw/` is ORIGINAL, so the document that
    loses this race is gone. A v1/v2 re-ingest, two papers sharing a title, or
    a route that does not namespace its filenames all land here.

    Keeping both and naming which is which beats refusing the commit: a
    refused item is approved forever with nowhere to go."""
    _two_docs_one_name(ws, monkeypatch, {"a": "BODY-A", "b": "BODY-B"})

    papers = ws / "raw" / "papers"
    survived = sorted(p.read_text(encoding="utf-8").split("\n\n")[1].split("\n")[0]
                      for p in papers.glob("*.md"))
    assert survived == ["BODY-A", "BODY-B"], "one document overwrote the other"
    assert (papers / "a-paper.md").is_file()          # the first keeps the plain name
    out = capsys.readouterr().out
    assert "already exists with different content" in out


def test_a_byte_identical_document_is_not_a_collision(ws, monkeypatch, capsys):
    """Re-converting the same source is not a conflict — it lands on itself."""
    _two_docs_one_name(ws, monkeypatch, {"a": "SAME", "b": "SAME"})

    papers = ws / "raw" / "papers"
    assert [p.name for p in papers.glob("*.md")] == ["a-paper.md"]
    assert "already exists" not in capsys.readouterr().out


def test_the_renamed_document_is_what_the_ledger_records(ws, monkeypatch):
    """Whatever name the document ended up under is the one the audit trail and
    the finalize pass have to point at, or the commit is recorded against a
    file that is not there."""
    _two_docs_one_name(ws, monkeypatch, {"a": "BODY-A", "b": "BODY-B"})

    for item in ledger.load_batch(ws, ledger.list_batches(ws)[0]):
        assert pathlib.Path(item.committed_path).is_file()


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


def _wants_images(ws, monkeypatch):
    """Opt this workspace into figure export, and stand in it.

    Exporting is off by default now, so a test about *where the figures land*
    has to ask for figures first, or it is a test about nothing.
    """
    (ws / "config.yaml").write_text("ingest:\n  textlayer_images: true\n",
                                    encoding="utf-8")
    monkeypatch.chdir(ws)


def test_a_committed_textlayer_document_still_finds_its_figures(ws, tmp_path, monkeypatch):
    """The whole defect, end to end: convert, commit, delete staging, look again.

    Every other test here calls the rewriting helper directly and so would not
    notice the route quietly ceasing to call it — which is precisely how the
    original bug looked from the outside: a route that reported success and a
    document whose figures were fine right up until the moment they were not.
    """
    pytest.importorskip("pymupdf4llm")
    from magi.ingest import gates

    _wants_images(ws, monkeypatch)
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

    def fake(route, entry, staging, topic=None):
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


# --------------------------------------------------------------------------
# what the text-layer route does about figures
# --------------------------------------------------------------------------

def _captioned_pdf(path):
    """A prose document whose figures are captioned, the way papers are.

    `_prose_pdf_with_figures` deliberately is not: it exists to exercise the
    *object* exporter, which does not care about captions. The crop does — the
    caption is its anchor — so a test of cropping needs a document that has
    them, or it passes while measuring nothing.
    """
    pymupdf = pytest.importorskip("pymupdf")
    prose = ("Cohort {n} diverged from the projections of the preceding year, "
             "and the discrepancy is examined against regional baseline {n}. ")
    doc = pymupdf.open()
    for page_no in range(4):
        page = doc.new_page()
        body = "".join(prose.format(n=page_no * 9 + i) for i in range(9))
        page.insert_textbox(pymupdf.Rect(60, 60, 540, 300),
                            f"Section {page_no + 1}\n\n" + body, fontsize=10)
        if page_no in (1, 3):
            page.draw_rect(pymupdf.Rect(120, 340, 480, 600),
                           color=(0, 0, 0), fill=(0.2, 0.4, 0.8))
            page.insert_textbox(
                pymupdf.Rect(120, 610, 480, 660),
                f"Figure {1 if page_no == 1 else 2}: Adoption against the "
                "regional baseline.", fontsize=9)
    doc.save(str(path))
    doc.close()
    return path


def _convert(pdf, staging, title="Institutional Adoption"):
    entry = types.SimpleNamespace(value=str(pdf), title=title,
                                  route="textlayer", source_type="file",
                                  retry_of=None, req_id="r1")
    return batch._run_route("textlayer", entry, staging)


def test_the_textlayer_route_crops_figures_by_caption(ws, tmp_path, monkeypatch):
    """The route used to export no figures at all, because its only offer was
    `write_images=True` — every embedded image *object*, inlined. Measured on a
    real 23-page paper carrying 4 figures: 117 files, 102 under 200x200, the
    smallest 301x24 and 40x24, single display equations rendered as pictures.

    Cropping by caption anchor is a different question with a different answer,
    and it is the one a reader is asking. It is the same extractor the OCR rung
    has always used; nothing about it was ever OCR-specific.
    """
    pytest.importorskip("pymupdf4llm")
    monkeypatch.chdir(ws)                    # no workspace opt-in: the default

    pdf = _captioned_pdf(tmp_path / "survey.pdf")
    result = _convert(pdf, tmp_path / "staging" / "item")
    assert result.success, result.errors

    assert result.images_dir, "no figures were exported"
    files = sorted(pathlib.Path(result.images_dir).iterdir())
    assert len(files) == 2, [f.name for f in files]

    body = pathlib.Path(result.markdown_path).read_text(encoding="utf-8")
    assert body.count("![") == 2
    for target in image_refs.iter_targets(body):
        assert image_refs.is_portable(target), target


def test_a_cropped_figure_lands_beside_its_own_caption(ws, tmp_path, monkeypatch):
    """Placement is the whole reason this is done page by page. Searched over a
    whole paper, "Figure 2" first matches the sentence in the body that
    mentions Figure 2, and the image lands paragraphs away from the figure."""
    pytest.importorskip("pymupdf4llm")
    monkeypatch.chdir(ws)

    pdf = _captioned_pdf(tmp_path / "survey.pdf")
    result = _convert(pdf, tmp_path / "staging" / "item")
    lines = pathlib.Path(result.markdown_path).read_text(encoding="utf-8").splitlines()

    for n, line in enumerate(lines):
        if line.startswith("!["):
            following = "\n".join(lines[n + 1:n + 4])
            assert re.search(r"Figure\s*\d", following), following


def test_what_happened_to_the_figures_is_always_said(ws, tmp_path, monkeypatch):
    """"Eight figures, all captioned" and "no figures found" are both facts the
    reviewer needs, and only one of them means something went wrong. A document
    that quietly has no figures is the failure this ladder exists to avoid,
    pointed at pictures instead of formulas."""
    pytest.importorskip("pymupdf4llm")
    monkeypatch.chdir(ws)

    for pdf, expected in ((_captioned_pdf(tmp_path / "with.pdf"), "2 figure(s)"),
                          (_prose_pdf_with_figures(tmp_path / "without.pdf"),
                           "no figures found")):
        result = _convert(pdf, tmp_path / "staging" / pdf.stem)
        said = [f for f in result.findings if f.code == "figures"]
        assert len(said) == 1, [f.code for f in result.findings]
        assert said[0].severity == "info"     # a fact, not a fault
        assert expected in said[0].detail, said[0].detail


def test_an_uncaptioned_document_exports_nothing_rather_than_guessing(
        ws, tmp_path, monkeypatch):
    """The anchor is caption text. Without one there is no way to tell a figure
    from a rule or a logo, and inventing figures is worse than reporting none —
    which is exactly what the object exporter did."""
    pytest.importorskip("pymupdf4llm")
    monkeypatch.chdir(ws)

    pdf = _prose_pdf_with_figures(tmp_path / "survey.pdf")
    result = _convert(pdf, tmp_path / "staging" / "item")

    assert result.images_dir is None
    assert "![](" not in pathlib.Path(result.markdown_path).read_text(encoding="utf-8")


def test_the_opt_in_still_exports_every_image_object(ws, tmp_path, monkeypatch):
    """The flag now selects between two answers rather than switching one off,
    and it is worth keeping for a document whose figures carry no captions —
    there the crop has nothing to anchor on and the object exporter, for all
    its noise, is the only one that returns anything at all."""
    pytest.importorskip("pymupdf4llm")
    _wants_images(ws, monkeypatch)

    pdf = _prose_pdf_with_figures(tmp_path / "survey.pdf")
    result = _convert(pdf, tmp_path / "staging" / "item")

    assert result.images_dir and pathlib.Path(result.images_dir).is_dir()
    body = pathlib.Path(result.markdown_path).read_text(encoding="utf-8")
    assert "![](images/" in body
    said = next(f for f in result.findings if f.code == "figures")
    assert "image object" in said.detail


def _table_pdf(path, *, ruling="booktabs"):
    """A page whose only structure is a table, in the style papers actually use."""
    pymupdf = pytest.importorskip("pymupdf")
    # Enough prose that the routing gate calls this a text-layer document at
    # all: a page carrying only a table is, correctly, not one.
    prose = ("Respondents in cohort {n} were contacted twice and the second "
             "contact is recorded separately, so the totals below count "
             "correspondence rather than people. ")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(60, 40, 540, 400),
                        "Sampling Outcomes\n\n"
                        + "".join(prose.format(n=i) for i in range(12)), fontsize=10)
    rows = [("Category", "Kept", "Excluded"), ("Correspondence", "412", "38"),
            ("Interviews", "119", "7"), ("Field notes", "58", "12")]
    y = 440
    for n, row in enumerate(rows):
        for x, cell in zip((70, 250, 400), row):
            page.insert_text((x, y), cell, fontsize=10)
        if ruling == "booktabs" and n == 0:
            page.draw_line((60, y + 6), (540, y + 6))
        y += 30
    if ruling == "booktabs":
        page.draw_line((60, 428), (540, 428))
        page.draw_line((60, y - 24), (540, y - 24))
    doc.save(str(path))
    doc.close()
    return path


@pytest.mark.parametrize("ruling", ["booktabs", "none"])
def test_a_table_survives_the_textlayer_route_as_a_table(ws, tmp_path, monkeypatch, ruling):
    r"""ROADMAP B2 says this route flattens tables into a line of prose, with
    `\hline` leaking as the literal word `height`.

    It does not reproduce on pymupdf4llm 1.28.2 — not on a fully ruled table,
    not on booktabs, not with no rules at all, and not on a real 23-page paper
    whose 10 tables all came back as Markdown tables (285 pipe rows against a
    205-row census). Whatever triggered the original observation is narrower
    than "this route, tables". So the current behaviour is pinned here instead
    of assumed: if a future version regresses to the flattening, this is what
    says so, rather than a note nobody re-measures.
    """
    pytest.importorskip("pymupdf4llm")
    monkeypatch.chdir(ws)

    pdf = _table_pdf(tmp_path / f"survey-{ruling}.pdf", ruling=ruling)
    entry = types.SimpleNamespace(value=str(pdf), title="Sampling", route="textlayer",
                                  source_type="file", retry_of=None, req_id="r1")
    result = batch._run_route("textlayer", entry, tmp_path / "staging" / "item")
    assert result.success, result.errors

    body = pathlib.Path(result.markdown_path).read_text(encoding="utf-8")
    assert "|Correspondence|412|38|" in body.replace(" ", "")
    assert "height" not in body                 # the \hline leak in the report


def test_a_dropped_table_is_still_caught_if_it_ever_happens(ws):
    """The gate that would catch a regression, exercised directly.

    Pinning the good behaviour above only helps while the conversion is good.
    This is the other half: source has tables, output has no table markup, and
    the item is flagged rather than approved on the strength of a caption that
    survived.
    """
    from magi.ingest import gates

    flat = ("# Sampling Outcomes\n\nTABLE I. Response rates.\n\n"
            "Category Kept Excluded heightCorrespondence 412 38 Interviews 119 7\n")
    codes = {f.code for f in gates.run_all(flat, source_chars=len(flat),
                                           source_tables=1, source_rows=4)}
    assert "tables-dropped" in codes
