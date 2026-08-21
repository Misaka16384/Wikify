"""Which optional parts of MAGI this machine has turned on.

Two different kinds of "optional" get answered here, and keeping them apart
matters because only one of them is something MAGI can act on:

*Features* are MAGI's own workflows — the literature radar, task tracking.
Turning one off is a preference, and turning it back on is a button.

*Tools* are other people's software — Ollama, Pandoc, Poppler, LaTeX — plus
MinerU, which is a hosted service. MAGI cannot install any of them. The only
honest thing a "turn this on" button can do for those is open the download
page and offer to look again afterwards. The one exception is Beads (``bd``),
the task-tracking store, which MAGI does install itself.

State lives in the global settings file under ``optional_features``, written by
``magi setup``. A key that is absent means *never asked*, which reads as ON:
a user who upgrades into this release must not lose a panel they were using.
Only an explicit ``false`` turns something off.
"""

from __future__ import annotations

from typing import NamedTuple


class Feature(NamedTuple):
    """One of MAGI's own capabilities, which the user may not want."""

    key: str
    label: str
    #: One sentence, in the second person, on what having it on buys you.
    what: str
    #: Binary this feature needs, or "" when it is pure MAGI.
    needs: str
    #: Whether `magi setup` can install `needs` without help.
    magi_installs: bool


FEATURES: tuple[Feature, ...] = (
    Feature(
        key="radar",
        label="Literature radar",
        what="watches arXiv and Semantic Scholar for new papers in your area, "
             "and queues them for you to triage",
        needs="",
        magi_installs=False,
    ),
    Feature(
        key="tasks",
        label="Task tracking",
        what="turns your reading and compiling backlog into a dependency-aware "
             "task graph",
        needs="bd",
        magi_installs=True,
    ),
)

FEATURE_KEYS = tuple(f.key for f in FEATURES)


def _settings() -> dict:
    from magi.kb_registry import load_settings

    return load_settings()


def feature_enabled(key: str, settings: dict | None = None) -> bool:
    """Is this feature on? Absent means never asked, which means on.

    `profile: kb-only` predates this and is the older way of saying "no task
    tracking". It still wins, so an existing kb-only machine does not quietly
    grow a Balthasar panel because the newer key was never written.
    """
    data = _settings() if settings is None else settings
    if key == "tasks" and data.get("profile") == "kb-only":
        return False
    chosen = data.get("optional_features") or {}
    value = chosen.get(key)
    return True if value is None else bool(value)


def set_feature(key: str, enabled: bool) -> None:
    """Persist a feature choice. Keeps `profile` in step for `tasks`.

    Leaving a stale `profile: kb-only` behind would make `feature_enabled`
    keep returning False no matter what was just written, so the two
    representations are updated together rather than allowed to disagree.
    """
    if key not in FEATURE_KEYS:
        raise ValueError(f"unknown feature: {key!r}")
    from magi.kb_registry import load_settings, save_settings

    data = load_settings()
    chosen = dict(data.get("optional_features") or {})
    chosen[key] = bool(enabled)
    data["optional_features"] = chosen
    if key == "tasks":
        data["profile"] = "full" if enabled else "kb-only"
    save_settings(data)


def enabled_features(settings: dict | None = None) -> dict[str, bool]:
    data = _settings() if settings is None else settings
    return {f.key: feature_enabled(f.key, data) for f in FEATURES}
