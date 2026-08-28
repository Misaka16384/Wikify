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

Two properties this has to have, because both failure modes are silent:

* **Idempotent.** Writing the same body twice leaves identical bytes. A block
  that grows a newline per run turns every upgrade into a diff nobody reads.
* **Order-preserving.** The block stays where it was — it does not migrate to
  the end of the file when the body changes, because a person put their own
  text around it deliberately.
"""

from __future__ import annotations

from pathlib import Path

from .wiki_common import atomic_write, normalize_newlines

BEGIN = "<!-- magi:begin -->"
END = "<!-- magi:end -->"

#: What a file gets when it has no block yet: the block, then whatever was
#: already there. First because it is the part a host must read.
_NEW = "{block}\n\n{existing}"


def block(body: str) -> str:
    """One managed block: markers plus the body, no trailing whitespace."""
    return f"{BEGIN}\n{body.strip()}\n{END}"


def read(text: str) -> str | None:
    """The body between the markers, or `None` when the text has no block."""
    text = normalize_newlines(text)
    start = text.find(BEGIN)
    if start == -1:
        return None
    end = text.find(END, start)
    if end == -1:
        return None
    return text[start + len(BEGIN):end].strip()


def apply(text: str, body: str) -> str:
    """`text` with its managed block set to `body`. Everything else survives.

    An unterminated `magi:begin` is left alone and the new block is prepended:
    somebody's half-deleted marker is not licence to decide where their file
    ends.
    """
    text = normalize_newlines(text)
    start = text.find(BEGIN)
    end = text.find(END, start) if start != -1 else -1

    if start == -1 or end == -1:
        existing = text.strip()
        if not existing:
            return block(body) + "\n"
        return _NEW.format(block=block(body), existing=existing) + "\n"

    head = text[:start].rstrip("\n")
    tail = text[end + len(END):].lstrip("\n")
    parts = [part for part in (head, block(body), tail.rstrip()) if part]
    return "\n\n".join(parts) + "\n"


def write(path, body: str) -> bool:
    """Set the managed block in `path`. Returns True when the file changed.

    Reporting "changed" rather than always rewriting is what lets `install` be
    run on every session start without touching mtimes, which editors and file
    watchers both react to.
    """
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = apply(existing, body)
    if normalize_newlines(existing) == updated:
        return False
    atomic_write(path, updated)
    return True
