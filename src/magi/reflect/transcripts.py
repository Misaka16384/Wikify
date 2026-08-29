"""Five hosts, four formats, one shape.

Every adapter answers the same question — *which sessions worked in this
workspace, and what was said in them* — and each one reads a format we do not
control and cannot ask to change. qwen-code is a fork of the Gemini CLI and
keeps its chats the same way, so that adapter is the same reader pointed at
`~/.qwen`. The rules are the same for all of them:

**Read-only.** A transcript belongs to the host that wrote it. Nothing here
opens a file for writing, and the SQLite adapter opens its database in `mode=ro`
so a bug cannot take a lock on somebody's live session.

**Fail-soft, per host.** A host that is not installed, whose directory does not
exist, whose file is half-written or whose schema moved yields nothing and says
so. Five adapters means five chances to be broken, and a slow loop that refuses
to run because one vendor changed a key is a slow loop that never runs. The
failures are collected and reported rather than raised: "codex could not be
read" is information, and dying is not.

**Joined by directory, not by name.** A session belongs to a workspace when its
working directory is inside it. Every format carries that somewhere — Claude
Code in each line's `cwd`, Codex in its `session_meta`, Gemini in the
`.project_root` beside the chats, opencode in a column — and matching on the
encoded directory *name* instead would be matching on a lossy encoding of the
thing we actually have.

**Truncated on the way out, not on the way in.** A transcript is read whole and
cut when it is handed to a model, because the cut belongs to the caller's
budget rather than to the parser.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

#: Every host MAGI knows how to read — "whose record can we make sense of?".
#: The names match `review.HOSTS` so a verdict and a transcript can be talked
#: about in the same words. Reading a host is not the same as installing into
#: it or calling it headless: `skills_cmd.HOSTS` and `review.HOSTS` answer
#: those, and each list is as long as what has actually been implemented.
HOSTS = ("claude", "codex", "gemini", "qwen", "opencode")

#: How much of one session a model is shown. From the design's sampling rule
#: (§12): enough to see what happened, small enough that eight of them fit.
EXCERPT_CHARS = 15000


@dataclass
class Turn:
    """One thing said, by one side."""
    role: str          # "user" | "assistant" | "tool" | "system"
    at: str            # ISO-8601, or "" when the format does not stamp it
    text: str


@dataclass
class Session:
    """One conversation, in one directory, on one host."""
    host: str
    session_id: str
    cwd: str
    path: str          # where it was read from, so a finding can cite it
    started: str = ""
    ended: str = ""
    turns: list = field(default_factory=list)

    @property
    def user_turns(self) -> list:
        return [turn for turn in self.turns if turn.role == "user"]

    def excerpt(self, limit: int = EXCERPT_CHARS) -> str:
        """The conversation as text, cut to `limit` from the **end**.

        The end, because that is where a session says how it went: what was
        tried last, what failed, what the person said about it. Cutting from
        the front keeps the setup and throws away the outcome.
        """
        lines = [f"{turn.role}: {turn.text}".strip() for turn in self.turns
                 if (turn.text or "").strip()]
        body = "\n\n".join(lines)
        if len(body) <= limit:
            return body
        return "…\n\n" + body[-limit:]


@dataclass
class Sweep:
    """What one pass over the hosts found, and what it could not read."""
    sessions: list = field(default_factory=list)
    unreadable: dict = field(default_factory=dict)   # host -> why


# ---------------------------------------------------------------- helpers


def _home() -> Path:
    return Path.home()


def _inside(candidate: str, root: Path) -> bool:
    """Is `candidate` the workspace or a directory under it?

    Compared as resolved paths rather than as strings: on Windows the same
    directory is spelled several ways (`D:\\x` vs `d:/x`), and on macOS a
    workspace under `/tmp` resolves through a symlink.
    """
    if not candidate:
        return False
    try:
        here = Path(candidate).resolve()
        there = Path(root).resolve()
    except (OSError, ValueError):
        return False
    return here == there or there in here.parents


def _text_of(content) -> str:
    """The words in a message, whatever shape the host stores them in.

    A string, a list of blocks, or a block dict — all four hosts use at least
    two of these, and a tool-use block has no text at all.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return str(content.get("text") or "")
    if isinstance(content, list):
        parts = [_text_of(item) for item in content]
        return "\n".join(part for part in parts if part)
    return ""


def _iso(value) -> str:
    """A timestamp as ISO-8601, from a string or an epoch in s/ms."""
    if isinstance(value, (int, float)) and value > 0:
        seconds = value / 1000 if value > 1e11 else value
        try:
            return dt.datetime.fromtimestamp(
                seconds, dt.timezone.utc).isoformat(timespec="seconds")
        except (OverflowError, OSError, ValueError):
            return ""
    return str(value or "")


def _lines(path: Path):
    """JSON objects from a JSONL file, skipping what will not parse.

    A live session is being appended to while this reads it, so the last line
    is routinely half-written. That is not a corrupt file, and refusing to read
    the other ten thousand lines because of it would mean never reading an
    active session at all.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                yield parsed


# ---------------------------------------------------------------- claude


def claude_sessions(root, home=None) -> list:
    """`~/.claude/projects/<slug>/<session>.jsonl`.

    The directory name is the working directory with its separators replaced,
    which is lossy — two different paths can encode to the same name. So the
    name only narrows the search and each line's own `cwd` decides.
    """
    base = (home or _home()) / ".claude" / "projects"
    if not base.is_dir():
        return []
    out = []
    for folder in sorted(base.iterdir()):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.jsonl")):
            session = _claude_one(path)
            if session and _inside(session.cwd, root):
                out.append(session)
    return out


def _claude_one(path: Path):
    session = Session(host="claude", session_id=path.stem, cwd="", path=str(path))
    for row in _lines(path):
        session.cwd = session.cwd or str(row.get("cwd") or "")
        session.session_id = str(row.get("sessionId") or session.session_id)
        kind = row.get("type")
        if kind not in ("user", "assistant"):
            continue
        message = row.get("message")
        if not isinstance(message, dict):
            continue
        text = _text_of(message.get("content"))
        stamp = str(row.get("timestamp") or "")
        session.started = session.started or stamp
        session.ended = stamp or session.ended
        if text.strip():
            session.turns.append(Turn(role=str(message.get("role") or kind),
                                      at=stamp, text=text))
    return session if session.turns else None


# ----------------------------------------------------------------- codex


def codex_sessions(root, home=None) -> list:
    """`~/.codex/sessions/<yyyy>/<mm>/<dd>/rollout-*.jsonl`."""
    base = (home or _home()) / ".codex" / "sessions"
    if not base.is_dir():
        return []
    out = []
    for path in sorted(base.rglob("rollout-*.jsonl")):
        session = _codex_one(path)
        if session and _inside(session.cwd, root):
            out.append(session)
    return out


def _codex_one(path: Path):
    session = Session(host="codex", session_id=path.stem, cwd="", path=str(path))
    for row in _lines(path):
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("cwd"):
            session.cwd = session.cwd or str(payload["cwd"])
        if payload.get("session_id"):
            session.session_id = str(payload["session_id"])
        stamp = _iso(row.get("timestamp") or payload.get("timestamp"))
        # `response_item/message` is the conversation. Reasoning blocks, tool
        # calls and token counts are the machinery around it.
        if row.get("type") == "response_item" and payload.get("type") == "message":
            text = _text_of(payload.get("content"))
            if text.strip():
                session.started = session.started or stamp
                session.ended = stamp or session.ended
                session.turns.append(Turn(role=str(payload.get("role") or "assistant"),
                                          at=stamp, text=text))
    return session if session.turns else None


# ---------------------------------------------------------------- gemini


def gemini_sessions(root, home=None) -> list:
    """`~/.gemini/tmp/<project>/chats/session-*.json`.

    The sibling `.project_root` holds the real directory. `projectHash` in the
    chat file is not a hash of any path we could reproduce, so the file beside
    it is the join — and where that file is missing, the session is skipped
    rather than guessed at.
    """
    return _gemini_shaped(root, ".gemini", "gemini", home=home)


def qwen_sessions(root, home=None) -> list:
    """`~/.qwen/tmp/<project>/chats/session-*.json`.

    qwen-code is a fork of the Gemini CLI, so it is the same reader pointed at
    a different directory. **Unverified against a real install** — there was no
    `~/.qwen` on the machine this was written on, so what is claimed here is
    the fork's inheritance, not a measurement. If the layout differs, this
    yields nothing, which is the failure every adapter in this file is built
    to have.
    """
    return _gemini_shaped(root, ".qwen", "qwen", home=home)


def _gemini_shaped(root, dirname: str, host: str, home=None) -> list:
    base = (home or _home()) / dirname / "tmp"
    if not base.is_dir():
        return []
    out = []
    for folder in sorted(base.iterdir()):
        marker = folder / ".project_root"
        chats = folder / "chats"
        if not (marker.is_file() and chats.is_dir()):
            continue
        try:
            cwd = marker.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if not _inside(cwd, root):
            continue
        for path in sorted(chats.glob("*.json")):
            session = _gemini_one(path, cwd, host=host)
            if session:
                out.append(session)
    return out


def _gemini_one(path: Path, cwd: str, host: str = "gemini"):
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    session = Session(host=host, session_id=str(data.get("sessionId") or path.stem),
                      cwd=cwd, path=str(path),
                      started=str(data.get("startTime") or ""),
                      ended=str(data.get("lastUpdated") or ""))
    for message in data.get("messages") or []:
        if not isinstance(message, dict):
            continue
        text = _text_of(message.get("content"))
        if text.strip():
            session.turns.append(Turn(role=str(message.get("type") or "user"),
                                      at=str(message.get("timestamp") or ""),
                                      text=text))
    return session if session.turns else None


# -------------------------------------------------------------- opencode


#: opencode keeps its history in SQLite rather than in files. Opened read-only
#: through a URI so a reader can never take a write lock on a live session.
OPENCODE_DB = (".local", "share", "opencode", "opencode.db")


def opencode_sessions(root, home=None) -> list:
    db = (home or _home()).joinpath(*OPENCODE_DB)
    if not db.is_file():
        return []
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    conn.row_factory = sqlite3.Row
    out = []
    try:
        rows = conn.execute(
            "SELECT id, directory, path, title, time_created, time_updated "
            "FROM session ORDER BY time_created").fetchall()
        for row in rows:
            cwd = str(row["directory"] or row["path"] or "")
            if not _inside(cwd, root):
                continue
            session = Session(host="opencode", session_id=str(row["id"]), cwd=cwd,
                              path=str(db), started=_iso(row["time_created"]),
                              ended=_iso(row["time_updated"]))
            for message in conn.execute(
                    "SELECT data, time_created FROM message WHERE session_id = ? "
                    "ORDER BY time_created", (row["id"],)).fetchall():
                turn = _opencode_turn(message)
                if turn:
                    session.turns.append(turn)
            if session.turns:
                out.append(session)
    except sqlite3.Error:
        return out
    finally:
        conn.close()
    return out


def _opencode_turn(row):
    try:
        data = json.loads(row["data"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    text = _text_of(data.get("content") or data.get("text") or data.get("parts"))
    if not text.strip():
        return None
    return Turn(role=str(data.get("role") or "assistant"),
                at=_iso(row["time_created"]), text=text)


# ------------------------------------------------------------------ sweep


ADAPTERS = {
    "claude": claude_sessions,
    "codex": codex_sessions,
    "gemini": gemini_sessions,
    "qwen": qwen_sessions,
    "opencode": opencode_sessions,
}


def sweep(root, home=None, hosts=None) -> Sweep:
    """Every session any host recorded in this workspace.

    One broken host does not stop the others: what it could not read is
    reported alongside what the rest found. Four adapters over four formats we
    do not control means four chances to be broken, and a slow loop that
    refuses to run because one vendor renamed a key is a slow loop that never
    runs.
    """
    result = Sweep()
    for name in (hosts or HOSTS):
        adapter = ADAPTERS.get(name)
        if adapter is None:
            continue
        try:
            result.sessions.extend(adapter(root, home=home))
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            result.unreadable[name] = f"{exc.__class__.__name__}: {exc}"
    result.sessions.sort(key=lambda session: (session.ended or session.started or "",
                                              session.host, session.session_id))
    return result
