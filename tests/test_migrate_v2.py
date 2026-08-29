"""What `magi migrate` does to a workspace built before v2.

Two conversions cannot be left to the person, because both are the kind of
thing that stays half-done forever:

**`wiki/theses/` splits.** v2 has no theses directory. What a thesis was is now
two things that behave differently — the working out, which is a draft, and the
claims it makes, which are propositions with a status somebody keeps current.
Only the first half moves mechanically; the second is a judgement, so migration
moves the file and says what is left to do rather than pretending it finished.

**`CLAUDE.md` collapses to a pointer.** Two files holding the same protocol
drift, and once they have, "what was the agent told" depends on which host read
which copy. The generated protocol is identical in both so collapsing loses
nothing — but text a person wrote is kept where they can find it.

The third property is the one that makes the command safe to run at all:
running it twice changes nothing the second time.
"""

import subprocess
import sys

import pytest

from magi import migrate


THESIS = ("---\ntitle: Gap Argument\ntype: thesis\ncreated: 2026-01-01\n"
          "updated: 2026-01-01\ntags: [qec]\nsummary: The gap survives.\n---\n\n"
          "# Gap Argument\n\nBody.\n")


@pytest.fixture
def old_workspace(tmp_path):
    """A v2 scaffold wound back to look like a pre-v2 library."""
    subprocess.run([sys.executable, "-m", "magi", "init",
                    "--topic-dir", str(tmp_path), "--name", "T"],
                   capture_output=True, text=True, check=True)
    theses = tmp_path / "wiki" / "theses"
    theses.mkdir(parents=True)
    (theses / "gap-argument.md").write_text(THESIS, encoding="utf-8")
    (theses / "_index.md").write_text("# Theses\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# MAGI Research Workspace: T\n\nold protocol\n",
                                        encoding="utf-8")
    return tmp_path


def _migrate(ws):
    result = subprocess.run([sys.executable, "-m", "magi", "migrate", str(ws), "--minimal"],
                            cwd=ws, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    assert "Traceback" not in result.stderr, result.stderr
    return result


# --------------------------------------------------------------------------
# theses
# --------------------------------------------------------------------------

def test_a_thesis_becomes_a_draft(old_workspace):
    _migrate(old_workspace)

    assert (old_workspace / "drafts" / "gap-argument.md").is_file()
    assert not (old_workspace / "wiki" / "theses").exists()


def test_the_move_says_what_it_could_not_do(old_workspace):
    """Turning prose into propositions is a judgement. Saying so is the
    difference between a migration that finished and one that looks finished."""
    out = _migrate(old_workspace).stdout
    assert "drafts/" in out
    assert "proposition" in out


def test_a_name_already_taken_is_left_alone_rather_than_guessed_about(old_workspace):
    (old_workspace / "drafts" / "gap-argument.md").write_text("mine\n", encoding="utf-8")

    result = _migrate(old_workspace)

    assert (old_workspace / "drafts" / "gap-argument.md").read_text(encoding="utf-8") == "mine\n"
    assert (old_workspace / "wiki" / "theses" / "gap-argument.md").is_file()
    assert "already exists" in result.stderr


def test_a_workspace_with_no_theses_is_untouched(tmp_path):
    subprocess.run([sys.executable, "-m", "magi", "init",
                    "--topic-dir", str(tmp_path), "--name", "T"],
                   capture_output=True, text=True, check=True)
    assert migrate.retire_theses(tmp_path) == (0, [])


def _theses(tmp_path, index_body=""):
    theses = tmp_path / "wiki" / "theses"
    theses.mkdir(parents=True, exist_ok=True)
    (theses / "a-thesis.md").write_text("# working out\n", encoding="utf-8")
    (theses / "_index.md").write_text(
        "# Theses\n\n## Contents\n\n| File |\n| :--- |\n" + index_body,
        encoding="utf-8")
    return theses


def test_a_generated_index_goes_with_the_directory(tmp_path):
    theses = _theses(tmp_path)

    moved, skipped = migrate.retire_theses(tmp_path)

    assert (moved, skipped) == (1, [])
    assert not theses.exists()


def test_an_index_somebody_wrote_in_is_not_deleted(tmp_path):
    """Everything under `## Recent Changes` is carried through by every index
    rebuild, precisely because a person typed it. A migration that is careful
    with a name collision and careful with CLAUDE.md was throwing these away
    on the way out."""
    theses = _theses(tmp_path, "\n## Recent Changes\n\n- the sweep stalled at n=40\n")

    moved, skipped = migrate.retire_theses(tmp_path)

    assert moved == 1
    assert skipped == ["_index.md"]
    assert theses.is_dir()
    assert "n=40" in (theses / "_index.md").read_text(encoding="utf-8")


def test_an_empty_recent_changes_section_is_still_just_generated(tmp_path):
    theses = _theses(tmp_path, "\n## Recent Changes\n\n")

    assert migrate.retire_theses(tmp_path) == (1, [])
    assert not theses.exists()


# --------------------------------------------------------------------------
# the two instruction files become one
# --------------------------------------------------------------------------

def test_claude_md_is_reduced_to_a_pointer(old_workspace):
    _migrate(old_workspace)
    assert (old_workspace / "CLAUDE.md").read_text(encoding="utf-8").strip() == "@AGENTS.md"


def test_text_only_claude_md_had_is_kept_where_it_can_be_found(old_workspace):
    (old_workspace / "CLAUDE.md").write_text("# House rules\n\nAlways ask first.\n",
                                             encoding="utf-8")

    result = _migrate(old_workspace)

    assert (old_workspace / "CLAUDE.md").read_text(encoding="utf-8").strip() == "@AGENTS.md"
    kept = sorted((old_workspace / ".backup").glob("CLAUDE_*.md"))
    assert kept, "the old CLAUDE.md was not kept anywhere"
    assert any("Always ask first." in p.read_text(encoding="utf-8") for p in kept)
    assert "move anything you still want" in result.stderr


def test_a_pointer_that_is_already_a_pointer_is_not_backed_up(old_workspace):
    (old_workspace / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    assert migrate.point_claude_at_agents(old_workspace) is None
    assert [p.name for p in old_workspace.glob("CLAUDE.md.*")] == []


# --------------------------------------------------------------------------
# running it twice
# --------------------------------------------------------------------------

def test_migrating_twice_changes_nothing_the_second_time(old_workspace):
    """The command exists to be run by somebody who is not sure whether they
    already ran it."""
    _migrate(old_workspace)
    before = {p.relative_to(old_workspace): p.read_bytes()
              for p in sorted(old_workspace.rglob("*"))
              if p.is_file() and "output" not in p.parts and ".beads" not in p.parts}

    _migrate(old_workspace)
    after = {p.relative_to(old_workspace): p.read_bytes()
             for p in sorted(old_workspace.rglob("*"))
             if p.is_file() and "output" not in p.parts and ".beads" not in p.parts}

    assert set(after) == set(before)
    changed = [str(k) for k in before if before[k] != after[k]]
    assert changed == [], changed


def test_a_workspace_that_could_not_be_scaffolded_is_not_half_migrated(
        old_workspace, monkeypatch, capsys):
    """It printed "this workspace is not migrated" and then moved every file
    out of `wiki/theses/` and rewrote `CLAUDE.md`. The half that ran anyway
    was the destructive half, under a message saying nothing had happened."""
    from magi import init_workspace

    monkeypatch.setattr(init_workspace, "main", lambda *a, **k: 1)
    theses_before = sorted(p.name for p in (old_workspace / "wiki" / "theses").iterdir())
    claude_before = (old_workspace / "CLAUDE.md").read_text(encoding="utf-8")

    code = migrate._migrate_topic(old_workspace)

    assert code == 1
    assert "not migrated" in capsys.readouterr().err
    assert sorted(p.name for p in (old_workspace / "wiki" / "theses").iterdir()) == \
        theses_before, "theses were moved into a workspace that has no drafts/"
    assert (old_workspace / "CLAUDE.md").read_text(encoding="utf-8") == claude_before
