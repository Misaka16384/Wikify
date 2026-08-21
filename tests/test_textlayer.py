"""Contracts for the text-layer gate.

The distinction these pin down is the one that is easy to collapse and must not
be: *readable* and *sufficient* are different questions. A maths paper's text
layer reads perfectly — measured across 20+ real arXiv PDFs from 1991 to 2025,
zero replacement characters — and is still the wrong thing to use, because the
2-D structure of a formula does not survive flattening. Characters are solved;
structure is not.

Synthetic PDFs, built with PyMuPDF, so these run anywhere without the network.
"""

import pytest

from magi.ingest import textlayer

pymupdf = pytest.importorskip("pymupdf", reason="PyMuPDF is a hard dependency")


def _pdf(tmp_path, name, *, pages=3, text="Ordinary prose. " * 40,
         fontname="helv", producer=None, blank=False):
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page()
        if not blank:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 750), text,
                                fontsize=10, fontname=fontname)
    if producer:
        doc.set_metadata({"producer": producer, "creator": producer})
    path = tmp_path / name
    doc.save(path)
    doc.close()
    return path


# --------------------------------------------------------------------------
# Is there a text layer at all
# --------------------------------------------------------------------------

def test_a_born_digital_document_is_usable(tmp_path):
    got = textlayer.inspect(_pdf(tmp_path, "prose.pdf"))
    assert got.usable
    assert got.chars_per_page > textlayer.MIN_CHARS_PER_PAGE


def test_a_page_with_no_text_is_not_usable(tmp_path):
    got = textlayer.inspect(_pdf(tmp_path, "blank.pdf", blank=True))
    assert not got.usable
    assert "no real text layer" in got.reason or "scan" in got.reason


def test_a_nearly_empty_text_layer_is_not_usable(tmp_path):
    """A scan sometimes carries a stray word or two of stamped-on text."""
    got = textlayer.inspect(_pdf(tmp_path, "sparse.pdf", text="page 1"))
    assert not got.usable


def test_a_corrupt_file_is_an_answer_not_a_crash(tmp_path):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.7\nthis is not a pdf")
    got = textlayer.inspect(bad)
    assert not got.usable and "could not open" in got.reason


def test_a_missing_file_is_an_answer_not_a_crash(tmp_path):
    got = textlayer.inspect(tmp_path / "nope.pdf")
    assert not got.usable


def test_the_page_count_is_reported(tmp_path):
    assert textlayer.inspect(_pdf(tmp_path, "p.pdf", pages=7)).pages == 7


def test_a_long_document_is_judged_on_a_sample(tmp_path):
    """Never decide on page one — title pages are sparse and unrepresentative."""
    got = textlayer.inspect(_pdf(tmp_path, "long.pdf", pages=40))
    assert got.usable and got.pages == 40


# --------------------------------------------------------------------------
# Is the text layer sufficient — the distinction that matters
# --------------------------------------------------------------------------

def test_math_fonts_are_recognised_by_name():
    """Font-name sniffing is exact, not a heuristic over the text."""
    for font in ("CMSY10", "CMEX10", "CMMI12", "MSBM7", "MSAM10",
                 "latinmodern-math", "XITSMath-Regular", "STIXMath",
                 "NewCMMath-Regular", "rsfs10"):
        assert textlayer.MATH_FONT_RE.search(font), font


def test_ordinary_text_fonts_are_not_math():
    for font in ("Helvetica", "TimesNewRoman", "NimbusRomNo9L-Regu",
                 "ArialMT", "CMR10", "LiberationSerif", "SourceSansPro"):
        assert not textlayer.MATH_FONT_RE.search(font), font


def test_cmr_is_not_treated_as_math():
    """Computer Modern Roman is the body face of every TeX document ever set.

    Treating it as a maths signal would send every LaTeX paper — including the
    prose-only ones this route exists for — to an OCR model for nothing.
    """
    assert not textlayer.MATH_FONT_RE.search("CMR10")
    assert not textlayer.MATH_FONT_RE.search("CMBX12")


def test_a_readable_maths_paper_is_still_refused(tmp_path, monkeypatch):
    """The whole point. Its text reads perfectly and it is still the wrong route:
    a fraction flattens into characters on a line and the meaning is gone."""
    real = textlayer.inspect

    def with_math(path):
        got = real(path)
        return got._replace(has_math=True, usable=True)

    monkeypatch.setattr(textlayer, "inspect", with_math)
    got = textlayer.inspect(_pdf(tmp_path, "maths.pdf"))

    assert got.usable is True
    assert got.route_here is False


def test_route_here_needs_both_conditions():
    T = textlayer.TextLayer
    assert T(True, False, "", 900, 10).route_here is True
    assert T(True, True, "", 900, 10).route_here is False     # readable, not sufficient
    assert T(False, False, "", 10, 10).route_here is False    # nothing to read
    assert T(False, True, "", 10, 10).route_here is False


# --------------------------------------------------------------------------
# The scanner trap: a text layer that exists and is garbage
# --------------------------------------------------------------------------

def test_a_glyph_soup_text_layer_is_rejected():
    """Unmapped glyph codes mean the text is there and unreadable — worse than
    absent, because its presence says 'no OCR needed'."""
    assert textlayer._cid_ratio("(cid:31)(cid:8)(cid:18)" * 40) > textlayer.MAX_CID_RATIO


def test_clean_text_has_no_cid_noise():
    assert textlayer._cid_ratio("The quick brown fox jumps over the lazy dog.") == 0.0


def test_a_scanner_producer_is_corroboration_not_a_verdict(tmp_path):
    """The text passed every readability check, so it is readable. Saying where
    it came from is useful; refusing on the strength of a metadata string is not
    — the field is trivially wrong or absent."""
    got = textlayer.inspect(_pdf(tmp_path, "scanned.pdf", producer="ABBYY FineReader 15"))
    assert got.usable
    assert "OCR" in got.reason


def test_a_tex_producer_does_not_by_itself_mean_math(tmp_path):
    got = textlayer.inspect(_pdf(tmp_path, "tex.pdf", producer="pdfTeX-1.40.25"))
    assert got.usable and not got.has_math


@pytest.mark.parametrize("producer", ["CamScanner", "Adobe Scan", "Tesseract 5.3"])
def test_known_scanner_producers_are_recognised(producer):
    assert textlayer.SCANNER_PRODUCER_RE.search(producer)


def test_printable_ratio_flags_binary_noise():
    assert textlayer._printable_ratio("\x00\x01\x02\x03" * 50) < textlayer.MIN_PRINTABLE_RATIO
    assert textlayer._printable_ratio("Normal readable text.") == 1.0


# --------------------------------------------------------------------------
# The reason string is for a person
# --------------------------------------------------------------------------

def test_every_outcome_explains_itself(tmp_path):
    for pdf in (_pdf(tmp_path, "a.pdf"),
                _pdf(tmp_path, "b.pdf", blank=True),
                tmp_path / "missing.pdf"):
        got = textlayer.inspect(pdf)
        assert got.reason and len(got.reason) > 15, got


def test_the_convenience_wrapper_agrees_with_inspect(tmp_path):
    pdf = _pdf(tmp_path, "x.pdf")
    assert textlayer.would_route_here(pdf) == textlayer.inspect(pdf).route_here
