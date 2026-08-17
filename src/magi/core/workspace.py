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
    return (path / "wiki").is_dir() or (path / "raw").is_dir()


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
    1. Upward walk from *start* (default: cwd) — a workspace- or
       hub-level config wins.
    2. User config dir: ``~/.config/magi/config.yaml``.
    """
    base = Path(start) if start is not None else Path.cwd()
    if base.is_file():
        base = base.parent
    for candidate in _walk_up(base):
        cfg = candidate / "config.yaml"
        if cfg.is_file():
            return cfg
    user_cfg = Path.home() / ".config" / "magi" / "config.yaml"
    if user_cfg.is_file():
        return user_cfg
    return None
