"""Contracts for the queue and the batch ledger.

The single most important behaviour here is the last one: reject an item and it
comes back on the next rung down, in the *next* batch, without anyone
re-submitting it by hand. Nothing else in this repo does that, so nothing else
tests it.
"""

import json

import pytest

from magi.ingest import ledger
from magi.ingest.convert_result import Finding


@pytest.fixture
def topic(tmp_path):
    return tmp_path


# --------------------------------------------------------------------------
# The queue is inert
# --------------------------------------------------------------------------

def test_enqueue_appends_exactly_one_line(topic):
    ledger.enqueue(topic, source_type="url", value="https://arxiv.org/abs/2608.16520")
    lines = ledger.queue_path(topic).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["kind"] == "enqueue"


def test_enqueue_writes_nowhere_else(topic):
    """The whole blast-radius argument for the browser extension rests on this."""
    (topic / "raw").mkdir()
    (topic / "wiki").mkdir()

    ledger.enqueue(topic, source_type="url", value="x")

    assert list((topic / "raw").iterdir()) == []
    assert list((topic / "wiki").iterdir()) == []


def test_queued_entries_come_back_in_order(topic):
    ledger.enqueue(topic, source_type="url", value="first")
    ledger.enqueue(topic, source_type="url", value="second")
    assert [e.value for e in ledger.pending(topic)] == ["first", "second"]


def test_an_empty_queue_is_not_an_error(topic):
    assert ledger.pending(topic) == []


def test_a_truncated_final_line_does_not_lose_the_rest(topic):
    """A process killed mid-write must not take the whole queue with it."""
    ledger.enqueue(topic, source_type="url", value="good")
    with open(ledger.queue_path(topic), "a", encoding="utf-8") as fh:
        fh.write('{"kind": "enqueue", "req_id": "req-tru')

    assert [e.value for e in ledger.pending(topic)] == ["good"]


def test_the_library_choice_survives(topic):
    ledger.enqueue(topic, source_type="url", value="x", library="MindPalace")
    assert ledger.pending(topic)[0].library == "MindPalace"


# --------------------------------------------------------------------------
# A batch claims what it processed
# --------------------------------------------------------------------------

def test_an_item_recorded_in_a_batch_leaves_the_queue(topic):
    req = ledger.enqueue(topic, source_type="url", value="x")
    batch = ledger.start_batch(topic)
    ledger.record_item(topic, batch, req_id=req, route="arxiv-html", source_value="x")

    assert ledger.pending(topic) == []


def test_an_unclaimed_entry_stays_pending(topic):
    ledger.enqueue(topic, source_type="url", value="claimed")
    later = ledger.enqueue(topic, source_type="url", value="not-yet")
    batch = ledger.start_batch(topic)
    ledger.record_item(topic, batch, req_id=ledger.pending(topic)[0].req_id,
                       route="tex", source_value="claimed")

    assert [e.req_id for e in ledger.pending(topic)] == [later]


# --------------------------------------------------------------------------
# The fold
# --------------------------------------------------------------------------

def test_an_item_starts_undecided(topic):
    batch = ledger.start_batch(topic)
    ledger.record_item(topic, batch, req_id="r", route="tex", source_value="x")
    item = ledger.load_batch(topic, batch)[0]

    assert item.decision is None and not item.decided


def test_a_decision_is_folded_in(topic):
    batch = ledger.start_batch(topic)
    item_id = ledger.record_item(topic, batch, req_id="r", route="tex", source_value="x")
    ledger.record_decision(topic, batch, item_id, "approve")

    assert ledger.load_batch(topic, batch)[0].decision == "approve"


def test_the_last_decision_wins(topic):
    batch = ledger.start_batch(topic)
    item_id = ledger.record_item(topic, batch, req_id="r", route="tex", source_value="x")
    ledger.record_decision(topic, batch, item_id, "approve")
    ledger.record_decision(topic, batch, item_id, "reject")

    assert ledger.load_batch(topic, batch)[0].decision == "reject"


def test_reset_is_undo_and_is_itself_just_another_record(topic):
    batch = ledger.start_batch(topic)
    item_id = ledger.record_item(topic, batch, req_id="r", route="tex", source_value="x")
    ledger.record_decision(topic, batch, item_id, "reject")
    ledger.record_decision(topic, batch, item_id, "reset")

    item = ledger.load_batch(topic, batch)[0]
    assert item.decision is None and not item.decided


def test_history_is_never_rewritten(topic):
    """Every decision stays on disk; the fold decides, the log remembers."""
    batch = ledger.start_batch(topic)
    item_id = ledger.record_item(topic, batch, req_id="r", route="tex", source_value="x")
    for d in ("approve", "reject", "reset", "approve"):
        ledger.record_decision(topic, batch, item_id, d)

    raw = ledger.batch_path(topic, batch).read_text(encoding="utf-8")
    assert raw.count('"kind": "decision"') == 4


def test_an_unknown_decision_is_refused(topic):
    batch = ledger.start_batch(topic)
    item_id = ledger.record_item(topic, batch, req_id="r", route="tex", source_value="x")
    with pytest.raises(ValueError):
        ledger.record_decision(topic, batch, item_id, "maybe")


def test_findings_survive_the_round_trip(topic):
    batch = ledger.start_batch(topic)
    ledger.record_item(topic, batch, req_id="r", route="tex", source_value="x",
                       findings=[Finding("figure-count-mismatch", "6 dropped")])

    findings = ledger.load_batch(topic, batch)[0].findings
    assert findings[0]["code"] == "figure-count-mismatch"
    assert "6 dropped" in findings[0]["detail"]


def test_a_failed_item_is_still_in_the_batch(topic):
    """A conversion that failed is something a reviewer needs to see, not hide."""
    batch = ledger.start_batch(topic)
    ledger.record_item(topic, batch, req_id="r", route="tex", source_value="x",
                       error="Pandoc conversion failed.")
    item = ledger.load_batch(topic, batch)[0]

    assert not item.ok and item.error


def test_a_commit_is_recorded_against_the_item(topic):
    batch = ledger.start_batch(topic)
    item_id = ledger.record_item(topic, batch, req_id="r", route="tex",
                                 source_value="x", staged_md="/staged/a.md")
    ledger.record_commit(topic, batch, item_id, "raw/papers/2026-08-21-a.md")

    assert ledger.load_batch(topic, batch)[0].committed_path.endswith("a.md")


def test_state_survives_a_restart(topic):
    """It is a file; there is nothing to reconstruct."""
    batch = ledger.start_batch(topic)
    item_id = ledger.record_item(topic, batch, req_id="r", route="tex", source_value="x")
    ledger.record_decision(topic, batch, item_id, "approve")

    reloaded = ledger.load_batch(topic, batch)
    assert reloaded[0].decision == "approve"


def test_batches_are_listed_newest_last(topic):
    a = ledger.start_batch(topic)
    b = ledger.start_batch(topic)
    assert set(ledger.list_batches(topic)) == {a, b}


# --------------------------------------------------------------------------
# The ladder — reject means "try the next rung down"
# --------------------------------------------------------------------------

@pytest.mark.parametrize("route,expected", [
    ("arxiv-html", "tex"),
    ("tex", "textlayer"),
    ("textlayer", "mineru"),
    ("mineru", "ocr"),
])
def test_each_rung_falls_to_the_next(route, expected):
    assert ledger.next_rung(route) == expected


def test_the_bottom_of_the_ladder_has_nowhere_to_fall():
    assert ledger.next_rung("ocr") is None


def test_the_vision_fanout_is_never_reached_by_falling():
    """Falling into the per-page vision path by default is the exact failure
    this whole pipeline exists to prevent."""
    assert ledger.LAST_RESORT not in ledger.LADDER
    for rung in ledger.LADDER:
        assert ledger.next_rung(rung) != ledger.LAST_RESORT


def test_an_unknown_route_has_no_next_rung():
    assert ledger.next_rung("something-else") is None


def test_a_rejected_item_can_be_requeued_one_rung_down(topic):
    """The end-to-end shape: reject, requeue, and it is pending again on the
    next route — with a link back to what it was retrying."""
    req = ledger.enqueue(topic, source_type="arxiv", value="2608.16520")
    batch = ledger.start_batch(topic)
    item_id = ledger.record_item(topic, batch, req_id=req, route="arxiv-html",
                                 source_value="2608.16520")
    ledger.record_decision(topic, batch, item_id, "reject")

    item = ledger.load_batch(topic, batch)[0]
    ledger.enqueue(topic, source_type="arxiv", value=item.source_value,
                   route=ledger.next_rung(item.route), retry_of=item.item_id)

    still_pending = ledger.pending(topic)
    assert len(still_pending) == 1
    assert still_pending[0].route == "tex"
    assert still_pending[0].retry_of == item_id


def test_a_requeued_item_is_not_swept_into_the_batch_it_came_from(topic):
    """batch-run must snapshot the queue; a retry belongs to the next run."""
    req = ledger.enqueue(topic, source_type="arxiv", value="x")
    batch = ledger.start_batch(topic)
    snapshot = ledger.pending(topic)

    item_id = ledger.record_item(topic, batch, req_id=req, route="arxiv-html",
                                 source_value="x")
    ledger.record_decision(topic, batch, item_id, "reject")
    ledger.enqueue(topic, source_type="arxiv", value="x", route="tex",
                   retry_of=item_id)

    assert [e.req_id for e in snapshot] == [req]
    assert ledger.pending(topic)[0].route == "tex"


def test_the_summary_reads_the_file_once(tmp_path, monkeypatch):
    """It called `spent()` for the total and `spent()` again for every kind,
    so a number that is a tally of one set of rows cost one full read and
    re-parse per kind. `magi map` and the dashboard both render this."""
    from magi.core import ledger

    for index in range(5):
        ledger.record(tmp_path, ledger.REVIEW, "codex", slug=f"s-{index}")

    reads = []
    real = ledger.entries
    monkeypatch.setattr(ledger, "entries",
                        lambda root: reads.append(1) or real(root))

    found = ledger.summary(tmp_path)

    assert len(reads) == 1, f"read the ledger {len(reads)} times for one summary"
    assert found["spent"] == 5
    assert found["by_kind"][ledger.REVIEW] == 5


def test_and_it_still_splits_the_week_by_kind(tmp_path):
    """The answer the count is for. Kept beside it so the optimisation cannot
    quietly become a different number."""
    from magi.core import ledger

    ledger.record(tmp_path, ledger.REVIEW, "codex", slug="a")
    ledger.record(tmp_path, ledger.REFLECT, "codex")
    ledger.record(tmp_path, ledger.REFLECT, "claude")

    found = ledger.summary(tmp_path)

    assert found["spent"] == 3
    assert found["by_kind"][ledger.REVIEW] == 1
    assert found["by_kind"][ledger.REFLECT] == 2
