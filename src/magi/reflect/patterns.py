"""One page per pattern: what keeps happening, and where it was seen.

This is the layer the design added after reading WikiSkill (design-v2 §12), and
it is not an exception to "derive, never store". A transcript is a host's
private cache: it lives outside the project, it rotates, and four vendors write
four formats. What a pass understood from one cannot be recomputed next month,
because the input will be gone. That makes a pattern page **truth**, not a
projection — and `durability.classify` says so: ORIGINAL, atomic write, lock.

It is also what makes the gates executable. "The same gap in at least two
independent sessions" and "not seen for ninety days" are queries against these
files. Written as prose in a prompt they are wishes; written here they are
`len(page.sessions) >= 2` and a date comparison.

**Nothing but `reflect` reads this directory.** Not the managed block, not any
skill, not `magi next`. An agent that can read the pattern library starts
defending against the patterns instead of following the rules, and then the
slow loop can no longer tell whether the rules it hardened are doing anything —
which is the ablation WikiSkill reports as a *drop* in score.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core.wiki_common import (atomic_write, parse_frontmatter_text,
                                split_frontmatter_text)

DIRNAME = ("output", "reflect", "patterns")

#: A pattern nobody has proposed anything about yet.
OPEN = "open"
#: A proposal has been made from it; it stays for provenance.
PROPOSED = "proposed"
#: Ninety days without recurring. What it produced goes to the queue.
RETIRED = "retired"
STATUSES = (OPEN, PROPOSED, RETIRED)

#: How long a pattern stays live without being seen again (design-v2 §12).
EXPIRY_DAYS = 90

#: How a patch is described. Deliberately three verbs and no more: anything a
#: model can express here, a person can check by eye, and `target` has to be an
#: exact substring of the file so "apply it" is a search rather than a judgement.
OPS = ("append", "replace", "insert_after")


@dataclass
class Pattern:
    slug: str
    title: str = ""
    first_seen: str = ""
    last_seen: str = ""
    sessions: list = field(default_factory=list)   # "host/session-id"
    hosts: list = field(default_factory=list)
    status: str = OPEN
    patch: dict = field(default_factory=dict)
    body: str = ""
    path: Path | None = None

    @property
    def independent(self) -> int:
        """How many separate sessions have shown this.

        Sessions, not observations: the same session mentioned twice is one
        session, and the gate the design asks for is about independence.
        """
        return len(set(self.sessions))

    def expired(self, now=None) -> bool:
        last = _date(self.last_seen)
        if last is None:
            return False
        now = now or dt.date.today()
        return (now - last).days > EXPIRY_DAYS


def _date(value):
    try:
        return dt.date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def directory(root) -> Path:
    return Path(root).joinpath(*DIRNAME)


def path_for(root, slug: str) -> Path:
    if not slug or slug != Path(slug).name or slug.startswith("."):
        raise ValueError(f"not a slug: {slug!r}")
    return directory(root) / f"{slug}.md"


def _as_list(value) -> list:
    """A list, whatever somebody typed.

    A scalar is one item — `sessions: 3` is a page a person edited by hand, and
    one such page used to raise out of `all_patterns` and take `ready`, `stale`
    and the whole decision queue down with it.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def read(path) -> Pattern:
    """Parse one page. Tolerant, like every other reader in this codebase."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    split = split_frontmatter_text(text)
    fm_text, body = split if split is not None else ("", text)
    data = parse_frontmatter_text(fm_text)
    patch = data.get("patch")
    return Pattern(
        slug=path.stem,
        title=str(data.get("title") or path.stem),
        first_seen=str(data.get("first_seen") or ""),
        last_seen=str(data.get("last_seen") or ""),
        sessions=_as_list(data.get("sessions")),
        hosts=_as_list(data.get("hosts")),
        status=str(data.get("status") or OPEN),
        patch=patch if isinstance(patch, dict) else {},
        body=body.strip(),
        path=path,
    )


def all_patterns(root) -> list:
    folder = directory(root)
    if not folder.is_dir():
        return []
    return [read(path) for path in sorted(folder.glob("*.md"))]


def render(pattern: Pattern) -> str:
    import yaml

    fm = {
        "title": pattern.title,
        "first_seen": pattern.first_seen,
        "last_seen": pattern.last_seen,
        "sessions": sorted(set(pattern.sessions)),
        "hosts": sorted(set(pattern.hosts)),
        "status": pattern.status,
    }
    if pattern.patch:
        fm["patch"] = pattern.patch
    dumped = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False,
                            default_flow_style=False).rstrip("\n")
    return f"---\n{dumped}\n---\n\n{pattern.body.strip()}\n"


def _lock_for(path: Path):
    from filelock import FileLock

    path.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(path.with_name(path.name + ".lock")), timeout=30)


def _write(path: Path, pattern: Pattern) -> Path:
    """The write itself, assuming the caller holds the lock."""
    from ..core.wiki_common import file_newline

    ending = file_newline(path) if path.is_file() else None
    atomic_write(path, render(pattern), newline=ending)
    pattern.path = path
    return path


def save(root, pattern: Pattern) -> Path:
    """Write one page, atomically and under a lock.

    ORIGINAL by `durability.classify`: there is one copy, it is edited in
    place across runs, and what it holds cannot be regenerated once the
    transcripts it came from have rotated away.
    """
    path = path_for(root, pattern.slug)
    with _lock_for(path):
        return _write(path, pattern)


def observe(root, slug: str, *, title: str, body: str, session: str, host: str,
            patch: dict | None = None, when=None) -> Pattern:
    """Record one sighting of a pattern, merging with what is already there.

    The body of an existing page is **kept**: it is the account written when
    the pattern was first understood, and a later pass rewriting it would
    quietly erase the evidence the ≥2-sessions gate rests on. What a sighting
    adds is the session, the host, and the date.
    """
    today = (when or dt.date.today()).isoformat()
    path = path_for(root, slug)

    # Read *and* write under one lock. Two sightings landing at once used to
    # read the same page, add one session each and write in turn — so one of
    # them vanished, which is an attack on the ≥2-independent-sessions gate
    # itself, on a file nothing can regenerate.
    with _lock_for(path):
        existing = read(path) if path.is_file() else None
        if existing is None:
            pattern = Pattern(slug=slug, title=title, first_seen=today,
                              last_seen=today, sessions=[session], hosts=[host],
                              body=body, patch=patch or {})
        else:
            pattern = existing
            pattern.last_seen = today
            pattern.sessions = sorted(set(pattern.sessions) | {session})
            pattern.hosts = sorted(set(pattern.hosts) | {host})
            # It happened again, whatever was decided last time. A pattern that
            # recurs after a proposal was turned down is exactly the case the
            # loop exists for — it now has more evidence and a recorded reason
            # the last idea was wrong. Leaving it `proposed` forever meant the
            # one pattern somebody had engaged with could never come back.
            pattern.status = OPEN
            if patch and not pattern.patch:
                pattern.patch = patch
        _write(path, pattern)
    return pattern


def mark(root, slug: str, status: str) -> "Pattern | None":
    """Set one page's status, re-reading it under the lock first.

    `read()` then `save()` looks like it is safe because `save()` locks, but
    the read is outside it: `propose` held a two-session copy while `observe`
    added the third under its own lock, and the write put the stale copy back.
    That is the same attack on the >=2-independent-sessions gate `observe`
    documents, on a directory `durability` classifies ORIGINAL — nothing
    regenerates it once the transcripts have rotated.

    Returns `None` if the page is gone, which is not an error: the proposal is
    already in the ledger, and that is the part that has to survive.
    """
    path = path_for(root, slug)
    with _lock_for(path):
        if not path.is_file():
            return None
        pattern = read(path)
        pattern.status = status
        _write(path, pattern)
    return pattern


def ready(root, minimum: int = 2, now=None) -> list:
    """Patterns that have earned a proposal: seen enough, and still current."""
    return [pattern for pattern in all_patterns(root)
            if pattern.status == OPEN
            and pattern.independent >= minimum
            and not pattern.expired(now)]


def stale(root, now=None) -> list:
    """Patterns that have gone quiet, and whose rules should be questioned."""
    return [pattern for pattern in all_patterns(root)
            if pattern.status != RETIRED and pattern.expired(now)]


# ---------------------------------------------------------------- patching


class PatchError(ValueError):
    """A patch that cannot be applied without guessing."""


def apply_patch(text: str, patch: dict) -> str:
    """Apply one `append` / `replace` / `insert_after` to a document.

    `target` must appear **exactly once**. Not "somewhere": a target matching
    twice means the patch does not say which one, and a patcher that picks the
    first is a patcher that edits the wrong paragraph eventually. Refusing is
    the only answer that cannot be silently wrong.
    """
    op = str(patch.get("op") or "").strip()
    if op not in OPS:
        raise PatchError(f"not a patch operation: {op!r} (one of {', '.join(OPS)})")
    body = str(patch.get("text") or "")
    if not body.strip():
        raise PatchError("the patch has no text")

    if op == "append":
        joiner = "" if text.endswith("\n") or not text else "\n"
        return text + joiner + body.rstrip("\n") + "\n"

    target = str(patch.get("target") or "")
    if not target:
        raise PatchError(f"{op} needs a target")
    found = text.count(target)
    if found == 0:
        raise PatchError("the target is not in the file, exactly as written")
    if found > 1:
        raise PatchError(f"the target appears {found} times — it has to name one place")

    if op == "replace":
        return text.replace(target, body, 1)
    index = text.index(target) + len(target)
    joiner = "" if body.startswith("\n") else "\n"
    return text[:index] + joiner + body.rstrip("\n") + "\n" + text[index:].lstrip("\n")


_SLUG_OK = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def is_slug(value: str) -> bool:
    return bool(_SLUG_OK.match(str(value or "")))
