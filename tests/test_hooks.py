"""The two hooks beyond the stop gate, and the one rule all three obey.

**A hook must not be able to break a session.** Everything here ends in exit 0
with parseable JSON, including the paths where the workspace is missing, the
payload is not JSON, or the file cannot be written. A hook that errors is a
hook the person turns off, and then the gate it was guarding is gone with it —
which is a worse outcome than every failure it was protecting against.

`fanout` counts sub-agent spawns and blocks none. Invariant 5 asks the agent to
say what a fan-out costs before starting one; counting makes that checkable,
and design-v2 §13 is explicit that MAGI hard-manages only the calls it starts
itself. A sub-agent is the agent's own work on the person's own account.

`session-start` is where background work goes, because §7 says there is no
daemon.
"""

import json
import subprocess
import sys

import pytest

from magi import hook_cmd, install_cmd


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "config.md").write_text("# scope\n", encoding="utf-8")
    return tmp_path


def _spawn(ws, session="s1", tool="Task"):
    return hook_cmd.fanout({"tool_name": tool, "session_id": session}, root=ws)


# --------------------------------------------------------------------------
# counting, never blocking
# --------------------------------------------------------------------------

def test_a_spawn_is_counted_quietly_until_it_is_worth_saying(ws):
    for _ in range(hook_cmd.LOUD_EVERY - 1):
        assert _spawn(ws) == {}, "a hook that speaks every time is a hook people mute"

    assert "sub-agents this session" in _spawn(ws)["systemMessage"]


def test_it_speaks_every_nth_spawn_not_every_spawn_past_the_nth(ws):
    """The first version skipped the first nine and then said the same sentence
    on every single spawn after — twenty spawns, eleven messages. The test above
    guarded the quiet half and the noisy half shipped anyway."""
    spoke = [i for i in range(1, hook_cmd.LOUD_EVERY * 2 + 2) if _spawn(ws)]

    assert spoke == [hook_cmd.LOUD_EVERY, hook_cmd.LOUD_EVERY * 2]


def test_it_does_not_fire_on_a_fan_out_the_skills_would_have_announced(ws):
    """The skills cap a fan-out at ten concurrent and require the agent to say
    the total first. A compile of a dozen sources is normal, announced and
    correct — warning there would be reminding the one workflow that already
    did the thing."""
    assert hook_cmd.LOUD_EVERY > 12

    for _ in range(12):
        assert _spawn(ws) == {}


def test_it_never_blocks_however_many_there_are(ws):
    """design-v2 §13: MAGI hard-manages only the calls it starts itself. A
    sub-agent is the agent's own work on the person's own account, and refusing
    it is not MAGI's decision to make."""
    said = [_spawn(ws) for _ in range(hook_cmd.LOUD_EVERY * 2)][-1]

    for _ in range(hook_cmd.LOUD_EVERY):
        said = _spawn(ws) or said
    assert "decision" not in said and "permissionDecision" not in said
    assert set(said) <= {"systemMessage"}


def test_each_session_counts_on_its_own(ws):
    for _ in range(hook_cmd.LOUD_EVERY + 2):
        _spawn(ws, session="busy")

    assert _spawn(ws, session="fresh") == {}
    assert hook_cmd.spawns(ws, "fresh") == 1


def test_a_tool_that_spawns_nothing_is_not_counted(ws):
    _spawn(ws, tool="Read")
    _spawn(ws, tool="Bash")

    assert hook_cmd.spawns(ws, "s1") == 0


def test_the_count_does_not_go_into_the_call_ledger(ws):
    """`llm-ledger.jsonl` is what MAGI spent, and the weekly budget reads it.
    Mixing in calls MAGI did not make would corrupt the one number that can
    refuse."""
    for _ in range(3):
        _spawn(ws)

    assert (ws / "output" / "fanout.jsonl").is_file()
    assert not (ws / "output" / "llm-ledger.jsonl").exists()


# --------------------------------------------------------------------------
# session start
# --------------------------------------------------------------------------

def test_session_start_says_what_the_workspace_needs(ws):
    from magi.kb import thread_cmd

    thread_cmd.main(["new", "p-a", "--topic-dir", str(ws), "--kind",
                     "proposition", "--title", "A", "--purpose", "because"])

    said = hook_cmd.session_start({}, root=ws)

    context = said["hookSpecificOutput"]["additionalContext"]
    assert "p-a" in context
    assert said["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_a_workspace_with_nothing_to_do_says_nothing(ws):
    assert hook_cmd.session_start({}, root=ws) == {}


# --------------------------------------------------------------------------
# nothing here may break a session
# --------------------------------------------------------------------------

@pytest.mark.parametrize("event", ["fanout", "session-start"])
@pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"tool_name": null}'])
def test_no_payload_can_make_a_hook_fail(event, stdin, ws):
    done = subprocess.run(
        [sys.executable, "-m", "magi", "hook", event, "--topic-dir", str(ws)],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
        errors="replace")

    assert done.returncode == 0, done.stderr
    json.loads(done.stdout)          # the assertion is that this parses


def test_a_hook_outside_a_workspace_is_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(hook_cmd, "find_workspace_root", lambda: None)
    assert hook_cmd.fanout({"tool_name": "Task", "session_id": "s"}) == {}
    assert hook_cmd.session_start({}) == {}


def test_a_count_that_cannot_be_written_still_answers(tmp_path):
    """A workspace whose `output/` is not a directory — a read-only checkout, a
    stray file, a full disk. The count is lost; the session is not."""
    (tmp_path / "threads").mkdir()
    (tmp_path / "output").write_text("not a directory", encoding="utf-8")

    assert hook_cmd.fanout({"tool_name": "Task", "session_id": "s"},
                           root=tmp_path) == {}
    assert hook_cmd.spawns(tmp_path, "s") == 0


# --------------------------------------------------------------------------
# what the installer writes
# --------------------------------------------------------------------------

def test_all_three_hooks_are_installed_for_claude(ws):
    line = install_cmd.install_hook(ws, "claude")

    settings = json.loads((ws / ".claude" / "settings.json").read_text(
        encoding="utf-8"))
    assert set(settings["hooks"]) == set(install_cmd.HOOKS)
    assert "Stop" in line and "PreToolUse" in line and "SessionStart" in line


def test_the_fanout_hook_matches_every_tool_the_counter_counts(ws):
    """It matched `Task` alone while `hook_cmd.SPAWNING` counts `Agent` and
    `Dispatch` too, so the hook never saw two thirds of what its own message
    claims to be counting. Still not a bare matcher: a `PreToolUse` hook that
    matches everything runs on every file read."""
    from magi import hook_cmd

    install_cmd.install_hook(ws, "claude")

    settings = json.loads((ws / ".claude" / "settings.json").read_text(
        encoding="utf-8"))
    matcher = settings["hooks"]["PreToolUse"][0]["matcher"]
    assert set(matcher.split("|")) == set(hook_cmd.SPAWNING)
    assert matcher, "an empty matcher would fire on every tool call"


def test_installing_twice_adds_nothing(ws):
    install_cmd.install_hook(ws, "claude")
    first = json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))

    line = install_cmd.install_hook(ws, "claude")

    again = json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert again == first
    assert "already installed" in line


def test_somebody_else_s_hook_on_the_same_event_is_left_alone(ws):
    """A person's own hook and ours are not in competition, and dropping theirs
    to install ours is the kind of helpfulness nobody asks for twice."""
    theirs = {"matcher": "", "hooks": [{"type": "command", "command": "notify-me"}]}
    (ws / ".claude").mkdir()
    (ws / ".claude" / "settings.json").write_text(
        json.dumps({"hooks": {"SessionStart": [theirs]}}), encoding="utf-8")

    install_cmd.install_hook(ws, "claude")

    settings = json.loads((ws / ".claude" / "settings.json").read_text(
        encoding="utf-8"))
    assert theirs in settings["hooks"]["SessionStart"]
    assert len(settings["hooks"]["SessionStart"]) == 2


def test_a_host_with_no_documented_hooks_is_told_so_plainly(ws):
    """opencode, not codex — codex grew hooks and MAGI writes them now."""
    line = install_cmd.install_hook(ws, "opencode")
    assert "no declarative hooks" in line
    assert not (ws / ".opencode").exists()


def test_the_count_is_derived_and_ignored(tmp_path):
    """Append-only and not recomputable, so it looks transactional — but the
    question this classification answers is what deleting it costs, and the
    answer is nothing: it nags once, inside the session it is counting.
    Unclassified it would come back `unknown`, which is the grey area that made
    "delete output/ and re-run" unsafe advice once already."""
    import subprocess as sp

    from magi import init_workspace
    from magi.core import durability

    assert durability.classify("output/fanout.jsonl") == "derived"

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    sp.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    done = sp.run(["git", "-C", str(tmp_path), "check-ignore", "-q",
                   "output/fanout.jsonl"], capture_output=True)

    assert done.returncode == 0, "a per-session counter in git is a merge conflict"


def test_the_fanout_log_does_not_grow_without_end(tmp_path):
    """`output/fanout.jsonl` is DERIVED — it answers "how many so far this
    session" and nothing reconstructs anything from it — and every spawn reads
    the whole file. Left unpruned that is a hook that gets slower for the life
    of the workspace."""
    import datetime as dt
    import json

    from magi import hook_cmd

    path = tmp_path / "output" / "fanout.jsonl"
    path.parent.mkdir(parents=True)
    stale = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat(
        timespec="seconds")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for index in range(hook_cmd.PRUNE_AT + 10):
            handle.write(json.dumps({"at": stale, "session": f"old-{index}",
                                     "tool": "Task"}) + "\n")

    count = hook_cmd.note_spawn(tmp_path, "now", "Task")

    assert count == 1, "this session has spawned once"
    assert len(hook_cmd._rows(path)) == 1, "and the month-old rows are gone"


def test_a_row_it_cannot_date_is_kept(tmp_path):
    """Dropping what cannot be dated would quietly lose a live session."""
    import json

    from magi import hook_cmd

    path = tmp_path / "output" / "fanout.jsonl"
    path.parent.mkdir(parents=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for index in range(hook_cmd.PRUNE_AT + 5):
            handle.write(json.dumps({"at": "not a date", "session": "live",
                                     "tool": "Task"}) + "\n")

    hook_cmd.note_spawn(tmp_path, "live", "Task")

    assert hook_cmd.spawns(tmp_path, "live") == hook_cmd.PRUNE_AT + 6


def test_a_recent_row_survives_a_prune(tmp_path):
    import json

    from magi import hook_cmd

    path = tmp_path / "output" / "fanout.jsonl"
    path.parent.mkdir(parents=True)
    hook_cmd.note_spawn(tmp_path, "live", "Task")
    for _ in range(3):
        hook_cmd.note_spawn(tmp_path, "live", "Agent")

    assert hook_cmd.spawns(tmp_path, "live") == 4


# --------------------------------------------------------------------------
# what the last session left behind, said at the start of the next one
# --------------------------------------------------------------------------

def test_session_start_says_what_was_left_in_flight(ws):
    """It was computed only by `sync --close`, which is the wrong end.

    "What you are leaving behind" got said on the way out; "what you are about
    to walk into" was said to nobody. The information existed and was already
    derived from files — it just never reached the moment it was for.
    """
    (ws / "inbox").mkdir(exist_ok=True)
    (ws / "inbox" / "paper.md").write_text("x", encoding="utf-8")

    said = hook_cmd.session_start({}, root=ws)

    context = said["hookSpecificOutput"]["additionalContext"]
    assert "Left in flight" in context
    assert "paper.md" in context


def test_a_quiet_workspace_still_says_nothing(ws):
    """A hook that speaks every time teaches people to skip it, so the extra
    sections must not turn silence into noise."""
    assert hook_cmd.session_start({}, root=ws) == {}


def test_both_halves_arrive_together(ws):
    from magi.kb import thread_cmd

    thread_cmd.main(["new", "p-a", "--topic-dir", str(ws), "--kind",
                     "proposition", "--title", "A", "--purpose", "because"])
    (ws / "inbox").mkdir(exist_ok=True)
    (ws / "inbox" / "paper.md").write_text("x", encoding="utf-8")

    context = hook_cmd.session_start({}, root=ws)["hookSpecificOutput"]["additionalContext"]

    assert "what this project needs" in context
    assert "Left in flight" in context


def test_a_broken_helper_cannot_take_the_session_down(ws, monkeypatch):
    """Every path in this module ends in exit 0 with parseable JSON. Two new
    sections are two new ways to raise inside a hook."""
    from magi import state as state_mod

    monkeypatch.setattr(state_mod, "handoff_lines",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    (ws / "inbox").mkdir(exist_ok=True)
    (ws / "inbox" / "paper.md").write_text("x", encoding="utf-8")

    assert hook_cmd.session_start({}, root=ws) == {}


def test_the_refusal_is_spelled_the_way_each_host_reads_it(ws):
    """Antigravity blocks a stop with `decision: continue`; Claude Code and
    Codex say `block`. Its own bundled docs add that any other value lets the
    agent stop — so sending ours would install a gate that never refuses."""
    from magi import state as state_mod

    report = state_mod.CloseReport()
    report.blocking = [state_mod.DebtItem(slug="p-x", why="no post explains it")]

    assert state_mod.hook_payload(report)["decision"] == "block"
    assert state_mod.hook_payload(report, "antigravity")["decision"] == "continue"
    assert "p-x" in state_mod.hook_payload(report, "antigravity")["reason"]


def test_a_clean_report_says_nothing_in_either_dialect(ws):
    from magi import state as state_mod

    clean = state_mod.CloseReport()
    assert state_mod.hook_payload(clean) == {}
    assert state_mod.hook_payload(clean, "antigravity") == {}
