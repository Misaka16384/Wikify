"""The layer that makes the slow loop's gates executable.

"The same gap in at least two independent sessions" and "not seen for ninety
days" are the two rules that stop the loop turning noise into rules. Written as
prose in a prompt they are wishes. Written as files they are
`len(set(sessions)) >= 2` and a date comparison — which is the entire reason
this directory exists.

The other property tested here is that a second sighting **adds** to a page
rather than rewriting it. The body is the account written when the pattern was
first understood; a later pass replacing it would quietly erase the evidence
the two-session gate rests on.
"""

from __future__ import annotations

import datetime as dt

import pytest

from magi.reflect import patterns


TODAY = dt.date(2026, 8, 29)


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "output").mkdir()
    return tmp_path


def seen(ws, slug="p-stall", session="claude/s-1", host="claude", when=TODAY, **kw):
    return patterns.observe(ws, slug, title=kw.get("title", "Sweeps stall at L=24"),
                            body=kw.get("body", "## What happened\n\nIt stalled."),
                            session=session, host=host, patch=kw.get("patch"),
                            when=when)


# --------------------------------------------------------------------------
# one page, many sightings
# --------------------------------------------------------------------------

def test_a_first_sighting_writes_a_page(ws):
    pattern = seen(ws)

    assert pattern.path.is_file()
    assert pattern.independent == 1
    assert patterns.read(pattern.path).title == "Sweeps stall at L=24"


def test_a_second_sighting_adds_a_session(ws):
    seen(ws, session="claude/s-1", host="claude")
    pattern = seen(ws, session="codex/s-2", host="codex",
                   when=TODAY + dt.timedelta(days=1))

    assert pattern.independent == 2
    assert pattern.hosts == ["claude", "codex"]
    assert pattern.first_seen == TODAY.isoformat()
    assert pattern.last_seen == (TODAY + dt.timedelta(days=1)).isoformat()


def test_the_same_session_twice_is_one_session(ws):
    """The gate is about independence, not about how often something was
    mentioned in one conversation."""
    seen(ws, session="claude/s-1")
    pattern = seen(ws, session="claude/s-1")
    assert pattern.independent == 1


def test_the_account_written_first_is_not_overwritten(ws):
    """It is the evidence the two-session gate rests on."""
    seen(ws, body="## What happened\n\nThe first, careful account.")
    seen(ws, session="codex/s-2", host="codex", body="something vaguer")

    assert "first, careful account" in patterns.read(
        patterns.path_for(ws, "p-stall")).body


# --------------------------------------------------------------------------
# the gates
# --------------------------------------------------------------------------

def test_one_session_is_not_enough_to_propose_on(ws):
    seen(ws)
    assert patterns.ready(ws, now=TODAY) == []


def test_two_sessions_earns_a_proposal(ws):
    seen(ws, session="claude/s-1", host="claude")
    seen(ws, session="codex/s-2", host="codex")

    assert [p.slug for p in patterns.ready(ws, now=TODAY)] == ["p-stall"]


def test_a_pattern_nobody_has_seen_for_ninety_days_goes_quiet(ws):
    old = TODAY - dt.timedelta(days=100)
    seen(ws, session="claude/s-1", when=old)
    seen(ws, session="codex/s-2", host="codex", when=old)

    assert patterns.ready(ws, now=TODAY) == []
    assert [p.slug for p in patterns.stale(ws, now=TODAY)] == ["p-stall"]


def test_a_pattern_that_comes_back_is_live_again(ws):
    """It recurred, so the rule it produced has just earned its keep."""
    page = patterns.path_for(ws, "p-stall")
    seen(ws, when=TODAY - dt.timedelta(days=200))
    text = page.read_text(encoding="utf-8").replace("status: open", "status: retired")
    page.write_text(text, encoding="utf-8")

    pattern = seen(ws, session="codex/s-9", host="codex", when=TODAY)
    assert pattern.status == patterns.OPEN


def test_a_slug_that_is_a_path_is_refused(ws):
    with pytest.raises(ValueError):
        patterns.path_for(ws, "../../escape")


# --------------------------------------------------------------------------
# patches
# --------------------------------------------------------------------------

def test_append_puts_it_at_the_end(ws):
    out = patterns.apply_patch("one\n", {"op": "append", "text": "two"})
    assert out == "one\ntwo\n"


def test_replace_needs_the_target_exactly_as_written(ws):
    with pytest.raises(patterns.PatchError):
        patterns.apply_patch("hello world\n",
                             {"op": "replace", "target": "HELLO", "text": "x"})


def test_a_target_that_matches_twice_is_refused(ws):
    """A patcher that picks the first match edits the wrong paragraph
    eventually, and does it quietly."""
    with pytest.raises(patterns.PatchError) as caught:
        patterns.apply_patch("a\na\n", {"op": "replace", "target": "a", "text": "b"})
    assert "twice" in str(caught.value) or "2 times" in str(caught.value)


def test_insert_after_lands_after_the_target(ws):
    out = patterns.apply_patch("## Rules\n\nfirst\n",
                               {"op": "insert_after", "target": "## Rules",
                                "text": "second"})
    assert out.splitlines()[:2] == ["## Rules", "second"]


def test_an_operation_nobody_defined_is_refused(ws):
    with pytest.raises(patterns.PatchError):
        patterns.apply_patch("x", {"op": "rewrite-everything", "text": "y"})


def test_a_patch_with_nothing_in_it_is_refused(ws):
    with pytest.raises(patterns.PatchError):
        patterns.apply_patch("x", {"op": "append", "text": "   "})
