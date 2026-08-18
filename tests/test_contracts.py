"""Contract locks: CLI --json shapes == WebUI API responses (== future MCP).

These tests exist to stop contract drift structurally: if either side
reshapes a payload, a lock here goes red before a user notices.
"""

from __future__ import annotations

import argparse

import pytest
from fastapi.testclient import TestClient

from magi import retrieval
from magi.radar import pending_names, scan_reports
from magi.sync import build_report
from magi.ui.api import create_app

KNOWN_HINT_CODES = {
    "graph-stale", "backlog-untracked", "ingest-start", "claims-unverified",
    "beads-missing", "pm-uninit", "bd-ready", "index-missing", "index-stale",
    "radar-digests-pending", "radar-gaps-pending", "hub-topics",
}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "cfg"))
    ws = tmp_path / "topic"
    (ws / "wiki" / "concepts").mkdir(parents=True)
    (ws / "inbox" / "radar").mkdir(parents=True)
    (ws / "config.yaml").write_text("topic: contract\n", encoding="utf-8")
    (ws / "wiki" / "concepts" / "alpha.md").write_text(
        "---\ntitle: alpha\ntype: concept\n---\n\n"
        "稀疏注意力降低复杂度。attention lowers complexity.\n",
        encoding="utf-8",
    )
    (ws / "inbox" / "radar" / "2026-08-18-digest.md").write_text(
        "---\nstatus: pending-review\n---\n# digest\n", encoding="utf-8")
    (ws / "inbox" / "radar" / "2026-08-18-citation-gaps.md").write_text(
        "---\nstatus: pending-review\n---\n# gaps\n", encoding="utf-8")
    args = argparse.Namespace(topic_dir=str(ws), no_vectors=True)
    assert retrieval.cmd_index(args) == 0
    return ws


def test_search_payload_identical_cli_vs_api(workspace):
    cli_payload = retrieval.run_search(
        "attention", mode="bm25", k=5, scope="local", topic_dir=str(workspace))
    assert cli_payload["results"], "fixture must produce at least one hit"

    client = TestClient(create_app())
    res = client.get(
        f"/api/workspace/search?q=attention&mode=bm25&limit=5&scope=local&workspace={workspace}")
    assert res.status_code == 200
    api_payload = res.json()

    # The API adds exactly one field (workspace); everything else must be
    # byte-identical in shape AND content to `magi search --json`.
    assert api_payload.pop("workspace")
    assert api_payload == cli_payload


def test_search_api_supports_cli_filters(workspace):
    client = TestClient(create_app())
    res = client.get(
        "/api/workspace/search?q=attention&mode=bm25&limit=5&scope=local"
        f"&collection=concepts&path=wiki/concepts/al*&workspace={workspace}")
    data = res.json()
    assert data["results"]
    assert all(r["collection"] == "concepts" for r in data["results"])

    res = client.get(
        "/api/workspace/search?q=attention&mode=bm25&limit=5&scope=local"
        f"&path=raw/nothing*&workspace={workspace}")
    assert res.json()["results"] == []


def test_hints_dual_track(workspace):
    rep = build_report(workspace)
    assert "hints_structured" in rep
    # text track is byte-identical to the legacy strings contract
    assert [h["text"] for h in rep["hints_structured"]] == rep["hints"]
    # every code is known (frontend HINT_ACTIONS + i18n must cover these)
    assert all(h["code"] in KNOWN_HINT_CODES for h in rep["hints_structured"])
    codes = {h["code"] for h in rep["hints_structured"]}
    assert "radar-digests-pending" in codes
    assert "radar-gaps-pending" in codes


def test_frontend_covers_all_hint_codes(workspace):
    client = TestClient(create_app())
    js = client.get("/app.js").text
    for code in KNOWN_HINT_CODES:
        assert f'"{code}"' in js, f"HINT_ACTIONS missing mapping for {code}"


def test_radar_reports_single_source_of_truth(workspace):
    reports = scan_reports(workspace)
    assert pending_names(reports, "digest") == ["2026-08-18-digest.md"]
    assert pending_names(reports, "citation-gap") == ["2026-08-18-citation-gaps.md"]

    client = TestClient(create_app())
    api = client.get(f"/api/workspace/radar?workspace={workspace}").json()
    assert api["pending_digests"] == pending_names(reports, "digest")
    assert api["pending_citation_gaps"] == pending_names(reports, "citation-gap")
    kinds = {d["name"]: d["kind"] for d in api["digests"]}
    assert kinds["2026-08-18-citation-gaps.md"] == "citation-gap"
