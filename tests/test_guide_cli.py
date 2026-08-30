"""`magi guide` — the manual as a queryable surface for humans and agents.

These lock the contract every reader of the manual depends on: stable chapter
anchors, a search that finds pasted error strings, and a symptom index whose
prescribed commands actually exist in the CLI.
"""

from __future__ import annotations

import json

import pytest

from magi.guide import (
    available_langs,
    find_chapter,
    load_guide,
    main,
    parse_chapters,
    search_guide,
    symptom_index,
)


def _chapters(lang):
    text, served = load_guide(lang)
    assert text, f"guide.{lang}.md must ship"
    assert served == lang
    return parse_chapters(text)


def test_both_languages_ship_and_agree_on_structure():
    assert set(available_langs()) >= {"zh", "en"}

    anchors = {}
    for lang in ("zh", "en"):
        chapters = _chapters(lang)
        assert len(chapters) >= 12
        a = [c["anchor"] for c in chapters]
        assert len(a) == len(set(a)), f"{lang}: duplicate chapter anchors"
        assert all(c["title"] for c in chapters)
        assert all(c["summary"] for c in chapters), f"{lang}: a chapter has no opening line"
        anchors[lang] = a

    # Anchors are the addressing scheme shared by the CLI, the WebUI and the
    # skill — a translation may not renumber or rename them.
    assert anchors["zh"] == anchors["en"]


def test_headings_inside_code_fences_are_not_chapters():
    # The radar chapter embeds a sample digest containing a literal "## title".
    chapters = _chapters("zh")
    titles = [c["title"] for c in chapters]
    assert not any(t.strip() in {"论文标题", "Paper title"} for t in titles)


def test_find_chapter_by_number_anchor_section_and_title():
    chapters = _chapters("zh")
    target = next(c for c in chapters if c["anchor"] == "graph")

    assert find_chapter(chapters, str(target["n"])) is target
    assert find_chapter(chapters, "graph") is target
    assert find_chapter(chapters, "GRAPH") is target
    assert find_chapter(chapters, target["title"][:3]) is target
    if target["sections"]:
        assert find_chapter(chapters, target["sections"][0]["anchor"]) is target
    assert find_chapter(chapters, "no-such-chapter") is None


@pytest.mark.parametrize("lang,needle", [
    # Real strings the CLI prints. When one is reworded the manual has to
    # follow it — this pair went stale the moment "no workspace found" became
    # "no project found", and the guide kept quoting the old one under a
    # green test.
    ("zh", "no project found"),
    ("en", "no project found"),
    ("zh", "mineru_api_token"),
])
def test_search_finds_real_error_strings_with_commands(lang, needle):
    from pathlib import Path as _Path

    source = "\n".join(
        f.read_text(encoding="utf-8", errors="replace")
        for f in (_Path(__file__).resolve().parents[1] / "src" / "magi").rglob("*.py"))
    assert needle in source, (
        f"{needle!r} is not a string this CLI prints any more — the manual is "
        f"being checked against an error that no longer exists")

    hits = search_guide(_chapters(lang), needle)
    assert hits, f"{lang}: manual should cover {needle!r}"
    top = hits[0]
    assert top["chapter_anchor"] and top["anchor"]
    assert top["matches"]
    assert any(h["commands"] for h in hits), "a fix should name a command to run"


def test_symptom_index_is_substantial_and_actionable():
    index = symptom_index(_chapters("zh"))
    assert len(index) >= 40
    assert all(e["symptom"] and e["fix"] for e in index)
    assert all(e["anchor"] for e in index)
    assert {e["source"] for e in index} == {"table", "callout"}
    # It must span the manual, not just the troubleshooting chapter.
    assert len({e["anchor"] for e in index}) >= 6
    assert sum(1 for e in index if e["commands"]) >= 20


def test_symptom_index_only_prescribes_real_commands():
    from magi.cli import _COMMANDS

    singles = {k[0] for k in _COMMANDS if len(k) == 1}
    groups: dict[str, set[str]] = {}
    for key in _COMMANDS:
        if len(key) == 2:
            groups.setdefault(key[0], set()).add(key[1])

    checked = 0
    for lang in ("zh", "en"):
        for entry in symptom_index(_chapters(lang)):
            for cmd in entry["commands"]:
                parts = cmd.split()
                if parts[0] != "magi" or len(parts) < 2:
                    continue
                head = parts[1]
                if head.startswith("-") or head.startswith("<"):
                    continue
                if head in groups:
                    sub = parts[2] if len(parts) > 2 else ""
                    assert sub in groups[head], f"{lang}: {cmd!r} names no real subcommand"
                else:
                    assert head in singles, f"{lang}: {cmd!r} names no real command"
                checked += 1
    assert checked >= 20


def test_cli_json_contracts(capsys):
    assert main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["lang"] in {"zh", "en"}
    assert len(data["chapters"]) >= 12
    assert all({"n", "anchor", "title", "summary", "sections"} <= set(c) for c in data["chapters"])

    assert main(["ingest", "--json"]) == 0
    chapter = json.loads(capsys.readouterr().out)
    assert chapter["anchor"] == "ingest"
    assert chapter["content"].lstrip().startswith("##")
    assert chapter["commands"]

    assert main(["--search", "mineru_api_token", "--json"]) == 0
    found = json.loads(capsys.readouterr().out)
    assert found["count"] >= 1
    assert found["hits"][0]["chapter_anchor"]

    # A miss is a clean exit 1 with an empty result, not a crash.
    assert main(["--search", "zzz-not-in-the-manual-zzz", "--json"]) == 1
    miss = json.loads(capsys.readouterr().out)
    assert miss["count"] == 0

    assert main(["--symptoms", "--json"]) == 0
    sym = json.loads(capsys.readouterr().out)
    assert sym["count"] >= 40

    assert main(["--symptoms", "--search", "ollama", "--json"]) == 0
    filtered = json.loads(capsys.readouterr().out)
    assert 0 < filtered["count"] <= sym["count"]

    assert main(["no-such-chapter", "--json"]) == 1
    err = json.loads(capsys.readouterr().out)
    assert "error" in err and err["chapters"]


def test_registered_in_the_dispatch_table():
    from magi.cli import _COMMANDS
    from magi.core.cli_i18n import command_help_zh

    assert ("guide",) in _COMMANDS
    assert _COMMANDS[("guide",)][0] == "magi.guide"
    assert command_help_zh(("guide",))
