"""What MAGI's own model calls cost, and the gate that says no.

Every call MAGI starts itself — a review, a reflect pass — is written down
where a person can see what their week has spent. Nothing else in the system
spends money without being asked, and this file is what makes that checkable
rather than believed.

**The unit is calls, not dollars.** A headless CLI does not reliably say what a
request cost, and a budget denominated in a number nobody can measure is a
budget that quietly does nothing. Calls are countable, and the one thing a
budget has to be able to do is refuse.

**MAGI only accounts for what MAGI starts.** A person's own agent session is
not in here and could not be: MAGI never sees it. Counting a guess at it would
make every number in the file a guess.

Same shape as every other ledger in this repo (`seen.jsonl`, `triage.jsonl`,
`ui-jobs.jsonl`): append-only JSONL under a lock. It survives a restart because
it is a file, and nothing is rewritten in place, so a crash mid-write cannot
corrupt what came before.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

#: Under `output/`, which is derived. The ledger is a record of what was spent,
#: not content anybody edits.
LEDGER = ("output", "llm-ledger.jsonl")

#: Calls per calendar week before the gate refuses. Weeks, not a rolling
#: window: "you have twelve left until Monday" is something a person can plan
#: around, and a rolling window refuses on a Tuesday for something that
#: happened eight days ago.
DEFAULT_WEEKLY = 40

#: Kinds of call, so the ledger can say where a week went.
REVIEW = "review"
REFLECT = "reflect"
KINDS = (REVIEW, REFLECT)

#: How long to wait for the append lock. Same reasoning as `threads.py`: a
#: ten-second wait means something is wrong with the lock, not with the write.
APPEND_TIMEOUT = 30.0


def week_of(when: dt.datetime) -> str:
    """The ISO week a moment falls in, as `2026-W35`."""
    year, week, _ = when.isocalendar()
    return f"{year}-W{week:02d}"


def path_for(root) -> Path:
    return Path(root).joinpath(*LEDGER)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_at(stamp):
    """A record's timestamp, or `None` when it is unreadable."""
    if not stamp:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def record(root, kind: str, host: str, *, model: str | None = None,
           effort: str | None = None, slug: str | None = None, ok: bool = True,
           seconds: float | None = None, note: str = "", when=None) -> dict:
    """Append one call. Returns the record written.

    `effort` is recorded next to `model` because it is the other half of what
    was asked for: the same review at `high` and at `low` is not the same call,
    and a budget that cannot tell them apart cannot explain itself afterwards.
    """
    from filelock import FileLock

    entry = {
        "at": (when or _now()).isoformat(timespec="seconds"),
        "kind": kind,
        "host": host,
        "model": model,
        "effort": effort,
        "slug": slug,
        "ok": bool(ok),
        "seconds": round(seconds, 1) if seconds is not None else None,
        "note": note,
    }
    path = path_for(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    with FileLock(str(lock), timeout=APPEND_TIMEOUT):
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def entries(root) -> list:
    """Every record, oldest first.

    A line that will not parse is skipped rather than fatal: this file is the
    thing a budget gate reads, and a gate that crashes on one bad line is a
    gate that stops every review in the workspace.
    """
    out: list = []
    try:
        text = path_for(root).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def spent(root, when=None, kind: str | None = None) -> int:
    """Calls this calendar week. **Failed calls count.**

    A call that timed out still spent the wall clock and, on a metered account,
    the money. Not counting it is how a broken adapter becomes a way to burn a
    week's budget in an afternoon.
    """
    week = week_of(when or _now())
    total = 0
    for entry in entries(root):
        if kind and entry.get("kind") != kind:
            continue
        stamp = parse_at(entry.get("at"))
        if stamp is not None and week_of(stamp) == week:
            total += 1
    return total


class OverBudget(RuntimeError):
    """The week's calls are spent. Carries the sentence to show a person."""

    def __init__(self, spent_: int, limit: int, until: str) -> None:
        self.spent, self.limit, self.until = spent_, limit, until
        super().__init__(
            f"this week's model budget is spent ({spent_}/{limit}) — "
            f"it refills {until}. Nothing was called, and nothing counts as "
            "reviewed.")


class SwitchedOff(RuntimeError):
    """The master switch is off."""

    def __init__(self) -> None:
        super().__init__(
            "MAGI's own model calls are switched off (`research.llm_calls: off`). "
            "Nothing was called, and nothing counts as reviewed.")


def next_monday(when=None) -> str:
    when = when or _now()
    days = 7 - when.isoweekday() + 1
    return (when + dt.timedelta(days=days)).date().isoformat()


def check(root, limit: int | None = None, enabled: bool = True, when=None) -> None:
    """Raise if this call may not happen. Silence means go ahead.

    Refusing is the whole point of the file, so it is one call at the top of
    anything that spends: over budget and switched off both stop *before* the
    subprocess, and both say the same last sentence — nothing counts as
    reviewed. A budget that let a claim retire unreviewed would be worse than
    no budget.
    """
    if not enabled:
        raise SwitchedOff()
    limit = DEFAULT_WEEKLY if limit is None else limit
    # Counted before either refusal, so both report the same true number. A
    # limit of zero used to be reported as "spent (0/0)" in a workspace that
    # had already made twelve calls, which reads as a fresh week rather than
    # as a switch somebody turned off.
    used = spent(root, when=when)
    if limit <= 0 or used >= limit:
        raise OverBudget(used, limit, next_monday(when))


def summary(root, limit: int | None = None, when=None) -> dict:
    """What the week has cost, for `MAP.md` and the dashboard.

    One pass. The obvious spelling — `spent()` for the total and `spent()`
    again per kind — read and re-parsed the whole file once per kind plus
    once more, for a number that is a tally of the same rows. `magi map` and
    the dashboard both call this on every render.
    """
    limit = DEFAULT_WEEKLY if limit is None else limit
    week = week_of(when or _now())
    used = 0
    by_kind = {kind: 0 for kind in KINDS}
    for entry in entries(root):
        stamp = parse_at(entry.get("at"))
        if stamp is None or week_of(stamp) != week:
            continue
        used += 1
        kind = entry.get("kind")
        if kind in by_kind:
            by_kind[kind] += 1
    return {
        "week": week,
        "spent": used,
        "limit": limit,
        "left": max(0, limit - used),
        "over": used >= limit,
        "until": next_monday(when),
        "by_kind": by_kind,
    }
