"""From patterns that recurred to proposals a person can weigh.

Almost every test here is about a restraint, because a loop that can propose
freely will propose constantly and then nobody reads any of it.

**Two independent sessions, or nothing.** One bad afternoon is not evidence.

**Where a fix may land depends on where the problem was seen.** A pattern that
showed up on one host is that host's problem; putting its workaround in the
shared protocol makes the other three read it every session for nothing.

**What was rejected comes back in full.** Being told no is the one place a
person said what they actually want, and a loop that forgets it proposes the
same thing every week.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from magi.core import ledger
from magi.reflect import patterns, proposals, propose


#: Captured at import, before the autouse fixture below swaps it out.
from magi import review as _review
_REAL_INSTALLED = _review.installed_hosts

TODAY = dt.date(2026, 8, 29)


@pytest.fixture(autouse=True)
def installed(monkeypatch):
    from magi import review

    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["claude", "codex"])


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "topic"
    (root / "threads").mkdir(parents=True)
    (root / "output").mkdir(parents=True)
    (root / "config.yaml").write_text("research:\n  weekly_calls: 10\n",
                                      encoding="utf-8")
    return root


def recurring(ws, slug="sweeps-stall", hosts=("claude", "codex")):
    """A pattern that has passed the two-session gate."""
    for index, host in enumerate(hosts):
        patterns.observe(ws, slug, title="Sweeps start before the boundary is checked",
                         body="## What happened\n\nIt stalled.\n\n> the boundary "
                              "condition was wrong",
                         session=f"{host}/s-{index}", host=host, when=TODAY)
    return patterns.read(patterns.path_for(ws, slug))


def answering(text):
    def reply(*args, **kwargs):
        return text
    return reply


def a_row(**kw):
    row = {"pattern": "sweeps-stall", "kind": "rule", "target": "AGENTS.md",
           "text": "Check the boundary condition before starting a sweep.",
           "evidence": ["> the boundary condition was wrong"]}
    row.update(kw)
    return json.dumps(row, ensure_ascii=False)


# --------------------------------------------------------------------------
# what earns a proposal
# --------------------------------------------------------------------------

def test_one_sighting_earns_nothing(ws, monkeypatch):
    patterns.observe(ws, "sweeps-stall", title="t", body="b",
                     session="claude/s-1", host="claude", when=TODAY)
    called = []
    monkeypatch.setattr(propose, "ask", lambda *a, **k: called.append(1) or "",
                        raising=False)

    report = propose.run(ws, host="codex", now=TODAY)

    assert not called and report.made == []
    assert "two independent sessions" in report.note


def test_a_pattern_seen_twice_becomes_a_proposal(ws, monkeypatch):
    recurring(ws)
    monkeypatch.setattr("magi.reflect.propose.ask", answering(a_row()))

    report = propose.run(ws, host="codex", now=TODAY)

    assert len(report.made) == 1
    made = proposals.get(ws, report.made[0])
    assert made.kind == proposals.RULE
    assert made.pattern == "sweeps-stall"
    assert made.hosts == ["claude", "codex"]
    assert made.open, "nobody has decided anything"


def test_the_observation_is_marked_as_acted_on(ws, monkeypatch):
    """It stays on disk: an accepted rule has to point at what produced it."""
    recurring(ws)
    monkeypatch.setattr("magi.reflect.propose.ask", answering(a_row()))

    propose.run(ws, host="codex", now=TODAY)

    page = patterns.read(patterns.path_for(ws, "sweeps-stall"))
    assert page.status == patterns.PROPOSED
    assert patterns.ready(ws, now=TODAY) == [], "and it does not come round again"


def test_and_it_is_marked_through_the_locked_path(ws, monkeypatch):
    """`read()` then `save()` reads outside the lock that `save()` takes, so a
    sighting landing in between is overwritten by the stale copy — the failure
    `patterns.observe` documents and guards against on the same file, which
    `durability` classifies ORIGINAL.

    Shaped as a ban on `save` rather than as the race itself, deliberately.
    Single-threaded, the two implementations are indistinguishable: they
    differ only when another writer lands between the read and the write, and
    the only seam between those two statements in the old code *is* the call
    to `save`. So what this pins is the call site — that `propose` no longer
    writes a pattern page through the unlocked pair — while the tests on
    `patterns.mark` in `test_guarantees_the_docstrings_make.py` cover the
    re-read under the lock.
    """
    recurring(ws)
    monkeypatch.setattr("magi.reflect.propose.ask", answering(a_row()))
    monkeypatch.setattr(patterns, "save", lambda *a, **k: pytest.fail(
        "propose wrote a pattern page through the unlocked read+save pair"))

    report = propose.run(ws, host="codex", now=TODAY)

    assert len(report.made) == 1
    assert patterns.read(patterns.path_for(ws, "sweeps-stall")).status == patterns.PROPOSED


# --------------------------------------------------------------------------
# where a fix may go
# --------------------------------------------------------------------------

def test_one_host_cannot_write_a_rule_for_everybody(ws, monkeypatch):
    """A workaround for one CLI in the shared layer makes every other host
    read it every session for nothing."""
    recurring(ws, hosts=("claude", "claude"))
    page = patterns.read(patterns.path_for(ws, "sweeps-stall"))
    page.sessions = ["claude/s-0", "claude/s-1"]
    page.hosts = ["claude"]
    patterns.save(ws, page)
    monkeypatch.setattr("magi.reflect.propose.ask", answering(a_row()))

    report = propose.run(ws, host="codex", now=TODAY)

    assert report.made == []
    assert "claude only" in report.skipped[0][1]


def test_one_host_may_still_change_its_own_configuration(ws, monkeypatch):
    recurring(ws, hosts=("claude", "claude"))
    page = patterns.read(patterns.path_for(ws, "sweeps-stall"))
    page.sessions, page.hosts = ["claude/s-0", "claude/s-1"], ["claude"]
    patterns.save(ws, page)
    monkeypatch.setattr("magi.reflect.propose.ask", answering(
        a_row(kind="patch", target=".claude/settings.json")))

    report = propose.run(ws, host="codex", now=TODAY)
    assert len(report.made) == 1


# --------------------------------------------------------------------------
# what it may not do
# --------------------------------------------------------------------------

def test_a_proposal_about_nothing_we_showed_it_is_dropped(ws, monkeypatch):
    recurring(ws)
    monkeypatch.setattr("magi.reflect.propose.ask",
                        answering(a_row(pattern="something-else")))

    report = propose.run(ws, host="codex", now=TODAY)
    assert report.made == [] and "cites no observation" in report.skipped[0][1]


def test_the_same_change_is_not_proposed_twice(ws, monkeypatch):
    recurring(ws)
    proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                      text="Check the boundary condition before starting a sweep.",
                      pattern="sweeps-stall")
    monkeypatch.setattr("magi.reflect.propose.ask", answering(a_row()))

    report = propose.run(ws, host="codex", now=TODAY)
    assert report.made == [] and "proposed before" in report.skipped[0][1]


def test_five_is_the_most_a_person_is_asked_to_weigh(ws, monkeypatch):
    for index in range(8):
        recurring(ws, slug=f"pattern-{index}")
    rows = "\n".join(a_row(pattern=f"pattern-{index}", text=f"rule {index}")
                     for index in range(8))
    monkeypatch.setattr("magi.reflect.propose.ask", answering(rows))

    report = propose.run(ws, host="codex", now=TODAY)
    assert len(report.made) == propose.MAX_PROPOSALS


def test_what_was_turned_down_goes_back_into_the_prompt(ws):
    """The one place a person said what they actually want."""
    recurring(ws)
    made = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Never run a sweep after 5pm.", pattern="sweeps-stall")
    proposals.decide(ws, made.id, proposals.REJECTED, note="that is not the problem")

    prompt = propose.build_prompt(patterns.ready(ws, now=TODAY),
                                  proposals.rejected(ws))

    assert "Never run a sweep after 5pm." in prompt
    assert "that is not the problem" in prompt


# --------------------------------------------------------------------------
# cost
# --------------------------------------------------------------------------

def test_over_budget_nothing_is_proposed(ws, monkeypatch):
    recurring(ws)
    (ws / "config.yaml").write_text("research:\n  weekly_calls: 1\n", encoding="utf-8")
    ledger.record(ws, ledger.REFLECT, "codex")
    called = []
    monkeypatch.setattr("magi.reflect.propose.ask",
                        lambda *a, **k: called.append(1) or "")

    report = propose.run(ws, host="codex", now=TODAY)
    assert not called and "budget" in report.note


def test_a_pass_that_could_not_run_proposes_nothing(ws, monkeypatch):
    recurring(ws)

    def boom(*args, **kwargs):
        raise RuntimeError("codex exited 127")

    monkeypatch.setattr("magi.reflect.propose.ask", boom)

    report = propose.run(ws, host="codex", now=TODAY)

    assert report.made == [] and "could not run" in report.note
    assert proposals.all_proposals(ws) == []
    assert ledger.entries(ws)[-1]["ok"] is False


def test_a_dry_run_costs_nothing(ws, monkeypatch):
    recurring(ws)
    called = []
    monkeypatch.setattr("magi.reflect.propose.ask",
                        lambda *a, **k: called.append(1) or "")

    report = propose.run(ws, host="codex", dry_run=True, now=TODAY)

    assert not called and "would ask codex" in report.note
    assert ledger.entries(ws) == []


def test_ctrl_c_during_the_proposal_call_is_not_swallowed(ws, monkeypatch):
    """Same shape as `reflect`, same fix: a 900-second subprocess behind
    `except BaseException` with no re-raise absorbs the interrupt, records a
    failed call and hands back a report. `review.review` has always re-raised.
    """
    from magi.core import ledger

    recurring(ws)

    def interrupted(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr("magi.reflect.propose.ask", interrupted)

    with pytest.raises(KeyboardInterrupt):
        propose.run(ws, host="codex", now=TODAY)

    assert ledger.entries(ws)[-1]["ok"] is False, "and the spend is still recorded"


def test_a_host_the_workspace_declares_reaches_the_thinking_stage(ws, monkeypatch):
    """`research.hosts` names a CLI the shipped table does not carry. The
    proposing stage looked up who was installed without saying which workspace
    was asking, so a declared CLI was invisible and `--host` naming it was
    rejected before it was looked up.

    Runs the real host table: the stub the rest of this file uses takes
    `*_a, **_k` and so cannot tell a caller that passes the config from one
    that does not.
    """
    import shutil

    recurring(ws)
    (ws / "config.yaml").write_text(
        "research:\n"
        "  weekly_calls: 10\n"
        "  hosts:\n"
        "    - key: mycli\n"
        "      bin: mycli-wrapper\n"
        "      argv: ['-p']\n"
        "      reader: true\n", encoding="utf-8")

    monkeypatch.setattr(_review, "installed_hosts", _REAL_INSTALLED)
    monkeypatch.setattr(shutil, "which",
                        lambda name, *a, **k: ("/fake/mycli-wrapper"
                                               if name == "mycli-wrapper" else None))

    report = propose.run(ws, dry_run=True, now=TODAY)

    assert report.host == "mycli", (
        "a CLI the workspace declares is a host like any other; the stage "
        f"chose {report.host!r} instead. note: {report.note!r}")


def test_a_duplicate_filed_during_the_model_call_is_skipped_not_crashed(ws, monkeypatch):
    """The race the re-read exists for, which had never been exercised.

    `parse()` checks against the proposals that existed before the call, and
    the model can take a quarter of an hour, so the code re-reads afterwards.
    That second branch did `skipped += 1` on the list `parse()` returned —
    `TypeError: 'int' object is not iterable` — so the one path written to
    survive a concurrent run was the one that took the run down.

    Simulated by answering the first read empty and the second with the row's
    own fingerprint, which is exactly what a second run filing it mid-call
    would produce.
    """
    recurring(ws)
    monkeypatch.setattr("magi.reflect.propose.ask", answering(a_row()))

    calls = {"n": 0}
    real = proposals.already_proposed

    def racing(root):
        calls["n"] += 1
        if calls["n"] == 1:
            return real(root)          # parse() sees nothing yet
        return {proposals.fingerprint(
            proposals.RULE, "AGENTS.md",
            "Check the boundary condition before starting a sweep.")}

    monkeypatch.setattr("magi.reflect.propose.proposals.already_proposed", racing)

    report = propose.run(ws, host="codex", now=TODAY)

    assert report.made == [], "the duplicate was filed anyway"
    assert report.skipped, "the skip was not recorded"
    assert "proposed before" in report.skipped[-1][1]
