"""The ledger: a count of MAGI's own calls, and the one switch that says no.

There was a weekly budget here until 2026-09-03; the person using it cancelled
it (ledger.py says why). What is left is the record — every call, its host,
model, effort, tier and outcome — and the master switch, which has to refuse
*before* the subprocess and end with the sentence every caller relies on:
nothing counts as reviewed.

The unit is calls rather than dollars because a headless CLI does not reliably
say what a request cost, and a count denominated in a number nobody can
measure is a count that quietly means nothing.
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


def test_the_summary_counts_the_week_by_kind_and_by_failure(ws):
    fill(ws, 3, when=AT)
    ledger.record(ws, ledger.REVIEW, "codex", ok=False, when=AT)
    out = ledger.summary(ws, when=AT)

    assert (out["spent"], out["failed"]) == (4, 1)
    assert out["by_kind"]["review"] == 4
    assert "limit" not in out and "left" not in out, "a count, not a quota"


def test_the_tier_is_recorded_and_tallied(ws):
    ledger.record(ws, ledger.REVIEW, "claude", model="opus", tier="strong", when=AT)
    ledger.record(ws, ledger.REVIEW, "claude", model="haiku", tier="cheap", when=AT)
    ledger.record(ws, ledger.REVIEW, "codex", when=AT)
    row = json.loads(ledger.path_for(ws).read_text(encoding="utf-8").splitlines()[0])
    assert row["tier"] == "strong"
    assert ledger.summary(ws, when=AT)["by_tier"] == {"strong": 1, "cheap": 1}


# --------------------------------------------------------------------------
# saying no
# --------------------------------------------------------------------------

def test_there_is_no_limit_to_hit(ws):
    """The weekly budget was cancelled on 2026-09-03: token plans make a
    per-call cap pointless, and the day it went it was refusing reviews over
    four calls that had failed on a vendor's own quota."""
    fill(ws, 500, when=AT)
    ledger.check(ws, when=AT)   # no exception is the pass


def test_the_master_switch_is_the_one_refusal(ws):
    """Off means off."""
    with pytest.raises(ledger.SwitchedOff) as caught:
        ledger.check(ws, enabled=False, when=AT)
    assert "nothing counts as reviewed" in str(caught.value)
