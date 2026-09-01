"""Two surfaces, one ledger of what a reviewer decided.

`record_triage`/`load_triage` existed and were reachable only from
`magi.ui.api`. There was no `magi radar triage`, so the `radar_review` skill
did the only thing left to it and hand-edited the digest's frontmatter — a
second store nothing else reads. An agent could triage forty candidates and
the WebUI's radar panel would still show forty undecided, because the two
surfaces were writing to different files and neither knew about the other.
"""

from pathlib import Path

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


CONTEXT_SECTION_REPORT = '---\nstatus: pending-review\n---\n\n## Our paper: Fracton Topological Holography (arXiv:2606.03582)\n\nAn abstract, for context.\n\n## Somebody elses paper\n\n- id: `2607.99999` · 2026 · source: citation-gap\n'


@pytest.fixture
def ws(tmp_path):
    from magi import init_workspace

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
    from magi import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    assert _triage(tmp_path, "--id", "x", "--decision", "accept") == 1


# --------------------------------------------------------------------------
# closing a report — the half that lived only in the WebUI
# --------------------------------------------------------------------------

def test_done_closes_a_report_the_cli_could_only_open(ws, capsys):
    """`mark_report_reviewed` was reachable from `ui/api.py` and nowhere else,
    so an operator who never opened the WebUI could record every decision and
    still be told the digest was pending by `status`, `next` and `sync`."""
    _triage(ws, "--id", "2608.11111", "--decision", "accept")
    _triage(ws, "--id", "2608.22222", "--decision", "dismiss")
    capsys.readouterr()

    assert _triage(ws, "--done") == 0

    digest = ws / "inbox" / "radar" / "2026-08-26-digest.md"
    assert "status: reviewed" in digest.read_text(encoding="utf-8")
    assert "2 of 2 decided" in capsys.readouterr().out


def test_done_says_how_much_of_the_report_was_actually_decided(ws, capsys):
    """A partial pass and a finished one are identical in the ledger. The skill
    asks a person to say "18 of 40, stopped at the fold" from memory; the tool
    knows the number, so it says it."""
    _triage(ws, "--id", "2608.11111", "--decision", "accept")
    capsys.readouterr()

    assert _triage(ws, "--done") == 0

    out = capsys.readouterr().out
    assert "1 of 2 decided" in out
    assert "1 left undecided" in out
    assert "2608.22222" in out


def test_one_call_can_decide_several_candidates(ws, capsys):
    """Forty candidates took forty invocations, so the only practical route
    through a digest was a shell loop written on the spot — and a loop written
    on the spot is one whose failures nobody reads."""
    assert _triage(ws, "--id", "2608.11111", "--id", "2608.22222",
                   "--decision", "dismiss") == 0

    assert radar.load_triage(ws, "2026-08-26-digest.md") == {
        "2608.11111": "dismiss", "2608.22222": "dismiss"}
    assert "2 candidates" in capsys.readouterr().out


def test_a_batch_with_one_bad_id_records_nothing(ws, capsys):
    """Half-applying is worse than refusing: the half that landed leaves no
    trace in the message, and the caller retries the whole batch."""
    assert _triage(ws, "--id", "2608.11111", "--id", "nope",
                   "--decision", "dismiss") == 1

    assert radar.load_triage(ws, "2026-08-26-digest.md") == {}
    assert "nope" in capsys.readouterr().err


def test_a_section_nothing_can_be_recorded_against_is_not_a_candidate(ws, capsys):
    """A citation-gap report opens with `## Our paper: ...` context sections.
    The candidate parser is deliberately tolerant of them and reads them as
    title-only entries, and `--decision` already refuses to record against one
    — so counting them made a real report read "11 of 12 decided", with a
    twelfth that could never be decided and a report that never looked done."""
    report = ws / "inbox" / "radar" / "2026-08-27-citation-gaps.md"
    report.write_text(CONTEXT_SECTION_REPORT, encoding="utf-8")
    _triage(ws, "--report", report.name, "--id", "2607.99999", "--decision", "dismiss")
    capsys.readouterr()

    assert _triage(ws, "--report", report.name, "--done") == 0

    out = capsys.readouterr().out
    assert "1 of 1 decided" in out
    assert "left undecided" not in out


def test_closing_a_closed_report_is_not_an_error(ws, capsys):
    """An agent that retries must not read a red exit as a real failure."""
    _triage(ws, "--done")
    capsys.readouterr()

    assert _triage(ws, "--done") == 0
    assert "already reviewed" in capsys.readouterr().out


def test_done_refuses_to_also_mean_a_single_decision(ws, capsys):
    assert _triage(ws, "--done", "--id", "2608.11111", "--decision", "accept") == 2
    assert "does not take a candidate" in capsys.readouterr().err


def test_done_reports_the_same_counts_to_a_machine(ws):
    _triage(ws, "--id", "2608.11111", "--decision", "accept")
    import io, json, contextlib

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert _triage(ws, "--done", "--json") == 0
    payload = json.loads(out.getvalue())
    assert payload["decided"] == 1 and payload["candidates"] == 2
    assert payload["undecided"] == ["2608.22222"]
    assert payload["closed"] is True


# --------------------------------------------------------------------------
# one reader, two instruction sources
# --------------------------------------------------------------------------

def _banner_source() -> str:
    """The digest banner, read out of the function that writes it."""
    import inspect

    source = inspect.getsource(radar.cmd_harvest)
    start = source.index("new candidates. Triage")
    return source[start:source.index("for c in fresh", start)]


def _gap_banner_source() -> str:
    """The citation-gap report's banner. A second report, the same reader, and
    it drifted the same way — it taught `bd create -t review` long after the
    triage ledger became the place decisions go."""
    import inspect

    source = inspect.getsource(radar.citation_gap_report)
    start = source.index("This is a scout report")
    return source[start:source.index("for own in own_ids", start)]


def test_the_digest_and_the_skill_do_not_teach_different_commands():
    """The banner is printed into every digest and the skill is loaded beside
    it. When they named different commands, an agent was following the product
    either way and the one it read decided what it did."""
    import re

    banner = _banner_source()
    skill = (Path(__file__).resolve().parents[1] / "src" / "magi" / "skills"
             / "radar_review" / "SKILL.md").read_text(encoding="utf-8")

    for what, text in (("digest", banner), ("citation-gap report", _gap_banner_source())):
        named = {m.group(1).strip() for m in re.finditer(r"`(magi [a-z][a-z -]*)", text)}
        assert named, f"the {what} banner names no command at all"
        unknown = {c for c in named if c not in skill}
        assert not unknown, (
            f"the {what} tells its reader to run {sorted(unknown)}, which the "
            "radar_review skill never mentions — two instruction sources, one reader")


def test_the_digest_never_tells_anyone_to_edit_it():
    """The frontmatter is a second store nothing else reads — the exact defect
    `magi radar triage` was added to close, and the banner was still teaching
    it long after."""
    for banner in (_banner_source(), _gap_banner_source()):
        assert "set `status: reviewed` in this file" not in banner
        assert "file `bd` issues" not in banner
        assert "bd create" not in banner
        assert "Do not edit this file" in banner


# --------------------------------------------------------------------------
# one ledger, two writers, one set of words
# --------------------------------------------------------------------------

def _decisions_the_webui_records() -> set:
    """Read out of `ui/api.py` itself. A list kept beside it is the thing that
    drifts, and drift here is what put a fourth word in the ledger."""
    import inspect
    import re

    from magi.ui import api

    source = inspect.getsource(api)
    written = set(re.findall(r'record_triage\([^)]*,\s*"([a-z-]+)"\)', source))
    # `dismiss` and `reset` reach `record_triage` as a variable, so they are
    # named by the branch that forwards them rather than by a literal.
    for match in re.findall(r'req\.action in \(([^)]*)\)', source):
        written |= {w.strip().strip('"') for w in match.split(",")
                    if w.strip().strip('"') in ("dismiss", "reset")}
    return written


def test_neither_surface_can_add_a_word_the_other_does_not_know():
    """One ledger, two writers. The panel's "create a reading task" button
    records `task`, which the CLI could not produce, did not document and left
    undefined for anyone reading the ledger — under a comment claiming the two
    surfaces stored the same three words."""
    written = _decisions_the_webui_records()
    assert "task" in written, "the reading-task action stopped recording anything"

    known = set(radar.TRIAGE_DECISIONS) | {"reset"}
    unknown = written - known
    assert not unknown, (
        f"the WebUI records {sorted(unknown)}, which radar.TRIAGE_DECISIONS "
        "does not define — one ledger with two vocabularies")


def test_the_cli_offers_only_what_the_cli_can_actually_do():
    """Making a reading task means creating a `bd` issue, which is the panel's
    job. Offering it here would record that a task exists when none does."""
    assert set(radar.TRIAGE_CLI_DECISIONS) <= set(radar.TRIAGE_DECISIONS) | {"reset"}
    assert "task" not in radar.TRIAGE_CLI_DECISIONS


def test_every_defined_decision_is_one_some_surface_writes():
    """The table from its own side: a word defined and recorded by nobody
    explains something that no longer happens."""
    written = _decisions_the_webui_records() | set(radar.TRIAGE_CLI_DECISIONS)
    orphans = set(radar.TRIAGE_DECISIONS) - written
    assert not orphans, f"defined but never recorded: {sorted(orphans)}"


# --------------------------------------------------------------------------
# the two surfaces count the same candidates
# --------------------------------------------------------------------------

def test_the_panel_and_the_cli_agree_on_how_many_can_be_decided(ws):
    """A report whose sections are not all candidates is the case that made
    them disagree, and it is the ordinary shape of a citation-gap report."""
    import io
    import json
    import contextlib

    report = ws / "inbox" / "radar" / "2026-08-27-citation-gaps.md"
    report.write_text(CONTEXT_SECTION_REPORT, encoding="utf-8")

    client = TestClient(create_app())
    payload = client.get("/api/workspace/radar/digest",
                         params={"workspace": str(ws), "file": report.name}).json()

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        _triage(ws, "--report", report.name, "--done", "--json")
    cli = json.loads(out.getvalue())

    assert payload["triageable"] == cli["candidates"] == 1
    assert len(payload["candidates"]) == 2, "the context section is still readable"


def test_the_panel_builds_no_triage_row_for_a_section_it_cannot_act_on():
    """Read out of `app.js`: a row with buttons that all answer 409 is a row
    that should not have been built, and its presence was what made the
    progress counter unreachable."""
    app_js = (Path(__file__).resolve().parents[1] / "src" / "magi" / "ui"
              / "static" / "app.js").read_text(encoding="utf-8")

    start = app_js.index("function buildCandidateRow(")
    head = app_js[start:start + 400]
    assert "if (!c.id) return buildContextRow(c);" in head, (
        "buildCandidateRow no longer skips candidates that carry no id")
    assert "function buildContextRow(" in app_js

