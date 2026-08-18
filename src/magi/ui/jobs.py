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


class Job:
    def __init__(
        self,
        job_id: str,
        command: list[str],
        workspace: str,
        name: str | None = None,
        max_log_lines: int = 2000,
    ) -> None:
        self.id = job_id
        self.command = command
        self.workspace = workspace
        self.name = name or (" ".join(command) if command else "magi")
        self.status = "pending"  # "pending", "running", "completed", "failed", "cancelled"
        self.exit_code: int | None = None
        self.created_at = dt.datetime.now(dt.timezone.utc).isoformat()
        self.finished_at: str | None = None
        self.logs: collections.deque[str] = collections.deque(maxlen=max_log_lines)
        self.process: subprocess.Popen | None = None
        self.listeners: Set[asyncio.Queue] = set()
        self._lock = threading.Lock()

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "name": self.name,
                "command": self.command,
                "workspace": self.workspace,
                "status": self.status,
                "exit_code": self.exit_code,
                "created_at": self.created_at,
                "finished_at": self.finished_at,
                "log_count": len(self.logs),
            }

    def append_log(self, line: str, loop: asyncio.AbstractEventLoop | None = None) -> None:
        line_clean = line.rstrip("\r\n")
        with self._lock:
            self.logs.append(line_clean)
            active_listeners = list(self.listeners)

        for q in active_listeners:
            try:
                if loop and not loop.is_closed():
                    loop.call_soon_threadsafe(q.put_nowait, {"type": "log", "line": line_clean})
                else:
                    q.put_nowait({"type": "log", "line": line_clean})
            except Exception:
                pass

    def notify_status_change(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        with self._lock:
            payload = {
                "type": "status",
                "status": self.status,
                "exit_code": self.exit_code,
                "finished_at": self.finished_at,
            }
            active_listeners = list(self.listeners)

        for q in active_listeners:
            try:
                if loop and not loop.is_closed():
                    loop.call_soon_threadsafe(q.put_nowait, payload)
                else:
                    q.put_nowait(payload)
            except Exception:
                pass


class TaskManager:
    def __init__(self, max_history: int = 100) -> None:
        self.max_history = max_history
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

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
    ) -> Job:
        job_id = uuid.uuid4().hex[:12]
        clean_command = [c for c in command if c]
        target_ws = str(Path(workspace).resolve()) if workspace else str(Path.cwd().resolve())
        job = Job(job_id=job_id, command=clean_command, workspace=target_ws, name=name)

        self._ensure_loop()

        with self._lock:
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
            )
            with job._lock:
                job.process = proc
                if job.status == "cancelled":
                    proc.terminate()

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
        finally:
            job.notify_status_change(self._loop)

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [j.to_dict() for j in reversed(list(self._jobs.values()))]

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
                proc.terminate()
                # Give it a moment to terminate gracefully before kill
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
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

        queue: asyncio.Queue = asyncio.Queue()

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
