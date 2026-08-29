"""`magi publish` — the end of a line that ended well, and what it buries.

The paper goes on the cold shelf, every proposition it reports gets
`superseded_by:` pointing at it, and the line closes. After that the paper is
the answer and the propositions are the working-out.

`superseded` is **terminal** — `vocab` gives it no way out — which is why this
command surveys before it writes. Two things it will not bury quietly:

* a `disputed` proposition, where a reviewer objected and nobody ruled;
* work still open, where the paper claims to end a line that has not finished.

Neither is forbidden. Papers ship with loose ends. What the tests here hold is
that shipping one is a thing somebody said yes to, and that the record says
which ones they were.
"""

import json
import subprocess
import sys

import pytest

from magi import publish_cmd
from magi.core import vocab
from magi.kb import thread_cmd, threads


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    (tmp_path / "raw" / "papers").mkdir(parents=True)
    (tmp_path / "config.md").write_text("# scope\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def paper(tmp_path):
    path = tmp_path / "our-paper.md"
    path.write_text("# What we found\n\nAll of it.\n", encoding="utf-8")
    return path


def _new(ws, slug, kind, lines=()):
    argv = ["new", slug, "--topic-dir", str(ws), "--kind", kind,
            "--title", slug, "--purpose", "because"]
    for line in lines:
        argv += ["--line", line]
    assert thread_cmd.main(argv) == 0


def _walk(ws, slug, *statuses):
    for dst in statuses:
        assert thread_cmd.main(["status", slug, dst, "--topic-dir", str(ws),
                                "--text", "step", "--host", "claude"]) == 0


def _note(ws, slug):
    return threads.read_note(ws / "threads" / f"{slug}.md")


# --------------------------------------------------------------------------
# the survey
# --------------------------------------------------------------------------

def test_the_survey_separates_unfinished_from_disputed(ws, paper):
    """Two different objections with two different answers, so they are two
    different lists rather than one count of "not ready"."""
    _new(ws, "l-x", "line")
    _new(ws, "p-open", "proposition", ["l-x"])
    _new(ws, "p-done", "proposition", ["l-x"])
    _new(ws, "p-fight", "proposition", ["l-x"])
    _walk(ws, "p-done", "conjectured", "testing", "supported")
    _walk(ws, "p-fight", "conjectured", "testing", "supported", "disputed")

    found = publish_cmd.survey(ws, paper, ["l-x"])

    assert found["unfinished"] == ["p-open"]
    assert found["disputed"] == ["p-fight"]
    assert {item["slug"] for item in found["supersede"]} == {
        "p-open", "p-done", "p-fight"}


def test_a_line_that_is_not_there_is_named_before_anything_is_written(ws, paper):
    result = publish_cmd.publish(ws, paper, ["l-nope"], "why")

    assert result["ok"] is False
    assert "l-nope" in result["error"]
    assert not (ws / "raw" / "papers" / paper.name).exists(), \
        "nothing should land before the lines are known to exist"


def test_a_paper_that_is_not_a_file_is_refused(ws, tmp_path):
    result = publish_cmd.publish(ws, tmp_path / "ghost.md", ["l-x"], "why")
    assert result["ok"] is False and "no such file" in result["error"]


# --------------------------------------------------------------------------
# what it refuses
# --------------------------------------------------------------------------

def test_unfinished_work_stops_the_publish(ws, paper):
    _new(ws, "l-x", "line")
    _new(ws, "p-open", "proposition", ["l-x"])

    result = publish_cmd.publish(ws, paper, ["l-x"], "the writeup")

    assert result["ok"] is False
    assert not (ws / "raw" / "papers" / paper.name).exists()
    said = publish_cmd.render(result)
    assert "p-open" in said and "--anyway" in said


def test_an_unresolved_objection_stops_the_publish_and_says_what_it_is(ws, paper):
    """`disputed` means a reviewer rejected a claimed result and nobody ruled.
    Publishing over it does not answer the objection, it deletes it."""
    _new(ws, "l-x", "line")
    _new(ws, "p-fight", "proposition", ["l-x"])
    _walk(ws, "p-fight", "conjectured", "testing", "supported", "disputed")

    result = publish_cmd.publish(ws, paper, ["l-x"], "the writeup")

    assert result["ok"] is False
    assert "makes the objection vanish" in publish_cmd.render(result)


def test_a_finished_line_publishes_with_no_ceremony(ws, paper):
    _new(ws, "l-x", "line")
    _new(ws, "p-done", "proposition", ["l-x"])
    _walk(ws, "p-done", "conjectured", "testing", "supported")

    result = publish_cmd.publish(ws, paper, ["l-x"], "the writeup")

    assert result["ok"], result
    assert result["superseded"] == ["p-done"] and result["closed"] == ["l-x"]


# --------------------------------------------------------------------------
# what it writes
# --------------------------------------------------------------------------

def test_every_superseded_proposition_points_at_the_paper(ws, paper):
    _new(ws, "l-x", "line")
    _new(ws, "p-done", "proposition", ["l-x"])
    _walk(ws, "p-done", "conjectured", "testing", "supported")

    publish_cmd.publish(ws, paper, ["l-x"], "the writeup")

    note = _note(ws, "p-done")
    assert note.status == "superseded"
    assert note.frontmatter["superseded_by"] == "[[raw/papers/our-paper.md]]"


def test_the_paper_lands_on_the_cold_shelf(ws, paper):
    _new(ws, "l-x", "line")

    result = publish_cmd.publish(ws, paper, ["l-x"], "the writeup")

    landed = ws / "raw" / "papers" / "our-paper.md"
    assert landed.is_file() and landed.read_text(encoding="utf-8") == \
        paper.read_text(encoding="utf-8")
    assert result["link"] == "[[raw/papers/our-paper.md]]"


def test_a_name_already_taken_by_different_content_is_kept(ws, paper):
    """`raw/` is ORIGINAL. Two papers sharing a filename is somebody's problem
    to look at, not a reason to destroy the earlier one."""
    (ws / "raw" / "papers" / "our-paper.md").write_text("someone else's\n",
                                                        encoding="utf-8")
    _new(ws, "l-x", "line")

    result = publish_cmd.publish(ws, paper, ["l-x"], "the writeup")

    assert "our-paper--published.md" in result["paper_at"]
    assert (ws / "raw" / "papers" / "our-paper.md").read_text(encoding="utf-8") \
        == "someone else's\n"


def test_publishing_the_same_paper_twice_lands_on_itself(ws, paper):
    _new(ws, "l-x", "line")
    _new(ws, "l-y", "line")
    publish_cmd.publish(ws, paper, ["l-x"], "the writeup")

    again = publish_cmd.publish(ws, paper, ["l-y"], "the writeup")

    assert again["paper_at"].endswith("our-paper.md")
    assert len(list((ws / "raw" / "papers").glob("our-paper*.md"))) == 1


def test_publishing_anyway_records_what_was_buried(ws, paper):
    """After this, `superseded` is terminal and the line is closed. The post is
    the only place left that can say a loose end was a loose end."""
    _new(ws, "l-x", "line")
    _new(ws, "p-open", "proposition", ["l-x"])
    _new(ws, "p-fight", "proposition", ["l-x"])
    _walk(ws, "p-fight", "conjectured", "testing", "supported", "disputed")

    result = publish_cmd.publish(ws, paper, ["l-x"], "shipping it", anyway=True)

    assert result["ok"], result
    closing = _note(ws, "l-x").posts[-1].text
    assert "unresolved objection" in closing and "p-fight" in closing
    assert "unfinished" in closing and "p-open" in closing


def test_a_question_on_the_line_is_answered_not_superseded(ws, paper):
    """`superseded` is not in a question's vocabulary — its terminal states are
    `answered` and `abandoned`. Publishing answers it."""
    _new(ws, "l-x", "line")
    _new(ws, "q-why", "question", ["l-x"])

    publish_cmd.publish(ws, paper, ["l-x"], "the writeup", anyway=True)

    assert _note(ws, "q-why").status == "answered"


def test_the_line_ends_closed_and_signed_as_a_person_s_decision(ws, paper):
    _new(ws, "l-x", "line")

    publish_cmd.publish(ws, paper, ["l-x"], "the writeup")

    note = _note(ws, "l-x")
    assert note.status == "closed"
    assert note.posts[-1].host == vocab.HUMAN


def test_a_note_on_another_line_is_left_alone(ws, paper):
    _new(ws, "l-x", "line")
    _new(ws, "l-y", "line")
    _new(ws, "p-theirs", "proposition", ["l-y"])

    publish_cmd.publish(ws, paper, ["l-x"], "the writeup")

    assert _note(ws, "p-theirs").status == "open"
    assert _note(ws, "l-y").status == "exploring"


# --------------------------------------------------------------------------
# the command line
# --------------------------------------------------------------------------

def _run(ws, *args):
    return subprocess.run([sys.executable, "-m", "magi", "publish", *args,
                           "--topic-dir", str(ws)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def test_a_dry_run_writes_nothing(ws, paper):
    _new(ws, "l-x", "line")
    _new(ws, "p-done", "proposition", ["l-x"])

    done = _run(ws, str(paper), "--line", "l-x", "--dry-run", "--json")

    assert done.returncode == 0
    assert json.loads(done.stdout)["supersede"][0]["slug"] == "p-done"
    assert not (ws / "raw" / "papers" / paper.name).exists()
    assert _note(ws, "l-x").status == "exploring"


def test_publishing_without_a_line_is_refused(ws, paper):
    done = _run(ws, str(paper))
    assert done.returncode == 1
    assert "which line" in done.stderr


def test_publishing_without_saying_what_it_is_is_refused(ws, paper):
    _new(ws, "l-x", "line")
    done = _run(ws, str(paper), "--line", "l-x")
    assert done.returncode == 1
    assert "say what this paper is" in done.stderr


def test_a_paper_the_library_cannot_read_is_filed_and_flagged(ws, tmp_path):
    """A PDF on the cold shelf is a file the graph and search cannot see. It is
    still the paper of record, so it is filed — and said out loud, because a
    silent one looks indexed."""
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 not really\n")
    _new(ws, "l-x", "line")

    result = publish_cmd.publish(ws, pdf, ["l-x"], "the writeup")

    assert result["ok"] and result["readable"] is False
    assert "magi ingest add" in publish_cmd.render(result)
