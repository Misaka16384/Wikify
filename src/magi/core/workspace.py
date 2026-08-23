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
    2. The user config file.

    Kept for callers that want "the one file that decides". ``load_config``
    no longer uses it: the two are *layers*, not alternatives, and treating
    them as alternatives meant the user file was unreachable for anyone with
    a workspace — which is everyone.
    """
    return find_workspace_config_yaml(start) or user_config_yaml()


def config_home() -> Path:
    """Where per-user MAGI state lives. ``MAGI_CONFIG_HOME`` overrides it.

    Lives here rather than in ``kb_registry`` because both the registry and
    the config loader need it and ``kb_registry`` already imports this module
    — putting it the other way round would be a cycle. It was previously
    private to the registry, so ``find_config_yaml`` hardcoded
    ``~/.config/magi`` instead: a test that isolated the registry still read
    the developer's real settings, which is the kind of leak that shows up
    only as an inexplicable pass.
    """
    override = os.environ.get("MAGI_CONFIG_HOME")
    return Path(override) if override else Path.home() / ".config" / "magi"


def user_config_yaml() -> Path | None:
    """``<config home>/config.yaml`` when it exists."""
    path = config_home() / "config.yaml"
    return path if path.is_file() else None


def find_workspace_config_yaml(start: str | os.PathLike | None = None) -> Path | None:
    """The nearest workspace- or hub-level config.yaml, and nothing else."""
    base = Path(start) if start is not None else Path.cwd()
    if base.is_file():
        base = base.parent
    for candidate in _walk_up(base):
        cfg = candidate / "config.yaml"
        if cfg.is_file() and (is_topic_root(candidate) or is_hub_root(candidate)):
            return cfg
    return None
