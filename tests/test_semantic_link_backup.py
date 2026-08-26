"""Where `magi link` puts the copy it makes before rewriting the concept cards.

`magi link --auto-merge` edits and merges concept files in place, so the backup
it takes first is the only record of what the wiki said beforehand. Two things
have to hold for that to be worth anything: the copies must not be read back as
concept cards by the passes that walk the wiki, and one run must not destroy the
previous run's backup.

The old location — a flat `scratch/concept_backups/` — got neither. `scratch/`
is documented as "deleting this costs time, never information", and every run
copied onto the same filenames, so running the command twice replaced the
backup of the good state with a backup of the already-merged one.
"""

import os

from magi.core import durability
from magi.kb import semantic_link


def _workspace(tmp_path, cards):
    concepts = tmp_path / "wiki" / "concepts"
    concepts.mkdir(parents=True)
    for name, body in cards.items():
        (concepts / name).write_text(body, encoding="utf-8")
    return tmp_path, str(concepts)


def test_the_backup_lands_where_the_scanners_already_skip(tmp_path):
    """`.backup` is the existing convention — `magi wiki refactor-concept`,
    which this module shells out to, has always written there, and six scanners
    skip any path with it as a component."""
    topic, concepts = _workspace(tmp_path, {"toric-code.md": "# Toric code\n"})

    semantic_link.backup_concepts(str(topic), concepts)

    copies = list((tmp_path / "wiki" / "concepts" / ".backup").rglob("toric-code.md"))
    assert len(copies) == 1
    assert ".backup" in copies[0].parts
    assert not (tmp_path / "scratch").exists()


def test_a_second_run_does_not_replace_the_first_runs_backup(tmp_path):
    """The backup was reliable right up until the moment you needed it: run
    the command twice and the good state was gone."""
    topic, concepts = _workspace(tmp_path, {"toric-code.md": "GOOD\n"})

    semantic_link.backup_concepts(str(topic), concepts)
    # Same instant is the hostile case — a same-second second run must still
    # not land on top of the first.
    (tmp_path / "wiki" / "concepts" / "toric-code.md").write_text("MERGED\n",
                                                                 encoding="utf-8")
    semantic_link.backup_concepts(str(topic), concepts)

    saved = sorted(p.read_text(encoding="utf-8")
                   for p in (tmp_path / "wiki" / "concepts" / ".backup")
                   .rglob("toric-code.md"))
    assert "GOOD\n" in saved, "the pre-merge state was overwritten by the re-run"


def test_the_backup_is_not_filed_as_disposable(tmp_path):
    """It sits under `wiki/`, which the durability convention calls ORIGINAL —
    so "delete the derived trees and re-run" never reaches it."""
    topic, concepts = _workspace(tmp_path, {"toric-code.md": "# Toric code\n"})
    semantic_link.backup_concepts(str(topic), concepts)

    copy = next((tmp_path / "wiki" / "concepts" / ".backup").rglob("*.md"))
    rel = os.path.relpath(copy, tmp_path).replace("\\", "/")
    assert durability.classify(rel) == "original"
    assert durability.is_regenerable(rel) is False
