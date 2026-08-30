"""What `magi migrate` does to a workspace v1 actually built.

The suite next door winds a v2 scaffold backwards to make its fixture, which
is close enough for most of what migration does and wrong about the one thing
that matters here: the index files. v1 wrote a line into every `_index.md` it
created, under the very heading migration reads to decide whether a person has
written there. A backwards-wound v2 scaffold has no such line, so the check
passed in tests and failed on every real library.

The index text below is copied from the last pre-rebuild commit — from
`bin/init_workspace.py:create_minimal_index` and the identical block in
`bin/llm-wiki.py:ensure_dir_index`. v1's `index_builder` rebuilt only
`wiki/references` and `wiki/concepts`, so in `wiki/theses/` it was never
cleared.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys

import pytest

from magi import migrate


#: Exactly what v1 wrote when it created an index, date apart.
V1_INDEX = (
    "# Theses\n\n"
    "## Contents\n\n"
    "| File | Summary | Tags | Updated |\n"
    "|------|---------|------|---------|\n\n"
    "## Recent Changes\n\n"
    "- 2025-11-02: Created missing index.\n"
)

THESIS = ("---\ntitle: Gap Argument\ntype: thesis\n---\n\n# Gap Argument\n\nBody.\n")


@pytest.fixture
def v1_workspace(tmp_path):
    """A library as v1 left it: no v2 marker files, v1's own index text."""
    root = tmp_path / "peng-ye"
    for sub in ("raw/notes", "wiki/concepts", "wiki/topics", "wiki/references",
                "wiki/theses"):
        (root / sub).mkdir(parents=True)
    (root / "wiki" / "theses" / "_index.md").write_text(V1_INDEX, encoding="utf-8")
    (root / "wiki" / "theses" / "gap-argument.md").write_text(THESIS, encoding="utf-8")
    (root / "config.md").write_text(
        "---\ntitle: Peng Ye\nscope: transport\n---\n", encoding="utf-8")
    (root / "log.md").write_text("# Log\n", encoding="utf-8")
    return root


def _migrate(root, *extra):
    return subprocess.run(
        [sys.executable, "-m", "magi", "migrate", str(root), "--minimal", *extra],
        capture_output=True, text=True, encoding="utf-8", errors="replace")


def _hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


# --------------------------------------------------------------------------
# the conversion that did not happen
# --------------------------------------------------------------------------

def test_the_index_v1_wrote_itself_does_not_count_as_a_persons_note(v1_workspace):
    """`retire_theses` keeps the directory when somebody has written under
    `## Recent Changes`. v1 put a line there on the day it made the file, so
    the check found the tool's own bootstrap line and read it as a person's —
    and the theses conversion, one of the two migration exists to guarantee,
    silently did not happen for any real library."""
    _migrate(v1_workspace)

    assert not (v1_workspace / "wiki" / "theses").exists(), (
        "wiki/theses/ survived migration; its _index.md holds only the line v1 "
        "wrote when it created the file")
    assert (v1_workspace / "drafts" / "gap-argument.md").is_file()


def test_a_line_a_person_wrote_still_keeps_the_directory(v1_workspace):
    """The other side of the same check, so the fix above cannot be widened
    into "delete whatever is under this heading"."""
    index = v1_workspace / "wiki" / "theses" / "_index.md"
    index.write_text(V1_INDEX + "- ask Wei about the boundary term\n", encoding="utf-8")

    result = _migrate(v1_workspace)

    assert (v1_workspace / "wiki" / "theses").is_dir()
    assert "has notes under" in result.stderr


def test_a_name_already_taken_keeps_its_content_not_just_its_existence(v1_workspace):
    """Asserting `.is_file()` on the file left behind says nothing about what
    is in it: emptying it would pass that check. What the promise is worth is
    the bytes."""
    (v1_workspace / "drafts").mkdir()
    (v1_workspace / "drafts" / "gap-argument.md").write_text("mine\n", encoding="utf-8")
    original = (v1_workspace / "wiki" / "theses" / "gap-argument.md").read_bytes()

    result = _migrate(v1_workspace)

    assert (v1_workspace / "drafts" / "gap-argument.md").read_text(encoding="utf-8") == "mine\n"
    assert (v1_workspace / "wiki" / "theses" / "gap-argument.md").read_bytes() == original
    assert "already exists" in result.stderr


# --------------------------------------------------------------------------
# looking before moving
# --------------------------------------------------------------------------

def test_a_dry_run_writes_absolutely_nothing(v1_workspace):
    """The files it moves are the only copy the user has, and `CLAUDE.md` is
    the one thing given a backup. Checked by hashing every file, not by
    reading the report the command wrote about itself."""
    before = _hashes(v1_workspace)

    result = subprocess.run(
        [sys.executable, "-m", "magi", "migrate", str(v1_workspace), "--dry-run"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")

    assert result.returncode == 0
    assert "would move 1 file(s)" in result.stdout
    assert _hashes(v1_workspace) == before, "a dry run changed something on disk"


def test_the_dry_run_and_the_real_run_agree_about_the_theses(v1_workspace):
    """A preview nobody checked against the thing it previews is a second
    implementation waiting to disagree."""
    planned_moved, planned_skipped = migrate.retire_theses(v1_workspace, dry_run=True)
    assert (v1_workspace / "wiki" / "theses" / "gap-argument.md").is_file()

    moved, skipped = migrate.retire_theses(v1_workspace)

    assert (moved, skipped) == (planned_moved, planned_skipped)


# --------------------------------------------------------------------------
# the hub
# --------------------------------------------------------------------------

def test_a_hub_migrates_every_project_under_it(tmp_path):
    """`_migrate_hub` had no behavioural test at all — the only reference to
    it anywhere in the suite read a default argument off its signature."""
    hub = tmp_path / "hub"
    (hub / "topics").mkdir(parents=True)
    (hub / "wikis.json").write_text('{"topics": []}', encoding="utf-8")
    for name in ("alpha", "beta"):
        project = hub / "topics" / name
        (project / "wiki" / "theses").mkdir(parents=True)
        (project / "raw").mkdir(parents=True)
        (project / "wiki" / "theses" / "_index.md").write_text(V1_INDEX, encoding="utf-8")
        (project / "wiki" / "theses" / f"{name}-argument.md").write_text(
            THESIS, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "magi", "migrate", str(hub), "--minimal"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")

    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("alpha", "beta"):
        project = hub / "topics" / name
        assert (project / "drafts" / f"{name}-argument.md").is_file(), (
            f"{name} was not migrated: {result.stdout}")
        assert not (project / "wiki" / "theses").exists()


# --------------------------------------------------------------------------
# what the derived artifacts inherit from a v1 file
# --------------------------------------------------------------------------

def test_a_half_quoted_title_does_not_reach_the_graph_with_its_quote():
    """v1 libraries were hand-edited for a year, so malformed frontmatter is
    normal input, not an edge case. `parse_scalar` unquotes only when both
    ends match and otherwise returned the value untouched, so
    `title: "Unclosed quote concept` was written into `output/graph.db` with
    the quote still attached and shown that way in the browser.

    The file is malformed either way and `magi lint` reports it; the graph
    should not repeat the typo back forever."""
    from magi.kb.llmwiki import parse_scalar

    assert parse_scalar('"Unclosed quote concept') == "Unclosed quote concept"
    assert parse_scalar("'half open") == "half open"
    # The cases that were already right stay right.
    assert parse_scalar('"proper"') == "proper"
    assert parse_scalar("'ok'") == "ok"
    assert parse_scalar('a"b') == 'a"b'
