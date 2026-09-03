"""Conjecture or finding, the bet command, and how `next` talks to people.

The protocol assumed a proposition is opened, bet on, then worked. A day of
real research ran the other way: the number came out first and the note was
opened about it, so every bet asked for was placed after the answer, and the
person was asked five times for predictions worth nothing. `found:` records
that a result came before its note and takes the question away.

The same day produced the other two habits tested here. `magi next` said
"post what you found, or move it" about a proposition opened that morning —
research runs on weeks. And it surfaced the bet, the disputed claim and the
line's phase one per turn, each an interruption; they are one conversation.
"""

import datetime as dt

import pytest

from magi import state
from magi.core import vocab
from magi.kb import thread_cmd, threads


NOW = dt.datetime(2026, 9, 3, 12, 0, tzinfo=dt.timezone.utc)


def at(days_ago=0):
    return (NOW - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    return tmp_path


def proposition(ws, slug, status=None, when=None, **extra):
    path = threads.create(ws / "threads" / f"{slug}.md", vocab.PROPOSITION,
                          slug.upper(), f"Why {slug}.", lines=["qec"], extra=extra or None)
    if status:
        threads.set_status(path, status, "moving", host="claude", at=when or at())
    return path


def run(ws, *argv):
    return thread_cmd.main(list(argv) + ["--topic-dir", str(ws)])


def note(ws, slug):
    return threads.read_note(ws / "threads" / f"{slug}.md")


# --------------------------------------------------------------------------
# found
# --------------------------------------------------------------------------

def test_a_finding_is_not_asked_for_a_bet(ws):
    proposition(ws, "p-found", status="testing", found="2026-09-01")
    proposition(ws, "p-guess", status="testing")
    asked = {item.slug for item in state.load(ws, now=NOW).queue if item.kind == "bet"}
    assert asked == {"p-guess"}


def test_strict_coaching_does_not_hold_a_session_for_a_findings_missing_bet(ws):
    proposition(ws, "p-found", status="testing", found="2026-09-01")
    proposition(ws, "p-guess", status="testing")
    owed = {item.slug for item in state.load(ws, now=NOW, coaching="strict").debt}
    assert "p-guess" in owed and "p-found" not in owed


def test_found_must_be_a_date(ws):
    path = proposition(ws, "p-x", found="yes")
    assert any("found must be a date" in message
               for _sev, message, _fix in threads.validate(threads.read_note(path)))
    assert not any("found" in message
                   for _sev, message, _fix in threads.validate(note(ws, "p-x"))
                   if "date" not in message)


def test_thread_new_found_records_today_by_default(ws, capsys):
    assert run(ws, "new", "p-f", "--kind", "proposition", "--title", "T",
               "--purpose", "Why.", "--found") == 0
    assert str(note(ws, "p-f").frontmatter["found"]) == dt.date.today().isoformat()
    assert "no prediction is asked for" in capsys.readouterr().out


def test_thread_new_found_takes_a_date_and_refuses_a_non_date(ws, capsys):
    assert run(ws, "new", "p-f", "--kind", "proposition", "--title", "T",
               "--purpose", "Why.", "--found", "2026-09-01") == 0
    assert str(note(ws, "p-f").frontmatter["found"]) == "2026-09-01"
    assert run(ws, "new", "p-g", "--kind", "proposition", "--title", "T",
               "--purpose", "Why.", "--found", "yesterday") == 1
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_found_is_for_propositions_only(ws, capsys):
    assert run(ws, "new", "qec", "--kind", "line", "--title", "T",
               "--purpose", "Why.", "--found") == 1
    assert "proposition" in capsys.readouterr().err


# --------------------------------------------------------------------------
# thread bet
# --------------------------------------------------------------------------

def test_thread_bet_sets_the_field_and_signs_the_post_human(ws):
    proposition(ws, "p-gap")
    assert run(ws, "bet", "p-gap", "refuted", "--text", "the drift looks real") == 0
    got = note(ws, "p-gap")
    assert got.frontmatter["bet"] == "refuted"
    last = got.posts[-1]
    assert last.host == vocab.HUMAN
    assert (last.field, last.value) == ("bet", "refuted")
    assert "drift" in last.text


def test_thread_bet_can_be_signed_otherwise_and_needs_no_text(ws):
    proposition(ws, "p-gap")
    assert run(ws, "bet", "p-gap", "unknown", "--host", "claude") == 0
    assert note(ws, "p-gap").posts[-1].host == "claude"


def test_thread_bet_refuses_a_question_and_a_missing_note(ws, capsys):
    threads.create(ws / "threads" / "q.md", vocab.QUESTION, "Q?", "Why.")
    assert run(ws, "bet", "q", "supported") == 1
    assert "proposition" in capsys.readouterr().err
    assert run(ws, "bet", "nope", "supported") == 1
    assert "no note" in capsys.readouterr().err


def test_a_bet_recorded_afterwards_clears_the_queue_item(ws):
    proposition(ws, "p-gap", status="testing")
    assert any(item.kind == "bet" for item in state.load(ws, now=NOW).queue)
    run(ws, "bet", "p-gap", "supported")
    assert not any(item.kind == "bet" for item in state.load(ws, now=NOW).queue)


# --------------------------------------------------------------------------
# how next talks
# --------------------------------------------------------------------------

def test_a_young_proposition_is_not_chased(ws):
    proposition(ws, "p-new", status="testing", when=at(days_ago=1), bet="unknown")
    st = state.load(ws, now=NOW)
    work = [a for a in state.candidates(st, now=NOW) if a.key == "work"][0]
    assert "oldest open work" in work.why
    assert "post what you found" not in work.why


def test_an_old_proposition_is(ws):
    proposition(ws, "p-old", status="testing", when=at(days_ago=15), bet="unknown")
    st = state.load(ws, now=NOW)
    work = [a for a in state.candidates(st, now=NOW) if a.key == "work"][0]
    assert "post what you found, or move it" in work.why


def test_the_patience_is_half_the_stall_threshold_and_no_new_knob(ws):
    assert state.nudge_days(state.load(ws, now=NOW, stall_days=14)) == 7
    assert state.nudge_days(state.load(ws, now=NOW, stall_days=21)) == 10
    assert state.nudge_days(state.load(ws, now=NOW, stall_days=1)) == 1


def test_everything_for_the_person_is_one_block(ws):
    """The ranking is unchanged; the shape is one heading over every item
    that needs the person, so an agent asks them together."""
    proposition(ws, "p-bet", status="testing")                     # needs a bet
    path = proposition(ws, "p-disp", status="supported")
    threads.set_status(path, "disputed", "VERDICT: refuted\n\nno", host=vocab.REVIEWER)
    st = state.load(ws, now=NOW)
    actions = state.candidates(st, now=NOW)
    text = state.render(st, actions)
    assert text.count("For the person") == 1
    block = text.split("For the person", 1)[1]
    human_lines = [a.why for a in actions if a.cost == "human"]
    assert all(why.split(" — ")[0] in block for why in human_lines)
    # Machine work that ranks after the block is introduced, not run into it.
    if any(a.cost != "human" for a in actions[actions.index(
            next(a for a in actions if a.cost == "human")):]):
        assert "Then:" in block


def test_with_nothing_for_the_person_there_is_no_block(ws):
    # A firm bet, not `unknown`: an open "don't know" is itself something the
    # block asks the person about, once, in case they now lean either way.
    proposition(ws, "p-x", status="testing", bet="supported")
    st = state.load(ws, now=NOW)
    assert "For the person" not in state.render(st, state.candidates(st, now=NOW))


# --------------------------------------------------------------------------
# a person's call, said at the keystroke
# --------------------------------------------------------------------------

def _disputed(ws, slug="p-gap"):
    path = proposition(ws, slug, status="supported")
    threads.set_status(path, "disputed", "VERDICT: refuted\n\nno", host=vocab.REVIEWER)
    return path


def test_moving_out_of_disputed_unsigned_says_how_to_sign_and_not_to_retry(ws, capsys):
    _disputed(ws)
    assert run(ws, "status", "p-gap", "testing", "--text", "rewording") == 0
    err = capsys.readouterr().err
    assert "person's call" in err
    assert "--host human" in err
    assert "Do not repeat this move" in err
    assert note(ws, "p-gap").status == "testing"          # a report, not a gate


def test_signed_human_it_says_nothing(ws, capsys):
    _disputed(ws)
    assert run(ws, "status", "p-gap", "testing", "--text", "they said keep it",
               "--host", "human") == 0
    assert "person's call" not in capsys.readouterr().err


def test_an_ordinary_move_says_nothing(ws, capsys):
    proposition(ws, "p-gap")
    run(ws, "status", "p-gap", "testing", "--text", "started")
    assert "person's call" not in capsys.readouterr().err


def test_the_debt_names_the_command_and_the_one_wrong_move(ws):
    _disputed(ws)
    run(ws, "status", "p-gap", "testing", "--text", "rewording")
    owed = [item for item in state.load(ws, now=NOW).debt if item.slug == "p-gap"]
    assert owed
    assert "magi thread post p-gap --host human" in owed[0].why
    assert "Do not repeat the move" in owed[0].why


def test_each_unsigned_repeat_is_one_more_debt_which_is_why_the_warning_exists(ws):
    path = _disputed(ws)
    run(ws, "status", "p-gap", "testing", "--text", "rewording")
    first = len([i for i in state.load(ws, now=NOW).debt if i.slug == "p-gap"])
    threads.set_status(path, "supported", "again", host="claude")
    threads.set_status(path, "disputed", "VERDICT: refuted\n\nno", host=vocab.REVIEWER)
    run(ws, "status", "p-gap", "testing", "--text", "rewording again")
    second = len([i for i in state.load(ws, now=NOW).debt if i.slug == "p-gap"])
    assert second == first + 1
