"""One pass of the slow loop: sessions in, pattern pages out.

No test here runs a real CLI. What is being checked is the contract around the
call, which is the part that can be wrong in a way nobody notices:

**The model may only name sessions it was given.** The ≥2-independent-sessions
gate is the loop's only defence against turning one bad afternoon into a
permanent rule. A model that could invent a second sighting would walk straight
through it, and nothing downstream would ever know.

**A pass that could not run writes nothing** — same rule as the reviewer, for
the same reason: a pattern page is evidence, and evidence nobody gathered is
worse than no evidence.

**One call per pass**, because a pattern is a thing that repeats and a reader
shown one session at a time cannot see repetition. It is also one call against
the budget instead of eight.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from magi.core import ledger, vocab
from magi.kb import threads
from magi.reflect import cmd, patterns
from magi.reflect.transcripts import Session, Turn


TODAY = dt.date(2026, 8, 29)
NOW = dt.datetime(2026, 8, 29, 12, 0, tzinfo=dt.timezone.utc)


def at(minutes_ago=0):
    return (NOW - dt.timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture(autouse=True)
def installed(monkeypatch):
    """What is on PATH is a fact about this machine, not about the code."""
    from magi import review

    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["claude", "codex"])


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "topic"
    (root / "threads").mkdir(parents=True)
    (root / "output").mkdir(parents=True)
    (root / "config.yaml").write_text("research:\n  weekly_calls: 10\n", encoding="utf-8")

    # One reversal inside each session's window. Two separate things that
    # happened, which is what two independent sightings means — the sampler
    # gives an event to the session it happened in, not to every session
    # whose window it lands near.
    first = threads.create(root / "threads" / "p-gap.md", vocab.PROPOSITION,
                           "The gap survives", "Decide before the numerics.")
    threads.set_status(first, "testing", "started", host="claude", at=at(230))
    threads.set_status(first, "supported", "converged", host="claude", at=at(200))
    threads.set_status(first, "refuted", "the boundary was wrong", host="claude",
                       at=at(170))

    second = threads.create(root / "threads" / "p-edge.md", vocab.PROPOSITION,
                            "The edge mode is protected", "Decide before the sweep.")
    threads.set_status(second, "testing", "started", host="codex", at=at(90))
    threads.set_status(second, "supported", "converged", host="codex", at=at(70))
    threads.set_status(second, "refuted", "same boundary again", host="codex", at=at(50))
    return root


@pytest.fixture
def sessions(monkeypatch):
    """Two sessions covering the reversal above, injected rather than on disk.

    The adapters have their own tests; what this file is about is what happens
    to what they return.
    """
    made = [
        Session(host="claude", session_id="s-1", cwd="", path="",
                started=at(240), ended=at(160),
                turns=[Turn("user", at(200), "why did the sweep stall?"),
                       Turn("assistant", at(180),
                            "the boundary condition was wrong")]),
        Session(host="codex", session_id="s-2", cwd="", path="",
                started=at(100), ended=at(40),
                turns=[Turn("user", at(60), "same thing again")]),
    ]

    class FakeSweep:
        sessions = made
        unreadable = {}

    monkeypatch.setattr(cmd.transcripts, "sweep", lambda *a, **k: FakeSweep())
    return made


def answering(text):
    def reply(*args, **kwargs):
        return text
    return reply


def one_pattern(sessions_named=("claude/s-1", "codex/s-2")):
    return json.dumps({
        "slug": "sweeps-start-before-the-boundary-is-checked",
        "title": "Sweeps start before the boundary condition is checked",
        "sessions": list(sessions_named),
        "body": "## What happened\n\nIt stalled.\n\n## Quotes\n\n> the boundary "
                "condition was wrong",
    }, ensure_ascii=False)


# --------------------------------------------------------------------------
# what one pass does
# --------------------------------------------------------------------------

def test_a_pass_writes_a_page_per_pattern(ws, sessions, monkeypatch):
    monkeypatch.setattr(cmd, "ask", answering(one_pattern()))

    report = cmd.run(ws, host="codex", now=TODAY)

    assert report.written == ["sweeps-start-before-the-boundary-is-checked"]
    page = patterns.read(patterns.path_for(ws, report.written[0]))
    assert page.independent == 2, "one event each, in two sessions"
    assert page.hosts == ["claude", "codex"]


def test_the_pass_costs_one_call(ws, sessions, monkeypatch):
    calls = []
    monkeypatch.setattr(cmd, "ask", lambda *a, **k: calls.append(1) or one_pattern())

    cmd.run(ws, host="codex", now=TODAY)

    assert len(calls) == 1
    assert [e["kind"] for e in ledger.entries(ws)] == ["reflect"]


def test_a_model_cannot_invent_a_second_sighting(ws, sessions, monkeypatch):
    """This gate is the loop's only defence against one bad afternoon becoming
    a permanent rule."""
    monkeypatch.setattr(cmd, "ask", answering(
        one_pattern(("claude/s-1", "gemini/never-happened"))))

    cmd.run(ws, host="codex", now=TODAY)

    page = patterns.read(patterns.path_for(
        ws, "sweeps-start-before-the-boundary-is-checked"))
    assert page.sessions == ["claude/s-1"]


def test_a_pattern_attributed_to_nothing_is_dropped(ws, sessions, monkeypatch):
    monkeypatch.setattr(cmd, "ask", answering(one_pattern(("gemini/nope",))))

    report = cmd.run(ws, host="codex", now=TODAY)

    assert report.written == []
    assert report.skipped and "names no session" in report.skipped[0][1]


def test_one_unparseable_line_does_not_lose_the_others(ws, sessions, monkeypatch):
    monkeypatch.setattr(cmd, "ask", answering(
        "here is what I found:\n{oops not json\n" + one_pattern()))

    report = cmd.run(ws, host="codex", now=TODAY)
    assert report.written == ["sweeps-start-before-the-boundary-is-checked"]


def test_a_slug_that_is_a_path_is_refused(ws, sessions, monkeypatch):
    monkeypatch.setattr(cmd, "ask", answering(json.dumps({
        "slug": "../../etc/passwd", "title": "x", "sessions": ["claude/s-1"],
        "body": "y"})))

    report = cmd.run(ws, host="codex", now=TODAY)
    assert report.written == [] and report.skipped[0][1] == "not a slug"


# --------------------------------------------------------------------------
# what a pass refuses to do
# --------------------------------------------------------------------------

def test_a_pass_that_could_not_run_writes_nothing(ws, sessions, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("codex exited 127")

    monkeypatch.setattr(cmd, "ask", boom)

    report = cmd.run(ws, host="codex", now=TODAY)

    assert report.written == [] and "could not run" in report.note
    assert not patterns.all_patterns(ws)
    assert ledger.entries(ws)[-1]["ok"] is False, "and it still cost what it cost"


def test_over_budget_nothing_is_read(ws, sessions, monkeypatch):
    (ws / "config.yaml").write_text("research:\n  weekly_calls: 1\n", encoding="utf-8")
    ledger.record(ws, ledger.REVIEW, "codex", slug="earlier")
    called = []
    monkeypatch.setattr(cmd, "ask", lambda *a, **k: called.append(1) or "")

    report = cmd.run(ws, host="codex", now=TODAY)

    assert not called and "budget" in report.note


def test_the_master_switch_stops_the_slow_loop_too(ws, sessions, monkeypatch):
    (ws / "config.yaml").write_text("research:\n  llm_calls: false\n", encoding="utf-8")
    called = []
    monkeypatch.setattr(cmd, "ask", lambda *a, **k: called.append(1) or "")

    report = cmd.run(ws, host="codex", now=TODAY)
    assert not called and "switched off" in report.note


def test_a_dry_run_reads_nothing_and_says_so(ws, sessions, monkeypatch):
    called = []
    monkeypatch.setattr(cmd, "ask", lambda *a, **k: called.append(1) or "")

    report = cmd.run(ws, host="codex", dry_run=True, now=TODAY)

    assert not called and "would ask codex" in report.note
    assert ledger.entries(ws) == []


def test_a_workspace_where_nothing_lines_up_is_not_read(ws, monkeypatch):
    class Empty:
        sessions = []
        unreadable = {}

    monkeypatch.setattr(cmd.transcripts, "sweep", lambda *a, **k: Empty())
    called = []
    monkeypatch.setattr(cmd, "ask", lambda *a, **k: called.append(1) or "")

    report = cmd.run(ws, host="codex", now=TODAY)

    assert not called and "nothing to read" in report.note


def test_a_host_that_could_not_be_read_is_reported_not_hidden(ws, sessions,
                                                              monkeypatch):
    class Partial:
        def __init__(self, made):
            self.sessions = made
            self.unreadable = {"gemini": "OSError: the vendor moved a directory"}

    monkeypatch.setattr(cmd.transcripts, "sweep", lambda *a, **k: Partial(sessions))
    monkeypatch.setattr(cmd, "ask", answering(one_pattern()))

    report = cmd.run(ws, host="codex", now=TODAY)

    assert "gemini" in report.unreadable
    assert "gemini" in cmd.render(report)


# --------------------------------------------------------------------------
# the prompt
# --------------------------------------------------------------------------

def test_the_prompt_names_the_sessions_and_what_happened(ws, sessions):
    from magi.reflect import signals as sig
    from magi.state import loaded

    picked = sig.sample(sessions, sig.collect(loaded(ws)))
    prompt = cmd.build_prompt(picked)

    assert "claude/s-1" in prompt
    assert "reversal: p-gap" in prompt
    assert "the boundary condition was wrong" in prompt, "the words themselves"


def test_one_event_is_not_evidence_from_two_sessions(ws, sessions):
    """Attaching one reversal to every session whose window it lands near
    presented the model with the same thing twice, under two headings — and a
    model naming both cleared the two-session gate off one event."""
    from magi.reflect import signals as sig
    from magi.state import loaded

    picked = sig.sample(sessions, sig.collect(loaded(ws)))
    seen = [signal.slug for item in picked for signal in item.signals]

    assert len(seen) == len(set(seen)), "no event counted twice"


def test_ctrl_c_during_a_headless_pass_is_not_swallowed(ws, sessions, monkeypatch):
    """A fifteen-minute subprocess behind `except BaseException` with no
    re-raise absorbs the interrupt, records it as a failed call, and returns a
    report — so the operator presses Ctrl+C and watches it carry on.
    `review.review` has always re-raised; these two did not."""
    def interrupted(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(cmd, "ask", interrupted)

    with pytest.raises(KeyboardInterrupt):
        cmd.run(ws, host="codex")


def test_and_the_call_is_still_recorded_before_it_propagates(ws, sessions, monkeypatch):
    """It spent the wall clock and, on a metered account, the money. A budget
    that only counts the calls that finished is one an interrupt walks
    through."""
    from magi.core import ledger

    def interrupted(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(cmd, "ask", interrupted)

    with pytest.raises(KeyboardInterrupt):
        cmd.run(ws, host="codex")

    assert ledger.entries(ws)[-1]["ok"] is False
