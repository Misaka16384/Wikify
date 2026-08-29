"""`magi decide` — the agent writing down what the person just said.

The human's only input surface is the conversation. They are not going to open
`decisions.md`, and a system that needs them to is a system whose record is
empty by the second week. So the agent transcribes, and these tests are about
the two properties that make the transcription worth having.

**Verbatim.** Summarising would make the record the agent's account of what the
person meant, which is exactly what a record is supposed to be independent of.

**Attributed.** The post is signed `human`, and that signature is what
`sync --close` looks for when a proposition leaves `disputed`. A prediction in
a file with nobody's name on it is indistinguishable from one the agent
invented, which is the whole value of having asked.
"""

import datetime as dt

import pytest

from magi import decide_cmd, state
from magi.core import vocab
from magi.kb import threads


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    return tmp_path


def proposition(ws, slug="p-gap"):
    return threads.create(ws / "threads" / f"{slug}.md", vocab.PROPOSITION,
                          "The gap survives", "Decide before the numerics.")


def run(ws, *argv):
    return decide_cmd.main(list(argv) + ["--topic-dir", str(ws)])


def decisions(ws):
    return (ws / "decisions.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# the record
# --------------------------------------------------------------------------

def test_the_words_are_kept_as_said(ws):
    proposition(ws)
    run(ws, "--about", "p-gap", "--text", "I think it holds in the bulk, not at the edge.")

    assert "I think it holds in the bulk, not at the edge." in decisions(ws)


def test_the_entry_says_what_it_was_about(ws):
    proposition(ws)
    run(ws, "--about", "p-gap", "--kind", "prediction", "--text", "It holds.")

    text = decisions(ws)
    assert "[[p-gap]]" in text
    assert "prediction" in text


def test_a_decision_about_nothing_in_particular_still_lands(ws):
    """Line pivots and project-level calls are decisions too, and they have no
    slug to hang on."""
    assert run(ws, "--text", "We stop chasing the disorder angle.") == 0
    assert "disorder angle" in decisions(ws)


def test_entries_accumulate_rather_than_replace(ws):
    run(ws, "--text", "first")
    run(ws, "--text", "second")

    text = decisions(ws)
    assert "first" in text and "second" in text


def test_an_empty_decision_is_refused(ws, capsys):
    assert run(ws, "--text", "   ") == 1
    assert "what they actually said" in capsys.readouterr().err


# --------------------------------------------------------------------------
# the note
# --------------------------------------------------------------------------

def test_a_prediction_lands_on_the_proposition_as_well(ws):
    path = proposition(ws)
    run(ws, "--about", "p-gap", "--bet", "supported", "--text", "It holds.")

    note = threads.read_note(path)
    assert note.frontmatter["bet"] == "supported"
    assert note.posts[-1].host == vocab.HUMAN


def test_the_note_keeps_everything_else_it_had(ws):
    path = threads.create(ws / "threads" / "p-gap.md", vocab.PROPOSITION,
                          "T", "Why.", lines=["qec"])
    run(ws, "--about", "p-gap", "--bet", "refuted", "--text", "I expect not.")

    note = threads.read_note(path)
    assert note.lines == ["qec"]
    assert note.frontmatter["purpose"] == "Why."
    assert threads.validate(note) == []


def test_a_bet_needs_something_to_bet_on(ws, capsys):
    assert run(ws, "--bet", "supported", "--text", "yes") == 1
    assert "--bet needs --about" in capsys.readouterr().err


def test_a_decision_about_a_note_that_is_not_there_says_so(ws, capsys):
    assert run(ws, "--about", "nope", "--text", "yes") == 1
    assert "either way" in capsys.readouterr().err, "the entry is still recorded"
    assert "yes" in decisions(ws)


# --------------------------------------------------------------------------
# what the record is for
# --------------------------------------------------------------------------

def test_a_transcribed_decision_settles_the_close_gate(ws):
    """The gate asks whether a human-only flip is on record. This is how an
    agent puts it on record without the person opening a file."""
    path = proposition(ws)
    threads.set_status(path, "testing", "started", host="claude")
    threads.set_status(path, "supported", "done", host="claude")
    threads.set_status(path, "disputed", "the reviewer disagrees", host="reviewer")

    run(ws, "--about", "p-gap", "--text", "I read both; the objection is about the edge case.")
    threads.set_status(path, "supported", "per the call above", host="claude")

    debt = [item.why for item in state.load(ws).debt]
    assert not any("person's call" in why for why in debt)


def test_the_prediction_is_recorded_before_the_answer(ws):
    """The only moment a prediction is honest is before the work. What is
    tested is that recording it costs one command at that moment."""
    path = proposition(ws)
    run(ws, "--about", "p-gap", "--bet", "unknown", "--text", "No idea, genuinely.")
    threads.set_status(path, "testing", "starting", host="claude")

    queue = [item.kind for item in state.load(ws).queue if item.slug == "p-gap"]
    assert "bet" not in queue, "'don't know' is an answer and stops the asking"


def test_the_date_is_the_days_date(ws):
    run(ws, "--text", "something")
    assert dt.date.today().isoformat() in decisions(ws)


# --------------------------------------------------------------------------
# transcription means transcription
#
# The command writes what a person said into two files that both have a
# structure of their own. Anything they say that happens to look like that
# structure is the interesting case: it is where "verbatim" and "parseable"
# pull against each other, and where getting it wrong forges a record rather
# than losing one.
# --------------------------------------------------------------------------

def test_a_quoted_status_line_does_not_become_a_transition(ws):
    """Signed `human`, which is the signature `sync --close` trusts as proof a
    person ruled on something. Inventing one from a sentence somebody typed is
    the worst thing in this file."""
    path = proposition(ws)
    threads.set_status(path, "testing", "started", host="claude")

    run(ws, "--about", "p-gap", "--text",
        "my worry is exactly this:\nstatus: testing -> refuted\nnothing more")

    note = threads.read_note(path)
    assert note.status == "testing", "nothing moved"
    assert [p.dst for p in note.posts if p.is_transition] == ["testing"]
    assert "status: testing -> refuted" in note.posts[-1].text, "and it is still there"


def test_a_quoted_post_heading_does_not_become_a_second_post(ws):
    path = proposition(ws)
    before = len(threads.read_note(path).posts)

    run(ws, "--about", "p-gap", "--text",
        "she said:\n### 2020-01-01T00:00:00Z · human\nit is fine")

    posts = threads.read_note(path).posts
    assert len(posts) == before + 1, "one thing was said, so one post"
    assert "2020-01-01" in posts[-1].text, "quoted, not back-dated"


def test_a_quoted_heading_does_not_become_a_second_decision(ws):
    """`MAP.md` lists the last few `## ` lines and `sync --close` asks whether
    a slug appears in one. A sentence that looks like an entry would otherwise
    be counted as one — dated whenever the sentence said."""
    proposition(ws)
    run(ws, "--text", "keep going\n## 2099-01-01 · [[p-gap]] we already settled this")

    # Counted the way everything downstream counts them: fence-aware, so a
    # `## ` quoted inside somebody's sentence is text and not an entry.
    assert state._recent_decisions(ws, 8) == ["## " + dt.date.today().isoformat()]
    assert "2099-01-01" in decisions(ws), "still said, still theirs"


def test_windows_line_endings_survive_intact(ws):
    proposition(ws)
    run(ws, "--text", "line one" + chr(13) + "\nline two")
    raw = (ws / "decisions.md").read_bytes()
    assert b"" + bytes([13, 13, 10]) not in raw


# --------------------------------------------------------------------------
# what it refuses, and what it keeps when it refuses
# --------------------------------------------------------------------------

def test_a_prediction_needs_something_that_can_be_wrong(ws, capsys):
    threads.create(ws / "threads" / "q-why.md", vocab.QUESTION,
                   "Why does it hold?", "Open question.")
    assert run(ws, "--about", "q-why", "--bet", "supported", "--text", "I say yes.") == 1

    assert "needs a proposition" in capsys.readouterr().err
    assert threads.read_note(ws / "threads" / "q-why.md").frontmatter.get("bet") is None
    assert not (ws / "decisions.md").is_file(), "nothing was written"


def test_a_slug_that_is_a_path_is_refused(ws, capsys):
    assert run(ws, "--about", "../elsewhere/notes", "--text", "hm") == 1
    assert "not a slug" in capsys.readouterr().err


def test_a_bet_that_did_not_take_is_reported_not_swallowed(ws, capsys, monkeypatch):
    """`decisions.md` claiming a person predicted something, with no `bet:` in
    the note, is a record of a decision that left no trace. Under strict
    coaching it is also a debt item that never clears no matter how often
    somebody answers it — so the failure is said out loud."""
    proposition(ws)

    def refuse(*args, **kwargs):
        raise ValueError("p-gap.md: bet did not take")

    monkeypatch.setattr(threads, "set_field", refuse)

    assert run(ws, "--about", "p-gap", "--bet", "supported", "--text", "it holds") == 1
    assert "did not take it" in capsys.readouterr().err
