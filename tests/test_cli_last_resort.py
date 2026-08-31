"""What a user sees when a command fails in a way nobody anticipated.

`cli.main` caught `ImportError`, `SystemExit` and `KeyboardInterrupt`. Anything
else reached the interpreter as a traceback — including under `--json`, where
the caller is a program that will choke on it. A corrupt `output/index.db`
produced exactly that: `sqlite3.DatabaseError` with a stack, out of
`magi search --json`.

Meanwhile `ui/api.py` wraps the identical operations in `except Exception`
twenty-two times, so the WebUI answered the same failure cleanly. Two surfaces
of one program, and the one people type into was the worse of the two.

The traceback is not discarded — it goes to the trace channel, so `--verbose`
still gives a developer everything.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

from magi import cli
from magi.core import trace


@pytest.fixture
def exploding(monkeypatch):
    """A registered command whose `main` raises something unexpected."""
    module = types.ModuleType("magi._exploding")

    def main(argv):
        raise RuntimeError("the roof fell in")

    module.main = main
    monkeypatch.setitem(sys.modules, "magi._exploding", module)
    monkeypatch.setitem(cli._COMMANDS, ("kaboom",),
                        ("magi._exploding", [], "explode on purpose"))
    return module


def test_an_unexpected_failure_is_one_line_not_a_stack(exploding, capsys):
    code = cli.main(["kaboom"])
    captured = capsys.readouterr()

    assert code == 1
    assert "Traceback" not in captured.err
    assert "RuntimeError: the roof fell in" in captured.err
    assert "--verbose" in captured.err, "a person needs to be told where the rest is"


def test_json_stays_json_when_the_answer_is_that_it_broke(exploding, capsys):
    """The contract `--json` makes is with a program, and a program cannot
    read a traceback."""
    code = cli.main(["kaboom", "--json"])
    captured = capsys.readouterr()

    assert code == 1
    payload = json.loads(captured.out)
    assert "RuntimeError" in payload["error"]


def test_the_traceback_survives_on_the_trace_channel(exploding, capsys, monkeypatch):
    """Nothing is hidden — it moves. A developer asks and gets all of it."""
    monkeypatch.setattr(trace, "_ON", True)

    cli.main(["kaboom"])
    captured = capsys.readouterr()

    assert "Traceback" in captured.err
    assert "the roof fell in" in captured.err


def test_the_three_it_already_handled_still_behave(exploding, monkeypatch):
    """A bottom handler that swallowed `SystemExit` would turn every clean
    refusal into an unexpected failure — `kb/thread_cmd.Refused` is a
    `SystemExit` on purpose, relying on the branch above."""

    def refusing(argv):
        raise SystemExit("refused for a stated reason")

    monkeypatch.setattr(sys.modules["magi._exploding"], "main", refusing)
    assert cli.main(["kaboom"]) == 1

    def interrupted(argv):
        raise KeyboardInterrupt

    monkeypatch.setattr(sys.modules["magi._exploding"], "main", interrupted)
    assert cli.main(["kaboom"]) == 130


def test_verbose_is_accepted_by_every_command_not_just_some(exploding, monkeypatch):
    """Consumed at the entry rather than declared by forty subparsers: the
    commands that most need tracing are the ones that spawn other commands,
    and a flag only some of them accept is a flag nobody reaches for."""
    monkeypatch.setattr(trace, "_ON", False)
    seen = {}

    def record(argv):
        seen["argv"] = argv
        return 0

    monkeypatch.setattr(sys.modules["magi._exploding"], "main", record)

    assert cli.main(["kaboom", "--verbose", "x"]) == 0
    assert seen["argv"] == ["x"], "the flag reached the subcommand's parser"
    assert trace.enabled()
