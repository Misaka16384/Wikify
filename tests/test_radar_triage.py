"""Two surfaces, one ledger of what a reviewer decided.

`record_triage`/`load_triage` existed and were reachable only from
`magi.ui.api`. There was no `magi radar triage`, so the `radar_review` skill
did the only thing left to it and hand-edited the digest's frontmatter — a
second store nothing else reads. An agent could triage forty candidates and
the WebUI's radar panel would still show forty undecided, because the two
surfaces were writing to different files and neither knew about the other.
"""

import pytest
from fastapi.testclient import TestClient

from magi import radar
from magi.ui.api import create_app

DIGEST = """---
status: pending-review
---
# Radar digest

## Fractonic order in three dimensions
- id: `2608.11111` · relevance: 0.71
- https://arxiv.org/abs/2608.11111

## Non-invertible symmetries revisited
- id: `2608.22222` · relevance: 0.55
- https://arxiv.org/abs/2608.22222
"""


@pytest.fixture
def ws(tmp_path):
    from magi.hub import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    (tmp_path / "inbox" / "radar").mkdir(parents=True, exist_ok=True)
    (tmp_path / "inbox" / "radar" / "2026-08-26-digest.md").write_text(
        DIGEST, encoding="utf-8")
    return tmp_path


def _triage(ws, *args):
    return radar.main(["triage", "--topic-dir", str(ws), *args])


# --------------------------------------------------------------------------
# the command that was missing
# --------------------------------------------------------------------------

def test_a_decision_can_be_recorded_by_id(ws):
    assert _triage(ws, "--id", "2608.11111", "--decision", "accept") == 0
    assert radar.load_triage(ws, "2026-08-26-digest.md") == {"2608.11111": "accept"}


def test_a_decision_can_be_recorded_by_position(ws):
    assert _triage(ws, "--index", "1", "--decision", "dismiss") == 0
    assert radar.load_triage(ws, "2026-08-26-digest.md") == {"2608.22222": "dismiss"}


def test_reset_clears_a_previous_decision(ws):
    _triage(ws, "--id", "2608.11111", "--decision", "accept")
    _triage(ws, "--id", "2608.11111", "--decision", "reset")
    assert radar.load_triage(ws, "2026-08-26-digest.md") == {}


def test_listing_shows_what_is_recorded(ws, capsys):
    _triage(ws, "--id", "2608.11111", "--decision", "accept")
    capsys.readouterr()

    assert _triage(ws, "--json") == 0
    import json

    rows = json.loads(capsys.readouterr().out)["candidates"]
    assert {r["id"]: r["decision"] for r in rows} == {
        "2608.11111": "accept", "2608.22222": None}


def test_it_defaults_to_the_newest_pending_report(ws):
    """A reviewer working through today's digest should not have to name it."""
    assert _triage(ws, "--id", "2608.11111", "--decision", "accept") == 0
    assert radar.load_triage(ws, "2026-08-26-digest.md")


# --------------------------------------------------------------------------
# the two surfaces agreeing
# --------------------------------------------------------------------------

def test_the_webui_reads_what_the_cli_recorded(ws):
    """This is the whole point: an agent's triage has to be visible in the
    panel, and the panel's has to be visible to the agent."""
    _triage(ws, "--id", "2608.11111", "--decision", "accept")
    _triage(ws, "--index", "1", "--decision", "dismiss")

    client = TestClient(create_app())
    res = client.get("/api/workspace/radar/digest",
                     params={"file": "2026-08-26-digest.md", "workspace": str(ws)})
    assert res.status_code == 200
    seen = {c["id"]: c.get("decision") for c in res.json()["candidates"]}
    assert seen == {"2608.11111": "accept", "2608.22222": "dismiss"}


def test_the_cli_reads_what_the_webui_recorded(ws, capsys):
    client = TestClient(create_app())
    res = client.post("/api/workspace/radar/candidate",
                      json={"file": "2026-08-26-digest.md", "index": 1,
                            "action": "dismiss", "workspace": str(ws)})
    assert res.status_code == 200

    assert radar.load_triage(ws, "2026-08-26-digest.md") == {"2608.22222": "dismiss"}


@pytest.mark.parametrize("word", ["accept", "dismiss", "reset"])
def test_the_cli_speaks_the_words_the_panel_stores(ws, word):
    assert _triage(ws, "--id", "2608.11111", "--decision", word) == 0


def test_a_word_the_panel_does_not_store_is_refused(ws):
    """A CLI writing "keep" where the panel writes "accept" would put two
    vocabularies in one ledger — the same bug one level down."""
    with pytest.raises(SystemExit):
        _triage(ws, "--id", "2608.11111", "--decision", "keep")
    assert radar.load_triage(ws, "2026-08-26-digest.md") == {}


# --------------------------------------------------------------------------
# refusing rather than guessing
# --------------------------------------------------------------------------

def test_an_unknown_candidate_is_an_error_not_a_new_record(ws):
    assert _triage(ws, "--id", "9999.99999", "--decision", "accept") == 1
    assert radar.load_triage(ws, "2026-08-26-digest.md") == {}


def test_an_out_of_range_index_is_an_error(ws):
    assert _triage(ws, "--index", "42", "--decision", "accept") == 1


def test_naming_no_candidate_is_a_usage_error(ws):
    assert _triage(ws, "--decision", "accept") == 2


def test_an_unknown_report_is_an_error(ws):
    assert _triage(ws, "--report", "nope.md", "--decision", "accept") == 1


def test_no_reports_at_all_is_an_error(tmp_path):
    from magi.hub import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    assert _triage(tmp_path, "--id", "x", "--decision", "accept") == 1
