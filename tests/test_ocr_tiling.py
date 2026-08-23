"""Reading a page a tile at a time, and knowing when to.

The measurement behind all of this, on a 49-row table page with
`glm-ocr:q8_0` at temperature 0:

    whole page          24 of 49 rows, output stops mid-sentence
    left and right      49 of 49
    3 horizontal bands  40 of 49   (a boundary cuts rows in half)

The stop is not a budget — `num_ctx` at 16384/32768/65536 and `num_predict` at
8192 all give byte-identical output. The model emits end-of-sequence having
covered about half the table, so the only lever is how much page one image
holds. These pin the parts of that which are checkable without a GPU.
"""


import pytest

from magi.ingest.ocr import tiler

pymupdf = pytest.importorskip("pymupdf", reason="PyMuPDF is a hard dependency")
Image = pytest.importorskip("PIL.Image", reason="Pillow ships with the OCR rung")


@pytest.fixture
def page_png(tmp_path):
    from PIL import Image as PILImage

    img = PILImage.new("RGB", (1200, 1600), "white")
    path = tmp_path / "page.png"
    img.save(path)
    return path


# --------------------------------------------------------------------------
# Cutting
# --------------------------------------------------------------------------

def test_two_tiles_cover_the_page_and_overlap(page_png):
    from PIL import Image as PILImage

    parts = tiler.tile(page_png, 2, 1)
    assert len(parts) == 2

    widths = []
    for p in parts:
        with PILImage.open(p) as im:
            widths.append(im.size[0])
            assert im.size[1] == 1600          # full height, this is a column cut
    # Together they are wider than the page: that surplus is the overlap, and
    # it is what keeps a row sitting on the seam whole in one of the two.
    assert sum(widths) > 1200


def test_tiles_are_written_losslessly(page_png):
    """The engine's `_preprocess_image` encodes JPEG on the way out. Writing
    JPEG here too would compress the same pixels twice — and it is not
    theoretical: the doubly-encoded right-hand tile of a measured page came
    back with 146 table rows where 25 exist, the model inventing rows off
    degraded pixels, while the same crop encoded once returned all 25."""
    for p in tiler.tile(page_png, 2, 1):
        assert p.suffix == ".png"


def test_tiles_keep_the_pages_own_pixels(page_png):
    """A tile exists to give the model less *page*, not a smaller picture of
    the same page. Shrinking the image instead makes it write more rows and
    read them wrong — measured: 0.7 MP produced 56 rows where 49 exist, and
    only 12 were right."""
    from PIL import Image as PILImage

    with PILImage.open(tiler.tile(page_png, 2, 1)[0]) as im:
        assert im.size[1] == 1600          # not resampled


def test_a_two_by_two_split_gives_four_tiles_in_reading_order(page_png):
    from PIL import Image as PILImage

    parts = tiler.tile(page_png, 2, 2)
    assert len(parts) == 4

    boxes = []
    for p in parts:
        with PILImage.open(p) as im:
            boxes.append(im.size)
    assert all(w < 1200 and h < 1600 for w, h in boxes)


def test_tiling_writes_only_into_the_directory_it_was_given(page_png, tmp_path):
    out = tmp_path / "scratch"
    parts = tiler.tile(page_png, 2, 1, out_dir=out)
    assert all(p.parent == out for p in parts)


# --------------------------------------------------------------------------
# Stitching
# --------------------------------------------------------------------------

def test_the_overlap_is_not_transcribed_twice():
    a = "row one\nrow two\nrow three"
    b = "row three\nrow four"
    assert tiler.stitch([a, b]).count("row three") == 1


def test_a_repeat_later_in_the_document_is_kept():
    """Papers do repeat themselves — a column header, a recurring caption. Only
    the seam is de-duplicated; deleting elsewhere would be the converter
    quietly editing the document."""
    a = "header\nrow one"
    b = "row two\nheader\nrow three"
    assert tiler.stitch([a, b]).count("header") == 2


def test_stitching_one_part_changes_nothing():
    assert tiler.stitch(["only this"]) == "only this"


def test_empty_parts_are_skipped_not_joined_as_blanks():
    assert tiler.stitch(["", "  ", "content"]) == "content"


def test_stitching_nothing_is_empty_not_an_error():
    assert tiler.stitch([]) == ""


# --------------------------------------------------------------------------
# Deciding which pages get tiled
# --------------------------------------------------------------------------

def _pdf(tmp_path, name, *, with_table):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(60, 40, 540, 300),
                        "Sampling outcomes. " * 30, fontsize=10)
    if with_table:
        rows = [("Category", "Kept"), ("Correspondence", "412"), ("Notes", "58")]
        y = 360
        for n, row in enumerate(rows):
            for x, cell in zip((70, 300), row):
                page.insert_text((x, y), cell, fontsize=10)
            page.draw_line((60, y + 6), (540, y + 6))
            y += 30
        for x in (60, 290, 540):
            page.draw_line((x, 348), (x, y - 24))
    path = tmp_path / name
    doc.save(path)
    doc.close()
    return path


def test_a_page_with_a_table_is_selected(tmp_path):
    assert tiler.pages_with_tables(_pdf(tmp_path, "t.pdf", with_table=True)) == {1}


def test_a_page_without_one_is_not(tmp_path):
    """Tiling every page would cost each of them roughly twice the time, and on
    the one measured page that melts down it turned a 559-character answer into
    a 32,785-character repetition loop. The quiet default is not to tile."""
    assert tiler.pages_with_tables(_pdf(tmp_path, "p.pdf", with_table=False)) == set()


def test_a_missing_or_unreadable_pdf_means_no_tiling_not_a_crash(tmp_path):
    """A scan has no text layer either, and gets read whole exactly as before.
    Being wrong here costs accuracy on one page; crashing costs the run."""
    assert tiler.pages_with_tables(tmp_path / "nope.pdf") == set()

    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.7\nnot really\n")
    assert tiler.pages_with_tables(broken) == set()


# --------------------------------------------------------------------------
# What the engine does with it
# --------------------------------------------------------------------------

def _engine(monkeypatch, answers):
    """An OCREngine whose model is a list of canned answers."""
    from magi.ingest.ocr.ocr_engine import OCREngine

    eng = OCREngine("glm-ocr:q8_0")
    seen = []

    def fake(image_path):
        seen.append(image_path)
        return answers[len(seen) - 1]

    monkeypatch.setattr(eng, "_transcribe", fake)
    return eng, seen


def test_a_tiled_page_calls_the_model_once_per_tile(page_png, monkeypatch):
    eng, seen = _engine(monkeypatch, ["left half", "right half"])
    result = eng.ocr_image(str(page_png), 1, tiles=(2, 1))

    assert len(seen) == 2
    assert result.success
    assert "left half" in result.markdown and "right half" in result.markdown


def test_an_untiled_page_calls_it_once_with_the_page_itself(page_png, monkeypatch):
    eng, seen = _engine(monkeypatch, ["the whole page"])
    eng.ocr_image(str(page_png), 1)

    assert seen == [str(page_png)]


def test_tiles_of_one_by_one_are_not_tiling(page_png, monkeypatch):
    eng, seen = _engine(monkeypatch, ["the whole page"])
    eng.ocr_image(str(page_png), 1, tiles=(1, 1))

    assert seen == [str(page_png)]


def test_the_tiles_are_cleaned_up_afterwards(page_png, monkeypatch):
    """They are scratch, not output. Leaving them beside the page images means
    the figure extractor later finds four copies of every page."""
    eng, _ = _engine(monkeypatch, ["a", "b"])
    before = set(page_png.parent.iterdir())
    eng.ocr_image(str(page_png), 1, tiles=(2, 1))

    assert set(page_png.parent.iterdir()) == before


def test_tiles_are_cleaned_up_even_when_the_model_fails(page_png, monkeypatch):
    from magi.ingest.ocr.ocr_engine import OCREngine

    eng = OCREngine("glm-ocr:q8_0")
    monkeypatch.setattr(eng, "_transcribe",
                        lambda _p: (_ for _ in ()).throw(RuntimeError("ollama down")))
    before = set(page_png.parent.iterdir())

    result = eng.ocr_image(str(page_png), 1, tiles=(2, 1))

    assert not result.success
    assert set(page_png.parent.iterdir()) == before


def test_html_tables_are_converted_on_the_way_out(page_png, monkeypatch):
    eng, _ = _engine(monkeypatch, ["<table><tr><td>a</td><td>b</td></tr></table>"])
    result = eng.ocr_image(str(page_png), 1)

    assert "| a | b |" in result.markdown
    assert "<table" not in result.markdown


def test_the_retry_wrapper_carries_the_tiling_through(page_png, monkeypatch):
    """It was the retry wrapper the pipeline actually calls, so a `tiles`
    argument the wrapper dropped would have been a change that tested green and
    did nothing."""
    eng, seen = _engine(monkeypatch, ["a", "b"])
    eng.ocr_image_with_retry(str(page_png), 1, max_retries=0, tiles=(2, 1))

    assert len(seen) == 2


# --------------------------------------------------------------------------
# The prompt
# --------------------------------------------------------------------------

def test_the_glm_prompt_names_a_notation():
    """Seven prompts were measured and only three distinct outputs came back:
    "output EVERY row, do not stop early" is byte-identical to the old
    `Text Recognition:`. The words that do anything are Markdown and HTML —
    naming a notation is what unlocks the table at all."""
    from magi.ingest.ocr.ocr_engine import GLM_PROMPT, OCREngine

    assert "Markdown" in GLM_PROMPT
    for model in ("glm-ocr", "glm-ocr:q8_0", "glm-ocr-16k"):
        assert OCREngine(model)._build_ocr_prompt() == GLM_PROMPT


def test_the_old_prompt_is_gone_from_every_glm_entry():
    """`Text Recognition:` transcribed the captions of three pages carrying 151
    table rows and skipped every row. That was filed as a capability limit; it
    was the prompt."""
    from magi.ingest.ocr.ocr_engine import OCREngine

    for name, cfg in OCREngine.MODEL_CONFIGS.items():
        if name.startswith("glm-ocr"):
            assert cfg["prompt"] != "Text Recognition:", name


# --------------------------------------------------------------------------
# The cache
# --------------------------------------------------------------------------

def _agent():
    """A PDF2MarkdownAgent with nothing set up but the engine it reports on."""
    from magi.ingest.ocr.agent import PDF2MarkdownAgent
    from magi.ingest.ocr.ocr_engine import OCREngine

    agent = PDF2MarkdownAgent.__new__(PDF2MarkdownAgent)
    agent.ocr_engine = OCREngine("glm-ocr:q8_0")
    return agent


def test_the_cache_records_what_produced_it():
    """`temp/page_7.json` is keyed on the page number alone, and a page cached
    under the old prompt is the old answer. Replaying it would serve exactly
    the results this change exists to replace — a fix that works only for
    people who have never run the tool."""
    agent = _agent()
    agent._table_pages = set()
    recipe = agent._recipe(7)

    assert "glm-ocr:q8_0" in recipe
    assert "whole" in recipe


def test_a_tiled_page_and_a_whole_page_do_not_share_a_cache_entry():
    agent = _agent()
    agent._table_pages = {7}
    tiled = agent._recipe(7)
    agent._table_pages = set()

    assert tiled != agent._recipe(7)
    assert "2x1" in tiled


def test_changing_the_prompt_changes_the_recipe(monkeypatch):
    agent = _agent()
    agent._table_pages = set()
    before = agent._recipe(1)
    monkeypatch.setattr(agent.ocr_engine, "_build_ocr_prompt", lambda: "something else")

    assert agent._recipe(1) != before


def test_changing_the_model_changes_the_recipe():
    from magi.ingest.ocr.ocr_engine import OCREngine

    agent = _agent()
    agent._table_pages = set()
    before = agent._recipe(1)
    agent.ocr_engine = OCREngine("qwen3-vl")

    assert agent._recipe(1) != before
