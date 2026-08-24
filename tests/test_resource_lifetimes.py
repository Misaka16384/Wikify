"""Things that must be released on the failing path, not just the happy one.

None of these is a clever bug. They are all the same omission — a close, a
cleanup or a kill placed at the end of a `try` instead of in a `finally` — and
they were all found by asking one question of each resource: *what happens to
this when the next line raises?*

On Windows the answer is not academic. An open ``fitz.Document`` or SQLite
connection holds the file, so the next thing to overwrite or delete it fails;
``proc.terminate()`` reaches the launcher and leaves pandoc, MinerU or Ollama
running underneath it.
"""

import sqlite3

import pytest


# --------------------------------------------------------------------------
# a job ends exactly once, however it ends
# --------------------------------------------------------------------------

def _manager(tmp_path, monkeypatch):
    from magi.ui import jobs

    tm = jobs.TaskManager.__new__(jobs.TaskManager)
    tm._loop = None
    tm._persisted = []
    monkeypatch.setattr(tm, "_persist_job", tm._persisted.append, raising=False)
    return jobs, tm


def test_a_job_cancelled_before_it_starts_is_still_archived(tmp_path, monkeypatch):
    """The early return sat in front of the lifecycle, so a job cancelled while
    pending was never persisted and never showed up in the history."""
    jobs, tm = _manager(tmp_path, monkeypatch)

    job = jobs.Job(job_id="j1", name="idx", command=["index"],
                   workspace=str(tmp_path))
    job.status = "cancelled"
    tm._run_job(job)

    assert tm._persisted == [job]


def test_a_cancelled_pending_job_never_spawns_anything(tmp_path, monkeypatch):
    jobs, tm = _manager(tmp_path, monkeypatch)
    spawned = []
    monkeypatch.setattr(jobs.subprocess, "Popen",
                        lambda *a, **k: spawned.append(a) or (_ for _ in ()).throw(
                            AssertionError("should not spawn")))

    job = jobs.Job(job_id="j2", name="idx", command=["index"],
                   workspace=str(tmp_path))
    job.status = "cancelled"
    tm._run_job(job)
    assert spawned == []


def test_the_output_pipe_is_closed(tmp_path, monkeypatch):
    jobs, tm = _manager(tmp_path, monkeypatch)

    closed = []

    class _Pipe:
        def __iter__(self):
            return iter(["line one\n"])

        def close(self):
            closed.append(True)

    class _Proc:
        stdout = _Pipe()
        returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(jobs.subprocess, "Popen", lambda *a, **k: _Proc())
    job = jobs.Job(job_id="j3", name="idx", command=["index"],
                   workspace=str(tmp_path))
    tm._run_job(job)

    assert closed == [True]


def test_cancelling_between_spawn_and_registration_kills_the_tree(tmp_path, monkeypatch):
    """This site still called `proc.terminate()` while `cancel_job` had already
    been moved to the tree — so the launcher died and pandoc did not."""
    jobs, tm = _manager(tmp_path, monkeypatch)

    killed = []

    class _Proc:
        stdout = None
        returncode = 0

        def wait(self):
            return 0

        def terminate(self):
            killed.append("single")

    monkeypatch.setattr(jobs.subprocess, "Popen", lambda *a, **k: _Proc())
    monkeypatch.setattr(jobs, "_terminate_tree",
                        lambda proc, kill=False: killed.append("tree"))

    job = jobs.Job(job_id="j4", name="idx", command=["index"],
                   workspace=str(tmp_path))

    real_lock = job._lock

    class _CancelOnEntry:
        """Flip to cancelled at the moment the process is registered."""
        def __init__(self):
            self.n = 0

        def __enter__(self):
            real_lock.acquire()
            self.n += 1
            if self.n == 2:
                job.status = "cancelled"
            return self

        def __exit__(self, *exc):
            real_lock.release()
            return False

    job._lock = _CancelOnEntry()
    tm._run_job(job)

    assert "tree" in killed and "single" not in killed


def test_a_closed_event_loop_drops_the_notification(tmp_path):
    """`asyncio.Queue` is not thread-safe, and a closed loop has no reader for
    it anyway. The old fallback wrote to the queue from the worker thread."""
    import asyncio

    from magi.ui import jobs

    job = jobs.Job(job_id="j5", name="idx", command=["index"],
                   workspace=str(tmp_path))
    q = asyncio.Queue()
    job.listeners.add(q)

    loop = asyncio.new_event_loop()
    loop.close()
    job._fan_out({"x": 1}, loop)
    job._fan_out({"x": 2}, None)

    assert q.qsize() == 0


# --------------------------------------------------------------------------
# databases and documents
# --------------------------------------------------------------------------

def test_a_failing_query_still_closes_the_connection(tmp_path, monkeypatch):
    """`melchior_status` closed at the end of the `try`, so "database is
    locked" — the realistic error, since a dashboard polls this while `magi
    index` holds a write lock — jumped past it."""
    from magi import sync

    db = tmp_path / "output" / "graph.db"
    db.parent.mkdir(parents=True)
    sqlite3.connect(db).close()          # exists, but has no `claims` table

    opened = []
    real_connect = sqlite3.connect

    def tracking(*a, **k):
        conn = real_connect(*a, **k)
        opened.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", tracking)
    (tmp_path / "wiki").mkdir()
    sync.melchior_status(tmp_path)

    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")     # already closed


def test_the_crop_tool_closes_the_pdf_on_every_path(tmp_path, monkeypatch):
    fitz = pytest.importorskip("fitz")
    from magi.ingest import pdf_math_crop

    pdf = tmp_path / "p.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf))
    doc.close()

    closed = []
    real_open = fitz.open

    def tracking(*a, **k):
        d = real_open(*a, **k)
        real_close = d.close

        def close():
            closed.append(True)
            real_close()
        d.close = close
        return d

    monkeypatch.setattr(pdf_math_crop.fitz, "open", tracking)
    # A search string that is not on the page: an early return, not the happy path.
    pdf_math_crop.extract_crop(str(pdf), "not on this page", str(tmp_path / "o.png"))

    assert closed == [True]


def test_a_zotero_directory_with_no_database_cleans_up_after_itself(tmp_path):
    """`__enter__` raising means `__exit__` is never called, so the temporary
    copy directory it had just made was left behind."""
    from magi.ingest import zotero

    handle = zotero.open_readonly(tmp_path)
    with pytest.raises(FileNotFoundError):
        handle.__enter__()

    assert handle._tmp is None, "the temporary directory was not released"


# --------------------------------------------------------------------------
# and one that is simply gone
# --------------------------------------------------------------------------

def test_the_chunker_keeps_no_unread_statistics():
    """A queue with a producer and no consumer is a leak with a nice name."""
    from magi.kb import chunker

    assert not hasattr(chunker, "_stats_queue")
