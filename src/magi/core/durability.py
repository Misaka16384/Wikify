"""What can be deleted and rebuilt, and what cannot. One place, so it is one answer.

D3 in the roadmap: derived data and original data are mixed together with no
marker, so every question about deleting, backing up or resetting something has
to be re-reasoned from scratch — and "rebuild it" is only safe advice if you
know what you would lose. This module is the convention, in a form code can
check rather than a paragraph somebody remembers.

Three categories, and the boundary between the first two is the useful one:

**ORIGINAL** — a person made it. Nothing can regenerate it. Losing it loses
work: the sources in ``raw/``, the wiki in ``wiki/``, the workspace's own
``config.yaml`` and ``config.md``, and — the one that is easy to miss because
it lives outside the workspace — the global ``registry.json`` and
``settings.json``, which are the list of libraries a person set up by hand.
That one was, until recently, written with a plain overwrite and read with a
handler that turned an unparseable file into an empty one.

**DERIVED** — a command produced it and the same command will produce it again.
``output/graph.db``, ``output/index.db``, ``output/.lint_cache.json``,
``scratch/``. Deleting any of these costs time, never information. `magi index
--rebuild` deletes the index deliberately, and that is a supported thing to do.

**TRANSACTIONAL** — neither. ``output/ingest/`` is an append-only log of what
was queued, converted, decided and committed. It cannot be regenerated, because
it records decisions a person made; but it is also not the artefact — the
artefacts it points at have already been copied into ``raw/``. Deleting it
loses the audit trail and the queue, not the library.

The practical consequences, which are the reason to write this down:

* "delete ``output/`` and re-run" is safe **except for ``output/ingest/``**;
* a backup that covers ``raw/``, ``wiki/``, the two config files and the global
  config directory is complete;
* anything ORIGINAL needs an atomic write and a lock; anything DERIVED does not.
"""

from __future__ import annotations

ORIGINAL = (
    "raw/",
    "wiki/",
    "inbox/",
    "config.yaml",
    "config.md",
    "~/.config/magi/registry.json",
    "~/.config/magi/settings.json",
)

DERIVED = (
    "output/graph.db",
    "output/index.db",
    "output/.lint_cache.json",
    "output/radar/",
    "scratch/",
)

TRANSACTIONAL = (
    "output/ingest/",
)


def classify(relpath: str) -> str:
    """``"original"``, ``"derived"``, ``"transactional"`` or ``"unknown"``.

    ``unknown`` is a real answer and not a failure: a path nobody has decided
    about yet should be reported as undecided rather than guessed into a
    category. Guessing is how ``output/ingest/`` would end up inside a
    "delete output/ and re-run" instruction.
    """
    path = relpath.replace("\\", "/").lstrip("./")

    def hit(entries):
        return any(path == e.rstrip("/") or path.startswith(e)
                   if e.endswith("/") else path == e or path.endswith("/" + e)
                   for e in entries)

    # Transactional first: `output/ingest/` sits inside a tree that is
    # otherwise derived, and the specific answer has to win.
    if hit(TRANSACTIONAL):
        return "transactional"
    if hit(DERIVED):
        return "derived"
    if hit(ORIGINAL):
        return "original"
    return "unknown"


def is_regenerable(relpath: str) -> bool:
    """True only for things a command will rebuild. ``unknown`` is not True."""
    return classify(relpath) == "derived"
