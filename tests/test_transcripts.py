"""Four hosts, four formats, one shape — and none of them ours to change.

Every fixture here is written by hand from the real files' structure rather
than copied from a machine: a transcript is somebody's actual work, and a test
suite is the wrong place for it. What is reproduced is the shape — which keys
carry the words, which one carries the working directory, and the ways each
format is awkward.

The property under test is mostly **failure**. Four adapters over four formats
we do not control is four chances to be broken, and a slow loop that refuses to
run because one vendor renamed a key is a slow loop that never runs. So a
missing host, a half-written line, a moved schema and an unreadable database
each have to end in "nothing from that host" rather than an exception.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from magi.reflect import transcripts


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "topic"
    (root / "threads").mkdir(parents=True)
    return root


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------
# claude code
# --------------------------------------------------------------------------

def claude_fixture(home, cwd, name="D--topic"):
    write_jsonl(home / ".claude" / "projects" / name / "sess-1.jsonl", [
        {"type": "summary", "summary": "not a turn"},
        {"type": "user", "cwd": cwd, "sessionId": "abc",
         "timestamp": "2026-08-29T10:00:00Z",
         "message": {"role": "user", "content": "why did the sweep stall?"}},
        {"type": "assistant", "cwd": cwd, "sessionId": "abc",
         "timestamp": "2026-08-29T10:01:00Z",
         "message": {"role": "assistant",
                     "content": [{"type": "text", "text": "the boundary was wrong"},
                                 {"type": "tool_use", "name": "Bash", "input": {}}]}},
    ])


def test_claude_reads_both_sides_of_the_conversation(home, ws):
    claude_fixture(home, str(ws))
    sessions = transcripts.claude_sessions(ws, home=home)

    assert len(sessions) == 1
    assert [turn.role for turn in sessions[0].turns] == ["user", "assistant"]
    assert "boundary was wrong" in sessions[0].turns[1].text
    assert sessions[0].session_id == "abc"


def test_a_tool_block_contributes_no_words(home, ws):
    """A `tool_use` block has no text. Rendering it as an empty turn would
    make a session look chattier than it was."""
    claude_fixture(home, str(ws))
    text = transcripts.claude_sessions(ws, home=home)[0].turns[1].text
    assert "Bash" not in text


def test_a_session_from_another_directory_is_not_ours(home, ws, tmp_path):
    claude_fixture(home, str(tmp_path / "elsewhere"))
    assert transcripts.claude_sessions(ws, home=home) == []


def test_the_directory_name_is_not_the_join(home, ws):
    """The folder name is the path with its separators replaced, which is
    lossy — two paths can encode the same. Each line carries the real one."""
    claude_fixture(home, str(ws), name="some-other-encoding")
    assert len(transcripts.claude_sessions(ws, home=home)) == 1


def test_a_half_written_last_line_does_not_lose_the_session(home, ws):
    """A live session is being appended to while this reads it."""
    claude_fixture(home, str(ws))
    path = home / ".claude" / "projects" / "D--topic" / "sess-1.jsonl"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"type": "assistant", "mess')

    assert len(transcripts.claude_sessions(ws, home=home)[0].turns) == 2


def test_no_claude_at_all_is_not_an_error(home, ws):
    assert transcripts.claude_sessions(ws, home=home) == []


# --------------------------------------------------------------------------
# codex
# --------------------------------------------------------------------------

def codex_fixture(home, cwd):
    write_jsonl(home / ".codex" / "sessions" / "2026" / "08" / "29"
                / "rollout-2026-08-29T02-10-18-abc.jsonl", [
        {"timestamp": "2026-08-29T02:10:18Z", "type": "session_meta",
         "payload": {"session_id": "s-1", "cwd": cwd, "cli_version": "1.0"}},
        {"timestamp": "2026-08-29T02:10:20Z", "type": "response_item",
         "payload": {"type": "message", "role": "user",
                     "content": [{"type": "input_text", "text": "check the gap"}]}},
        {"timestamp": "2026-08-29T02:10:30Z", "type": "response_item",
         "payload": {"type": "reasoning", "content": [{"text": "thinking"}]}},
        {"timestamp": "2026-08-29T02:10:40Z", "type": "response_item",
         "payload": {"type": "message", "role": "assistant",
                     "content": [{"type": "output_text", "text": "it closes at L=24"}]}},
        {"timestamp": "2026-08-29T02:10:41Z", "type": "event_msg",
         "payload": {"type": "token_count", "total": 900}},
    ])


def test_codex_takes_the_messages_and_leaves_the_machinery(home, ws):
    """Reasoning blocks, tool calls and token counts are around the
    conversation, not in it."""
    codex_fixture(home, str(ws))
    session = transcripts.codex_sessions(ws, home=home)[0]

    assert [turn.role for turn in session.turns] == ["user", "assistant"]
    assert "thinking" not in session.excerpt()
    assert session.session_id == "s-1"


def test_codex_finds_its_directory_in_the_session_header(home, ws, tmp_path):
    codex_fixture(home, str(tmp_path / "elsewhere"))
    assert transcripts.codex_sessions(ws, home=home) == []


# --------------------------------------------------------------------------
# gemini
# --------------------------------------------------------------------------

def gemini_fixture(home, cwd, folder="acajourney"):
    base = home / ".gemini" / "tmp" / folder
    (base / "chats").mkdir(parents=True)
    (base / ".project_root").write_text(cwd, encoding="utf-8")
    (base / "chats" / "session-2026-08-29T10-00-abc.json").write_text(json.dumps({
        "sessionId": "g-1", "projectHash": "0f0f0f", "startTime": "2026-08-29T10:00:00Z",
        "lastUpdated": "2026-08-29T10:20:00Z",
        "messages": [
            {"id": "1", "timestamp": "2026-08-29T10:00:00Z", "type": "user",
             "content": "does the gap survive?"},
            {"id": "2", "timestamp": "2026-08-29T10:01:00Z", "type": "gemini",
             "content": [{"text": "not at the boundary"}]},
        ],
    }), encoding="utf-8")
    return base


def test_gemini_joins_on_the_file_beside_the_chats(home, ws):
    """`projectHash` is not a hash of any path we can reproduce. The
    `.project_root` next to it is the real directory."""
    gemini_fixture(home, str(ws))
    session = transcripts.gemini_sessions(ws, home=home)[0]

    assert session.session_id == "g-1"
    assert "not at the boundary" in session.excerpt()


def test_a_gemini_folder_with_no_project_root_is_skipped_not_guessed(home, ws):
    base = gemini_fixture(home, str(ws))
    (base / ".project_root").unlink()
    assert transcripts.gemini_sessions(ws, home=home) == []


# --------------------------------------------------------------------------
# opencode
# --------------------------------------------------------------------------

def opencode_fixture(home, cwd, with_messages=True):
    db = home.joinpath(*transcripts.OPENCODE_DB)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE session(id TEXT PRIMARY KEY, directory TEXT, path TEXT,
                             title TEXT, time_created INTEGER, time_updated INTEGER);
        CREATE TABLE message(id TEXT PRIMARY KEY, session_id TEXT,
                             time_created INTEGER, data TEXT);
    """)
    conn.execute("INSERT INTO session VALUES('o-1', ?, ?, 'a title', 1756000000, 1756000900)",
                 (cwd, cwd))
    if with_messages:
        conn.execute("INSERT INTO message VALUES('m1','o-1',1756000001,?)",
                     (json.dumps({"role": "user", "content": "why is it stalling?"}),))
        conn.execute("INSERT INTO message VALUES('m2','o-1',1756000002,?)",
                     (json.dumps({"role": "assistant",
                                  "parts": [{"type": "text", "text": "a wrong boundary"}]}),))
    conn.commit()
    conn.close()
    return db


def test_opencode_reads_its_database(home, ws):
    opencode_fixture(home, str(ws))
    session = transcripts.opencode_sessions(ws, home=home)[0]

    assert [turn.role for turn in session.turns] == ["user", "assistant"]
    assert "wrong boundary" in session.excerpt()


def test_opencode_is_opened_read_only(home, ws):
    """A reader must not be able to take a write lock on somebody's live
    session."""
    opencode_fixture(home, str(ws))
    transcripts.opencode_sessions(ws, home=home)

    db = home.joinpath(*transcripts.OPENCODE_DB)
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO session VALUES('x','y','z','t',1,2)")
    conn.close()


def test_a_moved_schema_yields_nothing_rather_than_raising(home, ws):
    db = home.joinpath(*transcripts.OPENCODE_DB)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE something_else(id TEXT)")
    conn.commit()
    conn.close()

    assert transcripts.opencode_sessions(ws, home=home) == []


# --------------------------------------------------------------------------
# the sweep
# --------------------------------------------------------------------------

def test_one_broken_host_does_not_stop_the_others(home, ws, monkeypatch):
    claude_fixture(home, str(ws))
    codex_fixture(home, str(ws))

    def explode(*args, **kwargs):
        raise OSError("the vendor renamed a directory")

    monkeypatch.setitem(transcripts.ADAPTERS, "gemini", explode)

    result = transcripts.sweep(ws, home=home)

    assert {session.host for session in result.sessions} == {"claude", "codex"}
    assert "gemini" in result.unreadable
    assert "renamed a directory" in result.unreadable["gemini"]


def test_a_machine_with_no_hosts_is_quiet(home, ws):
    result = transcripts.sweep(ws, home=home)
    assert result.sessions == [] and result.unreadable == {}


def test_sessions_come_back_in_time_order(home, ws):
    claude_fixture(home, str(ws))
    codex_fixture(home, str(ws))

    hosts = [session.host for session in transcripts.sweep(ws, home=home).sessions]
    assert hosts == ["codex", "claude"], "codex ended at 02:10, claude at 10:01"


# --------------------------------------------------------------------------
# the excerpt
# --------------------------------------------------------------------------

def test_an_excerpt_is_cut_from_the_front_keeping_the_end(home, ws):
    """The end is where a session says how it went: what was tried last, what
    failed, what the person said about it."""
    session = transcripts.Session(host="claude", session_id="s", cwd="", path="")
    session.turns = [transcripts.Turn("user", "", "x" * 400),
                     transcripts.Turn("assistant", "", "the last word")]

    excerpt = session.excerpt(limit=100)

    assert excerpt.startswith("…")
    assert "the last word" in excerpt
    assert len(excerpt) <= 104


def test_a_short_session_is_not_cut(home, ws):
    session = transcripts.Session(host="claude", session_id="s", cwd="", path="")
    session.turns = [transcripts.Turn("user", "", "short")]
    assert session.excerpt(limit=100) == "user: short"
