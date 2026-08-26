"""What `magi init --force` lands on, and whether there is a way back.

`--force` says "Overwrite existing config/log/index files", which is honest
about what it does and silent about what that costs. The files it reaches are
ORIGINAL by the durability convention: `config.md` is the scope a person wrote,
`log.md` is the running record of the work, `config.yaml` is their settings.
Nothing regenerates any of them, so one mistyped flag in the wrong directory
used to be unrecoverable.
"""

import pytest

from magi.core import durability
from magi.hub import init_workspace


@pytest.fixture
def existing(tmp_path):
    """A workspace that has already been used, not a fresh directory."""
    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    (tmp_path / "config.md").write_text("# my real scope\n", encoding="utf-8")
    (tmp_path / "log.md").write_text("2026-08-01: did the work\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("radar:\n  days: 30\n", encoding="utf-8")
    return tmp_path


def _backups(path):
    return sorted((path.parent / ".backup").glob(f"{path.stem}_*{path.suffix}"))


@pytest.mark.parametrize("name", ["config.md", "log.md", "config.yaml"])
def test_force_keeps_what_it_overwrites(existing, name):
    target = existing / name
    before = target.read_text(encoding="utf-8")

    init_workspace.main(["--topic-dir", str(existing), "--name", "T", "--force"])

    assert target.read_text(encoding="utf-8") != before, "--force did not overwrite"
    kept = _backups(target)
    assert len(kept) == 1, f"no recoverable copy of {name}"
    assert kept[0].read_text(encoding="utf-8") == before


def test_without_force_nothing_is_touched_and_nothing_is_copied(existing):
    """The skip path must not start littering .backup directories."""
    before = (existing / "config.md").read_text(encoding="utf-8")

    init_workspace.main(["--topic-dir", str(existing), "--name", "T"])

    assert (existing / "config.md").read_text(encoding="utf-8") == before
    assert not (existing / ".backup").exists()


def test_a_fresh_workspace_makes_no_backups(tmp_path):
    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T", "--force"])
    assert not (tmp_path / ".backup").exists()


def test_two_forced_runs_keep_both_generations(existing):
    """A second --force must not overwrite the copy the first one saved — that
    is the state the user is most likely to actually want back."""
    original = (existing / "config.md").read_text(encoding="utf-8")

    init_workspace.main(["--topic-dir", str(existing), "--name", "T", "--force"])
    (existing / "config.md").write_text("# edited again\n", encoding="utf-8")
    init_workspace.main(["--topic-dir", str(existing), "--name", "T", "--force"])

    saved = [p.read_text(encoding="utf-8") for p in _backups(existing / "config.md")]
    assert original in saved, "the oldest generation was overwritten"
    assert "# edited again\n" in saved


def test_the_copies_are_not_filed_as_disposable(existing):
    init_workspace.main(["--topic-dir", str(existing), "--name", "T", "--force"])
    kept = _backups(existing / "config.md")[0]
    rel = kept.relative_to(existing).as_posix()
    assert durability.classify(rel) != "derived"
    assert durability.is_regenerable(rel) is False


def test_the_copies_stay_out_of_the_corpus(existing):
    """`.backup` is the convention every scanner already skips; a backup that
    gets indexed, linted or linked is a second copy of the wiki."""
    from magi.core.wiki_common import corpus_files

    init_workspace.main(["--topic-dir", str(existing), "--name", "T", "--force"])

    scanned = [p.relative_to(existing).as_posix() for p in corpus_files(existing)]
    assert not any(".backup" in p.split("/") for p in scanned), scanned
