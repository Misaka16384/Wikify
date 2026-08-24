"""Which parts of a markdown document a rewrite is allowed to touch.

Three separate regex passes in this repo rewrite markdown after every gate has
already run — `MarkdownCleaner._fix_latex` on the OCR route, `format_math`'s
delimiter cleanup on the KB side, and `image_refs.rewrite` on both. Whatever
they do to a document, nothing downstream will notice, and all three have been
caught doing damage:

* `_fix_latex` put blank lines around a stray ``$$`` that a model had left
  inside a table cell, splitting 19 table rows in half. The engine returned
  53 pipe rows; the file on disk carried 72. A table that reads cleanly and
  contains rows that were never in the document.
* `format_math` collapsed ``$$A$$ and $$B$$`` into one malformed block with
  the prose swallowed into the maths.
* pandoc's ``-t markdown`` default emitted simple tables that no GFM reader
  renders — the same shape one layer up.

Every one of those is the same mistake: a rule that is right for prose applied
to a span where it cannot be right. ``$$`` is a display-maths delimiter
everywhere except inside a table cell, where a cell cannot hold a block; a
fenced code block means what it says literally and nothing else.

So the protection is shared rather than re-derived per caller. It was
re-derived twice already, and the second version knew about tables but not
code fences while the first knew about code fences but not tables — each
missing exactly what the other had.
"""

from __future__ import annotations

import re
from typing import Callable, List, Tuple

CODE = "code"
TABLE = "table"
TEXT = "text"

_FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")


def normalize_newlines(text: str) -> str:
    """CRLF and lone CR to LF.

    Every rule below reasons in terms of ``\\n``, and on Windows a stray
    ``\\r`` sits between the last character of a line and its newline — which
    is precisely where patterns like ``([^\\n])\\s*\\$\\$`` look.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def classify_lines(text: str) -> List[Tuple[str, str]]:
    """Label every line ``CODE``, ``TABLE`` or ``TEXT``.

    A fence that is never closed protects everything to the end of the
    document. That is the conservative reading and the right one: an unclosed
    fence is already a broken document, and rewriting its contents cannot
    improve it.
    """
    out: List[Tuple[str, str]] = []
    fence: str | None = None       # the marker that opened the current block

    for line in text.split("\n"):
        m = _FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group(2)[0] * len(m.group(2))
                out.append((CODE, line))
            elif line.lstrip().startswith("|"):
                out.append((TABLE, line))
            else:
                out.append((TEXT, line))
            continue

        out.append((CODE, line))
        # A closing fence is the same character, at least as long, and carries
        # nothing after it. `` ```python `` opens; a bare `` ``` `` closes.
        if m and m.group(2)[0] == fence[0] and len(m.group(2)) >= len(fence) \
                and not m.group(3).strip():
            fence = None

    return out


def map_prose(text: str, fn: Callable[[str], str],
              *, protect: Tuple[str, ...] = (CODE, TABLE)) -> str:
    """Apply ``fn`` to each run of unprotected lines, leaving the rest alone.

    ``fn`` receives a whole run rather than one line at a time, so a pattern
    that legitimately spans a line break — a ``$$`` matched across two prose
    lines — keeps working. It may return any number of lines.
    """
    out: List[str] = []
    run: List[str] = []

    def flush() -> None:
        if run:
            out.extend(fn("\n".join(run)).split("\n"))
            run.clear()

    for kind, line in classify_lines(text):
        if kind in protect:
            flush()
            out.append(line)
        else:
            run.append(line)
    flush()
    return "\n".join(out)
