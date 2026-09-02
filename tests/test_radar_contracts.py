"""Radar behaviours a regression would quietly undo.

Every case here came out of running the radar against a real 67-paper library
(Prof. Peng Ye's group: topological order, SPT, fracton, TQFT) with a live
arXiv and Semantic Scholar harvest behind it. The worst one was silent: a
scheduled harvest read its config from wherever the scheduler happened to
start the process, found none, and produced a plausible digest that had lost
every arXiv listing.
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from magi import radar
from magi.core.config_loader import load_config, get as cfg_get


def _workspace(tmp_path: Path, **radar_cfg) -> Path:
    """A minimal but real topic workspace with a radar config."""
    ws = tmp_path / "ws"
    for d in ("wiki/references", "raw", "output", "inbox"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    (ws / "config.md").write_text("---\ntitle: t\n---\n", encoding="utf-8")
    body = ["radar:"]
    for k, v in radar_cfg.items():
        body.append(f"  {k}: {json.dumps(v)}")
    (ws / "config.yaml").write_text("\n".join(body) + "\n", encoding="utf-8")
    return ws


# --------------------------------------------------------------------------
# config follows --topic-dir, not the process cwd
# --------------------------------------------------------------------------

def test_config_is_read_from_the_workspace_not_the_cwd(tmp_path, monkeypatch):
    """`--topic-dir` used to select where output landed while config discovery
    stayed on cwd. The scheduler is the case that matters: it registers
    `magi radar harvest --topic-dir <ws>` and the scheduler's own working
    directory is System32 / `/` / `$HOME`, so the nightly run found no config
    at all and harvested with an empty category list."""
    ws = _workspace(tmp_path, arxiv_categories=["cond-mat.str-el", "hep-th"], days=21)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    stray = load_config()
    assert cfg_get(stray, "radar.arxiv_categories", None) is None

    scoped = load_config(start=ws)
    assert cfg_get(scoped, "radar.arxiv_categories", None) == ["cond-mat.str-el", "hep-th"]
    assert cfg_get(scoped, "radar.days", 7) == 21


def test_a_scheduled_harvest_starts_in_the_workspace(tmp_path, monkeypatch):
    """Belt and braces on top of the above: the registered command should also
    *run* in the workspace, so a scheduled harvest behaves the same as one you
    type by hand."""
    ws = _workspace(tmp_path, arxiv_categories=["hep-th"])
    recorded = {}

    monkeypatch.setattr(radar.sys, "platform", "win32")
    monkeypatch.setattr(radar.shutil if hasattr(radar, "shutil") else __import__("shutil"),
                        "which", lambda _: "C:\\magi.exe", raising=False)

    def fake_run(cmd, capture_output=True, text=True):
        recorded["cmd"] = cmd
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    import subprocess

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("shutil.which", lambda _: "C:\\magi.exe")

    args = types.SimpleNamespace(topic_dir=str(ws), time="03:00", uninstall=False)
    assert radar.cmd_install_schedule(args) == 0
    tr = next(recorded["cmd"][i + 1] for i, a in enumerate(recorded["cmd"]) if a == "/TR")
    assert "cd /d" in tr and str(ws) in tr, tr


def test_the_danger_zone_holds_only_destructive_operations():
    """Scheduling a harvest registers a reversible cron entry and touches no
    workspace data; `magi pm init` is additive and no-ops when the database
    already exists. Both used to sit behind the same type-the-exact-name modal
    as `migrate` and `setup --remove-legacy` — which is how a required
    first-run step came to read as something to avoid.

    The zone is for operations that destroy or restructure. Putting anything
    else in it spends the user's caution on the wrong thing, and they stop
    reading the modal."""
    from magi.ui.jobs import OPS

    for routine in ("radar-install-schedule", "pm-init"):
        assert OPS[routine]["danger"] is False, f"{routine} is not destructive"
    for destructive in ("migrate", "setup-remove-legacy", "setup"):
        assert OPS[destructive]["danger"] is True


# --------------------------------------------------------------------------
# --topic-dir validation
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["missing", "file"])
def test_a_bad_topic_dir_is_refused_not_fabricated(tmp_path, capsys, kind):
    """A nonexistent path used to get an `output/radar/` tree created inside it
    and the command reported success; a path that was a file crashed with a raw
    traceback out of Path.mkdir."""
    if kind == "missing":
        target = tmp_path / "nope"
    else:
        target = tmp_path / "a-file.txt"
        target.write_text("x", encoding="utf-8")

    args = types.SimpleNamespace(topic_dir=str(target), json=False)
    assert radar.cmd_status(args) == 1
    assert not (target / "output").exists()
    err = capsys.readouterr().err
    assert "--topic-dir" in err


# --------------------------------------------------------------------------
# harvest budget and knobs
# --------------------------------------------------------------------------

def test_max_candidates_zero_makes_no_network_calls(tmp_path, monkeypatch, capsys):
    ws = _workspace(tmp_path, arxiv_categories=["hep-th"], max_candidates=0)
    called = []
    monkeypatch.setattr(radar, "harvest_s2", lambda *a, **k: called.append("s2") or [])
    monkeypatch.setattr(radar, "harvest_arxiv", lambda *a, **k: called.append("arxiv") or ([], []))

    args = types.SimpleNamespace(topic_dir=str(ws), days=None)
    assert radar.cmd_harvest(args) == 0
    assert called == [], "harvested despite a zero cap"
    assert "max_candidates is 0" in capsys.readouterr().err


def test_a_harvest_with_no_seeds_says_the_best_leg_is_off(tmp_path, monkeypatch, capsys):
    """`harvest_s2([])` returns nothing and the log announced a harvest that
    never happened. Not a rare configuration: the config comment says seeds may
    stay empty, so a project that filled in only `own_arxiv_ids` silently gets
    the arXiv listings alone — which on a measured run produced none of the
    useful candidates."""
    ws = _workspace(tmp_path, arxiv_categories=["hep-th"], seed_arxiv_ids=[])
    monkeypatch.setattr(radar, "harvest_arxiv", lambda *a, **k: ([], []))

    args = types.SimpleNamespace(topic_dir=str(ws), days=None)
    assert radar.cmd_harvest(args) == 0

    err = capsys.readouterr().err
    assert "recommendations are off" in err
    assert "harvesting S2 recommendations" not in err, (
        "announced a harvest it did not run")


def test_a_harvest_with_seeds_still_says_it_is_harvesting(tmp_path, monkeypatch, capsys):
    """The other direction: the note must not replace the ordinary line."""
    ws = _workspace(tmp_path, arxiv_categories=["hep-th"],
                    seed_arxiv_ids=["2401.00505"])
    monkeypatch.setattr(radar, "harvest_s2", lambda *a, **k: [])
    monkeypatch.setattr(radar, "harvest_arxiv", lambda *a, **k: ([], []))

    args = types.SimpleNamespace(topic_dir=str(ws), days=None)
    assert radar.cmd_harvest(args) == 0

    err = capsys.readouterr().err
    assert "harvesting S2 recommendations" in err
    assert "recommendations are off" not in err


def test_days_zero_is_honoured_rather_than_treated_as_unset(tmp_path, monkeypatch):
    """`args.days or cfg(...)` silently replaced an explicit --days 0 with the
    default 7. Zero is a real request: only today's listings."""
    ws = _workspace(tmp_path, arxiv_categories=["hep-th"], days=30)
    seen = {}

    def spy(cats, days, **kwargs):
        seen["days"] = days
        return [], []

    monkeypatch.setattr(radar, "harvest_s2", lambda *a, **k: [])
    monkeypatch.setattr(radar, "harvest_arxiv", spy)
    monkeypatch.setattr(radar, "_score_candidates", lambda *a, **k: False)

    radar.cmd_harvest(types.SimpleNamespace(topic_dir=str(ws), days=0))
    assert seen["days"] == 0
    radar.cmd_harvest(types.SimpleNamespace(topic_dir=str(ws), days=None))
    assert seen["days"] == 30


def test_arxiv_recency_keeps_its_share_of_the_budget():
    """The reservation used to happen at fetch time and was then undone by the
    relevance sort — on a real harvest that put 9 of the top 10 on the
    Semantic Scholar side, which is backwards for a tool whose job is telling
    you what appeared this week."""
    cands = ([{"id": f"s{i}", "source": "s2-recommendation", "score": 0.9 - i * 0.001}
              for i in range(30)]
             + [{"id": f"a{i}", "source": "arxiv-new:hep-th", "score": 0.5 - i * 0.001}
                for i in range(30)])
    cands.sort(key=lambda c: -c["score"])
    kept = radar._apply_budget(cands, 20)
    assert len(kept) == 20
    recency = [c for c in kept if c["source"].startswith("arxiv-new")]
    assert len(recency) == 10, f"arXiv kept only {len(recency)} of its 10 reserved slots"


def test_every_configured_arxiv_category_gets_a_turn_in_the_budget():
    """Reserving for the arXiv *family* was not enough. `harvest_arxiv` fetches
    30 per category and concatenates them in config order, so with the default
    cap of 40 the first category's 30 overflowed the 20 reserved slots and
    every later category was fetched and dropped whole — under a log line that
    named all of them. Measured on a live run: three categories configured,
    twenty arXiv candidates, all twenty from the first."""
    cands = [{"id": f"s{i}", "source": "s2-recommendation"} for i in range(20)]
    for cat in ("cond-mat.str-el", "hep-th", "quant-ph"):
        cands += [{"id": f"{cat}-{i}", "source": f"arxiv-new:{cat}"} for i in range(30)]

    kept = radar._apply_budget(cands, 40)

    seen = {c["source"] for c in kept if c["source"].startswith("arxiv-new")}
    assert seen == {"arxiv-new:cond-mat.str-el", "arxiv-new:hep-th",
                    "arxiv-new:quant-ph"}, f"categories crowded out: {seen}"
    assert len(kept) == 40


def test_a_category_with_little_to_give_hands_its_turn_on():
    """Rotating must not leave the share unfilled: a quiet category costs the
    digest nothing, it just stops taking turns."""
    cands = [{"id": f"s{i}", "source": "s2-recommendation"} for i in range(20)]
    cands += [{"id": f"q{i}", "source": "arxiv-new:quiet"} for i in range(2)]
    cands += [{"id": f"b{i}", "source": "arxiv-new:busy"} for i in range(30)]

    kept = radar._apply_budget(cands, 40)

    recency = [c for c in kept if c["source"].startswith("arxiv-new")]
    assert len(recency) == 20, "the arXiv share went unfilled"
    assert sum(1 for c in recency if c["source"] == "arxiv-new:quiet") == 2


def test_a_small_result_set_is_not_reshuffled():
    cands = [{"id": "a", "source": "s2-recommendation", "score": 0.9},
             {"id": "b", "source": "arxiv-new:hep-th", "score": 0.1}]
    assert radar._apply_budget(cands, 40) == cands


# --------------------------------------------------------------------------
# digest round trip
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# the citation-gap report counts papers, not pairings
# --------------------------------------------------------------------------

def _pair(own, cand, refs, title="A Paper", **extra):
    return {"own_paper": own, "candidate_arxiv": cand, "candidate_title": title,
            "year": 2026, "shared_refs": refs, "abstract": "We study things.",
            **extra}


def test_one_paper_flagged_against_three_of_ours_is_still_one_candidate():
    """Each pairing used to get its own `## ` heading, so one paper parsed as
    several candidates carrying the same id — and `triage --id` records against
    the first, which left a decided paper still listed as undecided. A live run
    reported 18 candidates; there were 11 papers."""
    findings = [_pair("2401.00505", "2607.12023", 15),
                _pair("2512.06691", "2607.12023", 8),
                _pair("2605.13379", "2607.12023", 3),
                _pair("2401.00505", "2607.03762", 6, title="Another Paper")]

    text, papers = radar.citation_gap_report("2026-09-01", [], {}, findings, 2)

    assert len(papers) == 2
    ids = [c["id"] for c in radar.parse_digest_candidates(text)]
    assert ids == sorted(set(ids), key=ids.index), f"duplicate ids: {ids}"
    assert sorted(ids) == ["2607.03762", "2607.12023"]


def test_an_anchor_the_api_refused_to_describe_says_so_where_it_is_missing():
    """Two of five own papers were rate-limited on a live run. Their references
    came back and produced findings, but their context sections were skipped —
    so the report introduced some anchors and not others, and the only
    explanation was a warning five minutes upstream in another stream."""
    findings = [_pair("2606.03582", "2607.12023", 9)]
    own_meta = {"2606.03582": {"title": "", "abstract": "", "unavailable": True}}

    text, _papers = radar.citation_gap_report(
        "2026-09-01", ["2606.03582"], own_meta, findings, 2)

    assert "## Our paper: arXiv:2606.03582" in text
    assert "did not answer for this paper" in text
    assert "findings below are unaffected" in text


def test_an_anchor_we_simply_have_no_metadata_for_stays_quiet():
    """The other direction: having nothing to introduce is not an outage, and
    an alarm printed for the ordinary case trains people to ignore the alarm."""
    findings = [_pair("2606.03582", "2607.12023", 9)]
    own_meta = {"2606.03582": {"title": "", "abstract": "", "unavailable": False}}

    text, _papers = radar.citation_gap_report(
        "2026-09-01", ["2606.03582"], own_meta, findings, 2)

    assert "did not answer" not in text
    assert "## Our paper" not in text


def test_the_header_counts_papers_and_says_how_many_pairings_made_them():
    """`candidates: 18` counted pairings and called them candidates; only
    reading the whole file corrected it."""
    findings = [_pair("2401.00505", "2607.12023", 15),
                _pair("2512.06691", "2607.12023", 8)]

    text, _papers = radar.citation_gap_report("2026-09-01", [], {}, findings, 2)

    assert "candidates: 1" in text
    assert "pairs: 2" in text


def test_a_paper_decided_this_morning_is_marked_not_hidden():
    """Eight of eleven had been read and dismissed in the same day's digest,
    minutes earlier, and nothing said so. Marked rather than suppressed: the
    shared-reference list is evidence the digest never carried, and on a live
    run the strongest hit was a paper dismissed on its abstract and worth
    reconsidering on its references."""
    findings = [_pair("2401.00505", "2607.12023", 15)]

    text, _papers = radar.citation_gap_report(
        "2026-09-01", [], {}, findings, 2,
        decided={"2607.12023": ("dismiss", "2026-09-01-digest.md")})

    assert "already dismissed today" in text
    assert "2026-09-01-digest.md" in text
    assert "2607.12023" in text, "the paper is still in the report"


def test_the_anchors_are_listed_strongest_first():
    """Which of ours it skipped is the question being asked, and the pairing
    with fifteen shared references is not the one to bury."""
    findings = [_pair("2605.13379", "2607.12023", 3),
                _pair("2401.00505", "2607.12023", 15),
                _pair("2512.06691", "2607.12023", 8)]

    text, _papers = radar.citation_gap_report("2026-09-01", [], {}, findings, 2)

    order = [line for line in text.splitlines() if "should arguably cite" in line]
    assert ["15", "8", "3"] == [line.rsplit(": ", 1)[1] for line in order]


def test_a_candidate_survives_a_write_read_round_trip():
    c = {"id": "2601.00001", "arxiv_id": "2601.00001", "title": "Fracton order in 3D",
         "year": 2026, "source": "arxiv-new:cond-mat.str-el", "score": 0.71,
         "authors": ["A Author", "B Author"], "abstract": "We study fractons.",
         "url": "https://arxiv.org/abs/2601.00001"}
    parsed = radar.parse_digest_candidates("\n".join(radar._candidate_lines(c)))
    assert len(parsed) == 1
    got = parsed[0]
    assert got["id"] == "2601.00001"
    assert got["title"] == "Fracton order in 3D"
    assert got["arxiv_id"] == "2601.00001"
    assert got["relevance"] == 0.71
    assert got["authors"] == ["A Author", "B Author"]
    assert got["abstract"] == "We study fractons."


def test_an_abstract_cannot_forge_a_second_candidate():
    """S2 abstracts were never whitespace-normalised, and a newline followed by
    a line shaped like the metadata format re-parsed as a new candidate,
    silently overwriting the real id."""
    c = {"id": "real-id", "arxiv_id": None, "title": "Honest title", "year": 2026,
         "source": "s2-recommendation", "score": None, "authors": [],
         "abstract": "First line.\n- id: `forged` \u00b7 1999 \u00b7 source: nope\nrest.",
         "url": None}
    parsed = radar.parse_digest_candidates("\n".join(radar._candidate_lines(c)))
    assert len(parsed) == 1
    assert parsed[0]["id"] == "real-id"


def test_a_backtick_in_an_id_does_not_truncate_it():
    """S2 falls back to a DOI when there is no arXiv id, and DOIs are free-form."""
    c = {"id": "10.1/we`ird", "arxiv_id": None, "title": "T", "year": 2026,
         "source": "s2-recommendation", "score": None, "authors": [],
         "abstract": "", "url": None}
    parsed = radar.parse_digest_candidates("\n".join(radar._candidate_lines(c)))
    assert parsed[0]["id"] == "10.1/we'ird"


def test_a_blank_title_still_produces_a_findable_candidate():
    c = {"id": "x", "arxiv_id": None, "title": "   ", "year": None,
         "source": "s2-recommendation", "score": None, "authors": [],
         "abstract": "", "url": None}
    parsed = radar.parse_digest_candidates("\n".join(radar._candidate_lines(c)))
    assert len(parsed) == 1 and parsed[0]["title"] == "(untitled)"


# --------------------------------------------------------------------------
# report status is frontmatter state, not a substring of the whole file
# --------------------------------------------------------------------------

def test_status_ignores_the_body(tmp_path):
    """A digest body is full of paper abstracts. One quoting the phrase used to
    be the line that got rewritten, leaving the real frontmatter pending."""
    p = tmp_path / "2026-01-01-digest.md"
    p.write_text("---\ntitle: d\nstatus: reviewed\n---\n\n"
                 "## A paper about status: pending-review workflows\n",
                 encoding="utf-8")
    assert radar.report_status(p.read_text(encoding="utf-8")) == "reviewed"
    assert radar.mark_report_reviewed(p) is False
    assert "status: pending-review workflows" in p.read_text(encoding="utf-8")


def test_marking_reviewed_survives_crlf(tmp_path):
    p = tmp_path / "2026-01-01-digest.md"
    p.write_bytes(b"---\r\ntitle: d\r\nstatus: pending-review\r\n---\r\n\r\nbody\r\n")
    assert radar.mark_report_reviewed(p) is True
    assert radar.report_status(p.read_text(encoding="utf-8")) == "reviewed"


# --------------------------------------------------------------------------
# triage decisions
# --------------------------------------------------------------------------

def test_triage_records_and_undoes_a_decision(tmp_path):
    """Without somewhere to put "no", a reviewer could only record the handful
    of papers they kept, and the other thirty-five decisions lived in their
    head until the tab closed."""
    ws = _workspace(tmp_path)
    radar.record_triage(ws, "d.md", "p1", "dismiss")
    radar.record_triage(ws, "d.md", "p2", "accept")
    radar.record_triage(ws, "other.md", "p1", "accept")
    assert radar.load_triage(ws, "d.md") == {"p1": "dismiss", "p2": "accept"}

    radar.record_triage(ws, "d.md", "p1", "reset")
    assert radar.load_triage(ws, "d.md") == {"p2": "accept"}


def test_triage_survives_a_corrupt_line(tmp_path):
    ws = _workspace(tmp_path)
    radar.record_triage(ws, "d.md", "p1", "dismiss")
    path = ws / "output" / "radar" / "triage.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write("{not json at all\n")
    radar.record_triage(ws, "d.md", "p2", "accept")
    assert radar.load_triage(ws, "d.md") == {"p1": "dismiss", "p2": "accept"}


# --------------------------------------------------------------------------
# harvest age
# --------------------------------------------------------------------------

def test_harvest_age_comes_from_the_ledger(tmp_path):
    """Nothing recorded this, so a radar whose scheduled task had quietly
    stopped looked exactly like one that ran an hour ago."""
    import datetime as dt

    ws = _workspace(tmp_path)
    assert radar.last_harvest_date(ws) is None
    assert radar.harvest_age_days(ws) is None

    ledger = ws / "output" / "radar" / "seen.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    old = (dt.date.today() - dt.timedelta(days=9)).isoformat()
    newer = (dt.date.today() - dt.timedelta(days=3)).isoformat()
    ledger.write_text(
        json.dumps({"id": "a", "first_seen": old}) + "\n"
        + json.dumps({"id": "b", "first_seen": newer}) + "\n"
        + "garbage\n", encoding="utf-8")
    assert radar.last_harvest_date(ws) == newer
    assert radar.harvest_age_days(ws) == 3


# --------------------------------------------------------------------------
# the scout's success path
# --------------------------------------------------------------------------

def test_finding_something_does_not_crash_the_scout(tmp_path, monkeypatch, capsys):
    """`seen_before` was named in the summary line and assigned nowhere.

    The whole failure lived on the *success* path: no findings meant the
    `else` branch, which printed "no candidates survived the funnel" and
    returned 0. Every test and every dry run took that branch, so 2780 tests
    and 84 mutation guards went past a guaranteed NameError. It surfaced on
    the first real run that actually found a candidate.

    So this test is only worth anything if it makes the scout find one.
    """
    import argparse

    from magi import radar as radar_mod

    from magi import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    (tmp_path / "output" / "radar").mkdir(parents=True, exist_ok=True)
    (tmp_path / "inbox" / "radar").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.yaml").write_text(
        "radar:\n  own_arxiv_ids: ['2501.00001']\n", encoding="utf-8")

    def fake_get(url, retries=1, cfg=None):
        if "/references" in url:
            return {"data": [{"citedPaper": {"paperId": f"ref{i}"}} for i in range(4)]}
        if "/citations" in url:
            return {"data": []}
        if "/recommendations" in url:
            return {"recommendedPapers": [
                {"paperId": "cand1", "title": "A Competing Paper",
                 "year": 2026, "externalIds": {"ArXiv": "2601.00002"}}]}
        return {"paperId": "own", "title": "Our Paper", "year": 2025,
                "externalIds": {"ArXiv": "2501.00001"}}

    monkeypatch.setattr(radar_mod, "_s2_get", fake_get)

    code = radar_mod.cmd_citation_gap(argparse.Namespace(
        project_dir=str(tmp_path), topic_dir=str(tmp_path), paper=None, json=False))

    assert code == 0
    out = capsys.readouterr().out
    assert "citation-gap:" in out
    assert "paper(s) from" in out
    assert (tmp_path / "inbox" / "radar").glob("*-citation-gaps.md")


def test_an_unquoted_arxiv_id_is_refused_not_quietly_changed():
    """`own_arxiv_ids: [2606.03580]` is a float before any of our code runs.

    YAML reads it as 2606.0358 — the trailing zero is gone — and `str()` of
    that is a perfectly well-formed arXiv id belonging to a different paper.
    Nothing downstream can tell the difference, which is the whole problem.
    The digit cannot be recovered at this point, so the only honest move is to
    stop and name the fix.
    """
    from magi import radar as radar_mod

    with pytest.raises(SystemExit) as caught:
        radar_mod._ids_from_config([2606.03580], "radar.own_arxiv_ids")
    assert "2606.03580" in str(caught.value), "the message has to show the quoting"
    assert "radar.own_arxiv_ids" in str(caught.value)


def test_quoted_ids_pass_through_untouched():
    from magi import radar as radar_mod

    assert radar_mod._ids_from_config(["2606.03580", "2508.13961"], "x") == [
        "2606.03580", "2508.13961"]
    assert radar_mod._ids_from_config(None, "x") == []
