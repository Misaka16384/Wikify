"""Keep the suite out of the developer's real config directory.

Fifteen test files already set `MAGI_CONFIG_HOME` themselves, one at a time,
which works right up until a test reaches code that writes there without
anyone noticing it would. `magi init` registering the new workspace is exactly
that: a scaffolding test suddenly starts appending temp directories to the
real `~/.config/magi/registry.json`, and nothing fails, so nobody finds out.

`magi.core.workspace.config_home()` reads the variable on every call, so
setting it per test is enough. A test that wants its own value still sets one
— its own `monkeypatch.setenv` is set up after this fixture, so it is undone
before this one restores the environment.

This deliberately does **not** take `monkeypatch` as a parameter, tempting as
that is. Requesting it from an autouse fixture forces pytest to build
`monkeypatch` before every other function-scoped fixture in the suite, and
teardown is LIFO — so a test file with its own autouse fixture that expects
monkeypatch's undo to have already run gets it *after* instead.
`tests/test_perf_contracts.py` is one: its `clear_bd_cache` teardown called
`.cache_clear()` on whatever `pm.bd_available` currently was, and with the
ordering flipped that was still the test's own lambda.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def isolate_config_home(tmp_path_factory):
    home = tmp_path_factory.mktemp("magi-config-home")
    previous = os.environ.get("MAGI_CONFIG_HOME")
    os.environ["MAGI_CONFIG_HOME"] = str(home)
    try:
        yield home
    finally:
        if previous is None:
            os.environ.pop("MAGI_CONFIG_HOME", None)
        else:
            os.environ["MAGI_CONFIG_HOME"] = previous
