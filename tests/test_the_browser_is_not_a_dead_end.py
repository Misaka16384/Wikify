"""Every step of the daily loop can be taken without leaving the browser.

The criterion, in the author's words: an operation is *important* when skipping
it blocks the flow — when the person has to switch to the agent or the CLI to
carry on with ordinary work. Anything meeting that test belongs in the WebUI.

Measured against the loop, five steps failed it, and the two sharpest were the
two design-v2 §6 reserves for a human. Closing a research line and publishing a
paper are ceremonial *by design*, the acts an agent may never perform — and the
person who lives in the browser was the only one who could not perform them
either. Opening a note had no endpoint at all, which is the first thing
`magi next` asks a new workspace to do. Attaching a line was accepted only at
creation, so one forgetful moment made a note permanently uncountable. And
`decide` had an endpoint that nothing in the browser ever called, which is the
same wall with extra steps.

This file is the criterion written down. It is deliberately about reachability
rather than rendering: what it can prove is that the door exists and opens.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from magi.core import vocab
from magi.kb import threads
from magi.ui.api import create_app

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "src" / "magi" / "ui" / "static" / "app.js"


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "cfg"))
    root = tmp_path / "topic"
    for sub in ("threads", "inbox", "output", "drafts", "raw/papers", "wiki"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text("research:\n  coaching: light\n",
                                      encoding="utf-8")
    return root


@pytest.fixture
def client(ws):
    client = TestClient(create_app())
    client.ws = ws
    return client


def _post(client, path, **payload):
    payload.setdefault("workspace", str(client.ws))
    return client.post(path, json=payload)


def _get(client, path, **params):
    params.setdefault("workspace", str(client.ws))
    return client.get(path, params=params)


# --------------------------------------------------------------------------
# the whole loop, browser only
# --------------------------------------------------------------------------

def test_a_person_can_run_the_loop_without_a_terminal(client):
    """Open a line, open a claim on it, argue it, decide it, end the line —
    every step through the API the browser uses, and no other."""
    assert _post(client, "/api/workspace/thread/new", kind=vocab.LINE,
                 title="反常量子霍尔", purpose="零场下能不能量子化",
                 slug="qah").status_code == 200

    made = _post(client, "/api/workspace/thread/new", kind=vocab.PROPOSITION,
                 title="能隙在 30K 以上仍开", purpose="决定要不要做一个月数值",
                 slug="p-gap", lines=["qah"])
    assert made.status_code == 200, made.text

    assert _post(client, "/api/workspace/thread/post", slug="p-gap",
                 text="跑了 12x12 的 DMRG").status_code == 200
    assert _post(client, "/api/workspace/thread/status", slug="p-gap",
                 dst="testing", text="开始扫参数").status_code == 200
    assert _post(client, "/api/workspace/thread/status", slug="p-gap",
                 dst="supported", text="35K 仍有 4.2 meV").status_code == 200

    decided = _post(client, "/api/workspace/decide", about="p-gap",
                    text="我看过数据,认这条", bet="supported")
    assert decided.status_code == 200, decided.text
    assert "p-gap" in (client.ws / "decisions.md").read_text(encoding="utf-8")

    ended = _post(client, "/api/workspace/line/close", line="qah",
                  text="结论拿到了", anyway=True)
    assert ended.status_code == 200, ended.text
    assert threads.read_note(client.ws / "threads" / "qah.md").status == "closed"


def test_the_closing_ceremony_shows_what_it_would_silence_first(client):
    """`close_cmd` exists for the survey, not the flip: closing a line with
    three open propositions is a decision about those three, and somebody who
    has not been shown them has not made it. The browser gets the same answer
    before it presses, not as a rejection afterwards."""
    _post(client, "/api/workspace/thread/new", kind=vocab.LINE, title="L",
          purpose="why", slug="qah")
    _post(client, "/api/workspace/thread/new", kind=vocab.PROPOSITION, title="P",
          purpose="why", slug="p-open", lines=["qah"])

    found = _get(client, "/api/workspace/line/close", line="qah").json()
    assert [i["slug"] for i in found["open"]] == ["p-open"]

    refused = _post(client, "/api/workspace/line/close", line="qah", text="done")
    assert refused.status_code == 409, "it closed over open work without being told twice"


def test_a_line_forgotten_at_creation_can_be_attached_afterwards(client):
    """`--line` was accepted only at creation, so one forgetful moment made a
    note permanently uncountable toward its own line — the count was wrong and
    nothing in the system could repair it."""
    _post(client, "/api/workspace/thread/new", kind=vocab.LINE, title="L",
          purpose="why", slug="qah")
    _post(client, "/api/workspace/thread/new", kind=vocab.PROPOSITION, title="P",
          purpose="why", slug="p-gap")

    assert _get(client, "/api/workspace/line/close", line="qah").json()["open"] == []

    fixed = _post(client, "/api/workspace/thread/line", slug="p-gap",
                  lines=["qah"], text="开的时候漏了")
    assert fixed.status_code == 200, fixed.text

    after = _get(client, "/api/workspace/line/close", line="qah").json()
    assert [i["slug"] for i in after["open"]] == ["p-gap"]


def test_publishing_is_reachable_and_says_what_it_buries(client):
    """§6's other ceremony. `superseded` is terminal, so the survey comes
    first here too."""
    _post(client, "/api/workspace/thread/new", kind=vocab.LINE, title="L",
          purpose="why", slug="qah")
    _post(client, "/api/workspace/thread/new", kind=vocab.PROPOSITION, title="P",
          purpose="why", slug="p-gap", lines=["qah"])
    (client.ws / "drafts" / "our-paper.md").write_text("# What we found\n",
                                                       encoding="utf-8")

    assert "drafts/our-paper.md" in _get(client, "/api/workspace/papers").json()["papers"]

    found = _get(client, "/api/workspace/publish",
                 paper="drafts/our-paper.md", line="qah").json()
    assert [i["slug"] for i in found["supersede"]] == ["p-gap"]

    done = _post(client, "/api/workspace/publish", paper="drafts/our-paper.md",
                 lines=["qah"], text="这篇报告的就是它", anyway=True)
    assert done.status_code == 200, done.text
    assert (client.ws / "raw" / "papers" / "our-paper.md").is_file()
    assert threads.read_note(client.ws / "threads" / "p-gap.md").status == "superseded"


def test_publishing_cannot_reach_outside_the_workspace(client, tmp_path):
    """It copies into `raw/`, which this system treats as immutable truth, so
    "any path a request mentions" is not something this accepts.

    The file outside has to **exist**: a name that is merely absent is refused
    by the not-found check and says nothing about the boundary. The first
    version of this test used `../../../etc/passwd`, which does not exist on
    the machine it runs on, and passed with the boundary check deleted.
    """
    _post(client, "/api/workspace/thread/new", kind=vocab.LINE, title="L",
          purpose="why", slug="qah")
    outside = tmp_path / "not-ours.md"
    outside.write_text("# somebody else's\n", encoding="utf-8")
    escape = os.path.relpath(outside, client.ws)

    res = _get(client, "/api/workspace/publish", paper=escape, line="qah")

    assert res.status_code == 400
    assert "outside this workspace" in res.json()["detail"]


def test_a_note_id_is_canonical_or_refused(client):
    """A slug becomes a filename. `P Gap` and `p-gap` would be two notes about
    one claim, and `../p-gap` would write outside `threads/`."""
    ok = _post(client, "/api/workspace/thread/new", kind=vocab.PROPOSITION,
               title="The gap survives", purpose="why")
    assert ok.status_code == 200
    assert ok.json()["slug"] == "the-gap-survives"

    again = _post(client, "/api/workspace/thread/new", kind=vocab.PROPOSITION,
                  title="The gap survives", purpose="why")
    assert again.status_code == 409, "two notes about one claim"


# --------------------------------------------------------------------------
# and the doors are wired to something
# --------------------------------------------------------------------------

#: Endpoint -> the identifier in app.js that must reach it. An endpoint the
#: browser never calls is the same wall as a missing endpoint, with extra
#: steps — which is exactly what `/api/workspace/decide` was.
WIRED = {
    "/api/workspace/thread/new": "openNote",
    "/api/workspace/thread/line": "setThreadLines",
    "/api/workspace/line/close": "closeLineFlow",
    "/api/workspace/publish": "publishFlow",
    "/api/workspace/decide": "recordDecision",
    "/api/workspace/review": "askForReview",
    "/api/workspace/inbox": "loadInbox",
}


@pytest.mark.parametrize("path,handler", sorted(WIRED.items()))
def test_the_browser_actually_calls_it(path, handler):
    js = APP_JS.read_text(encoding="utf-8", errors="replace")
    assert path in js, f"nothing in the browser calls {path}"
    assert f"function {handler}(" in js, f"{handler} is gone"


# --------------------------------------------------------------------------
# and the doors do not open onto a modal
# --------------------------------------------------------------------------

def test_no_ceremony_asks_through_a_native_dialog():
    """Clicking "end this line" left the tab unresponsive for forty seconds
    with no toast and no change — `window.prompt`. Native dialogs block the
    render thread and are invisible to anything driving the page.

    The design failure under the freeze is the worse half: `closeLineFlow`
    rendered "closing this means these 3 are never mentioned again" into the
    panel and then opened a modal *over it* to ask for the reason. `close_cmd`
    exists so somebody sees what they are about to silence before deciding;
    putting that list behind the dialog that asks for the decision undoes it,
    on every browser, working or not.

    `window.confirm` survives in exactly one place — applying a version
    upgrade — where there is nothing behind the dialog to read and the
    question really is yes or no.
    """
    js = APP_JS.read_text(encoding="utf-8", errors="replace")

    # Calls, not mentions: the comment above `inlineConfirm` names both of
    # these, and the first version of this test counted that comment.
    assert "window.prompt(" not in js, (
        "a ceremony is asking through a modal again")
    assert js.count("window.confirm(") <= 1, (
        "a second native confirm appeared; the ceremonies use inlineConfirm")
    assert "function inlineConfirm(" in js


def test_a_draft_can_be_written_in_the_browser(client):
    """Publishing was reachable and its input was not: pressing it answered
    "no .md in drafts/ or output/ — put the write-up there first", which is a
    terminal instruction wearing a button."""
    made = _post(client, "/api/workspace/draft", title="What we found",
                 body="The gap stays open to 35K.")

    assert made.status_code == 200, made.text
    assert made.json()["path"] == "drafts/what-we-found.md"
    assert (client.ws / "drafts" / "what-we-found.md").read_text(
        encoding="utf-8").startswith("# What we found")
    assert "drafts/what-we-found.md" in _get(client, "/api/workspace/papers").json()["papers"]


def test_a_draft_needs_a_title_and_some_text(client):
    assert _post(client, "/api/workspace/draft", title="", body="x").status_code == 400
    assert _post(client, "/api/workspace/draft", title="T", body="  ").status_code == 400


def test_the_inbox_listing_skips_this_programs_own_lock_files(client):
    """`notes.md.lock` appeared in "3 files sitting in inbox/" as though it
    were something to ingest."""
    (client.ws / "inbox" / "notes.md.lock").write_text("", encoding="utf-8")
    (client.ws / "inbox" / "real.md").write_text("x", encoding="utf-8")

    payload = _get(client, "/api/workspace/inbox").json()

    assert [f["name"] for f in payload["files"]] == ["real.md"]
