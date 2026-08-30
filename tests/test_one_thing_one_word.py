"""A directory holding one research subject has one name: **project**.

It had five. `design-v2` §2 settles it in a line — *project = 一个知识库 =
一个目录* — but the code said `workspace`, the CLI said `topic`, the dashboard
said `Knowledge Base`, the prose said 本库, and the task-tracking panel said
课题. Three rounds of usability testing listed "本库 / 知识库 / 工作区 / Hub"
among the terms shown on screen and defined nowhere, and a modal existed whose
entire job was to disambiguate three of them.

Merging them made that modal read "**项目**（也叫项目）", which is the clearest
evidence available that the distinction was never real.

What this test guards is the *screen*, not the source. Three things keep their
old spelling on purpose and are asserted to keep it, because each is a
different word that happens to look the same:

* `/api/workspace/*` — a URL is a contract.
* `wiki/topics/` — a real directory of synthesis writeups.
* "library" in `Zotero library` and `graph physics library` — somebody else's
  product, and a JavaScript dependency.

`--topic-dir` also survives, as an accepted alias, because a rename that breaks
everybody's scripts to save them one word is not worth it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "src" / "magi" / "ui" / "static" / "app.js"
INDEX = ROOT / "src" / "magi" / "ui" / "static" / "index.html"

#: Entries whose "library" is not this system's. Named, so that adding one is
#: a decision somebody makes rather than a regex accident.
NOT_OURS = {
    "zotero_loading", "zotero_whole_library", "zotero_pick",
    "graph_map_no_d3",
    "core_detail_bal_uninit", "bal_no_db_initialized", "bal_store_at",
    "bal_store_shared", "bal_store_local", "bal_init_writes_hub",
    # The one place the old words belong: the modal that says they were all
    # this same thing. Excluding it is not a loophole — a reader who knew the
    # system under an old name needs that sentence to recognise it.
    "scope_help_body",
}

#: The words that used to mean "project" and must no longer appear on screen.
RETIRED = re.compile(r"工作区|工作空间|知识库|本库|课题|\bworkspace|\bWorkspace"
                     r"|knowledge base|Knowledge Base", re.IGNORECASE)

#: Things that legitimately contain one of those substrings.
ALLOWED = re.compile(r"api/workspace|wiki/topics|--topic-dir")


def _dictionary(lang: str) -> dict:
    js = APP_JS.read_text(encoding="utf-8", errors="replace")
    start = js.index(f"    {lang}: {{")
    end = js.index("\n    },", start)
    return dict(re.findall(r"^\s{6}(\w+):\s*(.+)$", js[start:end], re.MULTILINE))


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_the_screen_uses_one_word(lang):
    """Every string the dashboard shows, in both languages."""
    offenders = []
    for key, value in _dictionary(lang).items():
        if key in NOT_OURS or ALLOWED.search(value):
            continue
        if RETIRED.search(value):
            offenders.append((key, value[:70]))

    assert not offenders, (
        f"{lang} still calls a project something else: {offenders}")


def test_the_page_itself_uses_one_word():
    """`data-i18n` carries a fallback that shows before the dictionary loads,
    so a stale label here is a word somebody sees first."""
    html = INDEX.read_text(encoding="utf-8")

    # What is rendered, not what is written: element ids, CSS classes and
    # `data-i18n` *keys* all contain "workspace" and none of them is a word
    # anybody reads. The first version of this test flagged
    # `class="workspace-select-group"` and would have pushed a rename into
    # the stylesheet for nothing.
    shown = re.findall(r">([^<>]+)<", html)
    shown += re.findall(r'placeholder="([^"]*)"', html)
    shown += re.findall(r'title="([^"]*)"', html)

    offenders = [s.strip()[:70] for s in shown
                 if s.strip() and RETIRED.search(s) and not ALLOWED.search(s)]

    assert not offenders, f"index.html shows: {offenders}"


def test_the_words_that_only_look_alike_are_left_alone():
    """A blind sweep would have renamed a task database into a project and
    told somebody their Zotero was a research subject. Each of these is a
    different word that happens to be spelled the same."""
    js = APP_JS.read_text(encoding="utf-8", errors="replace")
    zh = _dictionary("zh")
    en = _dictionary("en")

    # Per entry, not "the word appears somewhere". Three entries say 任务库
    # and the first version of this test passed with one of them renamed,
    # because the other two still carried the word.
    for key in ("bal_store_local", "bal_store_at", "bal_store_shared"):
        assert "任务库" in zh[key], f"{key}: the beads task database got renamed"
    assert "library" in en["zotero_whole_library"],         "somebody else's product got renamed"
    assert "Zotero library" in en["zotero_loading"],         "somebody else's product got renamed"
    assert "/api/workspace/" in js, "a URL is a contract"


def test_both_spellings_of_the_flag_are_accepted():
    """A rename that breaks everybody's scripts to save them one word is not
    worth it, so `--topic-dir` stays as an alias — and `dest` stays
    `topic_dir`, because argparse takes it from the first long option and
    renaming the attribute would have been a rename of the code, not of the
    vocabulary."""
    from magi import retrieval

    parser = retrieval.build_parser()
    # Both subcommands: `retrieval` declares the flag twice, and a
    # reintroduction that removed the alias from only one of them slipped past
    # a version of this test that checked only `search`.
    for sub in ("search", "index"):
        for flag in ("--project-dir", "--topic-dir"):
            argv = [sub, "q", flag, "/tmp/x"] if sub == "search" else [sub, flag, "/tmp/x"]
            args = parser.parse_args(argv)
            assert args.topic_dir == "/tmp/x", f"{sub} {flag}"


def test_the_explainer_no_longer_disambiguates_one_word_from_itself():
    """Merging the vocabulary turned this modal into "**项目**（也叫项目）",
    and it was teaching `magi hub init`, which answers "unknown command"."""
    zh = _dictionary("zh")["scope_help_body"]

    assert "magi hub init" not in zh, "it still teaches a retired command"
    assert "也叫项目" not in zh, "it still disambiguates one word from itself"
    assert "registry.json" in zh, "what registering does is the part worth saying"
