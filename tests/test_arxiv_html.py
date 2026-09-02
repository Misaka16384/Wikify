"""Contracts for the arXiv HTML route.

The two rejection cases below are not hypothetical — both were produced by
fetching real papers while measuring coverage, and a naive status-code check
counted both as successes.
"""

import pytest

from magi.ingest import arxiv_html as ah


# A compact stand-in for a real LaTeXML rendering. The real thing runs 150 KB
# to 1.3 MB; what matters structurally is the alttext/annotation pair.
def _rendering(formulas=("E=mc^{2}", r"\frac{\hbar^{2}k^{2}}{2m}"), title="Some Real Paper"):
    maths = "\n".join(
        f'<math id="m{i}" class="ltx_Math" alttext="{f}" display="inline">'
        f"<semantics><mrow/>"
        f'<annotation encoding="application/x-tex">{f}</annotation>'
        f"</semantics></math>"
        for i, f in enumerate(formulas)
    )
    padding = "<p>body text</p>" * 2000      # clear the error-page size floor
    return (f"<html><head><title>[2608.16520] {title}</title></head>"
            f"<body>{maths}{padding}</body></html>").encode("utf-8")


ERROR_PAGE = (b"<!DOCTYPE html><html><head><title>arXiv error</title></head>"
              b"<body>Page not found</body></html>")

ABSTRACT_PAGE = (b"<html><head><title>[2608.20310] Signatures of a condensate</title>"
                 b"</head><body>" + b"<p>abstract text</p>" * 2000 + b"</body></html>")


# --------------------------------------------------------------------------
# Telling a rendering from something that merely returned 200
# --------------------------------------------------------------------------

def test_a_real_rendering_is_accepted():
    ok, why = ah._looks_like_a_paper(
        _rendering(), "https://arxiv.org/html/2608.16520",
        "https://arxiv.org/html/2608.16520")
    assert ok, why


def test_the_arxiv_error_page_is_rejected():
    """A missing /html paper returns a full HTML error page, not an empty body."""
    ok, why = ah._looks_like_a_paper(
        ERROR_PAGE, "https://arxiv.org/html/2608.20310",
        "https://arxiv.org/html/2608.20310")
    assert not ok
    assert "error page" in why


def test_an_ar5iv_redirect_to_the_abstract_is_rejected():
    """The false positive that inflated a coverage measurement.

    ar5iv answers a paper it cannot render with HTTP 200 and a redirect to
    arxiv.org/abs/<id>. The body is a real page — of the abstract — and carries
    no math at all. Scoring on the status code counts it as coverage.
    """
    ok, why = ah._looks_like_a_paper(
        ABSTRACT_PAGE, "https://ar5iv.labs.arxiv.org/html/2608.20310",
        "https://arxiv.org/abs/2608.20310")
    assert not ok
    assert "abstract page" in why


def test_a_rendering_without_alttext_is_rejected():
    """A page about the right paper is still useless if the TeX is not in it."""
    page = b"<html><body>" + b"<p>prose only</p>" * 3000 + b"</body></html>"
    ok, why = ah._looks_like_a_paper(
        page, "https://arxiv.org/html/x", "https://arxiv.org/html/x")
    assert not ok
    assert "alttext" in why


# --------------------------------------------------------------------------
# Getting the TeX back out
# --------------------------------------------------------------------------

def test_formulas_come_back_as_the_original_tex():
    page = _rendering().decode("utf-8")
    assert ah.extract_tex_formulas(page) == ["E=mc^{2}", r"\frac{\hbar^{2}k^{2}}{2m}"]


def test_the_annotation_element_wins_over_the_escaped_attribute():
    """alttext is HTML-escaped; the annotation element is not.

    Reading the attribute means an unescaping round-trip that can mangle a
    literal `<` or `\\&`. Prefer the element when both are present.
    """
    page = ('<math alttext="a &lt; b &amp; c">'
            '<annotation encoding="application/x-tex">a &lt; b &amp; c</annotation>'
            "</math>")
    assert ah.extract_tex_formulas(page) == ["a < b & c"]


def test_alttext_is_the_fallback_when_no_annotation_exists():
    page = '<math alttext="x^{2}"><mrow/></math>'
    assert ah.extract_tex_formulas(page) == ["x^{2}"]


def test_no_math_yields_no_formulas():
    assert ah.extract_tex_formulas("<html><body>prose</body></html>") == []


# --------------------------------------------------------------------------
# Title
# --------------------------------------------------------------------------

def test_the_arxiv_id_prefix_is_stripped_from_the_title():
    page = "<html><head><title>[2608.16520] Maximal Torus Entropy</title></head></html>"
    assert ah.page_title(page) == "Maximal Torus Entropy"


def test_a_legacy_id_prefix_is_stripped_too():
    page = "<html><head><title>[cond-mat/0506438] An Older Paper</title></head></html>"
    assert ah.page_title(page) == "An Older Paper"


def test_a_missing_title_is_none():
    assert ah.page_title("<html><body>no head</body></html>") is None


# --------------------------------------------------------------------------
# Figure paths
# --------------------------------------------------------------------------

def test_relative_figure_paths_are_pointed_at_images():
    """arXiv serves figures under {id}v{n}/; the rest of the pipeline wants images/."""
    md, n, mapping = ah._rewrite_image_paths(
        "![A caption](2401.00506v2/sbs.jpg)\n", "2401.00506")
    assert md == "![A caption](images/2401.00506-sbs.jpg)\n"
    assert n == 1
    assert mapping == {"2401.00506v2/sbs.jpg": "2401.00506-sbs.jpg"}


def test_figure_files_carry_the_paper_id():
    """raw/papers/images/ is shared by the whole library, and `fig1.png` is not
    a unique name in any library holding two papers. Without the prefix the
    second commit silently overwrote the first and one paper then displayed the
    other's figure — no error, nothing missing, just the wrong picture."""
    a, _, a_map = ah._rewrite_image_paths('<img src="2401.00506v1/fig1.png"/>', "2401.00506")
    b, _, b_map = ah._rewrite_image_paths('<img src="2502.11111v2/fig1.png"/>', "2502.11111")

    assert set(a_map.values()).isdisjoint(b_map.values())
    assert 'src="images/2401.00506-fig1.png"' in a
    assert 'src="images/2502.11111-fig1.png"' in b


def test_a_legacy_id_stays_one_path_segment():
    """cond-mat/0001002 has a slash in it; a filename may not."""
    md, _, mapping = ah._rewrite_image_paths(
        '<img src="cond-mat/0001002v1/fig1.png"/>', "cond-mat/0001002")
    assert mapping == {"cond-mat/0001002v1/fig1.png": "cond-mat-0001002-fig1.png"}
    assert "images/cond-mat-0001002-fig1.png" in md


def test_absolute_and_data_urls_are_left_alone():
    src = "![x](https://example.com/a.png)\n![y](data:image/png;base64,AAA)\n"
    md, n, mapping = ah._rewrite_image_paths(src, "2401.00506")
    assert md == src
    assert n == 0 and mapping == {}


def test_an_already_rewritten_path_is_not_rewritten_twice():
    md, n, mapping = ah._rewrite_image_paths("![a](images/fig.png)\n", "x")
    assert md == "![a](images/fig.png)\n"
    assert n == 0 and mapping == {}


# --------------------------------------------------------------------------
# Figures are actually fetched
# --------------------------------------------------------------------------

def test_figures_are_downloaded_next_to_the_markdown(tmp_path, monkeypatch):
    """Rewriting a path without fetching the file leaves a broken link, which is
    worse than the tarball route's silent drop, not better."""
    monkeypatch.setattr(ah, "http_get",
                        lambda url, timeout=60, throttle=None: (b"\x89PNG-bytes", "image/png", url))

    ok, failures = ah.download_figures(
        {"2401.00506v2/sbs.jpg": "2401.00506-sbs.jpg",
         "2401.00506v2/disp.png": "2401.00506-disp.png"},
        "https://arxiv.org/html/2401.00506v2", tmp_path / "images")

    assert ok == 2 and failures == []
    assert (tmp_path / "images" / "2401.00506-sbs.jpg").read_bytes() == b"\x89PNG-bytes"
    assert (tmp_path / "images" / "2401.00506-disp.png").exists()


def test_a_figure_is_fetched_once_even_if_referenced_twice(tmp_path, monkeypatch):
    """A paper that shows the same figure twice has two references and one file.

    Runs through the rewrite instead of handing download_figures a made-up
    duplicate, because the mapping is what makes this true and a made-up
    argument would not exercise it. At 15 s per arXiv request a needless second
    fetch is not a rounding error."""
    calls = []

    def fake_get(url, timeout=60, throttle=None):
        calls.append(url)
        return b"x", "image/png", url

    monkeypatch.setattr(ah, "http_get", fake_get)
    md, n, mapping = ah._rewrite_image_paths(
        "![one](2401.00506v2/a.png)\n![again](2401.00506v2/a.png)\n", "2401.00506")
    assert n == 2 and len(mapping) == 1

    ok, _ = ah.download_figures(mapping, "https://arxiv.org/html/x", tmp_path / "images")
    assert ok == 1 and len(calls) == 1


def test_one_failed_figure_does_not_abort_the_rest(tmp_path, monkeypatch):
    def fake_get(url, timeout=60, throttle=None):
        if "bad" in url:
            raise RuntimeError("HTTP Error 404: Not Found")
        return b"ok", "image/png", url

    monkeypatch.setattr(ah, "http_get", fake_get)
    ok, failures = ah.download_figures({"v2/bad.png": "x-bad.png",
                                        "v2/good.png": "x-good.png"},
                                       "https://arxiv.org/html/x", tmp_path / "images")

    assert ok == 1
    assert len(failures) == 1 and "bad.png" in failures[0]
    assert (tmp_path / "images" / "x-good.png").exists()


def test_figure_urls_resolve_against_the_page_url(tmp_path, monkeypatch):
    """The page URL ends in the paper id, which is a resource, not a directory.

    Treating it as a directory doubles the id into the path and every figure
    404s: .../html/2401.00506v2/2401.00506v2/sbs.jpg
    """
    seen = []

    def fake_get(url, timeout=60, throttle=None):
        seen.append(url)
        return b"x", "image/png", url

    monkeypatch.setattr(ah, "http_get", fake_get)
    ah.download_figures({"2401.00506v2/sbs.jpg": "2401.00506-sbs.jpg"},
                        "https://arxiv.org/html/2401.00506v2", tmp_path / "images")

    assert seen == ["https://arxiv.org/html/2401.00506v2/sbs.jpg"]


def test_arxiv_site_chrome_is_not_mistaken_for_a_figure():
    """The rendering also carries funder logos and UI glyphs as /static/... paths."""
    src = ("![](/static/base/1.0.1/images/icons/smileybones-small.svg)\n"
           "![Refer to caption](2608.20333v1/torus.png)\n")
    md, n, mapping = ah._rewrite_image_paths(src, "2608.20333")

    assert n == 1
    assert mapping == {"2608.20333v1/torus.png": "2608.20333-torus.png"}
    assert "![Refer to caption](images/2608.20333-torus.png)" in md
    # Not downloaded into this paper's images/ — but pointed somewhere real.
    assert ("https://arxiv.org/static/base/1.0.1/images/icons/"
            "smileybones-small.svg") in md


def test_raw_html_img_tags_are_rewritten_too():
    """Pandoc leaves a <figure>-wrapped image as raw HTML, which is what every
    real arXiv figure is. Measured on 2608.20333: both figures came through as
    <img> and only arXiv's own glyph became Markdown."""
    src = '<img src="2608.20333v1/torus.png" id="S2.F1.g1" class="ltx_graphics"/>\n'
    md, n, mapping = ah._rewrite_image_paths(src, "2608.20333")

    assert n == 1
    assert mapping == {"2608.20333v1/torus.png": "2608.20333-torus.png"}
    assert 'src="images/2608.20333-torus.png"' in md
    assert 'id="S2.F1.g1"' in md          # the rest of the tag is preserved


def test_html_and_markdown_figures_are_both_counted():
    src = ('![cap](2608.20333v1/a.png)\n'
           '<img src="2608.20333v1/b.png" id="x"/>\n')
    md, n, mapping = ah._rewrite_image_paths(src, "2608.20333")

    assert n == 2
    assert set(mapping) == {"2608.20333v1/a.png", "2608.20333v1/b.png"}
    assert ("![cap](images/2608.20333-a.png)" in md
            and 'src="images/2608.20333-b.png"' in md)


def test_html_chrome_images_are_not_treated_as_this_papers_figures():
    src = '<img src="/static/base/1.0.1/images/funders/logo.png" class="ds-funder-logo"/>\n'
    md, n, mapping = ah._rewrite_image_paths(src, "2608.20333")
    assert n == 0 and mapping == {}
    assert 'class="ds-funder-logo"' in md


def test_site_chrome_is_pointed_at_arxiv_rather_than_left_dangling():
    """Pandoc drags the whole page in, so the output carries arXiv's furniture
    as site-rooted paths. Those name a filesystem root with no such file — dead
    links dressed as working ones, and one `image-path-not-portable` finding on
    every single arXiv paper if left that way."""
    from magi.ingest import gates

    md, _, _ = ah._rewrite_image_paths(
        '![](/static/base/1.0.1/images/icons/smileybones-small.svg)\n'
        '![cap](2608.20333v1/torus.png)\n', "2608.20333")

    assert "](https://arxiv.org/static/base/1.0.1/images/icons/" in md
    assert gates.check_image_refs(md) is None


def test_a_relative_path_that_is_not_this_papers_figure_is_left_alone():
    """Only {id}v{n}/... is this paper's figure directory."""
    md, n, mapping = ah._rewrite_image_paths(
        "![x](someother/thing.png)\n", "2608.20333")
    assert n == 0 and mapping == {}
    assert md == "![x](someother/thing.png)\n"


# --------------------------------------------------------------------------
# align regrouping
# --------------------------------------------------------------------------

def test_consecutive_aligned_rows_are_folded_back_into_one_block():
    """LaTeXML splits an align environment into table rows; pandoc keeps them
    separate. MathJax then shows several equations instead of one aligned set."""
    src = "$$\na &= b + c\n$$\n$$\n&\\quad + d\n$$\n"
    md, runs = ah._regroup_align_tables(src)
    assert runs == 1
    assert r"\begin{aligned}" in md and r"\end{aligned}" in md
    assert "a &= b + c" in md and r"&\quad + d" in md


def test_unrelated_consecutive_equations_are_not_merged():
    """Two display equations with no alignment anchors are two equations."""
    src = "$$\nE = mc^2\n$$\n$$\nF = ma\n$$\n"
    md, runs = ah._regroup_align_tables(src)
    assert runs == 0
    assert r"\begin{aligned}" not in md


def test_a_lone_equation_is_untouched():
    src = "$$\na &= b\n$$\n"
    md, runs = ah._regroup_align_tables(src)
    assert runs == 0
    assert md == src


# --------------------------------------------------------------------------
# fetch() ordering
# --------------------------------------------------------------------------

def test_native_is_tried_before_ar5iv(monkeypatch):
    seen = []

    def fake_get(url, timeout=60, throttle=None):
        seen.append(url)
        return _rendering(), "text/html", url

    monkeypatch.setattr(ah, "http_get", fake_get)
    got = ah.fetch("2608.16520")

    assert got.ok and got.endpoint == "arxiv"
    assert seen == ["https://arxiv.org/html/2608.16520"]


def test_ar5iv_is_used_when_native_has_no_rendering(monkeypatch):
    def fake_get(url, timeout=60, throttle=None):
        if "ar5iv" in url:
            return _rendering(), "text/html", url
        return ERROR_PAGE, "text/html", url

    monkeypatch.setattr(ah, "http_get", fake_get)
    got = ah.fetch("cond-mat/0506438")

    assert got.ok and got.endpoint == "ar5iv"


def test_missing_on_both_endpoints_reports_why(monkeypatch):
    monkeypatch.setattr(ah, "http_get",
                        lambda url, timeout=60, throttle=None: (ERROR_PAGE, "", url))
    got = ah.fetch("2608.20310")

    assert not got.ok
    assert "ar5iv" in got.reason


def test_a_non_identifier_fails_before_any_request(monkeypatch):
    def explode(*a, **k):
        raise AssertionError("should not have made a request")

    monkeypatch.setattr(ah, "http_get", explode)
    result = ah.convert("not-an-arxiv-id", "/tmp/whatever")

    assert result.success is False


# --------------------------------------------------------------------------
# titles: two silent failures, both measured on live pages
# --------------------------------------------------------------------------

def test_a_title_split_across_markup_keeps_its_spaces():
    """2204.06023 arrived as "Homological invariants ofPauli stabilizer codes".

    The pattern captured raw HTML and whitespace-collapsed it, so the words on
    either side of a tag were welded together. Deleting tags is what does it;
    they have to become spaces.
    """
    page = ('<html><head><title>Homological invariants of'
            '<span class="x">Pauli</span> stabilizer codes</title></head>'
            '<body>x</body></html>')
    assert ah.page_title(page) == "Homological invariants of Pauli stabilizer codes"


def test_the_document_title_wins_over_the_page_title():
    """`<title>` is whatever the converter had to hand; the document title is
    the paper's by construction."""
    page = ('<html><head><title>Something Else</title></head><body>'
            '<h1 class="ltx_title ltx_title_document">The Real Title</h1>'
            '</body></html>')
    assert ah.page_title(page) == "The Real Title"


@pytest.mark.parametrize("heading", ["Abstract", "1Introduction", "2.1 Introduction",
                                     "Zusammenfassung", "References"])
def test_a_section_heading_is_refused_rather_than_returned_as_a_title(heading):
    """1806.08679 came back as "Abstract" and 2406.12962 as "1Introduction" —
    documents with no title element, where `<title>` holds the first heading.

    None sends the caller to the arXiv id, which is obviously not a title and
    gets noticed. A plausible wrong title does not: the session that found
    this nearly filed a direct competitor under a truncated name.
    """
    page = f"<html><head><title>{heading}</title></head><body>x</body></html>"
    assert ah.page_title(page) is None


@pytest.mark.parametrize("real", ["2D materials and their defects",
                                  "3-manifolds and their invariants"])
def test_a_real_title_that_starts_with_a_number_survives(real):
    """The number is stripped before the word is judged, so the check lands on
    "D materials..." rather than on the digit. A false positive here costs a
    real title."""
    page = f"<html><head><title>{real}</title></head><body>x</body></html>"
    assert ah.page_title(page) == real


def test_the_arxiv_id_prefix_is_still_stripped():
    page = "<html><head><title>[2608.20333] Real Title Here</title></head></html>"
    assert ah.page_title(page) == "Real Title Here"
