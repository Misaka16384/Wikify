"""The v2 vocabulary, frozen in one place: kinds, statuses, who may flip what.

`threads/` is one directory with one schema and three kinds of note, and the
whole point of that design is that a status word is a *fact the system reacts
to* rather than something an agent narrates. `magi next` reads statuses,
`sync --close` audits them, the reviewer is triggered by one specific
transition. That only works if every writer spells them the same way, so the
vocabulary lives here and nowhere else: no string literal like ``"supported"``
belongs in a command, a skill, or the WebUI.

Three things are frozen here and each has a reason:

**Kinds and statuses.** `proposition` is the unit with a truth value and it is
the only kind with a full lifecycle. `question` is open-ended — it has no truth
value, its children are propositions, and it closes when they answer it.
`line` is a research line whose note body *is* its STATUS, so its statuses are
phases of work rather than claims about the world.

**Legal transitions.** Not to police research — an agent that discovers the
answer in the literature may go from ``open`` straight to ``supported`` and
that is allowed — but to catch bookkeeping mistakes: a status word from the
wrong kind, or a move out of a terminal state. ``superseded`` is terminal
because a proposition replaced by a published paper is finished; if it comes
back it is a new proposition, with a new slug.

**Whose decision a transition is.** Almost everything belongs to whoever is
nearest (design principle: 记账靠近). The exceptions are the adjudications:
closing a line is a ritual reserved for a person, and ``conflict``,
``disputed`` and ``closed`` are left only by a human decision, because each of
them exists precisely to stop the machine from settling the question itself.

Nothing enforces this yet, and the docstring says so rather than letting the
table read as a guarantee. `threads.validate()` checks only that a posted
transition is *legal*, because a post's signature names the host that wrote it
(`claude`, `codex`) and not whose call it was — and the agent transcribing a
person's decision is the normal case, not an evasion. Enforcement needs the
decision itself on record, which is `magi sync --close` and `decisions.md` in
M2. Until then this table is the policy those checks will read.

Temperature (`tier_of`) is derived here too, because for notes under
``threads/`` it is a function of ``kind + status`` and files never move between
tiers. Everywhere else it is a function of the directory alone.
"""

from __future__ import annotations

# ---------------------------------------------------------------- kinds

PROPOSITION = "proposition"
QUESTION = "question"
LINE = "line"

KINDS = (PROPOSITION, QUESTION, LINE)

# ---------------------------------------------------------------- statuses

#: ``conflict`` is in every kind's list on purpose: it is a property of
#: concurrent writing, not of what the note is about.
CONFLICT = "conflict"

STATUSES = {
    PROPOSITION: (
        "open",
        "conjectured",
        "testing",
        "supported",
        "refuted",
        "superseded",
        "disputed",
        CONFLICT,
    ),
    QUESTION: ("open", "answered", "abandoned", CONFLICT),
    LINE: ("exploring", "active", "writing", "dormant", "closed", CONFLICT),
}

#: The status a note gets when it is created, per kind.
INITIAL_STATUS = {
    PROPOSITION: "open",
    QUESTION: "open",
    LINE: "exploring",
}

#: Reaching this triggers the reviewer (`magi review`, batched at `--close`).
REVIEW_TRIGGER = (PROPOSITION, "supported")

#: Reaching any of these puts the note on the human decision queue.
QUEUE_TRIGGERS = frozenset({
    (PROPOSITION, "disputed"),
    (PROPOSITION, CONFLICT),
    (QUESTION, CONFLICT),
    (LINE, CONFLICT),
})

# ---------------------------------------------------------------- transitions

#: ``{kind: {from_status: (allowed_to_status, ...)}}``. ``conflict`` is not
#: listed as a destination anywhere — every status can reach it, and only the
#: CLI writes it, so it is handled in `allowed_targets` rather than repeated
#: eight times.
_TRANSITIONS = {
    PROPOSITION: {
        "open": ("conjectured", "testing", "supported", "refuted", "superseded"),
        "conjectured": ("testing", "supported", "refuted", "superseded"),
        "testing": ("conjectured", "supported", "refuted", "superseded"),
        "supported": ("testing", "refuted", "disputed", "superseded"),
        "refuted": ("testing", "disputed", "superseded"),
        "disputed": ("testing", "supported", "refuted", "superseded"),
        "superseded": (),
        CONFLICT: ("open", "conjectured", "testing", "supported", "refuted",
                   "disputed", "superseded"),
    },
    QUESTION: {
        "open": ("answered", "abandoned"),
        "answered": ("open", "abandoned"),
        "abandoned": ("open",),
        CONFLICT: ("open", "answered", "abandoned"),
    },
    LINE: {
        "exploring": ("active", "writing", "dormant", "closed"),
        "active": ("exploring", "writing", "dormant", "closed"),
        "writing": ("active", "dormant", "closed"),
        "dormant": ("exploring", "active", "writing", "closed"),
        "closed": ("active", "dormant"),
        CONFLICT: ("exploring", "active", "writing", "dormant", "closed"),
    },
}

# ---------------------------------------------------------------- actors

AGENT = "agent"
HUMAN = "human"
REVIEWER = "reviewer"
CLI = "cli"

ACTORS = (AGENT, HUMAN, REVIEWER, CLI)

#: Everyone who is allowed to write an ordinary transition. The reviewer is
#: listed because its verdict flips ``supported → disputed`` on its own.
_DEFAULT_WRITERS = frozenset({AGENT, HUMAN, REVIEWER, CLI})

#: ``(kind, to_status)`` pairs a person alone may write. Closing a line is a
#: ritual (design §6); reopening one is the same decision in reverse.
_HUMAN_ONLY_TARGETS = frozenset({(LINE, "closed")})

#: Statuses that only a person's decision moves a note out of. All three are
#: adjudications rather than findings: ``conflict`` means two writers disagreed
#: about the status itself; ``disputed`` means the reviewer rejected a claimed
#: result and design-v2 §11 says it does not flip back on its own; ``closed``
#: is the far side of the ritual, and reopening a line is the same decision in
#: reverse. Each of them is a decision-queue entry until a person answers it.
_HUMAN_ONLY_SOURCES = frozenset({CONFLICT, "disputed", "closed"})


def statuses(kind: str) -> tuple:
    """Every status the kind may hold. Raises ``KeyError`` on an unknown kind."""
    return STATUSES[kind]


def is_status(kind: str, status: str) -> bool:
    return status in STATUSES.get(kind, ())


def allowed_targets(kind: str, status: str) -> tuple:
    """Statuses reachable from ``status``, ``conflict`` included."""
    table = _TRANSITIONS.get(kind)
    if table is None or status not in table:
        return ()
    return table[status] + (CONFLICT,)


def is_legal_transition(kind: str, src: str, dst: str) -> bool:
    """A no-op (``src == dst``) is legal: it is not a transition at all."""
    if src == dst:
        return is_status(kind, src)
    return dst in allowed_targets(kind, src)


def writers(kind: str, src: str, dst: str) -> frozenset:
    """Whose *decision* this transition is. Empty when it is illegal.

    ``HUMAN`` here means the call belongs to a person, not that a person typed
    the bytes: design-v2 §10 has the agent transcribe what the human decided,
    so the post is signed by whichever CLI was running. Reading it the other
    way would make the rule unsatisfiable — no host writes as "human".

    Callers should treat an empty set and "not mine to write" the same way:
    both mean *do not write it*.
    """
    if not is_legal_transition(kind, src, dst):
        return frozenset()
    if dst == CONFLICT:
        return frozenset({CLI})
    if src in _HUMAN_ONLY_SOURCES or (kind, dst) in _HUMAN_ONLY_TARGETS:
        return frozenset({HUMAN})
    return _DEFAULT_WRITERS


def may_write(actor: str, kind: str, src: str, dst: str) -> bool:
    return actor in writers(kind, src, dst)


def is_human_only(kind: str, src: str, dst: str) -> bool:
    """Whether this transition is a person's call rather than anybody's.

    The question `sync --close` asks of every posted flip. It is deliberately
    about the *decision* and not the typist: an agent transcribing what a
    person decided is the normal case, so what gets checked downstream is
    whether the decision is on record — as a post signed `human`, or as an
    entry in `decisions.md`.
    """
    return writers(kind, src, dst) == frozenset({HUMAN})


# ---------------------------------------------------------------- key_move

#: How a closed proposition was actually resolved. Written once, at the closing
#: section, and it is the field a person reads when they ask "was this a real
#: idea or did we just have enough compute". A person maintains this list;
#: additions go through design-v2 §4 first, so it stays comparable over time.
KEY_MOVES = (
    "new-method",
    "known-method-new-setting",
    "reduction-to-known",
    "brute-force",
    "lucky-observation",
)

# ---------------------------------------------------------------- coaching

#: How hard the forced-output protocol pushes. ``strict`` refuses to start a
#: derivation without a recorded prediction; ``light`` asks and accepts
#: silence; ``off`` never asks. "I don't know" is a valid answer at every level.
COACHING_LEVELS = ("off", "light", "strict")
DEFAULT_COACHING = "light"

#: The three question shapes the human is ever asked. Anything answerable with
#: "ok" is not a question (design §10).
FORCED_OUTPUT_KINDS = ("prediction", "choice", "falsification")

#: What a person may bet on a proposition. ``unknown`` is a real answer and is
#: recorded as one — it is the honest prior, and scoring it as a miss would
#: teach the wrong lesson.
BETS = ("supported", "refuted", "unknown")

# ---------------------------------------------------------------- temperature

COLD = "cold"
COLD_DERIVED = "cold-derived"
WARM_SHARED = "warm-shared"
WARM_LINE = "warm-line"
HOT = "hot"

#: Coldest first. Comparisons ("is this hotter than that") use the index.
TIERS = (COLD, COLD_DERIVED, WARM_SHARED, WARM_LINE, HOT)

#: Directory → tier, longest prefix wins. `threads/` is deliberately absent:
#: its notes take their temperature from ``kind + status``.
_TIER_BY_PREFIX = (
    ("raw/", COLD),
    ("wiki/references/", COLD_DERIVED),
    ("wiki/concepts/", WARM_SHARED),
    ("wiki/topics/", WARM_SHARED),
    ("drafts/", WARM_LINE),
    ("inbox/", HOT),
    ("scratch/", HOT),
)

#: Statuses that make a `threads/` note warm. Everything else in `threads/` is
#: hot: the note is still being argued about, whatever its kind.
_SETTLED_STATUSES = frozenset({
    "supported", "refuted", "superseded",   # proposition
    "answered", "abandoned",                # question
    "dormant", "closed",                    # line
})


def tier_of(relpath: str, kind: str = None, status: str = None):
    """Temperature of one file, or ``None`` when it has none.

    ``None`` covers two cases that behave the same way — derived artefacts and
    ledgers under ``output/``, which are rebuilt rather than edited, and paths
    nobody has decided about yet. Following `durability.classify`, not knowing
    is reported rather than guessed.

    For a note under ``threads/``, pass its ``kind`` and ``status``; without
    them the answer is ``HOT``, which is the safe default because it is the
    tier that promises the least.
    """
    path = relpath.replace("\\", "/").lstrip("./")
    if path.startswith("threads/"):
        if status is None:
            return HOT
        return WARM_LINE if status in _SETTLED_STATUSES else HOT
    for prefix, tier in _TIER_BY_PREFIX:
        if path.startswith(prefix):
            return tier
    return None


def is_hotter(a: str, b: str) -> bool:
    """True when tier ``a`` is hotter than ``b``. Unknown tiers compare False."""
    if a not in TIERS or b not in TIERS:
        return False
    return TIERS.index(a) > TIERS.index(b)
