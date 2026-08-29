"""What was proposed, and what a person did about it.

Two properties carry this file, and both are about who is allowed to write.

**A rejection keeps its full text.** Being turned down is not a filter — it is
the input to the next proposal. The loop reads what it already suggested and
was told no about, so that it stops suggesting it *and* can say what makes the
next idea different. Keeping only the absence would teach nothing.

**The verdict is a separate record.** Nothing is rewritten in place, so the
question "did anybody ever accept this, and when" has an answer even after
somebody changed their mind twice.
"""

from __future__ import annotations

import json

import pytest

from magi.reflect import proposals


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "output").mkdir()
    return tmp_path


def a_rule(ws, text="Check the boundary condition before starting a sweep.",
           target="AGENTS.md", pattern="sweeps-stall"):
    return proposals.propose(ws, kind=proposals.RULE, target=target, text=text,
                             pattern=pattern, hosts=["claude", "codex"],
                             evidence=["> the boundary condition was wrong"])


# --------------------------------------------------------------------------
# the record
# --------------------------------------------------------------------------

def test_a_proposal_starts_undecided(ws):
    made = a_rule(ws)
    assert made.open and not made.verdict
    assert proposals.open_proposals(ws)[0].id == made.id


def test_the_evidence_travels_with_it(ws):
    made = a_rule(ws)
    read = proposals.get(ws, made.id)
    assert read.pattern == "sweeps-stall"
    assert read.hosts == ["claude", "codex"]
    assert read.evidence == ["> the boundary condition was wrong"]


def test_a_proposal_with_no_text_is_not_a_proposal(ws):
    with pytest.raises(ValueError):
        proposals.propose(ws, kind=proposals.RULE, target="x", text="   ",
                          pattern="p")


def test_a_kind_nobody_defined_is_refused(ws):
    with pytest.raises(ValueError):
        proposals.propose(ws, kind="vibes", target="x", text="y", pattern="p")


# --------------------------------------------------------------------------
# deciding
# --------------------------------------------------------------------------

def test_accepting_makes_it_a_live_rule(ws):
    made = a_rule(ws)
    proposals.decide(ws, made.id, proposals.ACCEPTED, note="yes, that is the one")

    live = proposals.live_rules(ws)
    assert [p.id for p in live] == [made.id]
    assert live[0].note == "yes, that is the one"


def test_promoting_takes_it_out_of_the_block(ws):
    """The check runs now. A rule that is also a test is a rule every session
    pays to read twice."""
    made = a_rule(ws)
    proposals.decide(ws, made.id, proposals.ACCEPTED)
    proposals.decide(ws, made.id, proposals.PROMOTED)

    assert proposals.live_rules(ws) == []
    assert proposals.get(ws, made.id).verdict == proposals.PROMOTED


def test_a_rejection_keeps_every_word(ws):
    made = a_rule(ws, text="Never run a sweep after 5pm.")
    proposals.decide(ws, made.id, proposals.REJECTED, note="that is not the problem")

    turned_down = proposals.rejected(ws)
    assert len(turned_down) == 1
    assert turned_down[0].text == "Never run a sweep after 5pm."
    assert turned_down[0].note == "that is not the problem"


def test_the_last_word_wins_and_the_history_stays(ws):
    made = a_rule(ws)
    for verdict in (proposals.ACCEPTED, proposals.REJECTED, proposals.ACCEPTED):
        proposals.decide(ws, made.id, verdict)

    assert proposals.get(ws, made.id).verdict == proposals.ACCEPTED
    raw = proposals.path_for(ws).read_text(encoding="utf-8")
    assert raw.count('"kind": "decide"') == 3, "nothing is rewritten in place"


def test_a_verdict_nobody_defined_is_refused(ws):
    made = a_rule(ws)
    with pytest.raises(ValueError):
        proposals.decide(ws, made.id, "maybe")


def test_a_verdict_for_a_proposal_that_is_not_there_changes_nothing(ws):
    proposals.decide(ws, "r-nope", proposals.ACCEPTED)
    assert proposals.all_proposals(ws) == []


# --------------------------------------------------------------------------
# what the next pass is told
# --------------------------------------------------------------------------

def test_the_same_change_is_only_proposed_once(ws):
    """Proposing the same thing again while the first is still waiting is how
    a queue turns into a list of duplicates."""
    made = a_rule(ws)
    assert proposals.fingerprint(made.kind, made.target, made.text) \
        in proposals.already_proposed(ws)


def test_a_full_stop_does_not_make_it_a_new_idea(ws):
    """The one mechanical half of "do not propose it again" — an exact-text key
    let the same rule come back with punctuation added."""
    made = a_rule(ws, text="check the boundary condition")

    assert proposals.fingerprint(made.kind, "AGENTS.md",
                                 "Check the boundary condition.") \
        in proposals.already_proposed(ws)


def test_a_bad_line_does_not_stop_the_gate(ws):
    """This file decides what goes into the protocol every agent reads. A gate
    that crashes on one stray character stops the whole loop."""
    made = a_rule(ws)
    with open(proposals.path_for(ws), "a", encoding="utf-8") as handle:
        handle.write("{not json\n")

    assert [p.id for p in proposals.all_proposals(ws)] == [made.id]


def test_no_ledger_yet_is_not_an_error(ws):
    assert proposals.all_proposals(ws) == [] and proposals.live_rules(ws) == []


def test_the_ledger_is_the_two_files_it_says_it_is(ws):
    """`output/reflect/ledger.jsonl` records what was proposed;
    `output/llm-ledger.jsonl` records what was spent. Two questions."""
    from magi.core import ledger as spend

    a_rule(ws)
    spend.record(ws, spend.REFLECT, "codex")

    assert proposals.path_for(ws) != spend.path_for(ws)
    proposed = json.loads(proposals.path_for(ws).read_text(encoding="utf-8").splitlines()[0])
    assert "verdict" not in proposed, "a proposal is not a decision"
