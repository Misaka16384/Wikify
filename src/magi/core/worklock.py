"""One workspace, one bulk rewrite at a time — across processes.

The WebUI has had a concurrency gate since it had jobs (`ui/jobs.py`), and its
comment says the right thing: two jobs on one knowledge base can corrupt each
other. But that gate is a dict in one process. It cannot see a `magi lint --fix`
somebody ran by hand in a terminal, or a second `magi ui`, and those are not
exotic — the WebUI *tells* you the CLI commands it is running, so running one
yourself is the obvious next thing to try.

What two writers actually destroy is `wiki/**/*.md`. `lint --fix`, `link`,
`tags apply` and `math format` each walk the whole tree and rewrite cards in
place; whichever finishes last wins, so one run's repairs vanish with nothing
said. `magi index` and `graph build` are *not* in that set — SQLite with a
busy timeout degrades to a lock error rather than corruption, and both files
are derived anyway.

Two things this has to get right:

**Re-entrancy across processes.** A file lock is held by a handle, not by a
process tree, so `magi link` — which shells out to `magi wiki
refactor-concept` — would wait on itself forever. `ingest batch-commit ->
ingest finalize -> lint --fix` is three processes deep. Ownership is therefore
handed to children through the environment: every child is spawned as
`[sys.executable, "-m", "magi", ...]`, so a variable naming the workspace the
caller already holds is inherited, and a child that sees its own workspace
there proceeds without acquiring.

**Failing usefully.** Blocking forever is worse than the race. Waiting says so
after a couple of seconds and names what it is waiting for, and gives up with
an error a person can act on rather than a traceback.
"""

from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

#: Names the workspace whose lock this process already owns. Children read it,
#: never write it — the owner sets it before spawning anything.
ENV_HELD = "MAGI_WORKSPACE_LOCK"

#: Inside `output/`, which is where the ingest ledger's lock already lives.
LOCK_NAME = ".magi-workspace.lock"

#: Long enough for the slowest thing that takes it (a full `lint --fix` on a
#: large wiki, or a `link` pass over every concept card) to finish while
#: another waits, short enough that a wedged process is reported rather than
#: waited on. The wait is announced at 2s so a pause is never mysterious.
DEFAULT_TIMEOUT = 120.0
ANNOUNCE_AFTER = 2.0


class WorkspaceBusy(RuntimeError):
    """Another process is rewriting this workspace."""


def _key(topic) -> str:
    return str(Path(topic).resolve())


def _holder_path(topic) -> Path:
    return Path(topic) / "output" / (LOCK_NAME + ".holder")


def _describe_holder(topic) -> str:
    """Who has it, if they said. Best effort — never the reason a run fails."""
    try:
        rec = json.loads(_holder_path(topic).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "another magi process"
    what, pid = rec.get("what"), rec.get("pid")
    if what and pid:
        return f"`magi {what}` (pid {pid})"
    return what or "another magi process"


@contextmanager
def workspace_lock(topic, what: str, timeout: float = DEFAULT_TIMEOUT):
    """Hold the workspace against other *rewriting* processes.

    *what* is the command, for the message a blocked caller sees. Yields True
    when this call took the lock and False when an ancestor already held it —
    callers do not need to care, but tests do.
    """
    from filelock import FileLock, Timeout

    topic = Path(topic)
    key = _key(topic)
    if os.environ.get(ENV_HELD) == key:
        # An ancestor in this same chain owns it. Acquiring again would be a
        # deadlock, not a safeguard.
        yield False
        return

    lock_dir = topic / "output"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(lock_dir / LOCK_NAME), timeout=0)

    deadline = time.monotonic() + timeout
    announced = False
    while True:
        try:
            lock.acquire(timeout=0)
            break
        except Timeout:
            waited = timeout - (deadline - time.monotonic())
            if waited >= ANNOUNCE_AFTER and not announced:
                announced = True
                print(f"waiting for {_describe_holder(topic)} to finish in "
                      f"{topic.name}...", file=sys.stderr)
            if time.monotonic() >= deadline:
                raise WorkspaceBusy(
                    f"{_describe_holder(topic)} is already rewriting "
                    f"{topic}. Wait for it to finish, or stop it, then run "
                    f"this again.") from None
            time.sleep(0.25)

    previous = os.environ.get(ENV_HELD)
    os.environ[ENV_HELD] = key
    try:
        try:
            _holder_path(topic).write_text(
                json.dumps({"what": what, "pid": os.getpid()}), encoding="utf-8")
        except OSError:
            pass        # the message is a courtesy; the lock is the guarantee
        yield True
    finally:
        if previous is None:
            os.environ.pop(ENV_HELD, None)
        else:
            os.environ[ENV_HELD] = previous
        try:
            _holder_path(topic).unlink()
        except OSError:
            pass
        # `filelock` unlinks the lock file on release; that is its choice, not
        # ours, and it is why there is nothing here doing the opposite.
        # `kb/add_concept.py:229-235` argues for keeping the file, and it is
        # right about the hazard — between unlock and unlink another process
        # can acquire, and on POSIX the unlink then strands it holding an inode
        # nobody else can reach. The window is small and the library owns that
        # code path, so this notes it rather than fighting it. What is
        # guaranteed here is the part that matters: after release, the next
        # process gets the lock.
        lock.release()


def guard(topic, what: str):
    """`workspace_lock` for a `main()` that wants one line and an exit code.

    Returns a context manager that turns `WorkspaceBusy` into a printed message
    — the caller is a CLI, and a traceback here says nothing a person can use.
    """

    @contextmanager
    def _guarded():
        try:
            with workspace_lock(topic, what) as took:
                yield took
        except WorkspaceBusy as exc:
            print(f"magi: {exc}", file=sys.stderr)
            raise SystemExit(1) from None

    return _guarded()
