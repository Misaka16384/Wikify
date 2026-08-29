"""Three numbers v2 exists to bring down, written as tests so they can only go
one way.

v1's real defect was not any single feature — it was that the cost of picking
the system up kept rising and nothing pushed back. Seventy leaf commands, twenty
skills totalling 133KB, a seventy-line protocol block reloaded into every
session. Each addition was locally reasonable; the sum was a system a person
had to study before using and an agent had to pay for before starting.

So the budgets are tests. They are `xfail` until M3, when the command surface
collapses and the skills are rewritten — a failure here today is the milestone
not being done yet, not a regression. When M3 lands, delete the marks: after
that, exceeding a budget is a real failure and the fix is to take something out,
never to raise the number.

The budgets, and why each is that number:

* **`magi --help` ≤ 20 lines** — one screen. The porcelain a person is expected
  to remember is nine commands (design-v2 §7); everything else stays reachable
  behind `--help --all` and costs nothing to ignore.
* **each `SKILL.md` ≤ 40 lines** — a skill is loaded into a context window, so
  its length is a per-session tax. Forty lines fits frontmatter, when-to-use,
  ten steps and a few rules; boilerplate belongs in the managed block, once.
* **the managed block ≤ 40 lines** — it is read at the start of every session
  on every host. Reasons do not go in it. Pointers do.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SKILLS = sorted(Path(__file__).resolve().parents[1].joinpath("src/magi/skills").glob("*/SKILL.md"))

BEGIN = "<!-- magi:begin -->"
END = "<!-- magi:end -->"


def test_the_porcelain_fits_on_one_screen():
    result = subprocess.run([sys.executable, "-m", "magi", "--help"],
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    lines = result.stdout.strip().splitlines()
    assert len(lines) <= 20, f"`magi --help` is {len(lines)} lines:\n" + "\n".join(lines)


def test_hiding_a_command_is_presentation_not_removal():
    """The short help is a menu, not a smaller product. Everything v1 shipped
    still runs and still documents itself — `--help --all` is where a person
    who wants the reference manual finds it."""
    short = subprocess.run([sys.executable, "-m", "magi", "--help"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace").stdout
    every = subprocess.run([sys.executable, "-m", "magi", "--help", "--all"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace").stdout

    assert len(every.splitlines()) > 3 * len(short.splitlines())
    for command in ("ingest", "graph", "thread", "radar", "lint"):
        assert command in every, f"--help --all does not list {command}"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_a_skill_costs_at_most_forty_lines(skill):
    lines = skill.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 40, f"{skill.parent.name}/SKILL.md is {len(lines)} lines"


def test_the_managed_block_exists_and_stays_short(tmp_path):
    """The block a fresh workspace writes into AGENTS.md, measured end to end
    rather than from the template — the test should fail if the writer starts
    appending to what the template says."""
    subprocess.run([sys.executable, "-m", "magi", "init",
                    "--topic-dir", str(tmp_path), "--name", "T"],
                   capture_output=True, text=True, check=True)
    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

    assert BEGIN in text and END in text, "AGENTS.md has no managed block"
    block = text.split(BEGIN, 1)[1].split(END, 1)[0].strip().splitlines()
    assert len(block) <= 40, f"the managed block is {len(block)} lines"


def test_the_skill_count_is_going_down_not_up():
    """Not a budget — a fence. M3 lands on eight; until then nothing new gets
    added to the pile, because every skill added now is one more to rewrite."""
    assert SKILLS, 'no SKILL.md found — the glob moved and the budget above is vacuous'
    assert len(SKILLS) <= 20, f"{len(SKILLS)} skills; v1 had 20 and v2 targets 8"
