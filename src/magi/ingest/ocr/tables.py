"""Turn the HTML tables glm-ocr emits into Markdown tables.

The model writes tables as HTML no matter what it is asked for. A prompt saying
"render every table as a Markdown table with | pipes" still comes back as
``<table><tr><td>...``, because OCR training data spells tables in HTML. That
is not worth fighting: the content is correct, only the notation is wrong, and
notation is something we can convert exactly.

Two details this has to survive, both from real output:

* **the markup is not well-formed.** ``<td>$$[12, 4, 2]]</td>`` appears
  verbatim — an unbalanced ``$$`` and a stray bracket. A parser that requires
  valid HTML gets nothing; ``html.parser`` tolerates it, which is why the
  stdlib one is used rather than a regex or a strict parser.
* **cells arrive wrapped in display maths.** ``$$1 + y + y^2$$`` inside a table
  cell renders as a centred block in its own row and breaks the table. Display
  maths becomes inline maths in a cell; it was never display maths, the model
  just has one way of writing formulas.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

_TABLE_RE = re.compile(r"<table\b.*?</table\s*>", re.S | re.I)
# An unclosed final table: the model stopped mid-document, and the rows it did
# write are still worth keeping.
_TABLE_OPEN_RE = re.compile(r"<table\b.*", re.S | re.I)
_DISPLAY_IN_CELL = re.compile(r"\$\$(.+?)\$\$", re.S)


class _Rows(HTMLParser):
    """Collect ``<tr>``/``<td>`` text. Deliberately forgiving."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.header_len = 0
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._close_row()
            self._row = []
        elif tag in ("td", "th"):
            if self._row is None:      # a cell outside any row still counts
                self._row = []
            self._close_cell()
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._close_cell()
        elif tag == "tr":
            self._close_row()
        elif tag == "table":
            self._close_cell()
            self._close_row()

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def _close_cell(self):
        if self._cell is not None and self._row is not None:
            self._row.append(clean_cell("".join(self._cell)))
        self._cell = None

    def _close_row(self):
        self._close_cell()
        if self._row:
            self.rows.append(self._row)
        self._row = None

    def close(self):
        super().close()
        self._close_row()


def clean_cell(text: str) -> str:
    """One cell's text: no line breaks, no pipes, no display maths.

    Balancing the dollars is not tidying. Real output contains
    ``<td>$$[[12, 4, 2]]</td>`` — an opening ``$$`` with nothing closing it —
    and an odd delimiter does not stop at the cell: it swallows everything
    after it as maths, so one malformed cell can take the rest of the document
    with it.
    """
    text = _DISPLAY_IN_CELL.sub(lambda m: "$" + m.group(1).strip() + "$", text)
    text = text.replace("$$", "$")
    text = re.sub(r"\s+", " ", text).strip()
    if text.count("$") % 2:
        text += "$"
    # A literal pipe would end the cell early in Markdown.
    return text.replace("|", r"\|")


def to_markdown(rows: list[list[str]]) -> str:
    """Rows in, one Markdown table out. Ragged rows are padded, not dropped —
    a row the model wrote short is still a row someone may want to read."""
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(padded[0]) + " |",
           "|" + "|".join(["---"] * width) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in padded[1:]]
    return "\n".join(out)


def _is_prose_row(row: list[str]) -> bool:
    """A sentence the model kept writing after the table ended.

    When it does not close the table it carries on inside ``<td>``, so a page's
    closing paragraph arrives as ``<tr><td>The numbers of e-anyons and…</td>
    <td></td><td></td></tr>``. Converting that faithfully makes a table row out
    of a paragraph, which is unreadable and, worse, looks like data.

    One cell with a sentence in it and the rest empty is unambiguous; anything
    shorter is left alone, because a genuinely wide cell is still a cell.
    """
    filled = [c for c in row if c.strip()]
    return (len(filled) == 1 and len(filled[0]) >= 60
            and filled[0].count(" ") >= 8)


def _convert_one(html: str) -> str:
    parser = _Rows()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 — malformed markup is the normal case here
        pass

    rows = parser.rows
    # A table has columns. So a *trailing run* of rows that each hold a single
    # cell is where the table stopped and the model carried on writing — the
    # run is taken as a whole rather than row by row, because the run is mixed:
    # sentences, but also a display equation between two of them, and stopping
    # at the equation would leave the sentence above it stranded as a row.
    #
    # At least one of them has to read as prose before any of it is moved. A
    # genuinely single-column table is still a table.
    end = len(rows)
    while end and len([c for c in rows[end - 1] if c.strip()]) <= 1:
        end -= 1
    tail_rows = rows[end:] if any(_is_prose_row(r) for r in rows[end:]) else []
    if tail_rows:
        rows = rows[:end]
    trailing = [" ".join(c for c in r if c.strip()).strip() for r in tail_rows]
    trailing = [t for t in trailing if t]

    out = to_markdown(rows)
    if trailing:
        out = (out + "\n\n" if out else "") + "\n\n".join(trailing)
    return out


def html_tables_to_markdown(text: str) -> str:
    """Replace every ``<table>`` in ``text`` with the Markdown equivalent.

    Text outside tables is returned untouched: this is a notation fix, not a
    cleanup pass, and rewriting prose it was not asked to rewrite is how a
    converter starts losing content.
    """
    if "<table" not in text.lower():
        return text

    def repl(m):
        md = _convert_one(m.group(0))
        return "\n\n" + md + "\n\n" if md else m.group(0)

    out = _TABLE_RE.sub(repl, text)

    # A table the model never closed, because it stopped writing mid-row.
    if "<table" in out.lower():
        m = _TABLE_OPEN_RE.search(out)
        if m:
            md = _convert_one(m.group(0))
            if md:
                out = out[:m.start()] + "\n\n" + md + "\n"
    return out


def count_rows(text: str) -> int:
    """Data rows in ``text``, counting Markdown and HTML alike.

    The gates ask "did any table survive"; a route that answers in HTML must
    not read as a route that dropped the table.
    """
    n = sum(1 for line in text.splitlines()
            if line.strip().startswith("|") and not re.fullmatch(
                r"\|[\s\-:|]+\|", line.strip()))
    return n + len(re.findall(r"<tr\b", text, re.I))
