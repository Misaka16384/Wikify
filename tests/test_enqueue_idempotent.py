"""Queueing the same paper twice should not queue it twice.

Measured: clicking the browser button three times on one arXiv tab produced
three identical entries in `queue.jsonl`, which `batch-run` would convert three
times and put three rows in front of a reviewer.

The rule is "still waiting", not "ever seen", and the three exemptions below
are each a real workflow rather than an edge case. They are the reason this is
not simply a set of everything the ledger has recorded.
"""

import pytest

from magi.ingest import ledger


@pytest.fixture()
def topic(tmp_path):
    (tmp_path / "output" / "ingest").mkdir(parents=True)
    return tmp_path


def test_the_same_source_twice_returns_the_first_request(topic):
    first = ledger.enqueue(topic, source_type="arxiv", value="2410.11942")
    second = ledger.enqueue(topic, source_type="arxiv", value="2410.11942")
    assert first == second
    assert len(ledger.pending(topic)) == 1


def test_three_clicks_leave_one_entry(topic):
    """The measured case, exactly."""
    for _ in range(3):
        ledger.enqueue(topic, source_type="arxiv", value="2410.11942",
                       title="Operator algebra")
    assert len(ledger.pending(topic)) == 1


def test_different_papers_are_not_collapsed(topic):
    ledger.enqueue(topic, source_type="arxiv", value="2410.11942")
    ledger.enqueue(topic, source_type="arxiv", value="2503.03827")
    assert len(ledger.pending(topic)) == 2


def test_the_same_value_under_a_different_type_is_a_different_request(topic):
    ledger.enqueue(topic, source_type="url", value="10.1103/PhysRevX.8.031051")
    ledger.enqueue(topic, source_type="doi", value="10.1103/PhysRevX.8.031051")
    assert len(ledger.pending(topic)) == 2


# --------------------------------------------------------------------------
# the three exemptions
# --------------------------------------------------------------------------

def test_a_retry_is_never_deduplicated(topic):
    """The downgrade path. A rejected item is requeued on the next rung down,
    and collapsing it into the request it descends from would end that path."""
    first = ledger.enqueue(topic, source_type="arxiv", value="2410.11942")
    retry = ledger.enqueue(topic, source_type="arxiv", value="2410.11942",
                           route="tex", retry_of=first)
    assert retry != first
    assert len(ledger.pending(topic)) == 2


def test_a_retry_does_not_block_a_later_ordinary_request(topic):
    """A retry is exempt from being deduplicated; it must not become the thing
    that everything else deduplicates *against* either, or one rejection would
    silently swallow every later click on that paper."""
    first = ledger.enqueue(topic, source_type="arxiv", value="2410.11942")
    ledger.enqueue(topic, source_type="arxiv", value="2410.11942",
                   route="tex", retry_of=first)
    again = ledger.enqueue(topic, source_type="arxiv", value="2410.11942")
    assert again == first          # matches the ordinary request still waiting


def test_a_request_a_batch_already_took_does_not_block_a_new_one(topic, monkeypatch):
    """Re-ingest. arXiv issues a new version and the paper is worth converting
    again — only what is *still waiting* may collapse."""
    first = ledger.enqueue(topic, source_type="arxiv", value="2410.11942")
    batch_id = ledger.start_batch(topic)
    ledger.record_item(topic, batch_id, req_id=first, route="arxiv-html",
                       source_type="arxiv", source_value="2410.11942",
                       title=None, arxiv_id="2410.11942", staged_md=None,
                       findings=[], error=None, retry_of=None)
    assert ledger.pending(topic) == []

    second = ledger.enqueue(topic, source_type="arxiv", value="2410.11942")
    assert second != first
    assert len(ledger.pending(topic)) == 1


def test_another_library_is_another_destination(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    for ws in (a, b):
        (ws / "output" / "ingest").mkdir(parents=True)
    ledger.enqueue(a, source_type="arxiv", value="2410.11942", library="a")
    ledger.enqueue(b, source_type="arxiv", value="2410.11942", library="b")
    assert len(ledger.pending(a)) == 1
    assert len(ledger.pending(b)) == 1


# --------------------------------------------------------------------------
# saying so
# --------------------------------------------------------------------------

def test_find_pending_reports_what_is_waiting(topic):
    assert ledger.find_pending(topic, "arxiv", "2410.11942") is None
    req = ledger.enqueue(topic, source_type="arxiv", value="2410.11942")
    found = ledger.find_pending(topic, "arxiv", "2410.11942")
    assert found is not None and found.req_id == req


def test_the_endpoint_distinguishes_the_two_outcomes():
    """A caller told "queued" when nothing was queued is worse off than one
    told nothing: the duplicate it replaced was at least visible."""
    import inspect

    from magi.ui import api

    src = inspect.getsource(api)
    assert '"already-queued" if already else "queued"' in src
