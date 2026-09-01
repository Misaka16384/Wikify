"""Figures that the tarball had and the conversion lost.

An arXiv e-print package is lossless — the image files are right there next to
the ``.tex``. So a figure arriving missing is never the route's nature, it is
something in the conversion, and the recorded note that blamed the route was
wrong about it.

The mechanism, measured with pandoc 3.9 on arXiv 2401.00506:

    \\includegraphics[width=0.5\\textwidth]{sbs}       ->  ![](sbs.jpg)
    \\subfigure[]{\\includegraphics[...]{disp}}        ->  a <figure> holding
                                                          only its caption

Pandoc's LaTeX reader drops a macro it does not know **together with its
arguments**. `\\subfigure` (package ``subfigure``) and `\\subfloat` (package
``subfig``) are the two standard ways to build a multi-panel figure, which is
most figures in a physics paper — and the caption survives, so the output reads
complete. That paper referenced six figures and produced none.
"""

import re

import pytest

from magi.ingest.tex2md import unwrap_figure_macros

BS = chr(92)
INC = BS + "includegraphics"


def _g(target, opts="[width=0.5" + BS + "textwidth]"):
    return INC + opts + "{" + target + "}"


# --------------------------------------------------------------------------
# What gets unwrapped
# --------------------------------------------------------------------------

@pytest.mark.parametrize("macro", ["subfigure", "subfloat", "subcaptionbox",
                                   "resizebox", "raisebox", "somebodyscustommacro"])
def test_a_macro_wrapping_a_figure_is_unwrapped(macro):
    """Enumerating package names would only hold until the next package. The
    rule is structural: whatever the wrapper is called, the graphic inside it
    has to reach pandoc."""
    tex = BS + macro + "[]{" + _g("disp") + "}"
    out, n = unwrap_figure_macros(tex)

    assert n == 1
    assert out == _g("disp")


def test_a_doubly_wrapped_panel_comes_all_the_way_out():
    tex = BS + "subfigure[]{" + BS + "resizebox{2cm}{!}{" + _g("plot1") + "}}"
    out, n = unwrap_figure_macros(tex)

    assert out.strip() == _g("plot1")
    assert n == 2


def test_the_real_shape_from_the_paper():
    """Verbatim from `arxiv_semid.tex`, both panels of one figure."""
    tex = (BS + "subfigure[]{" + INC + "[width = 0.5 " + BS + "textwidth]{sbs}}" + "\n"
           + BS + "subfigure[]{" + INC + "[width = 0.25 " + BS + "textwidth]{disp}}")
    out, n = unwrap_figure_macros(tex)

    assert n == 2
    assert out.count(INC) == 2
    assert BS + "subfigure" not in out


def test_all_six_of_the_papers_figures_survive():
    tex = "\n".join(
        BS + "subfigure[]{" + _g(name) + "}"
        for name in ("sbs", "disp", "plot1", "plot2", "3dplot", "jjc"))
    out, n = unwrap_figure_macros(tex)

    assert n == 6
    assert len(re.findall(re.escape(INC), out)) == 6


# --------------------------------------------------------------------------
# What must not be touched
# --------------------------------------------------------------------------

def test_a_caption_keeps_its_wrapper():
    """Pandoc understands `\\caption`. Unwrapping would turn a caption into
    body text, which is a loss, not a fix."""
    tex = BS + "caption{See " + _g("inset") + " here}"
    out, n = unwrap_figure_macros(tex)

    assert n == 0
    assert out == tex


def test_a_link_around_a_figure_keeps_its_wrapper():
    tex = BS + "href{https://example.org}{" + _g("logo") + "}"
    out, n = unwrap_figure_macros(tex)

    assert n == 0


def test_a_macro_with_no_figure_in_it_is_left_alone():
    tex = BS + "textbf{ordinary bold text} and " + BS + "emph{emphasis}"
    assert unwrap_figure_macros(tex) == (tex, 0)


def test_the_figure_environment_is_not_a_macro_call():
    """`\\begin{figure}` matches the macro pattern but its braced argument is
    the environment name, so the environment must survive intact — it is what
    carries the caption and the float."""
    tex = (BS + "begin{figure}\n" + BS + "subfigure[]{" + _g("a") + "}\n"
           + BS + "caption{A caption}\n" + BS + "end{figure}")
    out, n = unwrap_figure_macros(tex)

    assert n == 1
    assert BS + "begin{figure}" in out and BS + "end{figure}" in out
    assert BS + "caption{A caption}" in out


def test_unbalanced_braces_leave_the_source_exactly_as_it_was():
    """Malformed TeX is common in real submissions. Guessing at a repair is how
    a converter starts inventing; the honest move is to change nothing and let
    pandoc report."""
    tex = BS + "subfigure[]{" + _g("disp")      # never closed
    out, n = unwrap_figure_macros(tex)

    assert n == 0
    assert out == tex


def test_text_with_no_macros_at_all_is_unchanged():
    tex = "Just a paragraph about $x^{-4}$ and nothing else.\n"
    assert unwrap_figure_macros(tex) == (tex, 0)


# --------------------------------------------------------------------------
# Through pandoc itself
# --------------------------------------------------------------------------

pandoc = pytest.importorskip("shutil").which("pandoc")


@pytest.mark.skipif(not pandoc, reason="pandoc is not installed")
def test_pandoc_really_does_drop_the_wrapped_figure(tmp_path):
    """The premise, checked rather than assumed. If a future pandoc learns
    `\\subfigure`, this is what says the workaround can go."""
    import subprocess

    (tmp_path / "sbs.png").write_bytes(
        bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000"
                      "001f15c4890000000a49444154789c6300010000050001"
                      "0d0a2db40000000049454e44ae426082"))
    doc = "\n".join([
        BS + "documentclass{article}", BS + "usepackage{graphicx}",
        BS + "begin{document}",
        BS + "begin{figure}", BS + "subfigure[]{" + INC + "{sbs}}",
        BS + "caption{c}", BS + "end{figure}",
        BS + "end{document}", ""])
    src = tmp_path / "w.tex"
    src.write_text(doc, encoding="utf-8")

    wrapped = subprocess.run([pandoc, "-f", "latex", "-t", "markdown", "w.tex"],
                             capture_output=True, text=True, cwd=tmp_path).stdout
    assert "sbs" not in wrapped              # the premise: the figure is gone
    assert "c" in wrapped                    # and the caption is not

    src.write_text(unwrap_figure_macros(doc)[0], encoding="utf-8")
    unwrapped = subprocess.run([pandoc, "-f", "latex", "-t", "markdown", "w.tex"],
                               capture_output=True, text=True, cwd=tmp_path).stdout
    assert "sbs" in unwrapped


@pytest.mark.skipif(not pandoc, reason="pandoc is not installed")
def test_a_latex_table_arrives_as_a_pipe_table(tmp_path):
    """Pandoc's default Markdown writer emits *simple* tables — space-aligned
    columns under dashes. Nothing in the library renders those: Obsidian and
    every GFM reader want pipes, so a converted table looked like a mangled
    paragraph *and* `tables-dropped` reported it missing, because it could not
    see one either. One false alarm and one real loss, from one default.
    """
    import subprocess

    from magi.ingest import gates

    doc = "\n".join([
        BS + "documentclass{article}", BS + "begin{document}",
        BS + "begin{table}", BS + "begin{tabular}{lrr}",
        "Category & Kept & Excluded " + BS + BS,
        "Correspondence & 412 & 38 " + BS + BS,
        BS + "end{tabular}", BS + "end{table}",
        BS + "end{document}", ""])
    (tmp_path / "t.tex").write_text(doc, encoding="utf-8")

    def convert(fmt):
        return subprocess.run([pandoc, "-f", "latex", "-t", fmt, "t.tex"],
                              capture_output=True, text=True, cwd=tmp_path).stdout

    plain = convert("markdown")
    assert gates.check_tables_survived(plain, 1, 2) is not None      # the bug

    piped = convert("markdown-simple_tables-multiline_tables-grid_tables+pipe_tables")
    assert "| Correspondence" in piped.replace("  ", " ")
    assert gates.check_tables_survived(piped, 1, 2) is None


@pytest.mark.skipif(not pandoc, reason="pandoc is not installed")
def test_the_converter_asks_pandoc_for_pipe_tables():
    """Guards the flag at its source, so a later edit cannot quietly restore
    the writer default."""
    import inspect

    from magi.ingest import tex2md

    src = inspect.getsource(tex2md.convert)
    assert "+pipe_tables" in src
    assert '"-t", "markdown"]' not in src


@pytest.mark.parametrize("call,note", [
    (BS + "resizebox{2cm}{!}{" + INC + "{x}}", "figure is the third argument"),
    (BS + "scalebox{0.5}{" + INC + "{x}}", "second"),
    (BS + "makebox[2cm][c]{" + INC + "{x}}", "after two optional arguments"),
    (BS + "raisebox{-1ex}{" + INC + "{x}}", "second"),
])
def test_the_figure_is_not_always_in_the_first_argument(call, note):
    r"""Measured with pandoc 3.9: \resizebox, \scalebox, \makebox and
    \raisebox all drop the graphic. \parbox is the one that keeps it, which is
    why guessing from the macro's shape would have been wrong — the rule reads
    the arguments and takes whichever actually holds the figure."""
    out, n = unwrap_figure_macros(call)
    assert n == 1, note
    assert out == INC + "{x}"


def test_a_group_after_the_macro_is_not_swallowed():
    """Consuming argument groups must stop at the one holding the figure, or a
    wrapper would eat the text that follows it."""
    tex = BS + "scalebox{0.5}{" + INC + "{x}} and then {a braced aside}"
    out, n = unwrap_figure_macros(tex)

    assert n == 1
    assert out == INC + "{x} and then {a braced aside}"


# --------------------------------------------------------------------------
# The dialect that predates the packages pandoc assumes
# --------------------------------------------------------------------------

from magi.ingest.tex2md import modernise_tex   # noqa: E402


def test_a_true_prefixed_dimension_is_normalised():
    r"""TeX's `true` prefix breaks pandoc two different ways, and which one
    depends on a space: `\vskip 0.3truein` is a hard parse error that loses the
    entire document, while `\vskip 0.3 truein` parses and puts the word
    "truein" in the body as text. One loud, one silent, one fix."""
    out, counts = modernise_tex(BS + "vskip 0.3truein and " + BS + "hskip 1 truecm")

    assert counts["true_dimens"] == 2
    assert "truein" not in out and "truecm" not in out
    assert "0.3in" in out and "1cm" in out


@pytest.mark.parametrize("unit", ["in", "cm", "mm", "pt", "bp", "pc"])
def test_every_true_unit_is_covered(unit):
    out, counts = modernise_tex(BS + "vskip 2true" + unit)
    assert counts["true_dimens"] == 1
    assert out == BS + "vskip 2" + unit


def test_a_word_starting_with_true_is_not_a_dimension():
    """`truetype` and a sentence about something being true are not units. The
    rule requires a digit in front."""
    tex = "This is true in general, and truetype fonts are fine."
    assert modernise_tex(tex)[0] == tex


def test_the_pre_graphicx_figure_macros_become_includegraphics():
    r"""`\epsfbox` and `\epsfig` are how a paper referenced a figure before
    graphicx won. Pandoc knows neither, so on a 2000-era paper all thirteen
    figures were invisible to it even once the document parsed."""
    out, counts = modernise_tex(
        BS + "epsfbox{sfigs/gs.eps} and "
        + BS + "epsfig{file=sfigs/quench.eps,width=3in}")

    assert counts["epsfbox"] == 1 and counts["epsfig"] == 1
    assert out.count(INC) == 2
    assert "{sfigs/gs.eps}" in out and "{sfigs/quench.eps}" in out


def test_the_file_key_is_found_wherever_it_sits():
    out, _ = modernise_tex(BS + "epsfig{width=3in,file=a.eps,height=2in}")
    assert out == INC + "{a.eps}"


def test_an_epsfig_with_no_file_key_is_left_exactly_as_it_was():
    """Rewriting something we did not understand is how a converter starts
    inventing."""
    tex = BS + "epsfig{width=3in}"
    assert modernise_tex(tex)[0] == tex


def test_a_modern_document_is_untouched():
    tex = (BS + "documentclass{article}\n" + BS + "usepackage{graphicx}\n"
           + INC + "[width=0.5" + BS + "textwidth]{fig1}\n")
    out, counts = modernise_tex(tex)

    assert out == tex
    assert not any(counts.values())


# --------------------------------------------------------------------------
# A macro being defined is not a macro wrapping a figure
# --------------------------------------------------------------------------

def test_a_newcommand_definition_is_not_unwrapped():
    r"""Found on cond-mat/0001002, and introduced by the unwrapper itself.

        \newcommand\frm[1]{\includegraphics{#1}}

    matches the call pattern exactly, and unwrapping it produced
    `\newcommand\includegraphics{#1}` — redefining the one command everything
    downstream depends on. Pandoc then failed two hundred lines away, which is
    what makes this worth a test rather than a comment.
    """
    tex = BS + "newcommand" + BS + "frm[1]{" + INC + "{#1}}"
    out, n = unwrap_figure_macros(tex)

    assert n == 0
    assert out == tex


@pytest.mark.parametrize("definer", ["newcommand", "renewcommand",
                                     "providecommand", "def",
                                     "DeclareRobustCommand"])
def test_every_definition_form_is_protected(definer):
    tex = BS + definer + BS + "fig{" + INC + "{x}}"
    assert unwrap_figure_macros(tex) == (tex, 0)


def test_a_starred_definition_is_protected_too():
    tex = BS + "newcommand*" + BS + "fig{" + INC + "{x}}"
    assert unwrap_figure_macros(tex) == (tex, 0)


def test_a_wrapper_inside_a_definition_body_is_still_unwrapped():
    r"""The guard protects the macro *being defined*, not everything in its
    body. `\centerline{\includegraphics{#1}}` inside a definition is a genuine
    wrapper and pandoc drops it like any other."""
    tex = (BS + "newcommand" + BS + "figu[1]{" + BS + "begin{figure}"
           + BS + "centerline{" + INC + "{#1}}" + BS + "end{figure}}")
    out, n = unwrap_figure_macros(tex)

    assert n == 1
    assert BS + "newcommand" + BS + "figu[1]{" in out
    assert BS + "centerline" not in out
    assert INC + "{#1}" in out


def test_a_call_that_merely_follows_a_definition_is_still_unwrapped():
    """The guard looks at what is immediately before the macro name, not
    anywhere earlier in the file."""
    tex = (BS + "newcommand" + BS + "x{y}\n\n"
           + BS + "subfigure[]{" + INC + "{a}}")
    out, n = unwrap_figure_macros(tex)

    assert n == 1
    assert BS + "subfigure" not in out
