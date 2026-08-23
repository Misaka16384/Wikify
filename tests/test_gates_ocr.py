"""Contracts for the checks that compare a conversion against its source.

Every case here is a shape measured on 2026-08-23 while grading the local OCR
rung against three real arXiv papers. The four failures they encode all
reported success at the time:

* three pages carrying 151 table rows produced none, captions intact;
* one page stopped mid-``\\begin{array}`` and left it unclosed;
* one page emitted 27,281 characters of a repeating block;
* pages that lost content recovered 41-63% of the source text, against
  96-102% for pages that converted whole.

The counts these checks judge against come from ``textlayer.census``; the
gates themselves stay pure, exactly as ``check_figures`` already did.
"""

from magi.ingest import gates


def _doc(body: str) -> str:
    return "---\ntitle: X\n---\n\n" + body


LONG_BODY = "word " * 300


# --------------------------------------------------------------------------
# tables that did not survive
# --------------------------------------------------------------------------

def test_a_source_table_with_no_table_in_the_output_is_reported():
    finding = gates.check_tables_survived(_doc(LONG_BODY), source_tables=2, source_rows=51)
    assert finding is not None
    assert finding.code == "tables-dropped"
    assert "51" in finding.detail


def test_a_transcribed_table_is_not_reported():
    md = _doc("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
    assert gates.check_tables_survived(md, source_tables=1, source_rows=3) is None


def test_a_source_with_no_tables_is_never_reported():
    assert gates.check_tables_survived(_doc(LONG_BODY), 0, 0) is None


def test_the_caption_alone_does_not_count_as_the_table():
    """The measured failure: the caption came through and the data did not."""
    md = _doc("TABLE I. Optimal weight-6 generalized toric codes with n <= 110.\n\n" + LONG_BODY)
    assert gates.check_tables_survived(md, 2, 51).code == "tables-dropped"


# --------------------------------------------------------------------------
# environments left open
# --------------------------------------------------------------------------

def test_an_unclosed_environment_is_reported():
    md = _doc(r"$$\left[ \begin{array}{cccccccccccc")
    finding = gates.check_environments_closed(md)
    assert finding is not None
    assert finding.code == "unclosed-environment"
    assert "array" in finding.detail


def test_a_balanced_document_is_not_reported():
    md = _doc(r"$$\begin{align} a &= b \\ c &= d \end{align}$$")
    assert gates.check_environments_closed(md) is None


def test_a_close_without_an_open_is_also_reported():
    finding = gates.check_environments_closed(_doc(r"text \end{equation} more"))
    assert finding is not None
    assert "never opened" in finding.detail


def test_nesting_the_same_environment_twice_needs_two_closings():
    md = _doc(r"\begin{array}{c}\begin{array}{c} x \end{array}")
    assert gates.check_environments_closed(md).code == "unclosed-environment"


def test_whitespace_between_begin_and_brace_does_not_hide_it():
    assert gates.check_environments_closed(_doc(r"\begin {cases} x")) is not None


# --------------------------------------------------------------------------
# repetition loops
# --------------------------------------------------------------------------

PASSAGE = (
    "Indeed, Corollary 4.5 of Ref. [35] asserts that the dimension is bounded "
    "for an untwisted torus of arbitrary size, and since it is upper bounded "
    "by Eq. (15), Theorem 1 follows immediately from the anyon picture. "
)


def test_a_restated_passage_is_reported():
    """Measured: one page came back with its whole body twice."""
    finding = gates.check_repetition(_doc(PASSAGE * 2))
    assert finding is not None
    assert finding.code == "repetition-loop"


def test_ordinary_prose_is_not_a_loop():
    assert gates.check_repetition(_doc(LONG_BODY.replace("word", "alpha beta gamma"))) is None


def test_uniform_filler_is_not_a_loop():
    """A column of identical values repeats trivially and means nothing."""
    assert gates.check_repetition(_doc("& 0 & \\cdots " * 80)) is None


def test_a_short_document_cannot_be_judged_for_looping():
    assert gates.check_repetition(_doc("short")) is None


# --------------------------------------------------------------------------
# output that could not have come from the page
# --------------------------------------------------------------------------

def test_an_output_far_larger_than_its_source_is_reported():
    """Measured: 27,281 characters produced from a page holding 1,526."""
    finding = gates.check_output_inflation(_doc("x" * 27281), source_chars=1526)
    assert finding is not None
    assert finding.code == "output-inflated"
    assert "17.9x" in finding.detail


def test_dense_latex_may_legitimately_exceed_its_plain_text():
    assert gates.check_output_inflation(_doc("y" * 2500), source_chars=1000) is None


def test_inflation_stands_down_without_a_census():
    assert gates.check_output_inflation(_doc("x" * 9000), source_chars=0) is None


# --------------------------------------------------------------------------
# text that never arrived
# --------------------------------------------------------------------------

def test_an_output_far_shorter_than_its_source_is_reported():
    finding = gates.check_text_coverage(_doc("a" * 300), source_chars=3000)
    assert finding is not None
    assert finding.code == "output-much-shorter-than-source"


def test_a_full_transcription_is_not_reported():
    body = "a" * 1000
    assert gates.check_text_coverage(_doc(body), source_chars=1000) is None


def test_a_source_we_could_not_count_stands_the_check_down():
    """An arXiv identifier has no local document, so there is nothing to compare."""
    assert gates.check_text_coverage(_doc("short"), source_chars=0) is None


def test_latex_markup_does_not_count_as_recovered_text():
    """Otherwise a page of \\begin{array} padding would look like full coverage."""
    md = _doc("\\begin{array}{cccccccccccccccccccccccccccccccc} " * 20)
    assert gates.check_text_coverage(md, source_chars=1500) is not None


# --------------------------------------------------------------------------
# wiring
# --------------------------------------------------------------------------

def test_run_all_reports_every_source_comparison_at_once(tmp_path):
    md = _doc(r"TABLE II. Continuation." + "\n\n$$\\begin{array}{cc")
    codes = {f.code for f in gates.run_all(md, images_dir=tmp_path,
                                           source_chars=4000, source_tables=2,
                                           source_rows=47)}
    assert {"tables-dropped", "unclosed-environment",
            "output-much-shorter-than-source"} <= codes


def test_without_source_counts_the_new_checks_stay_quiet(tmp_path):
    """The tex and arXiv-HTML rungs pass no census; they must not be accused."""
    codes = {f.code for f in gates.run_all(_doc(LONG_BODY), images_dir=tmp_path)}
    assert "tables-dropped" not in codes
    assert "output-much-shorter-than-source" not in codes


def test_a_clean_document_with_a_full_census_is_still_clean(tmp_path):
    body = "word " * 300
    md = _doc(body + "\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n")
    assert gates.run_all(md, images_dir=tmp_path, source_chars=1200,
                         source_tables=1, source_rows=3) == []
