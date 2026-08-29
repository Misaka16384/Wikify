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

from .core import vocab
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
    """Work that happened and was not written down."""
    slug: str
    why: str
    path: Path | None = None


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
         now=None) -> State:
    """Read `threads/` once and derive everything from it."""
    root = Path(root)
    now = now or dt.datetime.now(dt.timezone.utc)
    notes = [threads.read_note(path) for path in threads.note_paths(root)]

    state = State(root=root, notes=notes, wip_limit=wip_limit or WIP_LIMIT)
    state.lines = _lines(notes, now=now, stall_days=stall_days, limit=state.wip_limit)
    state.queue = _queue(notes, state.lines)
    state.debt = _debt(root, notes)
    return state


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
            why = ("a reviewer rejected this after it was claimed solved"
                   if note.status == "disputed" else
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


def _debt(root: Path, notes, links=None) -> list:
    """Changes that happened without anybody writing down that they did."""
    links = _link_index(root) if links is None else links
    items: list = []
    for note in sorted(notes, key=lambda n: n.slug):
        for severity, message, _ in threads.validate(note):
            if severity in ("critical", "warning") and _is_bookkeeping(message):
                items.append(DebtItem(slug=note.slug, why=message, path=note.path))

        for message in _unrecorded_decisions(root, note):
            items.append(DebtItem(slug=note.slug, why=message, path=note.path))

        stale = _stale_derivation(root, note, links)
        if stale is not None:
            items.append(DebtItem(
                slug=note.slug, path=note.path,
                why=f"{stale} changed after the last post here — the argument moved "
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
        out.append(f"{post.src} → {post.dst} is a person's call and nothing "
                   f"records that they made it — sign the post `--host human` "
                   f"or write it into {DECISIONS}")
    return out


def _decisions_mention(root: Path, slug: str) -> bool:
    path = Path(root) / DECISIONS
    try:
        return slug in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _stale_derivation(root: Path, note, links):
    """The derivation file that moved after this note last did, if any."""
    last = _last_post_time(note)
    if last is None:
        return None
    for link in threads.as_list(note.frontmatter.get("derivation")):
        target = _resolve(root, str(link), links)
        if target is None:
            continue
        try:
            moved = dt.datetime.fromtimestamp(target.stat().st_mtime, dt.timezone.utc)
        except OSError:
            continue
        if moved > last:
            try:
                return target.relative_to(root).as_posix()
            except ValueError:
                return target.name
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
        for found in directory.rglob("*.md"):
            index.setdefault(found.stem, found)
    return index


def _resolve(root: Path, link: str, links: dict | None = None):
    """A `[[wikilink]]` or path from a note's field to a real file."""
    name = link.strip().strip("[]").split("|")[0].strip()
    if not name:
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
}


def candidates(state: State) -> list:
    """Everything worth doing, most-owed first. Proposes; never acts.

    Debt is first because every other line of this list is computed from notes
    that are currently wrong. Then the human queue, because those are the only
    events allowed to interrupt somebody and they should not queue up behind
    machine work. Then the work itself.
    """
    actions: list = []

    for item in state.debt:
        actions.append(Action(
            key="debt", slug=item.slug, why=item.why, cost="llm",
            run=f"open threads/{item.slug}.md and post what happened"))

    for item in state.queue:
        prompt, run = _QUEUE_ACTION.get(item.kind, ("decide", "magi thread status {slug} …"))
        status = "testing" if item.kind == "bet" else "<status>"
        actions.append(Action(
            key=item.kind, slug=item.slug, line=item.line, cost="human",
            why=f"{item.why} — {prompt}",
            run=run.format(slug=item.slug, status=status)))

    # A line already on the queue is not idle — it is waiting on the person,
    # and asking them for a new proposition on top of that is noise.
    spoken_for = {item.line for item in state.queue}

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
             and (note.lines or [UNLINED])[0] == line]
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
    if not state.queue:
        out.append("Nothing. Every open question is somebody else's turn.")
    else:
        for item in state.queue:
            out.append(f"- **{item.kind}** [[{item.slug}]] — {item.why}")
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
    map_path: str | None = None

    @property
    def ok(self) -> bool:
        return not self.blocking


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
        for (first_at, first), (second_at, second) in zip(moves, moves[1:]):
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
        report.conflicts.append(note.slug)
        if write:
            threads.set_status(
                note.path, vocab.CONFLICT,
                f"{first.host} and {second.host} both set this within "
                f"{int(CONFLICT_WINDOW.total_seconds() // 60)} minutes "
                f"({first.src} → {first.dst}, then {second.src} → {second.dst}). "
                "Neither had read the other; which reading is right?",
                host=host)
    if report.conflicts:
        state = _reload(root)

    cutoff = now - dt.timedelta(hours=window_hours)
    for item in state.debt:
        if _touched_since(item.path, cutoff):
            report.blocking.append(item)
        else:
            report.older.append(item)

    if write:
        report.map_path = str(write_map(state))
    return report


def _reload(root):
    return load(root)


def _touched_since(path, cutoff) -> bool:
    if path is None:
        return True
    try:
        moved = dt.datetime.fromtimestamp(Path(path).stat().st_mtime, dt.timezone.utc)
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
    """
    if report.ok:
        return {}
    lines = [f"- {item.slug}: {item.why}" for item in report.blocking]
    return {
        "decision": "block",
        "reason": ("Bookkeeping is not finished. Post what happened, or move the "
                   "status with `magi thread status`, then stop again:\n"
                   + "\n".join(lines)),
    }


# ---------------------------------------------------------------- command


def _root_of(topic_dir):
    from .core.workspace import find_workspace_root

    root = Path(topic_dir).resolve() if topic_dir else find_workspace_root()
    if root is None:
        raise SystemExit("no workspace found (run inside a topic or pass --topic-dir)")
    return Path(root)


def _loaded(root):
    from .core.config_loader import get as config_get
    from .core.config_loader import load_config

    config = load_config(start=root)
    return load(root,
                wip_limit=config_get(config, "research.wip_limit", WIP_LIMIT),
                stall_days=config_get(config, "research.stall_days", STALL_DAYS))


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

    state = _loaded(_root_of(args.topic_dir))
    if args.line:
        state.lines = [view for view in state.lines if view.slug == args.line]
        state.queue = [item for item in state.queue if item.line == args.line]
        state.debt = [item for item in state.debt
                      if any(item.slug == note.slug and args.line in (note.lines or [])
                             for note in state.notes)]

    actions = candidates(state)
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

    state = _loaded(_root_of(args.topic_dir))
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
