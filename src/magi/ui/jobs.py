"""TaskManager for executing and monitoring background MAGI CLI jobs."""

from __future__ import annotations

import asyncio
import collections
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Set


class JobConflict(Exception):
    """Raised when the concurrency gate rejects a new job."""


# Server-side operation whitelist: the ONLY things POST /api/jobs can run.
# argv is relative to `magi`; params maps a boolean param name -> CLI flag.
# label_i18n/desc_i18n are frontend dictionary keys — the ops catalog drives
# the UI buttons, so the frontend holds zero op-specific knowledge.
#
# `home` says which panel a generic button for this op belongs on, and is the
# rest of keeping that promise. The frontend used to render every non-danger op
# into one grid on the Operations tab, minus a two-item blacklist written by op
# id — which is precisely the frontend holding op-specific knowledge. The
# result was a panel whose organising principle was "everything that has not
# been excluded": seven of its buttons already existed on the tab they belong
# to, `install-tasks` and `pull-models` appeared twice on the same screen, and
# what was left over was three index-rebuilding commands with confusingly
# similar names.
#
#   "<tab>"  render a generic button into that panel's ops mount
#   None     that panel already has a better, more contextual control for this
#            op — do not render a second one
#   "danger" the Danger Zone grid, behind the type-the-name confirm
#
# An op's home is the tab where a reader would go looking for its *effect*,
# not the tab named after its implementation: `index` rebuilds what Casper
# searches, so it lives next to the search box, where someone who cannot find
# a document they just added will actually be.
OPS: dict[str, dict] = {
    # kb-scoped maintenance
    "index": {"home": "casper", "argv": ["index"], "scope": "kb", "danger": False,
              "label_i18n": "op_rebuild_index",
              "desc_i18n": "op_desc_index"},
    "graph-build": {"home": "melchior", "argv": ["graph", "build"], "scope": "kb", "danger": False,
                    "label_i18n": "op_build_graph",
                    "desc_i18n": "op_desc_graph_build"},
    "wiki-reindex": {"home": "melchior", "argv": ["wiki", "reindex"], "scope": "kb", "danger": False,
                     "label_i18n": "op_reindex_wiki",
                     "desc_i18n": "op_desc_wiki_reindex"},
    "link": {"home": "melchior", "argv": ["link"], "scope": "kb", "danger": False,
             "label_i18n": "op_semantic_link",
             "desc_i18n": "op_desc_link"},
    "lint-fix": {"home": "melchior", "argv": ["lint", "--fix"], "scope": "kb", "danger": False,
                 "label_i18n": "op_lint_fix",
                 "desc_i18n": "op_desc_lint_fix"},
    # `magi stats` alone is ambiguous (three different reports); the button
    # means "summarize this workspace".
    "stats": {"home": "dashboard", "argv": ["stats", "wiki-summary"], "scope": "kb", "danger": False,
              "label_i18n": "op_stats",
              "desc_i18n": "op_desc_stats"},
    "backlog-sync": {"home": None, "argv": ["pm", "backlog-sync"], "scope": "kb", "danger": False,
                     "label_i18n": "op_backlog_sync",
                     "desc_i18n": "op_desc_backlog_sync"},
    # Additive and idempotent — `magi pm init` checks for .beads/metadata.json
    # and no-ops if it is there. It was in the Danger Zone behind a
    # type-the-exact-name modal, next to genuine deletions, while being the
    # exact step the dashboard tells a new user to take second. That made the
    # whole task-tracking bootstrap read as something to avoid.
    # `scope: "global"` is the concurrency class — a global job blocks every
    # other one. It is not the sentence to show a reader: `magi pm init`
    # writes at the hub root, which is wider than the workspace in the picker
    # but narrower than the machine. `badge_i18n` names the real reach.
    "pm-init": {"home": None, "argv": ["pm", "init"], "scope": "global", "danger": False,
                "badge_i18n": "scope_badge_hub",
                "label_i18n": "btn_danger_pm_init", "desc_i18n": "danger_pm_init_desc"},
    "radar-harvest": {"home": None, "argv": ["radar", "harvest"], "scope": "kb", "danger": False,
                      "label_i18n": "btn_radar_harvest",
                      "desc_i18n": "op_desc_radar_harvest"},
    # Both are long-running and subprocess-heavy, so they want the SSE log
    # stream and the concurrency gate this machinery already provides. Neither
    # is destructive: batch-run writes only into staging, and batch-commit
    # refuses any batch with an undecided item.
    "ingest-batch-run": {"home": None, 
        "argv": ["ingest", "batch-run"],
        "scope": "kb",
        "danger": False,
        "label_i18n": "op_ingest_batch_run",
        "desc_i18n": "op_desc_ingest_batch_run",
    },
    "ingest-batch-commit": {"home": None, 
        "argv": ["ingest", "batch-commit"],
        "scope": "kb",
        "danger": False,
        "label_i18n": "op_ingest_batch_commit",
        "desc_i18n": "op_desc_ingest_batch_commit",
    },
    "radar-citation-gap": {"home": None, "argv": ["radar", "citation-gap"], "scope": "kb", "danger": False,
                           "label_i18n": "btn_radar_citation_gap",
                           "desc_i18n": "op_desc_radar_citation_gap"},
    # Turning an optional feature on. Narrow on purpose: `magi setup` is far
    # too broad to sit behind a button labelled "turn on task tracking", and a
    # user clicking that has not consented to re-provisioning their machine.
    # Both are machine-wide because what they install is machine-wide, and both
    # are idempotent — clicking twice is not a mistake.
    "install-tasks": {"home": None, "argv": ["setup", "--install-tasks"], "scope": "global",
                      "danger": False, "badge_i18n": "ops_badge_global",
                      "label_i18n": "btn_install_tasks",
                      "desc_i18n": "op_desc_install_tasks"},
    "pull-models": {"home": None, "argv": ["setup", "--pull-models"], "scope": "global",
                    "danger": False, "badge_i18n": "ops_badge_global",
                    "label_i18n": "btn_pull_models",
                    "desc_i18n": "op_desc_pull_models"},
    # danger zone (server re-verifies confirm == op id)
    "setup": {"home": "danger", "argv": ["setup"], "scope": "global", "danger": True,
              "label_i18n": "btn_danger_setup", "desc_i18n": "danger_setup_desc"},
    "migrate": {"home": "danger", "argv": ["migrate"], "scope": "global", "danger": True,
                "label_i18n": "btn_danger_migrate", "desc_i18n": "danger_migrate_desc"},
    "setup-remove-legacy": {"home": "danger", "argv": ["setup", "--remove-legacy"], "scope": "global", "danger": True,
                            "label_i18n": "btn_danger_legacy", "desc_i18n": "danger_remove_legacy_desc"},
    # Not a danger-zone operation. It registers or removes a daily scheduled
    # harvest: reversible, idempotent, and it touches no workspace data. It sat
    # behind the same type-the-exact-name modal as `migrate` and
    # `setup --remove-legacy`, on a different tab from the feature it turns on,
    # which is a good way to make sure nobody ever schedules anything.
    "radar-install-schedule": {"home": "radar", "argv": ["radar", "install-schedule"], "scope": "kb", "danger": False,
                               "label_i18n": "btn_danger_install_schedule",
                               "desc_i18n": "danger_install_schedule_desc",
                               "params": {"uninstall": "--uninstall"}},
}

def _terminate_tree(proc, kill: bool = False) -> None:
    """Stop a job and everything it started.

    Cancel used to call ``proc.terminate()``, which reaches the ``magi``
    process and nothing below it. A job is mostly a launcher — batch-run shells
    out to pandoc, ingest to MinerU, index to Ollama — so the work carried on
    with nothing watching it, still holding a cloud token or a GPU.

    The child is spawned into its own group, so signalling the group reaches
    the whole tree. Falls back to the single process if that fails, which is
    still better than nothing.
    """
    import signal

    try:
        if os.name == "nt":
            # CTRL_BREAK is the only signal a new process group accepts on
            # Windows, and only a group leader can be sent it.
            if not kill:
                proc.send_signal(signal.CTRL_BREAK_EVENT)
                return
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=10)
            return
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGKILL if kill else signal.SIGTERM)
    except Exception:  # noqa: BLE001 — the process may already be gone
        try:
            proc.kill() if kill else proc.terminate()
        except Exception:  # noqa: BLE001
            pass


# Archive limits (decision: persist job history, but hard-cap total size)
# One SSE client's backlog. Mirrors the server-side log buffer: a browser that
# has stopped draining — a backgrounded tab, a stalled connection, a laptop
# that slept — must not be able to grow this without bound.


LISTENER_QUEUE_MAX = 2000


def _offer(q: "asyncio.Queue", payload: dict) -> None:
    """Hand a message to one listener without ever blocking the producer.

    Drops the OLDEST message to make room, not the newest. Two reasons: a log
    tail is more useful with a gap in the middle than cut off at the moment the
    reader stalled, and the terminal status message — the one `stream_logs`
    waits for before closing the connection — is always the newest. Dropping
    that would leave the stream open forever.
    """
    while True:
        try:
            q.put_nowait(payload)
            return
        except asyncio.QueueFull:
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:      # pragma: no cover - full and empty
                return


MAX_ARCHIVE_BYTES = 262_144
ARCHIVE_KEEP_RECORDS = 40
ARCHIVE_LOAD_RECORDS = 20
ARCHIVE_LOG_TAIL = 30


class Job:
    def __init__(
        self,
        job_id: str,
        command: list[str],
        workspace: str,
        name: str | None = None,
        max_log_lines: int = 2000,
        op_id: str | None = None,
        scope: str = "kb",
    ) -> None:
        self.id = job_id
        self.command = command
        self.workspace = workspace
        self.name = name or (" ".join(command) if command else "magi")
        self.op = op_id
        self.scope = scope
        self.status = "pending"  # "pending", "running", "completed", "failed", "cancelled"
        self.exit_code: int | None = None
        self.created_at = dt.datetime.now(dt.timezone.utc).isoformat()
        self.finished_at: str | None = None
        self.logs: collections.deque[str] = collections.deque(maxlen=max_log_lines)
        self.process: subprocess.Popen | None = None
        self.listeners: Set[asyncio.Queue] = set()
        self._lock = threading.Lock()
        # Where this job's record will be archived, decided now rather than
        # when it finishes. A job runs on a background thread and persists
        # itself minutes later; resolving the config home at that point meant
        # the destination could move underneath it. The test suite hit this for
        # real — its jobs outlived the fixture that redirected MAGI_CONFIG_HOME
        # and wrote 83 records into the developer's live job history.
        self.archive_path: Path | None = None

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "name": self.name,
                "op": self.op,
                "scope": self.scope,
                "command": self.command,
                "workspace": self.workspace,
                "status": self.status,
                "exit_code": self.exit_code,
                "created_at": self.created_at,
                "finished_at": self.finished_at,
                "log_count": len(self.logs),
                "archived": False,
            }

    def _fan_out(self, payload: dict, loop: asyncio.AbstractEventLoop | None) -> None:
        """Push one line to every open log stream.

        Jobs run on worker threads, and ``asyncio.Queue`` is documented as not
        thread-safe. With a live loop the write is handed to it with
        ``call_soon_threadsafe``, which is the whole point of that call. There
        used to be an ``else`` that wrote to the queue from this thread when
        the loop was missing or closed — a fallback whose *best* case is
        touching asyncio internals from the wrong thread, and whose realistic
        case is delivering to a queue that no coroutine will ever read again,
        because the loop that would read it is gone.

        Dropping the notification is what a closed loop means.
        """
        with self._lock:
            active_listeners = list(self.listeners)
        if not (loop and not loop.is_closed()):
            return
        for q in active_listeners:
            try:
                loop.call_soon_threadsafe(_offer, q, payload)
            except Exception:
                pass

    def append_log(self, line: str, loop: asyncio.AbstractEventLoop | None = None) -> None:
        line_clean = line.rstrip("\r\n")
        with self._lock:
            self.logs.append(line_clean)
        self._fan_out({"type": "log", "line": line_clean}, loop)

    def notify_status_change(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        with self._lock:
            payload = {
                "type": "status",
                "status": self.status,
                "exit_code": self.exit_code,
                "finished_at": self.finished_at,
            }
        self._fan_out(payload, loop)


class TaskManager:
    def __init__(self, max_history: int = 100) -> None:
        self.max_history = max_history
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._archive: list[dict] = []
        self._archive_home: str | None = None  # config home the archive was loaded from
        # Separate from _lock on purpose: the archive write does file I/O, and
        # _lock is also what the SSE log fan-out takes. Holding one lock for
        # both would let a slow disk stall every streaming client.
        self._archive_write_lock = threading.Lock()

    # -- persistence (jsonl in the magi config home, size-capped) ------------

    def _persist_file(self):
        from magi.kb_registry import _config_home

        home = _config_home()
        home.mkdir(parents=True, exist_ok=True)
        return home / "ui-jobs.jsonl"

    def _ensure_archive_loaded(self) -> None:
        try:
            path = self._persist_file()
        except Exception:
            return
        key = str(path)
        if self._archive_home == key:
            return
        self._archive_home = key
        recs: list[dict] = []
        try:
            if path.is_file():
                for line in path.read_text(encoding="utf-8").splitlines()[-ARCHIVE_LOAD_RECORDS:]:
                    try:
                        rec = json.loads(line)
                        rec["archived"] = True
                        recs.append(rec)
                    except Exception:
                        continue
        except OSError:
            pass
        self._archive = list(reversed(recs))  # newest first

    def _persist_job(self, job: Job) -> None:
        try:
            rec = job.to_dict()
            with job._lock:
                rec["log_tail"] = list(job.logs)[-ARCHIVE_LOG_TAIL:]
            rec["archived"] = True
            path = job.archive_path or self._persist_file()
            # Append-then-maybe-compact is a read-modify-write, and two jobs
            # finishing at once used to interleave inside it: both append, both
            # read, both rewrite — and the second rewrite drops whatever the
            # first added. Under load that emptied the file. One writer at a
            # time, and the rewrite lands atomically so a reader (or another
            # magi ui process on the same config home) sees the whole old file
            # or the whole new one, never a half-written one.
            with self._archive_write_lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if path.stat().st_size > MAX_ARCHIVE_BYTES:
                    lines = path.read_text(encoding="utf-8").splitlines()[-ARCHIVE_KEEP_RECORDS:]
                    tmp = path.with_name(path.name + ".compact")
                    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    os.replace(tmp, path)
            with self._lock:
                self._archive.insert(0, rec)
                del self._archive[ARCHIVE_LOAD_RECORDS:]
        except Exception:
            pass

    def get_archived(self, job_id: str) -> dict | None:
        self._ensure_archive_loaded()
        with self._lock:
            for rec in self._archive:
                if rec.get("id") == job_id:
                    return rec
        return None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _ensure_loop(self) -> asyncio.AbstractEventLoop | None:
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        return self._loop

    def create_job(
        self,
        command: list[str],
        workspace: str | None = None,
        name: str | None = None,
        op_id: str | None = None,
        scope: str = "kb",
    ) -> Job:
        job_id = uuid.uuid4().hex[:12]
        clean_command = [c for c in command if c]
        target_ws = str(Path(workspace).resolve()) if workspace else str(Path.cwd().resolve())
        job = Job(job_id=job_id, command=clean_command, workspace=target_ws,
                  name=name, op_id=op_id, scope=scope)
        try:
            job.archive_path = self._persist_file()
        except Exception:
            job.archive_path = None

        self._ensure_loop()

        with self._lock:
            # Concurrency gate: maintenance commands mutate workspace state,
            # so two jobs on one KB (or anything next to a global op) can
            # corrupt each other.
            active = [j for j in self._jobs.values() if j.status in ("pending", "running")]
            if len(active) >= 3:
                raise JobConflict("max 3 concurrent jobs — wait for one to finish")
            if any(j.scope == "global" for j in active):
                raise JobConflict("a global operation is running — wait for it to finish")
            if scope == "global" and active:
                raise JobConflict("global operations require no other running jobs")
            if scope == "kb" and any(j.workspace == target_ws for j in active):
                raise JobConflict("this workspace already has an active job")

            self._jobs[job_id] = job
            # Prune old completed jobs if needed
            if len(self._jobs) > self.max_history:
                for k, j in list(self._jobs.items()):
                    if j.status != "running":
                        del self._jobs[k]
                        break

        # Launch in background thread
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return job

    def _run_job(self, job: Job) -> None:
        """Run the job, and end it exactly once however it ends.

        Read from ``job.process`` rather than a local, because a Popen that
        raised never bound one — and this has to work on the path where there
        is no process at all (a job cancelled while still pending).
        """
        try:
            self._run_job_inner(job)
        finally:
            proc = job.process
            # The pipe is not closed by iterating it to EOF, and a job that
            # was cancelled before its output was drained never got there at
            # all. Either way the descriptor outlives the thread until a
            # garbage collection notices.
            if proc is not None and proc.stdout is not None:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
            # Early exits used to sit in front of this: a job cancelled while
            # still pending returned before the lifecycle ran, so it was never
            # archived and never appeared in the history. One exit path, one
            # place that ends a job.
            job.notify_status_change(self._loop)
            self._persist_job(job)

    def _run_job_inner(self, job: Job) -> None:
        with job._lock:
            if job.status == "cancelled":
                return
            job.status = "running"

        cmd = [sys.executable, "-m", "magi", *job.command]
        job.append_log(f"=== Starting job: {job.name} ===", self._loop)
        job.append_log(f"Command: {' '.join(cmd)}", self._loop)
        job.append_log(f"Workspace: {job.workspace}", self._loop)
        job.append_log("=" * 40, self._loop)

        env = dict(os.environ)
        # Ensure UTF-8 output
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        # Its own process group, so Cancel can reach the whole tree. A magi job
        # is mostly a launcher: batch-run shells out to pandoc, ingest to
        # MinerU, index to Ollama. Terminating only the direct child leaves
        # those running, still holding a token or a GPU, with nothing left
        # watching them. Same convention as core/ollama.py's start().
        group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                 if os.name == "nt" else {"start_new_session": True})
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=job.workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                env=env,
                **group,
            )
            with job._lock:
                job.process = proc
                if job.status == "cancelled":
                    # The whole tree, not just the launcher. This one site
                    # still called `proc.terminate()` while `cancel_job` had
                    # already been fixed to use the tree — so a job cancelled
                    # in the window between spawning and registering left
                    # pandoc, MinerU or Ollama running with nothing watching.
                    _terminate_tree(proc)

            if proc.stdout:
                for line in proc.stdout:
                    job.append_log(line, self._loop)

            proc.wait()
            job.exit_code = proc.returncode

            with job._lock:
                if job.status != "cancelled":
                    job.status = "completed" if proc.returncode == 0 else "failed"
                job.finished_at = dt.datetime.now(dt.timezone.utc).isoformat()

            job.append_log("=" * 40, self._loop)
            job.append_log(f"=== Job finished with status: {job.status} (exit {job.exit_code}) ===", self._loop)
        except Exception as exc:
            with job._lock:
                if job.status != "cancelled":
                    job.status = "failed"
                job.exit_code = -1
                job.finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
            job.append_log(f"=== Job failed with error: {exc} ===", self._loop)

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        self._ensure_archive_loaded()
        with self._lock:
            live = [j.to_dict() for j in reversed(list(self._jobs.values()))]
            live_ids = {j["id"] for j in live}
            archived = [dict(r) for r in self._archive if r.get("id") not in live_ids]
        return live + archived

    def cancel_job(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if not job:
            return False

        with job._lock:
            if job.status not in ("running", "pending"):
                return False
            job.status = "cancelled"
            job.finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
            proc = job.process

        if proc:
            try:
                _terminate_tree(proc)
                # Give it a moment to terminate gracefully before kill
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    _terminate_tree(proc, kill=True)
            except Exception:
                pass

        job.append_log("=== Job cancelled by user ===", self._loop)
        job.notify_status_change(self._loop)
        return True

    async def stream_logs(self, job_id: str) -> AsyncGenerator[str, None]:
        self._ensure_loop()
        job = self.get_job(job_id)
        if not job:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
            return

        queue: asyncio.Queue = asyncio.Queue(maxsize=LISTENER_QUEUE_MAX)

        # Safely snapshot buffered logs and register listener without holding lock across yield
        with job._lock:
            cached_logs = list(job.logs)
            is_active = (job.status in ("running", "pending"))
            if is_active:
                job.listeners.add(queue)
            status_snapshot = {
                "type": "status",
                "status": job.status,
                "exit_code": job.exit_code,
                "finished_at": job.finished_at,
            }

        # Replay existing buffered logs outside lock
        for log_line in cached_logs:
            yield f"data: {json.dumps({'type': 'log', 'line': log_line}, ensure_ascii=False)}\n\n"

        if not is_active:
            yield f"data: {json.dumps(status_snapshot, ensure_ascii=False)}\n\n"
            return

        try:
            while True:
                msg = await queue.get()
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                if msg.get("type") == "status" and msg.get("status") in ("completed", "failed", "cancelled"):
                    break
        finally:
            with job._lock:
                job.listeners.discard(queue)


# Global singleton instance
task_manager = TaskManager()
