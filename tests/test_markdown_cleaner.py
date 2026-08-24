"""The last step before a document is written, and what it must not touch.

`MarkdownCleaner` runs after every page of the OCR route — after the model,
after the table conversion, after the repair, and after every gate. Whatever it
does to a document, nothing downstream will notice.

It was splitting table rows. `$$` is a display-math delimiter everywhere except
inside a table cell, where it cannot be one, and the rule that puts blank lines
around a display block was cutting rows in half wherever the model had left a
stray `$$` behind. Measured end to end on a 49-row table: the engine returned
53 pipe rows and the file on disk carried **72**, scoring 31 of 49 rows right
against the 45 the engine had actually produced.

The shape of that failure is the one this whole pipeline exists to refuse: not
a crash, not a gap, but a clean-looking table containing rows that were never
in the document.
"""

import pytest

from magi.ingest.ocr.markdown_builder import MarkdownCleaner


@pytest.fixture
def clean():
    return MarkdownCleaner().clean


# --------------------------------------------------------------------------
# table rows survive intact
# --------------------------------------------------------------------------

def test_a_stray_display_delimiter_does_not_split_a_row(clean):
    """The real row, from the real model, on the real page."""
    row = r"| $[[62, 10, 6]]$ | x^{-1}y | x^{-1}y^{-1}$$ | (0, 31) | (1, 13) | 5.81 |"
    assert clean(row).splitlines() == [row]


def test_a_table_keeps_exactly_its_rows(clean):
    table = ("| $[[n,k,d]]$ | $f$ | $g$ |\n"
             "|---|---|---|\n"
             r"| $[[12,4,2]]$ | xy$$ | $xy$ |" "\n"
             r"| $[[14,6,2]]$ | $y$ | x^{-1}$$ |" "\n")
    out = clean(table)
    assert len([l for l in out.splitlines() if l.strip().startswith("|")]) == 4


def test_an_indented_row_is_still_a_row(clean):
    out = clean("intro\n\n   | a | b$$ | c |\n")
    rows = [l for l in out.splitlines() if l.strip().startswith("|")]
    assert rows == ["   | a | b$$ | c |"]


# --------------------------------------------------------------------------
# and display maths outside a table is still spaced out
# --------------------------------------------------------------------------

def test_a_display_formula_in_prose_still_gets_its_blank_lines(clean):
    out = clean("The result follows.$$E = mc^2$$Which completes the proof.")
    assert out.startswith("The result follows.\n\n$$")
    assert out.endswith("$$\n\nWhich completes the proof.")


def test_the_prose_around_a_table_is_still_processed(clean):
    """Rows are passed through; the paragraphs on either side are not exempt.
    Splitting the document at the table must not turn into skipping half of it.
    """
    out = clean("Before.$$x$$\n| a | b |\nAfter.$$y$$")
    assert out.startswith("Before.\n\n$$")
    assert "| a | b |" in out.splitlines()
    assert "After.\n\n$$" in out


def test_a_formula_on_its_own_line_after_prose_gains_a_blank_line(clean):
    """Consecutive non-table lines stay one block, so a `$$` matched across a
    line break behaves as it did before this became line-aware."""
    assert clean("A sentence\n$$x$$").startswith("A sentence\n\n$$")
