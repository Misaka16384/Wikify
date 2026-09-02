"""Adopting a folder someone else arranged.

The defects these guard against were all found by running `magi adopt` against
two real research repositories rather than against a fixture: a work log called
`log.md` reported as MAGI's own furniture, a repo whose material all sits one
level down surveying as a single useless row, and — the one that would have
quietly damaged a person's files — repointing a single link rewriting every
line ending in the file on the way past.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from magi import adopt


def _repo(root: Path) -> Path:
    """A folder shaped like the real ones: subtrees that link to each other."""
    (root / "plans").mkdir(parents=True)
    (root / "results").mkdir()
    (root / "plans" / "INDEX.md").write_text(
        "# Plans\n\nSee [WMIN](../results/WMIN.md) and [one](01.md).\n"
        "Background in `../results/REPORT.md`.\n", encoding="utf-8")
    (root / "plans" / "01.md").write_text(
        "# One\n\n[back](INDEX.md), [out](../results/WMIN.md)\n", encoding="utf-8")
    (root / "results" / "WMIN.md").write_text("# WMIN\n", encoding="utf-8")
    (root / "results" / "REPORT.md").write_text("# Report\n", encoding="utf-8")
    return root


def _project(root: Path) -> Path:
    (root / "config.yaml").write_text("project: t\n", encoding="utf-8")
    (root / "log.md").write_text("# log\n", encoding="utf-8")
    for d in ("raw", "wiki", "drafts", "threads", "inbox", "output", "scratch"):
        (root / d).mkdir(exist_ok=True)
    return root


def _plan(root: Path, moves: list[tuple[str, str]]) -> Path:
    p = root / "plan.json"
    p.write_text(json.dumps({"moves": [{"from": a, "to": b} for a, b in moves]}),
                 encoding="utf-8")
    return p


def _apply(root: Path, plan: Path, *extra: str) -> int:
    return adopt.main(["apply", str(plan), "--project-dir", str(root), *extra])


# --------------------------------------------------------------------------
# survey
# --------------------------------------------------------------------------

def test_a_work_log_is_not_magis_furniture(tmp_path):
    """`log.md` is a name MAGI wants too. In a folder that is not a project
    yet, it is a person's work log, and treating it as scaffold is how the
    survey would propose leaving a person's file behind."""
    _repo(tmp_path)
    (tmp_path / "log.md").write_text("# my work log\n", encoding="utf-8")

    row = next(e for e in adopt.survey(tmp_path)["entries"] if e["name"] == "log.md")
    assert row["scaffold"] is False
    assert row["name_collision"] is True


def test_in_a_real_project_the_same_name_is_furniture(tmp_path):
    _project(tmp_path)
    row = next(e for e in adopt.survey(tmp_path)["entries"] if e["name"] == "log.md")
    assert row["scaffold"] is True
    assert row["name_collision"] is False


def test_a_repo_hidden_under_one_wrapper_is_still_surveyed(tmp_path):
    """Everything under `research/` surveys as one row saying "112 files",
    which tells nobody anything. A lone wrapper is descended through."""
    _repo(tmp_path / "research")

    data = adopt.survey(tmp_path)
    assert data["descended_into"] == ["research"]
    assert {e["name"] for e in data["entries"]} == {"plans", "results"}


def test_a_folder_with_real_choices_in_it_is_not_descended_through(tmp_path):
    _repo(tmp_path)
    assert adopt.survey(tmp_path)["descended_into"] == []


def test_the_references_written_in_the_prose_are_collected(tmp_path):
    """A references table is where most of a project's library already is."""
    (tmp_path / "refs.md").write_text(
        "| [1204.1063](https://arxiv.org/abs/1204.1063) | Haah |\n"
        "| 2509.10418 | Ruba |\n"
        "doi:10.1103/PhysRevB.99.155118\n", encoding="utf-8")
    got = adopt.identities_in(tmp_path)
    assert got["arxiv"] == ["1204.1063", "2509.10418"]
    assert got["doi"] == ["10.1103/PhysRevB.99.155118"]


# --------------------------------------------------------------------------
# the links
# --------------------------------------------------------------------------

def test_moving_whole_directories_needs_no_repair(tmp_path):
    """The relative geometry between two subtrees survives when both move
    under one new parent — nothing to rewrite."""
    _project(_repo(tmp_path))
    moves = [(tmp_path / "plans", tmp_path / "drafts" / "plans"),
             (tmp_path / "results", tmp_path / "drafts" / "results")]
    assert adopt.plan_rewrites(tmp_path, moves) == []


def _edits_for(rewrites: list[dict], name: str) -> dict[str, dict]:
    """The edits made to one file, by the text they replace."""
    for r in rewrites:
        if Path(r["file"]).name == name:
            return {e["old"]: e for e in r["edits"]}
    return {}


def _deep(tmp_path: Path) -> list[tuple[Path, Path]]:
    """Move INDEX.md somewhere a level deeper.

    Depth is what makes a repair necessary: `../results/WMIN.md` resolves the
    same from `plans/` and from `drafts/`, so a move between two directories at
    the same depth needs nothing done to it.
    """
    return [(tmp_path / "plans" / "INDEX.md",
             tmp_path / "drafts" / "deep" / "INDEX.md")]


def test_a_move_that_keeps_the_depth_keeps_the_links_that_reach_upward(tmp_path):
    """`../results/WMIN.md` resolves the same from `plans/` as from `drafts/`,
    so a move between two directories at the same depth leaves it alone. A link
    to a sibling left behind is a different matter and still needs repair —
    which is why moving whole directories is a convenience, not a rule."""
    _project(_repo(tmp_path))
    moves = [(tmp_path / "plans" / "INDEX.md", tmp_path / "drafts" / "INDEX.md")]

    edits = _edits_for(adopt.plan_rewrites(tmp_path, moves), "INDEX.md")
    assert "../results/WMIN.md" not in edits
    assert edits["01.md"]["new"] == "../plans/01.md"


def test_a_file_that_leaves_its_neighbours_gets_its_links_repointed(tmp_path):
    """The case a repo messy enough to be worth adopting always reaches."""
    _project(_repo(tmp_path))
    edits = _edits_for(adopt.plan_rewrites(tmp_path, _deep(tmp_path)), "INDEX.md")
    assert edits["../results/WMIN.md"]["new"] == "../../results/WMIN.md"
    assert edits["01.md"]["new"] == "../../plans/01.md"


def test_the_file_left_behind_is_repointed_at_the_one_that_moved(tmp_path):
    """`01.md` does not move, and its link to INDEX.md breaks all the same."""
    _project(_repo(tmp_path))
    edits = _edits_for(adopt.plan_rewrites(tmp_path, _deep(tmp_path)), "01.md")
    assert edits["INDEX.md"]["new"] == "../drafts/deep/INDEX.md"


def test_a_path_written_in_prose_is_repaired_too(tmp_path):
    """Nothing renders a path inside a code span, so nothing else would ever
    notice it stopped matching — and half a research folder refers to the
    other half that way."""
    _project(_repo(tmp_path))
    edits = _edits_for(adopt.plan_rewrites(tmp_path, _deep(tmp_path)), "INDEX.md")
    assert edits["../results/REPORT.md"]["kind"] == "prose"
    assert edits["../results/REPORT.md"]["new"] == "../../results/REPORT.md"


def test_a_command_in_a_code_span_is_not_a_path(tmp_path):
    """`python ../results/REPORT.md` is a code span that contains a path.
    Rewriting inside it would corrupt the command.

    There is no mutation case behind this one, deliberately: loosening the
    pattern to match commands does not change the outcome, because a span with
    a space in it resolves to a path whose first component is `python ..` and
    no such file exists. What protects a command is the `exists()` check in
    `_retarget`, not the shape of `_TEXT_PATH` — and that check has a case of
    its own. Keeping a case here would have read like a guard while testing
    nothing.
    """
    _project(_repo(tmp_path))
    (tmp_path / "plans" / "INDEX.md").write_text(
        "Run `python ../results/REPORT.md` to see.\n", encoding="utf-8")
    assert _edits_for(adopt.plan_rewrites(tmp_path, _deep(tmp_path)),
                      "INDEX.md") == {}


def test_a_link_that_already_dangles_is_left_alone(tmp_path):
    """Not this plan's fault, and repointing it would invent a target that was
    never there. The destination is one level deeper on purpose: at the same
    depth the link would come out unchanged anyway and the test would pass
    without the guard doing anything."""
    _project(_repo(tmp_path))
    (tmp_path / "plans" / "INDEX.md").write_text(
        "[gone](../results/NOPE.md)\n", encoding="utf-8")
    assert _edits_for(adopt.plan_rewrites(tmp_path, _deep(tmp_path)),
                      "INDEX.md") == {}


def test_an_anchor_survives_the_repair(tmp_path):
    _project(_repo(tmp_path))
    (tmp_path / "plans" / "INDEX.md").write_text(
        "[x](../results/WMIN.md#section-3)\n", encoding="utf-8")
    edits = _edits_for(adopt.plan_rewrites(tmp_path, _deep(tmp_path)), "INDEX.md")
    assert edits["../results/WMIN.md#section-3"]["new"] == \
        "../../results/WMIN.md#section-3"


# --------------------------------------------------------------------------
# applying, and taking it back
# --------------------------------------------------------------------------

def test_apply_leaves_every_link_resolving(tmp_path):
    _project(_repo(tmp_path))
    plan = _plan(tmp_path, [("plans/INDEX.md", "drafts/INDEX.md")])
    assert _apply(tmp_path, plan) == 0

    moved = tmp_path / "drafts" / "INDEX.md"
    for link in adopt._links_in(moved):
        target = (moved.parent / link.split("#")[0])
        assert target.exists(), f"{link} dangles"
    assert "../plans/01.md" in moved.read_text(encoding="utf-8")


def test_undo_puts_the_words_back_as_well_as_the_files(tmp_path):
    """A move is undoable by moving back. An edit is only undoable if the
    manifest wrote down what it changed."""
    _project(_repo(tmp_path))
    before = (tmp_path / "plans" / "INDEX.md").read_bytes()

    plan = _plan(tmp_path, [("plans/INDEX.md", "drafts/INDEX.md")])
    _apply(tmp_path, plan)
    assert (tmp_path / "plans" / "INDEX.md").exists() is False

    assert adopt.main(["undo", "--project-dir", str(tmp_path)]) == 0
    assert (tmp_path / "plans" / "INDEX.md").read_bytes() == before


def test_repointing_a_link_does_not_touch_the_line_endings(tmp_path):
    """Found against a real repo: the rewrite went through `write_text`, which
    translates on Windows, so one repaired link turned every line in the file
    into a modification. A person diffing their own repo afterwards would see
    the whole file changed and no way to tell what actually did."""
    _project(_repo(tmp_path))
    crlf = "# Plans\r\n\r\n[WMIN](../results/WMIN.md)\r\n[one](01.md)\r\n"
    (tmp_path / "plans" / "INDEX.md").write_bytes(crlf.encode("utf-8"))

    plan = _plan(tmp_path, [("plans/INDEX.md", "drafts/INDEX.md")])
    _apply(tmp_path, plan)

    # Byte equality, not a count of "\r\n": the defect writes "\r\r\n", which
    # still contains one "\r\n" per line and counts the same.
    want = crlf.replace("(01.md)", "(../plans/01.md)").encode("utf-8")
    assert (tmp_path / "drafts" / "INDEX.md").read_bytes() == want


def test_a_dry_run_changes_nothing(tmp_path):
    _project(_repo(tmp_path))
    before = (tmp_path / "plans" / "INDEX.md").read_bytes()
    plan = _plan(tmp_path, [("plans/INDEX.md", "drafts/INDEX.md")])

    assert _apply(tmp_path, plan, "--dry-run") == 0
    assert (tmp_path / "plans" / "INDEX.md").read_bytes() == before
    assert not (tmp_path / "drafts" / "INDEX.md").exists()


def test_no_rewrite_refuses_rather_than_dangling_a_link_quietly(tmp_path):
    _project(_repo(tmp_path))
    plan = _plan(tmp_path, [("plans/INDEX.md", "drafts/INDEX.md")])
    assert _apply(tmp_path, plan, "--no-rewrite") == 1
    assert (tmp_path / "plans" / "INDEX.md").exists()


def test_break_links_is_the_way_to_say_it_on_purpose(tmp_path):
    _project(_repo(tmp_path))
    plan = _plan(tmp_path, [("plans/INDEX.md", "drafts/INDEX.md")])
    assert _apply(tmp_path, plan, "--no-rewrite", "--break-links") == 0
    assert "../results/WMIN.md" in (tmp_path / "drafts" / "INDEX.md").read_text(
        encoding="utf-8"), "the text was edited despite --no-rewrite"


# --------------------------------------------------------------------------
# what apply refuses outright
# --------------------------------------------------------------------------

@pytest.mark.parametrize("moves,because", [
    ([("plans", "drafts/plans"), ("results", "drafts/plans")],
     "two moves want the same destination"),
    ([("nope", "drafts/nope")], "nothing there to move"),
    ([("plans", "../escape")], "must stay inside the project"),
    ([("plans", "plans/inner")], "cannot move a directory inside itself"),
    ([("raw", "drafts/raw")], "MAGI's own scaffold"),
])
def test_apply_refuses_a_plan_it_cannot_carry_out(tmp_path, moves, because):
    _project(_repo(tmp_path))
    assert _apply(tmp_path, _plan(tmp_path, moves)) == 1


def test_apply_never_overwrites(tmp_path):
    _project(_repo(tmp_path))
    (tmp_path / "drafts" / "plans").mkdir()
    assert _apply(tmp_path, _plan(tmp_path, [("plans", "drafts/plans")])) == 1
    assert (tmp_path / "plans" / "INDEX.md").exists()


def test_a_refused_plan_moves_nothing_at_all(tmp_path):
    """One bad entry means the whole plan is not carried out — half an adopted
    folder is worse than an unadopted one."""
    _project(_repo(tmp_path))
    plan = _plan(tmp_path, [("plans", "drafts/plans"), ("nope", "drafts/nope")])
    assert _apply(tmp_path, plan) == 1
    assert (tmp_path / "plans" / "INDEX.md").exists()
    assert not (tmp_path / "drafts" / "plans").exists()
