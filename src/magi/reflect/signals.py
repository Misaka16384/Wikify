"""What MAGI itself knows went well or badly, without asking a model.

The slow loop reads transcripts, but transcripts are the *expensive* half and
the ambiguous one: a session where somebody was frustrated looks much like one
where they were thinking out loud. These signals are the cheap half — events
the notes already record, each of which happened at a knowable moment, so a
session can be picked because something in it actually went wrong rather than
because a model thought it looked interesting.

**Wins are collected too, and that is not symmetry for its own sake.** A loop
fed only failures grows only prohibitions: every proposal it can make is a
thing to stop doing. Improvements to *how* work is done can only come from
sessions where the work went well, so the sampler reserves room for them
(design-v2 §12).

Nothing here calls a model, writes a file, or decides anything. It answers one
question — *what happened, when, and on which note* — and leaves the judging to
the stage that can afford it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from ..core import vocab

#: A claim that was solved and then unsolved. The strongest single signal in
#: the system: somebody believed something, wrote it down, and was wrong.
REVERSAL = "reversal"

#: Work that happened and nobody recorded — the close gate's own complaint.
DEBT = "debt"

#: An independent reader disagreed with a claim that said it was solved.
REJECTION = "rejection"

#: A claim that went out and came back approved, first time. The only kind of
#: evidence that can support "keep doing it this way".
CLEAN = "clean"

LOSSES = (REVERSAL, DEBT, REJECTION)
WINS = (CLEAN,)


@dataclass
class Signal:
    """One thing that happened, with a time a session can be matched against."""
    kind: str
    slug: str
    at: str
    why: str
    path: str = ""

    @property
    def is_loss(self) -> bool:
        return self.kind in LOSSES

    def when(self):
        from ..state import parse_at

        return parse_at(self.at)


def collect(state) -> list:
    """Every signal in this workspace, newest last.

    Takes a loaded `state.State` rather than a path: the notes have already
    been read and parsed by then, and reading them twice is how two answers to
    the same question start to disagree.
    """
    out: list = []
    out.extend(_reversals(state))
    out.extend(_rejections(state))
    out.extend(_debt(state))
    out.extend(_clean(state))
    out.sort(key=lambda signal: signal.at or "")
    return out


def _reversals(state) -> list:
    """`supported → refuted`, and `supported → disputed` from a person.

    A reviewer's rejection is its own signal below; this is the case where the
    library itself changed its mind, which is the thing most worth
    understanding and the thing nobody goes back to look at.
    """
    out = []
    for note in state.notes:
        if note.kind != vocab.PROPOSITION:
            continue
        for post in note.posts:
            if not post.is_transition or post.src != "supported":
                continue
            if post.dst == "refuted":
                out.append(Signal(REVERSAL, note.slug, post.at,
                                  "a claim that said it was solved turned out wrong",
                                  str(note.path)))
            elif post.dst == "disputed" and post.host != vocab.REVIEWER:
                out.append(Signal(REVERSAL, note.slug, post.at,
                                  "a claim that said it was solved was put back in "
                                  "dispute", str(note.path)))
    return out


def _rejections(state) -> list:
    out = []
    for note in state.notes:
        for post in note.posts:
            if (post.host == vocab.REVIEWER and post.is_transition
                    and post.dst == "disputed"):
                out.append(Signal(REJECTION, note.slug, post.at,
                                  "an independent reader did not accept the claim as "
                                  "written", str(note.path)))
    return out


def _debt(state) -> list:
    """The close gate's own list, as signals.

    Dated by the event where one is known — `DebtItem.when` is the post that
    made the flip. Debt with no date is still a signal; it just cannot be
    matched to a session, and the sampler will not pretend otherwise.
    """
    return [Signal(DEBT, item.slug, item.when or "", item.why,
                   str(item.path) if item.path else "")
            for item in state.debt]


def _clean(state) -> list:
    """Claims that were reviewed and stood, having never been disputed.

    "First time" matters: a claim that was rejected, argued over and eventually
    accepted is a story about recovery, not about a method worth repeating.
    """
    out = []
    for note in state.notes:
        if note.kind != vocab.PROPOSITION or note.status != "supported":
            continue
        if any(post.dst == "disputed" for post in note.posts if post.is_transition):
            continue
        for post in note.posts:
            if post.host == vocab.REVIEWER and "VERDICT: stands" in (post.text or ""):
                out.append(Signal(CLEAN, note.slug, post.at,
                                  "a claim went out for review and stood, first time",
                                  str(note.path)))
                break
    return out


# ---------------------------------------------------------------- sampling


#: How many sessions one pass looks at, and how the room is divided. From
#: design-v2 §12: enough to see a pattern repeat, few enough to afford.
MAX_SESSIONS = 8
MAX_LOSS = 5
MAX_WIN = 3

#: How far either side of a signal a session still counts as "the one where
#: that happened". Generous, because a session's recorded end is when the last
#: message was written, not when the person stopped thinking about it.
NEAR = dt.timedelta(hours=2)


@dataclass
class Sample:
    """One session, and why it was picked."""
    session: object
    signals: list
    kind: str            # "loss" | "win"


def _distance(session, signal):
    """How far this event is from that session, or `None` if it is not near.

    Zero while the session was running. Outside it, the gap to the nearer end
    — which is what lets one event be given to the session it most likely
    happened in rather than to every session within two hours of it.
    """
    from ..state import parse_at

    moment = signal.when()
    if moment is None:
        return None
    start = parse_at(session.started) or parse_at(session.ended)
    end = parse_at(session.ended) or start
    if start is None or end is None:
        return None
    if start > end:
        start, end = end, start
    if start <= moment <= end:
        return dt.timedelta(0)
    gap = (start - moment) if moment < start else (moment - end)
    return gap if gap <= NEAR else None


def _overlaps(session, signal) -> bool:
    return _distance(session, signal) is not None


def sample(sessions, signals, max_loss: int = MAX_LOSS, max_win: int = MAX_WIN) -> list:
    """Pick the sessions worth reading, and say what happened in each.

    A session is worth reading when something recorded happened while it was
    running. Sessions with nothing attached are not sampled at all: reading a
    transcript costs a model call, and "nothing went wrong here" is not a thing
    worth paying to be told.

    Losses and wins are counted separately so that a bad week cannot crowd out
    every example of the work going well — which is the only evidence that can
    support a proposal about *method* rather than another prohibition.
    """
    # Each event belongs to the session it happened *in*, not to every session
    # whose window it lands near. Attaching one debt item to two sessions
    # presented the model with the same event twice, under two headings — and
    # a model naming both cleared the >=2-independent-sessions gate off a
    # single thing that happened once.
    claimed: dict = {}
    for signal in signals:
        best, distance = None, None
        for session in sessions:
            gap = _distance(session, signal)
            if gap is None:
                continue
            if distance is None or gap < distance:
                best, distance = session, gap
        if best is not None:
            claimed.setdefault(id(best), []).append(signal)

    attached: list = []
    for session in sessions:
        hits = claimed.get(id(session)) or []
        if not hits:
            continue
        kind = "loss" if any(signal.is_loss for signal in hits) else "win"
        attached.append(Sample(session=session, signals=hits, kind=kind))

    # Newest first: what is going wrong now is worth more than what went wrong
    # a month ago and may already have been fixed.
    attached.sort(key=lambda item: (item.session.ended or item.session.started or ""),
                  reverse=True)

    losses = [item for item in attached if item.kind == "loss"][:max_loss]
    wins = [item for item in attached if item.kind == "win"][:max_win]
    return losses + wins
