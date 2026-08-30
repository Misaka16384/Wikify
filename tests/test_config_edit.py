"""Surgical config.yaml editing: comments survive, YAML never corrupts."""

from __future__ import annotations

import yaml

from magi.core.config_edit import set_config_value


def test_scalar_edit_preserves_comments_and_siblings(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "# header comment\ntopic: t\nradar:\n  days: 7\n  # inner comment\n  max_candidates: 40\n",
        encoding="utf-8")
    set_config_value(p, "radar.days", 14)
    text = p.read_text(encoding="utf-8")
    assert "# header comment" in text
    assert "# inner comment" in text
    data = yaml.safe_load(text)
    assert data["radar"]["days"] == 14
    assert data["radar"]["max_candidates"] == 40
    assert data["topic"] == "t"


def test_block_list_collapses_to_flow(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        "radar:\n  seed_arxiv_ids:\n    - '2401.00505'\n    - '2606.10000'\n  days: 7\n",
        encoding="utf-8")
    set_config_value(p, "radar.seed_arxiv_ids", ["2401.00505"])
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert data["radar"]["seed_arxiv_ids"] == ["2401.00505"]
    assert data["radar"]["days"] == 7


def test_append_missing_section_and_nullable(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("topic: t\n", encoding="utf-8")
    set_config_value(p, "radar.min_relevance", 0.25)
    assert yaml.safe_load(p.read_text(encoding="utf-8"))["radar"]["min_relevance"] == 0.25
    set_config_value(p, "radar.min_relevance", None)
    assert yaml.safe_load(p.read_text(encoding="utf-8"))["radar"]["min_relevance"] is None


def test_cjk_content_untouched(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("topic: 量子拓扑\n", encoding="utf-8")
    set_config_value(p, "models.embedding", "qwen3-embedding:0.6b")
    text = p.read_text(encoding="utf-8")
    assert "量子拓扑" in text
    assert yaml.safe_load(text)["models"]["embedding"] == "qwen3-embedding:0.6b"


def test_two_writers_at_once_both_land(tmp_path):
    """Read-modify-write of one text file, which is the shape that drops an
    update. `magi reflect promote` and `magi reflect retire` both go through
    here, and a dropped retire is the silent one: nothing reconciles
    `research.rules` against the ledger, so a rule the person removed keeps
    failing `lint` while the ledger records it as gone."""
    import threading

    config = tmp_path / "config.yaml"
    config.write_text("research:\n  weekly_calls: 10\n", encoding="utf-8")

    start = threading.Barrier(2)

    def write(key, value):
        start.wait()
        set_config_value(config, f"research.{key}", value)

    workers = [threading.Thread(target=write, args=("rule_budget", 7)),
               threading.Thread(target=write, args=("weekly_calls", 42))]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    import yaml as _yaml
    parsed = _yaml.safe_load(config.read_text(encoding="utf-8"))
    assert parsed["research"]["rule_budget"] == 7, "one writer's edit was lost"
    assert parsed["research"]["weekly_calls"] == 42, "the other writer's edit was lost"
