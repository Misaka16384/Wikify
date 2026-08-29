"""The v2 WebUI surface: the map, the queue, the threads, and the dump box.

One property carries this file. **The browser and the terminal must answer the
same question the same way.** A dashboard that reports a different number than
`magi next` is worse than no dashboard: one of them is wrong, and from the
outside there is no way to tell which. So the tests below mostly compare an
endpoint against the function the CLI calls, rather than restating what the
answer should be — a restatement is a third copy of the rule, and it drifts
like the second one.

The other property is that nothing here decides anything. Which statuses a note
may become, who may say so, what counts as stalled — all of it arrives as data,
computed by the same `vocab` and `state` the CLI uses, so the JS has nothing to
judge and cannot judge it differently (design-v2 D4).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from magi import state
from magi.core import vocab
from magi.kb import threads
from magi.ui.api import create_app


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "magicfg"))
    root = tmp_path / "topic"
    (root / "threads").mkdir(parents=True)
    (root / "inbox").mkdir(parents=True)
    (root / "output").mkdir(parents=True)
    (root / "config.yaml").write_text("research:\n  coaching: light\n", encoding="utf-8")

    threads.create(root / "threads" / "qec.md", vocab.LINE, "QEC",
                   "Whether the code survives disorder.")
    gap = threads.create(root / "threads" / "p-gap.md", vocab.PROPOSITION,
                         "The gap survives", "Decide before the numerics.",
                         lines=["qec"])
    threads.set_status(gap, "testing", "started the sweep", host="claude", line="qec")
    threads.create(root / "threads" / "q-why.md", vocab.QUESTION,
                   "Why does it survive?", "Open question.", lines=["qec"])
    return root


@pytest.fixture
def client(ws):
    client = TestClient(create_app())
    client.ws = ws
    return client


def get(client, path, **params):
    params.setdefault("workspace", str(client.ws))
    res = client.get(path, params=params)
    assert res.status_code == 200, res.text
    return res.json()


def post(client, path, **payload):
    payload.setdefault("workspace", str(client.ws))
    return client.post(path, json=payload)


# --------------------------------------------------------------------------
# the map is what `magi next` says
# --------------------------------------------------------------------------

def test_the_map_is_field_for_field_what_the_cli_prints(client):
    loaded = state.loaded(client.ws)
    expected = state.to_json(loaded, state.candidates(loaded))

    payload = get(client, "/api/workspace/map")

    for key, value in expected.items():
        assert payload[key] == value, key


def test_the_map_carries_what_the_map_file_adds(client):
    payload = get(client, "/api/workspace/map")
    assert set(payload) >= {"retrospective", "unfiled", "unreviewed", "coaching",
                            "wip_limit"}
    assert payload["coaching"] == "light", "read from config, not assumed"


def test_the_feed_is_the_same_view_the_cli_renders(client):
    entries = state.feed(state.loaded(client.ws))
    payload = get(client, "/api/workspace/feed")

    assert payload["total"] == len(entries)
    assert [entry["slug"] for entry in payload["entries"]] == [e.slug for e in entries]


def test_a_window_narrows_the_feed(client):
    assert get(client, "/api/workspace/feed", window=0)["total"] >= 1
    # Everything in the fixture was posted just now, so an hour back keeps it.
    assert get(client, "/api/workspace/feed", window=1)["total"] >= 1


# --------------------------------------------------------------------------
# threads arrive knowing what they are
# --------------------------------------------------------------------------

def test_the_thread_list_says_kind_status_and_temperature(client):
    rows = {row["slug"]: row for row in get(client, "/api/workspace/threads")["threads"]}

    assert rows["p-gap"]["kind"] == vocab.PROPOSITION
    assert rows["p-gap"]["status"] == "testing"
    assert rows["p-gap"]["title"] == "The gap survives"
    assert rows["p-gap"]["tier"] == vocab.tier_of("threads/p-gap.md",
                                                  vocab.PROPOSITION, "testing")


def test_the_list_filters_the_way_the_query_asks(client):
    only = get(client, "/api/workspace/threads", kind=vocab.QUESTION)["threads"]
    assert [row["slug"] for row in only] == ["q-why"]

    assert get(client, "/api/workspace/threads", line="nowhere")["count"] == 0


def test_the_moves_come_from_the_vocabulary(client):
    """The buttons are built from this. A copy of the transition table in JS is
    a second table, and the two disagree the first time one is edited."""
    payload = get(client, "/api/workspace/thread", slug="p-gap")

    # Everything the vocabulary allows except `conflict`: that status is what
    # the close gate *writes* when two writers collide, and a person choosing
    # it from a dropdown is recording a disagreement that did not happen.
    assert [move["dst"] for move in payload["moves"]] == \
        [dst for dst in vocab.allowed_targets(vocab.PROPOSITION, "testing")
         if dst != vocab.CONFLICT]
    for move in payload["moves"]:
        assert move["writers"] == sorted(
            vocab.writers(vocab.PROPOSITION, "testing", move["dst"]))


def test_a_thread_carries_its_discussion(client):
    payload = get(client, "/api/workspace/thread", slug="p-gap")
    assert payload["posts"][-1]["dst"] == "testing"
    assert payload["posts"][-1]["text"] == "started the sweep"


def test_a_slug_that_is_a_path_is_refused(client):
    res = client.get("/api/workspace/thread",
                     params={"slug": "../config", "workspace": str(client.ws)})
    assert res.status_code == 400


def test_a_thread_that_is_not_there_is_a_404(client):
    res = client.get("/api/workspace/thread",
                     params={"slug": "p-nope", "workspace": str(client.ws)})
    assert res.status_code == 404


# --------------------------------------------------------------------------
# what a person does from the browser
# --------------------------------------------------------------------------

def test_a_post_from_the_browser_is_signed_as_a_person(client):
    """`sync --close` reads that signature to decide whether somebody actually
    ruled on something. A post signed with a host name claims a model said it,
    which is the one signature the record cannot afford to invent."""
    assert post(client, "/api/workspace/thread/post", slug="p-gap",
                text="I read this and I am not convinced.").status_code == 200

    note = threads.read_note(client.ws / "threads" / "p-gap.md")
    assert note.posts[-1].host == "human"
    assert note.posts[-1].text == "I read this and I am not convinced."


def test_an_empty_post_is_refused(client):
    assert post(client, "/api/workspace/thread/post", slug="p-gap",
                text="   ").status_code == 400


def test_a_status_change_needs_a_reason(client):
    res = post(client, "/api/workspace/thread/status", slug="p-gap",
               dst="supported", text="")
    assert res.status_code == 400
    assert threads.read_note(client.ws / "threads" / "p-gap.md").status == "testing"


def test_a_status_change_lands_with_the_reason_attached(client):
    assert post(client, "/api/workspace/thread/status", slug="p-gap",
                dst="supported", text="the sweep converged").status_code == 200

    note = threads.read_note(client.ws / "threads" / "p-gap.md")
    assert note.status == "supported"
    assert (note.posts[-1].src, note.posts[-1].dst) == ("testing", "supported")
    assert note.posts[-1].text == "the sweep converged"


def test_a_move_the_lifecycle_does_not_allow_is_refused(client):
    res = post(client, "/api/workspace/thread/status", slug="q-why",
               dst="supported", text="it is")
    assert res.status_code == 400
    assert "legal transition" in res.json()["detail"]


def test_deciding_writes_all_three_places(client):
    res = post(client, "/api/workspace/decide", about="p-gap", bet="supported",
               kind="prediction", text="I expect it holds in the bulk.")
    assert res.status_code == 200, res.text

    note = threads.read_note(client.ws / "threads" / "p-gap.md")
    assert note.frontmatter["bet"] == "supported"
    assert note.posts[-1].host == "human" and note.posts[-1].field == "bet"
    assert "holds in the bulk" in (client.ws / "decisions.md").read_text(encoding="utf-8")


def test_a_bet_on_something_that_cannot_be_wrong_is_refused(client):
    res = post(client, "/api/workspace/decide", about="q-why", bet="supported",
               text="yes")
    assert res.status_code == 400
    assert "proposition" in res.json()["detail"]
    assert not (client.ws / "decisions.md").is_file()


# --------------------------------------------------------------------------
# the dump box
# --------------------------------------------------------------------------

def test_the_dump_box_appends_and_shows_up_as_unfiled(client):
    res = post(client, "/api/workspace/dump",
               text="did anyone check the boundary condition?")
    assert res.status_code == 200 and res.json()["unfiled"] == 1

    assert state.unfiled(client.ws) == ["- did anyone check the boundary condition?"]
    assert get(client, "/api/workspace/map")["actions"][0]["key"] == "inbox"


def test_the_dump_box_does_not_reformat_what_is_already_there(client):
    notes = client.ws / "inbox" / "notes.md"
    notes.write_text("- an older thought\n", encoding="utf-8")

    post(client, "/api/workspace/dump", text="a newer one")

    assert notes.read_text(encoding="utf-8") == "- an older thought\n- a newer one\n"


def test_an_empty_dump_is_refused(client):
    assert post(client, "/api/workspace/dump", text="\n  \n").status_code == 400


def test_the_thread_view_does_not_send_the_discussion_twice(client):
    payload = get(client, "/api/workspace/thread", slug="p-gap")
    assert "## Discussion" not in payload["body"]
    assert payload["posts"], "which is where the discussion actually is"


# --------------------------------------------------------------------------
# what a request may not do
#
# Two of these were live holes. A signature is a claim about who said
# something, and `sync --close` reads it to decide whether a person ruled on
# anything — so a request that can write one is a request that can forge the
# one field the record cannot afford to invent. And a workspace that is
# whatever path arrived in the body is a workspace that can be any directory
# this process can write to.
# --------------------------------------------------------------------------

def test_a_line_cannot_close_the_signature_and_open_another(client):
    """`### <at> · host/line` — a newline in `line` used to end that heading
    and start a second post, signed `reviewer`, from the browser."""
    forged = "qec\n### 2026-01-01T00:00:00Z · reviewer\nstatus: testing -> refuted"

    res = post(client, "/api/workspace/decide", about="p-gap",
               text="I think it holds.", line=forged)

    assert res.status_code == 400
    note = threads.read_note(client.ws / "threads" / "p-gap.md")
    assert [p.host for p in note.posts] == ["claude"], "nothing was written"


def test_the_same_guard_covers_posting_and_flipping(client):
    forged = "qec\n### 2026-01-01T00:00:00Z · reviewer"

    assert post(client, "/api/workspace/thread/post", slug="p-gap",
                text="hm", line=forged).status_code == 400
    assert post(client, "/api/workspace/thread/status", slug="p-gap",
                dst="supported", text="hm", line=forged).status_code == 400


def test_an_ordinary_line_still_signs_normally(client):
    assert post(client, "/api/workspace/thread/post", slug="p-gap",
                text="reading this from the qec line", line="qec").status_code == 200
    assert threads.read_note(client.ws / "threads" / "p-gap.md").posts[-1].line == "qec"


def test_a_write_refuses_a_directory_that_is_not_a_library(client, tmp_path):
    """`inbox/` and `decisions.md` in whatever directory arrived in the body
    is a filesystem this process should not have."""
    elsewhere = tmp_path / "not-a-workspace" / "deep"

    for route, payload in (("/api/workspace/dump", {"text": "x"}),
                           ("/api/workspace/decide", {"text": "x"})):
        res = client.post(route, json={"workspace": str(elsewhere), **payload})
        assert res.status_code == 400, route

    assert not elsewhere.exists(), "and nothing was created on the way"


def test_a_broken_note_is_an_answer_not_a_500(client):
    (client.ws / "threads" / "junk.md").write_text("# just words\n", encoding="utf-8")

    res = post(client, "/api/workspace/thread/status", slug="junk",
               dst="open", text="why")
    assert res.status_code == 400


def test_a_note_saved_by_notepad_does_not_take_the_dashboard_down(client):
    """One cp1252 file used to 500 every v2 endpoint and `magi next` with it."""
    (client.ws / "threads" / "p-bad.md").write_bytes(
        "---\nkind: proposition\nstatus: open\ncreated: 2026-08-29\n"
        "purpose: caf".encode("utf-8") + bytes([0xE9])
        + "\n---\n\n# Caf".encode("utf-8") + bytes([0xE9, 10]))

    assert get(client, "/api/workspace/map")["lines"] is not None
    assert any(row["slug"] == "p-bad"
               for row in get(client, "/api/workspace/threads")["threads"])


def test_the_wip_rule_is_applied_once_and_in_python(client):
    """`decisions` is the queue with WIP dropped. The browser renders that
    list rather than filtering the raw queue a second time."""
    payload = get(client, "/api/workspace/map")
    assert "decisions" in payload
    assert all(item["kind"] != "wip" for item in payload["decisions"])


def test_a_scalar_line_arrives_as_a_list(client):
    """YAML lets `line:` be a scalar. The raw frontmatter carries whichever
    the author typed; `lines` is the shape the browser can rely on."""
    path = client.ws / "threads" / "p-scalar.md"
    path.write_text("---\nkind: proposition\nstatus: open\n"
                    "created: 2026-08-29\npurpose: p\nline: qec\n---\n\n"
                    "# Scalar line\n", encoding="utf-8")

    payload = get(client, "/api/workspace/thread", slug="p-scalar")
    assert payload["lines"] == ["qec"]
    assert payload["frontmatter"]["line"] == "qec", "raw, as written"


# --------------------------------------------------------------------------
# the slow loop's three buttons, from the browser
#
# Same code path as the CLI, which is what makes "the budget refuses" true in
# both places rather than only in the terminal.
# --------------------------------------------------------------------------

def test_a_proposal_is_a_decision_waiting_on_a_person(client):
    from magi.reflect import proposals

    made = proposals.propose(client.ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="p-stall")

    payload = get(client, "/api/workspace/map")
    kinds = [item["kind"] for item in payload["decisions"]]
    assert "proposal" in kinds
    assert any(made.id == item["slug"] for item in payload["decisions"])


def test_accepting_from_the_browser_writes_the_same_records(client):
    from magi.reflect import proposals

    made = proposals.propose(client.ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="p-stall")

    res = post(client, "/api/workspace/proposal", id=made.id, verb="accept")

    assert res.status_code == 200
    assert proposals.get(client.ws, made.id).verdict == proposals.ACCEPTED


def test_a_verb_nobody_defined_is_refused(client):
    res = post(client, "/api/workspace/proposal", id="r-1", verb="delete")
    assert res.status_code == 400


def test_retiring_from_the_browser_is_a_decision_a_person_can_make(client):
    """The queue asks "is this rule still earning its place?" every time
    `magi next` runs. Answering it only in a terminal means it sits there
    forever — and the dashboard exists so a person does not have to open one."""
    from magi.reflect import proposals

    made = proposals.propose(client.ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="p-quiet")
    post(client, "/api/workspace/proposal", id=made.id, verb="accept")

    res = post(client, "/api/workspace/proposal", id=made.id, verb="retire")

    assert res.status_code == 200
    assert proposals.get(client.ws, made.id).verdict == proposals.RETIRED
    assert made.id not in [rule.id for rule in proposals.live_rules(client.ws)]


def test_a_proposal_that_is_not_there_is_refused(client):
    res = post(client, "/api/workspace/proposal", id="r-nope", verb="accept")
    assert res.status_code == 400
    assert "no proposal" in res.json()["detail"]


def test_the_rule_budget_refuses_in_the_browser_too(client):
    """It has to be able to say no here, or the block and the ledger part
    company the first time somebody uses the dashboard."""
    from magi.core import managed
    from magi.reflect import proposals

    (client.ws / "config.yaml").write_text("research:\n  rule_budget: 1\n",
                                           encoding="utf-8")
    first = proposals.propose(client.ws, kind=proposals.RULE, target="AGENTS.md",
                              text="The first one.", pattern="p")
    second = proposals.propose(client.ws, kind=proposals.RULE, target="AGENTS.md",
                               text="The second one.", pattern="p")
    post(client, "/api/workspace/proposal", id=first.id, verb="accept")

    res = post(client, "/api/workspace/proposal", id=second.id, verb="accept")

    assert res.status_code == 400
    assert "full" in res.json()["detail"]
    assert proposals.get(client.ws, second.id).open


def test_capturing_a_clis_output_is_serialised(client, monkeypatch):
    """`redirect_stdout` swaps the process-global `sys.stdout`, and Starlette
    runs a sync route on a shared threadpool. Two tabs deciding at once
    interleaved their contexts: one request got the other's output, and the
    block exiting second restored `sys.stdout` to a buffer the first had
    already discarded — after which every uvicorn log line went somewhere
    nobody reads, for the life of the process."""
    from magi.reflect import proposals
    from magi.ui import v2

    made = proposals.propose(client.ws, kind=proposals.RULE, target="AGENTS.md",
                             text="Check the boundary first.", pattern="p-lock")
    from magi.reflect import cmd as reflect_cmd

    held = []
    real = reflect_cmd._decide

    def watching(*args, **kwargs):
        held.append(v2._CAPTURE_LOCK.locked())
        return real(*args, **kwargs)

    monkeypatch.setattr(reflect_cmd, "_decide", watching)

    post(client, "/api/workspace/proposal", id=made.id, verb="accept")

    assert held == [True], "the capture ran without holding the lock"
    assert not v2._CAPTURE_LOCK.locked(), "and it is released afterwards"


# --------------------------------------------------------------------------
# review, from the browser
# --------------------------------------------------------------------------

def _solved(ws, slug="p-gap"):
    """Walk the fixture's proposition to the one status review answers."""
    path = ws / "threads" / f"{slug}.md"
    threads.set_status(path, "supported", "the sweep converged", host="claude")
    return path


def test_the_plan_says_who_and_what_is_left_before_anything_is_spent(
        client, monkeypatch):
    """The browser's `--dry-run`. A button that spends money must not look
    like every other button, and "who is this asking, and what is left of the
    week" has to arrive before the press rather than in a log afterwards."""
    from magi import review as review_mod
    from magi.core import ledger

    _solved(client.ws)
    called = []
    monkeypatch.setattr(review_mod, "installed_hosts",
                        lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review_mod, "ask", lambda *a, **k: called.append(1) or "")

    plan = get(client, "/api/workspace/review/plan", slug="p-gap")

    assert plan["host"] == "codex"
    assert plan["budget"]["limit"] and plan["budget"]["left"] >= 1
    assert not called, "planning spent a call"
    assert ledger.entries(client.ws) == []


def test_a_slug_that_cannot_be_reviewed_is_refused_by_the_plan(client, monkeypatch):
    """Same guard as the CLI, at the same point: before the money. The panel
    can then say so instead of offering a button that will fail."""
    from magi import review as review_mod

    monkeypatch.setattr(review_mod, "installed_hosts", lambda *_a, **_k: ["codex"])

    plan = get(client, "/api/workspace/review/plan", slug="q-why")

    assert plan["refused"], "a question is not a claim and cannot be reviewed"
    assert plan["host"] is None


def test_reviewing_from_the_browser_writes_the_same_record(client, monkeypatch):
    """One slug, and the verdict lands in the note exactly as the CLI writes
    it — the browser is a second face on one library, not a second library."""
    from magi import review as review_mod

    _solved(client.ws)
    monkeypatch.setattr(review_mod, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review_mod, "ask",
                        lambda *a, **k: "VERDICT: stands\nREASON: the sweep supports it.")

    res = post(client, "/api/workspace/review", slug="p-gap")
    assert res.status_code == 200, res.text
    res = res.json()

    assert res["verdict"] == "stands"
    assert "sweep supports it" in res["reason"]
    assert res["budget"]["spent"] == 1
    note = threads.read_note(client.ws / "threads" / "p-gap.md")
    assert note.posts[-1].host == "reviewer"


def test_the_endpoint_reviews_one_claim_and_never_a_batch(client, monkeypatch):
    """`magi review` with no argument reviews everything unreviewed at once —
    the shape that let a workspace 39 calls into a limit of 40 finish at
    99/40. A button pressed twice must not be able to do that."""
    from magi import review as review_mod

    _solved(client.ws)
    threads.create(client.ws / "threads" / "p-two.md", vocab.PROPOSITION,
                   "Another", "why", lines=["qec"])
    _solved(client.ws, "p-two")
    called = []
    monkeypatch.setattr(review_mod, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review_mod, "ask",
                        lambda *a, **k: called.append(1) or "VERDICT: stands\nREASON: ok.")

    assert post(client, "/api/workspace/review", slug="p-gap").status_code == 200

    assert len(called) == 1, "one press, one claim"
    assert "p-two" in review_mod.pending(client.ws)


def test_a_spent_budget_refuses_and_says_so(client, monkeypatch):
    """409, not 500: the server is fine and the answer is "not this week"."""
    from magi import review as review_mod
    from magi.core import ledger

    _solved(client.ws)
    (client.ws / "config.yaml").write_text(
        "research:\n  weekly_calls: 1\n", encoding="utf-8")
    ledger.record(client.ws, ledger.REVIEW, "codex", slug="earlier")
    called = []
    monkeypatch.setattr(review_mod, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review_mod, "ask", lambda *a, **k: called.append(1) or "")

    res = client.post("/api/workspace/review",
                      json={"workspace": str(client.ws), "slug": "p-gap"})

    assert res.status_code == 409
    assert "budget" in res.json()["detail"]
    assert not called


def test_the_dashboard_can_see_what_the_week_cost(client):
    """design-v2 §13 puts the weekly budget in the WebUI. It was configurable
    there and never displayed, so the one number the configuration governs
    could only be read by opening MAP.md or the ledger by hand."""
    from magi.core import ledger

    ledger.record(client.ws, ledger.REVIEW, "codex", slug="p-gap")

    payload = get(client, "/api/workspace/map")

    assert payload["budget"]["spent"] == 1
    assert payload["budget"]["limit"] >= 1


# --------------------------------------------------------------------------
# what is sitting in inbox/
# --------------------------------------------------------------------------

def test_the_browser_can_see_the_files_it_told_you_to_drop_there(client):
    """The Dashboard's own suggested action is "drop paper PDFs into inbox/".
    Do it, and the Ingest Queue showed `WAITING IN QUEUE 0` over a directory
    with two papers in it, because that counter only ever tracked what its own
    URL/upload widgets had queued. There was no file listing for `inbox/`
    anywhere in the app."""
    (client.ws / "inbox" / "a-paper.pdf").write_bytes(b"%PDF-1.7 body")
    (client.ws / "inbox" / "notes-from-a-talk.md").write_text("x", encoding="utf-8")

    payload = get(client, "/api/workspace/inbox")

    assert payload["count"] == 2
    assert {f["name"] for f in payload["files"]} == {"a-paper.pdf",
                                                     "notes-from-a-talk.md"}


def test_the_pile_is_not_a_document(client):
    """`inbox/notes.md` is the pile: it has its own text box, `magi next`
    sorts it, and it is never something to ingest. Offering it here would put
    a "pick this up" button on the one file that must not be picked up."""
    (client.ws / "inbox" / "notes.md").write_text("- a thought\n", encoding="utf-8")
    (client.ws / "inbox" / "radar").mkdir(exist_ok=True)

    payload = get(client, "/api/workspace/inbox")

    assert payload["count"] == 0


def test_an_empty_inbox_says_zero_rather_than_failing(client):
    assert get(client, "/api/workspace/inbox") == {"files": [], "count": 0}


def test_there_is_an_operation_that_picks_them_up(client):
    """`magi ingest auto` with no paths takes the whole of `inbox/` and had no
    button anywhere — so the advice had no other end."""
    from magi.ui import jobs

    assert "ingest-auto" in jobs.OPS
    assert jobs.OPS["ingest-auto"]["argv"] == ["ingest", "auto"]
