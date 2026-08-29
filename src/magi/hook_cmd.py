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

#: When counting starts being worth saying out loud. Not a limit — nothing is
#: refused at any number. It is the point past which "how many so far" stops
#: being obvious to whoever is watching.
LOUD_AT = 10

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


def spawns(root, session: str) -> int:
    """How many sub-agents this session has started so far."""
    path = Path(root).joinpath(*FANOUT)
    if not path.is_file():
        return 0
    seen = 0
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
                if isinstance(row, dict) and row.get("session") == session:
                    seen += 1
    except OSError:
        return 0
    return seen


def note_spawn(root, session: str, tool: str, when=None) -> int:
    """Record one spawn and return the running count for this session."""
    from filelock import FileLock

    path = Path(root).joinpath(*FANOUT)
    row = {"at": (when or dt.datetime.now(dt.timezone.utc)).isoformat(
               timespec="seconds"),
           "session": session, "tool": tool}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = path.with_name(path.name + ".lock")
        # Windows `O_APPEND` is not atomic, and a fan-out is by definition
        # several writers at once — the one situation where an interleaved
        # line would be written.
        with FileLock(str(lock), timeout=10):
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:      # noqa: BLE001 — a lost count is not a lost session
        return spawns(root, session)
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
    if count < LOUD_AT:
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
    parser.add_argument("--topic-dir", help="Workspace (default: discovered)")
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
