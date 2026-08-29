"""Parity lock between the CLI command catalogue and its Chinese sidecar."""

from __future__ import annotations

from magi.cli import _COMMANDS, _GROUP_HELP
from magi.core.cli_i18n import (
    COMMAND_HELP_ZH,
    GROUP_HELP_ZH,
    command_help_zh,
    group_help_zh,
)


def test_command_translations_mirror_catalogue_exactly():
    missing = set(_COMMANDS) - set(COMMAND_HELP_ZH)
    stale = set(COMMAND_HELP_ZH) - set(_COMMANDS)
    assert not missing, f"commands without a translation: {sorted(missing)}"
    assert not stale, f"translations for removed commands: {sorted(stale)}"
    for key, value in COMMAND_HELP_ZH.items():
        assert isinstance(value, str) and value.strip(), f"empty translation for {key}"


def test_group_translations_mirror_group_help_exactly():
    assert set(GROUP_HELP_ZH) == set(_GROUP_HELP)
    for group, value in GROUP_HELP_ZH.items():
        assert isinstance(value, str) and value.strip(), f"empty translation for {group}"


def test_graph_browse_is_in_catalogue():
    assert ("graph", "browse") in _COMMANDS
    assert ("graph", "browse") in COMMAND_HELP_ZH


def test_lookup_helpers_fall_back_to_empty_string():
    assert command_help_zh(("nope",)) == ""
    assert group_help_zh(None) == ""


def test_a_misspelled_command_gets_the_same_courtesy_as_a_misspelled_slug():
    """`magi review` suggests a slug when you get one wrong. Getting the
    command name wrong got "run --help" and a menu of seventy-six to scan."""
    import io
    from contextlib import redirect_stderr

    from magi import cli

    err = io.StringIO()
    with redirect_stderr(err):
        code = cli.main(["serach", "x"])

    said = err.getvalue()
    assert code != 0
    assert "Did you mean: search?" in said, said


def test_a_word_that_resembles_nothing_does_not_invent_a_suggestion():
    """A wrong guess is worse than none: it sends somebody to a command that
    does something else."""
    import io
    from contextlib import redirect_stderr

    from magi import cli

    err = io.StringIO()
    with redirect_stderr(err):
        cli.main(["zzzzqqqq"])

    assert "Did you mean" not in err.getvalue()


def test_init_points_at_the_command_that_does_the_whole_job():
    """`magi skills install` installs skills and asks which host. `magi install`
    does skills, the protocol block and all three hooks without prompting, and
    is the one `magi --help` lists. Sending a first-timer to the sibling is how
    somebody ends up with skills and no end-of-session gate."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1]
           / "src" / "magi" / "init_workspace.py").read_text(encoding="utf-8")
    line = [ln for ln in src.splitlines() if "Next: cd into it" in ln][0]

    assert "'magi install'" in line
    assert "skills install" not in line
