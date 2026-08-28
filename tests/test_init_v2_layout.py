"""What `magi init` scaffolds in v2, and why each piece is there.

A workspace's shape is an interface: the skills, the lint rules and the router
all address directories by name, so "which directories exist" is not a detail
that can drift. This is the test that fails when it does.

Three of the entries carry a decision rather than a convention:

* `threads/` — research state lives in files, not in a task tracker. A
  proposition with a status is the unit the whole v2 loop reads.
* `decisions.md` — the one file nothing writes on its own initiative. An agent
  transcribes what a person decided; that is all that goes in it.
* `wiki/theses/` is **gone**. Its two halves moved: the working out to
  `drafts/`, the claims to `threads/`. An old workspace keeps its copy until
  `magi migrate` moves it, which is why lint tolerates one and requires none.
"""

import subprocess
import sys

import pytest

from magi.core import managed
from magi.core.workspace import INBOX_NON_SOURCES


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    path = tmp_path_factory.mktemp("v2-layout")
    subprocess.run([sys.executable, "-m", "magi", "init",
                    "--topic-dir", str(path), "--name", "T"],
                   capture_output=True, text=True, check=True)
    return path


@pytest.mark.parametrize("rel", [
    "raw", "raw/papers", "wiki", "wiki/concepts", "wiki/topics", "wiki/references",
    "threads", "drafts", "output", "inbox", "scratch",
])
def test_the_directories_a_v2_workspace_has(workspace, rel):
    assert (workspace / rel).is_dir(), rel


def test_theses_is_retired(workspace):
    assert not (workspace / "wiki" / "theses").exists()


def test_the_two_human_surfaces_exist(workspace):
    """One to write decisions into, one to dump anything into. A person who
    has to choose between five places writes in none of them."""
    assert (workspace / "decisions.md").is_file()
    assert (workspace / "inbox" / "notes.md").is_file()


def test_claude_md_points_at_agents_md_instead_of_copying_it(workspace):
    """Two files with the same protocol drift, and then the answer to "what
    was the agent told" depends on which host read which copy."""
    assert (workspace / "CLAUDE.md").read_text(encoding="utf-8").strip() == "@AGENTS.md"


def test_the_protocol_sits_in_a_managed_block(workspace):
    text = (workspace / "AGENTS.md").read_text(encoding="utf-8")
    body = managed.read(text)
    assert body is not None
    assert "MAGI" in body


def test_a_fresh_workspace_lints_clean(workspace):
    """The scaffold is what every other test starts from, so a workspace that
    is born with a complaint makes every downstream failure ambiguous."""
    result = subprocess.run([sys.executable, "-m", "magi", "lint", "."],
                            cwd=workspace, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    assert "Traceback" not in result.stderr, result.stderr
    assert result.returncode == 0, result.stdout
    assert "0 critical" in result.stdout


def test_an_old_workspace_keeps_its_theses_directory(tmp_path):
    """Retiring a directory must not turn every existing library's next lint
    run into a wall of "unexpected file" — those people did nothing."""
    subprocess.run([sys.executable, "-m", "magi", "init",
                    "--topic-dir", str(tmp_path), "--name", "T"],
                   capture_output=True, text=True, check=True)
    theses = tmp_path / "wiki" / "theses"
    theses.mkdir(parents=True)
    (theses / "old.md").write_text(
        "---\ntitle: Old\ntype: thesis\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        "tags: [x]\nsummary: An old thesis.\n---\n\n# Old\n\nBody.\n", encoding="utf-8")

    result = subprocess.run([sys.executable, "-m", "magi", "lint", "."],
                            cwd=tmp_path, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    assert "Traceback" not in result.stderr, result.stderr
    assert "Unexpected" not in result.stdout


def test_the_dump_area_is_not_something_to_ingest(workspace):
    """`inbox/` now holds two unrelated things: sources waiting to be turned
    into `raw/`, and the file a person types into. Counting the second as the
    first tells somebody they have work waiting that they do not, and handing
    it to the pipeline tries to turn a scratch pad into a paper."""
    assert "notes.md" in INBOX_NON_SOURCES

    result = subprocess.run([sys.executable, "-m", "magi", "ingest", "auto", "--json"],
                            cwd=workspace, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    assert "Traceback" not in result.stderr, result.stderr
    assert "nothing to ingest" in result.stdout, result.stdout

