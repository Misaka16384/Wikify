"""What MAGI already knows went well or badly.

Two properties carry this file.

**Wins are collected, and room is reserved for them.** A loop fed only failures
grows only prohibitions — every proposal it could make is a thing to stop
doing. Improvements to *how* the work is done can only come from sessions where
the work went well, so a bad week must not be able to crowd them out.

**A session is picked because something happened in it**, not because a model
found it interesting. Reading a transcript costs a call, and "nothing went
wrong here" is not worth paying to be told.
"""

from __future__ import annotations

import datetime as dt

import pytest

from magi import state
from magi.core import vocab
from magi.kb import threads
from magi.reflect import signals
from magi.reflect.transcripts import Session, Turn


NOW = dt.datetime(2026, 8, 29, 12, 0, tzinfo=dt.timezone.utc)


def at(minutes_ago=0):
    return (NOW - dt.timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    return tmp_path


def proposition(ws, slug, **extra):
    return threads.create(ws / "threads" / f"{slug}.md", vocab.PROPOSITION,
                          slug.upper(), f"Why {slug}.", lines=["qec"],
                          extra=extra or None)


def loaded(ws):
    return state.load(ws, now=NOW)


def session(host="claude", ident="s-1", started=None, ended=None):
    return Session(host=host, session_id=ident, cwd="", path="",
                   started=started or at(90), ended=ended or at(30),
                   turns=[Turn("user", at(60), "why did it stall?")])


# --------------------------------------------------------------------------
# losses
# --------------------------------------------------------------------------

def test_a_claim_that_was_solved_and_then_was_not(ws):
    """The strongest single signal in the system: somebody believed something,
    wrote it down, and was wrong."""
    path = proposition(ws, "p-gap")
    threads.set_status(path, "testing", "started", host="claude", at=at(120))
    threads.set_status(path, "supported", "converged", host="claude", at=at(90))
    threads.set_status(path, "refuted", "the boundary was wrong", host="claude", at=at(60))

    found = [s for s in signals.collect(loaded(ws)) if s.kind == signals.REVERSAL]
    assert [s.slug for s in found] == ["p-gap"]
    assert found[0].at == at(60)


def test_a_reviewers_rejection_is_its_own_signal(ws):
    path = proposition(ws, "p-gap")
    threads.set_status(path, "testing", "started", host="claude", at=at(120))
    threads.set_status(path, "supported", "converged", host="claude", at=at(90))
    threads.set_status(path, "disputed", "VERDICT: refuted", host=vocab.REVIEWER,
                       at=at(60))

    kinds = {s.kind for s in signals.collect(loaded(ws)) if s.slug == "p-gap"}
    assert signals.REJECTION in kinds
    assert signals.REVERSAL not in kinds, "the reviewer's move is not the library's"


def test_bookkeeping_debt_is_a_signal(ws):
    path = proposition(ws, "p-gap")
    text = path.read_text(encoding="utf-8").replace("status: open", "status: testing", 1)
    path.write_text(text, encoding="utf-8")

    found = [s for s in signals.collect(loaded(ws)) if s.kind == signals.DEBT]
    assert found and found[0].slug == "p-gap"


# --------------------------------------------------------------------------
# wins
# --------------------------------------------------------------------------

def test_a_claim_that_stood_first_time_is_a_win(ws):
    path = proposition(ws, "p-gap")
    threads.set_status(path, "testing", "started", host="claude", at=at(120))
    threads.set_status(path, "supported", "converged", host="claude", at=at(90))
    threads.append_post(path, "VERDICT: stands\n\nit follows", host=vocab.REVIEWER,
                        at=at(60))

    found = [s for s in signals.collect(loaded(ws)) if s.kind == signals.CLEAN]
    assert [s.slug for s in found] == ["p-gap"]


def test_a_claim_that_was_argued_over_is_not_a_win(ws):
    """A claim rejected, argued over and eventually accepted is a story about
    recovery, not about a method worth repeating."""
    path = proposition(ws, "p-gap")
    threads.set_status(path, "testing", "started", host="claude", at=at(180))
    threads.set_status(path, "supported", "converged", host="claude", at=at(150))
    threads.set_status(path, "disputed", "VERDICT: refuted", host=vocab.REVIEWER, at=at(120))
    threads.set_status(path, "testing", "fair point", host=vocab.HUMAN, at=at(90))
    threads.set_status(path, "supported", "fixed and re-run", host="claude", at=at(60))
    threads.append_post(path, "VERDICT: stands\n\nnow it does", host=vocab.REVIEWER,
                        at=at(30))

    assert not [s for s in signals.collect(loaded(ws)) if s.kind == signals.CLEAN]


# --------------------------------------------------------------------------
# sampling
# --------------------------------------------------------------------------

def test_a_session_with_nothing_attached_is_not_read(ws):
    """Reading a transcript costs a call."""
    picked = signals.sample([session()], [])
    assert picked == []


def test_a_session_is_picked_because_something_happened_in_it(ws):
    signal = signals.Signal(signals.REVERSAL, "p-gap", at(60), "wrong")
    picked = signals.sample([session()], [signal])

    assert len(picked) == 1
    assert picked[0].kind == "loss"
    assert picked[0].signals[0].slug == "p-gap"


def test_a_signal_from_another_day_belongs_to_another_session(ws):
    signal = signals.Signal(signals.REVERSAL, "p-gap", at(60 * 24 * 3), "old")
    assert signals.sample([session()], [signal]) == []


def test_a_bad_week_cannot_crowd_out_the_good_sessions(ws):
    """The reserved room for wins is the whole reason a proposal can ever be
    about method rather than another prohibition."""
    sessions, all_signals = [], []
    for index in range(9):
        ident = f"loss-{index}"
        moment = at(60 + index)
        sessions.append(session(ident=ident, started=moment, ended=moment))
        all_signals.append(signals.Signal(signals.REVERSAL, f"p-{index}", moment, "x"))
    for index in range(4):
        ident = f"win-{index}"
        moment = at(200 + index)
        sessions.append(session(ident=ident, started=moment, ended=moment))
        all_signals.append(signals.Signal(signals.CLEAN, f"q-{index}", moment, "y"))

    picked = signals.sample(sessions, all_signals)

    kinds = [item.kind for item in picked]
    assert kinds.count("loss") == signals.MAX_LOSS
    assert kinds.count("win") == signals.MAX_WIN
    assert len(picked) <= signals.MAX_SESSIONS


def test_the_newest_trouble_is_read_first(ws):
    """What is going wrong now is worth more than what went wrong a month ago
    and may already have been fixed."""
    old, new = at(600), at(30)
    sessions = [session(ident="old", started=old, ended=old),
                session(ident="new", started=new, ended=new)]
    all_signals = [signals.Signal(signals.REVERSAL, "p-old", old, "x"),
                   signals.Signal(signals.REVERSAL, "p-new", new, "y")]

    picked = signals.sample(sessions, all_signals, max_loss=1)
    assert [item.session.session_id for item in picked] == ["new"]


def test_debt_with_no_date_matches_no_session(ws):
    """It is still a signal; it just cannot be attributed, and the sampler does
    not pretend otherwise."""
    undated = signals.Signal(signals.DEBT, "p-gap", "", "nobody wrote it down")
    assert signals.sample([session()], [undated]) == []
