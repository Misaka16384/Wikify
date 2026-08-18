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
