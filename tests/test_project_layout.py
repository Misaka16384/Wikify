"""The layout table is the only list of what a project contains.

Eight modules used to answer "which directories count" with a hand-typed
tuple, and the differences between them were mostly correct — a maintenance
pass that rewrites files must skip `threads/`, a wikilink never lands in
`raw/`. What went wrong was not the disagreement, it was that no two of them
could be read together, so `magi lint` walked `("raw", "wiki", "inventory",
"datasets")` — two directories that do not exist, and neither of the two the
v2 rebuild added — and nothing anywhere said so.

These tests are the mechanism that replaces the grep. A directory added to
the scaffold fails the first test until it appears in `LAYOUT` with every
question answered, and each subsystem's set is held against the column it
claims to implement. Adding a directory therefore forces a decision instead
of allowing an omission, which is the only difference that stops this
happening again.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from magi.core.project import LAYOUT, Dir, Project, dirs, wikilink_dirs


@pytest.fixture(scope="module")
def scaffold(tmp_path_factory):
    """What `magi init` actually creates — the ground truth."""
    root = tmp_path_factory.mktemp("layout") / "p"
    subprocess.run([sys.executable, "-m", "magi", "init", "--project-dir", str(root),
                    "--name", "T"], capture_output=True, text=True, check=True)
    return root


def test_the_table_and_the_scaffold_agree_in_both_directions(scaffold):
    """The test that makes the rest of this file work.

    In one direction: a directory `magi init` creates that nobody classified
    is a directory every subsystem will silently skip. In the other: a row
    for a directory that no longer exists is how `magi lint` came to walk
    `inventory/` and `datasets/` long after they stopped being scaffolded.
    """
    on_disk = {p.name for p in scaffold.iterdir() if p.is_dir()
               and not p.name.startswith(".")}
    described = set(LAYOUT)

    unclassified = sorted(on_disk - described)
    assert not unclassified, (
        f"`magi init` creates {unclassified} and core/project.py does not "
        "describe them, so every subsystem that asks the layout a question "
        "will leave them out without saying so")

    imaginary = sorted(described - on_disk)
    assert not imaginary, (
        f"core/project.py describes {imaginary}, which `magi init` does not "
        "create — the shape of the `inventory`/`datasets` bug")


def test_every_directory_answers_every_question():
    """A row cannot be half-filled. The flags have no defaults except
    `wikilink`, which is genuinely optional, so this mostly guards against a
    future flag being added with a default that quietly means "no"."""
    answerable = [f.name for f in Dir.__dataclass_fields__.values()
                  if f.name not in ("what", "note", "wikilink")]
    for name, spec in LAYOUT.items():
        for flag in answerable:
            assert isinstance(getattr(spec, flag), bool), (
                f"{name}.{flag} is not a yes or a no")
        assert spec.what.strip(), f"{name} has no description"


def test_a_false_flag_that_would_surprise_a_reader_says_why():
    """`raw` not being graphed and `threads` not being rewritten are
    decisions; `drafts` not being graphed is an open question. All three are
    invisible in a boolean, and the difference between "decided against" and
    "nobody looked" is the whole reason the omissions lasted."""
    for name in ("raw", "drafts", "threads", "inbox", "output", "scratch"):
        assert LAYOUT[name].note.strip(), (
            f"{name} has a False flag a reader would question and no reason "
            "recorded for it")


# --------------------------------------------------------------------------
# each subsystem's set is the column it claims to implement
# --------------------------------------------------------------------------

def test_maintenance_passes_use_the_rewritten_column():
    from magi.core.wiki_common import CORPUS_DIRS

    assert tuple(sorted(CORPUS_DIRS)) == tuple(sorted(dirs(rewritten=True)))


def test_the_retrieval_index_uses_the_searchable_column():
    from magi import retrieval

    assert tuple(sorted(retrieval.CORPUS)) == tuple(sorted(dirs(searchable=True)))


def test_the_lint_document_loader_uses_the_documents_column():
    """The one that was wrong. `drafts/` is where every derivation lives and
    lint never opened it; `inventory/` and `datasets/` have not existed since
    v1."""
    from magi.kb import llmwiki

    assert tuple(sorted(llmwiki.DOCUMENT_DIRS)) == tuple(sorted(dirs(documents=True)))


def test_wikilink_resolution_uses_the_wikilink_column():
    from magi import state

    assert tuple(state._LINK_DIRS) == wikilink_dirs()


# --------------------------------------------------------------------------
# a project is a handle, not a path
# --------------------------------------------------------------------------

def test_a_project_carries_its_config_so_callers_cannot_forget_it(scaffold):
    """`magi reflect` could not see a host the project declared because
    `config=` was an optional argument that six call sites did not pass. A
    config that travels with the root is not an argument anybody can omit."""
    project = Project.at(scaffold)

    assert project is not None
    assert project.root == scaffold
    assert isinstance(project.config, dict) and project.config


def test_directory_accessors_come_from_the_table(scaffold):
    project = Project.of(scaffold)

    assert project.drafts == scaffold / "drafts"
    assert project.threads == scaffold / "threads"
    with pytest.raises(AttributeError):
        project.nonexistent_directory


def test_resolve_cannot_leave_the_project(tmp_path):
    """Both traversal holes found in review were a caller that forgot to
    check. This one cannot be forgotten because there is nothing to remember:
    the refusal is in the only function that turns text into a path."""
    root = tmp_path / "p"
    (root / "raw").mkdir(parents=True)
    outside = tmp_path / "secret.md"
    outside.write_text("not yours\n", encoding="utf-8")

    project = Project(root=root, config={})

    assert project.resolve("raw/../raw") == (root / "raw").resolve()
    for escape in ("../secret.md", "raw/../../secret.md", str(outside)):
        with pytest.raises(ValueError):
            project.resolve(escape)
    assert project.contains(root / "raw") is True
    assert project.contains(outside) is False


def test_markdown_skips_generated_indexes_and_backups(tmp_path):
    root = tmp_path / "p"
    (root / "wiki" / "concepts" / ".backup").mkdir(parents=True)
    (root / "drafts").mkdir(parents=True)
    (root / "wiki" / "concepts" / "a.md").write_text("a\n", encoding="utf-8")
    (root / "wiki" / "concepts" / "_index.md").write_text("i\n", encoding="utf-8")
    (root / "wiki" / "concepts" / ".backup" / "a.md").write_text("old\n", encoding="utf-8")
    (root / "drafts" / "d.md").write_text("d\n", encoding="utf-8")

    found = {p.name for p in Project(root=root, config={}).markdown(rewritten=True)}

    assert found == {"a.md", "d.md"}
