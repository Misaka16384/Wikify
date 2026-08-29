"""The commands that collapse a multi-step routine into one.

Migration used to be eight commands and a cd-loop; these are the pieces that
made it one, plus the guardrails that keep them from doing too much.
"""

from __future__ import annotations

import json

import pytest


# --------------------------------------------------------------------------
# magi sync --fix — act on the hints instead of printing them
# --------------------------------------------------------------------------

def test_sync_fix_only_automates_the_deterministic_repairs():
    from magi.cli import _COMMANDS
    from magi.sync import FIXABLE

    assert set(FIXABLE) == {"graph-stale", "index-missing", "index-stale",
                            "backlog-untracked", "pm-uninit"}
    # Things that need a human or an agent must stay out of it. `--fix` runs
    # deterministic commands; compiling is an LLM authoring pass and saying
    # "fixed" about it would be a lie in the one report a new user trusts.
    for code in ("beads-missing", "ingest-start", "claims-unverified",
                 "radar-digests-pending", "bd-ready", "compile-pending",
                 "radar-harvest-overdue"):
        assert code not in FIXABLE

    for cmd, _why in FIXABLE.values():
        key = tuple(cmd[:2]) if tuple(cmd[:2]) in _COMMANDS else (cmd[0],)
        assert key in _COMMANDS, f"{cmd} is not a real command"


def test_sync_fix_dry_run_changes_nothing(tmp_path, capsys):
    from magi.sync import run_fixes

    report = {"hints_structured": [
        {"code": "index-missing", "text": "...", "params": {}},
        {"code": "ingest-start", "text": "...", "params": {}},
    ]}
    ran, failed = run_fixes(report, dry_run=True)
    assert (ran, failed) == (1, 0)
    out = capsys.readouterr().out
    assert "would run magi index" in out
    assert "ingest" not in out.replace("would run magi index", "")


def test_sync_fix_deduplicates_repeated_commands(capsys):
    from magi.sync import run_fixes

    report = {"hints_structured": [
        {"code": "index-missing", "text": "", "params": {}},
        {"code": "index-stale", "text": "", "params": {}},
    ]}
    ran, _ = run_fixes(report, dry_run=True)
    assert ran == 1, "two hints about the same index should not run it twice"


# --------------------------------------------------------------------------
# magi migrate — finishes the job unless told not to
# --------------------------------------------------------------------------

def test_migrate_follows_through_by_default():
    import inspect

    from magi import migrate

    src = inspect.getsource(migrate.main)
    assert "--minimal" in src
    assert "follow_up = not args.minimal" in src
    assert inspect.signature(migrate._migrate_hub).parameters["follow_up"].default is True


# --------------------------------------------------------------------------
# magi ingest auto — route by what the file is, not by what you remember
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name,cfg,expected", [
    ("paper.tex", {"tools": {"pandoc_path": "/usr/bin/pandoc"}}, "tex"),
    ("2401.00001.tar.gz", {"tools": {"pandoc_path": "/usr/bin/pandoc"}}, "tex"),
    ("paper.pdf", {"ocr": {"mineru_api_token": "tok"}}, "mineru"),
    ("notes.md", {}, "add"),
    ("notes.txt", {}, "add"),
    ("archive.zip", {}, "skip"),
])
def test_routing(tmp_path, name, cfg, expected):
    from magi.ingest.auto import classify

    route, why = classify(tmp_path / name, cfg)
    assert route == expected, why
    assert why


def test_a_pdf_with_no_route_says_why(tmp_path, monkeypatch):
    from magi.ingest import auto

    monkeypatch.setattr(auto.shutil, "which", lambda _n: None)
    route, why = auto.classify(tmp_path / "paper.pdf", {})
    assert route == "skip"
    assert "mineru_api_token" in why and "Ollama" in why


def test_text_files_land_in_notes_and_papers_elsewhere():
    from magi.ingest.auto import default_type

    assert default_type("add") == "notes"
    assert default_type("mineru") == default_type("tex") == "papers"


def test_ingest_auto_is_registered():
    from magi.cli import _COMMANDS
    from magi.core.cli_i18n import command_help_zh

    assert _COMMANDS[("ingest", "auto")][0] == "magi.ingest.auto"
    assert command_help_zh(("ingest", "auto"))


# --------------------------------------------------------------------------
# magi skills install — asks which CLI instead of writing to all of them
# --------------------------------------------------------------------------

def test_installing_everywhere_is_never_the_default(monkeypatch):
    from magi import skills_cmd

    hosts = list(skills_cmd.HOSTS.values())
    monkeypatch.setattr(skills_cmd, "detected_hosts", lambda config=None: hosts)

    with pytest.raises(SystemExit) as excinfo:
        skills_cmd._resolve_hosts(None, interactive=False)
    msg = str(excinfo.value)
    assert "say which one" in msg
    for h in hosts:
        assert f"--host {h.key}" in msg

    assert skills_cmd._resolve_hosts(["all"]) == list(skills_cmd.HOSTS.values())
    assert skills_cmd._resolve_hosts(["auto"]) == hosts
    assert [h.key for h in skills_cmd._resolve_hosts(["codex"])] == ["codex"]


def test_a_single_detected_host_needs_no_question(monkeypatch):
    from magi import skills_cmd

    only = [skills_cmd.HOSTS["codex"]]
    monkeypatch.setattr(skills_cmd, "detected_hosts", lambda config=None: only)
    assert skills_cmd._resolve_hosts(None, interactive=False) == only
