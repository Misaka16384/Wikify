"""What belongs inside a figure's crop, and what does not.

Two defects, both found by putting the same page through this extractor and
through MinerU and looking at the two images side by side:

* **a four-panel figure came out as one panel.** The size thresholds were
  applied to each cluster on its own, and a panel of a stacked figure is small:
  0.56% of the page, or 35pt tall, or four dots. Three of the four were
  discarded before captions were considered, and the survivor inherited the
  whole figure's caption — so the output claimed to be Figure 1 and was a
  quarter of it.
* **a plot came out with both axis labels sliced off.** The rect is built from
  drawing boxes, and `E/t'`, `U/t'` and the tick values are text. A plot
  without its axes is close to unreadable.

The "85 of 86" already on record measured how many figures were *found*. It did
not measure whether the crop was complete, and those are different questions.
"""

import pytest

pymupdf = pytest.importorskip("pymupdf", reason="PyMuPDF is a hard dependency")

from magi.ingest import figures as fx  # noqa: E402


def _page(draw, *, caption="Figure 1: A schematic of the lattice.",
          extra_text=()):
    """One page: whatever `draw` puts on it, plus a caption underneath."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    draw(page)
    if caption:
        page.insert_textbox(pymupdf.Rect(72, 620, 540, 700), caption, fontsize=9)
    for rect, text in extra_text:
        page.insert_textbox(rect, text, fontsize=9)
    return doc, page


def _rects(page):
    return [f["rect"] for f in fx.detect_figures(page, abs(page.rect))]


# --------------------------------------------------------------------------
# A panel is not an independent graphic
# --------------------------------------------------------------------------

def test_a_small_panel_joins_the_figure_it_belongs_to():
    """Panel (a) is small enough to fail the standalone thresholds on its own.
    It is still part of Figure 1, and the crop has to contain it."""
    def draw(page):
        # a big panel that qualifies alone …
        page.draw_rect(pymupdf.Rect(100, 300, 500, 450), color=(0, 0, 0), width=2)
        # … and a small one above it, well under the area floor
        page.draw_circle(pymupdf.Point(130, 220), 22, color=(0, 0, 0), width=2)

    doc, page = _page(draw)
    rects = _rects(page)
    doc.close()

    assert len(rects) == 1, "the two panels are one figure, not two"
    assert rects[0].y0 <= 205, "the crop stops below the small panel"


def test_several_small_panels_all_join():
    """The measured figure had four panels and three were being dropped."""
    def draw(page):
        page.draw_rect(pymupdf.Rect(100, 320, 500, 430), color=(0, 0, 0), width=2)
        for y in (200, 250, 480):
            page.draw_circle(pymupdf.Point(130, y), 18, color=(0, 0, 0), width=2)

    doc, page = _page(draw)
    rects = _rects(page)
    doc.close()

    assert len(rects) == 1
    assert rects[0].y0 <= 190 and rects[0].y1 >= 490


def test_a_stray_mark_with_no_figure_under_the_caption_is_not_a_figure():
    """The thresholds still do their job: they decide whether something can
    stand alone. A page whose only graphic is a rule must not produce one."""
    def draw(page):
        page.draw_line(pymupdf.Point(100, 300), pymupdf.Point(500, 300),
                       color=(0, 0, 0), width=1)

    doc, page = _page(draw)
    rects = _rects(page)
    doc.close()

    assert rects == []


# --------------------------------------------------------------------------
# The text that is part of the figure
# --------------------------------------------------------------------------

def test_an_axis_label_beside_the_plot_is_inside_the_crop():
    """`E/t'` sits a few points clear of the drawing and is text, so it fell
    outside a rect built from drawing boxes."""
    def draw(page):
        page.draw_rect(pymupdf.Rect(200, 300, 500, 450), color=(0, 0, 0), width=2)

    # An axis label sits a few points clear of the plot, not a paragraph away.
    # Placed at that real distance: the text lands around x=170..188, a dozen
    # points short of the drawing at x=200.
    doc, page = _page(draw, extra_text=[
        (pymupdf.Rect(170, 292, 215, 312), "E / t'"),
    ])
    rects = _rects(page)
    doc.close()

    assert len(rects) == 1
    assert rects[0].x0 <= 172, "the axis label was cropped away"


def test_the_caption_is_not_pulled_into_the_image():
    """It is rendered as Markdown beside the figure; inside it as well would be
    the same words twice."""
    def draw(page):
        page.draw_rect(pymupdf.Rect(100, 300, 500, 450), color=(0, 0, 0), width=2)

    doc, page = _page(draw)
    rects = _rects(page)
    doc.close()

    assert len(rects) == 1
    assert rects[0].y1 < 620, "the crop reaches into the caption"


def test_a_paragraph_beside_a_figure_is_not_swallowed():
    """The reach is short and only short runs of text qualify — otherwise
    growing the crop would start eating the body of the paper."""
    prose = ("This paragraph sits close to the figure and is ordinary body "
             "text of the kind that runs beside a float, and it must stay "
             "outside the image no matter how near it falls.")

    def draw(page):
        page.draw_rect(pymupdf.Rect(100, 300, 400, 450), color=(0, 0, 0), width=2)

    doc, page = _page(draw, extra_text=[
        (pymupdf.Rect(410, 300, 560, 450), prose),
    ])
    rects = _rects(page)
    doc.close()

    assert len(rects) == 1
    assert rects[0].x1 < 430, "a paragraph was pulled into the figure"


# --------------------------------------------------------------------------
# The thresholds still mean something
# --------------------------------------------------------------------------

def test_the_standalone_thresholds_are_unchanged():
    """They were not loosened — they were moved from 'may this be part of a
    figure' to 'may this be a figure by itself'."""
    assert fx.MIN_AREA_FRAC == 0.012
    assert fx.MIN_DIM_PT == 40


def test_the_label_reach_is_shorter_than_a_line_of_prose():
    """A label is a few points clear of the plot; the next paragraph is a whole
    line away. That distance is the only thing separating them."""
    assert fx.LABEL_REACH_PT <= 20
    assert fx.LABEL_MAX_CHARS <= 60


# --------------------------------------------------------------------------
# The reference this writes has to be one
# --------------------------------------------------------------------------
#
# The alt text is the caption, and captions cite. `FIG. 1. Polynomial
# representation of Pauli operators [36].` is an ordinary caption; unescaped it
# closes the alt text at `[36]` and the whole line stops being an image
# reference. Measured on a real paper: eight figures cropped, eight placed, and
# only seven that any Markdown parser could find. The eighth rendered as the
# tail of its own caption followed by a literal `](images/....png)`.

def _figure(caption):
    return fx.Figure(page=1, index=1, label="Figure 1", caption=caption,
                     filename="p-f1.png", path="/tmp/p-f1.png")


def test_a_caption_that_cites_still_produces_a_reference():
    from magi.ingest import image_refs

    md = fx.figure_markdown(_figure("FIG. 1. Pauli operators [36] on a lattice."))
    assert image_refs.iter_targets(md) == ["images/p-f1.png"]


def test_the_caption_is_still_readable_after_escaping():
    md = fx.figure_markdown(_figure("FIG. 1. Pauli operators [36] on a lattice."))
    assert "Pauli operators" in md and "36" in md


def test_a_backslash_in_a_caption_does_not_escape_the_bracket_after_it():
    r"""A caption ending in a backslash would otherwise turn the `\[` that
    follows into a literal backslash and a live bracket — the escape defeating
    itself. Escaping happens in one pass, so it cannot."""
    from magi.ingest import image_refs

    md = fx.figure_markdown(_figure(r"FIG. 1. The operator \ acting on [2]."))
    assert image_refs.iter_targets(md) == ["images/p-f1.png"]


def test_a_very_long_caption_is_cut_before_it_is_escaped():
    """Truncating escaped text can leave half an escape at the end, which is a
    stray backslash that eats the closing bracket."""
    from magi.ingest import image_refs

    md = fx.figure_markdown(_figure("FIG. 1. " + "a [1] long caption " * 40))
    assert image_refs.iter_targets(md) == ["images/p-f1.png"]
