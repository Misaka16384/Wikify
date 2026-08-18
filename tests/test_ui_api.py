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

    # Empty command validation error
    res = client.post("/api/jobs", json={"command": [], "workspace": ws})
    assert res.status_code == 422

    # Create a quick job (e.g. `magi --version`)
    res = client.post("/api/jobs", json={"command": ["--version"], "workspace": ws, "name": "Version Check"})
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert job_id

    # Wait briefly for process to run
    time.sleep(0.6)

    # Inspect job
    res = client.get(f"/api/jobs/{job_id}")
    assert res.status_code == 200
    job_data = res.json()
    assert job_data["id"] == job_id
    assert len(job_data["logs"]) > 0

    # SSE streaming test with replayed logs
    res = client.get(f"/api/jobs/{job_id}/stream")
    assert res.status_code == 200
    assert "data:" in res.text

    # List jobs
    res = client.get("/api/jobs")
    assert res.status_code == 200
    assert any(j["id"] == job_id for j in res.json()["jobs"])

    # Non-existent job
    assert client.get("/api/jobs/nonexistent-id").status_code == 404
    assert client.post("/api/jobs/nonexistent-id/cancel").status_code == 400


def test_job_cancellation(client):
    ws = str(client.test_workspace)
    # Start a longer job or check cancellation
    res = client.post("/api/jobs", json={"command": ["sync"], "workspace": ws, "name": "Sync Job"})
    assert res.status_code == 200
    job_id = res.json()["job_id"]

    # Cancel immediately
    res = client.post(f"/api/jobs/{job_id}/cancel")
    assert res.status_code in (200, 400)


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
    assert "No index found" in res_search.json().get("error", "")


def test_task_manager_pruning_and_ring_buffer(tmp_path):
    from magi.ui.jobs import TaskManager

    tm = TaskManager(max_history=3)
    # Create 4 jobs
    j1 = tm.create_job(command=["--version"], workspace=str(tmp_path), name="Job 1")
    j2 = tm.create_job(command=["--version"], workspace=str(tmp_path), name="Job 2")
    j3 = tm.create_job(command=["--version"], workspace=str(tmp_path), name="Job 3")

    time.sleep(0.5)

    j4 = tm.create_job(command=["--version"], workspace=str(tmp_path), name="Job 4")
    time.sleep(0.5)

    jobs = tm.list_jobs()
    # Length should not exceed max_history
    assert len(jobs) <= 3
    assert any(j["id"] == j4.id for j in jobs)

    # Test ring buffer line limit
    j_ring = tm.create_job(command=["--version"], workspace=str(tmp_path), name="Ring Job")
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



