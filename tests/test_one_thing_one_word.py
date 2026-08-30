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
GUIDES = {
    "zh": ROOT / "src" / "magi" / "docs" / "guide.zh.md",
    "en": ROOT / "src" / "magi" / "docs" / "guide.en.md",
}

#: The dashboard's RETIRED list above is what a dropdown menu needed. Prose
#: reaches for more synonyms than a menu ever did: the guides also used
#: "library" and "knowledge base" as a fourth and fifth English gloss, 主题
#: (the direct translation of "topic") throughout the Chinese guide, and bare
#: 库 ("library"/"store", the noun the compounds above are built from) on its
#: own wherever a sentence just said "this library" or "67 libraries" instead
#: of naming one of the compounds. None of that reaches the screen, but a
#: reader of the manual meets it exactly the way a reader of the dashboard
#: used to meet 工作区 and 知识库.
GUIDE_RETIRED = re.compile(
    r"工作区|工作空间|知识库|本库|课题|主题|库"
    r"|\bworkspace\b|\btopic\b|\btopics\b|knowledge.base|\blibrar(?:y|ies)\b",
    re.IGNORECASE)

#: Each of these is a different word that happens to be spelled the same, or a
#: literal quote of something the CLI actually prints — checked the same way
#: ALLOWED is above: if the line carries one of these, the retired-looking
#: word next to it is not our word. Named per concept, with the reason, so
#: that adding one is a decision and not a regex accident.
GUIDE_ALLOWED = re.compile(
    r"topics[/\\]"                                    # wiki/topics/, and v1 hub's own topics/ — real directories, not "research subject"
    r"|topic pages|主题页"                              # what lives in wiki/topics/ — synthesis writeups, not projects
    r"|--topic-dir|--project-dir"                      # the accepted flag alias and its current spelling
    r"|magi kb\b|--library\b"                          # real command and real flag names
    r"|任务库|建库|task.store|task.database"            # the Beads task DB, not a project
    r"|仓库|\brepo\b|clone"                             # a git repository, not a project
    r"|模式库|pattern library"                          # output/reflect/patterns/, a different library entirely
    r"|--kb-only|--full\b|纯知识库|knowledge-base-only"  # the flag's own name for a feature mode, not the directory
    r"|战术主题|tactical theme"                          # the WebUI's colour scheme, not a research subject
    r"|主题分区|topic clusters"                          # a thematic cluster in the graph view, not a project
    r"|category.{0,30}(?:concept|topic|reference)"      # the `category:` frontmatter's real enum value
    r"|~/Library|Library/LaunchAgents"                  # macOS's own folder convention
    r"|my-topic|quantum-toys"                           # an arbitrary example directory name, not a claim about vocabulary
    r"|\{#workspace[a-z-]*\}"                           # an anchor; external links point at it, so it never changes
)

#: Text the guides quote because the CLI prints it. Kept apart from
#: `GUIDE_ALLOWED` because the two are excused for different reasons and only
#: this one can go stale: a quote stops being legitimate the moment the code
#: stops emitting it, and an exemption that outlives the string it protects is
#: a standing pass for a false quote. `test_no_exemption_excuses_text_the_cli_
#: never_prints` walks this tuple against the source.
QUOTED_OUTPUT = (
    "no workspace here and no searchable",
    "Migrating workspace",
    "what the library itself needs",
    "start building the library",
)

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


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_the_guides_use_one_word(lang):
    """The two long-form guides (`guide.zh.md`, `guide.en.md`) are prose, not
    a dropdown menu, so they reached for synonyms the dashboard never showed:
    "library" and "knowledge base" in English, 主题 and bare 库 in Chinese.
    Checked per line rather than per dictionary entry — a guide has no keys —
    but the principle is the same one `test_the_screen_uses_one_word` uses:
    a line that names one of the excused concepts is not making the mistake
    this test exists to catch."""
    offenders = []
    for number, line in enumerate(
            GUIDES[lang].read_text(encoding="utf-8").splitlines(), 1):
        # Cut the excused spans out and look at what is left, rather than
        # skipping any line that contains one. Skipping the line let
        # `magi kb disable <name>  # leave one workspace out` through: the
        # command name is excused, so the sentence beside it was never read.
        rest = GUIDE_ALLOWED.sub(" ", line)
        for phrase in QUOTED_OUTPUT:
            rest = rest.replace(phrase, " ")
        if GUIDE_RETIRED.search(rest):
            offenders.append((number, line.strip()[:120]))

    assert not offenders, (
        f"guide.{lang}.md still calls a project something else: {offenders}")
