"""What the research is doing right now, computed from the files every time.

This is the projection the rest of v2 reads: `magi next` ranks it, `MAP.md` is
it rendered for a person, `sync --close` refuses to let a session end while it
still shows debt. Nothing here is stored. A status lives in exactly one place —
the frontmatter of the note it belongs to — and everything else is arithmetic
over that. The moment a projection is written to disk it becomes a second
answer that can disagree with the first, and then somebody has to decide which
one is true.

Four things come out of the same pass over `threads/`:

**Lines.** Each research line, its phase, how many propositions are open under
it, when it last moved, and whether it has gone quiet. This is the half of
`MAP.md` a person actually reads.

**A decision queue.** Only the three kinds of event that are allowed to
interrupt somebody (design-v2 §6): a claimed result the reviewer rejected, two
writers who disagreed about a status, and a line whose direction may have
changed. Plus predictions the human owes — asked once, at the moment they are
still honest.

**Bookkeeping debt.** Not "work that is left" — *work that happened and was not
written down*. A proposition whose status the posts do not explain; a
derivation edited after the proposition that points at it last moved. Debt is
first in the `next` list because it is the cheapest thing in the system to fix
and the most expensive to leave: every other projection is wrong while it
stands.

**WIP.** How many propositions a line has open. Above the limit, the honest
next move is to close one rather than open another — a limit, not a score.
Ranking research by a number is the thing design-v2 §16 rules out; counting is
not ranking.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from .core import md_blocks, vocab
from .kb import threads

#: Open propositions a line may carry before `next` starts asking for one to be
#: closed. Seven is a working-memory number, not a measurement: past it a person
#: can no longer hold what is open, and the line stops being one line.
WIP_LIMIT = 7

#: Days without a post before a line is called quiet. Long enough that a week
#: off is not a flag, short enough that a forgotten line surfaces in a month.
STALL_DAYS = 21

#: Statuses that count against the WIP limit — the ones that are somebody's
#: turn. `disputed` is not one: it is waiting on a person, and counting it
#: would ask them to close the thing they are already being asked to judge.
_OPEN_STATUSES = frozenset({"open", "conjectured", "testing"})

#: The line every note that names no line belongs to. A project may run with no
#: explicit lines at all, and it should still have a map.
UNLINED = "(unlined)"


@dataclass
class LineView:
    slug: str
    status: str
    purpose: str = ""
    open_count: int = 0
    total: int = 0
    last_move: str | None = None
    stalled: bool = False
    over_wip: bool = False


@dataclass
class QueueItem:
    """Something only a person can settle. `why` is written for them to read."""
    kind: str
    slug: str
    why: str
    line: str | None = None


@dataclass
class DebtItem:
    """Work that happened and was not written down.

    `when` is the time of the event where one is known — the post that made
    the flip. Dating debt by the file's mtime instead makes a `git clone` or a
    `magi migrate` look like a session's worth of work, and a gate that fires
    on every checkout is a gate somebody turns off.
    """
    slug: str
    why: str
    path: Path | None = None
    when: str | None = None
    #: Whether this may hold a session closed. False for anything whose only
    #: evidence is a file mtime: `git clone`, `git checkout`, a restored
    #: backup, an editor's "save all" and a stray `touch` all rewrite mtimes
    #: without a word changing, so a finding derived from one is worth showing
    #: a person and not worth stopping them with. It still appears in
    #: `magi next` and in the closing report's `older` list.
    blocks: bool = True


@dataclass
class Action:
    """One thing that could be done next, and what it costs to do it."""
    key: str
    why: str
    run: str
    cost: str          # "certain" | "llm" | "human"
    slug: str | None = None
    line: str | None = None


@dataclass
class State:
    root: Path
    lines: list = field(default_factory=list)
    queue: list = field(default_factory=list)
    debt: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    wip_limit: int = WIP_LIMIT
    coaching: str = vocab.DEFAULT_COACHING
    #: Violations of the rules this library promoted for itself. Not debt —
    #: debt is work somebody did without recording it, and this is work that
    #: broke a rule a person accepted.
    violations: list = field(default_factory=list)

    @property
    def open_questions(self) -> list:
        return [note for note in self.notes
                if note.kind == vocab.QUESTION and note.status == "open"]


# ---------------------------------------------------------------- time


def parse_at(stamp: str):
    """A post's timestamp, or `None` when it is not one we wrote.

    Posts are signed by four different hosts and edited by hand in between, so
    an unparseable stamp is an ordinary event rather than a corrupt file.
    """
    if not stamp:
        return None
    text = stamp.strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _last_post_time(note):
    stamps = [parse_at(post.at) for post in note.posts]
    stamps = [stamp for stamp in stamps if stamp is not None]
    return max(stamps) if stamps else None


# ---------------------------------------------------------------- loading


def load(root, wip_limit: int | None = None, stall_days: int = STALL_DAYS,
         now=None, coaching: str = vocab.DEFAULT_COACHING) -> State:
    """Read `threads/` once and derive everything from it."""
    root = Path(root)
    now = now or dt.datetime.now(dt.timezone.utc)
    notes, unreadable = [], []
    for path in threads.note_paths(root):
        try:
            notes.append(threads.read_note(path))
        except (OSError, ValueError) as exc:
            # One note nobody can read must not take the whole projection with
            # it. `magi next`, `feed` and above all `sync --close --hook` have
            # to answer — and a note in this state *is* unrecorded work, so it
            # is reported as debt rather than skipped into silence.
            unreadable.append(DebtItem(
                slug=path.stem, path=path,
                why=f"this note could not be read ({exc.__class__.__name__}: "
                    f"{exc}) — nothing can be derived from it until it is fixed"))

    # Zero or less is not a limit anybody meant: every line would be over WIP
    # forever, which is the same as having no gate. The `or` covered `None` and
    # swallowed `0` with it, so the dashboard could show 0 while the gate
    # quietly used 7.
    try:
        limit = int(wip_limit)
    except (TypeError, ValueError):
        limit = WIP_LIMIT
    state = State(root=root, notes=notes, wip_limit=max(1, limit),
                  coaching=coaching)
    state.lines = _lines(notes, now=now, stall_days=stall_days, limit=state.wip_limit)
    state.queue = _queue(notes, state.lines) + _proposals(root)
    state.debt = unreadable + _debt(root, notes)
    state.violations = _violations(root, state)
    if coaching == "strict":
        missing = _missing_bets(notes)
        state.debt.extend(missing)
        # The nudge becomes the block. Leaving both in would put one missing
        # prediction on `magi next` twice, in two different voices, which reads
        # as two problems.
        covered = {item.slug for item in missing}
        state.queue = [item for item in state.queue
                       if not (item.kind == "bet" and item.slug in covered)]
    return state


def _violations(root, state) -> list:
    """What this library's own promoted rules catch.

    Read from `config.yaml` on every load, like everything else here. A rule
    that cannot be parsed is reported as a violation of itself rather than
    skipped: a gate quietly ignoring the rule somebody thought they had is
    discovered by not catching anything, which is the worst way to find out.
    """
    from .core import rules as rules_mod
    from .core.config_loader import get as config_get
    from .core.config_loader import load_config

    try:
        config = load_config(start=root)
        # `BUILTIN_SHAPE` first. It is documented as "rules MAGI enforces for
        # everybody" and nothing imported it, so `derivation:` could point
        # anywhere and a `conflict` could be walked out of unsigned — while
        # this module's docstring says everything executable is checked on
        # every run rather than believed. Parsed through the same function as
        # a person's own rules, because a built-in that took a different path
        # would be a second implementation to keep in step.
        parsed = rules_mod.parse(list(rules_mod.BUILTIN_SHAPE)
                                 + (config_get(config, "research.rules", []) or []))
    except rules_mod.RuleError as exc:
        return [rules_mod.Violation(rules_mod.Rule(name="rules", params={}),
                                    "config.yaml",
                                    f"config.yaml: {exc}")]
    except Exception:  # noqa: BLE001
        return []
    try:
        return rules_mod.check(state, parsed)
    except Exception:  # noqa: BLE001
        return []


def _missing_bets(notes) -> list:
    """Under `coaching: strict`, work started with no prediction is debt.

    The design's strict level is "no prediction, no derivation". A `PreToolUse`
    hook cannot enforce that: it sees a tool call, not which proposition the
    call is about, so it would have to block everything or nothing. The gate
    that *can* tell is the one that reads the notes — so strict makes a missing
    prediction block the session's end rather than the next file read.

    "Don't know" satisfies it. The point was never a correct prediction, it was
    a recorded one.

    Only `testing` blocks, while the queue asks as early as `conjectured`. The
    rule is "no prediction, no derivation", and a conjecture nobody has started
    on has no derivation yet — so the earlier ask stays a nudge and the block
    lands where work actually begins.
    """
    out = []
    for note in notes:
        if note.kind != vocab.PROPOSITION or note.status != "testing":
            continue
        if note.frontmatter.get("bet"):
            continue
        out.append(DebtItem(
            slug=note.slug, path=note.path,
            why="work started with no prediction on record, and coaching is strict "
                "— `magi decide --about {slug} --bet <supported|refuted|unknown> "
                "--text '<what they said>'`".format(slug=note.slug)))
    return out


def _lines(notes, now, stall_days: int, limit: int) -> list:
    line_notes = {note.slug: note for note in notes if note.kind == vocab.LINE}
    members: dict = {slug: [] for slug in line_notes}

    for note in notes:
        if note.kind == vocab.LINE:
            continue
        for slug in (note.lines or [UNLINED]):
            members.setdefault(slug, []).append(note)

    views = []
    for slug in sorted(members):
        owned = members[slug]
        header = line_notes.get(slug)
        stamps = [_last_post_time(note) for note in owned + ([header] if header else [])]
        stamps = [stamp for stamp in stamps if stamp is not None]
        last = max(stamps) if stamps else None
        open_count = sum(1 for note in owned
                         if note.kind == vocab.PROPOSITION and note.status in _OPEN_STATUSES)
        views.append(LineView(
            slug=slug,
            status=(header.status if header else "exploring"),
            purpose=str(header.frontmatter.get("purpose", "")) if header else "",
            open_count=open_count,
            total=len(owned),
            last_move=last.isoformat() if last else None,
            stalled=bool(last and (now - last).days >= stall_days),
            over_wip=open_count > limit,
        ))
    return views


def _queue(notes, lines) -> list:
    """The three interrupting events, plus the predictions a person owes."""
    items: list = []
    for note in sorted(notes, key=lambda n: n.slug):
        line = (note.lines or [UNLINED])[0]
        if (note.kind, note.status) in vocab.QUEUE_TRIGGERS:
            why = (_disputed_by(note) if note.status == "disputed" else
                   "two writers set this status within minutes of each other")
            items.append(QueueItem(kind=note.status, slug=note.slug, why=why, line=line))
        elif (note.kind == vocab.PROPOSITION
              and note.status in ("conjectured", "testing")
              and not note.frontmatter.get("bet")):
            items.append(QueueItem(
                kind="bet", slug=note.slug, line=line,
                why="work has started and nobody wrote down what they expect; "
                    "the prediction is only worth anything before the answer"))

    for view in lines:
        if view.over_wip:
            items.append(QueueItem(
                kind="wip", slug=view.slug, line=view.slug,
                why=f"{view.open_count} propositions open at once — more than one "
                    f"line's worth of work is happening under one name"))
        elif view.stalled and view.status not in ("dormant", "closed"):
            items.append(QueueItem(
                kind="phase", slug=view.slug, line=view.slug,
                why=f"nothing posted here since {view.last_move or 'ever'}; "
                    f"still {view.status}, or dormant?"))
    return items


def _disputed_by(note) -> str:
    """Who put this in dispute, read off the post that did it.

    A reviewer and a person are different events to a reader: one is a second
    opinion to weigh, the other is something they already know they did.
    """
    who = None
    for post in note.posts:
        if post.is_transition and post.dst == "disputed":
            who = post.host
    if who == vocab.REVIEWER:
        return "a reviewer rejected this after it was claimed solved"
    if who == vocab.HUMAN:
        return "you put this in dispute — it is waiting on what you decide"
    return "this was disputed after it was claimed solved"


def _proposals(root: Path) -> list:
    """What the slow loop has suggested and nobody has ruled on.

    Read here rather than kept anywhere: the ledger is the record, and a
    projection of it that could disagree is the thing this whole system is
    built to avoid. Failing to an empty list — a workspace that has never run
    `magi reflect` has no ledger, and that is not an error.
    """
    try:
        from .reflect import patterns, proposals as ledger

        items = [QueueItem(kind="proposal", slug=item.id, line=None,
                           why=f"[{item.kind}] {item.target}: {item.text}")
                 for item in ledger.open_proposals(root)]

        # A rule whose reason has gone quiet. Asked about rather than dropped:
        # ninety silent days may be the rule working, and only a person can
        # tell that apart from a rule nobody needed.
        quiet = {page.slug for page in patterns.stale(root)}
        items.extend(
            QueueItem(kind="retire", slug=rule.id, line=None,
                      why=f"nothing has matched \"{rule.pattern}\" for 90 days, and "
                          f"this rule came from it: {rule.text}")
            for rule in ledger.live_rules(root) if rule.pattern in quiet)
        return items
    except Exception:  # noqa: BLE001
        return []


def _debt(root: Path, notes, links=None) -> list:
    """Changes that happened without anybody writing down that they did."""
    links = _link_index(root) if links is None else links
    items: list = []
    for note in sorted(notes, key=lambda n: n.slug):
        for severity, message, _ in threads.validate(note):
            if severity in ("critical", "warning") and _is_bookkeeping(message):
                items.append(DebtItem(slug=note.slug, why=message, path=note.path))

        for message, when in _unrecorded_decisions(root, note):
            items.append(DebtItem(slug=note.slug, why=message, path=note.path,
                                  when=when))

        stale = _stale_derivation(root, note, links)
        if stale is not None:
            where, when = stale
            items.append(DebtItem(
                slug=note.slug, path=note.path, when=when, blocks=False,
                why=f"{where} changed after the last post here — the argument moved "
                    f"and the proposition did not"))
    return items


#: Which `validate` findings are debt rather than schema advice. Debt is
#: something a writer did and did not record; a missing `tags` field is not.
_DEBT_MARKERS = ("no post records the transition", "the last post left the note at",
                 "Illegal transition", "left the note at")


def _is_bookkeeping(message: str) -> bool:
    return any(marker in message for marker in _DEBT_MARKERS)


#: The file a person's decisions are transcribed into. Nothing else writes to
#: it, which is what makes "the slug is in there" a usable signal.
DECISIONS = "decisions.md"


def _unrecorded_decisions(root: Path, note) -> list:
    """Flips that were a person's call, with nothing on record that they made it.

    `vocab` says which transitions belong to a person — leaving `disputed`,
    `conflict` or `closed`, the three states that exist to stop the machine
    settling the question itself. It cannot say who typed the post, and it
    should not try: design-v2 §10 has the agent transcribe what the human
    decided, so every one of these posts is signed by whichever CLI was
    running.

    What can be checked is whether the decision was written down. Two ways
    count, and both are things a person actually does: a post signed `human`
    (they used the WebUI, or the agent signed on their behalf), or the slug
    appearing in `decisions.md`. Neither is proof — a determined agent can
    write either — and neither is meant to be. The point is that walking a
    proposition out of `disputed` leaves a trace somebody can audit, instead of
    the reviewer's objection quietly evaporating between two runs.
    """
    out = []
    for post in note.posts:
        if not post.is_transition:
            continue
        if not vocab.is_human_only(note.kind, post.src, post.dst):
            continue
        if post.host == vocab.HUMAN:
            continue
        if _decisions_mention(root, note.slug):
            continue
        out.append((f"{post.src} → {post.dst} is a person's call and nothing "
                    f"records that they made it — sign the post `--host human` "
                    f"or write it into {DECISIONS}", post.at))
    return out


def _decisions_mention(root: Path, slug: str) -> bool:
    """Whether `decisions.md` names this note, as a whole word.

    Substring matching is wrong here in the ordinary case, not an exotic one:
    slugs run `p-1`, `p-2`, … `p-10`, and a line about `p-10` contains `p-1`.
    That silently clears a real unrecorded decision on a different note.
    """
    import re

    # `_read_text`, not a strict decode: `decisions.md` is a file the design
    # tells a person to write in, Notepad still saves cp1252, and a decode
    # error here escaped the `except OSError` and took `magi next`, the Stop
    # hook and every v2 endpoint down with it. `_recent_decisions` reads the
    # same file the same way.
    text = _read_text(Path(root) / DECISIONS)
    if text is None:
        return False
    return re.search(rf"(?<![\w-]){re.escape(slug)}(?![\w-])", text) is not None


#: How far apart two files written by the same `git clone` may land. The
#: comparison below is between file mtimes, and git does not preserve them: a
#: fresh checkout stamps every file with the time it was written, seconds
#: apart. Anything inside this window is a checkout, not an edit.
CLONE_SKEW = dt.timedelta(minutes=5)


def _stale_derivation(root: Path, note, links):
    """The derivation that moved after this note did — `(path, when)` or None.

    Two comparisons, not one. The draft has to have moved after the note was
    last *discussed* (that is the finding: the argument moved on and the
    proposition did not) **and** after the note file itself was last written.

    The second is what survives a checkout. `git clone` gives every file the
    same mtime, so the first test alone fired on every note with a
    `derivation:` — post timestamps come from the file's contents and stay
    old, while the draft's mtime becomes now. `DebtItem` warns about exactly
    this: a gate that fires on every checkout is a gate somebody turns off.

    The timestamp comes back with the finding so the debt can be dated by the
    edit that caused it. Without it `_recent` falls back to the note's mtime,
    which is the one file this finding says did *not* change.
    """
    last = _last_post_time(note)
    if last is None:
        return None
    try:
        note_moved = dt.datetime.fromtimestamp(note.path.stat().st_mtime, dt.timezone.utc)
    except (OSError, AttributeError):
        note_moved = None
    for link in threads.as_list(note.frontmatter.get("derivation")):
        target = _resolve(root, str(link), links)
        if target is None:
            continue
        try:
            moved = dt.datetime.fromtimestamp(target.stat().st_mtime, dt.timezone.utc)
        except OSError:
            continue
        if moved <= last:
            continue
        if note_moved is not None and moved <= note_moved + CLONE_SKEW:
            continue
        try:
            where = target.relative_to(root).as_posix()
        except ValueError:
            where = target.name
        return where, moved.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


#: Where a `[[wikilink]]` may point, in the order a tie is broken. Drafts
#: first because that is what a `derivation:` names; `wiki/` last because a
#: concept card sharing a stem with a draft is the less likely target.
_LINK_DIRS = ("drafts", "threads", "wiki")


def _link_index(root: Path) -> dict:
    """`{stem: path}` for everywhere a wikilink can land — built once.

    The obvious implementation resolves each link with an `rglob`, which is
    one directory walk per link and turns a routine `magi sync` on a real
    library into thousands of them. One walk answers every link, which is the
    same trade `sync._scan_wiki` already makes for the same reason.
    """
    index: dict = {}
    for base in _LINK_DIRS:
        directory = Path(root) / base
        if not directory.is_dir():
            continue
        # Sorted: `rglob`'s order is arbitrary, so two files sharing a stem
        # would otherwise resolve differently on Windows and macOS for the
        # same repository.
        for found in sorted(directory.rglob("*.md")):
            index.setdefault(found.stem, found)
    return index


def _resolve(root: Path, link: str, links: dict | None = None):
    """A `[[wikilink]]` or path from a note's field to a real file."""
    name = link.strip().strip("[]").split("|")[0].strip()
    if not name or ".." in Path(name.replace("\\", "/")).parts:
        # A link is a name inside this workspace. `../../etc/passwd` is not a
        # broken link, it is a different question, and the answer is no.
        return None
    candidate = Path(root) / name
    if candidate.is_file():
        return candidate
    if not name.endswith(".md"):
        candidate = Path(root) / f"{name}.md"
        if candidate.is_file():
            return candidate
    index = _link_index(root) if links is None else links
    return index.get(Path(name).stem)


# ---------------------------------------------------------------- candidates


#: What each queue entry asks a person to do. The menu is computed; which item
#: gets picked is not — an agent reads this list against whatever the person
#: just said and chooses. Hard menu, soft choice (design-v2 §7).
_QUEUE_ACTION = {
    "disputed": ("does the objection stand?",
                 "magi thread status {slug} <supported|refuted|testing> --text '<why>'"),
    "conflict": ("which reading is right?",
                 "magi thread status {slug} <status> --text '<why>'"),
    "bet": ("say what you expect before the answer arrives",
            "magi thread status {slug} {status} --text '<prediction>'"),
    "wip": ("close something before opening anything here",
            "magi thread status <slug> <supported|refuted> --text '<why>'"),
    "phase": ("is this line still going, or is it dormant?",
              "magi thread status {slug} <active|writing|dormant> --text '<why>'"),
    "proposal": ("accept it, turn it down, or turn it into code",
                 "magi reflect accept {slug}  # or reject / promote"),
    "retire": ("is this rule still earning its place?",
               "magi reflect retire {slug}  # or leave it and it stays"),
}


def candidates(state: State) -> list:
    """Everything worth doing, most-owed first. Proposes; never acts.

    Debt is first because every other line of this list is computed from notes
    that are currently wrong. Then the human queue, because those are the only
    events allowed to interrupt somebody and they should not queue up behind
    machine work. Then the work itself.
    """
    actions: list = []

    dump = unfiled(state.root)
    if dump:
        first = dump[0][:60] + ("…" if len(dump[0]) > 60 else "")
        actions.append(Action(
            key="inbox", cost="llm",
            why=f"{len(dump)} unfiled line(s) in inbox/notes.md — starting \"{first}\"",
            run="read inbox/notes.md; turn each line into one of: "
                + ", ".join(WRITE_SURFACES)
                + "; quote the original in whatever it becomes, then remove the "
                  "line. Unsure — open it as a question."))

    for item in state.debt:
        actions.append(Action(
            key="debt", slug=item.slug, why=item.why, cost="llm",
            run=f"open threads/{item.slug}.md and post what happened"))

    for item in state.violations:
        # The rule's own id, so a person can go and read why it exists — or
        # retire it, which is the other half of having accepted it.
        source = f" (rule from {item.rule.source})" if item.rule.source else ""
        actions.append(Action(
            key="rule", slug=item.slug, cost="llm", why=item.why + source,
            run=f"fix it, or retire the rule: magi reflect list"))

    for item in state.queue:
        prompt, run = _QUEUE_ACTION.get(item.kind, ("decide", "magi thread status {slug} …"))
        status = "testing" if item.kind == "bet" else "<status>"
        actions.append(Action(
            key=item.kind, slug=item.slug, line=item.line, cost="human",
            why=f"{item.why} — {prompt}",
            run=run.format(slug=item.slug, status=status)))

    # A line already on the queue is not idle — it is waiting on the person,
    # and asking them for a new proposition on top of that is noise. A note can
    # name several lines, so every line it names is spoken for, not just the
    # first: a line whose only open work is shared would otherwise be invisible.
    by_slug = {note.slug: note for note in state.notes}
    spoken_for: set = set()
    for item in state.queue:
        note = by_slug.get(item.slug)
        spoken_for.update(note.lines if note and note.lines else [item.line])

    for view in state.lines:
        if view.status in ("closed", "dormant") or view.over_wip or view.stalled:
            continue
        if view.slug in spoken_for or view.open_count:
            continue
        scope = "" if view.slug == UNLINED else f" --line {view.slug}"
        name = "this project" if view.slug == UNLINED else view.slug
        actions.append(Action(
            key="empty-line", slug=view.slug, line=view.slug, cost="human",
            why=f"{name} has nothing open — what is the next question?",
            run=f"magi thread new <slug> --kind proposition{scope} …"))

    for slug in unreviewed(state):
        note = by_slug.get(slug)
        if note is None:
            # `pending()` reads the directory; this projection may have been
            # narrowed to one line. A claim outside it is somebody else's turn.
            continue
        actions.append(Action(
            key="review", slug=slug, cost="llm",
            line=(note.lines or [None])[0] if note else None,
            why=f"{slug} says it is solved and nobody independent has read it",
            run=f"magi review {slug}"))

    for view in state.lines:
        if view.slug in spoken_for or view.status in ("closed", "dormant"):
            continue
        oldest = _oldest_open(state.notes, view.slug)
        if oldest is None:
            continue
        since = (_last_post_time(oldest) or dt.datetime.min.replace(
            tzinfo=dt.timezone.utc)).date().isoformat()
        actions.append(Action(
            key="work", slug=oldest.slug, line=view.slug, cost="llm",
            why=f"{oldest.slug} has been {oldest.status} since {since} — "
                f"post what you found, or move it",
            run=f"magi thread status {oldest.slug} <status> --text '<what happened>'"))
    return actions


def _oldest_open(notes, line: str):
    """The open proposition on this line that has waited longest.

    One per line, deliberately. A router that lists every open proposition is
    a router that lists the whole project, and then the ranking it was for
    stops meaning anything.
    """
    owned = [note for note in notes
             if note.kind == vocab.PROPOSITION
             and note.status in _OPEN_STATUSES
             and line in (note.lines or [UNLINED])]
    if not owned:
        return None
    floor = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    return min(owned, key=lambda note: _last_post_time(note) or floor)


# ---------------------------------------------------------------- rendering


def _line_row(view: LineView) -> str:
    marks = []
    if view.over_wip:
        marks.append(f"WIP {view.open_count}")
    elif view.open_count:
        marks.append(f"{view.open_count} open")
    if view.stalled:
        marks.append("quiet")
    tail = f"  ({', '.join(marks)})" if marks else ""
    return f"  {view.slug:<24} {view.status:<10}{tail}"


def render(state: State, actions: list) -> str:
    """The human-readable `magi next`.

    Quiet by design: with no debt, no queue and nothing waiting, this prints
    the open questions and stops. A router that always finds something to say
    trains people to stop reading it.
    """
    out: list = []
    if state.lines:
        out.append("Lines")
        out.extend(_line_row(view) for view in state.lines)
        out.append("")

    if not state.notes:
        # `next` is the single entry, so in a library that has a wiki and no
        # research state yet it has to point at what there is rather than
        # report that nothing is owed — which is true and useless.
        return ("No propositions yet — this library has knowledge but nothing "
                "it is currently trying to find out.\n"
                "  magi thread new <slug> --kind proposition --title '<claim>' "
                "--purpose '<why now>'\n"
                "  magi sync    # what the library itself needs")

    if not actions:
        questions = state.open_questions
        if questions:
            out.append("Nothing owed. Open questions:")
            out.extend(f"  {note.slug}: {note.frontmatter.get('purpose', '')}"
                       for note in questions)
        else:
            out.append("Nothing owed and no open questions.")
        return "\n".join(out)

    labels = {"certain": "", "llm": " [needs an agent]", "human": " [needs you]"}
    out.append("Next")
    for index, action in enumerate(actions, 1):
        out.append(f"  {index}. {action.why}{labels.get(action.cost, '')}")
        out.append(f"     {action.run}")
    return "\n".join(out)


def to_json(state: State, actions: list) -> dict:
    return {
        "root": str(state.root),
        "lines": [vars(view) for view in state.lines],
        "pinned": pinned(state),
        "queue": [vars(item) for item in state.queue],
        "debt": [{"slug": item.slug, "why": item.why,
                  "path": str(item.path) if item.path else None}
                 for item in state.debt],
        "actions": [vars(action) for action in actions],
        "open_questions": [note.slug for note in state.open_questions],
    }



# ---------------------------------------------------------------- focus


def focus(root, line: str) -> set:
    """Workspace-relative paths a research line is currently looking at.

    A line is a *view* over a shared library, not a library of its own
    (design-v2 §2), so "what belongs to this line" cannot be a directory. It
    has to be derived, and the only honest source is what the line's own notes
    point at: the propositions and questions that name it, the drafts they use
    as derivations, and the concept cards they are stated in terms of.

    One hop, not a closure. Two hops from a concept card reaches most of the
    wiki, and a focus set that contains everything ranks nothing.
    """
    root = Path(root)
    projection = load(root)
    seeds = [note for note in projection.notes
             if note.slug == line or line in (note.lines or [])]

    links = _link_index(root)
    found: set = set()
    for note in seeds:
        found.add(_relative(root, note.path))
        text = note.body or ""
        for link in _wikilinks(text) + [str(x) for x in
                                        threads.as_list(note.frontmatter.get("derivation"))
                                        + threads.as_list(note.frontmatter.get("depends_on"))]:
            target = _resolve(root, link, links)
            if target is not None:
                found.add(_relative(root, target))
    return {rel for rel in found if rel}


def _relative(root: Path, path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return ""


def _wikilinks(text: str) -> list:
    import re

    return re.findall(r"\[\[([^\]|#]+)", text or "")


#: Where a person puts anything, in any order, whenever it occurs to them.
NOTES = ("inbox", "notes.md")

#: The five places a dumped line can end up. Named here because the routing is
#: the agent's judgement, and a list of five is the whole of the instruction.
WRITE_SURFACES = ("question", "proposition", "decision", "a post on an existing note",
                  "a task in beads")


def unfiled(root) -> list:
    """Lines the person dumped that nobody has filed yet.

    The dump is deliberately the only place they are asked to be tidy in — no
    format, no categories, no deciding where something goes at the moment they
    think of it. Filing is the agent's job, and it is `next`'s first item when
    there is anything here: a person's words waiting behind machine
    bookkeeping is the wrong signal about whose time is scarce.

    Filed lines are removed by whoever filed them, so what is left is exactly
    what is still unclassified. Nothing is lost by the removal: the thing the
    line became quotes it.
    """
    from .init_workspace import NOTES_STARTER

    text = _read_text(Path(root).joinpath(*NOTES))
    if text is None:
        return []
    # The starter text is scaffolding, not something somebody wrote — matched
    # line by line rather than by splitting on blank lines. The split version
    # dropped two paragraphs instead of one, so a line appended straight after
    # the starter (which is what appending to a file does) landed inside the
    # part being thrown away and this returned nothing at all.
    scaffold = {line.strip() for line in NOTES_STARTER.splitlines() if line.strip()}
    return [line.strip() for line in text.splitlines()
            if line.strip() and line.strip() not in scaffold
            and not line.lstrip().startswith("#")]


def _read_text(path: Path):
    """A file's text, or `None` when there is no file.

    `notes.md` is the one file the design tells a person to type into freely,
    and Notepad still writes cp1252 by default. A decode error there took down
    `magi next` entirely — so the bytes come back with replacements rather than
    an exception: slightly mangled words are worth more than no words.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def dump(root, text: str):
    """Append what somebody just said to `inbox/notes.md`, verbatim.

    The writer of the file `unfiled()` reads, kept next to it so the two cannot
    disagree about what a dumped line looks like. The box asks for no format,
    so this adds none beyond the `-` that makes the file read as a list.

    Appends rather than rewrites, and keeps the file's own line endings: a text
    box that reformats somebody's other two hundred lines because they typed
    one is a text box they stop using.
    """
    from .core.wiki_common import file_newline

    path = Path(root).joinpath(*NOTES)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return path
    # A `#` is *not* passed through: `unfiled()` reads a leading `#` as the
    # starter's scaffolding and drops the line, so a heading-shaped thought
    # would be written down and then never surface again. The box promises no
    # format; the one thing it owes in return is that what goes in comes back.
    chunk = "\n".join(line if line.startswith(("-", "*")) else f"- {line}"
                      for line in lines) + "\n"
    # Under a lock, like every other append in this codebase: Windows does not
    # implement `O_APPEND` atomically, and this is the one file a person's
    # browser and their agent write to at the same moment.
    from filelock import FileLock

    lock = path.with_name(path.name + ".lock")
    with FileLock(str(lock), timeout=30):
        existing = (path.read_text(encoding="utf-8", errors="replace")
                    if path.is_file() else "")
        if existing and not existing.endswith("\n"):
            chunk = "\n" + chunk
        ending = file_newline(path) if path.is_file() else None
        with open(path, "a", encoding="utf-8", newline=ending) as handle:
            handle.write(chunk)
    return path


def unreviewed(state: State) -> list:
    """Claims that say they are solved and have had no independent reader.

    Imported lazily and failing to an empty list: `magi next` has to answer in
    a workspace where the reviewer's dependencies are missing, and "I could not
    work out what needs reviewing" is not a reason to refuse to say anything at
    all.
    """
    try:
        from . import review as review_mod

        return review_mod.pending(state.root)
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------- feed


@dataclass
class Entry:
    """One post, lifted out of the note it lives in."""
    at: str
    host: str
    slug: str
    kind: str
    line: str | None
    src: str | None
    dst: str | None
    text: str


def feed(state: State, since=None, line: str | None = None,
         author: str | None = None) -> list:
    """Every post, newest first. Derived, never stored.

    There is no journal in v2 and this is why: a journal is a second place the
    same events are written, and the two drift the first time somebody edits a
    note without touching the log. The posts *are* the record; reading them in
    time order is a view over the notes, not a file.
    """
    entries: list = []
    for note in state.notes:
        for post in note.posts:
            if line and post.line != line and line not in (note.lines or []):
                continue
            if author and post.host != author:
                continue
            when = parse_at(post.at)
            if since is not None and (when is None or when < since):
                continue
            entries.append(Entry(at=post.at, host=post.host, slug=note.slug,
                                 kind=note.kind or "", line=post.line,
                                 src=post.src, dst=post.dst, text=post.text))
    entries.sort(key=lambda e: (parse_at(e.at) or dt.datetime.min.replace(
        tzinfo=dt.timezone.utc)), reverse=True)
    return entries


def render_feed(entries) -> str:
    if not entries:
        return "No posts yet."
    out = []
    for entry in entries:
        move = f"  {entry.src} → {entry.dst}" if entry.src and entry.dst else ""
        signature = entry.host + (f"/{entry.line}" if entry.line else "")
        out.append(f"{entry.at}  {entry.slug:<24} {signature}{move}")
        first = (entry.text or "").strip().splitlines()
        if first:
            out.append(f"    {first[0][:100]}")
    return "\n".join(out)


# ---------------------------------------------------------------- MAP


MAP_PATH = ("output", "MAP.md")


#: A closed proposition: the bet is now checkable against what happened.
_SETTLED = {"supported", "refuted"}


def retrospective(state: State, limit: int = 8) -> dict:
    """What the predictions were worth, and what was decided lately.

    Nobody goes back to look. The design's answer is that the map does it
    unasked — a hit rate a person never sees trains nothing, and the whole
    point of asking for a prediction before the work is that it can be checked
    after.

    `unknown` is not scored. It is the honest prior, and counting it as a miss
    would teach people to guess instead of saying they do not know — which is
    the one answer that keeps the rest of the numbers meaningful.
    """
    scored, unknown, late = [], 0, 0
    for note in state.notes:
        bet = note.frontmatter.get("bet")
        if note.kind != vocab.PROPOSITION or not bet or note.status not in _SETTLED:
            continue
        settled_at, bet_at = None, None
        for index, post in enumerate(note.posts):
            if post.is_transition and post.dst in _SETTLED:
                settled_at = index
            if post.field == "bet":
                bet_at = index
        if settled_at is not None and bet_at is not None and bet_at > settled_at:
            # Written after the answer arrived. Not a prediction, and counting
            # it as one lets the headline number inflate for free — the whole
            # reason a bet is asked for before the work is that it can be
            # checked after. A bet with no event behind it (set when the note
            # was created) predates everything and still counts.
            late += 1
            continue
        if bet == "unknown":
            unknown += 1
            continue
        scored.append({"slug": note.slug, "bet": bet, "outcome": note.status,
                       "hit": bet == note.status,
                       "at": note.posts[settled_at].at if settled_at is not None else ""})

    hits = sum(1 for row in scored if row["hit"])
    # Most recently settled last. Notes arrive in `note_paths` order, which is
    # alphabetical, so slicing without this showed `p-02…p-09` and silently
    # dropped the two oldest slugs rather than the two oldest bets.
    scored.sort(key=lambda row: row["at"])
    return {
        "bets": scored[-limit:],
        "hits": hits,
        "scored": len(scored),
        "unknown": unknown,
        "late": late,
        "rate": round(hits / len(scored), 2) if scored else None,
        "decisions": _recent_decisions(state.root, limit),
    }


def _recent_decisions(root, limit: int) -> list:
    """The headings of the last few entries in `decisions.md`."""
    text = _read_text(Path(root) / DECISIONS)
    if text is None:
        return []
    headings = [line.strip() for label, line in
                md_blocks.classify_lines(md_blocks.normalize_newlines(text))
                if label != md_blocks.CODE and line.startswith("## ")]
    return headings[-limit:]


def budget(root) -> dict:
    """What MAGI's own calls have cost this week.

    Read on demand and stored nowhere, like everything else here. Failing to
    an empty answer rather than raising: a workspace whose ledger is missing or
    unreadable still has to be able to draw its map.
    """
    try:
        from .core import ledger
        from .core.config_loader import get as config_get
        from .core.config_loader import load_config

        config = load_config(start=root)
        if not bool(config_get(config, "research.llm_calls", True)):
            return {"off": True}
        return ledger.summary(
            root, limit=config_get(config, "research.weekly_calls",
                                   ledger.DEFAULT_WEEKLY))
    except Exception:  # noqa: BLE001
        return {}


def pinned(state: State) -> list:
    """Notes a person pinned into the graph's skeleton, in slug order.

    The same `skeleton: true` the graph reads. Surfaced here because MAP.md and
    the map view are two renderings of one directory (design-v2 §12), and a pin
    that only one of them can see is a third thing pretending to be part of the
    first.
    """
    from .kb.llmwiki import _is_pinned

    return [note.slug for note in sorted(state.notes, key=lambda n: n.slug)
            if _is_pinned(note.frontmatter.get("skeleton"))]


def render_map(state: State, now=None) -> str:
    """`MAP.md`: the two things a person is supposed to look at.

    Per-line state, and the decisions only they can make. Maintenance is
    deliberately absent — a map that also lists chores is a map nobody reads,
    and the chores already have `magi next`.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    out = ["# MAP", "",
           f"> Rendered from `threads/` at {now.strftime('%Y-%m-%d %H:%M')} UTC. "
           "Editing this file changes nothing — the status lives in the note.",
           "", "## Lines", ""]

    if not state.lines:
        out.append("No lines yet.")
    else:
        out.append("| line | phase | open | last move | |")
        out.append("|---|---|---|---|---|")
        for view in state.lines:
            flags = " ".join(filter(None, [
                "**over WIP**" if view.over_wip else "",
                "quiet" if view.stalled else ""]))
            moved = (view.last_move or "")[:10]
            out.append(f"| [[{view.slug}]] | {view.status} | {view.open_count} "
                       f"| {moved} | {flags} |")

    out.extend(["", "## Decisions waiting on you", ""])
    # WIP is a limit `next` enforces, not a decision anybody is waiting on
    # (design-v2 §6). Listing it here would make the queue a chore list, which
    # is the one thing this section is not.
    decisions = [item for item in state.queue if item.kind != "wip"]
    if not decisions:
        out.append("Nothing. Every open question is somebody else's turn.")
    else:
        for item in decisions:
            out.append(f"- **{item.kind}** [[{item.slug}]] — {item.why}")
    kept = pinned(state)
    if kept:
        out.extend(["", "## Pinned", "",
                    "Kept in the graph's skeleton whatever their degree — "
                    "`skeleton: true` in the note.", ""])
        out.extend(f"- [[{slug}]]" for slug in kept)

    back = retrospective(state)
    if back["scored"] or back["unknown"] or back["late"] or back["decisions"]:
        out.extend(["", "## Looking back", ""])
        if back["rate"] is not None:
            out.append(f"Predictions: **{back['hits']}/{back['scored']}** right"
                       + (f", {back['unknown']} recorded as \"don't know\""
                          if back["unknown"] else "") + ".")
            out.append("")
            for row in back["bets"]:
                mark = "✓" if row["hit"] else "✗"
                out.append(f"- {mark} [[{row['slug']}]] — you said {row['bet']}, "
                           f"it came out {row['outcome']}")
        elif back["unknown"]:
            out.append(f"{back['unknown']} prediction(s) recorded as \"don't know\" — "
                       "an honest prior, and not scored.")
        if back["late"]:
            out.append("")
            out.append(f"{back['late']} bet(s) written down after the answer was "
                       "already in — not scored, and not a prediction.")
        if back["decisions"]:
            out.extend(["", "Decisions, most recent last:", ""])
            out.extend(f"- {heading[3:]}" for heading in back["decisions"])

    spent = budget(state.root)
    if spent.get("off"):
        out.extend(["", "## Spending", "",
                    "MAGI's own model calls are switched off "
                    "(`research.llm_calls: false`). Nothing is reviewed until "
                    "somebody turns them back on."])
    elif "limit" in spent:
        line = (f"{spent['spent']}/{spent['limit']} model calls this week "
                f"({spent['week']}), refilling {spent['until']}.")
        if spent.get("over"):
            line += (" The reviewer is off until then — and nothing counts as "
                     "reviewed in the meantime.")
        out.extend(["", "## Spending", "", line])

    out.append("")
    return "\n".join(out)


def write_map(state: State) -> Path:
    """Render `output/MAP.md`. Returns the path written."""
    from .core.wiki_common import atomic_write

    path = state.root.joinpath(*MAP_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, render_map(state))
    return path


# ---------------------------------------------------------------- closing


#: How close together two writers have to set a status before it counts as
#: them disagreeing rather than one following the other. Five minutes is long
#: enough to cover two agents working the same note in one session and short
#: enough that tomorrow's revision is not called a conflict.
CONFLICT_WINDOW = dt.timedelta(minutes=5)

#: How far back `--close` treats a note as "this session's work". Debt older
#: than this is reported and does not block: a hook that refuses to let anyone
#: stop until a library's whole history is tidy is a hook people switch off.
CLOSE_WINDOW_HOURS = 12


@dataclass
class CloseReport:
    blocking: list = field(default_factory=list)
    older: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    unreviewed: list = field(default_factory=list)
    map_path: str | None = None

    @property
    def ok(self) -> bool:
        """Whether the session may end.

        A conflict counts. The agent cannot resolve one — that is a person's
        call — but it just caused one, and stopping without saying so leaves
        the human to find it in a file. Blocking once is how they hear about it.
        """
        return not self.blocking and not self.conflicts


def detect_conflicts(notes, window=CONFLICT_WINDOW) -> list:
    """Notes where two different hosts set the status inside the window.

    Last-writer-wins is the rule for an ordinary flip, and it is fine: the
    second writer read the first one's post. What it cannot settle is two
    writers moving the same note at the same time, neither having seen the
    other — that is not a status, it is a disagreement, and only a person can
    say which reading was right.
    """
    found = []
    for note in notes:
        if note.status == vocab.CONFLICT:
            continue
        moves = [(parse_at(post.at), post) for post in note.posts if post.is_transition]
        moves = [(when, post) for when, post in moves if when is not None]

        # Only look after the last time somebody walked this note *out* of
        # `conflict`. Without that cut the original colliding pair sits in the
        # file forever, so every later run re-detects it and flips the note
        # straight back — silently undoing a decision a person made, which is
        # the one thing this status exists to protect.
        resolved = max((when for when, post in moves if post.src == vocab.CONFLICT),
                       default=None)
        if resolved is not None:
            moves = [(when, post) for when, post in moves if when > resolved]

        for (first_at, first), (second_at, second) in zip(moves, moves[1:]):
            # A reviewer's verdict is a *response* to the flip before it, not
            # a second writer who had not read the first. Calling it a conflict
            # rewrote `disputed` — the status the design puts a claim in so a
            # person can rule on it — into `conflict`, which says something
            # else entirely and which only a person can leave.
            if vocab.REVIEWER in (first.host, second.host):
                continue
            if first.host != second.host and abs(second_at - first_at) <= window:
                found.append((note, first, second))
                break
    return found


def close(root, window_hours: int = CLOSE_WINDOW_HOURS, write: bool = True,
          host: str = "magi", now=None) -> CloseReport:
    """The gate a session has to pass before it stops.

    Two things happen here and only here. Contended statuses become
    `conflict` — the CLI is the only writer allowed to set it, because it is
    never a judgement, only an observation that two writers collided. And the
    projection is checked for debt: something was done and not written down.

    Recent debt blocks; older debt is listed. The split is by file mtime, not
    by a session log, because a session log is one more thing to keep true.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    state = _reload(root)
    report = CloseReport()

    for note, first, second in detect_conflicts(state.notes):
        if not write:
            report.conflicts.append(note.slug)
            continue
        try:
            threads.set_status(
                note.path, vocab.CONFLICT,
                f"{first.host} and {second.host} both set this within "
                f"{int(CONFLICT_WINDOW.total_seconds() // 60)} minutes "
                f"({first.src} → {first.dst}, then {second.src} → {second.dst}). "
                "Neither had read the other; which reading is right?",
                host=host)
        except Exception as exc:  # noqa: BLE001
            # A note with a status no table knows, a file that vanished, a lock
            # somebody else is holding. Any of them is one note's problem; the
            # gate covers the whole workspace and must still answer for the rest.
            report.blocking.append(DebtItem(
                slug=note.slug, path=note.path,
                why=f"two writers collided here and the conflict could not be "
                    f"recorded ({exc.__class__.__name__}: {exc}) — settle it by hand"))
            continue
        report.conflicts.append(note.slug)
    if report.conflicts:
        state = _reload(root)

    cutoff = now - dt.timedelta(hours=window_hours)
    for item in state.debt:
        if item.blocks and _recent(item, cutoff):
            report.blocking.append(item)
        else:
            report.older.append(item)

    # No window on these. Debt is dated by the event that made it, so old debt
    # can be listed rather than blocked; a rule violation is a state the
    # workspace is in *now*, and being in it for a while does not make it fine.
    for item in state.violations:
        source = f" (rule from {item.rule.source})" if item.rule.source else ""
        report.blocking.append(DebtItem(slug=item.slug, why=item.why + source))

    drift = block_drift(root)
    if drift:
        report.blocking.append(DebtItem(slug="AGENTS.md", why=drift))

    # Named, not run. Design-v2 §11 triggers the reviewer here, and it will —
    # but a headless call per claim is minutes of latency and real money inside
    # a stop hook, and neither has a budget gate until M6. Naming them keeps
    # the loop closed: `magi next` proposes the review, and an agent that is
    # still working runs it. A stop hook that takes five minutes is a stop hook
    # somebody uninstalls.
    report.unreviewed = unreviewed(state)

    if write:
        report.map_path = str(write_map(state))
    return report


def block_drift(root) -> str:
    """Whether `AGENTS.md` still says what the ledger says. Empty when it does.

    The block's content is template + accepted rules, and the two are written
    at different moments: a verdict is recorded, then the block is re-rendered.
    A crash in between leaves them disagreeing, and a person reading either one
    has no way to tell. Checking costs one file read.
    """
    try:
        from .core import managed
        from .reflect import proposals

        agents = Path(root) / "AGENTS.md"
        if not agents.is_file():
            return ""
        current = managed.read(agents.read_text(encoding="utf-8", errors="replace"))
        if current is None:
            return ""
        live = proposals.live_rules(root)
        missing = [rule.text for rule in live
                   if " ".join(rule.text.split()) not in current]
        if missing:
            return (f"AGENTS.md is missing {len(missing)} accepted rule(s) — the "
                    f"ledger says they were accepted and the block does not show "
                    f"them. `magi install` rewrites it. First: {missing[0]!r}")
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _reload(root):
    """The projection as the workspace's own configuration defines it.

    The gate has to agree with `magi next` about what counts as debt, and
    under `coaching: strict` that includes a missing prediction. A gate reading
    defaults while the router reads config is two answers to one question.
    """
    from .core.config_loader import get as config_get
    from .core.config_loader import load_config

    config = load_config(start=root)
    return load(root,
                wip_limit=config_get(config, "research.wip_limit", WIP_LIMIT),
                stall_days=config_get(config, "research.stall_days", STALL_DAYS),
                coaching=config_get(config, "research.coaching", vocab.DEFAULT_COACHING))


def _recent(item: DebtItem, cutoff) -> bool:
    """Whether this debt is this session's, and so allowed to block.

    The event's own timestamp wins when there is one: a flip posted six months
    ago is six months old however recently the file was checked out. Only debt
    with no event to date it falls back to the file's mtime.
    """
    when = parse_at(item.when) if item.when else None
    if when is not None:
        return when >= cutoff
    if item.path is None:
        return True
    try:
        moved = dt.datetime.fromtimestamp(Path(item.path).stat().st_mtime, dt.timezone.utc)
    except OSError:
        return True
    return moved >= cutoff


def render_close(report: CloseReport) -> str:
    out = []
    for slug in report.conflicts:
        out.append(f"conflict: {slug} — two writers collided; it is on the decision queue")
    if report.blocking:
        out.append("Not finished — this happened and was not written down:")
        out.extend(f"  {item.slug}: {item.why}" for item in report.blocking)
        out.append("")
        out.append("Post what you did (`magi thread post`) or move the status "
                   "(`magi thread status`), then close again.")
    else:
        out.append("Bookkeeping is current.")
    if report.unreviewed:
        out.append("")
        out.append(f"Claiming to be solved, nobody independent has read them "
                   f"({len(report.unreviewed)}):")
        out.extend(f"  magi review {slug}" for slug in report.unreviewed[:5])
    if report.older:
        out.append("")
        out.append(f"Older debt, not blocking ({len(report.older)}):")
        out.extend(f"  {item.slug}: {item.why}" for item in report.older[:5])
    if report.map_path:
        out.append("")
        out.append(f"MAP written to {report.map_path}")
    return "\n".join(out)


def hook_payload(report: CloseReport) -> dict:
    """What a Claude Code Stop hook returns to keep a session from ending.

    The reason is read by the agent, not by a person, so it says what to do
    rather than what went wrong.

    Two different things stop a session and they need two different sentences.
    Unrecorded work is the agent's to clear: post it, or move the status. A
    conflict is not — two writers collided, only a person can say which
    reading was right, and it is already on the decision queue. Telling the
    agent to "post what happened" about a conflict asks it to clear something
    it has no way to clear, which is how a stop hook turns into a loop.
    """
    if report.ok:
        return {}
    parts = []
    if report.blocking:
        parts.append("Bookkeeping is not finished. Post what happened, or move "
                     "the status with `magi thread status`, then stop again:\n"
                     + "\n".join(f"- {item.slug}: {item.why}"
                                 for item in report.blocking))
    if report.conflicts:
        parts.append("Two writers moved the same note at the same time. This is "
                     "a person's call and is already on the decision queue — say "
                     "so, and do not resolve it yourself:\n"
                     + "\n".join(f"- {slug}" for slug in report.conflicts))
    return {"decision": "block", "reason": "\n\n".join(parts)}


# ---------------------------------------------------------------- command


def _root_of(topic_dir):
    from .core.workspace import find_workspace_root

    root = Path(topic_dir).resolve() if topic_dir else find_workspace_root()
    if root is None:
        raise SystemExit("no workspace found (run inside a topic or pass --topic-dir)")
    return Path(root)


def loaded(root):
    from .core.config_loader import get as config_get
    from .core.config_loader import load_config

    config = load_config(start=root)
    return load(root,
                wip_limit=config_get(config, "research.wip_limit", WIP_LIMIT),
                stall_days=config_get(config, "research.stall_days", STALL_DAYS),
                coaching=config_get(config, "research.coaching", vocab.DEFAULT_COACHING))


def _next(argv) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        prog="magi next",
        description="What to do next, derived from the notes. Proposes; never acts.")
    parser.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    parser.add_argument("--line", help="Only this research line")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    state = loaded(_root_of(args.topic_dir))
    if args.line:
        # The notes first, and everything else from them. Narrowing only the
        # derived lists left `open_questions` answering for the whole project,
        # and dropped debt on the line's *own* note — a line note has no
        # `line:` field, so "does it name this line" was false for the one note
        # that is this line.
        state.notes = [note for note in state.notes
                       if note.slug == args.line or args.line in (note.lines or [])]
        kept = {note.slug for note in state.notes}
        state.lines = [view for view in state.lines if view.slug == args.line]
        state.queue = [item for item in state.queue
                       if item.line == args.line or item.slug in kept]
        state.debt = [item for item in state.debt if item.slug in kept]
        state.violations = [item for item in state.violations if item.slug in kept]

    actions = candidates(state)
    if args.line:
        # An action that names another line is not this line's work. Actions
        # that name none — the dump, the debt — belong to the project rather
        # than to a line, and stay.
        actions = [action for action in actions if action.line in (None, args.line)]
    if args.json:
        print(json.dumps(to_json(state, actions), ensure_ascii=False, indent=2))
    else:
        print(render(state, actions))
    return 0


def _feed(argv) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(
        prog="magi feed",
        description="Every post, newest first — the record, read in time order.")
    parser.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    parser.add_argument("--since", help="ISO date or timestamp; only posts after it")
    parser.add_argument("--line", help="Only posts from this research line")
    parser.add_argument("--author", help="Only posts signed by this host")
    parser.add_argument("-n", type=int, default=40, help="Max entries (default 40)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    since = parse_at(args.since) if args.since else None
    if args.since and since is None:
        raise SystemExit(f"--since {args.since!r} is not a date I can read "
                         "(try 2026-08-01 or 2026-08-01T12:00:00Z)")

    state = loaded(_root_of(args.topic_dir))
    entries = feed(state, since=since, line=args.line, author=args.author)[:args.n]
    if args.json:
        print(json.dumps([vars(entry) for entry in entries], ensure_ascii=False, indent=2))
    else:
        print(render_feed(entries))
    return 0


def main(argv=None) -> int:
    """`magi next` and `magi feed` — two views of one pass over the notes."""
    argv = list(argv or [])
    if argv and argv[0] == "feed":
        return _feed(argv[1:])
    if argv and argv[0] == "next":
        argv = argv[1:]
    return _next(argv)


if __name__ == "__main__":
    raise SystemExit(main())
