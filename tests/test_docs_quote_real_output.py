"""A doc that quotes an error the CLI never prints is worse than no example.

`test_docs_describe_reality` checks that every command the docs *name* exists.
It cannot see the other half: the docs also quote what commands *say*, and
those strings rot silently. This session produced two of them —

* `magi guide --search "no workspace found"` as a worked example of pasting an
  error verbatim, after that sentence became "no project found";
* the whole search chapter promising `magi search` federates by default, after
  the default became this project only.

The second is the dangerous kind. A reader who follows it does not get an
error; they get a different answer than the one described, and no reason to
doubt it.

What this pins is narrow on purpose: the exact sentences the docs put in the
reader's hands as things to type or expect. It is not a general spellchecker
for prose, and it should not become one — a check that flags paraphrase is a
check somebody turns off.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

DOCS = (
    "README.md",
    "README_en.md",
    "src/magi/docs/guide.zh.md",
    "src/magi/docs/guide.en.md",
)

#: Sentences the docs hand a reader to paste into `magi guide --search`. Each
#: has to be something the CLI actually emits, or the example teaches a search
#: that returns nothing.
_SEARCH_EXAMPLE = re.compile(r'magi guide --search "([^"]+)"')


def _all_docs() -> list[tuple[str, str]]:
    return [(name, (REPO / name).read_text(encoding="utf-8", errors="replace"))
            for name in DOCS]


def _cli_strings() -> str:
    """Every literal the CLI can print, as one haystack.

    Read from source rather than by running commands: the strings live in
    branches most runs never reach, and a test that only sees the happy path
    would bless exactly the errors nobody checks.
    """
    out = []
    for path in (REPO / "src" / "magi").rglob("*.py"):
        out.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


@pytest.mark.parametrize("doc", DOCS)
def test_a_guide_search_example_finds_something_real(doc):
    """`magi guide --search "<error>"` examples quote an error verbatim, so
    the quoted text has to be one the code can produce."""
    haystack = _cli_strings()
    text = (REPO / doc).read_text(encoding="utf-8", errors="replace")

    # `<报错>` and `<the error>` are placeholders telling the reader to paste
    # their own text. Only literal quotes are claims about what MAGI prints.
    missing = [phrase for phrase in _SEARCH_EXAMPLE.findall(text)
               if "<" not in phrase and phrase not in haystack]

    assert not missing, (
        f"{doc} tells the reader to search for text the CLI never prints: "
        f"{missing}")


#: Words that mean "it reaches past this project", in either language.
_REACHES_OUT = re.compile(r"联邦|跨项目|跨库|所有启用|federat|every enabled|"
                          r"all enabled|across .*projects", re.IGNORECASE)

#: Words that mean "by default".
_BY_DEFAULT = re.compile(r"默认|by default", re.IGNORECASE)


def test_the_docs_do_not_promise_the_old_search_default():
    """`--scope` defaults to `local`. Three chapters said it federated.

    Checked by shape, not by spelling. The first version of this test banned
    the exact string "默认联邦检索", and the vocabulary sweep rewrote the same
    false sentence as "默认就会联邦检索" — one particle, and the ban was gone.
    A phrase that can be paraphrased past a guard was never being guarded.

    So: any line that mentions `magi search`, says "by default", and also says
    it reaches other projects is the claim this is looking for, however it is
    worded.
    """
    from magi import retrieval

    assert retrieval.build_parser().parse_args(["search", "q"]).scope == "local", (
        "the default changed — this test is now guarding the wrong claim")

    offenders = []
    for name, text in _all_docs():
        for number, line in enumerate(text.splitlines(), 1):
            if "magi search" not in line:
                continue
            if _BY_DEFAULT.search(line) and _REACHES_OUT.search(line):
                offenders.append(f"{name}:{number}: {line.strip()[:70]}")

    assert not offenders, (
        "these say searching reaches other projects by default, and it does "
        f"not: {offenders}")


def test_the_dashboard_chapter_does_not_deny_what_the_dashboard_does():
    """It said `magi review` was "deliberately not" a dashboard action and
    that ingest, close and publish had no buttons. All four have one, and a
    chapter that tells somebody a feature is missing is worse than one that
    omits it — they will not go looking."""
    from magi.ui import jobs

    assert "ingest-auto" in jobs.OPS
    for name, text in _all_docs():
        for phrase in ("`magi review` **刻意不在其中**",
                       "is deliberately **not** one of them",
                       "**摄入不在其中**",
                       "**Ingestion isn't among them**"):
            assert phrase not in text, f"{name} denies something the browser does"


@pytest.mark.parametrize("doc", DOCS)
def test_the_task_count_is_the_real_one(doc):
    """The chapter states how many background tasks the dashboard can start.
    A number in prose is a fact that rots the moment somebody adds one."""
    from magi.ui import jobs

    text = (REPO / doc).read_text(encoding="utf-8", errors="replace")
    claimed = re.findall(r"(?:后台任务有|dashboard can trigger|There are)\s*(\d+)",
                         text)

    for number in claimed:
        assert int(number) == len(jobs.OPS), (
            f"{doc} says {number} background tasks; there are {len(jobs.OPS)}")


def test_retired_commands_are_not_taught():
    """`magi ingest batch-list/decide/commit` were retired this session —
    `magi ingest review` was always doing all three, and having both spellings
    is most of why that group read as seventeen commands."""
    from magi.cli import _COMMANDS

    for gone in ("batch-list", "batch-decide", "batch-commit"):
        assert ("ingest", gone) not in _COMMANDS, f"{gone} came back"

    for name, text in _all_docs():
        for gone in ("magi ingest batch-list", "magi ingest batch-decide",
                     "magi ingest batch-commit"):
            assert gone not in text, f"{name} still teaches {gone}"


def test_no_exemption_excuses_text_the_cli_never_prints():
    """`test_one_thing_one_word` excuses lines that quote real CLI output. An
    exemption for a sentence the code stopped printing is worse than none: it
    is a standing pass for a false quote, and it survives exactly the change
    that made the quote wrong.

    Two of them were already dead when this was written — `no workspace found`
    and `this library has knowledge but…`, both rewritten in the vocabulary
    merge — and the guides were still quoting both under their protection.
    """
    from tests import test_one_thing_one_word as vocab

    haystack = _cli_strings()

    # Walked from the tuple itself, not from a copy kept here by hand. The
    # first version listed the phrases in this file, so adding a stale one
    # over there changed nothing on this side.
    assert vocab.QUOTED_OUTPUT, "the exemption list vanished"
    for phrase in vocab.QUOTED_OUTPUT:
        assert phrase in haystack, (
            f"the guides are excused for quoting {phrase!r} as CLI output, and "
            f"nothing in src/magi prints it any more")
