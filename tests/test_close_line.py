"""`magi close <line>` — and what closing a line actually costs.

A line is a view, not a folder, so closing one moves no files. What it changes
is attention: `state.candidates` skips a closed line outright. That is the
point of closing it, and it is also the danger — every proposition still open
on that line stops being offered, and nothing raises its hand later.

So the command's real work is the survey it runs first. Closing a line with
three open propositions is a decision about those three propositions, and a
person who has not been shown them has not made it. The tests below are mostly
about that: what it refuses, what it says, and what the record keeps when
somebody closes anyway.
"""

import json
import subprocess
import sys

import pytest

from magi import close_cmd, state
from magi.core import vocab
from magi.kb import thread_cmd


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    (tmp_path / "config.md").write_text("# scope\n", encoding="utf-8")
    return tmp_path


def _new(ws, slug, kind, **kw):
    argv = ["new", slug, "--topic-dir", str(ws), "--kind", kind,
            "--title", kw.get("title", slug), "--purpose", "because"]
    for line in kw.get("lines", []):
        argv += ["--line", line]
    assert thread_cmd.main(argv) == 0
    return ws / "threads" / f"{slug}.md"


def _settle(ws, slug, dst):
    assert thread_cmd.main(["status", slug, dst, "--topic-dir", str(ws),
                            "--text", "done", "--host", "claude"]) == 0


# --------------------------------------------------------------------------
# the survey
# --------------------------------------------------------------------------

def test_the_survey_counts_open_work_and_settled_work(ws):
    _new(ws, "l-a", "line")
    _new(ws, "p-open", "proposition", lines=["l-a"])
    _new(ws, "p-done", "proposition", lines=["l-a"])
    _settle(ws, "p-done", "conjectured")
    _settle(ws, "p-done", "testing")
    _settle(ws, "p-done", "supported")
    _new(ws, "p-elsewhere", "proposition", lines=["l-b"])

    found = close_cmd.survey(ws, "l-a")

    assert found["exists"] and found["status"] == "exploring"
    assert [item["slug"] for item in found["open"]] == ["p-open"]
    assert found["settled"] == 1, "a note on another line is not this line's business"


def test_an_unanswered_question_counts_as_open(ws):
    """As forgotten as an untested claim, and just as silent afterwards."""
    _new(ws, "l-a", "line")
    _new(ws, "q-why", "question", lines=["l-a"])

    found = close_cmd.survey(ws, "l-a")

    assert [item["kind"] for item in found["open"]] == [vocab.QUESTION]


def test_a_slug_that_is_not_a_line_is_not_a_line(ws):
    _new(ws, "p-a", "proposition")
    assert close_cmd.survey(ws, "p-a")["exists"] is False
    assert close_cmd.close(ws, "p-a", "why")["ok"] is False


# --------------------------------------------------------------------------
# what it refuses
# --------------------------------------------------------------------------

def test_open_work_stops_the_close_and_names_it(ws):
    _new(ws, "l-a", "line")
    _new(ws, "p-open", "proposition", lines=["l-a"])

    result = close_cmd.close(ws, "l-a", "moved on")

    assert result["ok"] is False
    assert "1 still open" in result["error"]
    said = close_cmd.render(result)
    assert "p-open" in said and "magi thread status p-open" in said
    assert "--anyway" in said, "a refusal has to say how to proceed"
    from magi.kb import threads
    assert threads.read_note(ws / "threads" / "l-a.md").status == "exploring"


def test_a_line_with_nothing_open_closes_without_ceremony(ws):
    _new(ws, "l-a", "line")

    result = close_cmd.close(ws, "l-a", "the question is answered")

    assert result["ok"] and result["changed"]
    from magi.kb import threads
    assert threads.read_note(ws / "threads" / "l-a.md").status == "closed"


def test_closing_a_closed_line_changes_nothing_and_is_not_an_error(ws):
    _new(ws, "l-a", "line")
    close_cmd.close(ws, "l-a", "done")

    again = close_cmd.close(ws, "l-a", "done")

    assert again["ok"] and again["changed"] is False


# --------------------------------------------------------------------------
# closing anyway keeps the record of what was orphaned
# --------------------------------------------------------------------------

def test_closing_anyway_writes_down_what_was_left_open(ws):
    """After this the router never mentions them again, so the post has to."""
    _new(ws, "l-a", "line")
    _new(ws, "p-open", "proposition", lines=["l-a"])
    _new(ws, "q-why", "question", lines=["l-a"])

    result = close_cmd.close(ws, "l-a", "the funding ended", anyway=True)

    assert result["ok"] and result["changed"]
    from magi.kb import threads
    note = threads.read_note(ws / "threads" / "l-a.md")
    assert note.status == "closed"
    posted = note.posts[-1].text
    assert "the funding ended" in posted
    assert "p-open" in posted and "q-why" in posted


def test_the_closing_post_is_signed_as_a_person_s_decision(ws):
    """`line → closed` is human-only in `vocab`. The signature is not a claim
    about who typed — design-v2 §10 has an agent transcribe what a person
    decided — it is what `sync --close` reads to tell a decision that was made
    from one that was assumed."""
    _new(ws, "l-a", "line")
    close_cmd.close(ws, "l-a", "done")

    from magi.kb import threads
    assert threads.read_note(ws / "threads" / "l-a.md").posts[-1].host == vocab.HUMAN


def test_an_agent_signed_close_is_debt_the_gate_reports(ws):
    """The other half of the same rule, and the reason `magi close` exists as
    its own command: the same flip typed through `thread status --host claude`
    lands as bookkeeping debt rather than being refused outright."""
    _new(ws, "l-a", "line")
    assert thread_cmd.main(["status", "l-a", "closed", "--topic-dir", str(ws),
                            "--text", "closing it myself", "--host", "claude"]) == 0

    debts = [item.why for item in state.load(ws).debt]

    assert any("person's call" in why for why in debts), debts


# --------------------------------------------------------------------------
# a closed line stops being offered, which is the whole point and the risk
# --------------------------------------------------------------------------

def test_a_closed_line_is_no_longer_offered_as_work(ws):
    _new(ws, "l-a", "line")
    _new(ws, "p-open", "proposition", lines=["l-a"])
    before = state.candidates(state.load(ws))
    assert any(action.line == "l-a" for action in before)

    close_cmd.close(ws, "l-a", "moved on", anyway=True)

    after = state.candidates(state.load(ws))
    assert not any(action.key == "work" and action.line == "l-a" for action in after)


# --------------------------------------------------------------------------
# the command line
# --------------------------------------------------------------------------

def _run(ws, *args):
    return subprocess.run([sys.executable, "-m", "magi", "close", *args,
                           "--topic-dir", str(ws)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def test_a_dry_run_surveys_without_needing_a_reason(ws):
    """You should be able to look before inventing a justification for a close
    you may not go through with."""
    _new(ws, "l-a", "line")
    _new(ws, "p-open", "proposition", lines=["l-a"])

    done = _run(ws, "l-a", "--dry-run", "--json")

    assert done.returncode == 0
    assert [item["slug"] for item in json.loads(done.stdout)["open"]] == ["p-open"]
    from magi.kb import threads
    assert threads.read_note(ws / "threads" / "l-a.md").status == "exploring"


def test_closing_without_saying_why_is_refused(ws):
    _new(ws, "l-a", "line")

    done = _run(ws, "l-a")

    assert done.returncode == 1
    assert "say why" in done.stderr


def test_the_close_gate_and_the_line_close_are_both_on_the_menu():
    """Two commands share the word "close" and mean different things: one ends
    a session, one ends a research line. They are adjacent in `--help` on
    purpose — a reader meets both descriptions at once rather than finding out
    from the wrong one."""
    done = subprocess.run([sys.executable, "-m", "magi", "--help"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")

    assert "--close to end a session" in done.stdout
    assert "Close a research line" in done.stdout
    assert len(done.stdout.strip().splitlines()) <= 20, "one screen is the ratchet"
