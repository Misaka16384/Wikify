"""The order a batch is reviewed in, and the thing that order must not become.

This was on the list for a while with nothing behind it, so it got measured
before it got built. Sixteen real conversions — MinerU and local OCR, native
PDFs and scans, each with independently known quality — through the actual
gates:

    4 of 16 documents carried a flag
    3 of 3 known-bad documents were among them
    1 of 11 known-good documents was too

So flags are selective rather than universal, which is the only thing that
makes sorting on them worth anything, and they point at the right documents.

And the same corpus settles what this must not turn into. One document in it is
missing half of a 49-row table and carries **no flag at all** — the model wrote
24 rows, stopped, and produced a page that reads as complete. "Unflagged" is
therefore not "checked", and an ordering that quietly became "approve the rest"
would ship exactly that document. Nothing here hides, drops, or decides.
"""

import types

import pytest

from magi.ingest import ledger


def _item(item_id, findings=(), decision=None):
    return ledger.BatchItem(
        item_id=item_id, req_id="r-" + item_id, route="ocr",
        source_type="file", source_value=f"{item_id}.pdf", title=item_id,
        arxiv_id=None, staged_md=f"{item_id}.md",
        findings=[dict(f) for f in findings], error=None,
        decision=decision, committed_path=None, retry_of=None)


FLAG = {"code": "tables-dropped", "detail": "...", "severity": "flag"}
OTHER = {"code": "repetition-loop", "detail": "...", "severity": "flag"}
INFO = {"code": "route-textlayer", "detail": "...", "severity": "info"}


# --------------------------------------------------------------------------
# what rises
# --------------------------------------------------------------------------

def test_a_flagged_item_comes_before_a_clean_one():
    order = ledger.review_order([_item("b"), _item("a", [FLAG])])
    assert [i.item_id for i in order] == ["a", "b"]


def test_more_flags_comes_first():
    order = ledger.review_order(
        [_item("a", [FLAG]), _item("b", [FLAG, OTHER]), _item("c")])
    assert [i.item_id for i in order] == ["b", "a", "c"]


def test_an_info_finding_does_not_promote_anything():
    """Every text-layer document carries `route-textlayer`, and every OCR
    document that repaired a page carries `page-repaired`. If those counted,
    a whole rung would sort above a genuine problem for saying what it did."""
    order = ledger.review_order([_item("a", [INFO, INFO]), _item("b", [FLAG])])
    assert [i.item_id for i in order] == ["b", "a"]


def test_a_decided_item_sinks_even_when_it_was_flagged():
    """It has had its attention. What is left to decide comes first."""
    order = ledger.review_order(
        [_item("a", [FLAG, OTHER], decision="approve"), _item("b")])
    assert [i.item_id for i in order] == ["b", "a"]


def test_the_order_is_stable_between_runs():
    """A queue that reshuffles between two runs that found the same things
    costs the reader the place they had got to."""
    items = [_item(x) for x in ("c", "a", "b")]
    once = [i.item_id for i in ledger.review_order(items)]
    assert once == [i.item_id for i in ledger.review_order(list(reversed(items)))]


# --------------------------------------------------------------------------
# what it must not do
# --------------------------------------------------------------------------

def test_nothing_is_dropped():
    """The measured false-negative rate is the reason: a document with no
    flags can still be missing half a table, so an ordering that filtered
    would be hiding the failure this pipeline exists to catch."""
    items = [_item(x, [FLAG] if x == "b" else []) for x in "abcde"]
    assert len(ledger.review_order(items)) == 5
    assert {i.item_id for i in ledger.review_order(items)} == set("abcde")


def test_no_decision_is_made_or_changed():
    items = [_item("a", [FLAG]), _item("b", decision="reject")]
    before = [(i.item_id, i.decision) for i in items]
    after = {i.item_id: i.decision for i in ledger.review_order(items)}
    assert all(after[item_id] == decision for item_id, decision in before)


def test_the_input_list_is_left_alone():
    items = [_item("b"), _item("a", [FLAG])]
    ledger.review_order(items)
    assert [i.item_id for i in items] == ["b", "a"]


def test_an_item_with_no_findings_field_does_not_break_the_sort():
    """Older ledger records predate findings entirely, and a batch written by
    one build gets read by the next."""
    bare = _item("a")._replace(findings=[])
    assert ledger.loud_findings(bare) == 0
    assert [i.item_id for i in ledger.review_order([bare, _item("b", [FLAG])])] \
        == ["b", "a"]


# --------------------------------------------------------------------------
# both renderings agree
# --------------------------------------------------------------------------

def test_the_cli_and_the_api_sort_the_same_queue_the_same_way():
    """Two views of one queue that disagree about which item is most urgent is
    the drift this codebase has paid for elsewhere — a count computed in JS and
    again in Python, and a panel that showed zero. One function, both callers."""
    import inspect

    from magi.ingest import batch
    from magi.ui import api

    for module in (batch, api):
        source = inspect.getsource(module)
        assert "review_order" in source, module.__name__
