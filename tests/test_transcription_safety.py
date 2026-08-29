"""Transcription must not be able to damage the file it is transcribed into.

`magi decide` and every post write down what a person actually said, word for
word. That is the whole value: a record nobody edited. It is also the whole
risk, because what a person says can contain this format's own structure —
a heading, a status line, a code fence. Two properties hold it together:

1. The words are unchanged.
2. Nothing in them is read as structure.

The failure this file is built around is the second one failing *quietly*. A
body whose fence is never closed reads as entirely code, so the "is anything
at risk here" test finds nothing at risk — and the one body that most needed
fencing is the one that does not get it. From then on the fence belongs to the
whole document: every later entry renders inside it, and the parser that
counts entries stops counting.
"""

from magi.core import md_blocks
from magi.decide_cmd import append_decision, quote_if_headings
from magi.kb import threads


# --------------------------------------------------------------------------
# unclosed fences
# --------------------------------------------------------------------------

def test_an_unclosed_fence_is_recognised():
    assert md_blocks.has_unclosed_fence("intro\n```py\nx = 1")
    assert md_blocks.has_unclosed_fence("~~~\nnothing closes this")
    assert not md_blocks.has_unclosed_fence("intro\n```py\nx = 1\n```\nafter")
    assert not md_blocks.has_unclosed_fence("no fences at all")
    assert not md_blocks.has_unclosed_fence("")


def test_a_longer_fence_does_not_close_a_shorter_one():
    """```` closes ```; ``` does not close ````."""
    assert not md_blocks.has_unclosed_fence("````\nbody\n`````")
    assert md_blocks.has_unclosed_fence("`````\nbody\n```")


def test_a_decision_with_an_unclosed_fence_is_quoted_whole():
    said = "we tried this\n```python\nresult = solve()"
    out = quote_if_headings(said)
    assert out != said, "an unclosed fence must not reach the document raw"
    assert said in out
    assert not md_blocks.has_unclosed_fence(out)


def test_a_post_with_an_unclosed_fence_is_quoted_whole():
    said = "the log said\n```\nTraceback (most recent call last):"
    out = threads.quote_if_structural(said)
    assert out != said
    assert said in out
    assert not md_blocks.has_unclosed_fence(out)


def test_the_wrapping_fence_outgrows_the_backticks_inside_it():
    said = "````\nstill open"
    out = threads.quote_if_structural(said)
    assert out.startswith("`````text")
    assert not md_blocks.has_unclosed_fence(out)


def test_a_later_decision_still_lands_as_its_own_entry(tmp_path):
    """The property the fencing exists for: entry two is an entry, not code."""
    append_decision(tmp_path, "we tried\n```python\nresult = solve()")
    append_decision(tmp_path, "and then it worked")

    text = (tmp_path / "decisions.md").read_text(encoding="utf-8")
    headings = [label for label, line in
                md_blocks.classify_lines(md_blocks.normalize_newlines(text))
                if label != md_blocks.CODE and line.startswith("## ")]
    assert len(headings) == 2, "the second entry was swallowed by the first"


# --------------------------------------------------------------------------
# what a reader can read, a writer can write
# --------------------------------------------------------------------------

def _note(tmp_path):
    path = tmp_path / "threads" / "p-x.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nkind: proposition\nstatus: testing\n---\n\n"
                    "# p-x\n\n## Discussion\n", encoding="utf-8")
    return path


def _make_it_cp1252(path):
    """What Notepad still writes by default, and what `_read` tolerates."""
    text = path.read_text(encoding="utf-8")
    path.write_bytes((text + "\nnaïve café\n").encode("cp1252"))
    return path


def test_a_note_a_reader_tolerates_is_a_note_a_writer_can_post_to(tmp_path):
    """These were two different standards for the same file: the readers
    decoded with replacements, the writers refused. So a note you could see in
    `magi next` raised UnicodeDecodeError the moment anybody posted to it, and
    the crash landed in the close gate rather than in the editor at fault."""
    path = _make_it_cp1252(_note(tmp_path))

    assert threads.read_note(path).frontmatter["status"] == "testing"
    threads.append_post(path, "still holds", host="claude")

    assert "still holds" in threads.read_note(path).body


def test_a_status_flip_survives_the_same_file(tmp_path):
    path = _make_it_cp1252(_note(tmp_path))
    threads.set_status(path, "supported", text="the sweep agrees", host="claude")
    assert threads.read_note(path).frontmatter["status"] == "supported"


def test_a_field_write_survives_the_same_file(tmp_path):
    path = _make_it_cp1252(_note(tmp_path))
    threads.set_field(path, "bet", "0.7", host="claude")
    assert str(threads.read_note(path).frontmatter["bet"]) == "0.7"
