"""Deciding whether a PDF's own text layer is worth reading, and reading it.

Two orthogonal questions, which are easy to run together and should not be:

**Is there a usable text layer?** A born-digital PDF carries its text; a scan
carries pixels. Running OCR over a born-digital paper is re-photographing
printed text — slower, lossier, and for the cloud route it costs money.

**Is the text layer sufficient?** Separate question, and the one that decides
whether we may use it. Characters come out fine — measured across 20+ real arXiv
PDFs from 1991 to 2025, zero replacement characters, because CM and AMS math
fonts carry canonical glyph names in ``/Encoding /Differences`` that MuPDF
already resolves. What does not survive is **structure**: recovering
``\\frac{a}{b}`` from a rule with material above and below, or ``x^{2}`` from a
raised smaller glyph, is 2-D layout parsing. No maintained rule-based tool does
it — MaxTract, the one serious attempt, last shipped in 2016.

So a paper with math goes to a model-backed route even though its text layer
reads perfectly, and one without math does not need to. That is the gate.

Everything here uses PyMuPDF, already a hard dependency, so the detection half
costs nothing at all.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

# LaTeX math fonts. Their presence means the document was typeset by TeX with
# real mathematics in it; font-name sniffing for this is an established
# technique and it is exact, not a heuristic over the text.
MATH_FONT_RE = re.compile(
    r"CMSY|CMEX|CMMI|CMBSY|CMMIB|MSAM|MSBM|EUFM|EUSM|"
    r"latinmodern-math|LMMath|STIXMath|STIX.*Math|Asana-?Math|"
    r"XITSMath|TeXGyre.*Math|NewCM.*Math|rsfs",
    re.IGNORECASE)

# Producers that mean the "text layer" is itself OCR output, and therefore only
# as good as whatever produced it. Corroborating evidence, never the decision.
SCANNER_PRODUCER_RE = re.compile(
    r"ABBYY|FineReader|CamScanner|ScanSnap|Adobe Scan|Tesseract|"
    r"Kofax|PaperPort|NAPS2|VueScan",
    re.IGNORECASE)

TEX_PRODUCER_RE = re.compile(r"pdfTeX|XeTeX|LuaTeX|dvips|Overleaf|LaTeX",
                             re.IGNORECASE)

# Title pages are sparse and unrepresentative, so never decide on page 1 alone.
SAMPLE_PAGES = 5

# Below this many characters per page, averaged, there is nothing to read.
MIN_CHARS_PER_PAGE = 200

# A page whose whole area is one image is a photograph of a page.
FULL_PAGE_IMAGE_RATIO = 0.95

# CID escapes (`/31 /8 /18`) appear when a font has no usable ToUnicode map. A
# few are noise; a majority means the extracted text is unusable even though it
# exists — the scanner trap, where a bad OCR layer is already baked in.
MAX_CID_RATIO = 0.5

MIN_PRINTABLE_RATIO = 0.7

_CID_RE = re.compile(r"[�]|\(cid:\d+\)|/\d{1,4}(?=\s)")


class TextLayer(NamedTuple):
    """What a PDF's own text layer is worth."""

    usable: bool            # is there readable text at all
    has_math: bool          # does it need a model to keep formulas
    reason: str             # why, in words a person can act on
    chars_per_page: int
    pages: int
    producer: str = ""

    @property
    def route_here(self) -> bool:
        """Whether this route may handle the document.

        Both conditions, and they are different: readable *and* not
        mathematical. A maths paper whose text layer is perfect still goes to a
        model, because the formulas would arrive as flattened character soup.
        """
        return self.usable and not self.has_math


def _open(pdf_path):
    try:
        import pymupdf as fitz
    except ImportError:  # pragma: no cover - legacy import name
        import fitz
    return fitz.open(str(pdf_path))


def _cid_ratio(text: str) -> float:
    if not text:
        return 0.0
    hits = sum(len(m.group(0)) for m in _CID_RE.finditer(text))
    return hits / max(len(text), 1)


def _printable_ratio(text: str) -> float:
    if not text:
        return 1.0
    good = sum(1 for ch in text if ch.isprintable() or ch.isspace())
    return good / len(text)


def inspect(pdf_path) -> TextLayer:
    """Look at a PDF and decide what its text layer is good for."""
    path = Path(pdf_path)
    try:
        doc = _open(path)
    except Exception as exc:  # noqa: BLE001 — a corrupt file is an answer
        return TextLayer(False, False, f"could not open the PDF: {exc}", 0, 0)

    with doc:
        pages = doc.page_count
        if not pages:
            return TextLayer(False, False, "the PDF has no pages", 0, 0)

        producer = " ".join(str(doc.metadata.get(k) or "")
                            for k in ("producer", "creator"))

        sample = min(SAMPLE_PAGES, pages)
        total_chars = 0
        full_page_images = 0
        collected = []
        fonts_seen: list[str] = []

        for n in range(sample):
            page = doc[n]
            text = page.get_text() or ""
            collected.append(text)
            total_chars += len(text.strip())

            try:
                for font in doc.get_page_fonts(n):
                    # (xref, ext, type, basefont, name, encoding)
                    if len(font) > 3 and font[3]:
                        fonts_seen.append(str(font[3]))
            except Exception:  # noqa: BLE001 — font table is best effort
                pass

            try:
                page_area = abs(page.rect)
                for img in page.get_images(full=True):
                    for rect in page.get_image_rects(img[0]):
                        if page_area and abs(rect) / page_area >= FULL_PAGE_IMAGE_RATIO:
                            full_page_images += 1
                            raise StopIteration
            except StopIteration:
                continue
            except Exception:  # noqa: BLE001
                pass

        text = "\n".join(collected)
        per_page = total_chars // max(sample, 1)
        has_math = bool(MATH_FONT_RE.search(" ".join(fonts_seen)))

        if full_page_images >= max(1, sample // 2) and per_page < MIN_CHARS_PER_PAGE:
            return TextLayer(False, has_math,
                             "each page is one full-page image — this is a scan",
                             per_page, pages, producer)

        if per_page < MIN_CHARS_PER_PAGE:
            return TextLayer(False, has_math,
                             f"only ~{per_page} characters per page — no real text layer",
                             per_page, pages, producer)

        cid = _cid_ratio(text)
        if cid > MAX_CID_RATIO:
            return TextLayer(False, has_math,
                             f"{cid:.0%} of the extracted text is unmapped glyph codes — "
                             "the text layer exists but is unreadable",
                             per_page, pages, producer)

        printable = _printable_ratio(text)
        if printable < MIN_PRINTABLE_RATIO:
            return TextLayer(False, has_math,
                             f"only {printable:.0%} of the extracted text is printable — "
                             "likely a bad OCR layer baked in by a scanner",
                             per_page, pages, producer)

        if SCANNER_PRODUCER_RE.search(producer):
            # Corroboration, not the decision: the text passed every check
            # above, so it is readable. Say where it came from and move on.
            note = f" (produced by {producer.strip()}, so this text is itself OCR)"
        else:
            note = ""

        if has_math:
            return TextLayer(True, True,
                             "readable text, but the document is TeX-typeset with real "
                             "mathematics — formulas would arrive as flattened characters"
                             + note,
                             per_page, pages, producer)

        return TextLayer(True, False,
                         f"a real text layer, ~{per_page} characters per page, no math fonts"
                         + note,
                         per_page, pages, producer)


def would_route_here(pdf_path) -> bool:
    return inspect(pdf_path).route_here
