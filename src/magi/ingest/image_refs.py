"""One shape for image references, and one place that says what it is.

Five routes produce Markdown and every one of them used to decide for itself
what an image reference looks like. They disagreed, and each disagreement was
a separate bug:

* the arXiv-HTML route wrote ``images/fig1.png`` — the *paper's own* basename,
  so two papers that both call a figure ``fig1.png`` overwrite each other in
  the shared ``raw/papers/images/`` directory and one paper silently shows the
  other's figure;
* the text-layer route wrote whatever absolute staging path ``pymupdf4llm``
  was handed (``C:/Users/.../Temp/tmpXXX/images/x.png``), which resolves for
  exactly as long as the staging directory exists — that is, until commit;
* the gate meant to catch precisely that only matched ``images/…``, so it read
  an absolute path as "no image references here" and reported the document
  clean.

The convention, stated once:

    Every image reference is ``images/<name>``, POSIX-relative, one level, and
    ``<name>`` carries the document's slug so it is unique inside the shared
    images directory of a library.

``images/`` is relative because the Markdown file and its images travel
together from staging into ``raw/<type>/``; anything absolute names a location
that will not exist after the move. The slug prefix is there because the
destination directory is shared by every paper in the library — uniqueness
within one document is not enough, and a collision there is the worst kind of
failure: nothing errors, nothing is missing, the figure is simply wrong.
"""

from __future__ import annotations

import os
import re

#: Where a route's images go, relative to the Markdown that references them.
IMAGE_DIR_NAME = "images"

#: Bound on the generated filename. `SLUG_MAX` (80) already accounts for
#: Windows' 260-character MAX_PATH; prefixing a slug onto a name that may
#: itself be long needs its own ceiling or the two stack up.
NAME_MAX = 110

# Both regexes are deliberately generous about the forms they accept, because
# the failure mode of a narrow one is not a mis-parse — it is a miss, and a
# checker that cannot see a reference reports the document as clean. That is
# exactly the defect this module exists to stop repeating, so widening these
# is cheaper than being right about which forms our routes happen to emit.

#: Two alternatives: a target containing a space is legal Markdown when it is
#: wrapped in angle brackets, and unquotable without them.
_MD_IMAGE_RE = re.compile(
    r"!\[[^\]]*\]\(\s*(?:<([^>]*)>|([^)\s]+))(?:\s+[\"'][^\"']*[\"'])?\s*\)")

#: Pandoc leaves any figure it cannot express in Markdown as raw HTML, which is
#: what happens to essentially every real arXiv figure — they sit inside
#: <figure> elements carrying ids and classes. Either quote style, because HTML
#: permits both even though pandoc only writes one.
_HTML_IMAGE_RE = re.compile(
    r'<(?:img|embed)\b[^>]*?\bsrc\s*=\s*(["\'])(.*?)\1', re.IGNORECASE)

_EXTERNAL_PREFIXES = ("http://", "https://", "data:", "//")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_UNSAFE_CHARS_RE = re.compile(r"[^\w.\-]+")


def iter_targets(md: str):
    """Every image target in the document, in the order they appear.

    Both spellings, one list. Duplicates are kept: a document that references
    the same file twice has two chances to be wrong about it.
    """
    md_targets = [bracketed or bare for bracketed, bare in _MD_IMAGE_RE.findall(md)]
    return md_targets + [target for _quote, target in _HTML_IMAGE_RE.findall(md)]


def is_external(target: str) -> bool:
    """A reference we neither own nor should rewrite."""
    return target.startswith(_EXTERNAL_PREFIXES)


def classify(target: str) -> str:
    """What is wrong with this reference, named so a message can say it.

    ``portable`` and ``external`` are both fine. Everything else is a reference
    that will not survive the move from staging into the library.
    """
    if is_external(target):
        return "external"
    if _WINDOWS_DRIVE_RE.match(target) or target.startswith(("/", "\\")):
        return "absolute"
    if "\\" in target:
        # A Windows separator in a Markdown link is not a path, it is an escape
        # sequence to anything that reads Markdown properly.
        return "backslash"
    parts = target.split("/")
    if ".." in parts:
        return "escaping"
    if len(parts) == 1:
        return "bare"
    if parts[0] != IMAGE_DIR_NAME:
        return "elsewhere"
    if len(parts) > 2:
        return "nested"
    return "portable"


def is_portable(target: str) -> bool:
    """True when a reference will still resolve after the document is moved."""
    return classify(target) in ("portable", "external")


def sanitize(filename: str) -> str:
    """A filename every filesystem we support will accept, unchanged if it can be."""
    name = _UNSAFE_CHARS_RE.sub("_", os.path.basename(filename.replace("\\", "/")))
    return name.strip("._") or "image"


def namespaced(slug: str, filename: str, *, max_length: int = NAME_MAX) -> str:
    """``<slug>-<name>``, the filename a route should write and reference.

    Idempotent: a name that already carries the slug is returned as-is, so a
    route whose upstream tool already namespaces its output (``pymupdf4llm``
    names files after the source PDF) does not end up prefixed twice.

    The truncation keeps the *tail* of the stem rather than the head. Figure
    names differ at the end — ``fig1``/``fig2``, ``-0001-01``/``-0001-02`` —
    so trimming from the front is what preserves the part that distinguishes
    two files from each other.
    """
    name = sanitize(filename)
    prefix = sanitize(slug)
    if not prefix or name.lower().startswith(prefix.lower() + "-"):
        return name[:max_length] if len(name) > max_length else name
    stem, ext = os.path.splitext(name)
    room = max_length - len(prefix) - 1 - len(ext)
    if room < 1:
        # A slug this long leaves no room for a name; keep the slug's head and
        # the extension, since the slug is what makes the file unique.
        return (prefix[:max_length - len(ext)] + ext)
    if len(stem) > room:
        stem = stem[-room:]
    return f"{prefix}-{stem}{ext}"


def rewrite(md: str, resolve, *, prefix: str = IMAGE_DIR_NAME + "/") -> tuple[str, dict[str, str]]:
    """Point every rewritable reference at ``<prefix><name>``.

    ``resolve(target)`` returns the local filename to use, or ``None`` to leave
    the reference alone. The returned mapping is ``{original target: local
    filename}`` — routes that fetch or copy the files afterwards must use it
    rather than recomputing the name, because the document and the directory
    agreeing is the whole point and two independent derivations of the same
    name is how they stop agreeing.

    ``prefix`` exists for the one caller that is not producing local files: a
    route may also need to repair references it does not own (arXiv's own site
    furniture, which pandoc drags in alongside the paper's figures), and those
    become whole URLs rather than entries in ``images/``.
    """
    mapping: dict[str, str] = {}

    def _local(target: str):
        if target in mapping:
            return mapping[target]
        if is_external(target) or classify(target) == "portable":
            return None
        name = resolve(target)
        if name:
            mapping[target] = name
        return name

    def _md_repl(m):
        target = m.group(1) or m.group(2)
        name = _local(target)
        return m.group(0).replace(target, f"{prefix}{name}", 1) if name else m.group(0)

    def _html_repl(m):
        quote, target = m.group(1), m.group(2)
        name = _local(target)
        if not name:
            return m.group(0)
        return m.group(0).replace(f"{quote}{target}{quote}",
                                  f"{quote}{prefix}{name}{quote}", 1)

    md = _MD_IMAGE_RE.sub(_md_repl, md)
    md = _HTML_IMAGE_RE.sub(_html_repl, md)
    return md, mapping
