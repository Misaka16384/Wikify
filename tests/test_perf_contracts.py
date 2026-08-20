"""The performance properties that a regression would quietly undo.

Every case here started as a real complaint: a dashboard that froze for
seconds on load, an index run that looked hung for twenty minutes, a search
box that stalled while indexing, job history that vanished under concurrency.
Speed asserted in seconds is flaky, so these pin the *mechanisms* instead —
how many subprocesses spawn, how many HTTP round trips happen, what survives
an interruption.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path

import pytest

from magi import pm, retrieval
from magi.ui import jobs as jobs_mod


# --------------------------------------------------------------------------
# bd: one spawn per beads root, not one per caller
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_bd_cache():
    pm.bd_cache_clear()
    yield
    pm.bd_cache_clear()


def _fake_bd(calls: list, monkeypatch):
    monkeypatch.setattr(pm, "bd_available", lambda: True)

    class Done:
        returncode = 0
        stdout = json.dumps({"summary": {"ready_issues": 1}})

    def run(args, cwd, timeout=60):
        calls.append(str(cwd))
        time.sleep(0.02)          # a real spawn is ~300ms; enough to overlap
        return Done()

    monkeypatch.setattr(pm, "_run_bd", run)


def test_repeated_status_reads_spawn_bd_once(tmp_path, monkeypatch):
    root = tmp_path / "hub"
    (root / ".beads").mkdir(parents=True)
    (root / ".beads" / "metadata.json").write_text("{}", encoding="utf-8")
    calls: list = []
    _fake_bd(calls, monkeypatch)

    for _ in range(5):
        assert pm.bd_status_summary(root) == {"ready_issues": 1}
    assert len(calls) == 1, f"expected one spawn, got {len(calls)}"


def test_topics_under_one_hub_share_the_lookup(tmp_path, monkeypatch):
    """The dashboard asks per knowledge base, but `bd` resolves its database
    by walking up — so every topic under a hub has the same answer, and used
    to pay for its own subprocess to hear it."""
    hub = tmp_path / "hub"
    (hub / ".beads").mkdir(parents=True)
    (hub / ".beads" / "metadata.json").write_text("{}", encoding="utf-8")
    topics = [hub / "topics" / f"t{i}" for i in range(4)]
    for t in topics:
        t.mkdir(parents=True)

    calls: list = []
    _fake_bd(calls, monkeypatch)
    for t in topics:
        pm.bd_status_summary(t)
    assert len(calls) == 1, f"one hub, {len(calls)} spawns"


def test_concurrent_callers_do_not_all_miss_the_cache(tmp_path, monkeypatch):
    """The fan-out is threaded, so a cache checked-then-filled without a gate
    would let every thread through at once — the exact cost being removed."""
    root = tmp_path / "hub"
    (root / ".beads").mkdir(parents=True)
    (root / ".beads" / "metadata.json").write_text("{}", encoding="utf-8")
    calls: list = []
    _fake_bd(calls, monkeypatch)

    threads = [threading.Thread(target=pm.bd_status_summary, args=(root,))
               for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1, f"8 concurrent callers caused {len(calls)} spawns"


def test_the_cache_expires(tmp_path, monkeypatch):
    root = tmp_path / "hub"
    (root / ".beads").mkdir(parents=True)
    (root / ".beads" / "metadata.json").write_text("{}", encoding="utf-8")
    calls: list = []
    _fake_bd(calls, monkeypatch)
    monkeypatch.setattr(pm, "_STATUS_TTL_SECONDS", 0.0)

    pm.bd_status_summary(root)
    pm.bd_status_summary(root)
    assert len(calls) == 2, "a zero TTL must not serve a stale answer"


# --------------------------------------------------------------------------
# the wiki tree is walked once, and still answers every question
# --------------------------------------------------------------------------

def test_one_scan_answers_what_four_walks_used_to(tmp_path):
    from magi import sync

    wiki = tmp_path / "wiki"
    for sub, n in (("concepts", 3), ("references", 2), ("topics", 1)):
        (wiki / sub).mkdir(parents=True)
        for i in range(n):
            (wiki / sub / f"c{i}.md").write_text("x", encoding="utf-8")
        (wiki / sub / "_index.md").write_text("skip me", encoding="utf-8")
    # nested cards count; backups and _index.md do not
    (wiki / "concepts" / "deep").mkdir()
    (wiki / "concepts" / "deep" / "d.md").write_text("x", encoding="utf-8")
    (wiki / ".backup").mkdir()
    (wiki / ".backup" / "old.md").write_text("x", encoding="utf-8")

    scan = sync._scan_wiki(wiki)
    assert scan.counts.get("concepts") == 4
    assert scan.counts.get("references") == 2
    assert scan.counts.get("topics") == 1
    assert scan.newest > 0
    assert sync._newest_md_mtime(wiki) == scan.newest


def test_a_missing_wiki_scans_to_nothing(tmp_path):
    from magi import sync

    scan = sync._scan_wiki(tmp_path / "nope")
    assert scan.newest == 0.0 and scan.counts == {}


# --------------------------------------------------------------------------
# embeddings: batched, bounded, and honest about failing
# --------------------------------------------------------------------------

class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


def _embedder(monkeypatch, post):
    e = retrieval.Embedder()
    monkeypatch.setattr(e, "_preflight", lambda: True)

    class Session:
        def post(self, url, json=None, timeout=None):
            return post(url, json, timeout)

    monkeypatch.setattr(e, "_http", lambda: Session())
    return e


def test_a_batch_is_one_round_trip(monkeypatch):
    seen = []

    def post(url, payload, timeout):
        seen.append((url, len(payload["input"])))
        return _Resp(200, {"embeddings": [[0.1, 0.2]] * len(payload["input"])})

    e = _embedder(monkeypatch, post)
    out = e.embed_many([f"chunk {i}" for i in range(16)])
    assert len(out) == 16
    assert seen == [("http://127.0.0.1:11434/api/embed", 16)]


def test_an_old_ollama_without_the_batch_route_still_works(monkeypatch):
    urls = []

    def post(url, payload, timeout):
        urls.append(url)
        if url.endswith("/api/embed"):
            return _Resp(404)
        return _Resp(200, {"embedding": [0.5]})

    e = _embedder(monkeypatch, post)
    out = e.embed_many(["a", "b"])
    assert out == [[0.5], [0.5]]
    # probes /api/embed once, then stops asking
    assert urls.count("http://127.0.0.1:11434/api/embed") == 1
    e.embed_many(["c"])
    assert urls.count("http://127.0.0.1:11434/api/embed") == 1


def test_a_short_batch_is_rejected_rather_than_misaligned(monkeypatch):
    """Fewer vectors back than chunks sent would attach each vector to the
    wrong chunk if zipped blindly."""
    e = _embedder(monkeypatch, lambda u, p, t: _Resp(200, {"embeddings": [[1.0]]}))
    assert e.embed_many(["a", "b", "c"]) is None


def test_a_timeout_is_not_retried(monkeypatch):
    """A timeout means the server is there and busy. Retrying makes the caller
    wait the whole ceiling twice — an 8s search took 17."""
    import requests

    attempts = []

    def post(url, payload, timeout):
        attempts.append(timeout)
        raise requests.exceptions.ReadTimeout("too slow")

    e = _embedder(monkeypatch, post)
    assert e.embed("q", timeout=8.0) is None
    assert attempts == [8.0], f"retried a timeout: {attempts}"


def test_a_dead_server_is_restarted_and_retried_once(monkeypatch):
    """Ollama can be OOM-killed mid-run; autostart used to run only at
    startup, so the rest of the run silently produced no vectors."""
    import requests

    calls = {"post": 0, "preflight": 0}

    def post(url, payload, timeout):
        calls["post"] += 1
        if calls["post"] == 1:
            raise requests.exceptions.ConnectionError("refused")
        return _Resp(200, {"embeddings": [[0.3]]})

    e = retrieval.Embedder()

    class Session:
        def post(self, url, json=None, timeout=None):
            return post(url, json, timeout)

    monkeypatch.setattr(e, "_http", lambda: Session())

    def preflight():
        calls["preflight"] += 1
        return True

    monkeypatch.setattr(e, "_preflight", preflight)
    assert e.embed("x") == [0.3]
    assert calls["post"] == 2 and calls["preflight"] >= 2


def test_a_disabled_embedder_re_arms_after_the_cooldown(monkeypatch):
    """A `magi ui` process lives for days. Staying disabled forever meant one
    blip took vector search out until the server was restarted."""
    import requests

    e = _embedder(monkeypatch, lambda u, p, t: (_ for _ in ()).throw(
        requests.exceptions.ReadTimeout("slow")))
    assert e.embed("q", timeout=1.0) is None
    assert e.available is False
    assert e.embed("q", timeout=1.0) is None      # still cooling down

    e._disabled_at -= retrieval.DISABLED_COOLDOWN + 1
    ok = []
    monkeypatch.setattr(e, "_http", lambda: type("S", (), {
        "post": staticmethod(lambda url, json=None, timeout=None:
                             (ok.append(1), _Resp(200, {"embeddings": [[9.0]]}))[1])})())
    assert e.embed("q") == [9.0]


def test_the_batch_size_is_configurable(monkeypatch):
    monkeypatch.setattr(retrieval, "load_config", lambda: {"ollama": {"embed_batch": 4}})
    assert retrieval.Embedder().batch == 4
    monkeypatch.setattr(retrieval, "load_config", lambda: {"ollama": {"embed_batch": "junk"}})
    assert retrieval.Embedder().batch == retrieval.EMBED_BATCH


# --------------------------------------------------------------------------
# bm25 does not pay for the vector stack
# --------------------------------------------------------------------------

def test_bm25_only_skips_the_sqlite_vec_load(tmp_path, monkeypatch):
    db = tmp_path / "index.db"
    db.write_bytes(b"")
    loaded = []
    real_import = __import__

    def spy(name, *a, **k):
        if name == "sqlite_vec":
            loaded.append(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr("builtins.__import__", spy)
    conn, vec = retrieval.open_db(db, create=True, want_vectors=False)
    conn.close()
    assert vec is False and loaded == []


# --------------------------------------------------------------------------
# job log fan-out: bounded, and the terminal message always lands
# --------------------------------------------------------------------------

def test_a_stalled_listener_cannot_grow_without_bound():
    q: asyncio.Queue = asyncio.Queue(maxsize=8)
    for i in range(500):
        jobs_mod._offer(q, {"type": "log", "line": f"line {i}"})
    assert q.qsize() == 8


def test_the_oldest_message_is_dropped_not_the_newest():
    """`stream_logs` closes the connection on the terminal status message —
    always the newest. Dropping that would hang the stream forever."""
    q: asyncio.Queue = asyncio.Queue(maxsize=4)
    for i in range(20):
        jobs_mod._offer(q, {"type": "log", "line": f"line {i}"})
    jobs_mod._offer(q, {"type": "status", "status": "completed"})
    drained = [q.get_nowait() for _ in range(q.qsize())]
    assert drained[-1] == {"type": "status", "status": "completed"}
    assert drained[0]["line"] == "line 17"


# --------------------------------------------------------------------------
# job archive: concurrent writers must not eat each other's records
# --------------------------------------------------------------------------

def test_concurrent_archive_writes_keep_every_record(tmp_path, monkeypatch):
    """Append-then-compact is a read-modify-write. Unlocked, two jobs
    finishing together could both append, both read, and both rewrite — the
    second rewrite dropping the first's record. Under load it emptied the
    file."""
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "cfg"))
    (tmp_path / "cfg").mkdir()
    tm = jobs_mod.TaskManager(max_history=200)
    # Compact aggressively so the dangerous path runs on nearly every write.
    monkeypatch.setattr(jobs_mod, "MAX_ARCHIVE_BYTES", 2_000)
    monkeypatch.setattr(jobs_mod, "ARCHIVE_KEEP_RECORDS", 40)

    def persist(i):
        job = jobs_mod.Job(job_id=f"j{i:03d}", command=["x"], workspace=str(tmp_path))
        job.archive_path = tm._persist_file()
        job.status = "completed"
        job.append_log(f"payload {i} " + "y" * 80)
        tm._persist_job(job)

    threads = [threading.Thread(target=persist, args=(i,)) for i in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    path = tm._persist_file()
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for line in lines:
        json.loads(line)          # every surviving line must be whole JSON
    assert len(lines) >= 40 - jobs_mod.ARCHIVE_KEEP_RECORDS
    assert len(lines) <= 41


def test_a_jobs_archive_destination_is_fixed_when_it_is_created(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "first"))
    tm = jobs_mod.TaskManager()
    job = jobs_mod.Job(job_id="abc", command=["x"], workspace=str(tmp_path))
    job.archive_path = tm._persist_file()
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "second"))
    assert job.archive_path == tmp_path / "first" / "ui-jobs.jsonl"


# --------------------------------------------------------------------------
# progress reporting
# --------------------------------------------------------------------------

def test_progress_is_throttled_but_always_reports_the_end(capsys):
    p = retrieval._Progress()
    p.start("backfilling vectors for 100 chunks")
    for i in range(20):
        p.tick(f"backfill: {i}")
    p.tick("backfill: 100/100", force=True)
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].endswith("backfilling vectors for 100 chunks")
    assert lines[-1].endswith("backfill: 100/100")
    assert len(lines) < 10, "throttling let every tick through"


def test_quiet_progress_says_nothing(capsys):
    p = retrieval._Progress(quiet=True)
    p.start("x")
    p.tick("y", force=True)
    assert capsys.readouterr().out == ""
