"""Documentation drift, caught by CI instead of by the user.

Five releases went out with features nobody had written down anywhere, and the
only thing that noticed was a person reading the docs later. These lock the
invariants that "remember to update the docs" was supposed to cover:

  - every skill that ships is named in both READMEs, which carry the full table
  - every command group the CLI dispatches is described in both guides
  - the two languages describe the same set of things
  - the skill counts the prose quotes match what actually ships
  - nothing is documented that no longer ships

The guides are task-organized and name a deliberate subset of the skills, so
they are held to parity with each other rather than to completeness.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
READMES = {"README.md": ROOT / "README.md", "README_en.md": ROOT / "README_en.md"}
GUIDES = {
    "guide.zh.md": ROOT / "src" / "magi" / "docs" / "guide.zh.md",
    "guide.en.md": ROOT / "src" / "magi" / "docs" / "guide.en.md",
}
ALL_DOCS = {**READMES, **GUIDES}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _skill_names() -> list[str]:
    from magi.skills_cmd import load_skills

    return sorted(s.name for s in load_skills())


# --------------------------------------------------------------------------
# skills
# --------------------------------------------------------------------------

@pytest.mark.parametrize("doc", sorted(READMES))
def test_every_shipped_skill_is_named_in_the_readme(doc):
    """The READMEs carry the complete skill table, so a skill added without a
    row there is a skill nobody can discover — the exact drift that prompted
    this file. The guides are task-organized and deliberately selective; they
    are held to parity with each other instead, below."""
    body = _text(READMES[doc])
    missing = [name for name in _skill_names() if name not in body]
    assert not missing, f"{doc} never mentions {missing}"


def test_the_guides_select_the_same_skills():
    """The guide names a subset on purpose. Which subset has to match across
    the two languages, or one reader gets pointed at a skill the other never
    hears about."""
    named = {}
    for name, path in GUIDES.items():
        body = _text(path)
        named[name] = {s for s in _skill_names() if s in body}
    assert named["guide.zh.md"] == named["guide.en.md"], (
        f"only in zh: {sorted(named['guide.zh.md'] - named['guide.en.md'])}\n"
        f"only in en: {sorted(named['guide.en.md'] - named['guide.zh.md'])}")


@pytest.mark.parametrize("doc", sorted(ALL_DOCS))
def test_the_skill_count_in_prose_matches_what_ships(doc):
    """"All 18 skills ship inside the wheel" stops being true the moment a
    nineteenth one lands."""
    body = _text(ALL_DOCS[doc])
    n = len(_skill_names())
    quoted = re.findall(r"(?:All\s+)?(\d+)\s*(?:个\s*(?:skill|技能)|skills)", body)
    wrong = [q for q in quoted if int(q) != n]
    assert not wrong, (
        f"{doc} says {wrong} skills; {n} actually ship. "
        f"Search the file for the number and fix it.")


#: Skill names are ordinary words now (`ask`, `compile`, `draft`), so a
#: name-*shape* pattern would match half the prose in the guide. Build the
#: alternation from what actually ships instead — which also means this file
#: needs no edit the next time a skill is added or retired.
_SKILL_NAME_RE = r"\b(" + "|".join(sorted(_skill_names(), key=len, reverse=True)) + r")\b"


def test_a_skill_documented_but_not_shipped_is_also_drift():
    """The other direction: a skill removed from the package but left in the
    docs sends the reader after something that is not there."""
    shipped = set(_skill_names())
    for doc, path in ALL_DOCS.items():
        named = set(re.findall(_SKILL_NAME_RE, _text(path)))
        ghosts = {n for n in named if n not in shipped}
        assert not ghosts, f"{doc} documents {sorted(ghosts)}, which no longer ship"


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def _command_groups() -> set[str]:
    from magi.cli import _COMMANDS

    return {key[0] for key in _COMMANDS}


@pytest.mark.parametrize("guide", sorted(GUIDES))
def test_every_command_group_appears_in_the_guide(guide):
    """The guide is the manual `magi guide` serves; a command group it never
    mentions is a feature with no documentation at all."""
    body = _text(GUIDES[guide])
    missing = [g for g in sorted(_command_groups()) if f"magi {g}" not in body]
    assert not missing, f"{guide} never mentions: {missing}"


# --------------------------------------------------------------------------
# the two languages
# --------------------------------------------------------------------------

def test_the_guides_describe_the_same_commands():
    """zh and en drift apart one edit at a time; each drift is a reader in one
    language missing a feature the other language has."""
    found = {}
    for name, path in GUIDES.items():
        found[name] = set(re.findall(r"magi ([a-z-]+)(?: [a-z-]+)?", _text(path)))
    only_zh = found["guide.zh.md"] - found["guide.en.md"]
    only_en = found["guide.en.md"] - found["guide.zh.md"]
    assert not (only_zh or only_en), (
        f"only in zh: {sorted(only_zh)}\nonly in en: {sorted(only_en)}")


def test_the_readmes_describe_the_same_skills():
    named = {}
    for name, path in READMES.items():
        named[name] = set(re.findall(rf"`{_SKILL_NAME_RE}`", _text(path)))
    assert named["README.md"] == named["README_en.md"], (
        f"only in zh: {sorted(named['README.md'] - named['README_en.md'])}\n"
        f"only in en: {sorted(named['README_en.md'] - named['README.md'])}")
