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

    One fact, one place. There used to be a second spelling —
    ``profile: kb-only`` — held in step with this one by ``set_feature``, and
    the drift it invited arrived on schedule: ``magi setup --full`` assigned
    ``profile`` directly, the newer key still said False, and the command
    printed "profile set to full" while changing nothing.

    Keeping two representations in sync is a maintenance obligation that has to
    be discharged correctly at every write site, forever. Removing one is
    discharged once. `profile` is gone: not read, not written, not derived
    back. A machine that was kb-only and never touched the newer key reads as
    "never asked", which is on — a deliberate clean break rather than a
    compatibility layer, per locked decision D9.
    """
    data = _settings() if settings is None else settings
    chosen = data.get("optional_features") or {}
    value = chosen.get(key)
    return True if value is None else bool(value)


def set_feature(key: str, enabled: bool) -> None:
    """Persist a feature choice. The only writer, and now the only spelling.

    A stale ``profile`` left on disk from an older release is discarded here
    rather than maintained: this is the one function that rewrites the block,
    so it is the cheapest place to make sure the dead key does not survive to
    confuse somebody reading the file by hand.
    """
    if key not in FEATURE_KEYS:
        raise ValueError(f"unknown feature: {key!r}")
    from magi.kb_registry import edit_settings

    with edit_settings() as data:
        chosen = dict(data.get("optional_features") or {})
        chosen[key] = bool(enabled)
        data["optional_features"] = chosen
        data.pop("profile", None)


def enabled_features(settings: dict | None = None) -> dict[str, bool]:
    data = _settings() if settings is None else settings
    return {f.key: feature_enabled(f.key, data) for f in FEATURES}
