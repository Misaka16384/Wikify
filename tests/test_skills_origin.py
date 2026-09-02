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
    """With no user directory, what loads is exactly what ships — counted from
    the package rather than written down here, so adding a skill does not mean
    editing a number in a test that was never about the number."""
    assert not skills_cmd.user_skills_dir().exists()
    packaged = list(skills_cmd.skills_dir().glob("*/SKILL.md"))
    assert len(skills_cmd.load_skills()) == len(packaged)


# --------------------------------------------------------------------------
# one word list facing the person
#
# There used to be three tables listing hosts — where a skill installs, what
# binary to run headless, whose record we can read — and the names diverged
# because each was edited on its own. There is one table now, so the question
# is no longer "do they agree" but "does the one word a person types still
# reach the record", including the spelling of a product that has since been
# renamed.
# --------------------------------------------------------------------------

def test_one_table_answers_all_three_questions():
    from magi import review
    from magi.core import hosts
    from magi.reflect import transcripts

    entry = hosts.catalog()[skills_cmd.resolve_host("gemini")]
    assert entry.key == "antigravity"
    assert entry.drops, "a record has to say where its skills go"
    assert entry.headless("q")[0] == "agy"
    assert entry.reader in transcripts.ADAPTERS
    assert entry.key in review.host_names()


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
    assert "Antigravity" in host.label and host.command == "agy"


def test_an_unknown_host_lists_both_spellings():
    import pytest as pytest_mod

    with pytest_mod.raises(SystemExit) as caught:
        skills_cmd._resolve_hosts(["nope"])
    said = str(caught.value)
    assert "gemini" in said and "antigravity" in said


# --------------------------------------------------------------------------
# removing asks the same question as writing
# --------------------------------------------------------------------------

def _claude():
    return skills_cmd.catalog(None)["claude"]


def _install_into(dest: Path) -> None:
    target = next(t for t in _claude().drops if t.kind == "skill")
    for sk in skills_cmd.load_skills():
        path, text = skills_cmd.files_for(sk, target, dest)[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _plant_a_persons_own(dest: Path, name: str) -> Path:
    """A skill they wrote, under a name we also ship. No mark: not ours."""
    d = dest / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: %s\ndescription: mine\n---\n\n# my own\n" % name,
        encoding="utf-8")
    (d / "REFERENCE.md").write_text("my reference material\n", encoding="utf-8")
    return d


def test_uninstall_leaves_a_skill_the_person_wrote(home, tmp_path):
    """`_ours` was written for exactly this and nothing called it.

    Its own docstring describes the bug — "somebody's own
    `~/.claude/skills/research/` — their prompt, their reference files — went
    with one `magi skills uninstall`" — so the guard existed at a layer that
    could not be wrong while the one call site that could was never wired.
    Reproduced against a real install before this test was written: 9 removed,
    including the person's directory and the reference file inside it.
    """
    dest = tmp_path / ".claude" / "skills"
    _install_into(dest)
    mine = _plant_a_persons_own(dest, "research")

    result = skills_cmd.uninstall_host(_claude(), skills_cmd.load_skills(),
                                       "project", dry_run=False,
                                       override_dir=dest)

    assert mine.is_dir(), "the person's skill was deleted"
    assert (mine / "REFERENCE.md").is_file(), "their reference file went too"
    assert str(mine) in result["kept"]
    assert str(mine) not in result["removed"]


def test_uninstall_still_removes_what_magi_wrote(home, tmp_path):
    dest = tmp_path / ".claude" / "skills"
    _install_into(dest)

    result = skills_cmd.uninstall_host(_claude(), skills_cmd.load_skills(),
                                       "project", dry_run=False,
                                       override_dir=dest)

    assert result["removed"], "nothing was removed at all"
    assert not (dest / "adopt").exists()
    assert result["kept"] == []


def test_what_was_kept_is_said_out_loud(home, tmp_path, capsys):
    """An uninstall that leaves a file behind and says nothing reads as a bug,
    and the person never learns why it is still there."""
    dest = tmp_path / ".claude" / "skills"
    _install_into(dest)
    _plant_a_persons_own(dest, "research")

    skills_cmd.main(["uninstall", "--host", "claude", "--dir", str(dest)])

    out = capsys.readouterr().out
    assert "kept" in out and "research" in out
