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


def atomic_write(filepath: str | Path, content: str, encoding: str = "utf-8", newline: str | None = None) -> None:
    """Safely and atomically write content to a file.

    Creates a temporary file in the same directory as the target file,
    writes the content, and then renames it to target file using os.replace.
    """
    import os
    import tempfile
    from pathlib import Path

    path = Path(filepath)
    dir_name = path.parent
    dir_name.mkdir(parents=True, exist_ok=True)

    fd, temp_path_str = tempfile.mkstemp(dir=dir_name, prefix=".tmp_atomic_")
    try:
        with open(fd, 'w', encoding=encoding, newline=newline) as f:
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
# What counts as "the library"
# --------------------------------------------------------------------------

# The same three trees `magi index` walks. scratch/ holds concept backups
# whose formulas are copies of the originals and output/ is generated, so a
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
