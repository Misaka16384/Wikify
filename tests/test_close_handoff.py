"""What `magi sync --close` says to whoever is here next.

The close gate reports what *this* session owes. This is the other half: work
left mid-flight that somebody opening the project in ten minutes would find
half-done with no way to ask about it — a batch queued and not run, a radar
report opened and not decided, changes not committed.

Every line is a query over state that already exists. Nothing is stored, and
that is the binding constraint rather than a preference: v2 retired `log.md`
because "writing the same events to a second place is how the two start
disagreeing" (`init_workspace.py`, `ingest/pipeline.py`). A handoff file kept
beside `threads/` would be that second place, so the handoff is computed at
render time and never written.

It also never blocks. The gate refuses on bookkeeping debt — work that
happened and was not written down. A queued batch is not debt; it is a session
that stopped somewhere reasonable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from magi import state


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)


def _commit_everything(root: Path) -> None:
    _git(root, "add", "-A")
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "base"], cwd=root, capture_output=True,
                   check=False)


@pytest.fixture
def project(tmp_path):
    from magi import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    return tmp_path


def _lines(root: Path) -> str:
    return "\n".join(state.handoff_lines(root))


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------

def test_a_folder_that_is_not_a_repo_says_nothing_about_commits(project):
    assert "uncommitted" not in _lines(project)


def test_a_repo_with_no_commits_yet_is_not_work_in_flight(project):
    """Everything in a fresh project is untracked, scaffold included. Reporting
    "12 uncommitted changes" at a project's first close is the same noise as
    firing on a fresh checkout, wearing a different hat."""
    _git(project, "init", "-q")
    assert "uncommitted" not in _lines(project)


def test_a_change_made_after_a_commit_is_named(project):
    """A tracked file edited since the last commit — the shape the real case
    had: work finished, sitting uncommitted, with the reason for that living
    only in somebody's chat window."""
    _git(project, "init", "-q")
    _commit_everything(project)
    (project / "config.md").write_text("edited\n", encoding="utf-8")

    got = _lines(project)
    assert "1 uncommitted change(s)" in got
    assert "config.md" in got


def test_a_wholly_untracked_directory_is_reported_as_the_directory(project):
    """git's porcelain collapses it, and that is the better line: a new
    `drafts/` with forty files in it should read as one thing, not forty."""
    _git(project, "init", "-q")
    _commit_everything(project)
    (project / "drafts" / "a.md").write_text("x", encoding="utf-8")
    (project / "drafts" / "b.md").write_text("x", encoding="utf-8")

    got = _lines(project)
    assert "drafts/" in got
    assert "a.md" not in got


# --------------------------------------------------------------------------
# inbox
# --------------------------------------------------------------------------

def test_sources_waiting_in_the_inbox_are_named(project):
    (project / "inbox" / "paper.md").write_text("x", encoding="utf-8")
    got = _lines(project)
    assert "1 file(s) waiting in inbox/" in got
    assert "paper.md" in got


def test_the_inbox_furniture_is_not_a_waiting_source(project):
    """`notes.md` and `_index.md` live in inbox/ permanently. Counting them
    would make every project report a full inbox forever."""
    from magi.core.workspace import INBOX_NON_SOURCES

    for name in INBOX_NON_SOURCES:
        (project / "inbox" / name).write_text("x", encoding="utf-8")
    assert "inbox/" not in _lines(project)


# --------------------------------------------------------------------------
# the contract around it
# --------------------------------------------------------------------------

def test_a_quiet_project_hands_over_nothing(project):
    assert state.handoff_lines(project) == []


def test_close_puts_the_handoff_on_the_report(project):
    """Through `close()`, not by calling the helper.

    The helper being right proves nothing about whether the gate calls it —
    delete the one line in `close()` and a test that only exercises
    `handoff_lines` stays green. design-v2 §4: the check belongs at the layer
    that can be wrong.
    """
    (project / "inbox" / "paper.md").write_text("x", encoding="utf-8")

    report = state.close(project, write=False)
    assert any("inbox/" in line for line in report.handoff)


def test_work_left_in_flight_does_not_refuse_the_session(project):
    """A queued batch is not debt. A gate that refused it is one people turn
    off, and then it enforces nothing at all."""
    (project / "inbox" / "paper.md").write_text("x", encoding="utf-8")

    report = state.close(project, write=False)
    assert report.handoff, "the fixture has something in flight"
    assert report.ok, "in-flight work must not block a close"


def test_the_render_says_who_it_is_for(project):
    (project / "inbox" / "paper.md").write_text("x", encoding="utf-8")

    text = state.render_close(state.close(project, write=False))
    assert "for whoever is here next" in text
    assert "paper.md" in text


def test_nothing_is_written_to_record_the_handoff(project):
    """The constraint that shaped this: no second place for the same events."""
    (project / "inbox" / "paper.md").write_text("x", encoding="utf-8")
    before = {p: p.stat().st_mtime_ns for p in project.rglob("*") if p.is_file()}

    state.close(project, write=False)

    after = {p: p.stat().st_mtime_ns for p in project.rglob("*") if p.is_file()}
    assert after == before, "close(write=False) wrote something"


def test_a_non_ascii_filename_reads_as_itself(project):
    r"""git escapes non-ASCII bytes as octal unless told not to.

    These projects live under `D:\文档\`, so the default would have printed
    `\344\270\255\346\226\207.md` in the one line whose whole job is to tell a
    person which file is unfinished. Raw docstring on purpose: without the `r`
    those escapes are real bytes, which is its own bug and one this repo has
    already had once.
    """
    _git(project, "init", "-q")
    _commit_everything(project)
    (project / "wiki" / "中文笔记.md").write_text("x", encoding="utf-8")

    got = _lines(project)
    assert "中文笔记.md" in got
    assert "\344" not in got
