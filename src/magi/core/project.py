"""What a project contains, in one place.

`workspace.py` answers "where is the root". This answers "what is inside it",
which is the question that kept being answered eight different ways.

Every subsystem needs a slightly different subset of the project's directories,
and the differences are real: a maintenance pass that rewrites files must not
touch `threads/`, because a discussion is append-only and nothing reformats
somebody's post; a `[[wikilink]]` may point at a draft but never at a source in
`raw/`. Those distinctions were correct. What was missing is a place where they
are *written down together*, so each was a hand-typed tuple in the module that
needed it — eight of them, maintained by grep.

The cost was not theoretical. `magi lint` walked `("raw", "wiki", "inventory",
"datasets")`: two directories that no longer exist and two that were added in
the v2 rebuild missing entirely, so nothing in `drafts/` — where every
derivation lives — was ever checked. `magi wiki reindex` still listed
`wiki/theses/`, which migration deletes. Nobody noticed either, because there
was no single list to read.

So: one row per directory, one column per question a subsystem asks. Adding a
directory to the scaffold means adding a row, and a row cannot be added without
answering every question — `test_project_layout.py` fails until the scaffold
and this table agree. Omission stops being silent, which is the only property
that actually prevents the next one.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Dir:
    """One directory in a project, and what every subsystem should do with it.

    The flags are named after the question they answer rather than after the
    command that asks it — commands get renamed and merged, and the question
    "may a maintenance pass rewrite files here" outlives whichever command is
    currently doing the rewriting.
    """

    #: One line: what this directory holds. Shown by `magi guide` and used in
    #: the layout section of the README, so it is documentation, not a comment.
    what: str

    #: A whole-project maintenance pass (`math format`, `lint --fix`, `link`,
    #: `tags apply`) may rewrite files here. False for anything append-only or
    #: derived: rewriting a discussion loses what somebody wrote.
    rewritten: bool

    #: The retrieval index walks it, so `magi search` can find it.
    searchable: bool

    #: `magi lint`'s generic document loader reads it. A directory can be
    #: checked without being in here — `threads/` has its own walker, because
    #: a note is a different shape from a card — so this means specifically
    #: "goes through `content_markdown_files`".
    documents: bool

    #: `magi graph build` takes nodes and edges from it.
    graphed: bool

    #: Priority when resolving `[[a-wikilink]]`; None means a link never lands
    #: here. Lower wins: a `derivation:` names a draft, and a concept card
    #: sharing a stem with a draft is the less likely target.
    wikilink: int | None = None

    #: Why a flag above is False when a reader would expect True. Kept as text
    #: rather than dropped, because "we decided not to" and "nobody has looked"
    #: are different states and only one of them is finished.
    note: str = ""


#: Every directory `magi init` creates, in the order the README lists them.
#: `test_project_layout.py` holds this against the scaffold in both
#: directions, so neither can grow a directory the other has not heard of.
LAYOUT: dict[str, Dir] = {
    "raw": Dir(
        what="Sources, the only truth: papers, articles, notes, data, repos.",
        rewritten=True, searchable=True, documents=True, graphed=False,
        note="Not graphed: the graph is a map of what has been written *about* "
             "the sources, and a source is the thing being written about.",
    ),
    "wiki": Dir(
        what="Compiled views: wiki/references (from raw), wiki/concepts, wiki/topics.",
        rewritten=True, searchable=True, documents=True, graphed=True,
        wikilink=3,
    ),
    "drafts": Dir(
        what="Working out, per line: drafts and derivations.",
        rewritten=True, searchable=True, documents=True, graphed=False,
        wikilink=1,
        note="Not graphed: undecided rather than settled. A draft carries "
             "wikilinks and a `derivation:`, so it has edges the graph does "
             "not currently show; adding them changes what `magi graph browse` "
             "displays and is a decision for a person, not a refactor.",
    ),
    "threads": Dir(
        what="Propositions, questions and lines, as forum-style notes.",
        rewritten=False, searchable=True, documents=False, graphed=True,
        wikilink=2,
        note="Not rewritten: append-only, so no maintenance pass reformats a "
             "post. Not in `documents`: linted by its own walker in "
             "`kb/threads.py`, because a note is not shaped like a card.",
    ),
    "inbox": Dir(
        what="Staging: sources waiting to be ingested, and notes.md.",
        rewritten=False, searchable=False, documents=False, graphed=False,
        note="Nothing here has been accepted into the project yet.",
    ),
    "output": Dir(
        what="Derived artefacts and ledgers: graph.db, index.db, MAP.md.",
        rewritten=False, searchable=False, documents=False, graphed=False,
        note="Regenerable by definition; a pass that read it would report "
             "every defect twice.",
    ),
    "scratch": Dir(
        what="Wastebasket, including concept backups.",
        rewritten=False, searchable=False, documents=False, graphed=False,
        note="Backups live here. A maintenance pass that rewrote them would "
             "destroy the copy being kept in case the pass went wrong.",
    ),
}


def dirs(**flags) -> tuple:
    """Directory names where every named flag holds.

        dirs(rewritten=True)            -> ('raw', 'wiki', 'drafts')
        dirs(searchable=True)           -> ('raw', 'wiki', 'drafts', 'threads')

    Callers name the question instead of retyping the answer, so a directory
    added to `LAYOUT` reaches every subsystem that said yes to it.
    """
    unknown = set(flags) - {f.name for f in Dir.__dataclass_fields__.values()}
    if unknown:
        raise ValueError(f"no such layout flag: {sorted(unknown)}")
    return tuple(
        name for name, spec in LAYOUT.items()
        if all(getattr(spec, flag) == want for flag, want in flags.items())
    )


def wikilink_dirs() -> tuple:
    """Where a `[[wikilink]]` may land, best candidate first."""
    ranked = [(spec.wikilink, name) for name, spec in LAYOUT.items()
              if spec.wikilink is not None]
    return tuple(name for _, name in sorted(ranked))


@dataclass(frozen=True)
class Project:
    """One project: a root, its config, and the layout above.

    Passed instead of a bare `Path` so that the things a caller has to
    remember stop being things a caller has to remember. The config is loaded
    once and travels with the root — the reason `magi reflect` could not see a
    host the project declared is that `config=` was an optional argument six
    call sites forgot — and `resolve()` cannot leave the root, so a path that
    came out of an ingested paper cannot address a file outside the project
    even if every caller forgets to check.
    """

    root: Path
    config: dict

    @classmethod
    def at(cls, start=None) -> "Project | None":
        """The project containing *start* (default: cwd), or None."""
        from .config_loader import load_config
        from .workspace import find_workspace_root

        root = find_workspace_root(start)
        if root is None:
            return None
        return cls(root=Path(root), config=load_config(start=root))

    @classmethod
    def of(cls, root) -> "Project":
        """The project rooted exactly at *root*, without searching for it."""
        from .config_loader import load_config

        root = Path(root)
        return cls(root=root, config=load_config(start=root))

    # -- the directories ---------------------------------------------------

    def __getattr__(self, name: str) -> Path:
        """`project.drafts` is `root / "drafts"`, for every name in LAYOUT."""
        if name in LAYOUT:
            return self.root / name
        raise AttributeError(name)

    def existing(self, **flags) -> list:
        """The directories matching *flags* that are actually on disk."""
        return [self.root / name for name in dirs(**flags)
                if (self.root / name).is_dir()]

    def markdown(self, **flags) -> list:
        """Every `.md` under the directories matching *flags*.

        Skips `_index.md` (generated) and anything under a `.backup/`, which
        is a copy of the file beside it: a pass that read both would report
        every defect twice and, worse, rewrite the copy being kept in case the
        pass went wrong.
        """
        out: list = []
        for base in self.existing(**flags):
            for path in sorted(base.rglob("*.md")):
                if path.name == "_index.md" or ".backup" in path.parts:
                    continue
                out.append(path)
        return out

    # -- paths from untrusted text -----------------------------------------

    def resolve(self, ref) -> Path:
        """*ref* relative to the root, refusing to leave it.

        A `sources:` field, a `SOURCE:` line and an uploaded filename all
        reach the filesystem after passing through text this project did not
        write. Both traversal holes found in review were a caller that forgot
        to check; a caller cannot forget this one.
        """
        candidate = (self.root / ref).resolve() if not os.path.isabs(ref) \
            else Path(ref).resolve()
        root = self.root.resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(f"{ref!r} resolves outside {self.root}")
        return candidate

    def contains(self, path) -> bool:
        """Whether *path* is inside this project. Never raises."""
        try:
            self.resolve(os.fspath(path))
            return True
        except (ValueError, OSError):
            return False
