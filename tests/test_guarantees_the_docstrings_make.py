"""Five places where a docstring promised something the code did not do.

Every one of these was found by reading a module against its own opening
paragraph. That is worth naming, because it is a cheap check with a high yield
and none of the 2397 tests already here were doing it: a docstring that says
"a name already taken is kept rather than overwritten" is a specification, and
the file it sits on top of is the implementation, and nothing was comparing
them.

The five:

* `publish_cmd.file_paper` — "kept rather than overwritten", except for the
  second collision, which overwrote.
* `close_cmd.survey` / `publish_cmd.members` — a survey built so a person is
  shown what closing a line would silence, walking one directory level while
  the projection that counts those notes walks all of them.
* `patterns.mark` (was `read` + `save` in `propose`) — `observe`'s docstring
  says two sightings landing at once used to lose one, and describes the lock
  that fixed it; the proposal path did the same unlocked read-modify-write on
  the same file.
* `state._decisions_mention` — `_read_text` exists two hundred lines away and
  its docstring records that this exact decode error once took down
  `magi next`; the decisions reader decoded strictly anyway.
* `managed.write` — `state.block_drift` blocks the session with "run
  `magi install`", and `magi install` died on the file it was complaining
  about.

Each fix here is paired with a test that puts the bug back, because a test
written after a fix passes either way until you have watched it fail.
"""

import pytest

from magi import close_cmd, publish_cmd, state
from magi.core import managed, vocab
from magi.kb import thread_cmd, threads
from magi.reflect import patterns


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    (tmp_path / "raw" / "papers").mkdir(parents=True)
    (tmp_path / "config.md").write_text("# scope\n", encoding="utf-8")
    return tmp_path


def _new(ws, slug, kind, lines=()):
    argv = ["new", slug, "--topic-dir", str(ws), "--kind", kind,
            "--title", slug, "--purpose", "because"]
    for line in lines:
        argv += ["--line", line]
    assert thread_cmd.main(argv) == 0


# --------------------------------------------------------------------------
# the cold shelf
# --------------------------------------------------------------------------

def test_a_third_paper_of_the_same_name_does_not_overwrite_the_second(ws):
    """`raw/` is ORIGINAL: nothing regenerates what is in the library, so
    every candidate name is tested. Guarding only the first collision meant
    `paper--published.md` was computed once and then trusted forever."""
    made = []
    for n in range(3):
        source = ws / f"v{n}" / "paper.md"
        source.parent.mkdir()
        source.write_text(f"draft {n}\n", encoding="utf-8")
        made.append(publish_cmd.file_paper(ws, source))

    assert len(set(made)) == 3, f"three different papers landed on {made}"
    assert [p.read_text(encoding="utf-8") for p in made] == [
        "draft 0\n", "draft 1\n", "draft 2\n"], "an earlier paper was overwritten"


def test_publishing_the_same_file_twice_still_lands_on_itself(ws):
    """The other half of the promise. Idempotence is why the check is on
    content and not on existence."""
    source = ws / "paper.md"
    source.write_text("same bytes\n", encoding="utf-8")
    assert publish_cmd.file_paper(ws, source) == publish_cmd.file_paper(ws, source)
    assert len(list((ws / "raw" / "papers").glob("*.md"))) == 1


def test_the_shelf_keeps_going_past_the_second_collision(ws):
    """Six papers, six files. The generator is endless because the caller
    stops at the first free name, and a bounded list would have to decide what
    to do when it ran out — and overwriting is the one answer not available."""
    for n in range(6):
        source = ws / f"w{n}" / "paper.md"
        source.parent.mkdir()
        source.write_text(f"body {n}\n", encoding="utf-8")
        publish_cmd.file_paper(ws, source)
    assert len(list((ws / "raw" / "papers").glob("*.md"))) == 6


# --------------------------------------------------------------------------
# the survey that is the whole point of the command
# --------------------------------------------------------------------------

def _file_under(ws, subdir, slug, kind, line):
    """Move a note into `threads/<subdir>/`, the way a person organising a
    large workspace would. `state` counts it; the flat glob did not."""
    _new(ws, slug, kind, [line])
    nested = ws / "threads" / subdir
    nested.mkdir(exist_ok=True)
    moved = nested / f"{slug}.md"
    (ws / "threads" / f"{slug}.md").rename(moved)
    return moved


def test_the_close_survey_sees_a_note_in_a_subdirectory(ws):
    """The failure this prevents is silent and permanent: `magi next` counts
    the note (it walks with `rglob`), the survey did not, so closing the line
    reported "nothing open" and the proposition was never offered again."""
    _new(ws, "l-qec", "line")
    _file_under(ws, "qec", "p-nested", "proposition", "l-qec")

    found = close_cmd.survey(ws, "l-qec")
    assert [item["slug"] for item in found["open"]] == ["p-nested"]


def test_the_projection_and_the_survey_agree_on_what_is_open(ws):
    """Stated as the property rather than the mechanism: whatever the router
    counts as open on a line is what the survey has to show before closing it.
    Two readers of the same tree are two answers waiting to disagree."""
    _new(ws, "l-qec", "line")
    _file_under(ws, "qec", "p-nested", "proposition", "l-qec")
    _new(ws, "p-flat", "proposition", ["l-qec"])

    surveyed = {item["slug"] for item in close_cmd.survey(ws, "l-qec")["open"]}
    walked = {path.stem for path in threads.note_paths(ws)} - {"l-qec"}
    assert surveyed == walked


def test_publish_supersedes_a_note_in_a_subdirectory(ws):
    """Same walk, worse consequence: the note keeps its old status on a line
    that just closed, so nothing routes it and nothing records that the paper
    was supposed to be its answer."""
    _new(ws, "l-qec", "line")
    _file_under(ws, "qec", "p-nested", "proposition", "l-qec")

    assert [n.slug for n in publish_cmd.members(ws, ["l-qec"])] == ["p-nested"]


def test_the_survey_no_longer_reads_the_directory_index_as_a_note(ws):
    """`note_paths` skips `_index.md` and dotfiles. The flat glob handed both
    to `read_note` and relied on it raising."""
    _new(ws, "l-qec", "line")
    (ws / "threads" / "_index.md").write_text("# threads\n", encoding="utf-8")
    assert close_cmd.survey(ws, "l-qec")["open"] == []


# --------------------------------------------------------------------------
# the pattern library, which nothing regenerates
# --------------------------------------------------------------------------

def _sighting(root, session):
    patterns.observe(root, "sweeps-stall", title="sweeps stall",
                     body="the sweep stalls", session=session, host="claude")


def test_marking_a_pattern_proposed_keeps_a_sighting_that_landed_meanwhile(tmp_path):
    """`propose` read the page, and by the time it wrote, `observe` had added
    a third independent session under its own lock. The write put the
    two-session copy back — an attack on the >=2-sessions gate itself, on a
    directory `durability` classifies ORIGINAL."""
    _sighting(tmp_path, "s1")
    patterns.read(patterns.path_for(tmp_path, "sweeps-stall"))  # what propose held
    _sighting(tmp_path, "s2")

    patterns.mark(tmp_path, "sweeps-stall", patterns.PROPOSED)

    after = patterns.read(patterns.path_for(tmp_path, "sweeps-stall"))
    assert after.status == patterns.PROPOSED
    assert after.sessions == ["s1", "s2"], "the concurrent sighting was dropped"


def test_the_old_shape_really_would_have_dropped_it(tmp_path):
    """The bug, put back verbatim. Without this the test above passes against
    both implementations and proves nothing about which one is running."""
    _sighting(tmp_path, "s1")
    stale = patterns.read(patterns.path_for(tmp_path, "sweeps-stall"))
    _sighting(tmp_path, "s2")

    stale.status = patterns.PROPOSED
    patterns.save(tmp_path, stale)  # `read` outside the lock, `save` inside it

    after = patterns.read(patterns.path_for(tmp_path, "sweeps-stall"))
    assert after.sessions == ["s1"], (
        "the unlocked read-modify-write no longer loses the sighting, so the "
        "test above is not testing what it says it is")


def test_marking_a_pattern_that_is_gone_is_not_an_error(tmp_path):
    """The proposal is already in the ledger, and that is the part that has to
    survive. Raising here would fail a run whose durable half succeeded."""
    assert patterns.mark(tmp_path, "never-existed", patterns.PROPOSED) is None


# --------------------------------------------------------------------------
# files a person typed into
# --------------------------------------------------------------------------

#: A curly quote as Notepad writes it on a Windows machine set to cp1252.
CP1252 = "the reviewer’s objection".encode("cp1252")


def test_a_decisions_file_notepad_saved_does_not_take_down_the_router(ws):
    """The decode error escaped an `except OSError` and reached the caller, so
    `magi next`, `magi sync --close` and the session-start hook all died on
    one smart quote in the file the design tells a person to write in."""
    (ws / state.DECISIONS).write_bytes(b"- p-1: " + CP1252 + b"\n")
    assert state._decisions_mention(ws, "p-1") is True
    assert state._decisions_mention(ws, "p-2") is False


def test_the_whole_projection_survives_it_too(ws):
    """The unit above is where it crashed; this is what the crash cost."""
    _new(ws, "l-x", "line")
    (ws / state.DECISIONS).write_bytes(b"- l-x: " + CP1252 + b"\n")
    state.load(ws)  # raised UnicodeDecodeError


def test_install_rewrites_an_agents_file_that_is_not_utf8(ws):
    """`block_drift` blocks the session saying `magi install` fixes this, and
    `magi install` crashed on the same file. A gate whose remedy cannot run is
    a gate somebody turns off."""
    agents = ws / "AGENTS.md"
    agents.write_bytes(b"# House rules\n\nMind " + CP1252 + b".\n")

    assert managed.write(agents, "the block body") is True
    assert managed.read(managed.read_tolerantly(agents)) == "the block body"


def test_and_it_does_not_burn_the_bytes_it_came_to_keep(ws):
    """The distinction the fix turns on, and the reason `_read_text`'s answer
    was the wrong one to copy.

    `errors="replace"` would pass the test above — the file is rewritten and
    `magi install` completes — while writing U+FFFD over the person's quote
    permanently. That is not a fix, it is a second kind of data loss with a
    green test in front of it. So the check here is on bytes: the cp1252 byte
    goes back exactly as it came, and the UTF-8 encoding of the replacement
    character never appears.
    """
    agents = ws / "AGENTS.md"
    agents.write_bytes(b"# House rules\n\nMind " + CP1252 + b".\n")

    managed.write(agents, "the block body")

    after = agents.read_bytes()
    assert CP1252 in after, "the person's own prose was mangled"
    assert b"\xef\xbf\xbd" not in after, "written back with `replace`, not `surrogateescape`"
    assert "reviewer’s objection" in after.decode("cp1252")
