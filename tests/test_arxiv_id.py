"""Contracts for the shared arXiv identifier parser.

The pattern this replaced matched only the modern YYMM.NNNNN form. Measured
against a real 758-item library, 18 of 213 resolvable identifiers were in the
pre-2007 archive/YYMMNNN form, so the legacy cases below are not hypothetical.
"""

import pytest

from magi.core.arxiv_id import (
    abs_url,
    find_arxiv_id,
    is_legacy,
    normalize_arxiv_id,
)


@pytest.mark.parametrize("raw,expected", [
    # Modern
    ("2608.16520", "2608.16520"),
    ("2608.16520v3", "2608.16520"),
    ("arXiv:2405.00208", "2405.00208"),
    ("https://arxiv.org/abs/2405.00208", "2405.00208"),
    ("https://arxiv.org/pdf/2405.00208v2", "2405.00208"),
    ("https://arxiv.org/e-print/2405.00208", "2405.00208"),
    ("2608.16520.tar.gz", "2608.16520"),
    ("2608.16520.tgz", "2608.16520"),
    ("10.48550/arXiv.2405.00208", "2405.00208"),
    # Legacy — the half that used to be dropped
    ("cond-mat/0506438", "cond-mat/0506438"),
    ("hep-th/9711200", "hep-th/9711200"),
    ("arXiv:1703.07038 [physics]", "1703.07038"),
    ("https://arxiv.org/abs/cond-mat/0506438", "cond-mat/0506438"),
    ("math.AG/0601001", "math.AG/0601001"),
    ("quant-ph/9705052v2", "quant-ph/9705052"),
    # Zotero's malformed-but-real values
    ("None arxiv:1212.5121", "1212.5121"),
])
def test_ids_are_recovered_and_version_stripped(raw, expected):
    assert normalize_arxiv_id(raw) == expected


@pytest.mark.parametrize("raw", [
    None,
    "",
    "no identifier here",
    "10.1103/PhysRevB.108.014301",   # a plain DOI is not an arXiv id
    "2026-08-21",                    # a date must not look like one
    "1234.5",                        # too few digits after the dot
])
def test_non_ids_return_none(raw):
    assert normalize_arxiv_id(raw) is None


def test_archive_case_is_canonicalised_but_the_serial_is_not():
    assert normalize_arxiv_id("COND-MAT/0506438") == "cond-mat/0506438"


def test_version_can_be_kept_when_asked():
    assert find_arxiv_id("2608.16520v3", keep_version=True) == "2608.16520v3"
    assert find_arxiv_id("2608.16520v3") == "2608.16520"


def test_legacy_is_flagged():
    assert is_legacy("cond-mat/0506438")
    assert not is_legacy("2608.16520")


def test_abs_url_round_trips_both_forms():
    for ident in ("2608.16520", "cond-mat/0506438"):
        assert normalize_arxiv_id(abs_url(ident)) == ident


def test_a_doi_that_merely_contains_digits_is_not_an_id():
    """Guard against the DOI 10.1016/j.nuclphysb.2019.114661 style false match."""
    assert normalize_arxiv_id("10.1016/j.nuclphysb.2019.114661") is None


@pytest.mark.parametrize("text", [
    "see figures/1234567 for the layout",
    "output/0601001 was regenerated",
    "data/9711200.csv",
    "notes/2024001 draft",
])
def test_a_path_shaped_like_a_legacy_id_is_not_one(text):
    """radar scans free-text markdown; `figures/1234567` must not read as a paper.

    This is why the legacy archive list is enumerated rather than shape-matched.
    """
    assert normalize_arxiv_id(text) is None


def test_every_enumerated_archive_parses():
    """The legacy archive list is closed; make sure none of it is dead weight."""
    from magi.core.arxiv_id import _LEGACY_ARCHIVES
    for archive in _LEGACY_ARCHIVES:
        ident = f"{archive}/0601001"
        assert normalize_arxiv_id(ident) == ident, archive


def test_math_ph_is_not_shadowed_by_math():
    """Alternation order matters: `math` must not swallow `math-ph`."""
    assert normalize_arxiv_id("math-ph/0601001") == "math-ph/0601001"
