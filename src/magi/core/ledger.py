"""What MAGI's own model calls cost — a record, and one switch.

Every call MAGI starts itself — a review, a reflect pass — is written down
where a person can see what their week has spent, and with what: host, model,
effort, how long, whether it worked. Nothing else in the system spends money
without being asked, and this file is what makes that checkable rather than
believed.

**There is no budget.** There was one — forty calls a week, refused past the
fortieth — and the person using it cancelled it on 2026-09-03: everyone on a
token plan pays nothing per call, review turned out to be worth far more than
the number allowed for, and on the day it was cancelled four calls that failed
on a vendor's own quota were counted against it, so the budget was refusing
reviews because a *different* limit had been hit. A gate whose only measured
effect was to stop the thing it was protecting is not a gate worth keeping.
The one refusal left is the master switch (`research.llm_calls: false`),
because "MAGI may not call a model on its own" is a decision a person can
want for reasons that have nothing to do with money.

**The unit is calls, not dollars.** A headless CLI does not reliably say what a
request cost, and a count denominated in a number nobody can measure is a
count that quietly means nothing. Calls are countable.

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
           seconds: float | None = None, note: str = "", when=None,
           tier: str | None = None) -> dict:
    """Append one call. Returns the record written.

    `effort` is recorded next to `model` because it is the other half of what
    was asked for: the same review at `high` and at `low` is not the same call,
    and a record that cannot tell them apart cannot explain itself afterwards.
    `tier` says which of the host's named tiers the model was — `strong`,
    `cheap`, `pinned` or `default` — so a week's reviews can be read as "how
    many were real readers" without a table of model names.
    """
    from filelock import FileLock

    entry = {
        "at": (when or _now()).isoformat(timespec="seconds"),
        "kind": kind,
        "host": host,
        "model": model,
        "effort": effort,
        "tier": tier,
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

    A line that will not parse is skipped rather than fatal: this file is read
    on every `magi next` and every dashboard render, and a reader that crashes
    on one bad line takes the router down with it.
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
    the money. The number here is what happened, not what worked.
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


class SwitchedOff(RuntimeError):
    """The master switch is off."""

    def __init__(self) -> None:
        super().__init__(
            "MAGI's own model calls are switched off (`research.llm_calls: off`). "
            "Nothing was called, and nothing counts as reviewed.")


def check(root, enabled: bool = True, when=None) -> None:
    """Raise if this call may not happen. Silence means go ahead.

    One call at the top of anything that spends. The only refusal is the
    master switch; it stops *before* the subprocess and says the sentence
    every caller relies on — nothing counts as reviewed. `root` and `when` are
    taken so the signature stays the shape it had when there was a budget to
    check, and so a per-workspace rule can be added here later without
    touching every spender again.
    """
    del root, when
    if not enabled:
        raise SwitchedOff()


def summary(root, when=None) -> dict:
    """What the week has cost, for `MAP.md` and the dashboard.

    One pass. The obvious spelling — `spent()` for the total and `spent()`
    again per kind — read and re-parsed the whole file once per kind plus
    once more, for a number that is a tally of the same rows. `magi map` and
    the dashboard both call this on every render.

    `failed` is counted separately: a week of twelve calls of which nine
    failed is a week with a broken adapter, and that is the reading somebody
    opening this section most needs.
    """
    week = week_of(when or _now())
    used = 0
    failed = 0
    by_kind = {kind: 0 for kind in KINDS}
    by_tier: dict = {}
    for entry in entries(root):
        stamp = parse_at(entry.get("at"))
        if stamp is None or week_of(stamp) != week:
            continue
        used += 1
        if not entry.get("ok", True):
            failed += 1
        kind = entry.get("kind")
        if kind in by_kind:
            by_kind[kind] += 1
        tier = entry.get("tier")
        if tier:
            by_tier[tier] = by_tier.get(tier, 0) + 1
    return {
        "week": week,
        "spent": used,
        "failed": failed,
        "by_kind": by_kind,
        "by_tier": by_tier,
    }
