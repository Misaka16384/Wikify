"""Keep the suite out of the developer's real config directory.

Fifteen test files already set `MAGI_CONFIG_HOME` themselves, one at a time,
which works right up until a test reaches code that writes there without
anyone noticing it would. `magi init` registering the new workspace is exactly
that: a scaffolding test suddenly starts appending temp directories to the
real `~/.config/magi/registry.json`, and nothing fails, so nobody finds out.

`magi.core.workspace.config_home()` reads the variable on every call, so
setting it per test is enough *for tests*. It was not enough for fixtures:
pytest builds higher-scoped fixtures before function-scoped ones, and three
module-scoped fixtures run `magi init` in a subprocess. They inherited the
real environment and registered pytest temp directories in the developer's own
`registry.json` — a full run moved it from 5 entries to 8, and those rows go
dangling as soon as pytest rotates its tmp root. So the session-scoped fixture
below redirects first, and checks afterwards that nothing wrote there anyway.

A test that wants its own value still sets one
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
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolate_config_home_for_the_session(tmp_path_factory):
    """Redirect before anything module-scoped runs, and prove it held.

    The per-test fixture below still gives each test its own directory. This
    one exists because module- and session-scoped fixtures are built first,
    and one of them running `magi init` writes to the real config directory.

    The check afterwards is the half that keeps it fixed: reading the real
    registry before redirecting and comparing at the end turns "somebody added
    a module-scoped fixture that shells out" into a failing suite rather than
    into a project list nobody can explain.
    """
    real = Path(os.path.expanduser(os.environ.get("XDG_CONFIG_HOME")
                                   or "~/.config")) / "magi" / "registry.json"
    before = real.read_bytes() if real.is_file() else None

    home = tmp_path_factory.mktemp("magi-config-home-session")
    previous = os.environ.get("MAGI_CONFIG_HOME")
    os.environ["MAGI_CONFIG_HOME"] = str(home)
    try:
        yield home
    finally:
        if previous is None:
            os.environ.pop("MAGI_CONFIG_HOME", None)
        else:
            os.environ["MAGI_CONFIG_HOME"] = previous

    after = real.read_bytes() if real.is_file() else None
    assert after == before, (
        f"the suite wrote to {real} — something ran outside the config-home "
        "isolation, most likely a module- or session-scoped fixture that "
        "shells out to `magi`")


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
