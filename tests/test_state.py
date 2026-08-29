"""The derived view of research state: `magi next`, `feed`, MAP, `--close`.

Everything here is computed from `threads/` on every call and stored nowhere.
That is the property the tests are really defending: the moment a projection
gets written down it becomes a second answer that can disagree with the first,
and then somebody has to decide which is true. So MAP.md is a rendering, the
feed is a view, and `next` recomputes.

The ordering in `next` is the other load-bearing decision. Debt comes first
because every line below it is computed from notes that are currently wrong.
Then the human queue, because those are the only three events allowed to
interrupt somebody and they must not sit behind machine work. Then the work.

`--close` is the gate. It blocks on debt from the last few hours and merely
lists anything older: a hook that refuses to let anyone stop until a library's
whole history is tidy is a hook people switch off, and a disabled gate enforces
nothing at all.
"""

import datetime as dt
import json
from pathlib import Path

import pytest

from magi import state
from magi.core import vocab
from magi.kb import threads


NOW = dt.datetime(2026, 8, 29, 12, 0, tzinfo=dt.timezone.utc)


def at(minutes_ago=0, days_ago=0):
    stamp = NOW - dt.timedelta(minutes=minutes_ago, days=days_ago)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    return tmp_path


def line(ws, slug="qec", status=None):
    path = threads.create(ws / "threads" / f"{slug}.md", vocab.LINE, slug.upper(),
                          f"Whether {slug} works.")
    if status:
        threads.set_status(path, status, "moving", host="claude", at=at())
    return path


def proposition(ws, slug, lines=("qec",), bet=None, status=None, when=None, **extra):
    path = threads.create(ws / "threads" / f"{slug}.md", vocab.PROPOSITION,
                          slug.upper(), f"Why {slug}.", lines=list(lines),
                          extra=({"bet": bet} if bet else None) or extra or None)
    if status:
        threads.set_status(path, status, "moving", host="claude", at=when or at())
    return path


def load(ws, **kwargs):
    kwargs.setdefault("now", NOW)
    return state.load(ws, **kwargs)


# --------------------------------------------------------------------------
# lines
# --------------------------------------------------------------------------

def test_a_line_carries_the_propositions_that_name_it(ws):
    line(ws)
    proposition(ws, "p-a")
    proposition(ws, "p-b", status="testing")

    view = load(ws).lines[0]
    assert view.slug == "qec"
    assert view.open_count == 2
    assert view.total == 2


def test_notes_that_name_no_line_still_get_a_row(ws):
    """A project may run with no explicit lines at all and should still have a
    map. Dropping those notes would make the map lie by omission."""
    proposition(ws, "p-loose", lines=())
    assert [view.slug for view in load(ws).lines] == [state.UNLINED]


def test_a_settled_proposition_stops_counting_as_open(ws):
    line(ws)
    proposition(ws, "p-a", status="testing")
    threads.set_status(ws / "threads" / "p-a.md", "supported", "done",
                       host="claude", at=at())

    assert load(ws).lines[0].open_count == 0


def test_a_line_nobody_has_posted_to_goes_quiet(ws):
    line(ws)
    proposition(ws, "p-a", status="testing", when=at(days_ago=40))

    views = {view.slug: view for view in load(ws, stall_days=21).lines}
    assert views["qec"].stalled is True


def test_a_line_posted_to_last_week_is_not_quiet(ws):
    line(ws)
    proposition(ws, "p-a", status="testing", when=at(days_ago=5))
    assert load(ws, stall_days=21).lines[0].stalled is False


# --------------------------------------------------------------------------
# the decision queue — the only three things allowed to interrupt somebody
# --------------------------------------------------------------------------

def test_a_disputed_proposition_waits_on_a_person(ws):
    line(ws)
    path = proposition(ws, "p-a", status="testing")
    threads.set_status(path, "supported", "done", host="claude", at=at())
    threads.set_status(path, "disputed", "the reviewer disagrees",
                       host="reviewer", at=at())

    item = [q for q in load(ws).queue if q.slug == "p-a"][0]
    assert item.kind == "disputed"


def test_work_started_with_no_prediction_asks_for_one(ws):
    """The prediction is only worth anything before the answer. Asking once, at
    the moment work starts, is the whole of the forced-output protocol here."""
    line(ws)
    proposition(ws, "p-a", status="testing")

    assert [q.kind for q in load(ws).queue if q.slug == "p-a"] == ["bet"]


def test_a_recorded_prediction_is_not_asked_for_again(ws):
    line(ws)
    proposition(ws, "p-a", bet="supported", status="testing")

    assert [q for q in load(ws).queue if q.slug == "p-a"] == []


def test_too_much_open_at_once_asks_for_a_close_not_a_ranking(ws):
    line(ws)
    for n in range(9):
        proposition(ws, f"p-{n}")

    item = [q for q in load(ws, wip_limit=7).queue if q.kind == "wip"][0]
    assert item.line == "qec"
    assert "more than one" in item.why


def test_a_quiet_line_is_asked_about_its_phase(ws):
    line(ws)
    proposition(ws, "p-a", status="testing", when=at(days_ago=40))

    assert any(q.kind == "phase" for q in load(ws, stall_days=21).queue)


# --------------------------------------------------------------------------
# debt — work that happened and was not written down
# --------------------------------------------------------------------------

def test_a_status_nobody_explained_is_debt(ws):
    path = proposition(ws, "p-a")
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("status: open", "status: supported", 1), encoding="utf-8")

    debt = load(ws).debt
    assert [item.slug for item in debt] == ["p-a"]
    assert "no post records" in debt[0].why


def test_a_derivation_that_moved_after_the_proposition_is_debt(ws):
    """The argument changed and the claim did not. Nothing is wrong with the
    file; what is wrong is that the note still says what it said before."""
    (ws / "drafts").mkdir()
    draft = ws / "drafts" / "gap-argument.md"
    draft.write_text("# Argument\n", encoding="utf-8")

    path = proposition(ws, "p-a", derivation=["[[gap-argument]]"])
    threads.set_status(path, "testing", "started", host="claude", at=at(minutes_ago=60))
    draft.write_text("# Argument\n\nRewritten.\n", encoding="utf-8")
    # Both files are pinned, because the code compares three things and the
    # fixture used to supply two. A post an hour old on a note file written
    # this second is not a state a workspace can be in: the note was last
    # written when that post was appended. Leaving it inconsistent is what
    # made the checkout guard read this as a checkout.
    import os
    an_hour_ago = NOW.timestamp() - 3600
    os.utime(path, (an_hour_ago, an_hour_ago))
    os.utime(draft, (NOW.timestamp(), NOW.timestamp()))

    debt = load(ws).debt
    assert any("gap-argument" in item.why for item in debt)


def test_a_tidy_workspace_owes_nothing(ws):
    line(ws)
    proposition(ws, "p-a", bet="supported", status="testing")
    assert load(ws).debt == []


# --------------------------------------------------------------------------
# what to do next
# --------------------------------------------------------------------------

def test_debt_outranks_everything_else(ws):
    """Every other line of the list is computed from notes that are currently
    wrong, so fixing the notes is always the first move."""
    line(ws)
    path = proposition(ws, "p-a", status="testing")
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("status: testing", "status: supported", 1), encoding="utf-8")
    disputed = proposition(ws, "p-b", status="testing")
    threads.set_status(disputed, "supported", "done", host="claude", at=at())
    threads.set_status(disputed, "disputed", "no", host="reviewer", at=at())

    keys = [action.key for action in state.candidates(load(ws))]
    assert keys[0] == "debt"
    assert "disputed" in keys


def test_a_line_with_nothing_open_is_asked_for_a_question(ws):
    line(ws)
    assert any(action.key == "empty-line" for action in state.candidates(load(ws)))


def test_a_line_already_waiting_on_a_person_is_not_also_nagged(ws):
    """Two prompts about one line is how a router teaches people to skim it."""
    line(ws)
    path = proposition(ws, "p-a", status="testing")
    threads.set_status(path, "supported", "done", host="claude", at=at())
    threads.set_status(path, "disputed", "no", host="reviewer", at=at())

    keys = [action.key for action in state.candidates(load(ws))]
    assert "empty-line" not in keys


def test_only_one_open_proposition_per_line_is_proposed(ws):
    """Listing every open proposition is listing the project, and then the
    ranking it was for stops meaning anything."""
    line(ws)
    for n in range(4):
        proposition(ws, f"p-{n}", bet="supported", status="testing",
                    when=at(days_ago=n))

    work = [action for action in state.candidates(load(ws)) if action.key == "work"]
    assert len(work) == 1
    assert work[0].slug == "p-3", "the one that has waited longest"


def test_nothing_owed_prints_the_open_questions_and_stops(ws):
    """A router that always finds something to say trains people to stop
    reading it."""
    threads.create(ws / "threads" / "q-order.md", vocab.QUESTION,
                   "What is the order parameter?", "Pin down the phase.")
    projection = load(ws)
    projection.lines = []

    text = state.render(projection, [])
    assert "Nothing owed" in text
    assert "q-order" in text


# --------------------------------------------------------------------------
# feed
# --------------------------------------------------------------------------

def test_the_feed_is_every_post_newest_first(ws):
    path = proposition(ws, "p-a")
    threads.set_status(path, "testing", "one", host="claude", at=at(minutes_ago=30))
    threads.append_post(path, "two", host="codex", at=at(minutes_ago=10))

    entries = state.feed(load(ws))
    assert [entry.text for entry in entries] == ["two", "one"]


def test_the_feed_can_be_narrowed_to_one_host(ws):
    path = proposition(ws, "p-a")
    threads.append_post(path, "mine", host="codex", at=at(minutes_ago=5))
    threads.append_post(path, "theirs", host="claude", at=at(minutes_ago=4))

    assert [e.text for e in state.feed(load(ws), author="codex")] == ["mine"]


def test_the_feed_can_start_from_a_date(ws):
    path = proposition(ws, "p-a")
    threads.append_post(path, "old", host="claude", at=at(days_ago=10))
    threads.append_post(path, "new", host="claude", at=at(minutes_ago=1))

    since = NOW - dt.timedelta(days=1)
    assert [e.text for e in state.feed(load(ws), since=since)] == ["new"]


# --------------------------------------------------------------------------
# MAP
# --------------------------------------------------------------------------

def test_the_map_says_that_editing_it_does_nothing(ws):
    """It reads as a status page somebody maintains, and the temptation is to
    correct it. Correcting it changes nothing; the next render overwrites."""
    line(ws)
    assert "Editing this file changes nothing" in state.render_map(load(ws), now=NOW)


def test_the_map_holds_lines_and_decisions_and_no_chores(ws):
    line(ws)
    proposition(ws, "p-a", status="testing")

    text = state.render_map(load(ws), now=NOW)
    assert "## Lines" in text and "## Decisions waiting on you" in text
    assert "[[qec]]" in text
    assert "backlog" not in text.lower()


def test_writing_the_map_puts_it_in_output(ws):
    line(ws)
    path = state.write_map(load(ws))
    assert path == ws / "output" / "MAP.md"
    assert path.read_text(encoding="utf-8").startswith("# MAP")


# --------------------------------------------------------------------------
# closing a session
# --------------------------------------------------------------------------

def test_two_writers_inside_the_window_is_a_conflict(ws):
    """Last-writer-wins settles an ordinary flip: the second writer had read
    the first one's post. It cannot settle two writers moving at once."""
    path = proposition(ws, "p-a")
    threads.set_status(path, "testing", "mine", host="claude", at=at(minutes_ago=32))
    threads.set_status(path, "supported", "theirs", host="codex", at=at(minutes_ago=30))

    report = state.close(ws, now=NOW)

    assert report.conflicts == ["p-a"]
    assert threads.read_note(path).status == vocab.CONFLICT


def test_the_same_writer_moving_twice_is_not_a_conflict(ws):
    path = proposition(ws, "p-a")
    threads.set_status(path, "testing", "one", host="claude", at=at(minutes_ago=32))
    threads.set_status(path, "supported", "two", host="claude", at=at(minutes_ago=31))

    assert state.close(ws, now=NOW).conflicts == []


def test_two_writers_days_apart_is_just_revision(ws):
    path = proposition(ws, "p-a")
    threads.set_status(path, "testing", "one", host="claude", at=at(days_ago=3))
    threads.set_status(path, "supported", "two", host="codex", at=at(minutes_ago=5))

    assert state.close(ws, now=NOW).conflicts == []


def test_close_blocks_on_debt_from_this_session(ws):
    path = proposition(ws, "p-a")
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("status: open", "status: supported", 1), encoding="utf-8")

    report = state.close(ws, now=NOW)

    assert report.ok is False
    assert [item.slug for item in report.blocking] == ["p-a"]


def test_close_only_lists_debt_older_than_the_window(ws):
    """A gate that refuses until a library's whole history is tidy is a gate
    people switch off, and a disabled gate enforces nothing."""
    import os

    path = proposition(ws, "p-a")
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("status: open", "status: supported", 1), encoding="utf-8")
    old = (NOW - dt.timedelta(days=5)).timestamp()
    os.utime(path, (old, old))

    report = state.close(ws, now=NOW)

    assert report.ok is True
    assert [item.slug for item in report.older] == ["p-a"]


def test_close_writes_the_map(ws):
    line(ws)
    report = state.close(ws, now=NOW)
    assert report.map_path and (ws / "output" / "MAP.md").is_file()


def test_the_hook_payload_tells_the_agent_what_to_do(ws):
    path = proposition(ws, "p-a")
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("status: open", "status: supported", 1), encoding="utf-8")

    payload = state.hook_payload(state.close(ws, now=NOW, write=False))

    assert payload["decision"] == "block"
    assert "magi thread status" in payload["reason"]
    assert "p-a" in payload["reason"]


def test_a_clean_close_says_nothing_to_the_hook(ws):
    line(ws)
    assert state.hook_payload(state.close(ws, now=NOW, write=False)) == {}


# --------------------------------------------------------------------------
# the commands
# --------------------------------------------------------------------------

def test_next_json_carries_the_whole_projection(ws, capsys):
    line(ws)
    proposition(ws, "p-a", status="testing")

    assert state.main(["next", "--topic-dir", str(ws), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert {"lines", "queue", "debt", "actions", "open_questions"} <= set(payload)
    assert payload["lines"][0]["slug"] == "qec"


def test_next_can_be_narrowed_to_one_line(ws, capsys):
    line(ws, "qec")
    line(ws, "transport")
    proposition(ws, "p-a", lines=("transport",), status="testing")

    state.main(["next", "--topic-dir", str(ws), "--line", "transport", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert [view["slug"] for view in payload["lines"]] == ["transport"]


def test_feed_json_is_a_list_of_posts(ws, capsys):
    path = proposition(ws, "p-a")
    threads.append_post(path, "hello", host="claude", at=at(minutes_ago=1))

    assert state.main(["feed", "--topic-dir", str(ws), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload[0]["slug"] == "p-a"
    assert payload[0]["host"] == "claude"


def test_a_since_nobody_can_parse_is_refused(ws):
    with pytest.raises(SystemExit) as caught:
        state.main(["feed", "--topic-dir", str(ws), "--since", "last tuesday"])
    assert "not a date" in str(caught.value)


# --------------------------------------------------------------------------
# flips that are a person's call
# --------------------------------------------------------------------------

def disputed(ws, slug="p-a"):
    path = proposition(ws, slug, status="testing")
    threads.set_status(path, "supported", "done", host="claude", at=at(minutes_ago=20))
    threads.set_status(path, "disputed", "no", host="reviewer", at=at(minutes_ago=10))
    return path


def test_an_agent_walking_a_proposition_out_of_disputed_is_debt(ws):
    """`disputed` exists to stop the machine settling the question itself. If
    the next run can flip it back, the reviewer's objection evaporates between
    two sessions and nobody is ever asked."""
    path = disputed(ws)
    threads.set_status(path, "supported", "it holds", host="claude", at=at())

    why = [item.why for item in load(ws).debt]
    assert any("person's call" in message for message in why)


def test_a_post_signed_by_the_person_settles_it(ws):
    path = disputed(ws)
    threads.set_status(path, "supported", "I read it; the objection is about the "
                       "boundary case", host=vocab.HUMAN, at=at())

    assert [item for item in load(ws).debt if "person's call" in item.why] == []


def test_writing_the_decision_down_settles_it_too(ws):
    """The agent transcribing what a person decided is the normal case, so the
    other way to satisfy this is the file that record lives in."""
    path = disputed(ws)
    threads.set_status(path, "supported", "per the call", host="claude", at=at())
    (ws / "decisions.md").write_text(
        "2026-08-29 p-a: the objection is about the boundary case; it stands "
        "for the bulk.\n", encoding="utf-8")

    assert [item for item in load(ws).debt if "person's call" in item.why] == []


def test_entering_disputed_is_nobody_special(ws):
    """The reviewer has to be able to raise the objection on its own; only
    dismissing it is the person's call."""
    disputed(ws)
    assert [item for item in load(ws).debt if "person's call" in item.why] == []


def test_the_policy_and_the_check_read_the_same_table(ws):
    assert vocab.is_human_only(vocab.PROPOSITION, "disputed", "supported")
    assert vocab.is_human_only(vocab.LINE, "closed", "active")
    assert not vocab.is_human_only(vocab.PROPOSITION, "testing", "supported")


# --------------------------------------------------------------------------
# what a line is looking at
# --------------------------------------------------------------------------

def test_a_lines_focus_is_what_its_notes_point_at(ws):
    """A line is a view over a shared library, not a library of its own, so
    "what belongs to this line" cannot be a directory — it has to be derived
    from what the line's own notes reference."""
    (ws / "drafts").mkdir()
    (ws / "drafts" / "gap-argument.md").write_text("# Argument\n", encoding="utf-8")
    (ws / "wiki" / "concepts").mkdir(parents=True)
    (ws / "wiki" / "concepts" / "toric-code.md").write_text("# Toric\n", encoding="utf-8")

    line(ws)
    proposition(ws, "p-a", derivation=["[[gap-argument]]"],
                depends_on=["[[toric-code]]"])

    assert state.focus(ws, "qec") == {
        "threads/qec.md", "threads/p-a.md",
        "drafts/gap-argument.md", "wiki/concepts/toric-code.md"}


def test_another_lines_work_is_not_in_this_lines_focus(ws):
    line(ws, "qec")
    line(ws, "transport")
    proposition(ws, "p-a", lines=("transport",))

    assert "threads/p-a.md" not in state.focus(ws, "qec")


def test_a_link_to_nothing_is_dropped_rather_than_guessed_at(ws):
    line(ws)
    proposition(ws, "p-a", derivation=["[[never-written]]"])

    assert state.focus(ws, "qec") == {"threads/qec.md", "threads/p-a.md"}


# --------------------------------------------------------------------------
# mechanisms, not seconds
# --------------------------------------------------------------------------

def test_one_walk_answers_every_link(ws, monkeypatch):
    """The obvious implementation resolves each `derivation:` with its own
    `rglob`, which is one directory walk per link — a routine `magi sync` on a
    real library becomes thousands of them. Speed in seconds is flaky to
    assert, so what is pinned is the mechanism."""
    (ws / "drafts").mkdir()
    line(ws)
    for n in range(20):
        (ws / "drafts" / f"d-{n}.md").write_text("# D\n", encoding="utf-8")
        proposition(ws, f"p-{n}", derivation=[f"[[d-{n}]]"],
                    status="testing", when=at(minutes_ago=n + 1))

    calls = []
    original = state._link_index
    monkeypatch.setattr(state, "_link_index",
                        lambda root: (calls.append(root), original(root))[1])

    load(ws)

    assert len(calls) == 1, f"walked the tree {len(calls)} times for 20 links"


def test_next_never_writes(ws, capsys):
    """`next` proposes and does not act (design-v2 §7). A router that edits
    the thing it is describing cannot be run to find out where you are."""
    line(ws)
    path = proposition(ws, "p-a", status="testing")
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("status: testing", "status: supported", 1), encoding="utf-8")

    before = {p: p.read_bytes() for p in sorted(ws.rglob("*")) if p.is_file()}
    state.main(["next", "--topic-dir", str(ws)])
    after = {p: p.read_bytes() for p in sorted(ws.rglob("*")) if p.is_file()}

    assert after == before
    assert "left the note at" in capsys.readouterr().out, "it saw the debt and left it"


def test_the_feed_never_writes(ws):
    path = proposition(ws, "p-a")
    threads.append_post(path, "hello", host="claude", at=at(minutes_ago=1))

    before = {p: p.read_bytes() for p in sorted(ws.rglob("*")) if p.is_file()}
    state.main(["feed", "--topic-dir", str(ws)])
    after = {p: p.read_bytes() for p in sorted(ws.rglob("*")) if p.is_file()}

    assert after == before


def test_a_link_that_names_two_files_picks_the_draft(ws):
    """`derivation:` names the working out, so a draft wins a stem it shares
    with a concept card. Guessing the other way points the debt check at a
    file the proposition was never about."""
    (ws / "drafts").mkdir()
    (ws / "wiki" / "concepts").mkdir(parents=True)
    (ws / "drafts" / "gap.md").write_text("# D\n", encoding="utf-8")
    (ws / "wiki" / "concepts" / "gap.md").write_text("# C\n", encoding="utf-8")

    resolved = state._resolve(ws, "[[gap]]")
    assert resolved == ws / "drafts" / "gap.md"

def test_a_library_with_no_research_state_is_pointed_somewhere(ws, capsys):
    """`next` is the single entry, so in a library that has a wiki and nothing
    it is currently trying to find out, reporting that nothing is owed is true
    and useless."""
    state.main(["next", "--topic-dir", str(ws)])
    out = capsys.readouterr().out
    assert "No propositions yet" in out
    assert "magi thread new" in out and "magi sync" in out


# --------------------------------------------------------------------------
# things the first version of this module got wrong
# --------------------------------------------------------------------------

def collided(ws, slug="p-a"):
    path = proposition(ws, slug)
    threads.set_status(path, "testing", "mine", host="claude", at=at(minutes_ago=32))
    threads.set_status(path, "supported", "theirs", host="codex", at=at(minutes_ago=30))
    return path


def test_a_conflict_a_person_resolved_stays_resolved(ws):
    """The colliding pair sits in the file forever. Without a cut at the
    resolution, every later run re-detects it and flips the note straight back,
    silently undoing the one decision this status exists to protect."""
    path = collided(ws)
    state.close(ws, now=NOW)
    threads.set_status(path, "supported", "I read both; the second is right",
                       host=vocab.HUMAN, at=at(minutes_ago=5))

    report = state.close(ws, now=NOW)

    assert report.conflicts == []
    assert threads.read_note(path).status == "supported"


def test_a_new_collision_after_a_resolution_is_still_caught(ws):
    path = collided(ws)
    state.close(ws, now=NOW)
    threads.set_status(path, "testing", "reopening", host=vocab.HUMAN, at=at(minutes_ago=20))
    threads.set_status(path, "supported", "mine", host="claude", at=at(minutes_ago=4))
    threads.set_status(path, "refuted", "theirs", host="codex", at=at(minutes_ago=3))

    assert state.close(ws, now=NOW).conflicts == ["p-a"]


def test_a_recorded_conflict_stops_the_session_once(ws):
    """The agent cannot resolve a conflict — that is a person's call — but it
    just caused one, and stopping without saying so leaves the human to find it
    in a file."""
    collided(ws)
    report = state.close(ws, now=NOW)
    assert report.ok is False
    assert state.hook_payload(report)["decision"] == "block"


def test_a_conflict_block_names_the_conflict_and_not_a_chore(ws):
    """A block whose reason lists nothing is a block nobody can clear. The
    payload used to describe only unrecorded work, so a session stopped purely
    by a collision got "post what happened" followed by an empty list — an
    instruction that does not apply to a conflict, about nothing in particular.
    An agent told to fix something and given nothing to fix either loops or
    invents work."""
    collided(ws)
    report = state.close(ws, now=NOW)
    assert not report.blocking, "this test is about a conflict on its own"

    reason = state.hook_payload(report)["reason"]

    assert "p-a" in reason
    assert "decision queue" in reason
    assert "magi thread status" not in reason, (
        "a conflict is not cleared by posting; saying so sends the agent to "
        "resolve something only a person can")


def test_one_unwritable_note_does_not_take_the_gate_down(ws):
    """A status no table knows, a file that vanished, a lock somebody holds:
    each is one note's problem. The gate answers for the whole workspace."""
    path = collided(ws, "p-bad")
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("status: supported", "status: nonsense", 1), encoding="utf-8")

    report = state.close(ws, now=NOW)

    assert any("could not be recorded" in item.why for item in report.blocking)


def test_a_decision_about_another_note_does_not_clear_this_one(ws):
    """Slugs run `p-1`, `p-2`, … `p-10`, and a line about `p-10` contains the
    substring `p-1`."""
    path = proposition(ws, "p-1", status="testing")
    threads.set_status(path, "supported", "done", host="claude", at=at(minutes_ago=20))
    threads.set_status(path, "disputed", "no", host="reviewer", at=at(minutes_ago=15))
    threads.set_status(path, "supported", "yes", host="claude", at=at(minutes_ago=10))
    (ws / "decisions.md").write_text("2026-08-29 p-10: unrelated.\n", encoding="utf-8")

    assert any("person's call" in item.why for item in load(ws).debt)


def test_old_unrecorded_decisions_do_not_block_after_a_checkout(ws):
    """A clone resets every mtime. Dating debt by the file would make a fresh
    checkout look like a session's work and the gate would never pass."""
    import os

    path = proposition(ws, "p-a", status="testing")
    threads.set_status(path, "supported", "done", host="claude", at=at(days_ago=190))
    threads.set_status(path, "disputed", "no", host="reviewer", at=at(days_ago=189))
    threads.set_status(path, "supported", "yes", host="claude", at=at(days_ago=188))
    os.utime(path, (NOW.timestamp(), NOW.timestamp()))

    report = state.close(ws, now=NOW)

    assert report.ok is True
    assert any("person's call" in item.why for item in report.older)


def test_a_proposition_on_two_lines_belongs_to_both(ws):
    """`line:` is multi-valued by design. Reading only the first makes a line
    whose open work is shared invisible to the router."""
    line(ws, "qec")
    line(ws, "transport")
    proposition(ws, "p-a", lines=("qec", "transport"), bet="supported",
                status="testing", when=at(days_ago=1))

    actions = state.candidates(load(ws))
    lines_with_work = {action.line for action in actions if action.key == "work"}

    assert lines_with_work == {"qec", "transport"}


def test_the_map_leaves_wip_out_of_the_decision_queue(ws):
    """WIP is a limit `next` enforces, not something anybody is waiting on.
    Listing it here turns the queue into a chore list."""
    line(ws)
    for n in range(9):
        proposition(ws, f"p-{n}")

    text = state.render_map(load(ws, wip_limit=7), now=NOW)
    section = text.split("## Decisions waiting on you", 1)[1]

    assert "wip" not in section


def test_a_link_that_climbs_out_of_the_workspace_resolves_to_nothing(ws):
    assert state._resolve(ws, "[[../../etc/passwd]]") is None
    assert state._resolve(ws, "..\\..\\secrets.md") is None


def test_the_queue_outranks_the_work(ws):
    """The three interrupting events must not sit behind machine work."""
    line(ws)
    disputed_path = proposition(ws, "p-a", status="testing")
    threads.set_status(disputed_path, "supported", "done", host="claude", at=at(minutes_ago=20))
    threads.set_status(disputed_path, "disputed", "no", host="reviewer", at=at(minutes_ago=10))
    line(ws, "transport")
    proposition(ws, "p-b", lines=("transport",), bet="supported", status="testing")

    keys = [action.key for action in state.candidates(load(ws))]

    assert keys.index("disputed") < keys.index("work")


# --------------------------------------------------------------------------
# the dump, the retrospective, and the strict level
# --------------------------------------------------------------------------

def dump(ws, *lines):
    path = ws / "inbox" / "notes.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    from magi.init_workspace import NOTES_STARTER

    path.write_text(NOTES_STARTER + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


def test_the_starter_text_is_not_something_somebody_wrote(ws):
    from magi.init_workspace import NOTES_STARTER

    (ws / "inbox").mkdir()
    (ws / "inbox" / "notes.md").write_text(NOTES_STARTER, encoding="utf-8")
    assert state.unfiled(ws) == []


def test_dumped_lines_are_the_first_thing_next_says(ws):
    """A person's words waiting behind machine bookkeeping is the wrong signal
    about whose time is scarce."""
    line(ws)
    path = proposition(ws, "p-a", status="testing")
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("status: testing", "status: supported", 1), encoding="utf-8")
    dump(ws, "- did anyone check the boundary condition?")

    actions = state.candidates(load(ws))
    assert actions[0].key == "inbox"
    assert actions[1].key == "debt", "debt still outranks everything else"


def test_the_five_places_a_line_can_go_are_named(ws):
    dump(ws, "- something")
    action = [a for a in state.candidates(load(ws)) if a.key == "inbox"][0]
    for surface in ("question", "proposition", "decision", "beads"):
        assert surface in action.run


def test_an_empty_dump_says_nothing(ws):
    dump(ws)
    assert not [a for a in state.candidates(load(ws)) if a.key == "inbox"]


def test_the_map_scores_the_predictions_that_can_be_scored(ws):
    proposition(ws, "p-hit", bet="supported", status="testing")
    threads.set_status(ws / "threads" / "p-hit.md", "supported", "yes", host="claude")
    proposition(ws, "p-miss", bet="refuted", status="testing")
    threads.set_status(ws / "threads" / "p-miss.md", "supported", "actually yes", host="claude")

    back = state.retrospective(load(ws))

    assert (back["hits"], back["scored"]) == (1, 2)
    assert back["rate"] == 0.5


def test_dont_know_is_not_counted_as_a_miss(ws):
    """It is the honest prior. Scoring it as wrong teaches people to guess,
    which makes every other number meaningless."""
    proposition(ws, "p-a", bet="unknown", status="testing")
    threads.set_status(ws / "threads" / "p-a.md", "refuted", "no", host="claude")

    back = state.retrospective(load(ws))
    assert back["scored"] == 0 and back["unknown"] == 1
    assert back["rate"] is None


def test_an_open_proposition_is_not_scored_yet(ws):
    proposition(ws, "p-a", bet="supported", status="testing")
    assert state.retrospective(load(ws))["scored"] == 0


def test_the_map_pulls_the_record_out_without_being_asked(ws):
    """Nobody goes back to look. A hit rate a person never sees trains
    nothing."""
    proposition(ws, "p-a", bet="supported", status="testing")
    threads.set_status(ws / "threads" / "p-a.md", "supported", "yes", host="claude")
    (ws / "decisions.md").write_text("## 2026-08-29 · [[p-a]]\n\nI think so.\n",
                                     encoding="utf-8")

    text = state.render_map(load(ws), now=NOW)
    assert "## Looking back" in text
    assert "1/1" in text
    assert "[[p-a]]" in text


def test_strict_coaching_makes_a_missing_prediction_block(ws):
    """A `PreToolUse` hook sees a tool call, not which proposition it is about,
    so it would have to block everything or nothing. The gate that can tell is
    the one that reads the notes."""
    proposition(ws, "p-a", status="testing")

    assert load(ws, coaching="light").debt == []
    strict = [item.why for item in load(ws, coaching="strict").debt]
    assert any("no prediction on record" in why for why in strict)


def test_dont_know_satisfies_the_strict_level(ws):
    """The point was never a correct prediction. It was a recorded one."""
    proposition(ws, "p-a", bet="unknown", status="testing")
    assert load(ws, coaching="strict").debt == []


# --------------------------------------------------------------------------
# reading the one file a person is allowed to be untidy in
#
# `inbox/notes.md` is where somebody types a thought without deciding where it
# goes. Every way of reading it wrong is a way of losing what they said, so
# these are the shapes the file actually takes: appended to, tidied, and typed
# into by an editor that does not write UTF-8.
# --------------------------------------------------------------------------

def test_a_line_appended_to_the_starter_is_seen(ws):
    """Appending is what appending to a file does. The old splitter dropped
    two paragraphs instead of one, so exactly this — the common case — came
    back empty."""
    from magi.init_workspace import NOTES_STARTER

    path = ws / "inbox" / "notes.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(NOTES_STARTER, encoding="utf-8")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("the disorder angle is probably a dead end\n")

    assert state.unfiled(ws) == ["the disorder angle is probably a dead end"]


def test_a_tidied_file_is_still_read(ws):
    path = ws / "inbox" / "notes.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Notes\n\nfirst idea\nsecond idea\n", encoding="utf-8")
    assert state.unfiled(ws) == ["first idea", "second idea"]


def test_a_file_that_is_not_utf8_does_not_take_next_down(ws):
    """Notepad still writes cp1252 by default, and this is the one file the
    design tells a person to type into freely."""
    path = ws / "inbox" / "notes.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes("# Notes\n\nCaf".encode("utf-8") + bytes([0xE9]) + b" idea" + bytes([10]))

    assert len(state.unfiled(ws)) == 1
    state.candidates(load(ws))  # the whole router used to die here


# --------------------------------------------------------------------------
# a bet is only a bet beforehand
# --------------------------------------------------------------------------

def test_a_bet_written_after_the_answer_is_not_scored(ws):
    """The reason a prediction is asked for before the work is that it can be
    checked after. Scoring one recorded afterwards lets the headline number
    inflate for free."""
    path = proposition(ws, "p-a", status="testing")
    threads.set_status(path, "supported", "it held", host="claude")
    threads.set_field(path, "bet", "supported", host="human", text="I always said so")

    back = state.retrospective(load(ws))
    assert (back["scored"], back["late"]) == (0, 1)
    assert back["rate"] is None


def test_a_bet_written_before_the_work_still_counts(ws):
    path = proposition(ws, "p-a", status="testing")
    threads.set_field(path, "bet", "supported", host="human", text="I think so")
    threads.set_status(path, "supported", "it held", host="claude")

    back = state.retrospective(load(ws))
    assert (back["hits"], back["scored"], back["late"]) == (1, 1, 0)


def test_the_map_says_when_a_bet_arrived_late(ws):
    path = proposition(ws, "p-a", status="testing")
    threads.set_status(path, "supported", "it held", host="claude")
    threads.set_field(path, "bet", "supported", host="human", text="I always said so")

    assert "after the answer was already in" in state.render_map(load(ws), now=NOW)


def test_the_bets_shown_are_the_most_recent_ones(ws):
    """Notes arrive alphabetically. Slicing that order dropped the oldest
    slugs rather than the oldest bets."""
    for index in range(4):
        slug = "p-{0}".format(index)
        path = proposition(ws, slug, bet="supported", status="testing")
        threads.set_status(path, "supported", "done", host="claude",
                           at="2026-08-{0:02d}T00:00:00Z".format(20 - index * 3))

    shown = [row["slug"] for row in state.retrospective(load(ws), limit=2)["bets"]]
    assert shown == ["p-1", "p-0"], "by when they settled, not by name"


# --------------------------------------------------------------------------
# strict says it once, and says it where the gate can hear
# --------------------------------------------------------------------------

def test_one_missing_prediction_is_one_thing_to_do(ws):
    proposition(ws, "p-a", status="testing")
    actions = state.candidates(load(ws, coaching="strict"))
    keys = [(action.key, action.slug) for action in actions]
    assert keys.count(("bet", "p-a")) + keys.count(("debt", "p-a")) == 1, keys


def test_the_nudge_survives_before_work_starts(ws):
    """Strict blocks where the derivation is, which is `testing`. A conjecture
    nobody has started on has none yet, so the earlier ask stays an ask."""
    proposition(ws, "p-a", status="conjectured")
    keys = [(action.key, action.slug) for action in state.candidates(load(ws, coaching="strict"))]
    assert ("bet", "p-a") in keys and ("debt", "p-a") not in keys


# --------------------------------------------------------------------------
# --line means --line
# --------------------------------------------------------------------------

def test_another_lines_review_is_not_this_lines_work(ws, capsys):
    line(ws, "qec")
    path = proposition(ws, "p-other", status="testing", lines=["other"])
    threads.set_status(path, "supported", "done", host="claude")

    state.main(["next", "--topic-dir", str(ws), "--line", "qec", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert not [a for a in payload["actions"] if a["key"] == "review"]


def test_the_queue_says_who_disputed_it(ws):
    """The WebUI can flip a note to `disputed` too, and a queue that tells a
    person a reviewer did something they just did themselves is a queue they
    stop reading."""
    path = proposition(ws, "p-a", status="testing")
    threads.set_status(path, "supported", "converged", host="claude")
    threads.set_status(path, "disputed", "the boundary condition was wrong",
                       host=vocab.HUMAN)

    why = [item.why for item in load(ws).queue if item.slug == "p-a"][0]
    assert "you put this in dispute" in why


def test_a_reviewers_rejection_still_says_reviewer(ws):
    path = proposition(ws, "p-a", status="testing")
    threads.set_status(path, "supported", "converged", host="claude")
    threads.set_status(path, "disputed", "the cited line is not there",
                       host=vocab.REVIEWER)

    why = [item.why for item in load(ws).queue if item.slug == "p-a"][0]
    assert "a reviewer rejected this" in why


def test_a_thought_that_starts_with_a_hash_comes_back(ws):
    """The box promises no format. The one thing it owes in return is that
    what goes in comes out — a leading `#` used to be written verbatim and
    then read as the starter's scaffolding, so it never surfaced again."""
    state.dump(ws, "# a heading-shaped thought")
    assert state.unfiled(ws) == ["- # a heading-shaped thought"]


def test_a_bullet_somebody_typed_is_left_alone(ws):
    state.dump(ws, "- already a bullet")
    assert state.unfiled(ws) == ["- already a bullet"]


# --------------------------------------------------------------------------
# what the week cost, where a person looks
#
# A limit that only announces itself by refusing is a limit that surprises
# somebody mid-sentence. The map is the file the design says a person reads.
# --------------------------------------------------------------------------

def test_the_map_says_what_the_week_has_cost(ws):
    from magi.core import ledger

    line(ws)
    (ws / "config.yaml").write_text("research:\n  weekly_calls: 10\n", encoding="utf-8")
    for index in range(3):
        ledger.record(ws, ledger.REVIEW, "codex", slug=f"p-{index}")

    text = state.render_map(load(ws), now=NOW)

    assert "## Spending" in text
    assert "3/10 model calls this week" in text


def test_a_spent_budget_says_nothing_counts_as_reviewed(ws):
    """The failure to avoid is a gate that stops the call and lets the claim
    retire anyway — that would spend nothing and approve everything."""
    from magi.core import ledger

    line(ws)
    (ws / "config.yaml").write_text("research:\n  weekly_calls: 2\n", encoding="utf-8")
    for index in range(2):
        ledger.record(ws, ledger.REVIEW, "codex", slug=f"p-{index}")

    text = state.render_map(load(ws), now=NOW)
    assert "nothing counts as reviewed" in text


def test_the_master_switch_is_said_out_loud(ws):
    line(ws)
    (ws / "config.yaml").write_text("research:\n  llm_calls: false\n", encoding="utf-8")

    assert "switched off" in state.render_map(load(ws), now=NOW)


def test_a_workspace_with_no_ledger_still_draws_its_map(ws):
    line(ws)
    text = state.render_map(load(ws), now=NOW)
    assert "0/40 model calls" in text, "the default limit, nothing spent"


# --------------------------------------------------------------------------
# the slow loop's proposals are a queue kind, not a special case
# --------------------------------------------------------------------------

def test_an_undecided_proposal_is_something_only_a_person_can_settle(ws):
    from magi.reflect import proposals

    made = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="p-stall")

    item = [q for q in load(ws).queue if q.kind == "proposal"][0]
    assert item.slug == made.id
    assert "Check the boundary first." in item.why


def test_a_decided_proposal_leaves_the_queue(ws):
    from magi.reflect import proposals

    made = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="p-stall")
    proposals.decide(ws, made.id, proposals.ACCEPTED)

    assert not [q for q in load(ws).queue if q.kind == "proposal"]


def test_the_action_says_the_three_things_a_person_can_do(ws):
    from magi.reflect import proposals

    made = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="p-stall")

    action = [a for a in state.candidates(load(ws)) if a.key == "proposal"][0]
    assert made.id in action.run
    assert "reject" in action.run and "promote" in action.run


def test_a_workspace_that_never_reflected_has_no_proposals(ws):
    """No ledger is not an error."""
    assert not [q for q in load(ws).queue if q.kind == "proposal"]


# --------------------------------------------------------------------------
# the way out
#
# Without this the loop only adds. Every accepted rule is read at the start of
# every session forever, and the reason it was accepted can stop being true
# without anybody noticing.
# --------------------------------------------------------------------------

def test_a_rule_whose_reason_went_quiet_is_asked_about(ws):
    import datetime as date_mod

    from magi.reflect import patterns, proposals

    old = date_mod.date.today() - date_mod.timedelta(days=100)
    for host in ("claude", "codex"):
        patterns.observe(ws, "sweeps-stall", title="t", body="b",
                         session=f"{host}/s", host=host, when=old)
    made = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="sweeps-stall")
    proposals.decide(ws, made.id, proposals.ACCEPTED)

    item = [q for q in load(ws).queue if q.kind == "retire"][0]
    assert item.slug == made.id
    assert "90 days" in item.why and "Check the boundary first." in item.why


def test_a_rule_whose_pattern_still_recurs_is_left_alone(ws):
    from magi.reflect import patterns, proposals

    for host in ("claude", "codex"):
        patterns.observe(ws, "sweeps-stall", title="t", body="b",
                         session=f"{host}/s", host=host)
    made = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="sweeps-stall")
    proposals.decide(ws, made.id, proposals.ACCEPTED)

    assert not [q for q in load(ws).queue if q.kind == "retire"]


def test_the_question_is_leave_it_or_drop_it(ws):
    """Ninety silent days may be the rule working. Only a person can tell that
    apart from a rule nobody needed."""
    import datetime as date_mod

    from magi.reflect import patterns, proposals

    old = date_mod.date.today() - date_mod.timedelta(days=100)
    for host in ("claude", "codex"):
        patterns.observe(ws, "sweeps-stall", title="t", body="b",
                         session=f"{host}/s", host=host, when=old)
    made = proposals.propose(ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="sweeps-stall")
    proposals.decide(ws, made.id, proposals.ACCEPTED)

    action = [a for a in state.candidates(load(ws)) if a.key == "retire"][0]
    assert "retire" in action.run and "leave it" in action.run
    assert "reject" not in action.run, (
        "rejecting says the idea was bad and bans it from ever being proposed "
        "again; retiring says its reason has gone")


# --------------------------------------------------------------------------
# one unreadable note must not take the projection with it
#
# `sync --close --hook` is the worst case: it is supposed to print JSON for a
# Stop hook, and a note nobody can read *is* unrecorded work — so the gate
# failing to run on account of one is the gate failing at exactly the moment
# it exists for.
# --------------------------------------------------------------------------

def test_a_note_that_cannot_be_read_becomes_debt_not_a_crash(ws, monkeypatch):
    line(ws)
    proposition(ws, "p-fine", status="testing")
    (ws / "threads" / "p-broken.md").write_text("---\nkind: proposition\n---\n",
                                                encoding="utf-8")

    real = threads.read_note

    def refuse(path):
        if Path(path).name == "p-broken.md":
            raise OSError("Permission denied")
        return real(path)

    monkeypatch.setattr(threads, "read_note", refuse)

    loaded = load(ws)

    assert [item.slug for item in loaded.debt][:1] == ["p-broken"]
    assert "could not be read" in loaded.debt[0].why
    assert any(note.slug == "p-fine" for note in loaded.notes), "the rest survives"


def test_the_close_gate_still_answers_with_a_broken_note(ws, monkeypatch):
    line(ws)
    (ws / "threads" / "p-broken.md").write_text("x", encoding="utf-8")

    real = threads.read_note

    def refuse(path):
        if Path(path).name == "p-broken.md":
            raise OSError("Permission denied")
        return real(path)

    monkeypatch.setattr(threads, "read_note", refuse)

    report = state.close(ws, write=False, now=NOW)

    assert not report.ok, "an unreadable note is unrecorded work"
    assert any("could not be read" in item.why for item in report.blocking)


# --------------------------------------------------------------------------
# --line means this line's everything
# --------------------------------------------------------------------------

def test_open_questions_are_this_lines_questions(ws, capsys):
    line(ws, "qec")
    line(ws, "other")
    threads.create(ws / "threads" / "q-here.md", vocab.QUESTION, "Here?", "p",
                   lines=["qec"])
    threads.create(ws / "threads" / "q-there.md", vocab.QUESTION, "There?", "p",
                   lines=["other"])

    state.main(["next", "--topic-dir", str(ws), "--line", "qec", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["open_questions"] == ["q-here"]


def test_debt_on_the_lines_own_note_is_not_dropped(ws, capsys):
    """A line note has no `line:` field, so "does it name this line" was false
    for the one note that *is* this line — and its debt vanished from the view
    whose first promise is that debt comes first."""
    path = line(ws, "qec")
    text = path.read_text(encoding="utf-8").replace("status: exploring",
                                                    "status: active", 1)
    path.write_text(text, encoding="utf-8")

    state.main(["next", "--topic-dir", str(ws), "--line", "qec", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert [item["slug"] for item in payload["debt"]] == ["qec"]


def test_a_fresh_checkout_does_not_look_like_a_session_of_work(ws):
    """`git clone` stamps every file with the time it was written, so the
    draft's mtime becomes now while the post timestamps inside the note stay
    old — and every proposition with a `derivation:` became debt. `DebtItem`
    warns about exactly this: a gate that fires on every checkout is a gate
    somebody turns off."""
    import os

    (ws / "drafts").mkdir()
    draft = ws / "drafts" / "gap-argument.md"
    draft.write_text("# Argument\n", encoding="utf-8")
    path = proposition(ws, "p-a", derivation=["[[gap-argument]]"])
    threads.set_status(path, "testing", "started", host="claude", at=at(minutes_ago=60))

    # What a checkout leaves behind: both files written seconds apart, now.
    now = NOW.timestamp()
    os.utime(path, (now, now))
    os.utime(draft, (now + 1, now + 1))

    assert [item for item in load(ws).debt if "gap-argument" in item.why] == []


def test_debt_dated_only_by_an_mtime_never_holds_a_session_closed(ws):
    """It is shown, and it does not gate. An mtime is rewritten by a clone, a
    checkout, a restored backup, an editor's "save all" and a stray `touch`,
    none of which changed a word — so it is worth telling somebody about and
    not worth stopping them with."""
    import os

    (ws / "drafts").mkdir()
    draft = ws / "drafts" / "gap-argument.md"
    draft.write_text("# Argument\n", encoding="utf-8")
    path = proposition(ws, "p-a", derivation=["[[gap-argument]]"])
    threads.set_status(path, "testing", "started", host="claude", at=at(minutes_ago=60))
    an_hour_ago = NOW.timestamp() - 3600
    os.utime(path, (an_hour_ago, an_hour_ago))
    os.utime(draft, (NOW.timestamp(), NOW.timestamp()))

    found = [item for item in load(ws).debt if "gap-argument" in item.why]
    assert found, "it is still reported"
    assert found[0].blocks is False, "and it is still not a gate"


def test_a_focus_set_does_not_build_the_whole_projection(ws, monkeypatch):
    """`focus` ran `load()` — debt, the rule engine, its own link index — and
    then `_link_index` again, to produce a ranking multiplier.
    `retrieval._line_focus` calls it on every `--line` search."""
    line(ws)
    proposition(ws, "p-a", status="testing")

    def refuse(*a, **k):
        raise AssertionError("focus built the full projection")

    monkeypatch.setattr(state, "load", refuse)

    found = state.focus(ws, "qec")

    assert any("p-a" in str(item) for item in found)


def test_the_gate_and_the_router_read_settings_through_one_function(ws):
    """`_reload` was a second copy of `loaded` — the same four config lookups
    written out again. Two spellings of "read the workspace's own settings" is
    how they get to disagree, which is the bug `magi sync` had."""
    import inspect

    body = inspect.getsource(state._reload)
    assert "loaded(root)" in body
    assert "config_get" not in body, "the second copy is back"
