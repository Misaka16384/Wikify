"""glm-ocr answers in HTML; the library speaks Markdown.

The prompt asks for "a Markdown table with | pipes" and the model returns
``<table><tr><td>`` regardless, because OCR training data spells tables in
HTML. Converting is exact and cheap, so the notation is fixed on the way out
rather than argued with on the way in.

Every fixture below is shaped like real output from `glm-ocr:q8_0`, including
the malformed parts — those are what a hand-rolled regex would fall over on.
"""

import re

import pytest

from magi.ingest.ocr import tables


# --------------------------------------------------------------------------
# The ordinary case
# --------------------------------------------------------------------------

SIMPLE = ("<table><tr><th>Code</th><th>f</th></tr>"
          "<tr><td>[[12,4,2]]</td><td>xy</td></tr>"
          "<tr><td>[[18,4,4]]</td><td>xy</td></tr></table>")


def test_an_html_table_becomes_a_markdown_table():
    md = tables.html_tables_to_markdown(SIMPLE)
    lines = [l for l in md.splitlines() if l.strip().startswith("|")]

    assert lines[0] == "| Code | f |"
    assert lines[1] == "|---|---|"
    assert "| [[12,4,2]] | xy |" in lines
    assert "<table" not in md and "<tr" not in md


def test_prose_around_the_table_is_left_alone():
    """A notation fix, not a cleanup pass. Rewriting text it was not asked to
    rewrite is how a converter starts losing content."""
    text = "TABLE I. Optimal codes.\n\n" + SIMPLE + "\n\nWe now turn to $B_p$."
    md = tables.html_tables_to_markdown(text)

    assert md.startswith("TABLE I. Optimal codes.")
    assert md.rstrip().endswith("We now turn to $B_p$.")


def test_text_with_no_table_is_returned_unchanged():
    text = "Just prose with $x^{-4}$ in it.\n"
    assert tables.html_tables_to_markdown(text) == text


# --------------------------------------------------------------------------
# The shapes real output actually has
# --------------------------------------------------------------------------

def test_display_maths_in_a_cell_becomes_inline():
    r"""The model writes every cell as ``$$...$$``. Display maths inside a
    table cell renders as a centred block on its own line and breaks the table
    apart; it was never display maths, the model has one way of writing a
    formula."""
    html = "<table><tr><td>$$1 + y + y^2$$</td><td>$$x^{-4}$$</td></tr></table>"
    md = tables.html_tables_to_markdown(html)

    assert "$1 + y + y^2$" in md
    assert "$$" not in md


def test_an_unbalanced_dollar_pair_is_closed():
    r"""Verbatim from a real page: ``<td>$$[[12, 4, 2]]</td>`` — opened and
    never closed. An odd delimiter does not stop at the cell boundary, it
    swallows the rest of the document as maths, so one bad cell can take the
    whole page with it."""
    html = "<table><tr><td>$$[[12, 4, 2]]</td><td>xy</td></tr></table>"
    md = tables.html_tables_to_markdown(html)

    row = [l for l in md.splitlines() if "12, 4, 2" in l][0]
    assert row.count("$") % 2 == 0, row


def test_a_table_the_model_never_closed_still_yields_its_rows():
    """Truncation mid-table is the normal failure here, and the rows written
    before it stopped are exactly the rows worth keeping."""
    html = ("Intro text.\n<table><tr><td>a</td><td>b</td></tr>"
            "<tr><td>c</td><td>d</td></tr>")
    md = tables.html_tables_to_markdown(html)

    assert "| a | b |" in md
    assert "| c | d |" in md
    assert "<tr" not in md


def test_ragged_rows_are_padded_not_dropped():
    """A row the model wrote short is still a row someone may want to read."""
    html = "<table><tr><td>a</td><td>b</td><td>c</td></tr><tr><td>x</td></tr></table>"
    md = tables.html_tables_to_markdown(html)

    assert "| x |  |  |" in md


def test_a_pipe_inside_a_cell_is_escaped():
    """Otherwise the cell ends early and every column after it shifts."""
    html = "<table><tr><td>a|b</td><td>c</td></tr></table>"
    md = tables.html_tables_to_markdown(html)

    row = [l for l in md.splitlines() if l.startswith("|")][0]
    assert r"a\|b" in row
    # Three *unescaped* pipes: the two borders and the one column separator.
    assert len(re.findall(r"(?<!\\)\|", row)) == 3, row


def test_newlines_inside_a_cell_do_not_break_the_row():
    html = "<table><tr><td>first\nsecond</td><td>c</td></tr></table>"
    md = tables.html_tables_to_markdown(html)
    assert "| first second | c |" in md


def test_entities_are_decoded():
    html = "<table><tr><td>a &amp; b</td><td>&lt;x&gt;</td></tr></table>"
    md = tables.html_tables_to_markdown(html)
    assert "| a & b | <x> |" in md


def test_several_tables_on_one_page_all_convert():
    """The measured pages carry TABLE I and TABLE II side by side."""
    md = tables.html_tables_to_markdown(SIMPLE + "\n\nBetween.\n\n" + SIMPLE)
    assert md.count("|---|---|") == 2
    assert "Between." in md


def test_an_empty_table_is_left_as_it_was():
    """Nothing to convert is not the same as something to delete."""
    html = "<table></table>"
    assert tables.html_tables_to_markdown(html) == html


# --------------------------------------------------------------------------
# Counting rows, for the gate
# --------------------------------------------------------------------------

def test_row_counting_sees_both_notations():
    """`check_tables_survived` asks whether any table survived. A route that
    answers in HTML must not read as a route that dropped the table."""
    assert tables.count_rows(SIMPLE) == 3
    assert tables.count_rows("| a | b |\n|---|---|\n| c | d |\n") == 2


def test_the_separator_line_is_not_counted_as_a_row():
    assert tables.count_rows("|---|---|\n") == 0


def test_prose_counts_as_no_rows():
    assert tables.count_rows("No tables here at all.\n") == 0


# --------------------------------------------------------------------------
# The gate, end to end
# --------------------------------------------------------------------------

def test_the_gate_does_not_call_an_html_table_a_dropped_table():
    """The loudest possible false alarm, on the one route where a genuinely
    dropped table is the thing worth catching."""
    from magi.ingest import gates

    body = "TABLE I. Codes.\n\n" + SIMPLE + "\n"
    assert gates.check_tables_survived(body, source_tables=1, source_rows=3) is None


def test_the_gate_still_fires_when_the_table_is_actually_gone():
    from magi.ingest import gates

    flat = "TABLE I. Codes.\n\nCode f [[12,4,2]] xy [[18,4,4]] xy\n"
    finding = gates.check_tables_survived(flat, source_tables=1, source_rows=3)
    assert finding is not None and finding.code == "tables-dropped"


@pytest.mark.parametrize("cell,expected", [
    ("$$x$$", "$x$"),
    ("  spaced   out  ", "spaced out"),
    ("$$a$$ and $$b$$", "$a$ and $b$"),
])
def test_cell_cleaning(cell, expected):
    assert tables.clean_cell(cell) == expected


# --------------------------------------------------------------------------
# Prose the model kept writing inside the table
# --------------------------------------------------------------------------

PROSE = ("The numbers of e-anyons and m-anyons are equal since they can be "
         "re-arranged and paired, forming a direct sum of toric codes.")


def test_a_trailing_sentence_is_a_paragraph_not_a_table_row():
    """Seen on a real page: the model never closed the table and carried on
    writing the closing paragraph inside `<td>`. Converting that faithfully
    turns a paragraph into a row, which is unreadable and — worse — looks like
    data."""
    html = ("<table><tr><td>a</td><td>b</td></tr>"
            f"<tr><td>{PROSE}</td><td></td></tr></table>")
    md = tables.html_tables_to_markdown(html)

    assert "| a | b |" in md
    assert PROSE in md
    assert f"| {PROSE}" not in md


def test_a_short_wide_cell_is_still_a_cell():
    """A genuinely wide column is not prose. The rule needs a sentence's worth
    of words before it takes a row out of the table."""
    html = "<table><tr><td>a</td><td>b</td></tr><tr><td>Total</td><td></td></tr></table>"
    md = tables.html_tables_to_markdown(html)

    assert "| Total |  |" in md


def test_a_sentence_in_the_middle_stays_in_the_table():
    """One-cell rows mid-table are usually spanning sub-headings, which belong
    to the table. Only the trailing run is pulled out."""
    html = ("<table><tr><td>a</td><td>b</td></tr>"
            f"<tr><td>{PROSE}</td><td></td></tr>"
            "<tr><td>c</td><td>d</td></tr></table>")
    md = tables.html_tables_to_markdown(html)

    assert f"| {PROSE} |" in md
    assert "| c | d |" in md


def test_several_trailing_sentences_all_become_paragraphs():
    html = ("<table><tr><td>a</td><td>b</td></tr>"
            f"<tr><td>{PROSE}</td><td></td></tr>"
            f"<tr><td>{PROSE} Again.</td><td></td></tr></table>")
    md = tables.html_tables_to_markdown(html)

    assert md.count("|") == 6           # header row and separator only


def test_the_whole_trailing_run_leaves_together_equation_and_all():
    """The run is mixed. On the real page a display equation sits between two
    sentences, and stopping at the equation left the sentence above it stranded
    as a table row. A table has columns; a trailing run of single-cell rows is
    where the table stopped."""
    html = ("<table><tr><td>a</td><td>b</td></tr>"
            f"<tr><td>{PROSE}</td><td></td></tr>"
            "<tr><td>$$e = mc^2$$</td><td></td></tr>"
            f"<tr><td>{PROSE}</td><td></td></tr></table>")
    md = tables.html_tables_to_markdown(html)

    assert md.count("|") == 6           # header and separator only
    assert "$e = mc^2$" in md
    assert "| $e = mc^2$" not in md


def test_a_single_column_table_is_still_a_table():
    """Nothing in the trailing run reads as prose, so none of it moves."""
    html = ("<table><tr><td>Value</td></tr><tr><td>12</td></tr>"
            "<tr><td>34</td></tr></table>")
    md = tables.html_tables_to_markdown(html)

    assert "| 12 |" in md and "| 34 |" in md
