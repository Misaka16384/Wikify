"""The closed vocabulary a promoted rule has to fit in.

The point of promoting a rule is that *something now checks it*. So what a
promotion produces must be a thing the gates already run — five predicates,
no escape hatch. A proposal that fits none of them cannot be promoted; it stays
prose, which is what most good advice is.

The two properties under test are the ones that make that safe: a rule that
cannot be executed is refused **where it is written** rather than discovered by
the gate at the worst moment, and every violation can say which proposal put
the rule there, because a rule nobody can trace is a rule nobody can retire.
"""

from __future__ import annotations

import datetime as dt

import pytest

from magi import state
from magi.core import rules, vocab
from magi.kb import threads


NOW = dt.datetime(2026, 8, 29, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    return tmp_path


def proposition(ws, slug="p-gap", status=None, **extra):
    path = threads.create(ws / "threads" / f"{slug}.md", vocab.PROPOSITION,
                          slug.upper(), f"Why {slug}.", lines=["qec"],
                          extra=extra or None)
    if status:
        threads.set_status(path, status, "moving", host="claude")
    return path


def loaded(ws):
    return state.load(ws, now=NOW)


# --------------------------------------------------------------------------
# what may be written down
# --------------------------------------------------------------------------

def test_a_rule_outside_the_vocabulary_is_refused():
    """There is no escape hatch on purpose: everything in the vocabulary is
    executable, and everything executable is checked on every run."""
    with pytest.raises(rules.RuleError) as caught:
        rules.parse([{"rule": "do_the_right_thing"}])
    assert "no such rule" in str(caught.value)


def test_a_rule_missing_a_parameter_is_refused_where_it_is_written():
    """A gate that quietly ignores the rule somebody thought they had is worse
    than one that will not start — the first kind is discovered by not
    catching anything."""
    with pytest.raises(rules.RuleError) as caught:
        rules.parse([{"rule": rules.REQUIRE_FIELD, "kind": "proposition"}])
    assert "needs" in str(caught.value)


def test_a_rule_round_trips_through_the_config_shape():
    entry = {"rule": rules.MAX_OPEN_PER_LINE, "limit": 3, "from": "r-abc"}
    parsed = rules.parse([entry])[0]

    assert parsed.source == "r-abc"
    assert rules.to_entry(parsed) == entry


# --------------------------------------------------------------------------
# the five predicates
# --------------------------------------------------------------------------

def test_require_field(ws):
    proposition(ws, "p-with", status="testing", bet="supported")
    proposition(ws, "p-without", status="testing")

    found = rules.check(loaded(ws), rules.parse([
        {"rule": rules.REQUIRE_FIELD, "kind": "proposition", "status": "testing",
         "field": "bet"}]))

    assert [v.slug for v in found] == ["p-without"]
    assert "no `bet:`" in found[0].message


def test_field_points_into(ws):
    proposition(ws, "p-good", derivation=["[[drafts/gap-argument]]"])
    proposition(ws, "p-bad", derivation=["[[wiki/concepts/gap]]"])

    found = rules.check(loaded(ws), rules.parse([
        {"rule": rules.FIELD_POINTS_INTO, "field": "derivation",
         "directory": "drafts"}]))

    assert [v.slug for v in found] == ["p-bad"]


def test_forbid_transition(ws):
    path = proposition(ws, "p-gap", status="testing")
    threads.set_status(path, "supported", "done", host="claude")
    threads.set_status(path, "refuted", "no", host="claude")

    found = rules.check(loaded(ws), rules.parse([
        {"rule": rules.FORBID_TRANSITION, "kind": "proposition",
         "src": "supported", "dst": "refuted"}]))

    assert [v.slug for v in found] == ["p-gap"]


def test_max_open_per_line(ws):
    threads.create(ws / "threads" / "qec.md", vocab.LINE, "QEC", "Whether.")
    for index in range(3):
        proposition(ws, f"p-{index}", status="testing")

    found = rules.check(loaded(ws), rules.parse([
        {"rule": rules.MAX_OPEN_PER_LINE, "limit": 2}]))

    assert [v.slug for v in found] == ["qec"]
    assert "more than the 2" in found[0].message


def test_leaving_status_requires_post_by(ws):
    path = proposition(ws, "p-gap", status="testing")
    threads.set_status(path, "supported", "done", host="claude")
    threads.set_status(path, "disputed", "VERDICT: refuted", host=vocab.REVIEWER)
    threads.set_status(path, "testing", "back to it", host="claude")

    found = rules.check(loaded(ws), rules.parse([
        {"rule": rules.LEAVING_REQUIRES_POST_BY, "status": "disputed",
         "host": vocab.HUMAN}]))

    assert [v.slug for v in found] == ["p-gap"]


def test_a_signature_added_after_the_flip_counts(ws):
    """The trap. A transition cannot be re-signed once it has happened, and
    the gate's own instruction is to sign a post — which necessarily lands
    after it. With the window closing at the transition, following that
    instruction exactly could never satisfy the rule, and the session became
    permanently unclosable.
    """
    path = proposition(ws, "p-gap", status="testing")
    threads.set_status(path, "supported", "done", host="claude")
    threads.set_status(path, "disputed", "VERDICT: refuted", host=vocab.REVIEWER)
    threads.set_status(path, "testing", "back to it", host="claude")
    rule = rules.parse([{"rule": rules.LEAVING_REQUIRES_POST_BY,
                         "status": "disputed", "host": vocab.HUMAN}])
    assert rules.check(loaded(ws), rule), "the fixture has to start in violation"

    threads.append_post(path, "I looked at it myself — re-running is right.",
                        host=vocab.HUMAN)

    assert rules.check(loaded(ws), rule) == []


def test_leaving_with_the_right_signature_is_fine(ws):
    path = proposition(ws, "p-gap", status="testing")
    threads.set_status(path, "supported", "done", host="claude")
    threads.set_status(path, "disputed", "VERDICT: refuted", host=vocab.REVIEWER)
    threads.set_status(path, "testing", "I say we re-run it", host=vocab.HUMAN)

    assert rules.check(loaded(ws), rules.parse([
        {"rule": rules.LEAVING_REQUIRES_POST_BY, "status": "disputed",
         "host": vocab.HUMAN}])) == []


# --------------------------------------------------------------------------
# where a rule came from
# --------------------------------------------------------------------------

def test_a_violation_can_name_the_proposal_behind_the_rule(ws):
    """A rule nobody can trace is a rule nobody can argue with, and one that
    cannot be argued with cannot be retired either."""
    proposition(ws, "p-gap", status="testing")

    found = rules.check(loaded(ws), rules.parse([
        {"rule": rules.REQUIRE_FIELD, "kind": "proposition", "status": "testing",
         "field": "bet", "from": "r-abc123"}]))

    assert found[0].rule.source == "r-abc123"


def test_a_proposal_that_names_a_predicate_becomes_a_rule():
    class Proposal:
        id = "r-abc"
        patch = {"rule": rules.REQUIRE_FIELD, "kind": "proposition",
                 "status": "testing", "field": "bet"}

    made = rules.from_proposal(Proposal())
    assert made.name == rules.REQUIRE_FIELD and made.source == "r-abc"


def test_prose_is_not_promotable_and_that_is_not_a_failure():
    """Most good advice is prose. The button is simply not available."""
    class Proposal:
        id = "r-abc"
        patch = {}

    assert rules.from_proposal(Proposal()) is None


def test_a_predicate_with_missing_parameters_is_not_promotable():
    class Proposal:
        id = "r-abc"
        patch = {"rule": rules.REQUIRE_FIELD, "kind": "proposition"}

    assert rules.from_proposal(Proposal()) is None


# --------------------------------------------------------------------------
# the rules nobody has to write down
# --------------------------------------------------------------------------

def test_the_builtin_rules_run_in_a_workspace_with_no_config(ws):
    """`BUILTIN_SHAPE` is documented as "rules MAGI enforces for everybody"
    and nothing imported it — `grep` matched its own definition and nothing
    else. So `derivation:` could point anywhere, in every workspace, while
    `rules.py` said everything executable is checked on every run."""
    proposition(ws, "p-good", derivation=["[[drafts/gap-argument]]"])
    proposition(ws, "p-bad", derivation=["[[wiki/concepts/gap]]"])

    found = state.load(ws, now=NOW).violations

    assert [v.slug for v in found] == ["p-bad"]
    assert "not under drafts/" in found[0].message


def test_leaving_conflict_unsigned_is_reported_as_debt_not_as_a_rule(ws):
    """It used to be both, and being both was the bug.

    `state._unrecorded_decisions` has always reported this transition, and it
    accepts *either* remedy the gate offers — a post signed `human`, or the
    decision written into `decisions.md`. Wiring
    `leaving_status_requires_post_by(conflict, human)` into `BUILTIN_SHAPE`
    added a second check that can only see posts, so a person who wrote it in
    `decisions.md` cleared the debt line and was held by the rule line with
    nothing left to try. One check, and the one that honours all the advice.
    """
    path = proposition(ws, "p-gap", status="testing")
    threads.set_status(path, vocab.CONFLICT, "two writers collided", host="magi")
    threads.set_status(path, "testing", "carrying on", host="claude")

    projection = state.load(ws, now=NOW)

    assert projection.violations == [], "the duplicate rule is back"
    assert any("person's call" in item.why for item in projection.debt), \
        "and the check that replaced it is not running"


def test_the_field_rule_is_still_built_in(ws):
    """Removing the duplicate must not take the half that was genuinely dead
    with it: nothing but `BUILTIN_SHAPE` checks where a `derivation:` points."""
    proposition(ws, "p-bad", derivation=["[[wiki/concepts/gap]]"])

    assert [v.slug for v in state.load(ws, now=NOW).violations] == ["p-bad"]


def test_the_builtins_are_added_to_a_persons_rules_not_swapped_for_them(ws):
    """Both, or the fix trades one silent gap for another."""
    import yaml

    proposition(ws, "p-bad", derivation=["[[wiki/concepts/gap]]"])
    proposition(ws, "p-nofield", status="testing")
    (ws / "config.yaml").write_text(yaml.safe_dump({"research": {"rules": [
        {"rule": rules.REQUIRE_FIELD, "kind": "proposition",
         "status": "testing", "field": "bet"}]}}), encoding="utf-8")

    found = {v.slug for v in state.load(ws, now=NOW).violations}

    assert found == {"p-bad", "p-nofield"}
