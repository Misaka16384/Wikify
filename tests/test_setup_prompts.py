"""Ctrl+C at a setup prompt means stop, not yes.

`_ask_yes_no` caught `KeyboardInterrupt` next to `EOFError` and returned the
default for both. Every question it asks defaults to True — "Turn on X?", "Do
you want X?" — so interrupting the setup answered yes to whatever was on
screen and carried on to the next one.

`EOFError` keeps the old behaviour on purpose: no terminal means take the
default, which is what a default is for.
"""

from __future__ import annotations

import builtins

import pytest

from magi import setup_cmd


def test_ctrl_c_aborts_instead_of_agreeing(monkeypatch):
    def interrupted(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr(builtins, "input", interrupted)

    with pytest.raises(SystemExit) as caught:
        setup_cmd._ask_yes_no("Turn on something expensive?", default=True)
    assert caught.value.code == 130


def test_no_terminal_still_takes_the_default(monkeypatch):
    def piped(prompt=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", piped)

    assert setup_cmd._ask_yes_no("Turn it on?", default=True) is True
    assert setup_cmd._ask_yes_no("Turn it on?", default=False) is False


@pytest.mark.parametrize("typed,default,expected", [
    ("y", False, True), ("yes", False, True), ("n", True, False),
    ("", True, True), ("", False, False), ("nonsense", True, False),
])
def test_what_a_person_types_still_decides(monkeypatch, typed, default, expected):
    monkeypatch.setattr(builtins, "input", lambda prompt="": typed)
    assert setup_cmd._ask_yes_no("?", default=default) is expected
