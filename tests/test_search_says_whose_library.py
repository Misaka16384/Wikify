"""A search that could not look at your library has to say so, last.

The persona wrote a note in a fresh workspace, searched for it, and got a full
page of results from unrelated projects on the same machine. Their own note was
not among them, because the workspace had no index yet. The one line explaining
that — `note: KB 'local' has no index — skipping` — sat above the results, on
stderr, in the same grey as every other note, in the position everybody scrolls
past.

Two different events were being reported with one sentence. Another registered
KB having no index is housekeeping: it contributes nothing and the rest of the
search is unaffected. **This** workspace having no index means the search never
looked at what the person was asking about, and every answer on the screen came
from somewhere else. That is not a note, it is the answer.

Nothing is hidden. The cross-library results were asked for by the default
scope and they stay; what changes is that the reader can tell what they are
looking at.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pytest

from magi import retrieval


def _workspace(path: Path, name: str) -> Path:
    done = subprocess.run([sys.executable, "-m", "magi", "init",
                           "--topic-dir", str(path), "--name", name],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    (path / "wiki" / "concepts").mkdir(parents=True, exist_ok=True)
    return path


def _search(root: Path, query: str) -> argparse.Namespace:
    return argparse.Namespace(query=query, mode="bm25", k=5, scope="auto",
                              kb=None, collection=None, path=None,
                              topic_dir=str(root), json=False)


def test_a_lone_unindexed_workspace_refuses_rather_than_answering(tmp_path, capsys):
    """The older, stricter behaviour, and still right: with nowhere else to
    look there is nothing to report but the missing index."""
    root = _workspace(tmp_path / "mine", "Mine")
    (root / "wiki" / "concepts" / "c.md").write_text(
        "---\ntitle: C\n---\nferromagnetic impurity\n", encoding="utf-8")

    # `cmd_search` catches its own `SearchError` and reports it, so the check
    # is on what a person is told and on the exit code, not on the exception.
    code = retrieval.cmd_search(_search(root, "impurity"))

    assert code != 0
    assert "no index" in capsys.readouterr().err


def test_with_other_libraries_to_fall_back_on_it_says_so_at_the_end(tmp_path, capsys):
    """The reported case. Another library answers, this one cannot, and the
    person needs to know which of those they are reading."""
    other = _workspace(tmp_path / "other", "Other")
    (other / "wiki" / "concepts" / "o.md").write_text(
        "---\ntitle: O\n---\nferromagnetic impurity in another project\n",
        encoding="utf-8")
    built = subprocess.run([sys.executable, "-m", "magi", "index",
                            "--topic-dir", str(other), "--no-vectors", "--quiet"],
                           capture_output=True, text=True)
    if built.returncode != 0 or not (other / "output" / "index.db").is_file():
        pytest.skip("indexing is unavailable in this environment")

    mine = _workspace(tmp_path / "mine", "Mine")
    (mine / "wiki" / "concepts" / "c.md").write_text(
        "---\ntitle: C\n---\nferromagnetic impurity of my own\n", encoding="utf-8")

    retrieval.cmd_search(_search(mine, "impurity"))

    err = capsys.readouterr().err
    assert "not searchable yet" in err, (
        "the one line saying why nothing here was searched is still a footnote")
    assert "magi index" in err, "and it does not name the fix"


def test_another_librarys_missing_index_stays_a_footnote(tmp_path, capsys):
    """The distinction the fix turns on. Someone else's unindexed library is
    housekeeping and must not get the loud sentence, or the loud sentence stops
    meaning anything."""
    mine = _workspace(tmp_path / "mine", "Mine")
    (mine / "wiki" / "concepts" / "c.md").write_text(
        "---\ntitle: C\n---\nferromagnetic impurity of my own\n", encoding="utf-8")
    built = subprocess.run([sys.executable, "-m", "magi", "index",
                            "--topic-dir", str(mine), "--no-vectors", "--quiet"],
                           capture_output=True, text=True)
    if built.returncode != 0 or not (mine / "output" / "index.db").is_file():
        pytest.skip("indexing is unavailable in this environment")

    _workspace(tmp_path / "other", "Other")  # registered, never indexed

    retrieval.cmd_search(_search(mine, "impurity"))

    err = capsys.readouterr().err
    assert "not searchable yet" not in err, (
        "somebody else's missing index got this workspace's sentence")
