"""Listing and acting on tasks.

The panel used to show four counts over a store shared by every topic under
the hub, so "17 ready" was a number the reader could neither open nor
attribute. Every issue MAGI opens carries a `topic:<workspace>` label, and
that label is the whole reason one shared store can answer per library.

These tests build their own beads store in a temp directory. None of them go
anywhere near a real one.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from magi import pm

pytestmark = pytest.mark.skipif(shutil.which("bd") is None,
                                reason="bd (the task engine) is not installed")


def _bd(args, cwd):
    return subprocess.run(["bd", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=60, encoding="utf-8",
                          errors="replace")


@pytest.fixture
def hub(tmp_path):
    """A hub with two topics under it, sharing one task store.

    Two on purpose: the bug being pinned here is a store that answers for
    every topic at once, and you cannot see that with only one.
    """
    root = tmp_path / "hub"
    for topic in ("alpha", "beta"):
        ws = root / "topics" / topic
        (ws / "wiki").mkdir(parents=True)
        (ws / "config.yaml").write_text(f"name: {topic}\n", encoding="utf-8")
        (ws / "log.md").write_text("# log\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=root, capture_output=True)
    init = _bd(["init"], root)
    if init.returncode != 0:
        pytest.skip(f"bd init failed here: {init.stderr[-200:]}")
    return root


def _make(hub, topic, title, **kw):
    res = _bd(["create", "-t", "task", f"[{topic}] {title}",
               "--label", f"topic:{topic}", "-d", kw.get("desc", "d")], hub)
    assert res.returncode == 0, res.stderr
    return res


# --------------------------------------------------------------------------
# scoping — the point of the whole thing
# --------------------------------------------------------------------------

def test_a_workspace_sees_only_its_own_tasks(hub):
    _make(hub, "alpha", "one")
    _make(hub, "alpha", "two")
    _make(hub, "beta", "three")

    alpha = pm.list_tasks(hub / "topics" / "alpha")
    beta = pm.list_tasks(hub / "topics" / "beta")

    assert len(alpha) == 2
    assert len(beta) == 1
    assert {t["title"] for t in alpha} == {"one", "two"}
    assert all(t["is_here"] for t in alpha)


def test_hub_scope_returns_every_topic_and_says_which_is_which(hub):
    _make(hub, "alpha", "one")
    _make(hub, "beta", "three")

    rows = pm.list_tasks(hub / "topics" / "alpha", scope="hub")
    assert len(rows) == 2
    here = {t["title"] for t in rows if t["is_here"]}
    away = {t["title"] for t in rows if not t["is_here"]}
    assert here == {"one"} and away == {"three"}


def test_the_topic_prefix_is_stripped_from_the_title(hub):
    """The store is shared, so a terminal listing needs `[topic]` in the
    title to say which library an issue belongs to. On a panel already
    filtered to that library it is noise repeated on every row."""
    _make(hub, "alpha", "Compile raw source: foo.md")
    row = pm.list_tasks(hub / "topics" / "alpha")[0]
    assert row["title"] == "Compile raw source: foo.md"
    assert row["topic"] == "alpha"


def test_no_store_reads_as_none_not_as_zero(tmp_path):
    """A workspace with no task store has not got zero tasks — it has no
    answer, and the panel renders those two states differently."""
    ws = tmp_path / "lonely"
    (ws / "wiki").mkdir(parents=True)
    (ws / "config.yaml").write_text("name: lonely\n", encoding="utf-8")
    assert pm.list_tasks(ws) is None


# --------------------------------------------------------------------------
# acting
# --------------------------------------------------------------------------

def _status(hub, topic, task_id):
    rows = pm.list_tasks(hub / "topics" / topic, include_closed=True)
    return next(r["status"] for r in rows if r["id"] == task_id)


def test_start_close_reopen_round_trip(hub):
    _make(hub, "alpha", "one")
    ws = hub / "topics" / "alpha"
    tid = pm.list_tasks(ws)[0]["id"]

    assert pm.act_on_task(ws, tid, "start")[0]
    assert _status(hub, "alpha", tid) == "in_progress"

    assert pm.act_on_task(ws, tid, "close")[0]
    assert _status(hub, "alpha", tid) == "closed"

    assert pm.act_on_task(ws, tid, "reopen")[0]
    assert _status(hub, "alpha", tid) == "open"


def test_closed_tasks_are_hidden_unless_asked_for(hub):
    _make(hub, "alpha", "one")
    ws = hub / "topics" / "alpha"
    tid = pm.list_tasks(ws)[0]["id"]
    pm.act_on_task(ws, tid, "close")

    assert pm.list_tasks(ws) == []
    assert len(pm.list_tasks(ws, include_closed=True)) == 1


def test_only_whitelisted_actions_run(hub):
    """The action name arrives off the wire from a browser, so the set of
    things it can name is closed — the same guarantee the ops table gives."""
    _make(hub, "alpha", "one")
    ws = hub / "topics" / "alpha"
    tid = pm.list_tasks(ws)[0]["id"]

    for bogus in ("delete", "rm -rf", "update --status closed", ""):
        ok, msg = pm.act_on_task(ws, tid, bogus)
        assert not ok
        assert "unknown action" in msg
    # And nothing happened to the issue.
    assert _status(hub, "alpha", tid) == "open"


def test_acting_without_a_store_fails_cleanly(tmp_path):
    ws = tmp_path / "lonely"
    ws.mkdir()
    ok, msg = pm.act_on_task(ws, "whatever-1", "close")
    assert not ok and "no task store" in msg


# --------------------------------------------------------------------------
# the endpoint
# --------------------------------------------------------------------------

def test_the_endpoint_reports_both_here_and_elsewhere(hub, monkeypatch, tmp_path):
    """"0 here" is only informative next to "2 under the hub" — on its own an
    empty panel looks like a broken one."""
    from fastapi.testclient import TestClient

    from magi.ui.api import create_app

    _make(hub, "beta", "three")
    _make(hub, "beta", "four")

    home = tmp_path / "cfg"
    home.mkdir()
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(home))
    client = TestClient(create_app())

    data = client.get("/api/workspace/tasks",
                      params={"workspace": str(hub / "topics" / "alpha")}).json()
    assert data["here"] == 0
    assert data["elsewhere"] == 2
    assert data["tasks"] == []
    assert data["store_root"] == str(hub)


def test_the_endpoint_refuses_an_unknown_action(hub, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from magi.ui.api import create_app

    _make(hub, "alpha", "one")
    home = tmp_path / "cfg"
    home.mkdir()
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(home))
    client = TestClient(create_app())

    ws = str(hub / "topics" / "alpha")
    tid = pm.list_tasks(hub / "topics" / "alpha")[0]["id"]
    res = client.post("/api/workspace/tasks/act",
                      json={"task_id": tid, "action": "nuke", "workspace": ws})
    assert res.status_code == 400


def test_the_counts_the_panel_shows_come_from_the_rows_it_lists():
    """app.js derives the four metrics from the same array it renders.

    They used to come from `bd status`, which answers for the whole hub while
    the list is filtered to one workspace — so a workspace owning none of them
    displayed READY 17 above an empty list.
    """
    from pathlib import Path

    app_js = (Path(__file__).resolve().parents[1]
              / "src" / "magi" / "ui" / "static" / "app.js").read_text(encoding="utf-8")
    assert "setTaskCounts(countTasks(data.tasks))" in app_js, (
        "the counts are no longer derived from the listed rows"
    )
