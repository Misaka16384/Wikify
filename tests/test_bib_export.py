"""magi bib — BibTeX export from reference cards."""

from __future__ import annotations

from magi.kb import bib_export


def _card(tmp_path, slug, fm_lines):
    refs = tmp_path / "wiki" / "references"
    refs.mkdir(parents=True, exist_ok=True)
    p = refs / f"{slug}.md"
    p.write_text("---\n" + "\n".join(fm_lines) + "\n---\n\n正文。\n", encoding="utf-8")
    return p


def test_entry_from_frontmatter(tmp_path):
    card = _card(tmp_path, "pretko-2020-fracton", [
        "title: Fracton Phases of Matter",
        "authors:",
        "  - Michael Pretko",
        "  - Xie Chen",
        "year: 2020",
        "venue: Int. J. Mod. Phys. A",
        "arxiv_id: '2001.01722'",
    ])
    fm = bib_export._read_frontmatter(card)
    entry = bib_export.build_entry(card, fm)
    assert entry.startswith("@article{pretko2020,")
    assert "title = {Fracton Phases of Matter}" in entry
    assert "author = {Michael Pretko and Xie Chen}" in entry
    assert "eprint = {2001.01722}" in entry
    assert "url = {https://arxiv.org/abs/2001.01722}" in entry


def test_misc_when_no_venue_and_cjk_safe(tmp_path):
    card = _card(tmp_path, "you-2019", [
        "title: 高阶规范理论与分数子",
        "authors: 尤肖江; 王强",
        "year: 2019",
    ])
    fm = bib_export._read_frontmatter(card)
    entry = bib_export.build_entry(card, fm)
    assert entry.startswith("@misc{")
    assert "高阶规范理论与分数子" in entry


def test_cli_slug_lookup_and_output_file(tmp_path, capsys):
    _card(tmp_path, "pretko-2020-fracton", [
        "title: Fracton Phases of Matter",
        "authors: [Michael Pretko]",
        "year: 2020",
    ])
    out = tmp_path / "refs.bib"
    rc = bib_export.main(["pretko-2020", "--topic-dir", str(tmp_path), "-o", str(out)])
    assert rc == 0
    assert "@" in out.read_text(encoding="utf-8")

    rc = bib_export.main(["--all", "--topic-dir", str(tmp_path)])
    assert rc == 0
    assert "@misc{pretko2020," in capsys.readouterr().out

    rc = bib_export.main(["no-such-card", "--topic-dir", str(tmp_path)])
    assert rc == 1
