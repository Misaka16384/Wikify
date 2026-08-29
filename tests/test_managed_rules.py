"""The managed block's truth: the template MAGI ships, plus what a person accepted.

This is the arrangement that lets a slow loop change the protocol every session
reads without letting a model write it. **A model never writes the block.** It
proposes; a person is the only gate; the CLI is the only pen; and what the pen
writes is derived from a ledger where every line records who decided what.

So what is guarded is the template and the rendering — not the result. Pinning
the rendered block would turn every rule a person accepted into a failing test,
which is a guard that teaches people to delete guards.

The budget is separate from the forty-line ratchet for the same reason: the
template is MAGI's, the rules are the workspace's, and mixing them would mean
one library's earned rules could fail another library's build.
"""

from __future__ import annotations

import hashlib

import pytest

from magi.core import managed
from magi.reflect import proposals


def a_rule(text):
    class Row:
        pass

    row = Row()
    row.text = text
    return row


# --------------------------------------------------------------------------
# what is guarded
# --------------------------------------------------------------------------

def test_the_template_is_the_same_for_every_workspace():
    """Two libraries at the same version get the same protocol. The name and
    the scope are the only things that differ."""
    a = managed.template("Alpha", "A scope.", "light")
    b = managed.template("Alpha", "A scope.", "light")
    assert hashlib.sha256(a.encode()).hexdigest() == \
        hashlib.sha256(b.encode()).hexdigest()


def test_the_rules_are_not_part_of_the_template():
    plain = managed.template("Alpha", "A scope.")
    with_rules = managed.body("Alpha", "A scope.",
                              rules=[a_rule("Check the boundary first.")])

    assert "Check the boundary first." not in plain
    assert with_rules.startswith(plain)


def test_the_ratchet_measures_the_template(tmp_path):
    """A workspace that accepted seven rules must not fail MAGI's own build."""
    assert len(managed.template("Alpha", "A scope.").splitlines()) <= 40


def test_the_same_ledger_renders_the_same_block():
    """The behaviour that is guarded: given these rules, this output."""
    rules = [a_rule("One."), a_rule("Two.")]
    assert managed.body("A", "B", rules=rules) == managed.body("A", "B", rules=rules)


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def test_no_rules_means_no_section():
    """An empty heading is a line every session pays to read for nothing."""
    assert "Rules this workspace earned" not in managed.body("A", "B", rules=[])


def test_each_rule_is_one_line():
    body = managed.body("A", "B", rules=[a_rule("First.\nsecond half"),
                                         a_rule("Second.")])
    section = body.split("Rules this workspace earned", 1)[1]
    assert section.strip().splitlines() == ["- First. second half", "- Second."]


def test_rendering_never_truncates():
    """The ledger is the truth and the block may not say less than it. A budget
    that silently dropped the eighth rule would leave somebody sure they had
    accepted something the agent never sees — refusing a new one is
    `magi reflect accept`'s job, not the renderer's."""
    rules = [a_rule(f"Rule {index}.") for index in range(managed.RULE_BUDGET + 5)]
    body = managed.body("A", "B", rules=rules)

    for index in range(managed.RULE_BUDGET + 5):
        assert f"Rule {index}." in body


# --------------------------------------------------------------------------
# the round trip through the ledger
# --------------------------------------------------------------------------

@pytest.fixture
def ws(tmp_path):
    (tmp_path / "output").mkdir()
    return tmp_path


def test_only_accepted_rules_reach_the_block(ws):
    accepted = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                                 text="Check the boundary first.", pattern="p")
    waiting = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                                text="Never sweep on a Friday.", pattern="p")
    turned_down = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                                    text="Ask before every command.", pattern="p")
    proposals.decide(ws, accepted.id, proposals.ACCEPTED)
    proposals.decide(ws, turned_down.id, proposals.REJECTED)

    body = managed.body("A", "B", rules=proposals.live_rules(ws))

    assert "Check the boundary first." in body
    assert waiting.text not in body, "nobody has decided about it"
    assert turned_down.text not in body


def test_a_promoted_rule_leaves_the_block(ws):
    """The check runs now; a rule that is also a test is read twice a session
    for nothing."""
    made = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="p")
    proposals.decide(ws, made.id, proposals.ACCEPTED)
    assert made.text in managed.body("A", "B", rules=proposals.live_rules(ws))

    proposals.decide(ws, made.id, proposals.PROMOTED)
    assert made.text not in managed.body("A", "B", rules=proposals.live_rules(ws))


def test_a_patch_proposal_is_not_a_rule(ws):
    """Only prose for the block is rendered into the block."""
    made = proposals.propose(ws, kind=proposals.PATCH, target=".claude/settings.json",
                             text="add a hook", pattern="p")
    proposals.decide(ws, made.id, proposals.ACCEPTED)

    assert proposals.live_rules(ws) == []
