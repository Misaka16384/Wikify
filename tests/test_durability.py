"""Which files a person made, and which a command will make again.

D3: derived and original data sit in the same tree with no marker, so every
question about deleting, resetting or backing something up gets re-reasoned
from scratch — and "just rebuild it" is only safe advice when you know what you
would lose.

The trap the categories exist to avoid is one path: `output/ingest/` is an
append-only record of what a person queued, decided and committed. It lives
inside a directory that is otherwise entirely regenerable, so any advice of the
form "delete output/ and re-run" is wrong about exactly one thing.
"""

import pytest

from magi.core import durability


@pytest.mark.parametrize("path", [
    "raw/papers/2601.00001.md",
    "wiki/concepts/toric-code.md",
    "config.yaml",
    "config.md",
    "~/.config/magi/registry.json",
])
def test_things_a_person_made(path):
    assert durability.classify(path) == "original"
    assert durability.is_regenerable(path) is False


@pytest.mark.parametrize("path", [
    "output/graph.db",
    "output/index.db",
    "output/.lint_cache.json",
    "output/radar/seen.jsonl",
    "scratch/chunk_a_01.md",
])
def test_things_a_command_will_make_again(path):
    assert durability.classify(path) == "derived"
    assert durability.is_regenerable(path) is True


def test_the_ingest_ledger_is_neither():
    """It cannot be regenerated — it records decisions — but the documents it
    points at are already in raw/. Losing it loses the audit trail, not the
    library."""
    assert durability.classify("output/ingest/batch-abc.jsonl") == "transactional"
    assert durability.is_regenerable("output/ingest/batch-abc.jsonl") is False


def test_the_specific_answer_beats_the_containing_one():
    """`output/` is derived and `output/ingest/` is not, so the order the
    categories are consulted in is the whole point."""
    assert durability.classify("output/ingest/queue.jsonl") == "transactional"


def test_an_undecided_path_says_so_rather_than_guessing():
    """Guessing is how output/ingest/ would end up inside a "delete output/"
    instruction in the first place."""
    assert durability.classify("something/nobody/decided.txt") == "unknown"
    assert durability.is_regenerable("something/nobody/decided.txt") is False


def test_windows_separators_classify_the_same():
    assert durability.classify(r"output\graph.db") == "derived"
    assert durability.classify(r"output\ingest\queue.jsonl") == "transactional"
