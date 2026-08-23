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
#
# Two patterns, not one, because an allowlist of families is structurally
# leaky: a real economics paper set in kpfonts (Kp--M-Sy-Regular) sailed through
# an earlier CM/AMS-only list and would have had its one display equation
# flattened. Every TeX math family, whoever ships it, names its faces after the
# encodings — SY for symbols, EX for extensions, MI for math italic — so the
# shape catches the ones nobody thought to enumerate.
_KNOWN_MATH_FAMILIES = (
    r"CMSY|CMEX|CMMI|CMBSY|CMMIB|MSAM|MSBM|EUFM|EUSM|EURM|rsfs|"
    r"latinmodern-math|LMMath|STIXMath|STIX.*Math|Asana-?Math|"
    r"XITSMath|TeXGyre.*Math|NewCM.*Math|Libertinus.*Math|"
    r"Fira.*Math|Garamond-?Math|Concrete.*Math|MinionMath|"
    r"KpMath|Kp-.*-(?:Sy|Ex|Mi)|txsy|txex|txmi|pxsy|pxex|pxmi"
)

# `<Family><Encoding><optional size>` — CMSY10, Kp--M-Sy-Regular, txexa, MSBM7.
# Anchored on a separator or a case change so ordinary words cannot match: a
# body face called "Symbola" or a name ending in "mi" must not read as maths.
_TEX_MATH_SHAPE = r"(?:^|[\s\-_.])[A-Za-z]{1,8}[\-_]{0,2}(?:SY|EX|MI|BSY|MIB)[\-_]?\d{0,2}(?:$|[\s\-_.])"

MATH_FONT_RE = re.compile(
    rf"(?:{_KNOWN_MATH_FAMILIES})|(?i:math)|{_TEX_MATH_SHAPE}")

# Producers that mean the "text layer" is itself OCR output, and therefore only
# as good as whatever produced it. Corroborating evidence, never the decision.
SCANNER_PRODUCER_RE = re.compile(
    r"ABBYY|FineReader|CamScanner|ScanSnap|Adobe Scan|Tesseract|"
    r"Kofax|PaperPort|NAPS2|VueScan",
    re.IGNORECASE)

TEX_PRODUCER_RE = re.compile(r"pdfTeX|XeTeX|LuaTeX|dvips|Overleaf|LaTeX",
                             re.IGNORECASE)

# Title pages are sparse and unrepresentative, so never decide on page 1 alone.
# Text and image sampling is spread across the document rather than taken from
# the front: a paper's first pages are its least typical.
SAMPLE_PAGES = 6

# Fonts are enumerated across the WHOLE document, not the sample. An earlier
# version looked only at the first five pages and passed a 44-page economics
# paper as math-free — its literature review runs to page 17 and its one
# display equation is on page 18. Long math-free front matter is an ordinary
# shape in empirical work, so a front-window check is exactly wrong here.
# Enumeration is cheap: measured under a second on a 115-page scan.
FONT_SCAN_CAP = 200

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

        # Spread the sample: first page, last page, and evenly in between.
        sample_n = min(SAMPLE_PAGES, pages)
        if pages <= sample_n:
            indices = list(range(pages))
        else:
            step = (pages - 1) / (sample_n - 1)
            indices = sorted({int(round(i * step)) for i in range(sample_n)})

        # Fonts across the whole document — see FONT_SCAN_CAP. A paper whose
        # equations start after its literature review must not read as prose.
        font_pages = (range(pages) if pages <= FONT_SCAN_CAP
                      else sorted({int(round(i * (pages - 1) / (FONT_SCAN_CAP - 1)))
                                   for i in range(FONT_SCAN_CAP)}))
        fonts_seen: list[str] = []
        for n in font_pages:
            try:
                for font in doc.get_page_fonts(n):
                    # (xref, ext, type, basefont, name, encoding)
                    if len(font) > 3 and font[3]:
                        fonts_seen.append(str(font[3]))
            except Exception:  # noqa: BLE001 — font table is best effort
                pass

        total_chars = 0
        full_page_images = 0
        collected = []

        for n in indices:
            page = doc[n]
            text = page.get_text() or ""
            collected.append(text)
            total_chars += len(text.strip())

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
        per_page = total_chars // max(len(indices), 1)
        has_math = bool(MATH_FONT_RE.search(" ".join(fonts_seen)))

        if full_page_images >= max(1, len(indices) // 2) and per_page < MIN_CHARS_PER_PAGE:
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


class Census(NamedTuple):
    """What the source document actually contains, counted rather than guessed.

    The gates judge a conversion by comparing what came out against what went
    in, and until this existed there was no "what went in" — so a route could
    return a clean-reading page that was missing half the document and nothing
    could tell. Measured on ``glm-ocr``: three pages carrying 151 table rows
    produced zero, and the text recovered fell to 41-63% of the page while
    table-free pages held 96-102%. Both numbers are here.

    ``ok`` is False when the document could not be read at all; callers should
    then skip the comparison rather than report a document as empty.
    """

    ok: bool
    pages: int = 0
    chars: int = 0
    tables: int = 0
    table_rows: int = 0


def census(pdf_path, page_range: tuple[int, int] | None = None) -> Census:
    """Count the text and tables a PDF holds, over all pages or a range.

    ``page_range`` is 1-based and inclusive, matching ``ingest ocr --pages``,
    so a partial conversion is compared against the part it converted rather
    than against the whole document.

    Never raises. This is evidence for a report, and a report that cannot be
    produced must not take the conversion down with it.
    """
    try:
        doc = _open(pdf_path)
    except Exception:  # noqa: BLE001
        return Census(False)

    try:
        lo, hi = (1, doc.page_count) if page_range is None else page_range
        hi = min(hi or doc.page_count, doc.page_count)
        chars = tables = rows = 0
        pages = 0
        for index in range(max(lo, 1) - 1, hi):
            page = doc[index]
            pages += 1
            chars += len(re.sub(r"\s+", "", page.get_text()))
            try:
                found = list(page.find_tables().tables)
            except Exception:  # noqa: BLE001 — table finding is best-effort
                found = []
            tables += len(found)
            rows += sum(getattr(t, "row_count", 0) for t in found)
        return Census(True, pages, chars, tables, rows)
    except Exception:  # noqa: BLE001
        return Census(False)
    finally:
        try:
            doc.close()
        except Exception:  # noqa: BLE001
            pass
