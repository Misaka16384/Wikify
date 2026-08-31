"""What the program did, when somebody needs to know.

There were 869 `print()` calls in this package and no logging of any kind, so
"why did that fail" had exactly one answer: run it again by hand with prints
added. That is fine for a bug you can reproduce in one command. It is useless
for the shape of failure this system actually has — a step inside a step,
where `magi sync --fix` runs three subcommands, two fail, and the report is
the last two lines of each.

This is deliberately not a logging framework. Nothing here changes what a
command prints; `print()` stays the way a command talks to a person, because
that output is a designed part of the interface and routing it through log
levels would make it worse. What this adds is a second channel that is silent
by default and says everything when asked:

    magi sync --fix --verbose        # or MAGI_DEBUG=1 magi sync --fix

On that channel go the things a person cannot see and a developer always
wants: which subprocess was spawned with which argv, how long it took, what
it exited with, and — the part that was missing entirely — the whole of what
it printed, rather than the tail somebody once decided was enough.
"""

from __future__ import annotations

import os
import sys
import time

#: Set by the CLI when `--verbose`/`-v` is present. Also read from the
#: environment, so it can be turned on for a whole session or for a subprocess
#: chain without editing every call site — which is exactly the case that
#: needs it, since the interesting failures are two processes down.
_ON = os.environ.get("MAGI_DEBUG", "").strip() not in ("", "0", "false", "no")

#: Passed to children so a chain traces end to end. A child that is spawned
#: without this stays quiet, which is what makes `--verbose` on the outermost
#: command still answer for the innermost one.
ENV_VAR = "MAGI_DEBUG"


def enabled() -> bool:
    return _ON


def enable() -> None:
    """Turn tracing on for this process and for anything it spawns."""
    global _ON
    _ON = True
    os.environ[ENV_VAR] = "1"


def consume_flag(argv: list) -> list:
    """Strip `--verbose`/`-v` from *argv*, turning tracing on if present.

    Handled here rather than in each of forty subcommand parsers: a flag that
    only some commands accept is a flag nobody remembers, and the commands
    that most need it are the ones that spawn other commands.

    Stripped wherever it appears, deliberately. The case that worries a reader
    — `--text --verbose`, somebody posting the word — argparse already refuses
    on its own, because it reads the second token as an option and reports a
    missing argument. The form that does work, `--text=--verbose`, is a single
    token and is not touched here. A cleverer filter that tried to tell a
    flag's value from a flag broke `magi sync --fix --verbose`, which is what
    people actually type.
    """
    kept = [a for a in argv if a not in ("--verbose", "-v")]
    if len(kept) != len(argv):
        enable()
    return kept


def say(message: str) -> None:
    """One line on the trace channel. Silent unless tracing is on."""
    if _ON:
        print(f"[magi] {message}", file=sys.stderr)


def step(label: str):
    """Context manager timing one step and reporting how it ended.

        with trace.step("graph build"):
            ...
    """

    class _Step:
        def __enter__(self):
            self.started = time.monotonic()
            say(f"-> {label}")
            return self

        def __exit__(self, exc_type, exc, tb):
            took = time.monotonic() - self.started
            if exc is None:
                say(f"<- {label} ok ({took:.2f}s)")
            else:
                say(f"<- {label} raised {exc_type.__name__}: {exc} ({took:.2f}s)")
            return False

    return _Step()


def ran(argv, proc, seconds: float) -> None:
    """Report a finished subprocess, in full.

    The whole of stdout and stderr, not a tail. `magi sync --fix` printing the
    last two lines of a failed step is how a `pm init` that declined itself
    became "ran 3 step(s), 2 failed" with no reason attached anywhere.
    """
    if not _ON:
        return
    shown = " ".join(str(a) for a in argv)
    say(f"$ {shown}")
    say(f"  exit {proc.returncode} in {seconds:.2f}s")
    for stream, text in (("out", proc.stdout), ("err", proc.stderr)):
        for line in (text or "").splitlines():
            say(f"  {stream}| {line}")


def run(argv, **kwargs):
    """`subprocess.run` that traces itself, for spawning our own CLI.

    Defaults chosen for the one thing this codebase spawns — itself:

    * `input=""` rather than `stdin=DEVNULL`. Capturing a child's output takes
      away its ability to ask, so it must not be left believing someone can
      answer. DEVNULL is not enough on Windows: it opens `NUL`, a character
      device, and `isatty()` answers True for it.
    * text mode with `errors="replace"`, because a converted paper can carry
      anything.
    """
    import subprocess

    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    if "stdin" not in kwargs and "input" not in kwargs:
        kwargs["input"] = ""

    started = time.monotonic()
    proc = subprocess.run(argv, **kwargs)
    ran(argv, proc, time.monotonic() - started)
    return proc
