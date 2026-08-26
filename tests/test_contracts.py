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

def _emitted_hint_codes() -> set[str]:
    """Every hint code `magi sync` can emit, read out of its own source.

    This used to be a hand-copied set, which is a fourth place the same list
    lived. `radar-harvest-overdue` shipped in neither the copy nor the WebUI's
    HINT_ACTIONS table, so the guard below passed without ever seeing it and
    an overdue radar rendered untranslated English prose in a <code> element
    with nothing to click — while `radar-harvest` sat in the ops whitelist the
    whole time. Deriving the set means adding a hint to sync.py now fails here
    until the UI knows what to do with it.
    """
    import inspect
    import re

    from magi import sync

    codes = set(re.findall(r'_hint\(\s*"([a-z0-9-]+)"', inspect.getsource(sync)))
    assert codes, "no hint codes found — did _hint()'s call shape change?"
    return codes


KNOWN_HINT_CODES = _emitted_hint_codes()


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


# --------------------------------------------------------------------------
# Every WebUI button has to be a command the CLI will actually accept.
# `wiki reindex`, `link` and `stats` each shipped an argv the parser rejected
# with exit 2 — the button just went red with an argparse usage line in the log.
# --------------------------------------------------------------------------

def _cli_usage(argv):
    """`magi <argv> --help`, captured. SystemExit(0) proves the path dispatches."""
    import contextlib
    import io as _io

    from magi import cli as magi_cli

    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        # cli.main normalizes argparse's SystemExit into a return code.
        rc = magi_cli.main([a for a in argv if not a.startswith("-")] + ["--help"])
    assert rc == 0, f"magi {' '.join(argv)} --help exited {rc}"
    return buf.getvalue()


def _unfilled_positionals(usage: str, argv) -> list[str]:
    """Required arguments left over once the op's own argv is accounted for."""
    import re

    named = set(argv)

    text = " ".join(usage.split("\n\n")[0].split())
    text = text.split("usage:", 1)[-1].strip()
    # Leading bare words are the prog name ("magi pm backlog-sync" — note the
    # hyphen, so this has to be tokenwise); the spec starts at the first token
    # that opens a bracket, a brace, or a flag.
    tokens = text.split()
    for i, tok in enumerate(tokens):
        if tok[0] in "[{-":
            tokens = tokens[i:]
            break
    else:
        tokens = []
    spec = re.sub(r"\[[^\[\]]*\]", " ", " ".join(tokens))   # drop optionals
    leftover = [tok for tok in spec.split() if tok not in ("...", "|")]
    # A word the op already passes is satisfied, whether it lands as a plain
    # positional or as one of a {choices} subcommand group.
    return [tok for tok in leftover
            if tok not in named
            and not (tok.startswith("{") and named & set(tok.strip("{}").split(",")))]


@pytest.mark.parametrize("op", sorted(__import__("magi.ui.jobs", fromlist=["OPS"]).OPS))
def test_every_webui_op_is_a_command_the_cli_accepts(op):
    from magi.ui.jobs import OPS

    argv = OPS[op]["argv"]
    leftover = _unfilled_positionals(_cli_usage(argv), argv)
    assert not leftover, (
        f"op '{op}' runs `magi {' '.join(argv)}` but the parser still requires "
        f"{leftover} — the job exits 2 before doing anything"
    )
