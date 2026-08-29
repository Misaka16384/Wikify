"""`magi reflect accept | reject | promote` — the three buttons, as a command.

They sit at the same level as `close` and `publish`: things a person does, and
the only way a verdict is ever written. A ledger the proposer can write is a
ledger that says whatever the proposer wanted it to say.

The budget test is the one that matters most. The rule section is read at the
start of every session on every host, so it has to be able to be *full* — and
being full has to mean "take something out first", not "the eighth rule quietly
does not appear". Refusing at accept time keeps the ledger and the block saying
the same thing.
"""

from __future__ import annotations

import json

import pytest

from magi import init_workspace
from magi.core import managed
from magi.reflect import cmd, proposals


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "topic"
    init_workspace.main(["--topic-dir", str(root), "--name", "T", "--scope", "S"])
    return root


def a_rule(ws, text="Check the boundary condition before starting a sweep."):
    return proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md", text=text,
                             pattern="sweeps-stall", hosts=["claude", "codex"])


def run(ws, *argv):
    return cmd.main(list(argv) + ["--topic-dir", str(ws)])


def block(ws):
    return (ws / "AGENTS.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# accepting
# --------------------------------------------------------------------------

def test_accepting_puts_the_rule_in_front_of_every_session(ws):
    made = a_rule(ws)

    assert run(ws, "accept", made.id, "--note", "yes, that one") == 0

    assert made.text in block(ws)
    assert proposals.get(ws, made.id).note == "yes, that one"


def test_the_block_is_rewritten_by_whoever_changed_the_ledger(ws):
    """Not at the next install. The block and the ledger disagreeing is the one
    state neither of them can be read in."""
    made = a_rule(ws)
    before = block(ws)

    run(ws, "accept", made.id)

    assert block(ws) != before


def test_rejecting_writes_it_down_in_full(ws):
    made = a_rule(ws, "Never run a sweep after 5pm.")

    assert run(ws, "reject", made.id, "--note", "that is not the problem") == 0

    turned_down = proposals.rejected(ws)
    assert turned_down[0].text == "Never run a sweep after 5pm."
    assert turned_down[0].note == "that is not the problem"
    assert "Never run a sweep after 5pm." not in block(ws)


def a_checkable_rule(ws, text="A proposition under test needs a prediction."):
    """A proposal that names a predicate the gates can actually run."""
    return proposals.propose(
        ws, kind=proposals.RULE, target="AGENTS.md", text=text,
        pattern="no-bet-before-work", hosts=["claude", "codex"],
        patch={"rule": "require_field", "kind": "proposition", "status": "testing",
               "field": "bet"})


def test_promoting_takes_the_prose_out_and_puts_a_check_in(ws):
    """The whole point of promoting: from a line every session reads and none
    of them reliably obeys, to something that runs."""
    made = a_checkable_rule(ws)
    run(ws, "accept", made.id)
    assert made.text in block(ws)

    assert run(ws, "promote", made.id) == 0

    assert made.text not in block(ws)
    assert proposals.get(ws, made.id).verdict == proposals.PROMOTED
    config = (ws / "config.yaml").read_text(encoding="utf-8")
    assert "require_field" in config and made.id in config


def test_prose_cannot_be_promoted_and_says_why(ws, capsys):
    """Most good advice is prose. The honest answer is that there is nothing
    to run — not a file somebody might write a check into one day."""
    made = a_rule(ws)
    run(ws, "accept", made.id)
    capsys.readouterr()

    assert run(ws, "promote", made.id) == 1

    assert "does not name one of" in capsys.readouterr().err
    assert made.text in block(ws), "and it stays where it was"


def test_retiring_a_promoted_rule_stops_the_check(ws):
    made = a_checkable_rule(ws)
    run(ws, "accept", made.id)
    run(ws, "promote", made.id)
    assert "require_field" in (ws / "config.yaml").read_text(encoding="utf-8")

    run(ws, "retire", made.id)

    assert "require_field" not in (ws / "config.yaml").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# the budget
# --------------------------------------------------------------------------

def test_a_full_rule_section_refuses_and_says_what_to_retire(ws, capsys):
    """Full has to mean "take something out first". The alternative — the
    eighth rule quietly not appearing — leaves somebody sure they accepted
    something the agent never sees."""
    kept = []
    for index in range(managed.RULE_BUDGET):
        made = a_rule(ws, f"Rule number {index}.")
        run(ws, "accept", made.id)
        kept.append(made)
    capsys.readouterr()

    one_too_many = a_rule(ws, "One rule too many.")
    code = run(ws, "accept", one_too_many.id)

    assert code == 1
    said = capsys.readouterr().err
    assert "full" in said and kept[0].id in said, "and it names one to retire"
    assert "One rule too many." not in block(ws)
    assert proposals.get(ws, one_too_many.id).open, "nothing was decided"


def test_retiring_one_makes_room(ws):
    for index in range(managed.RULE_BUDGET):
        run(ws, "accept", a_rule(ws, f"Rule number {index}.").id)
    first = proposals.live_rules(ws)[0]

    run(ws, "retire", first.id)
    fresh = a_rule(ws, "The one that was waiting.")

    assert run(ws, "accept", fresh.id) == 0
    assert "The one that was waiting." in block(ws)
    assert "Rule number 0." not in block(ws)


def test_the_budget_is_a_workspace_setting(ws):
    (ws / "config.yaml").write_text("research:\n  rule_budget: 1\n", encoding="utf-8")
    run(ws, "accept", a_rule(ws, "The first one.").id)

    assert run(ws, "accept", a_rule(ws, "The second one.").id) == 1


# --------------------------------------------------------------------------
# saying what is waiting
# --------------------------------------------------------------------------

def test_list_shows_what_is_undecided(ws, capsys):
    made = a_rule(ws)
    decided = a_rule(ws, "Already ruled on.")
    proposals.decide(ws, decided.id, proposals.REJECTED)

    run(ws, "list")

    out = capsys.readouterr().out
    assert made.id in out and "Already ruled on." not in out


def test_list_says_where_proposals_come_from_when_there_are_none(ws, capsys):
    run(ws, "list")
    assert "magi reflect propose" in capsys.readouterr().out


def test_a_verdict_needs_an_id(ws, capsys):
    assert run(ws, "accept") == 1
    assert "needs a proposal id" in capsys.readouterr().err


def test_a_verdict_on_something_that_is_not_there_says_so(ws, capsys):
    assert run(ws, "accept", "r-nope") == 1
    assert "no proposal" in capsys.readouterr().err


def test_json_output_is_machine_readable(ws, capsys):
    made = a_rule(ws)
    run(ws, "accept", made.id, "--json")

    payload = json.loads(capsys.readouterr().out)
    assert payload["id"] == made.id and payload["verdict"] == proposals.ACCEPTED


# --------------------------------------------------------------------------
# a fact about the subject is not a rule about the work
# --------------------------------------------------------------------------

def a_fact(ws, text="The boundary mode is gapless below L=16."):
    return proposals.propose(ws, kind=proposals.FACT, target="wiki", text=text,
                             pattern="sweeps-stall", hosts=["claude", "codex"])


def test_a_fact_is_filed_where_an_unfiled_thought_goes(ws):
    """The slow loop has not read the library, so it is not entitled to decide
    where a fact lives in it. `magi next` routes the inbox."""
    from magi import state

    made = a_fact(ws)

    assert run(ws, "accept", made.id) == 0
    assert any("gapless below L=16" in line for line in state.unfiled(ws))


def test_a_fact_never_reaches_the_block(ws):
    """Every session on every host would read it forever, whether or not that
    session is about the topic."""
    made = a_fact(ws)
    run(ws, "accept", made.id)

    assert "gapless below L=16" not in block(ws)


def test_the_note_says_where_it_came_from(ws):
    from magi import state

    made = a_fact(ws)
    run(ws, "accept", made.id)

    line = [row for row in state.unfiled(ws) if "gapless" in row][0]
    assert "sweeps-stall" in line


def test_a_fact_does_not_spend_the_rule_budget(ws):
    from magi.core import managed

    for _ in range(managed.RULE_BUDGET + 2):
        run(ws, "accept", a_fact(ws).id)

    assert run(ws, "accept", a_rule(ws).id) == 0


# --------------------------------------------------------------------------
# a change to how a skill works
#
# The loop may notice that a method could be better — that is half of why the
# sampler reserves room for sessions that went well. What it may *do* depends
# on whose file it is.
# --------------------------------------------------------------------------

def a_skill_change(ws, target="compile", text="Read the figure captions first."):
    return proposals.propose(
        ws, kind=proposals.SKILL, target=target, text=text,
        pattern="captions-missed", hosts=["claude", "codex"],
        patch={"op": "replace", "target": "## Rules", "text": "## Rules\n- Read captions."})


def test_a_change_to_an_official_skill_is_recorded_not_applied(ws, capsys):
    """MAGI does not edit its own package: the change would be lost at the next
    upgrade, and it would be made to a file every workspace on the machine
    shares, on one library's evidence."""
    made = a_skill_change(ws)

    assert run(ws, "accept", made.id) == 0

    said = capsys.readouterr().out
    assert "belongs upstream" in said
    assert proposals.get(ws, made.id).verdict == proposals.ACCEPTED


def test_a_change_to_your_own_skill_is_applied(ws, monkeypatch, tmp_path):
    from magi import skills_cmd

    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "magicfg"))
    mine = skills_cmd.user_skills_dir() / "sweep"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text("---\nname: sweep\n---\n\n## Rules\n- Old.\n",
                                   encoding="utf-8")

    made = a_skill_change(ws, target="sweep")
    assert run(ws, "accept", made.id) == 0

    assert "Read captions." in (mine / "SKILL.md").read_text(encoding="utf-8")


def test_a_skill_change_must_say_what_comes_out(ws, capsys):
    """A loop that only appends makes every skill longer every week, and a
    skill is loaded into a context window on every session that uses it."""
    from magi import skills_cmd

    made = proposals.propose(ws, kind=proposals.SKILL, target="sweep",
                             text="just add something", pattern="p",
                             hosts=["claude", "codex"])
    (skills_cmd.user_skills_dir() / "sweep").mkdir(parents=True, exist_ok=True)
    (skills_cmd.user_skills_dir() / "sweep" / "SKILL.md").write_text(
        "---\nname: sweep\n---\n\nbody\n", encoding="utf-8")

    assert run(ws, "accept", made.id) == 1
    assert "what goes in and what comes out" in capsys.readouterr().err
