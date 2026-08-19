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
