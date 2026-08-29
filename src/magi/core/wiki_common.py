"""Shared deterministic helpers for the llm-wiki bin scripts.

This module is deployed alongside the other scripts in ``bin/`` (the installer
copies ``bin/*``), so a sibling import — ``from wiki_common import ...`` — works
when a script is run as ``python .agents/bin/<script>.py`` (Python puts the
script's own directory on ``sys.path``).

It centralizes the frontmatter splitting/parsing and slug logic that previously
lived as near-duplicate copies in several scripts. The fence logic mirrors the
canonical implementation in ``llm-wiki.py`` (``---\\n`` ... ``\\n---``), which
remains the feature-rich reference parser (it adds YAML self-healing on top).
"""

from __future__ import annotations

import re
from typing import Any

try:  # pyyaml is a declared dependency, but degrade gracefully if absent.
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

# PyYAML ships two loaders: a pure-Python one and a libyaml-backed C one that
# is roughly an order of magnitude faster. `yaml.safe_load` always picks the
# slow one. Frontmatter is parsed once per card on every backlog scan, which
# runs on `magi sync`, on the dashboard, and on the Melchior panel — so the
# slow loader was a measurable share of those. Same safe subset either way.
if yaml is not None:
    _SafeLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
else:  # pragma: no cover - pyyaml missing
    _SafeLoader = None


def normalize_newlines(text: str) -> str:
    """Normalize CRLF / CR to LF for cross-platform frontmatter parsing."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_frontmatter_text(text: str) -> tuple[str, str] | None:
    """Split a markdown document into (frontmatter_text, body).

    Returns ``None`` when the document has no well-formed leading frontmatter.
    The frontmatter text excludes the ``---`` fences; the body includes
    everything after the closing fence (matching ``llm-wiki.py``).
    """
    text = normalize_newlines(text)
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return text[4:end], text[end + 4:]


def parse_frontmatter_text(fm_text: str) -> dict[str, Any]:
    """Parse a frontmatter block (without fences) into a dict.

    Robust: uses ``yaml.safe_load`` and never raises. Returns ``{}`` when the
    block is empty, not a mapping, or unparseable.
    """
    if yaml is None:
        return {}
    try:
        data = yaml.load(fm_text, Loader=_SafeLoader)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse YAML frontmatter from a full markdown string. Returns ``{}`` when
    frontmatter is absent or unparseable. Never raises."""
    parts = split_frontmatter_text(text)
    if parts is None:
        return {}
    return parse_frontmatter_text(parts[0])


#: Longest slug a filename may carry. Windows still enforces a 260-character
#: MAX_PATH unless the machine has opted into long paths, which is off by
#: default. A real paper title runs well past 200 characters, and the figure
#: files are longer still (``<slug>-fig12.png`` under ``images/``), so an
#: uncapped slug turns a workspace one directory too deep into a hard failure
#: on Windows while working fine on macOS and Linux.
SLUG_MAX = 80


def slugify(value: str, max_length: int = SLUG_MAX) -> str:
    """Unicode-aware slug, matching ``llm-wiki.py``'s canonical slugify.

    Keeps CJK and accented word characters (so non-ASCII concept names produce
    valid, non-empty filenames) while stripping path separators and other
    punctuation, and bounds the length so the result is a usable filename
    everywhere.
    """
    value = value.lower().replace("_", "-")
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^\w-]", "", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    if max_length and len(value) > max_length:
        # Cut on a word boundary when there is one nearby, so the truncation
        # reads as a shortened title rather than a corrupted one.
        cut = value[:max_length]
        head, sep, _ = cut.rpartition("-")
        value = (head if sep and len(head) >= max_length // 2 else cut).strip("-")
    return value


def file_newline(path: str | Path) -> str:
    """The line ending a file already uses, or the platform's for a new one.

    `atomic_write`'s default rewrites a whole file in the platform ending,
    which on Windows turns a one-line edit to an LF file into a diff of every
    line. Notes travel between macOS and Windows sessions, so a rewrite has to
    put back what it found rather than what this machine prefers.
    """
    import os
    from pathlib import Path as _Path

    try:
        raw = _Path(path).read_bytes()
    except OSError:
        return os.linesep
    if b"\r\n" in raw:
        return "\r\n"
    if b"\n" in raw:
        return "\n"
    return os.linesep


def atomic_write(filepath: str | Path, content: str, encoding: str = "utf-8",
                 newline: str | None = None, errors: str = "strict") -> None:
    """Safely and atomically write content to a file.

    Creates a temporary file in the same directory as the target file,
    writes the content, and then renames it to target file using os.replace.

    `errors` defaults to `"strict"` so that a mis-encoded write fails loudly.
    The one caller that overrides it is `managed.write`, which pairs
    `surrogateescape` on the read with `surrogateescape` here to round-trip
    a file somebody saved as cp1252 without touching the bytes it did not
    come to change.
    """
    import os
    import tempfile
    from pathlib import Path

    path = Path(filepath)
    dir_name = path.parent
    dir_name.mkdir(parents=True, exist_ok=True)

    fd, temp_path_str = tempfile.mkstemp(dir=dir_name, prefix=".tmp_atomic_")
    try:
        with open(fd, 'w', encoding=encoding, newline=newline, errors=errors) as f:
            f.write(content)
        os.replace(temp_path_str, path)
    except Exception:
        if os.path.exists(temp_path_str):
            try:
                os.remove(temp_path_str)
            except OSError:
                pass
        raise



# --------------------------------------------------------------------------
# Directory index files (_index.md)
# --------------------------------------------------------------------------

# Four functions rendered `_index.md` in three different formats, and three
# orchestrators ran them in three different orders, so the same file came out
# differently depending on whether you had just ingested, just compiled or
# just initialised the workspace — `magi ingest finalize` ends on reindex,
# `compile` ends on lint, and each one's output was the other's diff.
# They disagreed about the byline, the table separator, whether the first
# column held the filename or the title, whether `## Categories` existed,
# whether a summary with a pipe in it broke the table, and which frontmatter
# key dated a row.
#
# The shape below is the one `compile/templates/index_template.md` has
# documented all along: a Contents table keyed by filename, then Categories
# when the frontmatter actually distinguishes any. Everything that writes an
# index goes through here so there is nothing left to disagree about.

INDEX_BYLINE = "> Generated by magi — the tables below are rebuilt on every pass."

#: Anything from this heading down is the reader's, not ours. Nothing
#: generates it, the template invites an agent to keep a changelog there, and
#: a rebuild that silently ate it would be the same class of bug as the one
#: this module exists to fix.
INDEX_KEPT_HEADING = "## Recent Changes"


def index_title(directory) -> str:
    from pathlib import Path

    name = Path(directory).name
    if name == "wiki":
        return "Wiki Index"
    if name == "raw":
        return "Raw Index"
    return name.replace("-", " ").replace("_", " ").title() + " Index"


def index_cell(value) -> str:
    """One table cell: whitespace collapsed, pipes escaped.

    Only one of the old renderers escaped pipes, so a summary containing one
    tore the table in half in exactly half the code paths.
    """
    import re

    return re.sub(r"\s+", " ", str(value or "")).replace("|", "\\|").strip()


def _index_rows(directory):
    from pathlib import Path

    rows, categories = [], {}
    for path in sorted(Path(directory).glob("*.md")):
        if path.name == "_index.md":
            continue
        try:
            fm = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            fm = {}
        tags = fm.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        elif isinstance(tags, dict):
            tags = list(tags)
        elif not isinstance(tags, (list, tuple)):
            tags = [tags]
        # `ingested` is what the ingest routes stamp and `created` is what the
        # templates stamp; taking only one of them left half the library
        # undated depending on how it arrived.
        updated = fm.get("updated") or fm.get("ingested") or fm.get("created") or ""
        rows.append("| [{n}](<{n}>) | {s} | {t} | {u} |".format(
            n=path.name,
            s=index_cell(fm.get("summary")),
            t=index_cell(", ".join(str(t) for t in tags)),
            u=index_cell(updated)))
        cat = index_cell(fm.get("category") or fm.get("type") or "Uncategorized")
        categories.setdefault(cat, []).append(path.name)
    return rows, categories


def render_index(directory, *, today: str, existing: str | None = None) -> str:
    """The full text of one directory's `_index.md`.

    *existing* is the file's current contents, if any: whatever sits under
    ``## Recent Changes`` there is carried through untouched. Passing ``None``
    means "there is nothing to keep", not "discard it".
    """
    rows, categories = _index_rows(directory)

    parts = [
        f"# {index_title(directory)}",
        "",
        INDEX_BYLINE,
        "",
        f"Last updated: {today}",
        "",
        "## Contents",
        "",
        "| File | Summary | Tags | Updated |",
        "| :--- | :--- | :--- | :--- |",
    ]
    parts.extend(rows)
    parts.append("")

    # A "Categories" list that puts every file under "Uncategorized" is a
    # second copy of the table above wearing a hat. Show it when the
    # frontmatter actually separates things.
    if len(categories) > 1:
        parts += ["## Categories", ""]
        for cat, names in sorted(categories.items()):
            links = ", ".join(f"[{n}](<{n}>)" for n in names)
            parts.append(f"*   **{cat}**: {links}")
        parts.append("")

    if existing and INDEX_KEPT_HEADING in existing:
        parts.append(existing[existing.index(INDEX_KEPT_HEADING):].rstrip())
    return "\n".join(parts).rstrip() + "\n"


def write_index(path, *, today: str, directory=None) -> bool:
    """Rebuild one `_index.md`, atomically, and say whether it changed.

    The date line is part of the content, so stamping it unconditionally made
    every index dirty once a day whether or not a single row had moved — a
    whole-wiki diff every morning, and a wiki mtime that pushed the graph to
    "stale" for no reason. Compare everything *except* that line, and leave
    the file alone when nothing else moved.
    """
    from pathlib import Path

    path = Path(path)
    directory = Path(directory) if directory is not None else path.parent
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        existing = None

    text = render_index(directory, today=today, existing=existing)
    if existing is not None and _index_body(existing) == _index_body(text):
        return False
    atomic_write(path, text)
    return True


def _index_body(text: str) -> str:
    return "\n".join(line for line in text.split("\n")
                     if not line.startswith("Last updated:"))


# --------------------------------------------------------------------------
# What counts as "the library"
# --------------------------------------------------------------------------

# The same three trees `magi index` walks. output/ is generated and the
# concept backups under `wiki/**/.backup/` are copies of the originals, so a
# maintenance pass that included them would report every defect twice — and,
# worse, rewrite the backups you were keeping in case the fix went wrong.
CORPUS_DIRS = ("wiki", "raw", "drafts")


def corpus_files(root) -> list:
    """Every markdown file a workspace-wide maintenance pass should touch.

    Falls back to a plain recursive walk when *root* is not a workspace at
    all — a bare folder of notes still deserves an answer rather than silence.
    """
    from pathlib import Path

    root = Path(root).resolve()
    out: list = []
    for base in CORPUS_DIRS:
        d = root / base
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.md")):
            rel = p.relative_to(root)
            if p.name == "_index.md" or ".backup" in rel.parts:
                continue
            if any(part.startswith(".") for part in rel.parts):
                continue
            out.append(p)
    if not out and not any((root / b).is_dir() for b in CORPUS_DIRS):
        out = sorted(p for p in root.rglob("*.md")
                     if not any(part.startswith(".") for part in p.relative_to(root).parts))
    return out
