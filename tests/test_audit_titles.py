"""Which cards a bad title extraction damaged, found without re-fetching.

A wrong title does not leave a broken file. It leaves a plausible one — a
paper filed under "Abstract", or cut at a word boundary so it still reads like
a title — and nothing in the project can tell. On the library this was built
for, 13 of 36 committed cards were wrong and the only reason anybody knew was
that a person checked all of them by hand against the arXiv API.

The recovery is free because `output/ingest/batch-*.jsonl` records the title as
extracted and is in the never-rebuilt set. The ledger is what the extractor
said; the card is what is there now.

Run against that real library while this was written: 12 disagreements, which
is the number their own log recorded for the correction pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from magi.ingest import audit_titles


@pytest.fixture
def project(tmp_path):
    from magi import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    (tmp_path / "output" / "ingest").mkdir(parents=True, exist_ok=True)
    (tmp_path / "raw" / "papers").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _ledger(project: Path, rows: list[dict]) -> None:
    lines = [json.dumps(dict(kind="item", **r), ensure_ascii=False) for r in rows]
    (project / "output" / "ingest" / "batch-aaaa.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def _card(project: Path, name: str, arxiv_id: str, title: str) -> Path:
    p = project / "raw" / "papers" / name
    p.write_text(f"---\ntitle: {title}\narxiv_id: '{arxiv_id}'\n---\n\nbody\n",
                 encoding="utf-8")
    return p


def test_a_corrected_card_is_reported(project):
    _ledger(project, [{"arxiv_id": "1806.08679", "title": "Abstract"}])
    _card(project, "a.md", "1806.08679", "Foliated fracton order")

    found = audit_titles.disagreements(project)
    assert len(found) == 1
    assert found[0]["extracted"] == "Abstract"
    assert found[0]["on_disk"] == "Foliated fracton order"


def test_an_untouched_card_is_not(project):
    _ledger(project, [{"arxiv_id": "2204.06023", "title": "A Real Title"}])
    _card(project, "b.md", "2204.06023", "A Real Title")

    assert audit_titles.disagreements(project) == []


def test_quoting_alone_is_not_a_disagreement(project):
    """The ledger sometimes keeps the quotes the frontmatter drops. Reporting
    that pair puts a formatting artifact in a list whose entire value is that
    every row means something."""
    _ledger(project, [{"arxiv_id": "1603.05182", "title": "'Fractal symmetries'"}])
    _card(project, "c.md", "1603.05182", "Fractal symmetries")

    assert audit_titles.disagreements(project) == []


def test_wrapping_alone_is_not_a_disagreement(project):
    _ledger(project, [{"arxiv_id": "1.1", "title": "Two   words"}])
    _card(project, "d.md", "1.1", "Two words")

    assert audit_titles.disagreements(project) == []


def test_the_join_survives_a_ledger_with_no_committed_path(project):
    """The first version joined on `committed_path`, which the ledger's item
    records do not carry — measured on a real library: 37 records, 35 with a
    title, 0 with a path. It found nothing and printed that every card was
    fine, which is the exact false-clean this command exists to prevent."""
    _ledger(project, [{"arxiv_id": "9.9", "title": "What The Extractor Said"}])
    _card(project, "e.md", "9.9", "What Is There Now")

    found = audit_titles.disagreements(project)
    assert len(found) == 1, "joined on a field the ledger does not record"


def test_a_project_that_never_ingested_says_so(project, capsys):
    import argparse

    code = audit_titles.cmd_audit_titles(
        argparse.Namespace(topic_dir=str(project), json=False))
    assert code == 0
    assert "nothing has been ingested" in capsys.readouterr().out


def test_a_clean_library_is_not_called_correct(project, capsys):
    """No disagreement means nothing was edited — not that the titles are
    right. Saying the second thing would be the command inventing an
    authority it does not have; it never contacts the source."""
    import argparse

    _ledger(project, [{"arxiv_id": "1.1", "title": "Same"}])
    _card(project, "f.md", "1.1", "Same")

    audit_titles.cmd_audit_titles(argparse.Namespace(topic_dir=str(project), json=False))
    out = capsys.readouterr().out
    assert "not the same as every title being right" in out
    assert "export.arxiv.org" in out, "it should say how to actually check"
