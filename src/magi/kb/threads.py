"""`threads/` — propositions, questions and lines, written like a forum.

One directory, one schema, three kinds (see `magi.core.vocab`). A note has two
halves and the split is the whole concurrency story:

* **the body**, owned by whoever created the note — edited freely by that one
  writer, the way any draft is;
* **`## Discussion`**, append-only — every other writer, human or agent, adds a
  signed post at the end and never touches what is already there.

Appending is therefore the only write, and it is taken under a short per-note
lock. The lock is not paranoia: this module was first written without one, on
the reasoning that `open(path, "a")` plus a single small write is serialised by
the operating system. That is true on POSIX and **false on Windows**, where the C
runtime implements `O_APPEND` as seek-to-end followed by write — two steps, and
a second writer landing between them overwrites the first. Eight concurrent
appends to one note lost two of them on the first measured run. A post is
somebody's argument; losing one silently is the worst thing this file could do,
so it holds a lock for the length of one append.

The lock is per note and held for microseconds, which keeps the property that
matters: two agents working different propositions never wait for each other,
and a crash mid-append cannot corrupt a note, because the only write is at the
end of the file.

The other reason posts exist is audit. The only mutable frontmatter field is
`status`, and a status flip must carry a post saying what moved and why. That
makes a note's history readable from the note itself, which is what lets
`validate()` check the whole transition chain from a snapshot — no journal, no
database, no memory of who was running at the time.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core import md_blocks, vocab
from ..core.wiki_common import (atomic_write, file_newline, parse_frontmatter_text,
                                split_frontmatter_text)

DIRNAME = "threads"

POST_HEADING = "## Discussion"

#: Seconds to wait for another writer's append. Generous because the work under
#: the lock is one read and one write, so waiting this long means something is
#: wrong rather than busy.
APPEND_TIMEOUT = 30.0

#: `### <ISO time> · <host>/<line>`. The line suffix is optional: a post about
#: a note that belongs to no line still needs a signature.
_POST_HEADER = re.compile(
    r"^###[ \t]+(?P<at>\S+)[ \t]*·[ \t]*(?P<host>[^/\s]+)(?:/(?P<line>[^\s]+))?[ \t]*$"
)

#: The first line of a post that carries a transition. `->` is accepted next to
#: `→` because half the hosts writing these are on a keyboard without it.
_POST_STATUS = re.compile(
    r"^status:[ \t]*(?P<src>[a-z-]+)[ \t]*(?:->|→|=>)[ \t]*(?P<dst>[a-z-]+)[ \t]*$"
)

#: A frontmatter field set from a post, recorded the way a status flip is.
#: A `bet:` that appears in a file with no event behind it cannot be told from
#: one written after the answer arrived, and a prediction nobody can date is
#: not a prediction.
_POST_FIELD = re.compile(
    r"^set:[ \t]*(?P<field>[a-z_]+)[ \t]*=[ \t]*(?P<value>.+?)[ \t]*$"
)

_HEADING_RE = re.compile(r"^##[ \t]+Discussion[ \t]*$", re.MULTILINE)

# ---------------------------------------------------------------- schema

COMMON_REQUIRED = ("kind", "status", "created", "purpose")

#: Fields every kind may carry. `line` is optional on purpose — a project can
#: run with zero explicit lines until a sub-direction is worth naming.
COMMON_OPTIONAL = ("line", "tags", "updated", "title")

KIND_OPTIONAL = {
    vocab.PROPOSITION: (
        "depends_on",      # [[concept]] this proposition is stated in terms of
        "answers",         # [[question]] it is an answer to
        "bet",             # the human's prediction, recorded before the work
        "derivation",      # [[drafts/...]] where the argument actually lives
        "superseded_by",   # [[raw/...]] or [[threads/...]] that replaced it
        "key_move",        # how it was resolved, written at closing time
    ),
    vocab.QUESTION: (),
    vocab.LINE: (),
}

#: Fields whose value must be a list even when it has one element. YAML makes
#: `line: foo` and `line: [foo]` different types, and every reader downstream
#: would otherwise have to normalise.
LIST_FIELDS = ("line", "tags", "depends_on", "answers", "derivation")

#: Statuses at which a proposition is closed and `key_move` becomes meaningful.
_CLOSED_PROPOSITION = frozenset({"supported", "refuted", "superseded"})


@dataclass
class Post:
    at: str
    host: str
    line: str | None = None
    src: str | None = None
    dst: str | None = None
    field: str | None = None
    value: str | None = None
    text: str = ""

    @property
    def is_transition(self) -> bool:
        return self.src is not None and self.dst is not None


@dataclass
class Note:
    path: Path
    frontmatter: dict = field(default_factory=dict)
    body: str = ""
    posts: list = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.path.stem

    @property
    def kind(self) -> str | None:
        return self.frontmatter.get("kind")

    @property
    def status(self) -> str | None:
        return self.frontmatter.get("status")

    @property
    def lines(self) -> list:
        return as_list(self.frontmatter.get("line"))

    @property
    def tier(self) -> str | None:
        return vocab.tier_of("threads/x.md", self.kind, self.status)


# ---------------------------------------------------------------- helpers


def as_list(value) -> list:
    """`None` → `[]`, a scalar → `[scalar]`, a list → itself."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item is not None]
    return [value]


def utcnow() -> str:
    """Post timestamps are UTC to the second: they are compared across hosts."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_thread_path(relpath) -> bool:
    parts = Path(str(relpath).replace("\\", "/")).parts
    return bool(parts) and parts[0] == DIRNAME


# ---------------------------------------------------------------- reading


def _labelled(text: str) -> list:
    """Lines paired with `code` / `table` / `text`, newlines normalised.

    Everything below reads structure off a line's prefix, and a fenced code
    block is the one place where a line that looks like a heading is not one. A
    post that quotes another post's signature inside a fence would otherwise
    become a post itself — and, if the quote carried a `status:` line, would
    invent a transition nobody made.
    """
    return md_blocks.classify_lines(md_blocks.normalize_newlines(text or ""))


def _heading_lines(labelled) -> list:
    """Indices of the real `## Discussion` headings, fences excluded."""
    return [index for index, (label, line) in enumerate(labelled)
            if label != md_blocks.CODE and _HEADING_RE.match(line)]


def parse_posts(body: str) -> list:
    """Every signed post under `## Discussion`, in file order.

    Text before the heading is the body and is ignored here. A `###` heading
    that does not match the signature is not a post — it is a subsection of
    somebody's prose, and swallowing it would invent transitions.
    """
    labelled = _labelled(body)
    headings = _heading_lines(labelled)
    if not headings:
        return []

    posts: list = []
    current: Post | None = None
    buffer: list = []

    def flush() -> None:
        if current is not None:
            current.text = "\n".join(buffer).strip()
            posts.append(current)

    for label, raw_line in labelled[headings[0] + 1:]:
        if label != md_blocks.CODE:
            header = _POST_HEADER.match(raw_line)
            if header:
                flush()
                current = Post(at=header.group("at"), host=header.group("host"),
                               line=header.group("line"))
                buffer = []
                continue
            if current is not None and current.src is None:
                status = _POST_STATUS.match(raw_line.strip())
                if status:
                    current.src = status.group("src")
                    current.dst = status.group("dst")
                    continue
            if current is not None and current.field is None and not buffer:
                changed = _POST_FIELD.match(raw_line.strip())
                if changed:
                    current.field = changed.group("field")
                    current.value = changed.group("value")
                    continue
        if current is None:
            continue
        buffer.append(raw_line)
    flush()
    return posts


def has_discussion(text: str) -> bool:
    """True when the text carries a real `## Discussion` heading.

    A heading quoted inside a code fence does not count: treating it as one
    would leave the next post with nowhere to live.
    """
    return bool(_heading_lines(_labelled(text)))


def read_note(path) -> Note:
    """Parse one note. Never raises on malformed content — `validate` reports."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    split = split_frontmatter_text(text)
    # Broken frontmatter must not hide the discussion: the posts are the audit
    # trail, and a note that has lost its header is exactly when somebody needs
    # to read what happened to it.
    fm_text, body = split if split is not None else ("", text)
    return Note(path=path, frontmatter=parse_frontmatter_text(fm_text),
                body=body, posts=parse_posts(body))


def transitions(posts) -> list:
    """`[(src, dst), ...]` in order, from the posts that carry one."""
    return [(post.src, post.dst) for post in posts if post.is_transition]


def derived_status(kind: str, posts) -> str | None:
    """Where the posted history says the note ended up.

    `None` when no post carries a transition, which for a note still at its
    initial status is the correct and unremarkable answer.
    """
    moves = transitions(posts)
    if not moves:
        return None
    return moves[-1][1]


# ---------------------------------------------------------------- writing


def quote_if_structural(text: str) -> str:
    """Fence a body whose own lines would be read as this format's structure.

    Posts are transcription: `magi decide` writes what a person said, word for
    word. Somebody quoting a status line — "my worry is exactly this: status:
    testing -> refuted" — would otherwise have that line eaten by the parser
    and reappear as a transition **signed with their name**, which is the one
    signature the record cannot afford to invent. The line also vanishes from
    every reader, so the transcription is not even verbatim.

    Fencing keeps both properties: the words are unchanged and the parser sees
    a code block, which it already knows to skip. The fence is sized to survive
    a body that contains backticks of its own.
    """
    body = (text or "").strip()
    if not body:
        return body
    labelled = _labelled(body)
    risky = any(label != md_blocks.CODE and (
        _POST_HEADER.match(line) or _HEADING_RE.match(line)
        or _POST_STATUS.match(line.strip()) or _POST_FIELD.match(line.strip()))
        for label, line in labelled)
    if not risky:
        return body
    longest = max((len(run) for run in re.findall(r"`+", body)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{body}\n{fence}"


def format_post(text: str, host: str, line: str | None = None, at: str | None = None,
                src: str | None = None, dst: str | None = None,
                field: str | None = None, value=None) -> str:
    """One post, heading included, ending in exactly one blank line."""
    signature = host if not line else f"{host}/{line}"
    out = [f"### {at or utcnow()} · {signature}"]
    if src and dst:
        out.append(f"status: {src} → {dst}")
    if field:
        out.append(f"set: {field} = {value}")
    body = quote_if_structural(text)
    if body:
        out.append("")
        out.append(body)
    out.append("")
    return "\n".join(out)


def lock_path(path) -> Path:
    """Where one note's append lock lives.

    Under the workspace's `output/`, which is DERIVED — a lock file is not
    content, and putting it next to the note would mean a stray file inside a
    directory people read, back up and sync. Notes outside a workspace (tests,
    a loose file) get a hidden sibling instead of a guess about the root.
    """
    path = Path(path)
    if path.parent.name == DIRNAME:
        name = path.name
        return path.parent.parent / "output" / ".locks" / f"{DIRNAME}-{name}.lock"
    return path.with_name(f".{path.name}.lock")


def append_post(path, text: str, host: str, line: str | None = None,
                at: str | None = None, src: str | None = None,
                dst: str | None = None, field: str | None = None,
                value=None) -> str:
    """Append one signed post under a short per-note lock. Returns the post.

    Creates the `## Discussion` heading when the note has none. Raises
    `FileNotFoundError` when the note does not exist — see `create`.
    """
    from filelock import FileLock

    path = Path(path)
    # A post on a note that does not exist would create a file with no
    # frontmatter — no kind, no status, invisible to `next` and to every
    # projection. Whoever meant to open a proposition should call `create`.
    if not path.exists():
        raise FileNotFoundError(str(path))

    post = format_post(text, host=host, line=line, at=at, src=src, dst=dst,
                       field=field, value=value)
    lock = lock_path(path)
    lock.parent.mkdir(parents=True, exist_ok=True)

    with FileLock(str(lock), timeout=APPEND_TIMEOUT):
        existing = path.read_text(encoding="utf-8")
        with open(path, "a", encoding="utf-8", newline=file_newline(path)) as handle:
            handle.write(_join_chunk(existing, post))
            handle.flush()
    return post


class IllegalTransition(ValueError):
    """A flip the lifecycle does not allow. Carries what was allowed instead."""

    def __init__(self, kind: str, src: str, dst: str, allowed) -> None:
        self.kind, self.src, self.dst, self.allowed = kind, src, dst, list(allowed)
        super().__init__(
            f"{kind}: {src} → {dst} is not a legal transition; "
            f"from {src} it may reach {self.allowed}")


def set_status(path, dst: str, text: str, host: str, line: str | None = None,
               at: str | None = None) -> str:
    """Flip a note's status and post the reason, both under one lock.

    These are one action, so they are one function. Splitting them is how a
    note ends up with a status nobody explained, or a post describing a flip
    that never happened — and the whole audit story rests on the two agreeing.

    The status is written first and the post second. A crash between them
    leaves a real status with no explanation, which `lint` reports as
    bookkeeping debt; the other order would leave a post claiming a transition
    that did not happen, which reads as fact.

    Raises `IllegalTransition` when the lifecycle forbids the move, and
    `FileNotFoundError` when the note does not exist.
    """
    from filelock import FileLock

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    lock = lock_path(path)
    lock.parent.mkdir(parents=True, exist_ok=True)

    with FileLock(str(lock), timeout=APPEND_TIMEOUT):
        current = path.read_text(encoding="utf-8")
        split = split_frontmatter_text(current)
        if split is None:
            raise ValueError(f"{path} has no frontmatter to flip")
        frontmatter = parse_frontmatter_text(split[0])
        kind = frontmatter.get("kind")
        src = frontmatter.get("status")
        if not vocab.is_legal_transition(kind, src, dst):
            raise IllegalTransition(kind, src, dst, vocab.allowed_targets(kind, src))

        ending = file_newline(path)
        if src != dst:
            atomic_write(path, _replace_status(current, dst), newline=ending)
        post = format_post(text, host=host, line=line, at=at,
                           src=src if src != dst else None,
                           dst=dst if src != dst else None)
        with open(path, "a", encoding="utf-8", newline=ending) as handle:
            handle.write(_join_chunk(path.read_text(encoding="utf-8"), post))
    return post


def set_field(path, key: str, value, host: str, text: str = "",
              line: str | None = None, at: str | None = None) -> None:
    """Set one frontmatter field, under the lock, with a post saying who.

    Used for the fields a person owns — `bet:` above all. A prediction that
    appears in a file with nobody's name on it is indistinguishable from one
    the agent invented, which is the entire value of having asked.
    """
    from filelock import FileLock

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    lock = lock_path(path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(lock), timeout=APPEND_TIMEOUT):
        current = path.read_text(encoding="utf-8")
        ending = file_newline(path)
        atomic_write(path, _replace_field(current, key, value), newline=ending)
        # The write above verifies itself, but a caller acting on "it worked"
        # deserves the check to be here rather than two functions away: a
        # `decisions.md` entry saying a person predicted something, with no
        # `bet:` in the note, is a record of a decision that left no trace.
        if read_note(path).frontmatter.get(key) != value:
            raise ValueError(f"{path.name}: {key} did not take")
        post = format_post(text, host=host, line=line, at=at, field=key, value=value)
        with open(path, "a", encoding="utf-8", newline=ending) as handle:
            handle.write(_join_chunk(path.read_text(encoding="utf-8"), post))


def _replace_field(text: str, key: str, value) -> str:
    """Set `key` in the frontmatter, adding it when it is not there.

    Same shape as `_replace_status`, and same reason for the verify step: a
    line edit and a YAML parse are two readings of one text, and they disagree
    on anything this module did not write.
    """
    import yaml

    split = split_frontmatter_text(text)
    if split is None:
        # Returning the text unchanged made this a silent no-op on a note
        # whose frontmatter somebody had broken by hand — `read_note` tolerates
        # exactly that, so the caller had no way to find out.
        raise ValueError("no frontmatter to set a field in")
    fm_text, body = split

    rendered = yaml.safe_dump({key: value}, allow_unicode=True,
                              default_flow_style=False).strip()
    # `lambda`, not the string: a value containing a backslash escape would
    # otherwise be read as a replacement template and blow up on `\1`.
    edited = re.sub(rf"(?m)^{re.escape(key)}:[^\n]*$", lambda _: rendered,
                    fm_text, count=1)
    if edited == fm_text:
        edited = f"{fm_text}\n{rendered}"
    if parse_frontmatter_text(edited).get(key) == value:
        return f"---\n{edited}\n---{body}"

    data = parse_frontmatter_text(fm_text)
    data[key] = value
    dumped = yaml.safe_dump(data, allow_unicode=True, sort_keys=False,
                            default_flow_style=False).rstrip("\n")
    return f"---\n{dumped}\n---{body}"


def _replace_status(text: str, dst: str) -> str:
    """Set the frontmatter's status to `dst`, and make sure it took.

    The cheap path edits the one line, which keeps the file byte-identical
    apart from that word — comments, key order and spacing all survive. But a
    line edit and a YAML parse are two different readings of the same text, and
    they disagree on anything this module did not write: flow style
    (`{status: open, ...}`) has no line to match, and a multi-line quoted scalar
    can contain a line that *looks* like the status and is not. Both failures
    are silent, and a silent one here is the worst kind — `set_status` would
    post "open → testing" over a note still saying `open`.

    So the result is parsed back. If the cheap path did not actually move the
    status, the frontmatter is re-serialised from the parsed mapping instead:
    that reformats the block, which is a visible cost, and it is the right
    trade against a status the audit trail lies about.
    """
    split = split_frontmatter_text(text)
    if split is None:
        return text
    fm_text, body = split

    edited = re.sub(r"(?m)^status:[^\n]*$", f"status: {dst}", fm_text, count=1)
    if parse_frontmatter_text(edited).get("status") == dst:
        return f"---\n{edited}\n---{body}"

    import yaml

    data = parse_frontmatter_text(fm_text)
    data["status"] = dst
    dumped = yaml.safe_dump(data, allow_unicode=True, sort_keys=False,
                            default_flow_style=False).rstrip("\n")
    return f"---\n{dumped}\n---{body}"


def _join_chunk(existing: str, post: str) -> str:
    """The bytes to append so `post` lands under a `## Discussion` heading."""
    chunk = ""
    if existing and not existing.endswith("\n"):
        chunk += "\n"
    if not has_discussion(existing):
        chunk += f"\n{POST_HEADING}\n"
    return chunk + "\n" + post


def render(kind: str, title: str, purpose: str, status: str | None = None,
           lines=None, created: str | None = None, extra: dict | None = None,
           body: str = "") -> str:
    """A new note as text. Field order is fixed so diffs stay readable."""
    fm: dict = {
        "kind": kind,
        "status": status or vocab.INITIAL_STATUS[kind],
        "created": created or dt.date.today().isoformat(),
        "purpose": purpose,
    }
    listed = as_list(lines)
    if listed:
        fm["line"] = listed
    for key, value in (extra or {}).items():
        fm[key] = value

    import yaml
    fm_text = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False,
                             default_flow_style=False).rstrip("\n")
    parts = [f"---\n{fm_text}\n---", "", f"# {title}", ""]
    if body.strip():
        parts.extend([body.strip(), ""])
    # No trailing blank: the first appended post supplies the blank line that
    # separates it from the heading, the same way every later post does.
    parts.append(POST_HEADING)
    return "\n".join(parts) + "\n"


def create(path, kind: str, title: str, purpose: str, **kwargs) -> Path:
    """Write a new note. Refuses to overwrite: a slug is an identity."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, render(kind, title, purpose, **kwargs))
    return path


# ---------------------------------------------------------------- validation


def validate(note: Note) -> list:
    """`[(severity, message, fixable), ...]`. Pure — the caller reports.

    Severity follows the lint convention: `critical` fails the command,
    everything else is advice. The line between them here is whether the
    machine can still act on the note: an unknown `kind` or a status that does
    not belong to it breaks `magi next`, so those are critical; a missing
    `key_move` only costs a person context later.
    """
    out: list = []
    fm = note.frontmatter

    kind = fm.get("kind")
    if not kind:
        out.append(("critical", "Missing frontmatter field: kind.", False))
        return out
    if kind not in vocab.KINDS:
        out.append(("critical",
                    f"Invalid kind: {kind!r}; expected one of {list(vocab.KINDS)}.", False))
        return out

    status = fm.get("status")
    if not status:
        out.append(("critical", "Missing frontmatter field: status.", False))
    elif not vocab.is_status(kind, status):
        out.append(("critical",
                    f"Invalid status for kind {kind}: {status!r}; "
                    f"expected one of {list(vocab.statuses(kind))}.", False))

    for required in ("created", "purpose"):
        if not fm.get(required):
            out.append(("warning", f"Missing frontmatter field: {required}.", False))

    purpose = fm.get("purpose")
    if isinstance(purpose, str) and "\n" in purpose.strip():
        out.append(("suggestion",
                    "purpose is one line: what this note is for, not what it says.", False))

    allowed = set(COMMON_REQUIRED) | set(COMMON_OPTIONAL) | set(KIND_OPTIONAL.get(kind, ()))
    for key in sorted(set(fm) - allowed):
        out.append(("suggestion",
                    f"Unknown frontmatter field for kind {kind}: {key}.", False))

    for key in LIST_FIELDS:
        if key in fm and not isinstance(fm[key], (list, tuple)):
            out.append(("warning", f"{key} must be a list, even with one entry.", False))

    if kind == vocab.LINE and fm.get("line"):
        out.append(("warning",
                    "A line note has no line: field — its slug is the line.", False))

    if "bet" in fm and fm["bet"] not in vocab.BETS:
        out.append(("warning",
                    f"Invalid bet: {fm['bet']!r}; expected one of {list(vocab.BETS)}.", False))

    if "key_move" in fm:
        if fm["key_move"] not in vocab.KEY_MOVES:
            out.append(("warning",
                        f"Invalid key_move: {fm['key_move']!r}; "
                        f"expected one of {list(vocab.KEY_MOVES)}.", False))
        elif status not in _CLOSED_PROPOSITION:
            out.append(("suggestion",
                        "key_move is written when a proposition closes, not before.", False))
    elif kind == vocab.PROPOSITION and status in ("supported", "refuted"):
        out.append(("suggestion",
                    "A closed proposition records key_move: how it was actually solved.", False))

    out.extend(_validate_history(note, kind, status))
    return out


def _validate_history(note: Note, kind: str, status) -> list:
    """The posted transition chain, checked against the frontmatter status."""
    out: list = []

    if len(_heading_lines(_labelled(note.body))) > 1:
        out.append(("warning",
                    f"More than one '{POST_HEADING}' heading. Harmless — posts are read "
                    "from the first one on — but only one of them is the forum.",
                    False))

    moves = transitions(note.posts)
    if not moves:
        if status and status != vocab.INITIAL_STATUS.get(kind):
            out.append(("warning",
                        f"status is {status!r} but no post records the transition; "
                        "a status flip carries a post.", False))
        return out

    current = vocab.INITIAL_STATUS.get(kind)
    for index, (src, dst) in enumerate(moves):
        if index == 0 and src != current:
            # A note may be created already in motion (migration, or a
            # proposition split off an existing one). Take the first post's
            # own starting point and only check the chain from there.
            current = src
        if src != current:
            out.append(("warning",
                        f"Post {index + 1} starts at {src!r} but the previous post "
                        f"left the note at {current!r}.", False))
        elif not vocab.is_legal_transition(kind, src, dst):
            allowed = list(vocab.allowed_targets(kind, src))
            out.append(("critical",
                        f"Illegal transition for kind {kind}: {src} → {dst}; "
                        f"from {src} the note may reach {allowed}.", False))
        current = dst

    if status and current != status:
        out.append(("warning",
                    f"status is {status!r} but the last post left the note at "
                    f"{current!r}.", False))
    return out


# ---------------------------------------------------------------- lint


def note_paths(root) -> list:
    """Every note under `threads/`. `_index.md` is scaffolding, not a note."""
    directory = Path(root) / DIRNAME
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.rglob("*.md")
                  if path.name != "_index.md"
                  and not any(part.startswith(".")
                              for part in path.relative_to(directory).parts))




def lint(root) -> list:
    """`[(severity, message, path, fixable), ...]` for the whole tree.

    Reads and never writes. The one repair this module used to offer —
    merging a duplicated `## Discussion` heading — is gone: appends now take
    a lock, so MAGI cannot produce the duplicate, and a hand-written one
    breaks nothing (posts are found from the first heading onward either
    way). Deleting a heading line somebody typed was the larger risk.
    """
    issues: list = []

    for path in note_paths(root):
        try:
            note = read_note(path)
        except OSError as exc:
            issues.append(("critical", f"Could not read file: {exc}", path, False))
            continue
        except UnicodeDecodeError:
            issues.append(("critical", "Markdown file is not valid UTF-8.", path, False))
            continue

        for severity, message, fixable in validate(note):
            issues.append((severity, message, path, fixable))

    return issues
