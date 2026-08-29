"""The closed vocabulary a promoted rule has to fit in.

A rule in the protocol block is read by every session and followed by none of
them reliably. Promoting it is supposed to mean *something now checks it* — so
what a promotion produces has to be a thing the gates already run, not a file
somebody might write a check into one day. A skeleton test waiting on a
physicist to write pytest is a promotion in name only: the ledger says
`promoted`, the prose is gone from the block, and nothing is checking anything.
That is the rubber stamp again, wearing a different hat.

So there are five predicates and no escape hatch. A proposal that does not fit
one of them cannot be promoted — it stays prose, or it becomes a package-level
proposal asking for a sixth. The vocabulary being small and closed is the
feature: everything in it is executable by `magi lint` and `magi sync --close`,
and everything executable is checked on every run rather than believed.

Every instance carries `from:`, the ledger id of the proposal that produced it,
so a violation can say *why this rule exists* in the words of whoever accepted
it. A rule nobody can trace is a rule nobody can argue with, and one that
cannot be argued with cannot be retired either.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field

from . import vocab

#: A note of this kind, at this status, must carry this frontmatter field.
#: The `coaching: strict` bet check is this rule with (proposition, testing, bet).
REQUIRE_FIELD = "require_field"

#: What this field links to must live under this directory. Evidence pointing
#: at `raw/` is this rule; so is a derivation pointing at `drafts/`.
FIELD_POINTS_INTO = "field_points_into"

#: A move the lifecycle allows but this library does not.
FORBID_TRANSITION = "forbid_transition"

#: How many propositions may be open on one line at once.
MAX_OPEN_PER_LINE = "max_open_per_line"

#: Leaving this status needs a post signed by this host. The `disputed` gate is
#: this rule with (disputed, human).
LEAVING_REQUIRES_POST_BY = "leaving_status_requires_post_by"

VOCABULARY = (REQUIRE_FIELD, FIELD_POINTS_INTO, FORBID_TRANSITION,
              MAX_OPEN_PER_LINE, LEAVING_REQUIRES_POST_BY)

#: What each predicate needs. Checked when a rule is written, not when it runs:
#: a rule that cannot be executed should be refused by the thing that adds it,
#: not discovered by the gate at the worst moment.
REQUIRED = {
    REQUIRE_FIELD: ("kind", "status", "field"),
    FIELD_POINTS_INTO: ("field", "directory"),
    FORBID_TRANSITION: ("kind", "src", "dst"),
    MAX_OPEN_PER_LINE: ("limit",),
    LEAVING_REQUIRES_POST_BY: ("status", "host"),
}


@dataclass
class Rule:
    name: str
    params: dict = dataclass_field(default_factory=dict)
    source: str = ""          # ledger id of the proposal this came from

    def describe(self) -> str:
        bits = ", ".join(f"{k}={v}" for k, v in sorted(self.params.items()))
        return f"{self.name}({bits})"


@dataclass
class Violation:
    rule: Rule
    slug: str
    message: str

    @property
    def why(self) -> str:
        return self.message


class RuleError(ValueError):
    """A rule that cannot be executed. Raised where it is written, not run."""


def parse(entries) -> list:
    """Rules from `config.yaml`'s `rules:`. Refuses what it cannot run.

    A malformed rule raises rather than being skipped: a gate that quietly
    ignores the rule somebody thought they had is worse than one that will not
    start, because the first kind is discovered by not catching anything.
    """
    out = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            raise RuleError(f"a rule is a mapping, not {type(entry).__name__}")
        params = {k: v for k, v in entry.items() if k not in ("rule", "from")}
        name = str(entry.get("rule") or "")
        if name not in VOCABULARY:
            raise RuleError(f"no such rule: {name!r} (one of {', '.join(VOCABULARY)})")
        missing = [key for key in REQUIRED[name] if key not in params]
        if missing:
            raise RuleError(f"{name} needs {', '.join(missing)}")
        out.append(Rule(name=name, params=params, source=str(entry.get("from") or "")))
    return out


def to_entry(rule: Rule) -> dict:
    return {"rule": rule.name, **rule.params, "from": rule.source}


# ---------------------------------------------------------------- checking


def check(state, rules) -> list:
    """Every violation of every rule, in note order.

    Takes a loaded `state.State`: the notes are already parsed by then, and a
    second reader of the same files is a second answer waiting to disagree.
    """
    out: list = []
    for rule in rules:
        out.extend(_CHECKERS[rule.name](state, rule))
    return out


def _require_field(state, rule) -> list:
    kind, status, field = (rule.params["kind"], rule.params["status"],
                           rule.params["field"])
    return [Violation(rule, note.slug,
                      f"{note.slug} is a {kind} at {status} with no `{field}:`")
            for note in state.notes
            if note.kind == kind and note.status == status
            and not note.frontmatter.get(field)]


def _field_points_into(state, rule) -> list:
    from ..kb import threads

    field, directory = rule.params["field"], str(rule.params["directory"]).strip("/")
    out = []
    for note in state.notes:
        for link in threads.as_list(note.frontmatter.get(field)):
            cleaned = str(link).strip().strip("[]").replace("\\", "/")
            if cleaned and not cleaned.lstrip("./").startswith(directory + "/"):
                out.append(Violation(
                    rule, note.slug,
                    f"{note.slug}: `{field}` points at {cleaned}, which is not "
                    f"under {directory}/"))
    return out


def _forbid_transition(state, rule) -> list:
    kind, src, dst = rule.params["kind"], rule.params["src"], rule.params["dst"]
    out = []
    for note in state.notes:
        if note.kind != kind:
            continue
        for post in note.posts:
            if post.is_transition and post.src == src and post.dst == dst:
                out.append(Violation(
                    rule, note.slug,
                    f"{note.slug} went {src} → {dst}, which this library does not do"))
    return out


def _max_open_per_line(state, rule) -> list:
    limit = int(rule.params["limit"])
    return [Violation(rule, view.slug,
                      f"{view.slug} has {view.open_count} open at once, more than "
                      f"the {limit} this library allows")
            for view in state.lines if view.open_count > limit]


def _leaving_requires_post_by(state, rule) -> list:
    """Leaving a status without the signature that is supposed to authorise it.

    Only the *last* departure is checked. An older one may have been settled by
    something this rule did not exist for yet, and a rule that fires on history
    is a rule somebody turns off.
    """
    status, host = rule.params["status"], rule.params["host"]
    out = []
    for note in state.notes:
        leaving = [index for index, post in enumerate(note.posts)
                   if post.is_transition and post.src == status]
        if not leaving:
            continue
        index = leaving[-1]
        window = note.posts[max(0, index - 1):index + 1]
        if not any(post.host == host for post in window):
            out.append(Violation(
                rule, note.slug,
                f"{note.slug} left {status} with no post signed `{host}`"))
    return out


_CHECKERS = {
    REQUIRE_FIELD: _require_field,
    FIELD_POINTS_INTO: _field_points_into,
    FORBID_TRANSITION: _forbid_transition,
    MAX_OPEN_PER_LINE: _max_open_per_line,
    LEAVING_REQUIRES_POST_BY: _leaving_requires_post_by,
}


# ------------------------------------------------------------- from a proposal


#: What a proposal has to say to be promotable. The model proposes a rule in
#: this vocabulary or it proposes prose; there is no third thing.
def from_proposal(proposal):
    """The rule a proposal asks for, or `None` if it does not fit.

    `None` is a real answer and the common one. A proposal that names no
    predicate is not broken — it is prose, which is what most good advice is,
    and the button for turning it into code is simply not available.
    """
    patch = getattr(proposal, "patch", None) or {}
    name = str(patch.get("rule") or "")
    if name not in VOCABULARY:
        return None
    params = {k: v for k, v in patch.items() if k not in ("rule", "op", "target", "text")}
    missing = [key for key in REQUIRED[name] if key not in params]
    if missing:
        return None
    return Rule(name=name, params=params, source=proposal.id)


#: Rules MAGI enforces for everybody, spelled in the same vocabulary so that a
#: person reading `config.yaml` sees the same shape as their own.
BUILTIN_SHAPE = (
    {"rule": FIELD_POINTS_INTO, "field": "derivation", "directory": "drafts",
     "from": "builtin"},
    {"rule": LEAVING_REQUIRES_POST_BY, "status": vocab.CONFLICT, "host": vocab.HUMAN,
     "from": "builtin"},
)
