"""Contracts for the ingest queue and batch-review endpoints.

The one that matters most is `/api/ingest/enqueue`. It is the browser
extension's only door, this server has no authentication of any kind, and the
argument for that being acceptable is entirely "that endpoint can only append
one line to a queue". These tests are what hold the argument up.
"""

from __future__ import annotations

import inspect
import sqlite3

import pytest
from fastapi.testclient import TestClient

from magi.ui.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "magicfg"))
    ws = tmp_path / "topic"
    for sub in ("wiki/concepts", "wiki/references", "output", "inbox/radar", "raw/papers"):
        (ws / sub).mkdir(parents=True, exist_ok=True)
    (ws / "config.yaml").write_text("topic: t\n", encoding="utf-8")
    conn = sqlite3.connect(ws / "output" / "graph.db")
    conn.executescript(
        "CREATE TABLE nodes(id TEXT PRIMARY KEY, path TEXT, title TEXT, type TEXT,"
        " category TEXT, summary TEXT, created TEXT, updated TEXT);"
        "CREATE TABLE edges(source_id TEXT, target_id TEXT, type TEXT);")
    conn.close()

    c = TestClient(create_app())
    c.ws = ws
    return c


def _stage(ws, *, decision=None, error=None, findings=()):
    """One finished item in a batch, as batch-run would have left it."""
    from magi.ingest import ledger
    from magi.ingest.convert_result import Finding

    req = ledger.enqueue(ws, source_type="arxiv", value="2608.16520")
    batch_id = ledger.start_batch(ws)
    staged = ledger.staging_dir(ws, batch_id) / req
    staged.mkdir(parents=True, exist_ok=True)
    md = staged / "2026-08-21-a-paper.md"
    md.write_text("---\ntitle: A Paper\n---\n\n" + "word " * 200, encoding="utf-8")

    item_id = ledger.record_item(
        ws, batch_id, req_id=req, route="arxiv-html", source_value="2608.16520",
        title="A Paper", staged_md=None if error else str(md), error=error,
        findings=[Finding(*f) for f in findings])
    if decision:
        ledger.record_decision(ws, batch_id, item_id, decision)
    return batch_id, item_id


# --------------------------------------------------------------------------
# Reading the queue
# --------------------------------------------------------------------------

def test_the_queue_endpoint_reports_pending_and_batches(client):
    batch_id, _ = _stage(client.ws)
    data = client.get(f"/api/workspace/ingest/queue?workspace={client.ws}").json()

    assert data["batches"][0]["batch_id"] == batch_id
    assert data["batches"][0]["undecided"] == 1


def test_an_empty_workspace_has_an_empty_queue(client):
    data = client.get(f"/api/workspace/ingest/queue?workspace={client.ws}").json()
    assert data["pending"] == [] and data["batches"] == []


def test_a_batch_comes_back_with_a_preview(client):
    batch_id, item_id = _stage(client.ws)
    data = client.get(
        f"/api/workspace/ingest/batch?batch={batch_id}&workspace={client.ws}").json()

    assert data["items"][0]["item_id"] == item_id
    assert "A Paper" in data["items"][0]["preview"]
    assert data["undecided"] == 1


def test_an_unknown_batch_is_a_404(client):
    r = client.get(f"/api/workspace/ingest/batch?batch=batch-nope&workspace={client.ws}")
    assert r.status_code == 404


def test_a_failed_item_is_shown_rather_than_hidden(client):
    """A conversion that failed is something a reviewer needs to see."""
    batch_id, _ = _stage(client.ws, error="Pandoc conversion failed.")
    data = client.get(
        f"/api/workspace/ingest/batch?batch={batch_id}&workspace={client.ws}").json()

    assert data["items"][0]["error"] == "Pandoc conversion failed."
    assert data["items"][0]["preview"] == ""


def test_findings_reach_the_reviewer(client):
    batch_id, _ = _stage(client.ws,
                         findings=[("figure-count-mismatch", "6 dropped", "flag")])
    data = client.get(
        f"/api/workspace/ingest/batch?batch={batch_id}&workspace={client.ws}").json()
    assert data["items"][0]["findings"][0]["code"] == "figure-count-mismatch"


def test_a_staged_path_outside_the_workspace_is_not_read(client):
    """Containment, the same guard the radar report reader keeps."""
    from magi.ingest import ledger

    outside = client.ws.parent / "secret.md"
    outside.write_text("SHOULD NOT BE READ", encoding="utf-8")
    batch_id = ledger.start_batch(client.ws)
    ledger.record_item(client.ws, batch_id, req_id="r", route="tex",
                       source_value="x", staged_md=str(outside))

    data = client.get(
        f"/api/workspace/ingest/batch?batch={batch_id}&workspace={client.ws}").json()
    assert data["items"][0]["preview"] == ""


# --------------------------------------------------------------------------
# Deciding
# --------------------------------------------------------------------------

def test_approving_is_recorded(client):
    batch_id, item_id = _stage(client.ws)
    r = client.post("/api/workspace/ingest/decide", json={
        "batch_id": batch_id, "item_id": item_id,
        "decision": "approve", "workspace": str(client.ws)})

    assert r.json()["decision"] == "approve"
    data = client.get(
        f"/api/workspace/ingest/batch?batch={batch_id}&workspace={client.ws}").json()
    assert data["undecided"] == 0


def test_rejecting_requeues_on_the_next_route(client):
    """One click means: this conversion is bad, try another way."""
    batch_id, item_id = _stage(client.ws)
    r = client.post("/api/workspace/ingest/decide", json={
        "batch_id": batch_id, "item_id": item_id,
        "decision": "reject", "workspace": str(client.ws)})

    assert r.json()["requeued_on"] == "tex"
    queue = client.get(f"/api/workspace/ingest/queue?workspace={client.ws}").json()
    assert queue["pending"][0]["route"] == "tex"


def test_undo_puts_an_item_back_in_play(client):
    batch_id, item_id = _stage(client.ws, decision="approve")
    client.post("/api/workspace/ingest/decide", json={
        "batch_id": batch_id, "item_id": item_id,
        "decision": "reset", "workspace": str(client.ws)})

    data = client.get(
        f"/api/workspace/ingest/batch?batch={batch_id}&workspace={client.ws}").json()
    assert data["undecided"] == 1


def test_an_unknown_decision_is_refused(client):
    batch_id, item_id = _stage(client.ws)
    r = client.post("/api/workspace/ingest/decide", json={
        "batch_id": batch_id, "item_id": item_id,
        "decision": "maybe", "workspace": str(client.ws)})
    assert r.status_code == 400


def test_deciding_an_unknown_item_is_a_404(client):
    batch_id, _ = _stage(client.ws)
    r = client.post("/api/workspace/ingest/decide", json={
        "batch_id": batch_id, "item_id": "item-nope",
        "decision": "approve", "workspace": str(client.ws)})
    assert r.status_code == 404


# --------------------------------------------------------------------------
# The extension's door: blast radius
# --------------------------------------------------------------------------

def test_enqueue_queues_one_thing(client, monkeypatch):
    monkeypatch.chdir(client.ws)
    r = client.post("/api/ingest/enqueue",
                    json={"value": "https://arxiv.org/abs/2608.16520"})

    assert r.status_code == 200
    body = r.json()
    assert body["source_type"] == "arxiv" and body["value"] == "2608.16520"


def test_enqueue_touches_nothing_outside_the_queue(client, monkeypatch):
    """The entire security argument for an unauthenticated endpoint.

    Everything it creates stays inside output/ingest/ — the queue line and the
    lock guarding concurrent appends to it. Nothing reaches raw/ or wiki/.
    """
    from magi.ingest import ledger

    monkeypatch.chdir(client.ws)
    before = {p for p in client.ws.rglob("*") if p.is_file()}

    client.post("/api/ingest/enqueue", json={"value": "2608.16520"})

    new = {p for p in client.ws.rglob("*") if p.is_file()} - before
    assert ledger.queue_path(client.ws) in new

    ingest_dir = ledger.ingest_dir(client.ws).resolve()
    for path in new:
        assert path.resolve().is_relative_to(ingest_dir), f"escaped the queue: {path}"


def test_enqueue_cannot_reach_an_unregistered_library(client):
    """Closed world: it picks from what exists, it does not invent a target."""
    r = client.post("/api/ingest/enqueue",
                    json={"value": "2608.16520", "library": "NotRegistered"})
    assert r.status_code == 404


def test_enqueue_rejects_an_empty_value(client):
    assert client.post("/api/ingest/enqueue", json={"value": ""}).status_code == 422


def test_the_enqueue_endpoint_cannot_spawn_a_job(client):
    """Not 'it does not today' — the handler imports neither subprocess nor the
    task manager, so there is nothing there for it to reach."""
    import io
    import tokenize

    from magi.ui import api as api_module

    source = inspect.getsource(api_module.create_app)
    start = source.index('@app.post("/api/ingest/enqueue")')
    end = source.index("@app.post", start + 10)
    body = source[start:end]

    # Scan the code, not the prose about the code. The handler's own docstring
    # explains that it reaches no subprocess, and a naive substring search finds
    # that sentence and calls it a violation.
    code_only = []
    for tok in tokenize.generate_tokens(io.StringIO(body.strip()).readline):
        if tok.type not in (tokenize.COMMENT, tokenize.STRING):
            code_only.append(tok.string)
    code = " ".join(code_only)

    for forbidden in ("subprocess", "task_manager", "create_job", "Popen"):
        assert forbidden not in code, f"the enqueue handler can reach {forbidden}"


def test_the_new_ingest_ops_are_not_danger_zone():
    """batch-run writes only to staging; batch-commit refuses undecided batches."""
    from magi.ui.jobs import OPS

    for op in ("ingest-batch-run", "ingest-batch-commit"):
        assert OPS[op]["danger"] is False
        assert OPS[op]["scope"] == "kb"
