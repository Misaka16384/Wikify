"""The proposal ledger: what was suggested, and what a person did about it.

`output/reflect/ledger.jsonl` — append-only, folded last-write-wins, the same
shape as every other ledger in this repo. It is not `output/llm-ledger.jsonl`:
that one records what was *spent*, this one records what was *proposed*. Two
questions, two files.

**The CLI writes it, at the moment a person decides.** Not the model that made
the proposal, and not on the model's say-so. A ledger the proposer can write is
a ledger that says whatever the proposer wanted it to say, and the whole reason
this file exists is to be the thing a proposal cannot argue with.

**A rejection keeps its full text.** Being turned down is not a filter, it is
the input to the next proposal: the loop is supposed to read what it already
suggested and was told no about, so that it stops suggesting it and can say
*why the next idea is different*. Dropping the text would leave only the
absence, and an absence teaches nothing.

Two rules that were prose in the design become queries here: "already rejected,
do not propose again" is a lookup, and "accepted and still live" is what the
managed block renders from.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

LEDGER = ("output", "reflect", "ledger.jsonl")

#: A person accepted it. For a rule, this is what puts it in the managed block.
ACCEPTED = "accepted"
#: A person said no. Kept in full — it is the next proposal's input.
REJECTED = "rejected"
#: A person turned it into code: a hook, a gate, a test. The prose goes away
#: because the check now runs.
PROMOTED = "promoted"
#: The pattern behind it went quiet for ninety days and nobody defended it.
RETIRED = "retired"
VERDICTS = (ACCEPTED, REJECTED, PROMOTED, RETIRED)

#: What a proposal is asking to change.
RULE = "rule"          # a line of prose in the managed block
PATCH = "patch"        # an edit to a file, in the patterns.OPS vocabulary
SKILL = "skill"        # a change to how a skill does its work
FACT = "fact"          # something true about the subject, which belongs in the wiki
KINDS = (RULE, PATCH, SKILL, FACT)

APPEND_TIMEOUT = 30.0


@dataclass
class Proposal:
    """One suggestion and its fate."""
    id: str
    at: str = ""
    kind: str = RULE
    target: str = ""          # the file, skill or block it wants to change
    text: str = ""            # the rule, or the patch's text
    pattern: str = ""         # the page it came from
    hosts: list = field(default_factory=list)
    evidence: list = field(default_factory=list)   # verbatim quotes
    patch: dict = field(default_factory=dict)
    verdict: str = ""         # "" while nobody has decided
    decided_at: str = ""
    note: str = ""            # what the person said when deciding

    @property
    def open(self) -> bool:
        return not self.verdict

    @property
    def live(self) -> bool:
        """Accepted, and not since promoted or retired — what the block shows."""
        return self.verdict == ACCEPTED


def path_for(root) -> Path:
    return Path(root).joinpath(*LEDGER)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _append(root, record: dict) -> dict:
    from filelock import FileLock

    path = path_for(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    with FileLock(str(lock), timeout=APPEND_TIMEOUT):
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def propose(root, *, kind: str, target: str, text: str, pattern: str,
            hosts=None, evidence=None, patch=None, at=None) -> Proposal:
    """Record a proposal. Nobody has decided anything yet."""
    if kind not in KINDS:
        raise ValueError(f"not a proposal kind: {kind!r} (one of {', '.join(KINDS)})")
    if not str(text).strip():
        raise ValueError("a proposal with no text is not a proposal")
    record = {
        "kind": "propose",
        "id": f"r-{uuid.uuid4().hex[:10]}",
        "at": at or _now(),
        "proposal_kind": kind,
        "target": target,
        "text": text,
        "pattern": pattern,
        "hosts": sorted(set(hosts or [])),
        "evidence": list(evidence or []),
        "patch": patch or {},
    }
    _append(root, record)
    return _to_proposal(record)


def decide(root, proposal_id: str, verdict: str, note: str = "", at=None) -> dict:
    """Record what a person decided. The CLI calls this; nothing else does."""
    if verdict not in VERDICTS:
        raise ValueError(f"not a verdict: {verdict!r} (one of {', '.join(VERDICTS)})")
    return _append(root, {"kind": "decide", "id": proposal_id, "verdict": verdict,
                          "note": note, "at": at or _now()})


def _to_proposal(record: dict) -> Proposal:
    return Proposal(
        id=str(record.get("id") or ""),
        at=str(record.get("at") or ""),
        kind=str(record.get("proposal_kind") or RULE),
        target=str(record.get("target") or ""),
        text=str(record.get("text") or ""),
        pattern=str(record.get("pattern") or ""),
        hosts=[str(h) for h in (record.get("hosts") or [])],
        evidence=[str(e) for e in (record.get("evidence") or [])],
        patch=record.get("patch") if isinstance(record.get("patch"), dict) else {},
    )


def all_proposals(root) -> list:
    """Every proposal with its latest verdict folded in, oldest first.

    A bad line is skipped rather than fatal: this file gates what goes into the
    protocol every agent reads, and a gate that crashes on one stray character
    stops the whole loop.
    """
    path = path_for(root)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    order: list = []
    by_id: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        ident = str(record.get("id") or "")
        if record.get("kind") == "propose":
            if ident not in by_id:
                order.append(ident)
            by_id[ident] = _to_proposal(record)
        elif record.get("kind") == "decide" and ident in by_id:
            proposal = by_id[ident]
            proposal.verdict = str(record.get("verdict") or "")
            proposal.decided_at = str(record.get("at") or "")
            proposal.note = str(record.get("note") or "")
    return [by_id[ident] for ident in order]


def get(root, proposal_id: str):
    for proposal in all_proposals(root):
        if proposal.id == proposal_id:
            return proposal
    return None


def open_proposals(root) -> list:
    return [p for p in all_proposals(root) if p.open]


def live_rules(root) -> list:
    """Accepted rules, oldest acceptance first.

    What the managed block renders, and what "retire the oldest" means. Sorted
    by *when they were accepted* rather than when they were proposed: a rule
    proposed in January and accepted yesterday is the newest one there is, and
    telling somebody to retire it because it was thought of first is telling
    them to retire the wrong rule.

    Promoted ones are gone on purpose: the check runs now, and a rule that is
    also a check is a rule every session pays to read twice.
    """
    live = [p for p in all_proposals(root) if p.live and p.kind == RULE]
    live.sort(key=lambda p: p.decided_at or p.at)
    return live


def rejected(root) -> list:
    """Everything a person said no to, in full.

    Handed back to the next pass so it stops proposing the same thing — and so
    it can say what makes the next idea different.
    """
    return [p for p in all_proposals(root) if p.verdict == REJECTED]


def fingerprint(kind: str, target: str, text: str) -> tuple:
    """How two proposals are told apart.

    Case, spacing and trailing punctuation do not make a different idea. An
    exact-text key let the same rule come back with a full stop added, which is
    the one thing "do not propose it again" was supposed to prevent.
    """
    words = " ".join(str(text or "").lower().split()).strip(" .;:!?")
    return (str(kind), str(target or "").strip().lower(), words)


def already_proposed(root) -> set:
    """Changes that have been proposed before, whatever was decided.

    Includes the open ones: proposing the same change twice while the first is
    still waiting is how a queue turns into a list of duplicates.
    """
    # A retired proposal is not in here. Retiring says "its reason has gone",
    # and the whole point of it being a separate verdict from `reject` is that
    # the same idea may come back when the pattern does. Counting it as
    # already-proposed made the two verdicts identical at the one gate where
    # the difference shows.
    return {fingerprint(p.kind, p.target, p.text) for p in all_proposals(root)
            if p.verdict != RETIRED}
