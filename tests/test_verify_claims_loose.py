"""Loose-tier matching for claim verification.

PDF-extracted sources carry layout artifacts — ligatures, line-break
hyphenation, full-width CJK punctuation, spaces injected between CJK
characters. Honest quotes must still verify against them.
"""

from __future__ import annotations

from magi.kb.verify_claims import normalize_loose, verify_local


def _put(tmp_path, rel, text):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_ligature_and_hyphenation(tmp_path):
    # source as a PDF extractor would emit it
    _put(tmp_path, "raw/paper.md",
         "The eﬀective ﬁeld theory description is compli-\ncated by fracton immobility.\n")
    status, note = verify_local(
        "The effective field theory description is complicated by fracton immobility.",
        "raw/paper.md", str(tmp_path))
    assert status == "verified", note
    assert "loose" in note


def test_cjk_fullwidth_and_injected_spaces(tmp_path):
    _put(tmp_path, "raw/zh.md",
         "拓扑 序 的 基态 简并度 依赖 于 流形 的 亏格 ， 这 是 长程 纠缠 的 标志 。\n")
    status, note = verify_local(
        "拓扑序的基态简并度依赖于流形的亏格，这是长程纠缠的标志。",
        "raw/zh.md", str(tmp_path))
    assert status == "verified", note


def test_curly_quotes_and_dashes(tmp_path):
    _put(tmp_path, "raw/q.md",
         "The “restricted mobility” of excitations — a defining feature — persists.\n")
    status, note = verify_local(
        'The "restricted mobility" of excitations - a defining feature - persists.',
        "raw/q.md", str(tmp_path))
    assert status == "verified", note


def test_fabricated_quote_still_fails(tmp_path):
    _put(tmp_path, "raw/paper.md", "Fractons exhibit restricted mobility.\n")
    status, note = verify_local(
        "Fractons can move freely in all directions.",
        "raw/paper.md", str(tmp_path))
    assert status == "unverified"


def test_normalize_loose_folds_expected_artifacts():
    assert normalize_loose("eﬀective ﬁeld") == "effectivefield"
    assert normalize_loose("compli-\ncated") == "complicated"
    assert normalize_loose("，（）") == normalize_loose(",()")


# --------------------------------------------------------------------------
# a SOURCE that points out of the project
# --------------------------------------------------------------------------

QUOTE = "The gap closes at the boundary."


def _outside_with_the_evidence(tmp_path):
    """A real file, outside the project, that really does contain the quote.

    Both halves matter. A missing file answers "file not found" whether or not
    the guard is there, and a file without the quote answers "not found in
    source" — either way the test would pass against no guard at all.
    """
    project = tmp_path / "project"
    (project / "raw").mkdir(parents=True)
    outside = tmp_path / "elsewhere" / "private.md"
    outside.parent.mkdir(parents=True)
    outside.write_text(QUOTE + "\n", encoding="utf-8")
    return project, outside


def test_a_relative_source_cannot_climb_out_of_the_project(tmp_path):
    project, outside = _outside_with_the_evidence(tmp_path)

    status, note = verify_local(QUOTE, "../elsewhere/private.md", str(project))

    assert status == "unverified", (
        f"a claim verified itself against {outside}, which is outside the "
        f"project: {note}")
    assert "traversal" in note


def test_an_absolute_source_cannot_reach_outside_either(tmp_path):
    project, outside = _outside_with_the_evidence(tmp_path)

    status, note = verify_local(QUOTE, str(outside), str(project))

    assert status == "unverified", note
    assert "traversal" in note


def test_the_same_evidence_inside_the_project_still_verifies(tmp_path):
    """The other side of the guard, so it cannot be widened into refusing
    everything: the identical quote, in the identical file, inside."""
    project, _ = _outside_with_the_evidence(tmp_path)
    (project / "raw" / "private.md").write_text(QUOTE + "\n", encoding="utf-8")

    status, note = verify_local(QUOTE, "raw/private.md", str(project))

    assert status == "verified", note
