"""The queue and the batch ledger — where an ingest waits for a human.

Two append-only JSONL files, folded last-write-wins. That is the pattern this
repo already runs on (``seen.jsonl``, ``triage.jsonl``, ``ui-jobs.jsonl``): it
survives a restart because it is a file, undo is just another appended record,
and nothing is ever rewritten in place so a crash mid-write cannot corrupt what
came before.

Deliberately not the radar's shape. Radar round-trips its candidates through a
hand-authored markdown digest and re-parses them with regexes, because there
really is a document there for a person to read. A batch item *is* the artifact;
inventing a markdown file whose only purpose is being re-parsed would recreate
exactly the coupling that makes the radar digest fragile.

``queue.jsonl``      one line per acquisition request. Inert: nothing reads it
                     except ``batch-run``. This is all the browser extension can
                     ever write, which is what keeps its blast radius at zero.
``<batch_id>.jsonl`` one run: what was attempted, what came out, what a human
                     decided, and what was committed.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, NamedTuple

INGEST_DIRNAME = os.path.join("output", "ingest")
QUEUE_NAME = "queue.jsonl"
STAGING_DIRNAME = "staging"
LOCK_NAME = ".lock"

# Best first. Rejecting an item moves it one step down and it reappears in the
# next batch, so this order is also the retry order.
LADDER: tuple[str, ...] = ("arxiv-html", "tex", "textlayer", "mineru", "ocr")

# Never reached by falling down the ladder. It costs one agent subagent per PDF
# page, so it is only ever entered by someone explicitly asking for it after
# being shown the page count.
LAST_RESORT = "vision"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def ingest_dir(topic) -> Path:
    return Path(topic) / INGEST_DIRNAME


def queue_path(topic) -> Path:
    return ingest_dir(topic) / QUEUE_NAME


def staging_dir(topic, batch_id: str) -> Path:
    return ingest_dir(topic) / STAGING_DIRNAME / batch_id


def batch_path(topic, batch_id: str) -> Path:
    return ingest_dir(topic) / f"{batch_id}.jsonl"


def _append(path: Path, record: dict) -> None:
    """Add one line, safely against another process doing the same.

    A plain append is not enough. POSIX ``O_APPEND`` makes the seek-and-write
    one atomic step, but Windows does not, and a measured harness of six
    concurrent writers loses and interleaves lines there. The queue is written
    by the CLI, by the WebUI job, and by the browser extension's endpoint, so
    two writers at once is ordinary rather than exotic — and a lost line is a
    paper that silently never gets ingested.
    """
    from filelock import FileLock, Timeout

    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    lock = FileLock(str(path.parent / LOCK_NAME), timeout=10)
    try:
        with lock:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
    except Timeout:
        # Better a duplicate than a dropped paper: the fold is last-write-wins
        # on decisions and de-duplicates items by id, so an extra line is
        # survivable in a way that a missing one is not.
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)


def _read(path: Path) -> list[dict]:
    if not Path(path).is_file():
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # A half-written final line from a killed process. Everything before
            # it is still good, which is the whole point of append-only.
            continue
    return out


# --------------------------------------------------------------------------
# The queue
# --------------------------------------------------------------------------

class QueueEntry(NamedTuple):
    req_id: str
    at: str
    source_type: str      # "url" | "doi" | "arxiv" | "file" | "zotero"
    value: str
    library: str | None
    route: str | None     # forced starting rung, when this is a retry
    retry_of: str | None
    title: str | None


def enqueue(topic, *, source_type: str, value: str, library: str | None = None,
            route: str | None = None, retry_of: str | None = None,
            title: str | None = None) -> str:
    """Record one acquisition request and return its id.

    Appends a line. Touches nothing else — no network, no conversion, no writing
    into the library. An entry sitting here is inert until someone runs a batch,
    and what a batch produces is still inert until a human approves it.
    """
    req_id = _new_id("req")
    _append(queue_path(topic), {
        "kind": "enqueue",
        "req_id": req_id,
        "at": _now(),
        "source": {"type": source_type, "value": value, "library": library},
        "route": route,
        "retry_of": retry_of,
        "title": title,
        "status": "queued",
    })
    return req_id


def pending(topic) -> list[QueueEntry]:
    """Everything queued that no batch has claimed yet."""
    claimed = set()
    for path in ingest_dir(topic).glob("batch-*.jsonl") if ingest_dir(topic).is_dir() else []:
        for rec in _read(path):
            if rec.get("kind") == "item" and rec.get("req_id"):
                claimed.add(rec["req_id"])

    out = []
    for rec in _read(queue_path(topic)):
        if rec.get("kind") != "enqueue" or rec.get("req_id") in claimed:
            continue
        src = rec.get("source") or {}
        out.append(QueueEntry(
            req_id=rec["req_id"], at=rec.get("at", ""),
            source_type=src.get("type", ""), value=src.get("value", ""),
            library=src.get("library"), route=rec.get("route"),
            retry_of=rec.get("retry_of"), title=rec.get("title")))
    return out


# --------------------------------------------------------------------------
# A batch
# --------------------------------------------------------------------------

class BatchItem(NamedTuple):
    item_id: str
    req_id: str
    route: str
    source_value: str
    title: str | None
    arxiv_id: str | None
    staged_md: str | None
    findings: list
    error: str | None
    decision: str | None       # None | "approve" | "reject"
    committed_path: str | None
    retry_of: str | None

    @property
    def decided(self) -> bool:
        return self.decision in ("approve", "reject")

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.staged_md)


def start_batch(topic) -> str:
    """Open a new batch and return its id."""
    batch_id = _new_id("batch")
    _append(batch_path(topic, batch_id),
            {"kind": "open", "batch_id": batch_id, "at": _now()})
    return batch_id


def record_item(topic, batch_id: str, *, req_id: str, route: str,
                source_value: str, title: str | None = None,
                arxiv_id: str | None = None, staged_md: str | None = None,
                findings: Iterable | None = None, error: str | None = None,
                retry_of: str | None = None) -> str:
    item_id = _new_id("item")
    _append(batch_path(topic, batch_id), {
        "kind": "item",
        "item_id": item_id,
        "req_id": req_id,
        "at": _now(),
        "route": route,
        "source_value": source_value,
        "title": title,
        "arxiv_id": arxiv_id,
        "staged_md": staged_md,
        "findings": [{"code": f.code, "detail": f.detail, "severity": f.severity}
                     for f in (findings or [])],
        "error": error,
        "retry_of": retry_of,
    })
    return item_id


def record_decision(topic, batch_id: str, item_id: str, decision: str) -> None:
    """Approve, reject, or undo. Undo is just another appended record — the fold
    takes the last one, exactly as the radar's triage log does."""
    if decision not in ("approve", "reject", "reset"):
        raise ValueError(f"unknown decision: {decision!r}")
    _append(batch_path(topic, batch_id),
            {"kind": "decision", "item_id": item_id,
             "decision": decision, "at": _now()})


def record_commit(topic, batch_id: str, item_id: str, committed_path: str) -> None:
    _append(batch_path(topic, batch_id),
            {"kind": "commit", "item_id": item_id,
             "committed_path": str(committed_path), "at": _now()})


def load_batch(topic, batch_id: str) -> list[BatchItem]:
    """Fold one batch's log into its current state."""
    items: dict[str, dict] = {}
    order: list[str] = []
    for rec in _read(batch_path(topic, batch_id)):
        kind = rec.get("kind")
        if kind == "item":
            items[rec["item_id"]] = dict(rec)
            order.append(rec["item_id"])
        elif kind == "decision" and rec.get("item_id") in items:
            decision = rec.get("decision")
            items[rec["item_id"]]["decision"] = None if decision == "reset" else decision
        elif kind == "commit" and rec.get("item_id") in items:
            items[rec["item_id"]]["committed_path"] = rec.get("committed_path")

    out = []
    for item_id in order:
        rec = items[item_id]
        out.append(BatchItem(
            item_id=item_id, req_id=rec.get("req_id", ""), route=rec.get("route", ""),
            source_value=rec.get("source_value", ""), title=rec.get("title"),
            arxiv_id=rec.get("arxiv_id"), staged_md=rec.get("staged_md"),
            findings=rec.get("findings") or [], error=rec.get("error"),
            decision=rec.get("decision"), committed_path=rec.get("committed_path"),
            retry_of=rec.get("retry_of")))
    return out


def list_batches(topic) -> list[str]:
    d = ingest_dir(topic)
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("batch-*.jsonl"))


def next_rung(route: str) -> str | None:
    """The rung below ``route``, or None at the bottom.

    Never returns the vision fan-out: falling into it by default is the whole
    failure this pipeline exists to prevent. Someone can still ask for it, after
    being shown what it costs.
    """
    try:
        idx = LADDER.index(route)
    except ValueError:
        return None
    return LADDER[idx + 1] if idx + 1 < len(LADDER) else None
