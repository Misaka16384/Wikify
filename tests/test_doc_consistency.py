"""Every document must give the same install and upgrade advice.

There are seven places that tell someone how to get MAGI — two READMEs, two
guides, two installer scripts and the plugin manifests — plus a maintainer
document that deliberately says something different because it is doing a
different job. They drift, and a reader who follows the stale one ends up with
a command that fails or silently does nothing.

The facts these tests encode were established by running the commands:

* `pipx upgrade --install magi-research` installs when missing and upgrades
  when present. It is the one command users are given.
* `pipx install --force <pinned>` is broken under pipx's uv backend: it exits 1
  after printing "Installing to existing venv" and leaves the old version in
  place. Only RELEASING.md may name it, and only as a warning.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

CANON = "pipx upgrade --install magi-research"

#: Everything a user might read to learn how to install.
USER_DOCS = [
    REPO / "README.md",
    REPO / "README_en.md",
    REPO / "src" / "magi" / "docs" / "guide.en.md",
    REPO / "src" / "magi" / "docs" / "guide.zh.md",
]

RELEASING = REPO / "docs" / "RELEASING.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# one command, everywhere
# --------------------------------------------------------------------------

@pytest.mark.parametrize("doc", USER_DOCS, ids=lambda p: p.name)
def test_every_user_doc_gives_the_canonical_command(doc):
    assert CANON in _read(doc), (
        f"{doc.name} never names the command every other document gives")


@pytest.mark.parametrize("doc", USER_DOCS, ids=lambda p: p.name)
def test_no_user_doc_recommends_the_broken_force_install(doc):
    """`pipx install --force` leaves the old version installed here.

    A user who follows it thinks they upgraded and did not — the worst kind of
    wrong instruction, because nothing visibly fails.
    """
    text = _read(doc)
    offenders = [ln.strip() for ln in text.splitlines()
                 if "pipx install --force" in ln]
    assert not offenders, (
        f"{doc.name} recommends a command that silently does nothing:\n  "
        + "\n  ".join(offenders))


def test_only_the_maintainer_doc_mentions_the_broken_command_and_warns():
    """It has to be named somewhere, so the next maintainer does not rediscover
    it the slow way — but named as a trap, not as a recipe."""
    text = _read(RELEASING)
    assert "pipx install --force" in text, (
        "the trap is undocumented; the next release will rediscover it")
    idx = text.index("pipx install --force")
    window = text[max(0, idx - 400):idx + 400]
    assert "Do not use" in window or "WARN" in window, (
        "RELEASING.md names the broken command without marking it as broken")


# --------------------------------------------------------------------------
# the two languages must say the same thing
# --------------------------------------------------------------------------

def _commands(text: str) -> set[str]:
    """The *shape* of each command in a fenced block: verbs and flags only.

    Example arguments are meant to differ between languages — `magi search
    "anyon statistics"` and `magi search "任意子统计"` are the same instruction,
    correctly localised. So quoted values and <placeholders> collapse to a
    marker, and what is left is the part the two documents must agree on:
    which command, with which flags.
    """
    out: set[str] = set()
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.DOTALL):
        for line in block.splitlines():
            line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
            if not re.match(r"^(magi|pipx|uv|curl|powershell|irm)\b", line):
                continue
            line = re.sub(r'"[^"]*"', " ", line)        # quoted example values
            line = re.sub(r"<[^>]*>", " ", line)        # <name> / <名字>
            tokens = line.split()
            # Skeleton = the words before the first flag, plus the flag names.
            # A flag's *value* is an example too (`--q topology` vs `--q 拓扑`)
            # and is no more required to match than a quoted one.
            words, flags = [], []
            for tok in tokens:
                if tok.startswith("-"):
                    flags.append(tok.split("=", 1)[0])
                elif not flags:
                    words.append(tok)
            out.add(" ".join(words + sorted(flags)))
    return out


def test_the_two_guides_prescribe_the_same_commands():
    en = _commands(_read(REPO / "src" / "magi" / "docs" / "guide.en.md"))
    zh = _commands(_read(REPO / "src" / "magi" / "docs" / "guide.zh.md"))
    only_en, only_zh = sorted(en - zh), sorted(zh - en)
    assert not only_en and not only_zh, (
        "the guides disagree on substance:\n"
        f"  only in EN: {only_en}\n  only in ZH: {only_zh}")


def test_the_two_readmes_prescribe_the_same_commands():
    en = _commands(_read(REPO / "README_en.md"))
    zh = _commands(_read(REPO / "README.md"))
    only_en, only_zh = sorted(en - zh), sorted(zh - en)
    assert not only_en and not only_zh, (
        "the READMEs disagree on substance:\n"
        f"  only in EN: {only_en}\n  only in ZH: {only_zh}")


# --------------------------------------------------------------------------
# the scripts must do what the guides say they do
# --------------------------------------------------------------------------

def test_the_installers_run_the_command_the_guides_describe():
    """Both guides tell the reader the one-line installer runs this. If the
    script changes and the prose does not, the prose is a lie about software
    the reader is about to pipe into a shell."""
    for script in (REPO / "install.sh", REPO / "install.ps1"):
        text = _read(script)
        assert "upgrade --install" in text, (
            f"{script.name} no longer runs the idempotent form the guides promise")


def test_the_installers_prefer_pipx_and_keep_uv_as_the_fallback():
    for script in (REPO / "install.sh", REPO / "install.ps1"):
        text = _read(script)
        assert text.index("pipx") < text.index("astral.sh/uv"), (
            f"{script.name} reaches for uv before pipx")


# --------------------------------------------------------------------------
# things this release added that the docs have to know about
# --------------------------------------------------------------------------

@pytest.mark.parametrize("guide", ["guide.en.md", "guide.zh.md"],)
def test_both_guides_document_the_cloud_embedding_block(guide):
    text = _read(REPO / "src" / "magi" / "docs" / guide)
    assert "embedding-cloud" in text, f"{guide} has no cloud-embedding section"
    for key in ("embedding.provider", "embedding.base_url", "embedding.api_key"):
        assert key in text or key.split(".")[-1] in text, f"{guide} omits {key}"


@pytest.mark.parametrize("guide", ["guide.en.md", "guide.zh.md"])
def test_both_guides_name_the_rebuild_flag(guide):
    """Changing embedding model needs it, and a remediation hint that names a
    flag the docs never mention sends the reader looking in the wrong place."""
    text = _read(REPO / "src" / "magi" / "docs" / guide)
    assert "magi index --rebuild" in text, f"{guide} never mentions --rebuild"


def test_the_rebuild_flag_the_docs_promise_actually_exists():
    import subprocess
    import sys

    out = subprocess.run([sys.executable, "-m", "magi.cli", "index", "--help"],
                         capture_output=True, text=True, timeout=60)
    assert "--rebuild" in out.stdout


# --------------------------------------------------------------------------
# a document must not contradict itself, or the software
# --------------------------------------------------------------------------

@pytest.mark.parametrize("guide", ["guide.en.md", "guide.zh.md"])
def test_no_guide_denies_a_flag_that_exists(guide):
    """Both guides prescribed `magi index --rebuild` and then, 350 lines
    later, stated the flag does not exist. Naming a flag is not enough — the
    earlier test only checked it was mentioned somewhere, which a page that
    also denies it still satisfies.
    """
    text = _read(REPO / "src" / "magi" / "docs" / guide)
    denials = [ln.strip() for ln in text.splitlines()
               if "--rebuild" in ln
               and re.search(r"\bno\b.*--rebuild|--rebuild.*\bno\b|没有.*--rebuild", ln)]
    assert not denials, (
        f"{guide} says the flag does not exist:\n  " + "\n  ".join(denials))


def test_the_skill_count_in_the_docs_matches_the_shipped_skills():
    """Three documents carried three different hardcoded counts — 19, 18 and
    a docstring saying 18 — against an actual 20. A number written by hand in
    prose drifts the moment a skill is added, and nothing notices.
    """
    from magi.skills_cmd import load_skills

    real = len(load_skills())
    shipped = len(list((REPO / "src" / "magi" / "skills").glob("*/SKILL.md")))
    assert real == shipped, "load_skills() disagrees with what is on disk"

    for doc in (REPO / "src" / "magi" / "docs" / "guide.en.md",
                REPO / "src" / "magi" / "docs" / "guide.zh.md"):
        for line in _read(doc).splitlines():
            # Only lines actually talking about skills — "0/0 claims verified"
            # is a different N/N and none of this test's business.
            if not re.search(r"skills|技能", line):
                continue
            claims = (re.findall(r"\b(\d+)/\1\b", line)
                      + re.findall(r"\b(\d+) skills\b", line)
                      + re.findall(r"(\d+) 个技能", line))
            for claim in claims:
                assert int(claim) == real, (
                    f"{doc.name} claims {claim} skills, there are {real}:\n"
                    f"  {line.strip()}")
