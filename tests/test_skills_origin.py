"""Official skills are MAGI's to replace. Everything else is somebody's.

A person can train their own skill, and they can fork one of ours. The old
rule — "overwrite it if the text mentions magi" — could not tell those apart,
because a fork of an official skill necessarily still mentions magi. So every
install quietly ate their edits, which is the thing this project decided in
writing that it does not do.

The mark is the whole mechanism: the eight that ship carry `origin: magi`, and
install replaces a file that carries it and nothing else.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from magi import skills_cmd

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "magicfg"))
    return tmp_path


# --------------------------------------------------------------------------
# the mark
# --------------------------------------------------------------------------

@pytest.mark.parametrize("skill", sorted(
    p.name for p in (ROOT / "src" / "magi" / "skills").iterdir() if p.is_dir()))
def test_every_official_skill_says_so(skill):
    text = (ROOT / "src" / "magi" / "skills" / skill / "SKILL.md").read_text(
        encoding="utf-8")
    assert skills_cmd.ORIGIN_MARK in text


def test_a_forked_skill_is_not_overwritten(tmp_path):
    """The case the old heuristic got wrong: a fork of ours still says "magi"
    everywhere, so "does the text mention magi" replaced exactly the file it
    should have left alone."""
    path = tmp_path / "SKILL.md"
    path.write_text("---\nname: magi\ndescription: my own version\n---\n\n"
                    "Run `magi next` my way.\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    assert skills_cmd._write(path, "official text\n", force=False) == "skipped"
    assert path.read_text(encoding="utf-8") == before


def test_installing_twice_over_a_fork_changes_nothing(tmp_path):
    path = tmp_path / "SKILL.md"
    mine = "---\nname: magi\n---\n\nmagi, but mine.\n"
    path.write_text(mine, encoding="utf-8")

    for _ in range(2):
        skills_cmd._write(path, "official text\n", force=False)

    assert path.read_text(encoding="utf-8") == mine


def test_a_file_magi_wrote_is_updated(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text(f"---\nname: magi\n{skills_cmd.ORIGIN_MARK}\n---\n\nold\n",
                    encoding="utf-8")

    assert skills_cmd._write(path, "new text\n", force=False) == "updated"
    assert path.read_text(encoding="utf-8") == "new text\n"


def test_force_is_still_force(tmp_path):
    """Somebody who says `--force` has been told what it does."""
    path = tmp_path / "SKILL.md"
    path.write_text("mine\n", encoding="utf-8")

    assert skills_cmd._write(path, "theirs\n", force=True) == "updated"


# --------------------------------------------------------------------------
# the second source
# --------------------------------------------------------------------------

def test_a_skill_somebody_made_is_installed_too(home):
    """User-level, beside `registry.json`: a skill somebody trained is about
    how *they* work, not about one library."""
    mine = skills_cmd.user_skills_dir() / "sweep"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text('---\nname: sweep\ndescription: "My sweep."\n'
                                   '---\n\nDo it my way.\n', encoding="utf-8")

    names = {skill.name for skill in skills_cmd.load_skills()}
    assert "sweep" in names
    assert "magi" in names, "and the packaged ones are still there"


def test_a_name_in_both_places_is_the_persons(home):
    """They went and wrote one. The packaged copy losing is the whole point of
    the directory existing."""
    mine = skills_cmd.user_skills_dir() / "magi"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text('---\nname: magi\ndescription: "Mine."\n---\n\n'
                                   'My entry point.\n', encoding="utf-8")

    found = {skill.name: skill for skill in skills_cmd.load_skills()}
    assert found["magi"].description == "Mine."
    assert not found["magi"].official


def test_no_such_directory_is_not_an_error(home):
    assert not skills_cmd.user_skills_dir().exists()
    assert len(skills_cmd.load_skills()) == 8


# --------------------------------------------------------------------------
# one word list facing the person
#
# Three tables in this codebase list hosts, and they answer three different
# questions — where a skill installs, what binary to run headless, whose
# record we can read. The names diverged for a real reason. But only one of
# them is typed by a person, and they should not have to know that one vendor
# is called two things depending on which command they are running.
# --------------------------------------------------------------------------

def test_the_word_a_person_types_is_gemini():
    from magi import review
    from magi.reflect import transcripts

    assert "gemini" in review.HOSTS
    assert "gemini" in transcripts.HOSTS
    assert skills_cmd.resolve_host("gemini") in skills_cmd.HOSTS


def test_the_product_name_still_works():
    """Somebody who learned `antigravity` does not get an error for it."""
    assert skills_cmd.resolve_host("antigravity") == "antigravity"
    assert skills_cmd._resolve_hosts(["antigravity"])[0].key == "antigravity"


def test_both_spellings_reach_the_same_host():
    assert (skills_cmd._resolve_hosts(["gemini"])[0].key
            == skills_cmd._resolve_hosts(["antigravity"])[0].key)


def test_the_label_still_names_the_product():
    """The alias is about what a person types, not about renaming the tool."""
    host = skills_cmd._resolve_hosts(["gemini"])[0]
    assert "Antigravity" in host.label and host.binary == "agy"


def test_an_unknown_host_lists_both_spellings():
    import pytest as pytest_mod

    with pytest_mod.raises(SystemExit) as caught:
        skills_cmd._resolve_hosts(["nope"])
    said = str(caught.value)
    assert "gemini" in said and "antigravity" in said
