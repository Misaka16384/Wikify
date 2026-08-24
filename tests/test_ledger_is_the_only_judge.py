"""One question about a batch item, one implementation of the answer.

D4 in the roadmap says: *a piece of the UI that is making a judgement rather
than rendering one probably belongs in Python.* The version that actually cost
something was worse than that — not JavaScript re-deriving a Python answer,
but **two Python implementations of the same answer, one of them wrong**:

* rejecting an item requeues it one rung down. The CLI inherited the item's own
  source type; the WebUI passed the literal ``"arxiv"`` for everything, so a
  rejected local PDF was recorded as an arXiv paper whose identifier was a file
  path.
* counting what a batch still owes a person. The CLI asked ``item.decided``,
  which is strict about which words count; one WebUI endpoint flattened items
  to dicts first and asked ``not row["decision"]``, which agrees only until
  something writes a third value.

Both were introduced in the same feature whose *point* was to stop this — the
review ordering shipped one day earlier is shared by both front ends precisely
because of D4. So the guard cannot be "remember not to do it again".

`ledger` owns these answers now, and the scans below say so in a form that
fails a test rather than a review.
"""

import pathlib
import re

import pytest

from magi.ingest import ledger


def _src():
    return pathlib.Path(ledger.__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# structural: nobody re-derives the answers
# --------------------------------------------------------------------------

def test_nothing_outside_the_ledger_hardcodes_a_source_type():
    """A literal source type at an enqueue site is a guess written down as
    fact — which is exactly what `routing.infer_source_type` exists to avoid
    doing silently."""
    src = _src()
    # A keyword assignment specifically. `routing.infer_source_type` returning
    # the literal "url" is the definition of the vocabulary, not a guess about
    # one item; `return "url"` does not match this.
    bad = re.compile(r"""source_type\s*=\s*['"]""")
    offenders = []
    for path in src.rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if bad.search(line):
                offenders.append(f"{path.relative_to(src)}:{n}: {line.strip()}")

    assert not offenders, (
        "these pass a literal source type instead of inheriting the item's or "
        "calling routing.infer_source_type():\n  " + "\n  ".join(offenders))


def test_the_web_api_does_not_reimplement_the_decided_test():
    """`BatchItem.decided` is stricter than truthiness. Asking the flattened
    dict instead quietly reintroduces the looser test."""
    api = _src() / "ui" / "api.py"
    subscript = re.compile(r"""\[\s*['"]decision['"]\s*\]""")
    offenders = []
    for n, line in enumerate(api.read_text(encoding="utf-8").splitlines(), 1):
        code = line.split("#", 1)[0]          # a comment may quote the bug
        if "not " in code and subscript.search(code):
            offenders.append(f"{n}: {line.strip()}")

    assert not offenders, (
        "these judge decidedness off a dict rather than BatchItem.decided; "
        "use ledger.undecided():\n  " + "\n  ".join(offenders))


# --------------------------------------------------------------------------
# behavioural: the shared answers are the right ones
# --------------------------------------------------------------------------

def _item(**kw):
    base = dict(item_id="i1", req_id="r1", route="mineru", source_type="file",
                source_value="D:/docs/paper.pdf", title="A Paper", arxiv_id=None,
                staged_md=None, findings=[], error=None, decision=None,
                committed_path=None, retry_of=None)
    base.update(kw)
    return ledger.BatchItem(**base)


def test_a_rejected_local_file_is_requeued_as_a_local_file(tmp_path):
    nxt = ledger.requeue_next_rung(tmp_path, _item())
    assert nxt == "ocr"
    queued = ledger.pending(tmp_path)
    assert [q.source_type for q in queued] == ["file"]
    assert [q.value for q in queued] == ["D:/docs/paper.pdf"]


def test_a_rejected_url_keeps_being_a_url(tmp_path):
    ledger.requeue_next_rung(
        tmp_path, _item(source_type="url", source_value="https://x.test/p.pdf"))
    assert [q.source_type for q in ledger.pending(tmp_path)] == ["url"]


def test_an_item_with_no_recorded_type_gets_one_inferred(tmp_path):
    """Records written before the ledger stored the type. Inferring is a guess;
    writing "arxiv" over a file path was a guess already made and forgotten."""
    ledger.requeue_next_rung(
        tmp_path, _item(source_type="", source_value="D:/docs/paper.pdf"))
    assert [q.source_type for q in ledger.pending(tmp_path)] == ["file"]


def test_retry_of_points_at_the_item_not_the_request(tmp_path):
    ledger.requeue_next_rung(tmp_path, _item(item_id="item-9", req_id="req-9"))
    assert [q.retry_of for q in ledger.pending(tmp_path)] == ["item-9"]


def test_the_bottom_of_the_ladder_requeues_nothing(tmp_path):
    assert ledger.requeue_next_rung(tmp_path, _item(route="ocr")) is None
    assert ledger.pending(tmp_path) == []


# --------------------------------------------------------------------------

@pytest.mark.parametrize("decision,still_waiting", [
    (None, True), ("approve", False), ("reject", False),
    ("", True), ("maybe", True), ("APPROVE", True),
])
def test_only_the_two_words_that_mean_something_count_as_decided(decision, still_waiting):
    """`"maybe"` is truthy, so `not row["decision"]` would call it decided."""
    items = [_item(decision=decision)]
    assert bool(ledger.undecided(items)) is still_waiting


def test_a_committed_item_no_longer_blocks_a_commit():
    """Deliberately a different question from `undecided`."""
    items = [_item(decision=None, committed_path="raw/papers/x.md")]
    assert ledger.undecided(items) == items
    assert ledger.blocking_commit(items) == []
