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
from ..core.wiki_common import atomic_write, parse_frontmatter_text, split_frontmatter_text

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


def format_post(text: str, host: str, line: str | None = None, at: str | None = None,
                src: str | None = None, dst: str | None = None) -> str:
    """One post, heading included, ending in exactly one blank line."""
    signature = host if not line else f"{host}/{line}"
    out = [f"### {at or utcnow()} · {signature}"]
    if src and dst:
        out.append(f"status: {src} → {dst}")
    body = (text or "").strip()
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
                dst: str | None = None) -> str:
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

    post = format_post(text, host=host, line=line, at=at, src=src, dst=dst)
    lock = lock_path(path)
    lock.parent.mkdir(parents=True, exist_ok=True)

    with FileLock(str(lock), timeout=APPEND_TIMEOUT):
        existing = path.read_text(encoding="utf-8")
        chunk = ""
        if existing and not existing.endswith("\n"):
            chunk += "\n"
        if not has_discussion(existing):
            chunk += f"\n{POST_HEADING}\n"
        chunk += "\n" + post
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(chunk)
            handle.flush()
    return post


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
    parts.extend([POST_HEADING, ""])
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
