"""Unit and API integration tests for MAGI WebUI."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from magi.ui.api import create_app
from magi.ui.jobs import task_manager


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Isolate MAGI_CONFIG_HOME to prevent polluting user registry
    cfg_dir = tmp_path / "magicfg"
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(cfg_dir))

    # Create dummy workspace
    ws = tmp_path / "test-topic"
    ws.mkdir(parents=True)
    (ws / "config.yaml").write_text("topic: test-topic\n", encoding="utf-8")
    (ws / "wiki" / "concepts").mkdir(parents=True)
    (ws / "wiki" / "references").mkdir(parents=True)
    (ws / "output").mkdir(parents=True)
    (ws / "inbox" / "radar").mkdir(parents=True)
    (ws / "raw").mkdir(parents=True)

    # Seed concept
    (ws / "wiki" / "concepts" / "test-concept.md").write_text(
        "---\ntitle: Test Concept\ntype: concept\n---\nContent about test concept.\n",
        encoding="utf-8",
    )

    # Seed radar digest
    digest_file = ws / "inbox" / "radar" / "2026-08-18-digest.md"
    digest_file.write_text(
        "---\ndate: 2026-08-18\nstatus: pending-review\n---\n# Literature Digest\n\n- Paper 1\n",
        encoding="utf-8",
    )

    # Seed raw backlog file
    (ws / "raw" / "uncompiled-source.md").write_text("# Raw Note\n", encoding="utf-8")

    # Seed graph database
    graph_db = ws / "output" / "graph.db"
    conn = sqlite3.connect(graph_db)
    conn.executescript(
        """
        CREATE TABLE nodes(id TEXT PRIMARY KEY, path TEXT, title TEXT, type TEXT, category TEXT, summary TEXT, created TEXT, updated TEXT);
        CREATE TABLE edges(source_id TEXT, target_id TEXT, type TEXT);
        CREATE TABLE claims(id TEXT PRIMARY KEY, doc_id TEXT, text TEXT, status TEXT);
        CREATE TABLE evidence(claim_id TEXT, source_type TEXT, source TEXT, quote TEXT);
        INSERT INTO nodes VALUES('wiki/concepts/test-concept', 'wiki/concepts/test-concept.md', 'Test Concept', 'concept', NULL, 'Summary', '2026-08-18', '2026-08-18');
        INSERT INTO claims VALUES('c1', 'wiki/concepts/test-concept.md', 'Claim text 1', 'verified');
        INSERT INTO evidence VALUES('c1', 'local_wiki', 'wiki/concepts/test-concept.md', 'Content about test concept.');
        """
    )
    conn.close()

    # Seed retrieval index database
    index_db = ws / "output" / "index.db"
    iconn = sqlite3.connect(index_db)
    iconn.executescript(
        """
        CREATE TABLE chunks(id INTEGER PRIMARY KEY, path TEXT, collection TEXT, heading TEXT, start_line INT, end_line INT, content TEXT);
        CREATE VIRTUAL TABLE chunks_fts USING fts5(content, content='chunks', content_rowid='id');
        INSERT INTO chunks VALUES(1, 'wiki/concepts/test-concept.md', 'concepts', 'Test Concept', 1, 10, 'Content about test concept.');
        INSERT INTO chunks_fts(rowid, content) VALUES(1, 'Content about test concept.');
        """
    )
    iconn.close()

    app = create_app()
    client = TestClient(app)
    client.test_workspace = ws
    return client


def test_status_endpoint(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "version" in data
    assert "active_jobs_count" in data
    assert "doctor_ok" in data


def test_kb_registry_flow(client):
    ws = client.test_workspace

    # Register
    res = client.post("/api/kb/register", json={"path": str(ws), "name": "test-ws", "enabled": True})
    assert res.status_code == 200
    assert res.json()["name"] == "test-ws"

    # List
    res = client.get("/api/kb")
    assert res.status_code == 200
    kbs = res.json()["kbs"]
    assert any(k["name"] == "test-ws" for k in kbs)

    # Toggle
    res = client.post("/api/kb/test-ws/toggle", json={"enabled": False})
    assert res.status_code == 200
    assert res.json()["enabled"] is False

    # Unregister
    res = client.delete("/api/kb/test-ws")
    assert res.status_code == 200
    assert res.json()["deleted"] is True

    # Confirm unregister
    res = client.get("/api/kb")
    kbs = res.json()["kbs"]
    assert not any(k["name"] == "test-ws" for k in kbs)


def test_doctor_endpoint(client):
    res = client.get("/api/doctor")
    assert res.status_code == 200
    data = res.json()
    assert "doctor" in data
    assert any(d["tool"] == "magi" for d in data["doctor"])


def test_workspace_sync_and_introspection(client):
    ws = str(client.test_workspace)

    # Sync
    res = client.get(f"/api/workspace/sync?workspace={ws}")
    assert res.status_code == 200
    data = res.json()
    assert "cores" in data
    assert "melchior" in data["cores"]

    # Claims
    res = client.get(f"/api/workspace/claims?workspace={ws}")
    assert res.status_code == 200
    claims_data = res.json()
    assert claims_data["total"] >= 1
    assert claims_data["claims"][0]["id"] == "c1"

    # Backlog
    res = client.get(f"/api/workspace/backlog?workspace={ws}")
    assert res.status_code == 200
    backlog_data = res.json()
    assert backlog_data["count"] >= 1

    # Radar status
    res = client.get(f"/api/workspace/radar?workspace={ws}")
    assert res.status_code == 200
    radar_data = res.json()
    assert "2026-08-18-digest.md" in radar_data["pending_digests"]

    # Radar digest read
    res = client.get(f"/api/workspace/radar/digest?file=2026-08-18-digest.md&workspace={ws}")
    assert res.status_code == 200
    assert "Literature Digest" in res.json()["content"]

    # Radar digest traversal protection
    res = client.get(f"/api/workspace/radar/digest?file=../../CLAUDE.md&workspace={ws}")
    assert res.status_code in (400, 404)


def test_workspace_search(client):
    ws = str(client.test_workspace)
    res = client.get(f"/api/workspace/search?q=test+concept&mode=bm25&workspace={ws}")
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) >= 1
    assert "test-concept" in data["results"][0]["path"]


def test_graph_sql_guard(client):
    ws = str(client.test_workspace)

    # Valid SELECT
    res = client.get(f"/api/workspace/graph/query?sql=SELECT+*+FROM+nodes&workspace={ws}")
    assert res.status_code == 200
    data = res.json()
    assert len(data["results"]) >= 1

    # Valid SELECT containing keywords in string literals
    res = client.get(f"/api/workspace/graph/query?sql=SELECT+*+FROM+nodes+WHERE+title='INSERT'&workspace={ws}")
    assert res.status_code == 200

    res = client.get(f"/api/workspace/graph/query?sql=SELECT+*+FROM+nodes+WHERE+summary+LIKE+'%update%'&workspace={ws}")
    assert res.status_code == 200

    # Valid comments before SELECT
    res = client.get(f"/api/workspace/graph/query?sql=%2F*+safe+comment+*%2F+SELECT+*+FROM+nodes&workspace={ws}")
    assert res.status_code == 200

    # Valid CTE (WITH)
    res = client.get(f"/api/workspace/graph/query?sql=WITH+t+AS+(SELECT+id+FROM+nodes)+SELECT+*+FROM+t&workspace={ws}")
    assert res.status_code == 200
    assert len(res.json()["results"]) >= 1

    # Valid recursive CTE
    res = client.get(f"/api/workspace/graph/query?sql=WITH+RECURSIVE+cnt(x)+AS+(SELECT+1+UNION+ALL+SELECT+x%2B1+FROM+cnt+WHERE+x<3)+SELECT+x+FROM+cnt&workspace={ws}")
    assert res.status_code == 200
    assert len(res.json()["results"]) == 3

    # Block non-SELECT (e.g. INSERT)
    res = client.get(f"/api/workspace/graph/query?sql=INSERT+INTO+nodes(id)+VALUES('x')&workspace={ws}")
    assert res.status_code == 400
    assert "Security Guard" in res.json()["detail"]

    # Block DROP
    res = client.get(f"/api/workspace/graph/query?sql=DROP+TABLE+nodes&workspace={ws}")
    assert res.status_code == 400

    # Block embedded DELETE inside WITH or subquery
    res = client.get(f"/api/workspace/graph/query?sql=WITH+t+AS+(SELECT+1)+DELETE+FROM+nodes&workspace={ws}")
    assert res.status_code == 400

    # Block ATTACH
    res = client.get(f"/api/workspace/graph/query?sql=ATTACH+DATABASE+'evil.db'+AS+evil&workspace={ws}")
    assert res.status_code == 400

    # Block semicolon statement stacking with destructive queries
    res = client.get(f"/api/workspace/graph/query?sql=SELECT+*+FROM+nodes;+DROP+TABLE+nodes&workspace={ws}")
    assert res.status_code == 400

    # Non-existent DB
    res = client.get("/api/workspace/graph/query?sql=SELECT+1&workspace=/nonexistent/path")
    assert res.status_code == 404


def test_kb_registry_errors(client):
    # Register invalid path
    res = client.post("/api/kb/register", json={"path": "/nonexistent/path/for/kb", "name": "bad"})
    assert res.status_code == 400

    # Toggle non-existent KB
    res = client.post("/api/kb/unknown-kb-xyz/toggle", json={"enabled": True})
    assert res.status_code == 404

    # Delete non-existent KB
    res = client.delete("/api/kb/unknown-kb-xyz")
    assert res.status_code == 404


def test_jobs_lifecycle(client):
    ws = str(client.test_workspace)

    # Raw argv is no longer a thing — the old body shape must be rejected
    res = client.post("/api/jobs", json={"command": ["--version"], "workspace": ws})
    assert res.status_code == 422

    # Unknown op rejected by the whitelist
    res = client.post("/api/jobs", json={"op": "rm-rf", "kb": ws})
    assert res.status_code == 400

    # Danger op without server-side confirm rejected
    res = client.post("/api/jobs", json={"op": "migrate", "kb": ws})
    assert res.status_code == 400
    assert "confirm" in res.json()["detail"]

    # Undeclared param rejected
    res = client.post("/api/jobs", json={"op": "stats", "kb": ws, "params": {"nuke": True}})
    assert res.status_code == 400

    # Whitelisted op runs
    res = client.post("/api/jobs", json={"op": "stats", "kb": ws})
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert res.json()["op"] == "stats"

    job_data = {}
    for _ in range(60):
        job_data = client.get(f"/api/jobs/{job_id}").json()
        if job_data.get("status") in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.25)
    assert job_data.get("status") in ("completed", "failed", "cancelled")
    assert len(job_data.get("logs", [])) > 0

    # SSE streaming test with replayed logs
    res = client.get(f"/api/jobs/{job_id}/stream")
    assert res.status_code == 200
    assert "data:" in res.text

    # List jobs
    res = client.get("/api/jobs")
    assert res.status_code == 200
    assert any(j["id"] == job_id for j in res.json()["jobs"])

    # Ops catalog drives the frontend
    ops = client.get("/api/ops").json()["ops"]
    op_ids = {o["op"] for o in ops}
    assert {"index", "graph-build", "stats", "migrate", "radar-install-schedule"} <= op_ids
    assert all(o.get("label_i18n") for o in ops)
    assert all(o["danger"] for o in ops if o["op"] in ("setup", "migrate", "pm-init"))

    # Non-existent job
    assert client.get("/api/jobs/nonexistent-id").status_code == 404
    assert client.post("/api/jobs/nonexistent-id/cancel").status_code == 400


def test_job_persistence_survives_in_archive(client):
    ws = str(client.test_workspace)
    res = client.post("/api/jobs", json={"op": "stats", "kb": ws})
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    for _ in range(60):
        jobs = client.get("/api/jobs").json()["jobs"]
        if all(j["status"] not in ("pending", "running") for j in jobs):
            break
        time.sleep(0.25)

    archive = Path(os.environ["MAGI_CONFIG_HOME"]) / "ui-jobs.jsonl"
    assert archive.is_file(), "finished jobs must be persisted to the config home"
    ids = [json.loads(line).get("id")
           for line in archive.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert job_id in ids


def test_taskmanager_concurrency_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "cfg"))
    from magi.ui.jobs import Job, JobConflict, TaskManager

    tm = TaskManager()
    busy_ws = str(tmp_path / "ws-a")
    fake = Job("fakejob00001", ["index"], busy_ws, op_id="index", scope="kb")
    fake.status = "running"
    tm._jobs[fake.id] = fake

    # same-KB second job blocked
    with pytest.raises(JobConflict):
        tm.create_job(["stats"], workspace=busy_ws, op_id="stats", scope="kb")
    # global op blocked while anything runs
    with pytest.raises(JobConflict):
        tm.create_job(["setup"], workspace=str(tmp_path / "other"), op_id="setup", scope="global")
    # anything blocked while a global op runs
    fake.scope = "global"
    with pytest.raises(JobConflict):
        tm.create_job(["stats"], workspace=str(tmp_path / "other"), op_id="stats", scope="kb")
    fake.scope = "kb"
    # global cap of 3
    for i in range(2):
        extra = Job(f"fakejob0000{i + 2}", ["index"], str(tmp_path / f"ws-{i}"), op_id="index", scope="kb")
        extra.status = "running"
        tm._jobs[extra.id] = extra
    with pytest.raises(JobConflict):
        tm.create_job(["stats"], workspace=str(tmp_path / "ws-z"), op_id="stats", scope="kb")


def test_docs_and_static(client):
    # Docs - default
    res = client.get("/api/docs/readme")
    assert res.status_code == 200
    data = res.json()
    assert "readme_zh" in data
    assert "readme_en" in data
    assert "content" in data
    assert "lang" in data

    # Docs - localized Chinese
    res_zh = client.get("/api/docs/readme?lang=zh")
    assert res_zh.status_code == 200
    data_zh = res_zh.json()
    assert data_zh["lang"] == "zh"
    assert data_zh["content"] == data_zh["readme_zh"]

    # Docs - localized English
    res_en = client.get("/api/docs/readme?lang=en")
    assert res_en.status_code == 200
    data_en = res_en.json()
    assert data_en["lang"] == "en"
    assert data_en["content"] == data_en["readme_en"]

    # Docs - case-insensitive and prefix variations
    for param in ("EN", "En", "en-US", "english"):
        r = client.get(f"/api/docs/readme?lang={param}")
        assert r.status_code == 200
        d = r.json()
        assert d["lang"] == "en"
        assert d["content"] == d["readme_en"]

    for param in ("ZH", "zh-CN", "chinese", "other"):
        r = client.get(f"/api/docs/readme?lang={param}")
        assert r.status_code == 200
        d = r.json()
        assert d["lang"] == "zh"
        assert d["content"] == d["readme_zh"]

    res_cmd = client.get("/api/docs/commands")
    assert res_cmd.status_code == 200
    assert len(res_cmd.json()["commands"]) > 10

    # Static assets
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "MAGI" in res_root.text
    assert "lang-toggle" in res_root.text
    assert "data-i18n" in res_root.text
    assert "Melchior" in res_root.text
    assert "Balthasar" in res_root.text
    assert "Casper" in res_root.text

    res_css = client.get("/styles.css")
    assert res_css.status_code == 200
    assert ".lang-toggle" in res_css.text
    assert ".lang-pill" in res_css.text

    res_js = client.get("/app.js")
    assert res_js.status_code == 200
    assert "setLanguage" in res_js.text
    assert "I18N" in res_js.text

    res_vendor = client.get("/vendor/marked.min.js")
    assert res_vendor.status_code == 200


def test_i18n_dictionary_symmetry_and_completeness(client):
    import re
    from pathlib import Path

    res_js = client.get("/app.js")
    assert res_js.status_code == 200
    js = res_js.text

    # Parse ZH and EN dictionary blocks
    zh_match = re.search(r"zh:\s*\{(.*?)\n\s*\},", js, re.DOTALL)
    en_match = re.search(r"en:\s*\{(.*?)\n\s*\},", js, re.DOTALL)
    assert zh_match is not None
    assert en_match is not None

    zh_keys = set(re.findall(r"^\s*([a-zA-Z0-9_]+)\s*:", zh_match.group(1), re.MULTILINE))
    en_keys = set(re.findall(r"^\s*([a-zA-Z0-9_]+)\s*:", en_match.group(1), re.MULTILINE))

    assert len(zh_keys) > 100
    assert zh_keys == en_keys, f"i18n key mismatch: ZH-only={zh_keys - en_keys}, EN-only={en_keys - zh_keys}"

    # Verify all direct t("...") calls in app.js exist in dictionary
    direct_t_keys = set(re.findall(r'\bt\(["\']([a-zA-Z0-9_]+)["\']', js))
    missing_direct = direct_t_keys - zh_keys
    assert not missing_direct, f"Direct t() keys missing in dictionary: {missing_direct}"

    # Verify all HTML data-i18n keys exist in translation dictionary
    res_html = client.get("/")
    assert res_html.status_code == 200
    html = res_html.text

    html_i18n = set(re.findall(r'data-i18n="([^"]+)"', html))
    html_ph = set(re.findall(r'data-i18n-placeholder="([^"]+)"', html))
    html_title = set(re.findall(r'data-i18n-title="([^"]+)"', html))
    all_html_keys = html_i18n | html_ph | html_title

    missing_keys = all_html_keys - zh_keys
    assert not missing_keys, f"HTML attributes missing in i18n dictionary: {missing_keys}"

    # Verify danger actions keys exist
    danger_actions = set(re.findall(r'data-action="([^"]+)"', html))
    for act in danger_actions:
        assert f"danger_{act}_title" in zh_keys, f"Missing danger title key: danger_{act}_title"
        assert f"danger_{act}_desc" in zh_keys, f"Missing danger desc key: danger_{act}_desc"

    # Verify op task keys exist
    op_keys = set(re.findall(r'data-op="([^"]+)"', html))
    for op in op_keys:
        op_k = f"op_{op}" if not op.startswith("op_") else op
        assert op_k in zh_keys, f"Missing op key: {op_k}"

    # Verify terminology abstraction in standard UI cards/banners (no raw Beads / bd / graph.db)
    # Check that visible text labels in index.html don't expose low-level jargon
    assert "Beads CLI not found" not in html
    assert "Beads" not in html
    assert "bd " not in html
    assert "graph.db" not in html


def test_pm_task_engine_abstraction(client):
    ws = str(client.test_workspace)
    res = client.get(f"/api/workspace/pm?workspace={ws}")
    assert res.status_code == 200
    data = res.json()
    assert "task_engine_ready" in data
    assert "beads_available" in data
    assert data["task_engine_ready"] == data["beads_available"]


def test_readme_docs_edge_cases(client):
    # Empty string parameter
    r = client.get("/api/docs/readme?lang=")
    assert r.status_code == 200
    assert r.json()["lang"] == "zh"

    # Whitespace parameter
    r = client.get("/api/docs/readme?lang=%20%20")
    assert r.status_code == 200
    assert r.json()["lang"] == "zh"

    # Prefix match English variations
    for param in ("EN", "en_US", "en-GB", "english"):
        r = client.get(f"/api/docs/readme?lang={param}")
        assert r.status_code == 200
        assert r.json()["lang"] == "en"

    # Prefix match Chinese variations
    for param in ("ZH", "zh_CN", "zh-TW", "chinese", "other"):
        r = client.get(f"/api/docs/readme?lang={param}")
        assert r.status_code == 200
        assert r.json()["lang"] == "zh"



def test_markdown_claims_fallback(tmp_path, client):
    # Create workspace without graph.db
    ws2 = tmp_path / "test-topic-fallback"
    ws2.mkdir(parents=True)
    (ws2 / "wiki" / "concepts").mkdir(parents=True)
    card = ws2 / "wiki" / "concepts" / "claim-card.md"
    card.write_text(
        """---
title: Claim Card
type: concept
---

<!-- magi:claims
CLAIM: Fallback claim extracted from markdown
EVIDENCE: Verified by direct experiment
SOURCE: wiki/references/test.md
STATUS: verified
-->
""",
        encoding="utf-8",
    )

    res = client.get(f"/api/workspace/claims?workspace={ws2}")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["verified"] == 1
    assert "Fallback claim" in data["claims"][0]["text"]


def test_sql_advanced_guards(client):
    ws = str(client.test_workspace)

    # PRAGMA table_info
    res = client.get(f"/api/workspace/graph/query?sql=PRAGMA+table_info(nodes)&workspace={ws}")
    assert res.status_code == 200
    assert len(res.json()["results"]) >= 1

    # EXPLAIN query
    res = client.get(f"/api/workspace/graph/query?sql=EXPLAIN+QUERY+PLAN+SELECT+*+FROM+nodes&workspace={ws}")
    assert res.status_code == 200

    # Semicolon in string literal
    res = client.get(f"/api/workspace/graph/query?sql=SELECT+*+FROM+nodes+WHERE+title='test;+not+stacked'&workspace={ws}")
    assert res.status_code == 200

    # Semicolon before a comment
    res = client.get(f"/api/workspace/graph/query?sql=SELECT+*+FROM+nodes;+--+innocent+comment&workspace={ws}")
    assert res.status_code == 200


def test_radar_path_traversal_variations(client):
    ws = str(client.test_workspace)

    # Sibling directory escape attempt
    res = client.get(f"/api/workspace/radar/digest?file=../radar_sibling/evil.md&workspace={ws}")
    assert res.status_code == 400

    # Deep parent escape attempt
    res = client.get(f"/api/workspace/radar/digest?file=../../../../../../etc/passwd&workspace={ws}")
    assert res.status_code == 400


def test_invalid_workspace_isolation(client):
    # Ensure querying an explicit invalid workspace does not fall back to cwd
    nonexistent = "/nonexistent/custom/topic"
    res = client.get(f"/api/workspace/graph/query?sql=SELECT+*+FROM+nodes&workspace={nonexistent}")
    assert res.status_code == 404
    assert "Knowledge graph database not found" in res.json()["detail"]

    res_search = client.get(f"/api/workspace/search?q=test&workspace={nonexistent}")
    assert res_search.status_code == 200
    # unified contract: the API relays the CLI's exact error envelope
    assert "no index at output/index.db" in res_search.json().get("error", "")


def test_task_manager_pruning_and_ring_buffer(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "cfg"))
    from magi.ui.jobs import TaskManager

    def _drain(tm):
        for _ in range(80):
            if all(j.status not in ("pending", "running") for j in tm._jobs.values()):
                return
            time.sleep(0.25)

    tm = TaskManager(max_history=3)
    # Distinct workspaces — the concurrency gate rejects same-KB parallelism
    for i in range(3):
        tm.create_job(command=["--version"], workspace=str(tmp_path / f"ws{i}"), name=f"Job {i}")
    _drain(tm)
    j4 = tm.create_job(command=["--version"], workspace=str(tmp_path / "ws3"), name="Job 4")
    _drain(tm)

    # Live map is pruned to max_history; the newest job survives
    assert len(tm._jobs) <= 3
    assert j4.id in tm._jobs

    # Test ring buffer line limit
    j_ring = tm.create_job(command=["--version"], workspace=str(tmp_path / "ws-ring"), name="Ring Job")
    for i in range(2500):
        j_ring.append_log(f"log line {i}")
    assert len(j_ring.logs) == 2000
    assert j_ring.logs[-1] == "log line 2499"


def test_language_detection_and_js_mechanics(client):
    res_js = client.get("/app.js")
    assert res_js.status_code == 200
    js = res_js.text

    # Verify language detection handles prefix matching safely
    assert "startsWith(\"zh\")" in js
    assert "startsWith(\"en\")" in js

    # Verify workspace select re-rendering helper
    assert "renderWorkspaceSelect" in js

    # Verify doctor modal re-rendering on language switch
    assert "if (els.doctorModal && els.doctorModal.classList.contains(\"open\"))" in js


def test_eva_nerv_theme_architecture_and_css_validity(client):
    res_css = client.get("/styles.css")
    assert res_css.status_code == 200
    css = res_css.text

    # Verify EVA theme selector exists
    assert '[data-theme="eva"]' in css

    # R1: Verify signature EVA / NERV command bridge color scheme
    # (v1.3.1 visual refactor palette; compare case-insensitively)
    css_l = css.lower()
    # Tactical black base
    assert "#050608" in css_l
    assert "#0c0f14" in css_l
    assert "#12161f" in css_l
    assert "#0d1017" in css_l

    # MAGI Terminal Amber ramp: primary / hover-high / bright accents
    assert "#ff9421" in css_l
    assert "#ffac4e" in css_l
    assert "#ffa51e" in css_l

    # Melchior Cyan (#45d5ea), Balthasar Phosphor Green (#35ef7e), Casper Blood Red (#ff4a57)
    assert "#45d5ea" in css_l
    assert "#35ef7e" in css_l
    assert "#ff4a57" in css_l

    # Corner brackets and tactical accents
    assert '[data-theme="eva"] .card::before' in css
    assert '[data-theme="eva"] .card::after' in css

    # WebKit prefixes, modal backdrops, focus rings, and cross-browser resilience
    assert "-webkit-backdrop-filter" in css
    assert '[data-theme="eva"] select option' in css
    assert '[data-theme="eva"] :focus-visible' in css
    assert '[data-theme="eva"] .modal-backdrop' in css
    assert ".btn-secondary.active" in css
    assert '[data-theme="eva"] .btn-secondary.active' in css

    # R2: Three-Core tactical enhancements
    assert '[data-theme="eva"] #tab-melchior' in css
    assert '[data-theme="eva"] #tab-balthasar' in css
    assert '[data-theme="eva"] #tab-casper' in css
    assert '[data-theme="eva"] #task-ready-val' in css
    assert '[data-theme="eva"] #task-progress-val' in css
    assert '[data-theme="eva"] #task-blocked-val' in css
    assert '[data-theme="eva"] .tab-btn[data-tab="melchior"].active' in css
    assert '[data-theme="eva"] .tab-btn[data-tab="balthasar"].active' in css
    assert '[data-theme="eva"] .tab-btn[data-tab="casper"].active' in css
    assert '[data-theme="eva"] #sync-ratio-badge' in css
    assert '[data-theme="eva"] #active-jobs-badge' in css
    assert '[data-theme="eva"] .status-dot' in css
    assert '[data-theme="eva"] .pane-list' in css
    assert '[data-theme="eva"] .search-hit-card' in css
    assert '[data-theme="eva"] .terminal-container' in css
    assert '[data-theme="eva"] .terminal-body' in css
    assert '[data-theme="eva"] .terminal-btn' in css
    assert '[data-theme="eva"] .terminal-cancel-btn' in css


def test_eva_theme_dom_and_js_mechanics(client):
    res_html = client.get("/")
    assert res_html.status_code == 200
    html = res_html.text

    # Verify MAGI MODE toggle button exists in topbar with proper i18n hooks
    assert 'id="magi-mode-btn"' in html
    assert 'data-i18n="magi_mode_btn"' in html
    assert 'data-i18n-title="magi_mode_btn_title"' in html

    # Verify terminal controls use CSS classes without hardcoded inline background/colors
    assert 'class="terminal-autoscroll-label"' in html
    assert 'class="btn btn-secondary btn-sm terminal-btn terminal-cancel-btn"' in html
    assert 'class="btn btn-secondary btn-sm terminal-btn"' in html

    res_js = client.get("/app.js")
    assert res_js.status_code == 200
    js = res_js.text

    # Verify state, DOM element binding, and theme switcher logic
    assert "magiModeBtn: document.getElementById(\"magi-mode-btn\")" in js
    assert "detectInitialTheme" in js
    assert 'safeStorageSet("magi-mode", "true")' in js
    assert 'safeStorageSet("magi-mode", "false")' in js
    assert 'safeStorageSet("magi-base-theme"' in js
    assert 'els.magiModeBtn.addEventListener("click"' in js

    # Verify rapid theme switching safety: timer stopping and boot sequence cancellation
    assert "startEvaClock" in js
    assert "stopEvaClock" in js
    assert "evaBootTimer = null" in js
    assert "classList.remove(\"active\")" in js
    assert "classList.add(\"is-running\")" in js
    assert "classList.remove(\"is-running\")" in js

    # Ensure applyTheme manages the clock conditionally rather than an unconditional startEvaClock in init
    js_norm = js.replace("\r\n", "\n")
    assert "applyTheme(state.theme);\n  setLanguage(state.lang);\n  loadInitialStatus();" in js_norm

    # Verify deep linking for theme and tabs
    assert "URLSearchParams(window.location.search).get(\"theme\")" in js
    assert "URLSearchParams(window.location.search).get(\"tab\")" in js


def test_i18n_dictionary_symmetry_and_html_coverage(client):
    import re
    res_html = client.get("/")
    assert res_html.status_code == 200
    html = res_html.text

    res_js = client.get("/app.js")
    assert res_js.status_code == 200
    js = res_js.text

    # Extract all HTML data-i18n tags
    html_keys = set(re.findall(r'data-i18n(?:-title|-placeholder)?="([a-zA-Z0-9_]+)"', html))
    assert len(html_keys) > 0
    assert "magi_mode_btn" in html_keys
    assert "magi_mode_btn_title" in html_keys

    # Extract zh and en dictionary blocks
    zh_start = js.find("zh: {")
    en_start = js.find("en: {")
    storage_start = js.find("// Safe localStorage")
    assert zh_start != -1 and en_start != -1 and storage_start != -1

    zh_block = js[zh_start:en_start]
    en_block = js[en_start:storage_start]

    zh_keys = set(re.findall(r'^\s*([a-zA-Z0-9_]+)\s*:', zh_block, re.MULTILINE))
    en_keys = set(re.findall(r'^\s*([a-zA-Z0-9_]+)\s*:', en_block, re.MULTILINE))
    # The block-opening labels themselves ("zh: {" / "en: {") match the key
    # regex but are not translation keys.
    zh_keys.discard("zh")
    en_keys.discard("en")

    # Test dictionary key symmetry
    missing_in_en = zh_keys - en_keys
    missing_in_zh = en_keys - zh_keys
    assert not missing_in_en, f"Keys present in zh but missing in en: {missing_in_en}"
    assert not missing_in_zh, f"Keys present in en but missing in zh: {missing_in_zh}"

    # Test that all HTML keys are covered in translations
    untranslated_zh = html_keys - zh_keys
    untranslated_en = html_keys - en_keys
    assert not untranslated_zh, f"HTML keys missing in zh dictionary: {untranslated_zh}"
    assert not untranslated_en, f"HTML keys missing in en dictionary: {untranslated_en}"


def test_eva_completion_layer_hud_boot_and_tactical_css(client):
    css = client.get("/styles.css").text

    # CRT scanline overlay (opt-in via the glass tuner) + honeycomb watermark
    assert '[data-theme="eva"].crt-on body::before' in css
    assert "data:image/svg+xml" in css

    # Chamfered tactical controls and hazard striping on danger surfaces
    assert "-webkit-clip-path: polygon(" in css
    assert "clip-path: polygon(" in css
    assert "repeating-linear-gradient(-45deg, #ffb000" in css.lower()

    # Motion is opt-in: animations gated behind reduced-motion media query
    assert "@media (prefers-reduced-motion: no-preference)" in css

    # Tri-monolith HUD, core state machine, boot sequence
    assert '[data-theme="eva"] .eva-hud' in css
    assert '[data-theme="eva"] .eva-boot.active' in css
    assert ".eva-core.state-ok.core-mel .eva-core-shape" in css
    assert ".eva-core.state-warn .eva-core-stat" in css
    assert ".eva-core.state-err .eva-core-shape" in css
    assert ".eva-core.state-off .eva-core-shape" in css
    assert ".eva-hex-sync" in css
    assert ".eva-clock" in css
    assert '[data-theme="eva"] .terminal-container.is-running' in css

    html = client.get("/").text
    assert 'id="eva-hud"' in html
    assert 'id="eva-boot"' in html
    assert 'id="eva-clock"' in html
    for el_id in (
        "eva-core-mel", "eva-core-bal", "eva-core-cas",
        "eva-mel-stat", "eva-bal-stat", "eva-cas-stat",
        "eva-mel-detail", "eva-bal-detail", "eva-cas-detail",
        "eva-sync-val", "eva-hud-mode",
    ):
        assert f'id="{el_id}"' in html, f"HUD element #{el_id} missing"
    assert "MELCHIOR" in html and "BALTHASAR" in html and "CASPER" in html

    # Decorative layers must not leak into the accessibility tree
    assert 'id="eva-hud" aria-hidden="true"' in html
    assert 'id="eva-boot" aria-hidden="true"' in html

    js = client.get("/app.js").text
    for sym in ("startEvaClock", "stopEvaClock", "runEvaBoot", "updateEvaHud", "evaCoreState"):
        assert sym in js, f"JS symbol {sym} missing"
    assert 'classList.toggle("eva-alert"' in js
    assert "prefers-reduced-motion" in js


def test_bib_drafts_and_config_endpoints(client):
    ws = client.test_workspace

    # bib: 404 with no cards, entries after creating one
    assert client.get(f"/api/workspace/bib?all=1&workspace={ws}").status_code == 404
    (ws / "wiki" / "references" / "pretko-2020.md").write_text(
        "---\ntitle: Fracton Phases\nauthors: [Michael Pretko]\nyear: 2020\narxiv_id: '2001.01722'\n---\n\nx\n",
        encoding="utf-8")
    data = client.get(f"/api/workspace/bib?all=1&workspace={ws}").json()
    assert data["count"] == 1
    assert data["entries"][0]["bibtex"].startswith("@")
    one = client.get(f"/api/workspace/bib?card=pretko-2020&workspace={ws}").json()
    assert one["entries"][0]["card"] == "pretko-2020"

    # drafts listing
    (ws / "drafts").mkdir()
    (ws / "drafts" / "intro.md").write_text("# 引言草稿\n\n内容。\n", encoding="utf-8")
    d = client.get(f"/api/workspace/drafts?workspace={ws}").json()
    assert d["count"] == 1
    assert d["drafts"][0]["title"] == "引言草稿"

    # config: read whitelisted fields, surgical write preserves comments
    cfg = ws / "config.yaml"
    cfg.write_text("topic: test-topic\n# keep me\nradar:\n  days: 7\n", encoding="utf-8")
    got = client.get(f"/api/workspace/config?workspace={ws}").json()
    vals = {f["key"]: f["value"] for f in got["fields"]}
    assert vals["radar.days"] == 7
    res = client.post("/api/workspace/config",
                      json={"key": "radar.min_relevance", "value": 0.3, "workspace": str(ws)})
    assert res.status_code == 200
    text = cfg.read_text(encoding="utf-8")
    assert "# keep me" in text
    assert "min_relevance: 0.3" in text

    # non-whitelisted key and type mismatch rejected
    assert client.post("/api/workspace/config",
                       json={"key": "tools.pandoc_path", "value": "x", "workspace": str(ws)}).status_code == 400
    assert client.post("/api/workspace/config",
                       json={"key": "radar.days", "value": "seven", "workspace": str(ws)}).status_code == 400


def test_radar_review_write_actions(client):
    ws = client.test_workspace
    f = ws / "inbox" / "radar" / "2026-08-19-digest.md"
    f.write_text(
        "---\ndate: 2026-08-19\nstatus: pending-review\n---\n\n"
        "# Literature Radar — 2026-08-19\n\n"
        "## Sparse Attention at Scale\n\n"
        "- id: `2508.01234` · 2026 · source: arxiv-new:cs.CL · relevance: 0.61\n"
        "- https://arxiv.org/abs/2508.01234\n\n"
        "## Second Paper 论文\n\n"
        "- id: `DOI:10/xyz` · 2025 · source: s2-recommendation\n",
        encoding="utf-8",
    )

    # digest GET returns parsed candidates + review status
    data = client.get(f"/api/workspace/radar/digest?file={f.name}&workspace={ws}").json()
    assert data["status"] == "pending-review"
    assert data["kind"] == "digest"
    assert len(data["candidates"]) == 2
    c0 = data["candidates"][0]
    assert c0["arxiv_id"] == "2508.01234"
    assert c0["relevance"] == 0.61
    assert c0["url"] == "https://arxiv.org/abs/2508.01234"

    # accept-to-inbox writes the queue file
    body = {"file": f.name, "index": 0, "action": "accept-to-inbox", "workspace": str(ws)}
    res = client.post("/api/workspace/radar/candidate", json=body)
    assert res.status_code == 200
    created = res.json()["created"]
    accepted = ws / created
    assert accepted.is_file()
    text = accepted.read_text(encoding="utf-8")
    assert "to-ingest" in text and "2508.01234" in text

    # duplicate accept -> 409; bad index -> 404
    assert client.post("/api/workspace/radar/candidate", json=body).status_code == 409
    assert client.post("/api/workspace/radar/candidate",
                       json={**body, "index": 99}).status_code == 404

    # create-issue is best-effort: env may lack bd or a beads root
    res = client.post("/api/workspace/radar/candidate",
                      json={**body, "index": 1, "action": "create-issue"})
    assert res.status_code in (200, 409, 502, 503)

    # mark-reviewed flips exactly once, then conflicts
    res = client.post("/api/workspace/radar/review",
                      json={"file": f.name, "workspace": str(ws)})
    assert res.status_code == 200
    assert "status: reviewed" in f.read_text(encoding="utf-8")
    res = client.post("/api/workspace/radar/review",
                      json={"file": f.name, "workspace": str(ws)})
    assert res.status_code == 409

    # traversal guard on the write path
    res = client.post("/api/workspace/radar/review",
                      json={"file": "../../config.yaml", "workspace": str(ws)})
    assert res.status_code in (400, 404)


def test_radar_citation_gap_reports_visible(client):
    ws = client.test_workspace
    gap = ws / "inbox" / "radar" / "2026-08-18-citation-gaps.md"
    gap.write_text(
        "---\ndate: 2026-08-18\nstatus: pending-review\n---\n# Citation Gap Scout\n",
        encoding="utf-8",
    )

    res = client.get(f"/api/workspace/radar?workspace={ws}")
    assert res.status_code == 200
    data = res.json()

    assert "2026-08-18-citation-gaps.md" in data["pending_citation_gaps"]
    kinds = {d["name"]: d["kind"] for d in data["digests"]}
    assert kinds["2026-08-18-citation-gaps.md"] == "citation-gap"
    assert kinds["2026-08-18-digest.md"] == "digest"
    # original contract: pending_digests stays digests-only
    assert "2026-08-18-citation-gaps.md" not in data["pending_digests"]

    # sync hints must surface pending citation-gap reports too
    from magi.sync import build_report
    rep = build_report(ws)
    assert any("citation-gap report(s) pending" in h for h in rep["hints"])


def test_sync_hints_card_and_researcher_guidance(client):
    html = client.get("/").text
    assert 'id="sync-hints-card"' in html
    assert 'id="sync-hints-list"' in html
    assert 'data-i18n="hints_title"' in html

    js = client.get("/app.js").text
    # actionable hints pipeline (code-driven, no prose parsing)
    assert "HINT_ACTIONS" in js
    assert "renderSyncHints" in js
    assert "renderSyncHints(rep.hints_structured, rep.hints)" in js
    # researcher-facing guidance & bilingual error mapping
    assert "localizeApiError" in js
    assert "vec_unavailable_hint" in js
    assert "search_no_results_hint" in js
    # README repo-relative images resolve against GitHub raw
    assert "raw.githubusercontent.com/Misaka16384/magi/main/" in js


def test_vendored_marked_is_complete_and_digests_escape_html(client):
    # v1.1.0 shipped a truncated marked.min.js (12.9KB of ~40KB) that failed to
    # parse, silently disabling all markdown rendering. Guard against recurrence.
    res = client.get("/vendor/marked.min.js")
    assert res.status_code == 200
    body = res.text
    assert len(body) > 30000, f"marked.min.js looks truncated ({len(body)} bytes)"
    assert "module.exports" in body[-500:], "marked.min.js does not end cleanly"

    # Digest content is external data (S2/arXiv titles); it must be
    # HTML-escaped before going through marked.parse.
    js = client.get("/app.js").text
    assert "safeMd" in js
    assert 'replace(/</g, "&lt;")' in js


def test_host_allowlist_blocks_dns_rebinding(client):
    # DNS rebinding delivers a foreign Host header to 127.0.0.1; the
    # TrustedHostMiddleware must reject it before any route runs.
    res = client.get("/api/status", headers={"Host": "evil.example.com"})
    assert res.status_code == 400

    for good_host in ("testserver", "127.0.0.1", "localhost", "127.0.0.1:8000"):
        res = client.get("/api/status", headers={"Host": good_host})
        assert res.status_code == 200, f"Host {good_host} should be allowed"


def test_docs_commands_zh(client):
    data = client.get("/api/docs/commands").json()
    assert len(data["commands"]) > 10
    for row in data["commands"]:
        assert row["help_zh"], f"missing help_zh for {row['command']}"
        if row["group"]:
            assert row["group_help_zh"], f"missing group_help_zh for {row['command']}"
    groups = {row["group"] for row in data["commands"] if row["group"]}
    assert groups <= set(data["groups_zh"])
    assert all(v for v in data["groups_zh"].values())


def test_graph_browse_endpoint(client):
    ws = client.test_workspace
    conn = sqlite3.connect(ws / "output" / "graph.db")
    conn.executescript(
        """
        CREATE TABLE tags(node_id TEXT, tag TEXT);
        CREATE TABLE aliases(node_id TEXT, alias TEXT);
        INSERT INTO nodes VALUES('wiki/references/second-card', 'wiki/references/second-card.md', 'Second Card', 'reference', NULL, 'S', '2026-08-18', '2026-08-18');
        INSERT INTO edges VALUES('wiki/concepts/test-concept', 'wiki/references/second-card', 'wikilink');
        INSERT INTO edges VALUES('wiki/concepts/test-concept', 'Ghost Page', 'wikilink');
        INSERT INTO tags VALUES('wiki/concepts/test-concept', 'physics');
        """
    )
    conn.close()

    data = client.get(f"/api/workspace/graph/browse?workspace={ws}").json()
    assert data["view"] == "overview"
    ov = data["results"]
    assert ov["nodes_by_type"]["concept"] == 1
    assert ov["nodes_by_type"]["reference"] == 1
    assert ov["edges_by_type"]["wikilink"] == 2
    assert ov["broken_links"] >= 1

    data = client.get(f"/api/workspace/graph/browse?view=nodes&q=second&workspace={ws}").json()
    assert data["count"] == 1
    assert data["results"][0]["id"] == "wiki/references/second-card"

    data = client.get(
        f"/api/workspace/graph/browse?view=links&node=wiki/concepts/test-concept&workspace={ws}"
    ).json()
    assert data["results"]["node"]["title"] == "Test Concept"
    ghost = [e for e in data["results"]["outgoing"] if e["target_id"] == "Ghost Page"]
    assert ghost and ghost[0]["title"] is None

    data = client.get(f"/api/workspace/graph/browse?view=broken&workspace={ws}").json()
    assert any(r["target_text"] == "Ghost Page" for r in data["results"])

    assert client.get(f"/api/workspace/graph/browse?view=bogus&workspace={ws}").status_code == 400

    res = client.get("/api/workspace/graph/browse?workspace=/nonexistent/path")
    assert res.status_code == 404
    assert "Knowledge graph database not found" in res.json()["detail"]


def test_graph_browse_map_view(client):
    ws = client.test_workspace
    # Seed edges locally: the client fixture is function-scoped, so nothing
    # from other tests' seeding carries over.
    conn = sqlite3.connect(ws / "output" / "graph.db")
    conn.executescript(
        """
        INSERT INTO nodes VALUES('wiki/references/map-card', 'wiki/references/map-card.md', 'Map Card', 'reference', NULL, 'M', '2026-08-18', '2026-08-18');
        INSERT INTO nodes VALUES('tag:physics', NULL, 'physics', 'tag', NULL, NULL, '2026-08-18', '2026-08-18');
        INSERT INTO edges VALUES('wiki/concepts/test-concept', 'wiki/references/map-card', 'wikilink');
        INSERT INTO edges VALUES('wiki/concepts/test-concept', 'Ghost Page', 'wikilink');
        INSERT INTO edges VALUES('wiki/concepts/test-concept', 'tag:physics', 'has_tag');
        """
    )
    conn.close()

    data = client.get(f"/api/workspace/graph/browse?view=map&workspace={ws}").json()
    assert data["view"] == "map"
    results = data["results"]
    assert results["truncated"] is False
    assert data["count"] == len(results["nodes"])
    by_id = {n["id"]: n for n in results["nodes"]}
    assert set(by_id) == {"wiki/concepts/test-concept", "wiki/references/map-card",
                          "Ghost Page"}
    assert by_id["Ghost Page"]["type"] == "ghost"
    assert by_id["wiki/concepts/test-concept"]["degree"] == 2
    edges = {(e["source"], e["target"], e["type"]) for e in results["edges"]}
    assert ("wiki/concepts/test-concept", "Ghost Page", "wikilink") in edges
    assert ("wiki/concepts/test-concept", "wiki/references/map-card", "wikilink") in edges

    data = client.get(f"/api/workspace/graph/browse?view=map&tags=true&workspace={ws}").json()
    by_id = {n["id"]: n for n in data["results"]["nodes"]}
    assert by_id["tag:physics"]["type"] == "tag"
    assert by_id["tag:physics"]["degree"] == 1


def test_radar_digest_authors(client):
    ws = client.test_workspace
    f = ws / "inbox" / "radar" / "2026-08-20-digest.md"
    f.write_text(
        "---\ndate: 2026-08-20\nstatus: pending-review\n---\n\n"
        "# Literature Radar — 2026-08-20\n\n"
        "## Paper With Authors\n\n"
        "- id: `2508.09999` · 2026 · source: arxiv-new:cs.CL\n"
        "- authors: Alice One, Bob Two\n"
        "- https://arxiv.org/abs/2508.09999\n\n"
        "## Paper Without Authors\n\n"
        "- id: `DOI:10/abc` · 2025 · source: s2-recommendation\n",
        encoding="utf-8",
    )

    data = client.get(f"/api/workspace/radar/digest?file={f.name}&workspace={ws}").json()
    cands = data["candidates"]
    assert len(cands) == 2
    assert cands[0]["authors"] == ["Alice One", "Bob Two"]
    assert cands[1]["authors"] == []


def test_ui_backgrounds_endpoint(client):
    data = client.get("/api/ui/backgrounds").json()
    assert data["source"] == "bundled"
    assert data["base_url"] == "/backgrounds/"
    for variant in ("blue", "red"):
        entries = data["variants"][variant]
        assert entries
        for e in entries:
            assert e["file"] and e["w"] and e["h"] and e["aspect"]

    override = Path(os.environ["MAGI_CONFIG_HOME"]) / "ui-backgrounds" / "blue"
    override.mkdir(parents=True)
    (override / "x.webp").write_bytes(b"RIFFfake")
    data = client.get("/api/ui/backgrounds").json()
    assert data["source"] == "user"
    assert data["base_url"] == "/ui-bg/"
    assert data["variants"]["blue"] == [
        {"file": "blue/x.webp", "w": None, "h": None, "aspect": None}
    ]


def test_no_cors_headers_emitted(client):
    # Design mandate: no CORS headers at all. JSON-body mutations then force a
    # preflight that always fails cross-origin, making the API CSRF-free.
    res = client.get("/api/status", headers={"Origin": "https://evil.example.com"})
    assert res.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in res.headers.keys()}

    res = client.options(
        "/api/jobs",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in res.headers.keys()}


def _guide_files():
    from magi.guide import docs_dir

    return sorted(docs_dir().glob("guide.*.md"))


def test_guide_endpoint_and_language_fallback(client):
    res = client.get("/api/docs/guide")
    assert res.status_code == 200
    data = res.json()
    assert data["lang"] == "zh"
    assert data["requested"] == "zh"
    assert data["content"].lstrip().startswith("#")
    assert set(data["available"]) >= {"zh", "en"}
    assert data["version"]

    for param, expect in (("en", "en"), ("EN", "en"), ("en-US", "en"), ("zh-CN", "zh"), ("nonsense", "zh")):
        d = client.get(f"/api/docs/guide?lang={param}").json()
        assert d["requested"] == expect
        assert d["content"]


def test_guide_markdown_structure():
    # The reader derives its chapter rail from h2/h3 and its callouts from
    # `[!TAG]` blockquotes — both are contracts between the markdown and app.js.
    import re

    files = _guide_files()
    assert len(files) >= 2, "guide must ship at least zh + en"

    known_tags = {"EXPECT", "FIX", "WARN", "NOTE", "TIP"}
    anchors_by_lang = {}

    for path in files:
        text = path.read_text(encoding="utf-8")
        # Strip fenced blocks: a "## " inside a sample digest is not a chapter.
        body = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

        h2s = re.findall(r"^## (.+)$", body, flags=re.MULTILINE)
        assert len(h2s) >= 10, f"{path.name}: expected a full manual, got {len(h2s)} chapters"

        anchors = []
        for head in h2s:
            m = re.search(r"\{#([A-Za-z0-9_-]+)\}\s*$", head)
            assert m, f"{path.name}: chapter without a stable anchor: {head}"
            anchors.append(m.group(1))
        assert len(anchors) == len(set(anchors)), f"{path.name}: duplicate chapter anchors"
        anchors_by_lang[path.name] = anchors

        for tag in re.findall(r"^> \[!([A-Z]+)\]", body, flags=re.MULTILINE):
            assert tag in known_tags, f"{path.name}: unknown callout tag [!{tag}]"

        assert re.search(r"^> \[!EXPECT\]", body, flags=re.MULTILINE), (
            f"{path.name}: a scenario manual must state expected outcomes"
        )
        assert re.search(r"^> \[!FIX\]", body, flags=re.MULTILINE), (
            f"{path.name}: a scenario manual must state what to do when it fails"
        )

    # Translations must stay structurally interchangeable: same chapters, same
    # anchors, same order — the rail and any deep link work in either language.
    distinct = {tuple(v) for v in anchors_by_lang.values()}
    assert len(distinct) == 1, f"guide translations disagree on chapters: {anchors_by_lang}"


def test_guide_only_cites_real_commands():
    # Locks the manual against CLI drift: every `magi ...` line in a fenced
    # block must resolve to a real entry in the dispatch table.
    import re

    from magi.cli import _COMMANDS

    singles = {k[0] for k in _COMMANDS if len(k) == 1}
    groups = {}
    for key in _COMMANDS:
        if len(key) == 2:
            groups.setdefault(key[0], set()).add(key[1])

    checked = 0
    for path in _guide_files():
        text = path.read_text(encoding="utf-8")
        for block in re.findall(r"```[a-z]*\n(.*?)```", text, flags=re.DOTALL):
            for line in block.splitlines():
                line = line.strip()
                if not line.startswith("magi "):
                    continue
                parts = [t for t in line.split() if t]
                if any(t.startswith(("<", "&lt;")) for t in parts[1:2]):
                    continue  # `magi <command> --help` placeholder
                head = parts[1]
                if head in groups:
                    sub = parts[2] if len(parts) > 2 else ""
                    assert sub in groups[head], f"{path.name}: unknown subcommand: {line}"
                else:
                    assert head in singles, f"{path.name}: unknown command: {line}"
                checked += 1
    assert checked > 40, f"expected the manual to be command-dense, checked only {checked}"


def test_guide_reader_wiring(client):
    html = client.get("/").text
    assert 'data-doc="guide"' in html
    assert 'id="docs-toc-list"' in html
    assert 'class="docs-shell"' in html

    css = client.get("/styles.css").text.lower()
    for rule in (".docs-toc-link", ".doc-callout", ".cal-expect", ".code-wrap", ".copy-btn"):
        assert rule in css, f"missing guide reader style: {rule}"

    js = client.get("/app.js").text
    for fn in ("decorateCallouts", "decorateCodeBlocks", "buildGuideNav", "syncGuideSpy", "currentDocKey"):
        assert fn in js, f"missing guide reader function: {fn}"
    # The callout contract itself, and the anchor syntax the rail depends on.
    assert 'EXPECT: { cls: "expect"' in js
    assert "{#" in js


def test_tab_strip_wraps_instead_of_hiding_tabs(client):
    """A hidden horizontal scroller put tabs out of reach on narrow windows."""
    css = client.get("/styles.css").text
    nav = css[css.index(".tabs-nav {"):]
    nav = nav[:nav.index("}")]
    assert "flex-wrap: wrap" in nav, "the tab strip must wrap, not scroll out of view"
    assert "overflow-x: auto" not in nav, "wrapping removes the need for a hidden scroller"


def test_danger_zone_uses_the_shared_glass_recipe(client):
    css = client.get("/styles.css").text
    block = css[css.index('[data-theme="eva"] .danger-card {'):]
    block = block[:block.index("\n}")]
    assert "backdrop-filter: blur(var(--glass-blur))" in block, (
        "the danger card was the one panel that missed the liquid-glass pass"
    )
    assert "var(--glass-alpha)" in block, "it must follow the tuner like every other panel"
    assert "255, 74, 87" in block, "and keep its red identity"


def test_backdrop_picker_is_wired(client):
    html = client.get("/").text
    for hook in ('id="bg-thumbs"', 'id="bg-shuffle-btn"', 'id="bg-picker-note"'):
        assert hook in html, f"missing backdrop picker hook: {hook}"

    js = client.get("/app.js").text
    for fn in ("bgPicks", "setBgPicks", "renderBgPicker"):
        assert fn in js, f"missing backdrop picker function: {fn}"
    # An explicit pick has to win over aspect matching, or pinning does nothing.
    pool = js[js.index("function bgEligible("):]
    pool = pool[:pool.index("\n  }")]
    assert "bgPicks(variant)" in pool


def test_every_bundled_backdrop_has_a_thumbnail(client):
    import json

    from magi.ui.api import _get_static_dir

    root = _get_static_dir() / "backgrounds"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    total = 0
    for variant, entries in manifest["variants"].items():
        assert entries, f"{variant}: no artwork"
        for e in entries:
            assert e.get("thumb"), f"{variant}/{e['file']}: no thumbnail for the picker"
            thumb = root / e["thumb"]
            assert thumb.is_file(), f"missing thumbnail file: {e['thumb']}"
            size = thumb.stat().st_size
            assert size < 40_000, f"{e['thumb']} is {size}B — thumbnails must stay small"
            total += size
    assert total < 400_000, "the whole thumbnail set should cost less than one full image"


def test_magi_mode_cuts_the_same_corner_off_every_box(client):
    """One shape language: MAGI mode had chamfered buttons and square panels."""
    css = client.get("/styles.css").text
    eva = css[css.index("/* \u2500\u2500 One shape for every box"):]
    eva = eva[:eva.index('[data-theme="eva"] .btn-primary {')]

    # Three scales, all cutting the same two corners.
    for px in (14, 8, 5):
        shape = (f"polygon({px}px 0, 100% 0, 100% calc(100% - {px}px), "
                 f"calc(100% - {px}px) 100%, 0 100%, 0 {px}px)")
        assert eva.count(shape) == 2, f"{px}px group needs the prefixed and plain clip-path"

    for sel in (".card", ".eva-hud-frame", ".modal-window", ".danger-card",
                ".btn", ".icon-btn", ".text-input", ".select-input", ".action-row",
                ".badge", ".stat-pill", ".eva-clock", ".lang-toggle", ".brand-badge"):
        assert f'[data-theme="eva"] {sel},' in eva or f'[data-theme="eva"] {sel} {{' in eva, (
            f"{sel} is still a plain rectangle in MAGI mode"
        )


def test_magi_mode_has_no_rounded_corners_left(client):
    """A 2px radius reads as a rounded box next to a chamfered one."""
    css = client.get("/styles.css").text
    eva = css[css.index('[data-theme="eva"] .topbar {'):]
    strays = [ln.strip() for ln in eva.splitlines()
              if "border-radius" in ln and "border-radius: 0" not in ln]
    assert not strays, f"rounded corners survive in MAGI mode: {strays}"


def test_clipped_panels_keep_their_lift(client):
    """clip-path discards an outer box-shadow; these panels use a filter instead."""
    css = client.get("/styles.css").text
    for sel in ('[data-theme="eva"] .card {', '[data-theme="eva"] .eva-hud-frame {',
                '[data-theme="eva"] .modal-window {', '[data-theme="eva"] .danger-card {'):
        block = css[css.index(sel):]
        block = block[:block.index("\n}")]
        assert "drop-shadow(" in block, f"{sel} lost its depth to the chamfer"
        shadows = [ln.strip() for ln in block.splitlines()
                   if ln.strip().startswith("box-shadow") and "inset" not in ln
                   and "none" not in ln]
        assert not shadows, f"{sel} still paints a shadow the clip would eat: {shadows}"
