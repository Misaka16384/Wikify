"""The budget, and the two ways it says no.

The property that matters is not the arithmetic — it is what happens at the
boundary. A budget that stops the call but lets the claim retire unreviewed
would be worse than no budget at all: it would spend nothing and approve
everything. So both refusals happen *before* the subprocess, and both end with
the same sentence.

The unit is calls rather than dollars because a headless CLI does not reliably
say what a request cost, and a budget denominated in a number nobody can
measure is a budget that quietly does nothing.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from magi.core import ledger


AT = dt.datetime(2026, 8, 26, 12, 0, tzinfo=dt.timezone.utc)   # a Wednesday


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "output").mkdir()
    return tmp_path


def fill(ws, count, when=AT, kind=ledger.REVIEW):
    for index in range(count):
        ledger.record(ws, kind, "codex", slug=f"p-{index}", when=when)


# --------------------------------------------------------------------------
# what is written down
# --------------------------------------------------------------------------

def test_a_call_is_one_line(ws):
    ledger.record(ws, ledger.REVIEW, "codex", slug="p-gap", seconds=12.34, when=AT)

    lines = ledger.path_for(ws).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert (entry["kind"], entry["host"], entry["slug"]) == ("review", "codex", "p-gap")
    assert entry["seconds"] == 12.3


def test_a_failed_call_still_counts(ws):
    """It spent the wall clock and, on a metered account, the money. Not
    counting it is how a broken adapter burns a week in an afternoon."""
    ledger.record(ws, ledger.REVIEW, "codex", ok=False, note="timed out", when=AT)
    assert ledger.spent(ws, when=AT) == 1


def test_a_line_that_will_not_parse_is_skipped_not_fatal(ws):
    """This file is what the gate reads. A gate that crashes on one bad line
    stops every review in the workspace."""
    ledger.record(ws, ledger.REVIEW, "codex", when=AT)
    with open(ledger.path_for(ws), "a", encoding="utf-8") as handle:
        handle.write("{not json\n")

    assert ledger.spent(ws, when=AT) == 1


def test_no_ledger_yet_is_not_an_error(ws):
    assert ledger.entries(ws) == [] and ledger.spent(ws, when=AT) == 0


# --------------------------------------------------------------------------
# the week
# --------------------------------------------------------------------------

def test_last_weeks_calls_are_last_weeks(ws):
    """Calendar weeks, not a rolling window: "twelve left until Monday" is
    something a person can plan around."""
    fill(ws, 3, when=AT - dt.timedelta(days=7))
    fill(ws, 2, when=AT)

    assert ledger.spent(ws, when=AT) == 2


def test_the_summary_says_what_is_left_and_when_it_refills(ws):
    fill(ws, 3, when=AT)
    out = ledger.summary(ws, limit=10, when=AT)

    assert (out["spent"], out["left"], out["over"]) == (3, 7, False)
    assert out["until"] == "2026-08-31", "the next Monday"
    assert out["by_kind"]["review"] == 3


# --------------------------------------------------------------------------
# saying no
# --------------------------------------------------------------------------

def test_under_budget_says_nothing(ws):
    fill(ws, 2, when=AT)
    ledger.check(ws, limit=5, when=AT)   # no exception is the pass


def test_at_the_limit_it_refuses(ws):
    fill(ws, 5, when=AT)
    with pytest.raises(ledger.OverBudget) as caught:
        ledger.check(ws, limit=5, when=AT)

    said = str(caught.value)
    assert "5/5" in said and "2026-08-31" in said
    assert "nothing counts as reviewed" in said, (
        "a budget that lets a claim retire unreviewed is worse than no budget")


def test_the_master_switch_refuses_before_anything_else(ws):
    """Off means off — not "off unless there is budget left"."""
    with pytest.raises(ledger.SwitchedOff) as caught:
        ledger.check(ws, limit=1000, enabled=False, when=AT)
    assert "nothing counts as reviewed" in str(caught.value)


def test_a_zero_budget_is_a_refusal_not_a_free_pass(ws):
    with pytest.raises(ledger.OverBudget):
        ledger.check(ws, limit=0, when=AT)
