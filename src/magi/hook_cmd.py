"""`magi hook <event>` — what a host's hooks call, and all it may do.

Two hooks beyond the stop gate, both on Claude Code because it is the only
host that documents any of this (design-v2 §13: "other hosts have none").

**`fanout`** counts sub-agent spawns and never blocks one. Invariant 5 in the
managed block asks the agent to say what a fan-out costs before it starts one,
and a rule that the agent alone enforces is a rule that quietly stops holding
in the sessions where it matters most. Counting makes it checkable. Blocking
would make it a budget, and design-v2 §13 is explicit that MAGI hard-manages
only the calls it starts itself — a sub-agent is the agent's own work on the
person's own account, and refusing it is not MAGI's call.

**`session-start`** is where background work happens, because §7 says there is
no daemon: everything except the radar runs when a session begins. It prints
what `magi next` would print, which is the one thing worth knowing at that
moment, and it prints nothing when there is nothing — a hook that speaks every
time teaches people to skip it.

**A hook must not be able to break a session.** Every path here ends in exit 0
with parseable JSON on stdout, including the paths where the workspace is
missing, the payload is not JSON, or a file cannot be written. A hook that
errors is a hook the person turns off, and then the gate it guarded is gone.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from .core.workspace import find_workspace_root

#: One line per sub-agent spawn. Deliberately not `llm-ledger.jsonl`: that
#: counts what MAGI spent and enforces a weekly budget against it, and mixing
#: in calls MAGI did not make would corrupt the one number the budget reads.
FANOUT = ("output", "fanout.jsonl")

#: How often the count is worth saying out loud — every Nth spawn, not every
#: spawn past an Nth. Not a limit: nothing is refused at any number.
#:
#: Twenty-five because the skills cap a fan-out at ten concurrent and require
#: the agent to announce the total first, so a compile of a dozen sources is
#: normal, announced and correct. A counter that fired there would be warning
#: about the one workflow that had already done what it was reminding about.
#: Past twenty-five nobody announced anything, or the announcement was wrong.
LOUD_EVERY = 25

#: Tools that spawn a sub-agent, by the names hosts actually use.
SPAWNING = ("Task", "Agent", "Dispatch")


def _payload(stream=None) -> dict:
    """The hook's JSON on stdin, or `{}`.

    Anything unparseable is `{}` rather than an error: this runs inside
    somebody's editor session, and the worst outcome is not a missed count.
    """
    try:
        raw = (stream or sys.stdin).read()
    except (OSError, ValueError):
        return {}
    try:
        parsed = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _root(explicit=None):
    if explicit:
        return Path(explicit)
    try:
        return find_workspace_root()
    except Exception:      # noqa: BLE001 — a hook has no business raising
        return None


#: Rows in `fanout.jsonl` before a write also tidies it. High enough that a
#: normal week never reaches it, low enough that the file cannot become
#: something the hook is slow to read.
PRUNE_AT = 2000

#: How far back a row is still worth keeping. The only question this file
#: answers is "how many so far *this session*", and no session is a week old.
KEEP_FOR = dt.timedelta(days=7)


def _rows(path: Path) -> list:
    """Every parseable row in the log. Unparseable lines are skipped, not
    fatal: a truncated write must cost one row, never the count."""
    if not path.is_file():
        return []
    out = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
    except OSError:
        return []
    return out


def _still_worth_keeping(rows: list, now) -> list:
    """Rows inside the retention window. A row with no readable timestamp is
    kept: dropping what we cannot date would quietly lose a live session."""
    cutoff = now - KEEP_FOR
    kept = []
    for row in rows:
        try:
            at = dt.datetime.fromisoformat(str(row.get("at") or "").replace("Z", "+00:00"))
        except ValueError:
            kept.append(row)
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=dt.timezone.utc)
        if at >= cutoff:
            kept.append(row)
    return kept


def _rewrite(path: Path, rows: list) -> None:
    """Replace the log with `rows`. Called holding the lock."""
    body = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(body, encoding="utf-8", newline="\n")
    tmp.replace(path)


def spawns(root, session: str) -> int:
    """How many sub-agents this session has started so far."""
    return sum(1 for row in _rows(Path(root).joinpath(*FANOUT))
               if row.get("session") == session)


def note_spawn(root, session: str, tool: str, when=None) -> int:
    """Record one spawn and return the running count for this session.

    Counted from the rows this call already read, inside the lock it already
    holds. Appending and then calling `spawns()` opened the file a second
    time, outside the lock, on a hook that runs once per sub-agent.

    Pruned here too, for want of anywhere else. `output/fanout.jsonl` is
    DERIVED — it exists to answer "how many so far this session" and nothing
    reconstructs anything from it — so a row older than the retention window
    is not history, it is a file that grows forever on a path that reads the
    whole thing every time.
    """
    from filelock import FileLock

    now = when or dt.datetime.now(dt.timezone.utc)
    path = Path(root).joinpath(*FANOUT)
    row = {"at": now.isoformat(timespec="seconds"), "session": session, "tool": tool}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = path.with_name(path.name + ".lock")
        # Windows `O_APPEND` is not atomic, and a fan-out is by definition
        # several writers at once — the one situation where an interleaved
        # line would be written.
        with FileLock(str(lock), timeout=10):
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows = _rows(path)
            if len(rows) > PRUNE_AT:
                kept = _still_worth_keeping(rows, now)
                if len(kept) < len(rows):
                    _rewrite(path, kept)
                    rows = kept
            return sum(1 for item in rows if item.get("session") == session)
    except Exception:      # noqa: BLE001 — a lost count is not a lost session
        return spawns(root, session)


def fanout(payload: dict, root=None) -> dict:
    """Count one spawn. Returns what the hook prints — never a block."""
    tool = str(payload.get("tool_name") or "")
    if tool not in SPAWNING:
        return {}
    root = _root(root)
    if root is None:
        return {}
    session = str(payload.get("session_id") or "unknown")
    count = note_spawn(root, session, tool)
    # Every twenty-fifth, not every one past the twenty-fifth. Saying it each
    # time is how a hook becomes noise, and a hook that is noise gets removed
    # along with the gate beside it.
    if not count or count % LOUD_EVERY:
        return {}
    # `systemMessage` reaches the agent without stopping it. Invariant 5 asks
    # it to say what a fan-out costs; past this many it plainly has not, and
    # being told the number is more use than being stopped.
    return {"systemMessage":
            f"{count} sub-agents this session. Say what the rest will cost "
            f"before spawning them (managed block, invariant 5)."}


def session_start(payload: dict, root=None) -> dict:
    """What is worth knowing at the start of a session, and nothing else."""
    root = _root(root)
    if root is None:
        return {}
    try:
        from . import state as state_mod

        loaded = state_mod.loaded(root)
        actions = state_mod.candidates(loaded)
    except Exception:      # noqa: BLE001 — a hook has no business raising
        return {}
    if not actions:
        return {}
    top = actions[:3]
    said = "\n".join(f"- {action.why}\n  {action.run}" for action in top)
    more = len(actions) - len(top)
    if more > 0:
        said += f"\n({more} more: magi next)"
    return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext":
                                   "MAGI — what this workspace needs:\n" + said}}


EVENTS = {"fanout": fanout, "session-start": session_start}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi hook",
        description="Called by an agent CLI's hooks. Not for typing by hand.")
    parser.add_argument("event", choices=sorted(EVENTS))
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir", help="Workspace (default: discovered)")
    args = parser.parse_args(argv)

    try:
        answer = EVENTS[args.event](_payload(), root=args.topic_dir)
    except Exception:      # noqa: BLE001
        # The whole point: a hook that raises is a hook somebody removes, and
        # then the gate it was guarding is gone too.
        answer = {}
    print(json.dumps(answer, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
