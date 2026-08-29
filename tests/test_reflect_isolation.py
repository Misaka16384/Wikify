"""The pattern library is not for the working agent.

WikiSkill's ablation is the whole reason this file exists: give the agent doing
the work access to the pattern library and the score goes *down*. It starts
defending against the patterns instead of following the rules, and once it
does, the slow loop can no longer tell whether the rules it hardened are doing
anything — the signal it learns from has been contaminated by its own output.

So `output/reflect/` must not appear anywhere an agent reads at the start of a
session or is told to look during one: not the managed block, not a skill, not
a suggestion `magi next` prints. Those are the three surfaces; everything else
in the workspace is already blind to `output/` (design-v2 §12).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from magi import state
from magi.core import managed, vocab
from magi.kb import threads

FORBIDDEN = "output/reflect"
ROOT = Path(__file__).resolve().parents[1]


def test_the_managed_block_never_mentions_it():
    """It is read at the start of every session on every host."""
    body = managed.body("A topic", "A scope.", "light")
    assert FORBIDDEN not in body


@pytest.mark.parametrize("skill", sorted(
    p.name for p in (ROOT / "src" / "magi" / "skills").iterdir() if p.is_dir()))
def test_no_skill_mentions_it(skill):
    text = (ROOT / "src" / "magi" / "skills" / skill / "SKILL.md").read_text(
        encoding="utf-8")
    assert FORBIDDEN not in text


def test_nothing_next_suggests_mentions_it(tmp_path):
    """The one place a path could be put in front of a working agent.

    `magi next` proposes commands to run. A suggestion naming the pattern
    library would be an invitation to read it, which is the thing the ablation
    says not to do.
    """
    (tmp_path / "threads").mkdir()
    (tmp_path / "inbox").mkdir()
    (tmp_path / "inbox" / "notes.md").write_text("- an unfiled thought\n",
                                                 encoding="utf-8")
    line = threads.create(tmp_path / "threads" / "qec.md", vocab.LINE, "QEC", "Whether.")
    threads.set_status(line, "active", "moving", host="claude")
    gap = threads.create(tmp_path / "threads" / "p-gap.md", vocab.PROPOSITION,
                         "The gap survives", "Decide.", lines=["qec"])
    threads.set_status(gap, "testing", "started", host="claude")
    threads.set_status(gap, "supported", "converged", host="claude")

    loaded = state.load(tmp_path)
    actions = state.candidates(loaded)

    assert actions, "the fixture is meant to produce suggestions"
    for action in actions:
        assert FORBIDDEN not in action.run
        assert FORBIDDEN not in action.why


def test_the_map_a_person_reads_does_not_send_them_there_either(tmp_path):
    """A person may read it; they are not the agent the ablation is about. But
    the map is the one file a session is told to look at, so a path printed
    there reaches the agent anyway."""
    (tmp_path / "threads").mkdir()
    threads.create(tmp_path / "threads" / "qec.md", vocab.LINE, "QEC", "Whether.")

    assert FORBIDDEN not in state.render_map(state.load(tmp_path))


def test_the_directory_alone_is_not_a_workspace(tmp_path):
    """A fixture that only has `output/reflect/` must not be mistaken for a
    library — `is_topic_root` looks for wiki/, raw/ or threads/."""
    from magi.core.workspace import is_topic_root

    (tmp_path / "output" / "reflect" / "patterns").mkdir(parents=True)
    (tmp_path / "config.yaml").write_text("research: {}\n", encoding="utf-8")

    assert not is_topic_root(tmp_path)
