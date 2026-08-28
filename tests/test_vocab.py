"""The v2 vocabulary: what a status word may be, and who may write it.

Every other v2 mechanism reads statuses — `magi next` ranks by them, the
reviewer is triggered by one specific transition, `sync --close` audits them.
So the failure this file exists to catch is not "a bad word got written" but
"two parts of the system disagreed about which words exist", which shows up
much later as a note nobody's router can see.

Two rules here are not bookkeeping and are worth stating twice. Closing a
research line is a ritual reserved for a person (design-v2 §6): an agent that
can close a line can quietly end a research direction while nobody is reading.
And `conflict` is never chosen — it is what the CLI writes when two writers
flipped the same status at once, so only the system enters it and only a person
leaves it.
"""

import pytest

from magi.core import vocab


# --------------------------------------------------------------------------
# the vocabulary is internally consistent
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kind", vocab.KINDS)
def test_every_kind_has_statuses_and_a_starting_one(kind):
    assert vocab.statuses(kind)
    assert vocab.INITIAL_STATUS[kind] in vocab.statuses(kind)


@pytest.mark.parametrize("kind", vocab.KINDS)
def test_transitions_only_name_statuses_the_kind_has(kind):
    """A typo in the transition table is invisible until a flip is rejected."""
    for status in vocab.statuses(kind):
        assert vocab.is_status(kind, status)
        for target in vocab.allowed_targets(kind, status):
            assert vocab.is_status(kind, target), f"{kind}: {status} → {target}"


@pytest.mark.parametrize("kind", vocab.KINDS)
def test_conflict_is_reachable_from_everywhere(kind):
    for status in vocab.statuses(kind):
        assert vocab.CONFLICT in vocab.allowed_targets(kind, status)


def test_a_status_from_another_kind_is_not_a_status():
    assert not vocab.is_status(vocab.LINE, "supported")
    assert not vocab.is_status(vocab.PROPOSITION, "exploring")
    assert not vocab.is_legal_transition(vocab.PROPOSITION, "open", "active")


def test_superseded_is_terminal():
    """A proposition replaced by a paper is finished. If the question comes
    back it comes back as a new proposition, with a new slug and its own
    history — reopening this one would silently rewrite what was published."""
    targets = vocab.allowed_targets(vocab.PROPOSITION, "superseded")
    assert targets == (vocab.CONFLICT,)


def test_no_transition_out_of_open_backwards():
    for status in ("conjectured", "testing", "supported", "refuted"):
        assert "open" not in vocab.allowed_targets(vocab.PROPOSITION, status)


def test_staying_put_is_legal_and_is_not_a_transition():
    assert vocab.is_legal_transition(vocab.PROPOSITION, "testing", "testing")
    assert not vocab.is_legal_transition(vocab.PROPOSITION, "nonsense", "nonsense")


# --------------------------------------------------------------------------
# who may write what
# --------------------------------------------------------------------------

def test_only_a_person_closes_a_line():
    assert vocab.writers(vocab.LINE, "active", "closed") == frozenset({vocab.HUMAN})
    assert not vocab.may_write(vocab.AGENT, vocab.LINE, "active", "closed")
    assert vocab.may_write(vocab.HUMAN, vocab.LINE, "active", "closed")


def test_only_the_cli_writes_conflict_and_only_a_person_resolves_it():
    assert vocab.writers(vocab.PROPOSITION, "testing", vocab.CONFLICT) == frozenset({vocab.CLI})
    assert vocab.writers(vocab.PROPOSITION, vocab.CONFLICT, "testing") == frozenset({vocab.HUMAN})
    assert not vocab.may_write(vocab.AGENT, vocab.PROPOSITION, vocab.CONFLICT, "testing")


def test_ordinary_bookkeeping_is_written_by_whoever_is_nearest():
    """The default has to be permissive or the locality principle is a lie."""
    for actor in (vocab.AGENT, vocab.HUMAN, vocab.REVIEWER, vocab.CLI):
        assert vocab.may_write(actor, vocab.PROPOSITION, "testing", "supported")


def test_the_reviewer_can_dispute_what_it_reviewed():
    assert vocab.may_write(vocab.REVIEWER, vocab.PROPOSITION, "supported", "disputed")


def test_an_illegal_transition_has_no_writers():
    assert vocab.writers(vocab.PROPOSITION, "superseded", "open") == frozenset()
    assert not vocab.may_write(vocab.HUMAN, vocab.PROPOSITION, "superseded", "open")


def test_the_review_trigger_is_a_real_transition():
    kind, status = vocab.REVIEW_TRIGGER
    assert vocab.is_status(kind, status)
    for pair in vocab.QUEUE_TRIGGERS:
        assert vocab.is_status(*pair)


# --------------------------------------------------------------------------
# temperature
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path,tier", [
    ("raw/papers/2601.00001.md", vocab.COLD),
    ("wiki/references/kitaev-2003.md", vocab.COLD_DERIVED),
    ("wiki/concepts/toric-code.md", vocab.WARM_SHARED),
    ("wiki/topics/qec-landscape.md", vocab.WARM_SHARED),
    ("drafts/gap-argument.md", vocab.WARM_LINE),
    ("inbox/notes.md", vocab.HOT),
    ("scratch/chunk_01.md", vocab.HOT),
])
def test_a_directory_decides_temperature_outside_threads(path, tier):
    assert vocab.tier_of(path) == tier


def test_windows_separators_are_the_same_paths():
    assert vocab.tier_of(r"wiki\concepts\toric-code.md") == vocab.WARM_SHARED


def test_derived_artefacts_have_no_temperature():
    """`None` rather than a guess, following `durability.classify`: a path
    nobody decided about should say so instead of being sorted somewhere."""
    assert vocab.tier_of("output/graph.db") is None
    assert vocab.tier_of("config.yaml") is None


@pytest.mark.parametrize("kind,status,tier", [
    (vocab.PROPOSITION, "open", vocab.HOT),
    (vocab.PROPOSITION, "conjectured", vocab.HOT),
    (vocab.PROPOSITION, "testing", vocab.HOT),
    (vocab.PROPOSITION, "disputed", vocab.HOT),
    (vocab.PROPOSITION, vocab.CONFLICT, vocab.HOT),
    (vocab.PROPOSITION, "supported", vocab.WARM_LINE),
    (vocab.PROPOSITION, "refuted", vocab.WARM_LINE),
    (vocab.PROPOSITION, "superseded", vocab.WARM_LINE),
    (vocab.QUESTION, "open", vocab.HOT),
    (vocab.QUESTION, "answered", vocab.WARM_LINE),
    (vocab.LINE, "active", vocab.HOT),
    (vocab.LINE, "dormant", vocab.WARM_LINE),
])
def test_a_thread_note_takes_its_temperature_from_kind_and_status(kind, status, tier):
    """Files never move between tiers — that is the point of deriving it."""
    assert vocab.tier_of("threads/x.md", kind, status) == tier


def test_an_unreadable_thread_note_is_treated_as_hot():
    """Hot promises the least, so it is the safe answer when the status is
    unknown: nothing downstream will treat the note as settled."""
    assert vocab.tier_of("threads/x.md") == vocab.HOT


def test_tiers_are_ordered_coldest_first():
    assert vocab.is_hotter(vocab.HOT, vocab.COLD)
    assert not vocab.is_hotter(vocab.COLD, vocab.HOT)
    assert not vocab.is_hotter(vocab.HOT, "not-a-tier")


def test_leaving_an_adjudication_is_a_human_decision():
    """`conflict`, `disputed` and `closed` all exist to stop the machine from
    settling the question itself. If an agent may walk back out of them, the
    decision queue is a suggestion box — the reviewer's rejection gets flipped
    back by the next run and nobody is ever asked."""
    assert vocab.writers(vocab.PROPOSITION, "disputed", "supported") == frozenset({vocab.HUMAN})
    assert vocab.writers(vocab.PROPOSITION, vocab.CONFLICT, "testing") == frozenset({vocab.HUMAN})
    assert vocab.writers(vocab.LINE, "closed", "active") == frozenset({vocab.HUMAN})
    for actor in (vocab.AGENT, vocab.REVIEWER, vocab.CLI):
        assert not vocab.may_write(actor, vocab.PROPOSITION, "disputed", "supported")
        assert not vocab.may_write(actor, vocab.LINE, "closed", "active")


def test_entering_disputed_is_not_gated():
    """The reviewer has to be able to raise the objection on its own; only
    dismissing it is the human's call."""
    assert vocab.may_write(vocab.REVIEWER, vocab.PROPOSITION, "supported", "disputed")
    assert vocab.may_write(vocab.AGENT, vocab.PROPOSITION, "supported", "disputed")
