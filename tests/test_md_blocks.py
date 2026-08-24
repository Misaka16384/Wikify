"""The shared answer to "may this rewrite touch that span?".

Two callers already re-derived this and each missed what the other had: the
OCR route's cleaner protected table rows but not fenced code, and the KB
formatter protected fenced code but not table rows. Both were caught
corrupting real documents. The tests here are the contract they now share.
"""

from magi.core.md_blocks import (CODE, TABLE, TEXT, classify_lines, map_prose,
                                 normalize_newlines)

SHOUT = str.upper


def _kinds(text):
    return [k for k, _ in classify_lines(text)]


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def test_a_fenced_block_is_protected_including_its_fences():
    assert _kinds("a\n```\nx\n```\nb") == [TEXT, CODE, CODE, CODE, TEXT]


def test_a_fence_with_an_info_string_still_opens_and_a_bare_fence_closes():
    assert _kinds("```python\nx = 1\n```") == [CODE, CODE, CODE]


def test_a_table_row_is_protected():
    assert _kinds("intro\n| a | b |\n|---|---|") == [TEXT, TABLE, TABLE]


def test_an_indented_table_row_is_still_a_row():
    assert _kinds("   | a | b |") == [TABLE]


def test_a_pipe_inside_a_fence_is_code_not_a_table():
    """Order matters: the fence wins, so a table drawn in a code sample is
    never handed to a table rule."""
    assert _kinds("```\n| a | b |\n```") == [CODE, CODE, CODE]


def test_a_tilde_fence_is_not_closed_by_a_backtick_fence():
    assert _kinds("~~~\nx\n```\ny\n~~~\nz") == [CODE] * 5 + [TEXT]


def test_a_longer_fence_is_needed_to_close_a_longer_one():
    assert _kinds("````\n```\nx\n````\ndone") == [CODE] * 4 + [TEXT]


def test_an_unclosed_fence_protects_the_rest_of_the_document():
    """A document with an unclosed fence is already broken; rewriting the
    inside of it cannot make it better."""
    assert _kinds("a\n```\nx\ny") == [TEXT, CODE, CODE, CODE]


# --------------------------------------------------------------------------
# mapping
# --------------------------------------------------------------------------

def test_prose_is_transformed_and_protected_spans_are_not():
    out = map_prose("hello\n```\nkeep me\n```\n| a |\nbye", SHOUT)
    assert out.splitlines() == ["HELLO", "```", "keep me", "```", "| a |", "BYE"]


def test_a_run_of_prose_arrives_as_one_string():
    """A pattern that spans a line break has to keep working."""
    seen = []
    map_prose("one\ntwo\n| row |\nthree", lambda b: seen.append(b) or b)
    assert seen == ["one\ntwo", "three"]


def test_the_callback_may_return_more_lines_than_it_got():
    out = map_prose("x\n| row |", lambda b: b + "\nextra")
    assert out.splitlines() == ["x", "extra", "| row |"]


def test_tables_can_be_left_unprotected_when_a_caller_wants_that():
    out = map_prose("| a |", SHOUT, protect=(CODE,))
    assert out == "| A |"


def test_a_document_with_nothing_to_protect_is_one_call():
    seen = []
    map_prose("a\nb\nc", lambda b: seen.append(b) or b)
    assert seen == ["a\nb\nc"]


def test_an_empty_document_survives():
    assert map_prose("", SHOUT) == ""


# --------------------------------------------------------------------------
# newlines
# --------------------------------------------------------------------------

def test_crlf_and_lone_cr_both_become_lf():
    assert normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"


def test_a_crlf_table_row_is_still_classified_as_a_row():
    """Without normalisation the row arrives as "| a |\\r" — still a row, but
    every downstream pattern anchored on \\n is now one character off."""
    assert _kinds(normalize_newlines("intro\r\n| a |\r\n")) == [TEXT, TABLE, TEXT]
