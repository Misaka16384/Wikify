"""Every guard in this repo, and the change that must make it fail.

A test written after a fix passes either way until somebody has watched it
fail. That sentence is in `design-v2.md` and in `ROADMAP.md`, and it has been
the most productive habit in this project — and until now it left nothing
behind. Each review round re-derived the same mutations by hand, ran them
once, and threw them away, so the next round could not tell a guard that bites
from a guard that has never been tried.

This is the list, kept. Each case names a guard, the exact text that makes it
hold, the exact text that used to be there, and the test that must go red in
between. Running it is the difference between "the suite is green" and "the
suite would notice".

    python -m tests.mutations              # all of them
    python -m tests.mutations layout       # one area

It edits files in place and restores them in a `finally`, so it refuses to
start on a dirty working tree: an interrupted run must never be mistaken for
somebody's unsaved work. Not part of the default pytest run — it rewrites
source and spawns a pytest per case, which is neither safe nor fast enough to
belong in the loop people run constantly.

**Adding a guard means adding a case here.** A guard nobody has watched fail
is a guard with an unknown value, and this file is where that gets checked.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    """One guard, and the smallest change that must break it."""

    #: What the mutation does, in the words of the defect it recreates.
    label: str
    #: Repo-relative file to edit.
    path: str
    #: Text as it stands today — the fix.
    fixed: str
    #: Text to put back — the defect. Empty string deletes the fix.
    broken: str
    #: Test file, optionally `<file> -k <expr>`, that must fail.
    target: str
    #: Which review round or area this belongs to.
    area: str = "misc"
