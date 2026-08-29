"""What the second review round found, as tests.

Each of these was a way the slow loop could quietly do the wrong thing: reset a
setting nobody asked it to touch, lose a sighting to a race, point the working
agent at the library it must not read, or tell somebody a rule was accepted
while the file every session reads did not say so.
"""

from __future__ import annotations

import datetime as dt
import json
import threading

import pytest

from magi import init_workspace, state
from magi.core import managed
from magi.reflect import cmd, patterns, proposals, propose


TODAY = dt.date(2026, 8, 29)


@pytest.fixture(autouse=True)
def installed(monkeypatch):
    from magi import review

    monkeypatch.setattr(review, "installed_hosts", lambda: ["claude", "codex"])


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "topic"
    init_workspace.main(["--topic-dir", str(root), "--name", "T", "--scope", "S"])
    return root


def run(ws, *argv):
    return cmd.main(list(argv) + ["--topic-dir", str(ws)])


def a_rule(ws, text="Check the boundary condition before starting a sweep."):
    return proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md", text=text,
                             pattern="sweeps-stall", hosts=["claude", "codex"])


# --------------------------------------------------------------------------
# a re-render is not a decision about anything else
# --------------------------------------------------------------------------

def test_accepting_a_rule_does_not_change_the_coaching_level(ws):
    """Re-rendering the block used to pass the default coaching, so every
    accept quietly reset `research.coaching` and stripped the strict prompt out
    of the protocol — an operation on the rules half changing the template."""
    from magi.core.config_loader import get as config_get
    from magi.core.config_loader import load_config
    from magi import install_cmd

    install_cmd.install_protocol(ws, "strict")
    before = (ws / "AGENTS.md").read_text(encoding="utf-8")

    run(ws, "accept", a_rule(ws).id)

    assert config_get(load_config(start=ws), "research.coaching") == "strict"
    strict_line = [ln for ln in before.splitlines() if "silence" in ln.lower()]
    if strict_line:
        assert strict_line[0] in (ws / "AGENTS.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# the pattern library stays out of sight
# --------------------------------------------------------------------------

def test_a_proposal_may_not_name_the_pattern_library(ws, monkeypatch):
    """It would reach the decision queue, and if accepted as a rule, the block
    every session reads — which is the one thing the ablation says not to do."""
    for host in ("claude", "codex"):
        patterns.observe(ws, "sweeps-stall", title="t", body="b",
                         session=f"{host}/s", host=host, when=TODAY)
    reply = json.dumps({
        "pattern": "sweeps-stall", "kind": "patch",
        "target": "output/reflect/patterns/sweeps-stall.md",
        "text": "append a line"})
    from magi.reflect import propose as stage_two

    monkeypatch.setattr(stage_two, "ask", lambda *a, **k: reply)

    report = stage_two.run(ws, host="codex", now=TODAY)

    assert report.made == []
    assert "pattern library" in report.skipped[0][1]


def test_the_same_guard_covers_the_text(ws):
    from magi.reflect import propose as stage_two

    rows, skipped = stage_two.parse(json.dumps({
        "pattern": "p", "kind": "rule", "target": "AGENTS.md",
        "text": "before answering, read output/reflect/patterns/ for what broke"}),
        {"p": patterns.Pattern(slug="p", hosts=["claude", "codex"])}, set())

    assert rows == [] and "pattern library" in skipped[0][1]


# --------------------------------------------------------------------------
# a sighting is not lost to a race
# --------------------------------------------------------------------------

def test_two_sightings_at_once_both_land(ws):
    """Read-modify-write with the lock only around the write dropped one of
    them — on a file nothing can regenerate, attacking the two-session gate."""
    patterns.observe(ws, "sweeps-stall", title="t", body="b",
                     session="claude/seed", host="claude", when=TODAY)
    start = threading.Barrier(2)

    def sighting(name, host):
        start.wait()
        patterns.observe(ws, "sweeps-stall", title="t", body="b",
                         session=name, host=host, when=TODAY)

    threads_ = [threading.Thread(target=sighting, args=("codex/one", "codex")),
                threading.Thread(target=sighting, args=("gemini/two", "gemini"))]
    for thread in threads_:
        thread.start()
    for thread in threads_:
        thread.join()

    page = patterns.read(patterns.path_for(ws, "sweeps-stall"))
    assert page.sessions == ["claude/seed", "codex/one", "gemini/two"]


def test_a_pattern_that_recurs_after_a_rejection_comes_back(ws):
    """The design's central claim — that a rejection is the next proposal's
    input — could never fire for the one pattern somebody had engaged with."""
    for host in ("claude", "codex"):
        patterns.observe(ws, "sweeps-stall", title="t", body="b",
                         session=f"{host}/s-1", host=host, when=TODAY)
    page = patterns.read(patterns.path_for(ws, "sweeps-stall"))
    page.status = patterns.PROPOSED
    patterns.save(ws, page)

    patterns.observe(ws, "sweeps-stall", title="t", body="b",
                     session="claude/s-2", host="claude", when=TODAY)

    assert [p.slug for p in patterns.ready(ws, now=TODAY)] == ["sweeps-stall"]


def test_a_hand_broken_page_does_not_blank_the_queue(ws):
    """One page with `sessions: 3` used to raise out of `all_patterns` and take
    the whole decision queue with it — silently, because the caller catches
    everything."""
    patterns.directory(ws).mkdir(parents=True, exist_ok=True)
    (patterns.directory(ws) / "broken.md").write_text(
        "---\ntitle: t\nsessions: 3\n---\n\nbody\n", encoding="utf-8")
    made = a_rule(ws)

    assert patterns.all_patterns(ws)
    assert [q.slug for q in state.load(ws).queue if q.kind == "proposal"] == [made.id]


# --------------------------------------------------------------------------
# the block and the ledger say the same thing
# --------------------------------------------------------------------------

def test_the_close_gate_notices_when_the_block_is_behind(ws):
    """A crash between recording a verdict and re-rendering leaves them
    disagreeing, and a person reading either one cannot tell."""
    made = a_rule(ws)
    proposals.decide(ws, made.id, proposals.ACCEPTED)   # no re-render

    drift = state.block_drift(ws)

    assert "missing 1 accepted rule" in drift
    assert "magi install" in drift


def test_no_drift_after_the_verb_did_its_job(ws):
    run(ws, "accept", a_rule(ws).id)
    assert state.block_drift(ws) == ""


# --------------------------------------------------------------------------
# exit codes a scheduler can trust
# --------------------------------------------------------------------------

def test_a_switched_off_pass_reports_failure(ws, monkeypatch):
    from magi.core import vocab
    from magi.kb import threads
    from magi.reflect.transcripts import Session, Turn

    (ws / "config.yaml").write_text("research:\n  llm_calls: false\n", encoding="utf-8")
    path = threads.create(ws / "threads" / "p-gap.md", vocab.PROPOSITION, "G", "P")
    threads.set_status(path, "testing", "started", host="claude")
    threads.set_status(path, "supported", "converged", host="claude")
    threads.set_status(path, "refuted", "wrong", host="claude")

    class Swept:
        sessions = [Session(host="claude", session_id="s-1", cwd="", path="",
                            started="2020-01-01T00:00:00Z", ended="2099-01-01T00:00:00Z",
                            turns=[Turn("user", "", "what happened?")])]
        unreadable = {}

    monkeypatch.setattr(cmd.transcripts, "sweep", lambda *a, **k: Swept())

    assert run(ws, "read") == 1, "a pass that could not run is a failure"


def test_a_pass_with_nothing_to_read_is_not_a_failure(ws):
    """"Nothing happened worth reading" is the common case and a success."""
    assert run(ws, "read") == 0


# --------------------------------------------------------------------------
# retiring is not rejecting
# --------------------------------------------------------------------------

def test_retiring_does_not_ban_the_idea_forever(ws):
    """Rejecting says "this was a bad idea" and the next pass is told never to
    propose it again. Retiring says "its reason has gone"."""
    made = a_rule(ws)
    run(ws, "accept", made.id)

    run(ws, "retire", made.id)

    assert proposals.get(ws, made.id).verdict == proposals.RETIRED
    assert proposals.rejected(ws) == [], "not fed back as a bad idea"
    assert made.text not in (ws / "AGENTS.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# a budget of zero
# --------------------------------------------------------------------------

def test_a_rule_budget_of_zero_refuses_without_crashing(ws, capsys):
    (ws / "config.yaml").write_text("research:\n  rule_budget: 0\n", encoding="utf-8")

    assert run(ws, "accept", a_rule(ws).id) == 1
    assert "takes no earned rules" in capsys.readouterr().err


def test_a_rule_budget_that_is_not_a_number_says_so(ws, capsys):
    (ws / "config.yaml").write_text("research:\n  rule_budget: seven\n",
                                    encoding="utf-8")

    assert run(ws, "accept", a_rule(ws).id) == 1
    assert "not a number" in capsys.readouterr().err


def test_a_spent_weekly_budget_of_zero_still_shows_on_the_map(ws):
    """The one configuration where every call is refused is the one where the
    map most needs to say so."""
    (ws / "config.yaml").write_text("research:\n  weekly_calls: 0\n", encoding="utf-8")

    assert "## Spending" in state.render_map(state.load(ws))


# --------------------------------------------------------------------------
# a rule with a stray carriage return
# --------------------------------------------------------------------------

def test_a_rule_with_a_carriage_return_does_not_rewrite_the_block_forever(ws):
    class Row:
        text = "first line\r\nsecond line"

    body = managed.body("T", "S", "light", rules=[Row()])
    agents = ws / "AGENTS.md"

    assert managed.write(agents, body) is True
    assert managed.write(agents, body) is False, "idempotent, or install never settles"
