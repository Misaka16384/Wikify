"""Contracts for the LaTeX -> Markdown route.

Two of these encode bugs found by measuring the route against real arXiv
submissions: a .tgz was routed here by auto.py and then handed to pandoc as raw
gzip, and `find_main_tex` picked whichever file `os.walk` reached first, which
on a real bundle is as likely to be the supplement as the paper.
"""

import os
import shutil
import tarfile

import pytest

from magi.ingest import tex2md


# --------------------------------------------------------------------------
# Archive detection — one predicate, used everywhere
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "2608.16520.tar.gz",
    "2608.16520.tgz",
    "paper.tar",
    "paper.tar.bz2",
    "PAPER.TAR.GZ",
])
def test_tar_archives_are_recognised(name):
    assert tex2md._is_tar_archive(name)


@pytest.mark.parametrize("name", ["paper.tex", "paper.pdf", "notes.md", "figure.png"])
def test_non_archives_are_not(name):
    assert not tex2md._is_tar_archive(name)


def test_tgz_and_tar_gz_agree_on_the_slug():
    """The .tgz bug: the slug and the extract decision disagreed.

    `.tar.gz` was stripped whole for the slug, but `.tgz` fell through to
    os.path.splitext, which only removes the last component.
    """
    assert tex2md._archive_slug("2608.16520.tar.gz") == "2608.16520"
    assert tex2md._archive_slug("2608.16520.tgz") == "2608.16520"
    assert tex2md._archive_slug("2608.16520.tex") == "2608.16520"


def test_archive_slug_keeps_the_arxiv_id_intact():
    """Identity rides on the filename: tex2md recovers arxiv_id from it."""
    for name in ("2608.16520.tar.gz", "2608.16520.tgz"):
        assert tex2md.ARXIV_ID_RE.search(tex2md._archive_slug(name))


# --------------------------------------------------------------------------
# Main-file selection
# --------------------------------------------------------------------------

def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


DOC = r"\documentclass{revtex4-2}" "\n" r"\begin{document}" "\n%s\n" r"\end{document}"


def test_a_file_included_by_another_is_never_the_main_file(tmp_path):
    """The classic bundle: main.tex \\input's a section that also declares a class."""
    _write(tmp_path, "main.tex", DOC % r"\input{sections/intro}")
    _write(tmp_path, "sections/intro.tex", DOC % "Intro body.")

    assert os.path.basename(tex2md.find_main_tex(str(tmp_path))) == "main.tex"


def test_supplementary_material_does_not_win(tmp_path):
    """Alphabetically 'supplement' sorts before 'zpaper' — order must not decide."""
    _write(tmp_path, "supplement.tex", DOC % "Supplementary material.")
    _write(tmp_path, "zpaper.tex", DOC % "The actual paper.")

    assert os.path.basename(tex2md.find_main_tex(str(tmp_path))) == "zpaper.tex"


def test_standalone_figure_wrapper_does_not_win(tmp_path):
    """A TikZ figure shipped as its own compilable file is not the paper."""
    _write(tmp_path, "aaa_figure.tex",
           r"\documentclass{standalone}" "\n" r"\begin{document}\tikz\draw(0,0);\end{document}")
    _write(tmp_path, "ms.tex", DOC % "Real body.")

    assert os.path.basename(tex2md.find_main_tex(str(tmp_path))) == "ms.tex"


def test_the_slug_breaks_a_tie(tmp_path):
    """arXiv names the download after the id; the bundle often does too."""
    _write(tmp_path, "other.tex", DOC % "Something.")
    _write(tmp_path, "2608.16520.tex", DOC % "The paper.")

    picked = tex2md.find_main_tex(str(tmp_path), slug="2608.16520")
    assert os.path.basename(picked) == "2608.16520.tex"


def test_shallower_beats_nested_all_else_equal(tmp_path):
    """A bundle that ships an older copy in a subdirectory: same name, two depths."""
    _write(tmp_path, "paper.tex", DOC % "Top-level copy.")
    _write(tmp_path, "old/v1/paper.tex", DOC % "Superseded copy.")

    picked = tex2md.find_main_tex(str(tmp_path))
    assert os.path.relpath(picked, str(tmp_path)) == "paper.tex"


def test_a_strong_name_hint_outranks_depth(tmp_path):
    """Deliberate: 'ms.tex' one level down beats an unnamed file at the root.

    Depth is a weak signal (-5/level); being named like a manuscript is a
    stronger one. Pinned so the weighting cannot drift silently.
    """
    _write(tmp_path, "zz.tex", DOC % "Ambiguous.")
    _write(tmp_path, "src/ms.tex", DOC % "The manuscript.")

    assert os.path.basename(tex2md.find_main_tex(str(tmp_path))) == "ms.tex"


def test_falls_back_to_any_tex_when_no_documentclass(tmp_path):
    """Older submissions sometimes ship a fragment; do not return None."""
    _write(tmp_path, "body.tex", "Just a fragment, no preamble.\n")
    picked = tex2md.find_main_tex(str(tmp_path))
    assert picked is not None and picked.endswith("body.tex")


def test_returns_none_on_an_empty_tree(tmp_path):
    assert tex2md.find_main_tex(str(tmp_path)) is None


def test_selection_is_deterministic(tmp_path):
    """Two files of identical merit must not depend on filesystem walk order."""
    _write(tmp_path, "alpha.tex", DOC % "A.")
    _write(tmp_path, "beta.tex", DOC % "B.")

    picks = {tex2md.find_main_tex(str(tmp_path)) for _ in range(5)}
    assert len(picks) == 1


# --------------------------------------------------------------------------
# The two forms round-trip through a real archive
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# convert() reports instead of exiting
# --------------------------------------------------------------------------

def test_a_missing_input_is_a_result_not_an_exit(tmp_path):
    """The route used to sys.exit(1) here, which a caller cannot inspect."""
    result = tex2md.convert(str(tmp_path / "nope.tex"), str(tmp_path / "out"))
    assert result.success is False
    assert any("not found" in e for e in result.errors)


def test_an_archive_with_no_tex_reports_rather_than_exits(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("no tex here", encoding="utf-8")
    archive = tmp_path / "2608.16520.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(src, arcname="notes.txt")

    result = tex2md.convert(str(archive), str(tmp_path / "out"))
    assert result.success is False
    assert any("main .tex" in e for e in result.errors)


def test_main_still_exits_1_on_failure(tmp_path, capsys):
    """The CLI contract is unchanged: same stdout, same exit code."""
    code = tex2md.main([str(tmp_path / "nope.tex"), "-o", str(tmp_path / "out")])
    assert code == 1
    assert "not found" in capsys.readouterr().out


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_a_real_conversion_reports_unresolved_figures_as_a_finding(tmp_path):
    """Figure loss used to be a print swallowed by the calling subprocess."""
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "main.tex",
           r"\documentclass{article}" "\n"
           r"\title{A Small Paper}" "\n"
           r"\begin{document}\maketitle\section{Intro}" "\n"
           r"Energy is $E = mc^2$." "\n"
           r"\includegraphics{missingfig}" "\n"
           r"\end{document}")

    archive = tmp_path / "2608.16520.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(src / "main.tex", arcname="main.tex")

    result = tex2md.convert(str(archive), str(tmp_path / "out"))

    assert result.success is True
    assert os.path.isfile(result.markdown_path)
    codes = {f.code for f in result.findings}
    assert "figure-unresolved" in codes
    # Identity rides in on the filename and must reach the frontmatter.
    body = open(result.markdown_path, encoding="utf-8").read()
    assert "arxiv_id: '2608.16520'" in body


# --------------------------------------------------------------------------
# The two forms round-trip through a real archive
# --------------------------------------------------------------------------

@pytest.mark.parametrize("suffix", [".tar.gz", ".tgz"])
def test_both_archive_forms_extract_and_resolve(tmp_path, suffix):
    src = tmp_path / "src"
    src.mkdir()
    _write(src, "main.tex", DOC % r"\input{intro}")
    _write(src, "intro.tex", DOC % "Intro.")

    archive = tmp_path / f"2608.16520{suffix}"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(src / "main.tex", arcname="main.tex")
        tar.add(src / "intro.tex", arcname="intro.tex")

    assert tex2md._is_tar_archive(str(archive))
    assert tex2md._archive_slug(archive.name) == "2608.16520"

    extract = tmp_path / f"out{suffix.replace('.', '_')}"
    extract.mkdir()
    with tarfile.open(archive, "r:*") as tar:
        tar.extractall(path=extract)

    assert os.path.basename(tex2md.find_main_tex(str(extract), slug="2608.16520")) == "main.tex"


# --------------------------------------------------------------------------
# the title, and where `source:` points afterwards
# --------------------------------------------------------------------------

@pytest.mark.parametrize("tex,want", [
    (r"\title{Simple Title}", "Simple Title"),
    (r"\title[Short]{The Long Real Title}", "The Long Real Title"),
    (r"\title{A \textbf{Bold} Ending}", "A Bold Ending"),
    (r"\title {Spaced Brace}", "Spaced Brace"),
    (r"\title{Two Lines \\ Of Title}", "Two Lines Of Title"),
    ("no title anywhere", None),
])
def test_the_title_survives_the_shapes_latex_actually_uses(tex, want):
    """Reported from a real ingest: a paper arrived as `title: '2605.12601'`.

    The old pattern required `{` immediately after `\title`, so the very
    common `\title[Short]{Long}` matched nothing at all and the paper was
    filed under its arXiv id. `[^}]+` also stopped at the first nested brace,
    so any markup inside a title truncated it — which is the worse failure,
    because half a title still reads like a title.
    """
    from magi.ingest.tex2md import extract_title

    assert extract_title(tex) == want
