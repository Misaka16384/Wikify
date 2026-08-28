"""The part of `AGENTS.md` the CLI owns, and the part it must never touch.

Every host reads an instruction file at the top of a session — `AGENTS.md` for
Codex and most others, `CLAUDE.md` for Claude Code, which in a MAGI workspace
holds nothing but `@AGENTS.md` so there is one text and not two. That file is
shared property: MAGI needs to keep its protocol current across upgrades, and
the person needs to write project instructions that survive the next upgrade.

So the file is split by two markers. Between them belongs to the CLI and is
rewritten whole on every `magi install`; everything outside belongs to whoever
wrote it and is never read, moved or reflowed. The alternative — appending, the
way most tools do it — is how an instruction file ends up with four copies of a
protocol that changed three times, each contradicting the last.

Three properties this has to have, because all three failure modes are silent:

* **Idempotent.** Writing the same body twice leaves identical bytes. A block
  that grows a newline per run turns every upgrade into a diff nobody reads.
* **Order-preserving.** The block stays where it was — it does not migrate to
  the end of the file when the body changes, because a person put their own
  text around it deliberately.
* **Self-healing.** A file that somehow ends up with two blocks converges to
  one. Two blocks is the same disease as appending, arrived at differently:
  two protocols in one file and no way to know which the host obeyed.

Markers are read the way the rest of the repo reads markdown structure —
`md_blocks.classify_lines`, so a fenced example of what the markers look like
is an example and not a block. Without that, documenting this format inside
`AGENTS.md` would cause the next `install` to splice the live protocol into the
middle of the code fence, where a host reads it as sample text.
"""

from __future__ import annotations

from pathlib import Path

from . import md_blocks
from .wiki_common import atomic_write, file_newline, normalize_newlines

BEGIN = "<!-- magi:begin -->"
END = "<!-- magi:end -->"


def block(body: str) -> str:
    """One managed block: markers plus the body, no trailing whitespace."""
    return f"{BEGIN}\n{body.strip()}\n{END}"


def _pairs(labelled) -> list:
    """`[(begin_index, end_index), ...]` for every complete block.

    Markers inside a code fence are examples. An opener with no closer, or a
    closer with no opener, is somebody mid-edit: it is left exactly where it
    is rather than treated as licence to decide where their file ends.
    """
    found: list = []
    start = None
    for index, (label, line) in enumerate(labelled):
        if label == md_blocks.CODE:
            continue
        stripped = line.strip()
        if stripped == BEGIN and start is None:
            start = index
        elif stripped == END and start is not None:
            found.append((start, index))
            start = None
    return found


def _labelled(text: str) -> list:
    return md_blocks.classify_lines(normalize_newlines(text or ""))


def read(text: str) -> str | None:
    """The body of the first managed block, or `None` when there is none."""
    labelled = _labelled(text)
    pairs = _pairs(labelled)
    if not pairs:
        return None
    start, end = pairs[0]
    return "\n".join(line for _, line in labelled[start + 1:end]).strip()


def apply(text: str, body: str) -> str:
    """`text` with exactly one managed block, set to `body`.

    Every complete block is removed and one is put back where the first one
    was, so a file that picked up a duplicate converges instead of carrying the
    stale copy forever. Text outside the blocks comes back as it went in, with
    one exception: the blank lines at the two seams normalise to exactly one,
    which is what makes writing the same body twice a byte-for-byte no-op.
    """
    labelled = _labelled(text)
    pairs = _pairs(labelled)
    lines = [line for _, line in labelled]

    if not pairs:
        existing = "\n".join(lines).strip()
        if not existing:
            return block(body) + "\n"
        return f"{block(body)}\n\n{existing}\n"

    removed = set()
    for start, end in pairs:
        removed.update(range(start, end + 1))

    at = pairs[0][0]
    head = "\n".join(lines[index] for index in range(at) if index not in removed).rstrip("\n")
    tail = "\n".join(lines[index] for index in range(at, len(lines))
                     if index not in removed).strip("\n")

    parts = [part for part in (head, block(body), tail) if part]
    return "\n\n".join(parts) + "\n"


def write(path, body: str) -> bool:
    """Set the managed block in `path`. Returns True when the file changed.

    Reporting "changed" rather than always rewriting is what lets `install` be
    run on every session start without touching mtimes, which editors and file
    watchers both react to. The file keeps whatever line endings it already
    had: these files travel between macOS and Windows sessions, and rewriting
    all of them to suit this machine turns one edit into a whole-file diff.
    """
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = apply(existing, body)
    if normalize_newlines(existing) == updated:
        return False
    atomic_write(path, updated, newline=file_newline(path))
    return True
