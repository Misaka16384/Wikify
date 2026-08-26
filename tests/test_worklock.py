"""The lock that stops two processes rewriting one wiki at the same time.

The WebUI's gate is a dict in one process. It cannot see a `magi lint --fix`
somebody ran by hand — which is the obvious thing to try, since the dashboard
prints the CLI command beside every button it offers.

The two ways a lock like this goes wrong are both worse than the race it
prevents: deadlocking a command against itself, and blocking forever with no
explanation. Most of this file is about those.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

from magi.core.worklock import ENV_HELD, LOCK_NAME, WorkspaceBusy, workspace_lock


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "output").mkdir()
    return tmp_path


# --------------------------------------------------------------------------
# it locks
# --------------------------------------------------------------------------

def test_it_takes_the_lock(ws):
    with workspace_lock(ws, "lint --fix") as took:
        assert took is True
        assert (ws / "output" / LOCK_NAME).exists()


def test_two_workspaces_do_not_block_each_other(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for p in (a, b):
        (p / "output").mkdir(parents=True)

    with workspace_lock(a, "lint --fix"):
        # `magi each` runs a command in every topic of a hub; a lock keyed on
        # the wrong thing would serialise the whole hub.
        with workspace_lock(b, "lint --fix") as took:
            assert took is True


# --------------------------------------------------------------------------
# re-entrancy — the half that deadlocks if it is wrong
# --------------------------------------------------------------------------

def test_the_same_workspace_twice_in_one_chain_does_not_deadlock(ws):
    """`magi link` shells out to `magi wiki refactor-concept`, and
    `batch-commit -> finalize -> lint --fix` is three processes deep. A file
    lock is held by a handle, not a process tree, so without a handoff the
    command waits on itself."""
    with workspace_lock(ws, "link") as outer:
        assert outer is True
        with workspace_lock(ws, "wiki refactor-concept") as inner:
            assert inner is False, "the child acquired a second time"


def test_a_child_process_inherits_the_hold(ws):
    """The handoff has to survive a real spawn — every child is launched as
    `[sys.executable, "-m", "magi", ...]`, so the environment is the channel."""
    child = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(_src_dir())!r})
        from magi.core.worklock import workspace_lock
        with workspace_lock({str(ws)!r}, "lint --fix") as took:
            print("TOOK" if took else "INHERITED")
    """)
    with workspace_lock(ws, "link"):
        out = subprocess.run([sys.executable, "-c", child], capture_output=True,
                             text=True, env=dict(os.environ))
    assert out.returncode == 0, out.stderr
    assert "INHERITED" in out.stdout, out.stdout


def test_the_environment_is_left_as_it_was_found(ws):
    before = os.environ.get(ENV_HELD)
    with workspace_lock(ws, "lint --fix"):
        assert os.environ[ENV_HELD] == str(ws.resolve())
    assert os.environ.get(ENV_HELD) == before


def test_a_nested_release_does_not_free_the_outer_hold(ws):
    with workspace_lock(ws, "link"):
        with workspace_lock(ws, "wiki refactor-concept"):
            pass
        assert os.environ[ENV_HELD] == str(ws.resolve()), (
            "the inner exit cleared the outer's ownership, so the next child "
            "would try to acquire a lock its parent is holding")


# --------------------------------------------------------------------------
# the other half: failing usefully rather than hanging
# --------------------------------------------------------------------------

def _holder_script(ws, seconds):
    return textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {str(_src_dir())!r})
        from magi.core.worklock import workspace_lock
        with workspace_lock({str(ws)!r}, "lint --fix"):
            print("HELD", flush=True)
            time.sleep({seconds})
    """)


def test_a_second_process_is_refused_with_something_actionable(ws):
    holder = subprocess.Popen([sys.executable, "-c", _holder_script(ws, 6)],
                              stdout=subprocess.PIPE, text=True,
                              env={k: v for k, v in os.environ.items()
                                   if k != ENV_HELD})
    try:
        assert holder.stdout.readline().strip() == "HELD"
        with pytest.raises(WorkspaceBusy) as exc:
            with workspace_lock(ws, "link", timeout=1.0):
                pass
        message = str(exc.value)
        assert "lint --fix" in message, "it does not say what is holding it"
        assert str(ws) in message
        assert "Wait for it" in message
    finally:
        holder.kill()
        holder.wait()


def test_the_holder_is_named_by_pid_too(ws):
    with workspace_lock(ws, "lint --fix"):
        rec = json.loads((ws / "output" / (LOCK_NAME + ".holder"))
                         .read_text(encoding="utf-8"))
    assert rec["what"] == "lint --fix"
    assert rec["pid"] == os.getpid()


def test_the_holder_note_is_cleared_on_release(ws):
    with workspace_lock(ws, "lint --fix"):
        pass
    assert not (ws / "output" / (LOCK_NAME + ".holder")).exists()


def test_the_next_process_gets_the_lock_after_a_clean_release(ws):
    """Whether the lock *file* survives release is `filelock`'s business — it
    unlinks it, and an earlier version of this test asserted the opposite
    because the comment it was written from described a hand-rolled lock in
    `kb/add_concept.py` rather than this library. What must hold either way is
    that the workspace is free afterwards."""
    with workspace_lock(ws, "lint --fix"):
        pass

    with workspace_lock(ws, "link", timeout=1.0) as took:
        assert took is True


def test_a_killed_holder_does_not_leave_the_workspace_locked(ws):
    """`filelock` uses a real OS lock on both platforms — `msvcrt.locking` on
    Windows, `fcntl.flock` on POSIX — so the kernel drops it when the handle
    dies. A sentinel-file lock would strand the workspace here."""
    holder = subprocess.Popen([sys.executable, "-c", _holder_script(ws, 60)],
                              stdout=subprocess.PIPE, text=True,
                              env={k: v for k, v in os.environ.items()
                                   if k != ENV_HELD})
    assert holder.stdout.readline().strip() == "HELD"
    holder.kill()
    holder.wait()

    with workspace_lock(ws, "link", timeout=10.0) as took:
        assert took is True


def test_the_lock_is_released_when_the_body_raises(ws):
    with pytest.raises(ValueError):
        with workspace_lock(ws, "lint --fix"):
            raise ValueError("boom")

    with workspace_lock(ws, "link", timeout=1.0) as took:
        assert took is True


def _src_dir():
    from pathlib import Path

    return Path(__file__).resolve().parents[1] / "src"
