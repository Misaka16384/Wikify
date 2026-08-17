"""Unified workspace discovery.

This is the single source of truth for "where am I?" questions, replacing
three previously-independent implementations (llm-wiki resolve_wiki_root's
cwd heuristic, validate-output's find_wiki_root, config_loader's upward
walk). All new code must use these helpers; do not add a fourth walker.

Markers:
- topic workspace root: contains a ``wiki/`` or ``raw/`` directory
  (created by ``magi init``)
- hub root: contains ``wikis.json`` and a ``topics/`` directory
  (created by ``magi hub init``)
"""

from __future__ import annotations

import os
from pathlib import Path

_MAX_WALK = 30


def _walk_up(start: Path):
    current = start.resolve()
    for _ in range(_MAX_WALK):
        yield current
        if current.parent == current:
            return
        current = current.parent


def is_topic_root(path: Path) -> bool:
    """A MAGI topic workspace, not just any project with a wiki/ or raw/ dir.

    Requires a content dir AND a magi marker file (written by ``magi init``)
    so foreign repos that happen to contain ``raw/`` or ``wiki/`` in the
    ancestor chain are not misdetected by the upward walk.
    """
    has_content = (path / "wiki").is_dir() or (path / "raw").is_dir()
    has_marker = any((path / m).is_file() for m in ("config.md", "log.md", "config.yaml"))
    return has_content and has_marker


def is_hub_root(path: Path) -> bool:
    return (path / "wikis.json").is_file() and (path / "topics").is_dir()


def find_workspace_root(start: str | os.PathLike | None = None) -> Path | None:
    """Walk up from *start* (default: cwd) to the nearest topic workspace root.

    Returns ``None`` when no workspace marker is found up to the filesystem
    root. A hub root does NOT count as a topic workspace.
    """
    base = Path(start) if start is not None else Path.cwd()
    if base.is_file():
        base = base.parent
    for candidate in _walk_up(base):
        if is_topic_root(candidate):
            return candidate
    return None


def find_hub_root(start: str | os.PathLike | None = None) -> Path | None:
    """Walk up from *start* (default: cwd) to the nearest hub root."""
    base = Path(start) if start is not None else Path.cwd()
    if base.is_file():
        base = base.parent
    for candidate in _walk_up(base):
        if is_hub_root(candidate):
            return candidate
    return None


def find_config_yaml(start: str | os.PathLike | None = None) -> Path | None:
    """Locate the effective ``config.yaml``.

    Search order:
    1. Upward walk from *start* (default: cwd) — but ONLY config.yaml files
       sitting at a MAGI topic or hub root count. ``config.yaml`` is a very
       common filename (Hugo, CI, ML repos); accepting an arbitrary one
       from the ancestor chain would silently hijack model/OCR settings.
    2. User config dir: ``~/.config/magi/config.yaml``.
    """
    base = Path(start) if start is not None else Path.cwd()
    if base.is_file():
        base = base.parent
    for candidate in _walk_up(base):
        cfg = candidate / "config.yaml"
        if cfg.is_file() and (is_topic_root(candidate) or is_hub_root(candidate)):
            return cfg
    user_cfg = Path.home() / ".config" / "magi" / "config.yaml"
    if user_cfg.is_file():
        return user_cfg
    return None
