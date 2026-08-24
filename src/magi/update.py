"""magi update — is there a newer release, and how does this install take it?

Two things here that look like details and are not.

**Ask the index the upgrade will actually read.** ``pypi.org/pypi/<pkg>/json``
publishes a new version within seconds; ``pypi.org/simple/<pkg>/``, which is
what every resolver consults, lags it by minutes. Checking the fast one means
telling somebody a version is available and then watching ``pipx upgrade``
answer "already at latest version" — correctly, because as far as the index is
concerned it is. A notice you cannot act on is worse than no notice: it teaches
people to ignore the notices. So this reads the simple index, and what it says
is available really is installable.

**How MAGI was installed decides how it upgrades, and guessing wrong is
destructive.** ``pipx install --force`` over an existing install prints
``Installing to existing venv``, exits 1, and **leaves the old version in
place** — a failure whose message reads like success. A source checkout must
not be touched by a package manager at all. So the install method is detected
and the wrong command is never run; when it cannot be detected, the command is
printed for a person to run rather than guessed at.

The startup notice is deliberately one release behind the network: the check
runs in a background thread and writes a cache, and the *next* invocation reads
that cache. Nothing about starting `magi` ever waits on PyPI.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from magi import __version__

PACKAGE = "magi-research"
SIMPLE_INDEX = f"https://pypi.org/simple/{PACKAGE}/"

#: How long a cached answer stays fresh. A day: new releases are not urgent,
#: and a check per invocation would be a request per shell command.
CACHE_TTL_S = 24 * 60 * 60

#: The background fetch gets this long. It is not on anyone's critical path —
#: if it does not finish, the cache stays stale and the next run tries again.
FETCH_TIMEOUT_S = 6

_VERSION_IN_FILENAME = re.compile(
    rf"{re.escape(PACKAGE.replace('-', '_'))}-(\d+(?:\.\d+)*)"
    r"(?:-py3-none-any\.whl|\.tar\.gz)")


# --------------------------------------------------------------------------
# versions
# --------------------------------------------------------------------------

def parse_version(text: str) -> tuple[int, ...] | None:
    """``"1.13.0"`` -> ``(1, 13, 0)``. Anything else -> None.

    Deliberately refuses anything that is not purely numeric dotted segments,
    which means pre-releases (``1.14.0rc1``) are ignored rather than offered.
    Nobody should be nudged onto a release candidate by a background check.
    """
    if not re.fullmatch(r"\d+(?:\.\d+)*", text or ""):
        return None
    return tuple(int(p) for p in text.split("."))


def is_newer(candidate: str, current: str) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    if a is None or b is None:
        return False
    # Compare on equal length so 1.13 and 1.13.0 are the same version.
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def fetch_latest(timeout: int = FETCH_TIMEOUT_S) -> str | None:
    """The newest version the *simple index* is serving, or None.

    None means "could not look", which is not the same as "nothing newer" and
    is never reported as such — the caller stays silent instead.
    """
    from magi.core.http import http_text

    try:
        body = http_text(SIMPLE_INDEX, timeout=timeout)
    except Exception:  # noqa: BLE001 — an update check must never be an error
        return None

    best: tuple[int, ...] | None = None
    best_text = None
    for match in _VERSION_IN_FILENAME.finditer(body):
        parsed = parse_version(match.group(1))
        if parsed is not None and (best is None or parsed > best):
            best, best_text = parsed, match.group(1)
    return best_text


# --------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------

def cache_path() -> Path:
    from magi.core.workspace import config_home

    return config_home() / "update-check.json"


def read_cache() -> dict:
    try:
        data = json.loads(cache_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 — derived data; a bad cache is no cache
        return {}


def write_cache(latest: str | None) -> None:
    from magi.core.wiki_common import atomic_write

    try:
        atomic_write(cache_path(), json.dumps(
            {"checked_at": time.time(), "latest": latest,
             "checked_from": __version__}, indent=2) + "\n")
    except Exception:  # noqa: BLE001
        pass


def cache_is_fresh(cache: dict | None = None) -> bool:
    data = read_cache() if cache is None else cache
    at = data.get("checked_at")
    return isinstance(at, (int, float)) and (time.time() - at) < CACHE_TTL_S


# --------------------------------------------------------------------------
# how this copy was installed
# --------------------------------------------------------------------------

class Install:
    """Where this `magi` lives and what upgrades it."""

    def __init__(self, kind: str, command: list[str] | None, note: str = ""):
        self.kind = kind            # pipx | uv | pip | source | unknown
        self.command = command      # None when nothing may be run automatically
        self.note = note

    def __repr__(self) -> str:      # pragma: no cover — debugging aid
        return f"Install({self.kind!r}, {self.command!r})"


def detect_install(prefix: str | None = None, package_file: str | None = None,
                   base_prefix: str | None = None) -> Install:
    """Work out which tool owns this install. Arguments exist for testing.

    The order matters: a uv tool venv and a pipx venv are both "a venv", so the
    path they sit in is the only thing that tells them apart, and that check has
    to come before the generic pip fallback.

    All three inputs are parameters, including ``base_prefix``. An earlier
    version took ``prefix`` for testing and then compared the *real*
    ``sys.prefix`` against the real ``sys.base_prefix`` for the venv case — so
    the injected value was ignored by exactly one branch, and that branch's
    answer depended on whether the test runner happened to be inside a venv.
    It passed locally and failed in CI, which is the only reason it was noticed.
    A seam that is only half a seam is worse than none: it looks tested.
    """
    prefix = (prefix or sys.prefix).replace("\\", "/")
    base = (base_prefix or getattr(sys, "base_prefix", sys.prefix)).replace("\\", "/")
    pkg = (package_file or __file__).replace("\\", "/")
    low = prefix.lower()

    # A checkout, editable or not: the package is not inside the environment it
    # is imported from. Never hand this to a package manager.
    if "/src/magi/" in pkg and "/site-packages/" not in pkg:
        return Install("source", None,
                       "this is a source checkout — `git pull` in "
                       f"{pkg.split('/src/magi/')[0]}")

    if "/pipx/venvs/" in low or "pipx" in low.split("/"):
        # NOT `pipx install --force`: over an existing install it prints
        # "Installing to existing venv", exits 1, and leaves the old version
        # in place. Reproduced on v1.12.0 and again in an isolated PIPX_HOME.
        return Install("pipx", ["pipx", "upgrade", PACKAGE])

    if "/uv/tools/" in low or "/uv/tool/" in low:
        return Install("uv", ["uv", "tool", "install", "--force", "--refresh",
                              PACKAGE])

    if prefix != base:
        return Install("pip", [sys.executable, "-m", "pip", "install",
                               "--upgrade", PACKAGE],
                       "installed into a virtual environment")

    return Install("unknown", None,
                   "could not tell how this was installed; upgrade with the "
                   "tool you used (pipx / uv / pip)")


# --------------------------------------------------------------------------
# the startup notice
# --------------------------------------------------------------------------

def notice_enabled() -> bool:
    """Off for anything that is not a person reading a terminal.

    `MAGI_NO_UPDATE_CHECK` covers scripts and CI without asking anyone to write
    a settings file, and `NO_COLOR`-style env opt-outs are what people already
    expect to reach for.
    """
    if os.environ.get("MAGI_NO_UPDATE_CHECK"):
        return False
    if os.environ.get("CI"):
        return False
    try:
        from magi.kb_registry import load_settings

        if load_settings().get("update_check") is False:
            return False
    except Exception:  # noqa: BLE001 — never let settings break a command
        pass
    return True


def pending_notice() -> str:
    """One line, from the cache only. Never touches the network.

    Reading a cache the *previous* run filled is the whole design: no
    invocation of `magi` ever waits on pypi.org, and the worst case is being
    told about a release a day late.
    """
    latest = read_cache().get("latest")
    if not isinstance(latest, str) or not is_newer(latest, __version__):
        return ""
    how = detect_install()
    action = ("magi update" if how.command
              else (how.note or "upgrade with your package manager"))
    return f"magi {latest} is available (you have {__version__}) — {action}"


def refresh_in_background() -> None:
    """Fetch and cache, on a daemon thread, if the cache has gone stale.

    Daemon so it can never hold the process open, and every failure is
    swallowed: an update check that delays or breaks a command has cost more
    than it could ever save.
    """
    if not notice_enabled() or cache_is_fresh():
        return
    import threading

    def run() -> None:
        try:
            write_cache(fetch_latest())
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=run, daemon=True).start()


# --------------------------------------------------------------------------
# upgrading from inside the dashboard
#
# The WebUI cannot run the upgrade itself, and the reason is not caution: on
# Windows a live `magi ui` holds its own venv's `python.exe` and every loaded
# `.pyd` open, so pipx or uv cannot replace them. The upgrade fails partway and
# leaves a half-written install — and it fails in front of somebody whose page
# has just gone blank, because the server they were reading it in is the thing
# being replaced.
#
# So the server does not upgrade. It starts a detached helper that waits for
# the server to exit, upgrades, relaunches the dashboard on the same port, and
# writes down what happened. The page comes back by itself and says so.
# --------------------------------------------------------------------------

def result_path() -> Path:
    from magi.core.workspace import config_home

    return config_home() / "update-result.json"


def _write_result(**fields) -> None:
    from magi.core.wiki_common import atomic_write

    try:
        atomic_write(result_path(),
                     json.dumps({"at": time.time(), **fields}, indent=2,
                                ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def read_result() -> dict:
    try:
        data = json.loads(result_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def clear_result() -> None:
    try:
        result_path().unlink()
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def spawn_detached_upgrade(*, wait_pid: int, relaunch: list[str] | None) -> bool:
    """Start the helper that will upgrade once ``wait_pid`` has exited.

    Detached in the strong sense: its own process group / session, no inherited
    console on Windows, and stdio pointed at the null device. It has to outlive
    the process that started it, because that process is what it is waiting for.
    """
    import subprocess

    argv = [sys.executable, "-m", "magi", "update", "--_run-detached",
            "--_wait-pid", str(wait_pid)]
    if relaunch:
        argv += ["--_relaunch", json.dumps(relaunch)]

    kwargs: dict = {"stdin": subprocess.DEVNULL,
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        # DETACHED_PROCESS so it does not die with the console, and
        # CREATE_NEW_PROCESS_GROUP so a Ctrl-C in the old shell cannot reach it.
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        kwargs["start_new_session"] = True

    try:
        subprocess.Popen(argv, **kwargs)
        return True
    except Exception:  # noqa: BLE001
        return False


def _run_detached(wait_pid: int, relaunch: list[str] | None) -> int:
    """The helper. Runs with nobody watching, so everything it learns is written
    down — this file is the only way the outcome ever reaches a person."""
    import subprocess

    _write_result(state="waiting", pid=wait_pid, installed=__version__)

    # The dashboard is shutting itself down. Give it long enough to release its
    # files, and give up rather than upgrading underneath a process that is
    # still running — that is the exact failure this whole path exists to avoid.
    deadline = time.time() + 60
    while _pid_alive(wait_pid) and time.time() < deadline:
        time.sleep(0.5)
    if _pid_alive(wait_pid):
        _write_result(state="failed", installed=__version__,
                      error=f"the dashboard (pid {wait_pid}) was still running "
                            "after 60s; nothing was upgraded")
        return 1

    # Windows releases handles asynchronously after the process object goes.
    time.sleep(1.5)

    how = detect_install()
    if how.command is None:
        _write_result(state="failed", installed=__version__,
                      error=how.note or "no upgrade command for this install")
        return 1

    _write_result(state="running", installed=__version__,
                  command=" ".join(how.command))
    try:
        proc = subprocess.run(how.command, capture_output=True, text=True)
    except Exception as exc:  # noqa: BLE001
        _write_result(state="failed", installed=__version__,
                      command=" ".join(how.command), error=str(exc))
        return 1

    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        _write_result(state="failed", installed=__version__,
                      command=" ".join(how.command),
                      error=f"exit {proc.returncode}", output=output[-4000:])
        return proc.returncode

    # What is on disk now, not what was asked for. `pipx install --force` is
    # documented to print "Installing to existing venv" and leave the old
    # version behind, so a command that exits 0 is not proof of anything.
    now = _installed_version_on_disk()
    _write_result(state="done", installed=__version__, now=now,
                  changed=bool(now and now != __version__),
                  command=" ".join(how.command), output=output[-4000:])

    if relaunch:
        try:
            kwargs: dict = {"stdin": subprocess.DEVNULL,
                            "stdout": subprocess.DEVNULL,
                            "stderr": subprocess.DEVNULL}
            if os.name == "nt":
                kwargs["creationflags"] = 0x00000008 | 0x00000200
            else:
                kwargs["start_new_session"] = True
            subprocess.Popen(relaunch, **kwargs)
        except Exception as exc:  # noqa: BLE001
            _write_result(state="done", installed=__version__, now=now,
                          changed=bool(now and now != __version__),
                          command=" ".join(how.command),
                          relaunch_error=str(exc))
    return 0


def _installed_version_on_disk() -> str | None:
    """Ask the upgraded package, in a fresh interpreter.

    This process imported `magi` before the upgrade, so its `__version__` is
    the old one no matter what happened on disk.
    """
    import subprocess

    try:
        proc = subprocess.run(
            [sys.executable, "-c",
             "import magi, sys; sys.stdout.write(magi.__version__)"],
            capture_output=True, text=True, timeout=30)
    except Exception:  # noqa: BLE001
        return None
    out = (proc.stdout or "").strip()
    return out or None


# --------------------------------------------------------------------------
# the command
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse
    import subprocess

    parser = argparse.ArgumentParser(
        prog="magi update",
        description="Check for a newer release and install it.")
    parser.add_argument("--check", action="store_true",
                        help="Only report; do not install anything.")
    parser.add_argument("--json", action="store_true",
                        help="Machine-readable result.")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Do not ask before upgrading.")
    # Internal, and named so: this is how the WebUI hands the upgrade to a
    # process that will outlive it. Not for people to type.
    parser.add_argument("--_run-detached", dest="run_detached",
                        action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_wait-pid", dest="wait_pid", type=int, default=0,
                        help=argparse.SUPPRESS)
    parser.add_argument("--_relaunch", dest="relaunch", default="",
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.run_detached:
        relaunch = None
        if args.relaunch:
            try:
                parsed = json.loads(args.relaunch)
                relaunch = parsed if isinstance(parsed, list) else None
            except ValueError:
                relaunch = None
        return _run_detached(args.wait_pid, relaunch)

    how = detect_install()
    latest = fetch_latest()
    if latest is not None:
        write_cache(latest)

    # "Could not look" is not "nothing newer", and must not be reported as it.
    unreachable = latest is None
    available = (not unreachable) and is_newer(latest, __version__)

    if args.json:
        print(json.dumps({
            "installed": __version__,
            "latest": latest,
            "update_available": available,
            "checked": not unreachable,
            "install_method": how.kind,
            "command": how.command,
            "note": how.note,
        }, indent=2, ensure_ascii=False))
        return 0

    if unreachable:
        print(f"magi {__version__} — could not reach {SIMPLE_INDEX} to check "
              "for updates.", file=sys.stderr)
        print("That is a network problem, not an answer about versions.",
              file=sys.stderr)
        return 1

    if not available:
        print(f"magi {__version__} is the latest release.")
        return 0

    print(f"magi {latest} is available (you have {__version__}).")

    if how.command is None:
        print(f"\n{how.note}")
        return 0

    if args.check:
        print("\nTo install it:  " + " ".join(how.command))
        return 0

    print(f"\nDetected install: {how.kind}"
          + (f" — {how.note}" if how.note else ""))
    print("Running: " + " ".join(how.command))

    interactive = (not args.yes) and sys.stdin.isatty() and sys.stdout.isatty()
    if interactive:
        try:
            if input("Proceed? [Y/n] ").strip().lower() in ("n", "no"):
                print("nothing changed.")
                return 0
        except (EOFError, KeyboardInterrupt):
            print("\nnothing changed.")
            return 130

    # Windows holds the files of a running install: a `magi ui` dashboard, its
    # venv python, and whatever launched it all keep the directory open, and the
    # upgrade fails halfway with a permission error that leaves the CLI broken.
    if os.name == "nt":
        print("\nIf this fails with a permission error, a `magi ui` process is "
              "holding the files — stop every one of them and try again.")

    try:
        proc = subprocess.run(how.command)
    except FileNotFoundError:
        print(f"\n{how.command[0]} is not on PATH. Run this yourself:\n  "
              + " ".join(how.command), file=sys.stderr)
        return 1

    if proc.returncode != 0:
        print(f"\nupgrade failed (exit {proc.returncode}). Nothing was changed "
              "by magi itself.", file=sys.stderr)
        return proc.returncode

    # Say what is actually installed now rather than what was asked for. The
    # documented pipx failure mode exits non-zero, but a tool that silently
    # kept the old version would look identical to success from here.
    print(f"\nUpgrade command finished. Run `magi --version` in a new shell to "
          f"confirm you are on {latest}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
