"""Commands must not report an outcome they did not have.

Five findings from the M3 review shared one shape: something failed, or was
about to happen, and the program said otherwise. A migration that scaffolded
nothing printed "6/6 topics migrated". A `--json` flag emitted text that was
not JSON. A `--dry-run` predicted one file and then the real run moved another.
A migration copied keys out of a stranger's config file. And the one command
the protocol tells every session to end with was not on the menu.

None of them crash. That is the point: the failure mode is a person acting on
a sentence that was not true, which is why each one gets a test rather than a
note in a changelog.
"""

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from magi import migrate


# --------------------------------------------------------------------------
# a migration that failed says so
# --------------------------------------------------------------------------

def test_a_topic_whose_scaffolding_failed_is_not_migrated(tmp_path, monkeypatch):
    """`_migrate_topic` warned and returned 0 anyway, so a hub loop counted a
    complete failure as a success and `main` exited 0 for a script to believe."""
    (tmp_path / "wiki").mkdir()
    monkeypatch.setattr("magi.init_workspace.main", lambda argv: 1)
    monkeypatch.setattr(migrate.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            returncode=0, stdout="", stderr=""))

    assert migrate._migrate_topic(tmp_path) == 1


def test_a_failed_graph_build_is_reported_but_does_not_fail_the_migration(
        tmp_path, monkeypatch, capsys):
    """The files are in place; the graph and the index are derived from them
    and `magi sync --fix` rebuilds both. Failing the migration over recoverable
    derived data would stop a hub loop over the topics that would have worked."""
    (tmp_path / "wiki").mkdir()
    monkeypatch.setattr("magi.init_workspace.main", lambda argv: 0)
    monkeypatch.setattr(migrate.subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            returncode=1, stdout="", stderr="boom"))

    assert migrate._migrate_topic(tmp_path) == 0
    said = capsys.readouterr().out
    assert "FAILED" in said and "magi sync --fix" in said


# --------------------------------------------------------------------------
# only settings this program has are carried across
# --------------------------------------------------------------------------

def _configs(tmp_path, legacy_text):
    (tmp_path / "config.yaml").write_text(
        "ollama:\n  base_url: \"http://127.0.0.1:11434\"\n"
        "models:\n  embedding: \"qwen3-embedding:0.6b\"\n", encoding="utf-8")
    legacy = tmp_path / "legacy.yaml"
    legacy.write_text(legacy_text, encoding="utf-8")
    return legacy


def test_a_known_setting_is_still_carried(tmp_path):
    """The feature: a token pasted a year ago should not have to be found and
    pasted again."""
    legacy = _configs(tmp_path, "ocr:\n  mineru_api_token: \"tok-123\"\n")

    assert migrate.carry_legacy_config(tmp_path, legacy) == ["ocr.mineru_api_token"]
    assert "tok-123" in (tmp_path / "config.yaml").read_text(encoding="utf-8")


def test_a_key_this_program_never_had_is_not_carried(tmp_path):
    """The search looks in `~/.claude` and `~/.gemini` — the agent CLIs' own
    directories, where a `config.yaml` is far more likely to be theirs than
    Wikify's. A section the new config lacks used to sail straight through the
    "never clobber a deliberate edit" guard on `current is None`."""
    legacy = _configs(tmp_path, "permissions:\n  allow: \"everything\"\n"
                                "telemetry:\n  endpoint: \"https://example.invalid\"\n")

    assert migrate.carry_legacy_config(tmp_path, legacy) == []
    written = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "example.invalid" not in written and "permissions" not in written


# --------------------------------------------------------------------------
# --json is JSON; --dry-run predicts the real run
# --------------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path):
    done = subprocess.run(
        [sys.executable, "-m", "magi", "init", "--topic-dir", str(tmp_path),
         "--name", "T"], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return tmp_path


def test_install_json_is_parseable_json(workspace):
    """The skills step used to print its human-readable report to stdout ahead
    of the JSON object, which is the one failure a `--json` flag exists to make
    impossible."""
    done = subprocess.run(
        [sys.executable, "-m", "magi", "install", "--topic-dir", str(workspace),
         "--host", "claude", "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")

    payload = json.loads(done.stdout)          # the assertion is that this works
    assert payload["hosts"] == ["claude"]
    assert "skills" in payload, "the skills step's own report belongs in the object"


def test_a_dry_run_predicts_the_claude_md_rewrite(workspace):
    """A real run collapses `CLAUDE.md` to a pointer, keeping a copy of what a
    person wrote there. The dry run compared only the managed block, so it said
    "block is current" and the real run then moved that file."""
    (workspace / "CLAUDE.md").write_text("# my own notes\n\nkeep this\n",
                                         encoding="utf-8")

    done = subprocess.run(
        [sys.executable, "-m", "magi", "install", "--topic-dir", str(workspace),
         "--host", "claude", "--dry-run", "--no-skills"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")

    assert "CLAUDE.md" in done.stdout, done.stdout
    assert (workspace / "CLAUDE.md").read_text(encoding="utf-8").startswith("# my own")


def test_a_dry_run_with_nothing_to_do_says_nothing_to_do(workspace):
    subprocess.run(
        [sys.executable, "-m", "magi", "install", "--topic-dir", str(workspace),
         "--host", "claude", "--no-skills"], capture_output=True, text=True)

    done = subprocess.run(
        [sys.executable, "-m", "magi", "install", "--topic-dir", str(workspace),
         "--host", "claude", "--dry-run", "--no-skills"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")

    assert "would" not in done.stdout, done.stdout


# --------------------------------------------------------------------------
# the command the protocol requires is on the menu
# --------------------------------------------------------------------------

def test_the_close_gate_is_a_command_a_person_can_find():
    """The managed block tells every session to end with `magi sync --close`.
    On the three hosts with no stop hook that is the only self-check there is,
    and it was reachable only through `--help --all`."""
    from magi.cli import PORCELAIN

    assert "sync" in PORCELAIN

    done = subprocess.run([sys.executable, "-m", "magi", "--help"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    assert "\n  sync " in done.stdout
    assert len(done.stdout.strip().splitlines()) <= 20, "one screen is the ratchet"
