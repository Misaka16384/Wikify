"""Contracts for the post-conversion checks.

Each of these exists because a real conversion went wrong in exactly this way
while reporting success. None of them block an item — they decide what a
reviewer is told and which items to look at first.
"""

import pytest

from magi.ingest import gates


def _doc(body: str, arxiv_id: str | None = None) -> str:
    fm = "---\ntitle: X\n"
    if arxiv_id:
        fm += f"arxiv_id: '{arxiv_id}'\n"
    return fm + "---\n\n" + body


LONG_BODY = "word " * 300


# --------------------------------------------------------------------------
# A PDF where source was expected
# --------------------------------------------------------------------------

def test_a_pdf_payload_is_caught_by_its_magic_bytes():
    """arXiv serves the PDF for submissions uploaded as PDF only."""
    finding = gates.check_payload_is_not_pdf(b"%PDF-1.7\n%\xe2\xe3")
    assert finding is not None
    assert finding.code == "payload-is-pdf"


def test_a_gzip_payload_is_not_flagged_as_pdf():
    assert gates.check_payload_is_not_pdf(b"\x1f\x8b\x08\x00") is None


def test_an_empty_payload_does_not_crash_the_check():
    assert gates.check_payload_is_not_pdf(b"") is None


# --------------------------------------------------------------------------
# Shell output
# --------------------------------------------------------------------------

def test_a_body_of_a_few_words_is_flagged():
    finding = gates.check_not_a_shell(_doc("Only a handful of words here."))
    assert finding is not None
    assert finding.code == "suspiciously-short"


def test_a_normal_paper_is_not_flagged():
    assert gates.check_not_a_shell(_doc(LONG_BODY)) is None


def test_an_input_heavy_source_sharpens_the_explanation():
    """The named failure: a stub main file whose \\input's were never assembled."""
    tex = r"\documentclass{article}\input{sec1}\input{sec2}\include{sec3}"
    finding = gates.check_not_a_shell(_doc("Short."), tex_source=tex)
    assert "3 \\input" in finding.detail


def test_frontmatter_does_not_count_towards_the_word_total():
    """A long YAML header must not disguise an empty document."""
    md = "---\n" + "key: value\n" * 200 + "---\n\nTiny.\n"
    assert gates.check_not_a_shell(md) is not None


def test_the_short_check_is_a_flag_not_a_block():
    """A genuine four-paragraph Comment or erratum exists."""
    finding = gates.check_not_a_shell(_doc("Short erratum text."))
    assert finding.severity == "flag"


# --------------------------------------------------------------------------
# Leftover TeX
# --------------------------------------------------------------------------

def test_raw_tex_surviving_into_the_prose_is_caught():
    """Pandoc exiting 0 while leaving the macro it choked on inline."""
    finding = gates.check_no_leftover_tex(_doc(r"Text \cite{foo} more \ref{bar}."))
    assert finding is not None
    assert finding.code == "leftover-tex"


def test_tex_inside_math_is_not_leftover():
    """`\\begin{aligned}` in a display block is the correct output, not a defect."""
    body = "Prose.\n\n$$\n\\begin{aligned}\na &= b\n\\end{aligned}\n$$\n\n" + LONG_BODY
    assert gates.check_no_leftover_tex(_doc(body)) is None


def test_tex_inside_a_fenced_code_block_is_not_leftover():
    body = "Here is an example:\n\n```latex\n\\begin{document}\n```\n\n" + LONG_BODY
    assert gates.check_no_leftover_tex(_doc(body)) is None


def test_inline_math_is_not_leftover():
    assert gates.check_no_leftover_tex(_doc(r"The value $\alpha \ne \beta$ holds.")) is None


def test_clean_prose_produces_nothing():
    assert gates.check_no_leftover_tex(_doc(LONG_BODY)) is None


def test_the_offending_commands_are_named():
    finding = gates.check_no_leftover_tex(_doc(r"\usepackage{amsmath} and \label{eq:1}"))
    assert "usepackage" in finding.detail or "label" in finding.detail


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

def test_dropped_figures_are_counted():
    """arXiv 2401.00506: six referenced, zero survived, run reported success."""
    finding = gates.check_figures(referenced=6, resolved=0)
    assert finding is not None
    assert "6" in finding.detail and "0" in finding.detail


def test_all_figures_present_is_silent():
    assert gates.check_figures(referenced=4, resolved=4) is None


def test_a_paper_with_no_figures_is_silent():
    assert gates.check_figures(referenced=0, resolved=0) is None


def test_more_resolved_than_referenced_is_not_an_error():
    assert gates.check_figures(referenced=2, resolved=3) is None


# --------------------------------------------------------------------------
# Broken image links
# --------------------------------------------------------------------------

def test_an_image_reference_with_no_file_is_caught(tmp_path):
    """Rewriting a path without fetching the file looks complete and is not."""
    finding = gates.check_broken_image_links(
        _doc("![cap](images/missing.png)"), tmp_path)
    assert finding is not None
    assert "missing.png" in finding.detail


def test_a_present_image_is_silent(tmp_path):
    (tmp_path / "fig.png").write_bytes(b"x")
    assert gates.check_broken_image_links(_doc("![c](images/fig.png)"), tmp_path) is None


def test_html_img_references_are_checked_too(tmp_path):
    """Pandoc leaves <figure>-wrapped images as raw HTML, which is most of them."""
    finding = gates.check_broken_image_links(
        _doc('<img src="images/gone.png" id="f1"/>'), tmp_path)
    assert finding is not None and "gone.png" in finding.detail


def test_external_images_are_not_expected_on_disk(tmp_path):
    md = _doc("![x](https://example.com/a.png)\n![y](/static/logo.svg)")
    assert gates.check_broken_image_links(md, tmp_path) is None


def test_a_malformed_reference_is_not_also_reported_as_a_missing_file(tmp_path):
    """One problem is one finding. A path that cannot resolve anywhere is
    check_image_refs's to report; saying it twice says it is two problems."""
    md = _doc("![c](C:/Temp/tmp1/images/a.png)")
    assert gates.check_broken_image_links(md, tmp_path) is None
    assert gates.check_image_refs(md) is not None


# --------------------------------------------------------------------------
# Image references that will not survive the move out of staging
# --------------------------------------------------------------------------

def test_an_absolute_staging_path_is_caught():
    """The defect this check exists for, and the one its predecessor could not
    see: `pymupdf4llm` references each image by the directory it was handed,
    so pointing it at staging put an absolute temp path in every reference.
    The old check matched `](images/…)` and nothing else, so it read that
    document as having no image references at all and reported it clean.

    A gate that only recognises the correct answer cannot report a wrong one.
    """
    finding = gates.check_image_refs(
        _doc("![](C:/Users/x/AppData/Local/Temp/tmp1/images/p.pdf-0001-01.png)"))
    assert finding is not None
    assert finding.code == "image-path-not-portable"
    assert "absolute" in finding.detail


def test_a_posix_staging_path_is_caught_too():
    finding = gates.check_image_refs(_doc("![](/tmp/magi-staging/images/a.png)"))
    assert finding is not None and finding.code == "image-path-not-portable"


def test_a_bare_filename_is_caught():
    """Renders next to the document in staging and nowhere after the move."""
    assert gates.check_image_refs(_doc("![](fig1.png)")) is not None


def test_a_path_climbing_out_of_the_document_is_caught():
    assert gates.check_image_refs(_doc("![](../images/a.png)")) is not None


def test_html_references_are_judged_by_the_same_rule():
    """Most real arXiv figures survive pandoc as raw HTML, so a check that only
    reads ![]() is blind to the majority of them."""
    finding = gates.check_image_refs(_doc('<img src="C:/Temp/t/images/a.png"/>'))
    assert finding is not None


def test_the_convention_itself_passes():
    assert gates.check_image_refs(_doc("![c](images/2401.00506-fig1.png)")) is None


def test_remote_images_are_not_a_portability_problem():
    assert gates.check_image_refs(
        _doc("![x](https://arxiv.org/static/logo.svg)\n![y](data:image/png;base64,AA)")) is None


def test_every_kind_of_wrongness_is_named_in_one_finding():
    """A reviewer gets told what is wrong with each, not just that something is."""
    finding = gates.check_image_refs(
        _doc("![](/tmp/x/a.png)\n![](b.png)\n![](../c.png)\n![](figs/d.png)"))
    assert finding is not None
    assert "4 image reference(s)" in finding.detail
    for word in ("absolute", "no directory", "climbs out", "not under images/"):
        assert word in finding.detail


def test_a_document_with_no_images_is_silent():
    assert gates.check_image_refs(_doc(LONG_BODY)) is None


def test_run_all_reports_an_unportable_path_without_an_images_dir():
    """The shape check needs no directory to run, which matters: the routes that
    got this wrong are exactly the ones that did not report an images_dir."""
    findings = gates.run_all(_doc("![](C:/Temp/t/images/a.png)\n" + LONG_BODY))
    assert "image-path-not-portable" in {f.code for f in findings}


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------

def test_a_mismatched_arxiv_id_is_caught():
    """A misnamed download files the wrong paper under the right name."""
    finding = gates.check_identity_agrees("2608.16520", _doc(LONG_BODY, "1234.56789"))
    assert finding is not None
    assert finding.code == "identity-mismatch"


def test_a_matching_id_is_silent():
    assert gates.check_identity_agrees("2608.16520", _doc(LONG_BODY, "2608.16520")) is None


def test_a_version_suffix_is_not_a_mismatch():
    assert gates.check_identity_agrees("2608.16520v2", _doc(LONG_BODY, "2608.16520")) is None


def test_a_legacy_id_compares_correctly():
    assert gates.check_identity_agrees(
        "cond-mat/0506438", _doc(LONG_BODY, "cond-mat/0506438")) is None


def test_no_expectation_means_nothing_to_check():
    assert gates.check_identity_agrees(None, _doc(LONG_BODY, "2608.16520")) is None


def test_no_id_in_the_output_is_not_a_mismatch():
    assert gates.check_identity_agrees("2608.16520", _doc(LONG_BODY)) is None


# --------------------------------------------------------------------------
# run_all
# --------------------------------------------------------------------------

def test_a_clean_document_produces_no_findings(tmp_path):
    assert gates.run_all(_doc(LONG_BODY), images_dir=tmp_path) == []


def test_several_problems_are_all_reported(tmp_path):
    md = _doc(r"Short \cite{x} text. ![f](images/nope.png)", "1111.11111")
    findings = gates.run_all(md, figures_referenced=3, figures_resolved=0,
                             images_dir=tmp_path, expected_arxiv_id="2608.16520")
    codes = {f.code for f in findings}

    assert {"identity-mismatch", "suspiciously-short", "leftover-tex",
            "figure-count-mismatch", "broken-image-links"} <= codes


def test_the_pdf_check_only_runs_when_a_payload_is_given(tmp_path):
    findings = gates.run_all(_doc(LONG_BODY), images_dir=tmp_path)
    assert "payload-is-pdf" not in {f.code for f in findings}


def test_findings_are_ordered_most_alarming_first(tmp_path):
    """A reviewer reads top-down; identity trouble outranks a missing figure."""
    md = _doc("Short.", "1111.11111")
    findings = gates.run_all(md, figures_referenced=1, figures_resolved=0,
                             expected_arxiv_id="2608.16520")
    assert findings[0].code == "identity-mismatch"


# --------------------------------------------------------------------------
# repetition: the check belongs to the routes that can actually loop
# --------------------------------------------------------------------------

def test_a_latexml_conversion_is_not_asked_whether_it_looped():
    r"""Measured on a real 37-paper library, all converted from LaTeX: this
    fired on 36 of them. Three things were repeating — inlined base64
    figures, 200-character runs of whitespace, and LaTeXML's own PGF
    internals (`\lx@inpgf@ignorespaces`, 181 times in one paper).

    None is a converter restating a page. A flag that is on for everything is
    off, and worse, it desensitises the reader to the real conversion failures
    beside it in the same list.
    """
    looped = ("Some varied prose about stabilizer codes and their invariants. " * 40)
    for route in ("arxiv-html", "tex", "textlayer"):
        codes = {f.code for f in gates.run_all(looped, route=route)}
        assert "repetition-loop" not in codes, route


def test_a_recognition_route_is_still_asked():
    """The failure it was built for is real: glm-ocr returned a page twice."""
    looped = ("Some varied prose about stabilizer codes and their invariants. " * 40)
    for route in sorted(gates.RECOGNITION_ROUTES):
        codes = {f.code for f in gates.run_all(looped, route=route)}
        assert "repetition-loop" in codes, route


def test_an_inlined_figure_is_not_a_restatement():
    """ar5iv inlines figures as base64. Those runs are entirely alphanumeric
    and highly varied, so they pass every test meant to spot filler — and a
    3 MB paper carries megabytes of them."""
    import hashlib

    varied = "".join(hashlib.sha256(str(i).encode()).hexdigest() for i in range(40))
    blob = "data:image/png;base64," + varied
    # The same figure inlined twice, which is ordinary in a paper — and enough
    # for every 200-character window inside it to occur more than once.
    doc = f"---\ntitle: x\n---\n\n![a]({blob})\n\nprose\n\n![a again]({blob})\n"
    assert gates.repetition_runs(doc) == 1


def test_a_wall_of_whitespace_is_not_a_restatement():
    """The worst offender in the real corpus repeated 1718 times and was 200
    characters of whitespace with one stray character in it — "varied" by
    period, and entirely wordless."""
    body = ((" " * 199 + ".") * 12)
    assert gates.repetition_runs(f"---\ntitle: x\n---\n\n{body}\n") == 1
