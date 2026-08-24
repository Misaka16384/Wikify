"""`format_math` had no tests at all, and it was corrupting real documents.

The bug: a line carrying two display formulas with prose between them —
``$$A$$ and $$B$$`` — came out as

    $$
    A$$ and $$B
    $$

because the pattern ran from the *first* opening delimiter to the *last*
closing one. Two independent expressions and the English word between them
fused into one block containing illegal delimiters. The familiar shape: not a
crash, not a gap, just something that reads like it was meant.

Most of what is below is not the fix — it is the behaviour that was already
correct, written down before touching anything, so that a real regression is
reported by a test rather than by a reader months later. That is the same
call the B2 note records: pin the current correct behaviour instead of
trusting a note nobody has re-run.
"""

import pytest

from magi.kb.format_math import clean_math_delimiters as clean


# --------------------------------------------------------------------------
# the bug
# --------------------------------------------------------------------------

def test_two_formulas_on_one_line_are_left_alone():
    """Any rewrite has to decide where the maths ends and the prose begins,
    and nothing here knows. Leaving it is the only safe answer."""
    assert clean("$$A$$ and $$B$$") == "$$A$$ and $$B$$"


def test_an_equation_between_two_display_blocks_is_left_alone():
    assert clean("$$x$$ = $$y$$") == "$$x$$ = $$y$$"


def test_prose_never_ends_up_inside_a_maths_block():
    """The damage stated as the thing it must never do, not as one output.

    Whatever the rules become, a line of the form `$$…$$ word $$…$$` must not
    come back with `word` sitting between a `$$` opener and its closer.
    """
    inside, depth = [], 0
    for line in clean("$$E_1$$ whereas $$E_2$$").splitlines():
        if line.strip() == "$$":
            depth ^= 1
        elif depth:
            inside.append(line)
    assert not any("whereas" in line for line in inside)


# --------------------------------------------------------------------------
# what already worked, pinned
# --------------------------------------------------------------------------

@pytest.mark.parametrize("src,want", [
    ("$$x$$", "$$\nx\n$$"),
    ("$$E = mc^2$$", "$$\nE = mc^2\n$$"),
    (r"$$\frac{a}{b}$$", "$$\n\\frac{a}{b}\n$$"),
    ("  $$x$$", "  $$\nx\n$$"),
    ("Result:\n$$x = 1$$\nDone.", "Result:\n$$\nx = 1\n$$\nDone."),
    ("$$a$$\n$$b$$", "$$\na\n$$\n$$\nb\n$$"),
])
def test_a_line_that_is_one_display_formula_becomes_three_lines(src, want):
    assert clean(src) == want


def test_an_already_expanded_block_is_stable():
    """Idempotence — this runs on files that have been through it before."""
    assert clean("$$\nx\n$$") == "$$\nx\n$$"


def test_inline_maths_is_not_touched():
    assert clean("inline $x$ here") == "inline $x$ here"


def test_a_display_formula_mid_sentence_is_not_expanded():
    """There is prose after it on the same line, so it is not a block."""
    assert clean("text $$x$$ more") == "text $$x$$ more"


def test_a_table_row_is_not_expanded():
    assert clean("| a | $$x$$ | b |") == "| a | $$x$$ | b |"


def test_a_fenced_code_block_is_left_verbatim():
    src = "```\n$$A$$ and $$B$$\n```"
    assert clean(src) == src


def test_consecutive_blocks_joined_by_an_operator_are_merged():
    """The aligned-environment merge, pinned so the guard above cannot
    silently disable it."""
    out = clean("$$\nx\n$$\n\n$$\n= y\n$$")
    assert "\\begin{aligned}" in out
    assert "&= y" in out
