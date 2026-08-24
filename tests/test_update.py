"""Update checking, and upgrading a package the running process is inside.

Two facts drive most of what is tested here, and neither is obvious:

**The two PyPI indexes disagree for minutes.** `pypi.org/pypi/<pkg>/json`
publishes a release within seconds; `pypi.org/simple/<pkg>/`, which is what
every installer resolves against, lags. A notice sourced from the fast one
announces a version that `pipx upgrade` then correctly declines to install —
teaching people that the notices are noise. So the check reads the simple
index, and everything below is about what that returns.

**A live `magi ui` holds open the files it would be replacing.** Its venv's
`python.exe` and every loaded extension module are locked on Windows, so the
upgrade cannot happen inside the server process. It is handed to a detached
helper that waits for the server to exit first — and "waits" has to be real,
because upgrading underneath a process that is still running is the exact
failure the design exists to avoid.
"""

import json
import time

import pytest

from magi import update


# --------------------------------------------------------------------------
# versions
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,want", [
    ("1.13.0", (1, 13, 0)),
    ("1.13", (1, 13)),
    ("2", (2,)),
    ("1.14.0rc1", None),
    ("1.14.0.dev3", None),
    ("", None),
    ("latest", None),
])
def test_only_plain_numeric_versions_are_understood(text, want):
    """A background check must never nudge somebody onto a release candidate,
    so an unparseable version is ignored rather than guessed at."""
    assert update.parse_version(text) == want


@pytest.mark.parametrize("newer,older", [
    ("1.13.1", "1.13.0"),
    ("1.14.0", "1.13.9"),
    ("2.0.0", "1.99.99"),
    ("1.13.10", "1.13.9"),      # not string order
])
def test_newer_is_newer(newer, older):
    assert update.is_newer(newer, older)
    assert not update.is_newer(older, newer)


def test_the_same_version_is_not_newer():
    assert not update.is_newer("1.13.0", "1.13.0")


def test_trailing_zeros_do_not_make_a_version_newer():
    assert not update.is_newer("1.13", "1.13.0")
    assert not update.is_newer("1.13.0", "1.13")


def test_an_unparseable_candidate_is_never_offered():
    assert not update.is_newer("1.14.0rc1", "1.13.0")


# --------------------------------------------------------------------------
# reading the index installers actually use
# --------------------------------------------------------------------------

SIMPLE_PAGE = """<!DOCTYPE html><html><body>
<a href="...">magi_research-1.12.5-py3-none-any.whl</a>
<a href="...">magi_research-1.12.5.tar.gz</a>
<a href="...">magi_research-1.13.0-py3-none-any.whl</a>
<a href="...">magi_research-1.13.0.tar.gz</a>
</body></html>"""


def test_the_newest_version_is_taken_from_the_simple_index(monkeypatch):
    from magi.core import http

    monkeypatch.setattr(http, "http_text", lambda url, timeout=0: SIMPLE_PAGE)
    assert update.fetch_latest() == "1.13.0"


def test_it_reads_the_simple_index_not_the_json_api(monkeypatch):
    """The JSON API is minutes ahead of what installers can actually get."""
    seen = []
    from magi.core import http

    monkeypatch.setattr(http, "http_text",
                        lambda url, timeout=0: seen.append(url) or SIMPLE_PAGE)
    update.fetch_latest()
    assert seen == [update.SIMPLE_INDEX]
    assert "/simple/" in seen[0]


def test_a_prerelease_on_the_index_is_not_offered(monkeypatch):
    from magi.core import http

    page = SIMPLE_PAGE + '<a href="">magi_research-1.14.0rc1-py3-none-any.whl</a>'
    monkeypatch.setattr(http, "http_text", lambda url, timeout=0: page)
    assert update.fetch_latest() == "1.13.0"


def test_an_unreachable_index_is_none_and_not_an_exception(monkeypatch):
    """"Could not look" is a different answer from "nothing newer", and the
    callers all have to be able to tell them apart."""
    from magi.core import http

    def boom(*a, **k):
        raise OSError("no route to host")

    monkeypatch.setattr(http, "http_text", boom)
    assert update.fetch_latest() is None


# --------------------------------------------------------------------------
# the notice never waits on the network
# --------------------------------------------------------------------------

@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("MAGI_NO_UPDATE_CHECK", raising=False)
    monkeypatch.delenv("CI", raising=False)
    return tmp_path


def test_the_notice_comes_from_the_cache_only(home, monkeypatch):
    from magi.core import http

    def boom(*a, **k):
        raise AssertionError("pending_notice must not touch the network")

    monkeypatch.setattr(http, "http_text", boom)
    update.write_cache("99.0.0")
    assert "99.0.0" in update.pending_notice()


def test_no_notice_when_the_cache_is_empty(home):
    assert update.pending_notice() == ""


def test_no_notice_when_the_cache_is_not_newer(home):
    from magi import __version__

    update.write_cache(__version__)
    assert update.pending_notice() == ""


def test_a_corrupt_cache_is_silence_not_a_crash(home):
    update.cache_path().parent.mkdir(parents=True, exist_ok=True)
    update.cache_path().write_text("{not json", encoding="utf-8")
    assert update.read_cache() == {}
    assert update.pending_notice() == ""


def test_a_fresh_cache_is_not_refetched(home, monkeypatch):
    calls = []
    monkeypatch.setattr(update, "fetch_latest", lambda *a, **k: calls.append(1))
    update.write_cache("1.0.0")
    update.refresh_in_background()
    time.sleep(0.2)
    assert calls == []


def test_a_stale_cache_is_refetched(home, monkeypatch):
    calls = []
    monkeypatch.setattr(update, "fetch_latest",
                        lambda *a, **k: calls.append(1) or "1.0.0")
    update.write_cache("1.0.0")
    stale = json.loads(update.cache_path().read_text(encoding="utf-8"))
    stale["checked_at"] = time.time() - update.CACHE_TTL_S - 10
    update.cache_path().write_text(json.dumps(stale), encoding="utf-8")

    update.refresh_in_background()
    for _ in range(50):
        if calls:
            break
        time.sleep(0.02)
    assert calls == [1]


@pytest.mark.parametrize("var", ["MAGI_NO_UPDATE_CHECK", "CI"])
def test_the_check_can_be_switched_off_by_environment(home, monkeypatch, var):
    monkeypatch.setenv(var, "1")
    assert update.notice_enabled() is False


def test_the_check_can_be_switched_off_in_settings(home):
    from magi.kb_registry import save_settings

    save_settings({"update_check": False})
    assert update.notice_enabled() is False


# --------------------------------------------------------------------------
# which tool owns this install
# --------------------------------------------------------------------------

def test_a_source_checkout_is_never_handed_to_a_package_manager():
    how = update.detect_install(prefix="/usr", package_file="/work/magi/src/magi/update.py")
    assert how.kind == "source"
    assert how.command is None


def test_pipx_is_upgraded_not_force_installed():
    """`pipx install --force` over an existing install prints "Installing to
    existing venv", exits 1, and leaves the old version in place — a failure
    whose message reads like success."""
    how = update.detect_install(
        prefix="/home/u/.local/pipx/venvs/magi-research",
        package_file="/home/u/.local/pipx/venvs/magi-research/lib/site-packages/magi/update.py")
    assert how.kind == "pipx"
    assert how.command == ["pipx", "upgrade", "magi-research"]
    assert "--force" not in how.command


def test_a_uv_tool_install_uses_force_and_refresh():
    how = update.detect_install(
        prefix="/home/u/.local/share/uv/tools/magi-research",
        package_file="/home/u/.local/share/uv/tools/magi-research/lib/site-packages/magi/update.py")
    assert how.kind == "uv"
    assert "--refresh" in how.command


def test_a_plain_virtualenv_uses_its_own_pip():
    how = update.detect_install(
        prefix="/work/.venv", base_prefix="/usr",
        package_file="/work/.venv/lib/site-packages/magi/update.py")
    assert how.kind == "pip"
    assert "pip" in how.command


def test_an_unrecognised_install_refuses_to_guess():
    """A system-wide install owned by something we cannot name.

    `base_prefix` is passed explicitly, and that is the point: it used to be
    read from the live interpreter no matter what the caller injected, so this
    test's answer depended on whether the test runner was inside a venv. It
    passed locally and failed in CI — a seam that is only half a seam is worse
    than none, because it looks tested.
    """
    how = update.detect_install(prefix="/usr", base_prefix="/usr",
                                package_file="/usr/lib/site-packages/magi/update.py")
    assert how.kind == "unknown"
    assert how.command is None
    assert how.note


def test_detection_does_not_depend_on_the_running_interpreter():
    """Same inputs, same answer, whether or not this process is in a venv."""
    args = dict(prefix="/usr", base_prefix="/usr",
                package_file="/usr/lib/site-packages/magi/update.py")
    assert update.detect_install(**args).kind == "unknown"
    assert update.detect_install(**args).kind == "unknown"


# --------------------------------------------------------------------------
# the detached upgrade
# --------------------------------------------------------------------------

def test_the_helper_refuses_to_upgrade_under_a_live_process(home, monkeypatch):
    """The whole reason the helper exists. Upgrading while the dashboard still
    holds its files open is the failure, so timing out has to mean "did not
    upgrade", not "upgraded anyway"."""
    monkeypatch.setattr(update, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(update.time, "time",
                        lambda _c=iter([0, 0, 100, 100, 100] + [100] * 50): next(_c))

    ran = []
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: ran.append(a))

    assert update._run_detached(4242, None) == 1
    assert ran == []
    result = update.read_result()
    assert result["state"] == "failed"
    assert "still running" in result["error"]


def test_a_successful_upgrade_records_the_version_on_disk(home, monkeypatch):
    """Not the version it asked for. A command that exits 0 is not proof: the
    documented pipx failure keeps the old version and still finishes."""
    import subprocess
    import types

    monkeypatch.setattr(update, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(update.time, "sleep", lambda *_: None)
    monkeypatch.setattr(update, "detect_install",
                        lambda *a, **k: update.Install("pipx", ["pipx", "upgrade", "x"]))
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            returncode=0, stdout="upgraded", stderr=""))
    monkeypatch.setattr(update, "_installed_version_on_disk", lambda: "9.9.9")

    assert update._run_detached(1, None) == 0
    result = update.read_result()
    assert result["state"] == "done"
    assert result["now"] == "9.9.9"
    assert result["changed"] is True


def test_an_upgrade_that_changed_nothing_says_so(home, monkeypatch):
    import subprocess
    import types

    from magi import __version__

    monkeypatch.setattr(update, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(update.time, "sleep", lambda *_: None)
    monkeypatch.setattr(update, "detect_install",
                        lambda *a, **k: update.Install("pipx", ["pipx", "upgrade", "x"]))
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            returncode=0, stdout="Installing to existing venv", stderr=""))
    monkeypatch.setattr(update, "_installed_version_on_disk", lambda: __version__)

    update._run_detached(1, None)
    result = update.read_result()
    assert result["state"] == "done"
    assert result["changed"] is False


def test_a_failed_upgrade_keeps_its_output(home, monkeypatch):
    import subprocess
    import types

    monkeypatch.setattr(update, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(update.time, "sleep", lambda *_: None)
    monkeypatch.setattr(update, "detect_install",
                        lambda *a, **k: update.Install("pipx", ["pipx", "upgrade", "x"]))
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            returncode=1, stdout="", stderr="permission denied"))

    assert update._run_detached(1, None) == 1
    result = update.read_result()
    assert result["state"] == "failed"
    assert "permission denied" in result["output"]


# --------------------------------------------------------------------------
# the command
# --------------------------------------------------------------------------

def test_json_output_distinguishes_offline_from_up_to_date(home, monkeypatch, capsys):
    monkeypatch.setattr(update, "fetch_latest", lambda *a, **k: None)
    update.main(["--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["checked"] is False
    assert data["update_available"] is False
    assert data["latest"] is None


def test_being_offline_is_a_non_zero_exit_and_says_why(home, monkeypatch, capsys):
    monkeypatch.setattr(update, "fetch_latest", lambda *a, **k: None)
    assert update.main([]) == 1
    err = capsys.readouterr().err
    assert "could not reach" in err
    assert "not an answer about versions" in err


def test_check_only_never_runs_anything(home, monkeypatch, capsys):
    import subprocess

    monkeypatch.setattr(update, "fetch_latest", lambda *a, **k: "99.0.0")
    monkeypatch.setattr(update, "detect_install",
                        lambda *a, **k: update.Install("pipx", ["pipx", "upgrade", "x"]))
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: pytest.fail("--check must not install"))

    assert update.main(["--check"]) == 0
    assert "pipx upgrade x" in capsys.readouterr().out


def test_up_to_date_is_a_clean_exit(home, monkeypatch, capsys):
    from magi import __version__

    monkeypatch.setattr(update, "fetch_latest", lambda *a, **k: __version__)
    assert update.main([]) == 0
    assert "latest release" in capsys.readouterr().out


# --------------------------------------------------------------------------
# the endpoints
# --------------------------------------------------------------------------

@pytest.fixture
def client(home):
    from fastapi.testclient import TestClient

    from magi.ui.api import create_app

    return TestClient(create_app())


def test_the_status_endpoint_answers_from_the_cache(client, monkeypatch):
    """A page load must not wait on pypi.org any more than a command does."""
    monkeypatch.setattr(update, "fetch_latest",
                        lambda *a, **k: pytest.fail("no network on a page load"))
    update.write_cache("99.0.0")
    body = client.get("/api/update").json()
    assert body["latest"] == "99.0.0"
    assert body["update_available"] is True


def test_refresh_is_the_button_and_may_wait(client, monkeypatch):
    monkeypatch.setattr(update, "fetch_latest", lambda *a, **k: "99.9.9")
    body = client.get("/api/update?refresh=1").json()
    assert body["latest"] == "99.9.9"
    assert body["checked"] is True


def test_an_offline_refresh_is_not_reported_as_up_to_date(client, monkeypatch):
    monkeypatch.setattr(update, "fetch_latest", lambda *a, **k: None)
    body = client.get("/api/update?refresh=1").json()
    assert body["checked"] is False
    assert body["update_available"] is False


def test_an_install_that_cannot_be_upgraded_refuses_with_a_reason(client, monkeypatch):
    monkeypatch.setattr(update, "detect_install",
                        lambda *a, **k: update.Install("source", None, "it is a checkout"))
    res = client.post("/api/update/apply")
    assert res.status_code == 400
    assert "checkout" in res.json()["detail"]


def test_applying_spawns_a_helper_and_then_shuts_down(client, monkeypatch):
    """The order is the safety property: the helper is already waiting on this
    pid before the shutdown starts, so a shutdown that never happens is a
    stuck upgrade rather than one that ran underneath a live server."""
    import magi.ui.api as api_mod

    order = []
    monkeypatch.setattr(update, "detect_install",
                        lambda *a, **k: update.Install("pipx", ["pipx", "upgrade", "x"]))
    monkeypatch.setattr(update, "spawn_detached_upgrade",
                        lambda **kw: order.append(("spawn", kw)) or True)
    # Without this the endpoint signals the *test runner*. It did, once, which
    # is why the shutdown is a module-level function and not a closure.
    monkeypatch.setattr(api_mod, "_shutdown_this_server",
                        lambda: order.append(("shutdown", {})))

    body = client.post("/api/update/apply").json()
    assert body["started"] is True
    assert [step for step, _ in order] == ["spawn", "shutdown"],         "the helper must already be waiting on this pid before we start dying"
    assert order[0][1]["wait_pid"] > 0
    assert any("magi" in part for part in order[0][1]["relaunch"])


def test_a_helper_that_will_not_start_is_an_error_not_a_shutdown(client, monkeypatch):
    monkeypatch.setattr(update, "detect_install",
                        lambda *a, **k: update.Install("pipx", ["pipx", "upgrade", "x"]))
    monkeypatch.setattr(update, "spawn_detached_upgrade", lambda **kw: False)

    import magi.ui.api as api_mod
    died = []
    monkeypatch.setattr(api_mod, "_shutdown_this_server", lambda: died.append(1))

    assert client.post("/api/update/apply").status_code == 500
    assert died == [], "a dashboard that could not start the helper must stay up"


def test_the_result_survives_for_the_relaunched_dashboard(client):
    """The helper runs while no page is open, so this file is the only channel
    its outcome has."""
    update._write_result(state="done", installed="1.0.0", now="1.1.0", changed=True)
    body = client.get("/api/update/result").json()
    assert body["state"] == "done" and body["now"] == "1.1.0"

    client.post("/api/update/result/clear")
    assert client.get("/api/update/result").json() == {}


# --------------------------------------------------------------------------
# The relaunched dashboard, reported as a hung process
#
# The first version spawned it with DETACHED_PROCESS and its output pointed at
# the null device. A console window appeared anyway — black, silent, and never
# returning a prompt, which is exactly what a hung process looks like. The
# upgrade had in fact succeeded and the dashboard behind that window was
# serving the new version.
#
# Two defects, one report: the wrong Windows flag, and throwing away the only
# evidence of what the new server said.
# --------------------------------------------------------------------------

def test_a_detached_child_gets_no_console_window():
    """CREATE_NO_WINDOW (0x08000000), not DETACHED_PROCESS (0x8)."""
    kwargs = update._detached_kwargs()
    if update.os.name != "nt":
        assert kwargs["start_new_session"] is True
        return
    flags = kwargs["creationflags"]
    assert flags & 0x08000000, "CREATE_NO_WINDOW is missing"
    assert not (flags & 0x00000008), "DETACHED_PROCESS is back; it showed a window"
    assert flags & 0x00000200, "CREATE_NEW_PROCESS_GROUP is missing"


def test_the_relaunched_server_keeps_a_log(home, tmp_path):
    """Output thrown away is why "it just sat there" could not be diagnosed."""
    log = tmp_path / "ui.log"
    kwargs = update._detached_kwargs(log)
    stream = kwargs["stdout"]
    assert stream is kwargs["stderr"]
    assert hasattr(stream, "write"), "output is still going to the null device"
    stream.write("hello\n")
    stream.close()
    assert "hello" in log.read_text(encoding="utf-8")


def test_an_unwritable_log_falls_back_rather_than_failing(home, tmp_path, monkeypatch):
    """A log is a nicety; not relaunching the dashboard is not.

    The failure is forced rather than provoked with a hopeless path: the first
    version of this test used "/nonexistent-root/x/ui.log", which Windows
    cheerfully created on the current drive — so it tested the happy path and
    left a directory behind on the machine.
    """
    import builtins
    import subprocess

    def no_open(*a, **k):
        raise OSError("read-only file system")

    monkeypatch.setattr(builtins, "open", no_open)
    kwargs = update._detached_kwargs(tmp_path / "ui.log")
    assert kwargs["stdout"] is subprocess.DEVNULL


@pytest.mark.parametrize("argv,want", [
    (["py", "-m", "magi", "ui", "--host", "127.0.0.1", "--port", "8737"],
     ("127.0.0.1", 8737)),
    (["py", "-m", "magi", "ui", "--port", "9000"], ("127.0.0.1", 9000)),
    (["py", "-m", "magi", "ui", "--no-open"], None),
    (["py", "-m", "magi", "ui", "--port", "notanumber"], None),
])
def test_the_relaunch_port_is_read_out_of_the_command(argv, want):
    assert update._port_of(argv) == want


def test_no_second_server_is_started_on_a_port_that_answers(home, monkeypatch):
    """`magi ui` treats an explicitly requested busy port as fatal, so a
    duplicate does not step aside politely. Somebody who restarted the
    dashboard themselves while waiting keeps the one they started."""
    import subprocess

    monkeypatch.setattr(update, "_port_state", lambda h, p, timeout=0.4: "taken")
    monkeypatch.setattr(update.time, "sleep", lambda *_: None)
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: pytest.fail("must not start a second server"))

    note = update._relaunch(["py", "-m", "magi", "ui", "--port", "8737"])
    assert "still serving" in note


def test_the_relaunch_waits_for_the_old_listener_to_go(home, monkeypatch):
    """The socket outlives the process by a moment; relaunching into that
    window is a race that loses silently."""
    import subprocess

    states = iter(["taken", "taken", "free"])
    monkeypatch.setattr(update, "_port_state",
                        lambda h, p, timeout=0.4: next(states, "free"))
    monkeypatch.setattr(update.time, "sleep", lambda *_: None)
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: started.append(a[0]))

    assert update._relaunch(["py", "-m", "magi", "ui", "--port", "8737"]) == ""
    assert started and started[0][-1] == "8737"


def test_a_relaunch_that_could_not_start_is_recorded(home, monkeypatch):
    import subprocess

    monkeypatch.setattr(update, "_port_state", lambda h, p, timeout=0.4: "free")

    def boom(*a, **k):
        raise OSError("no such file")

    monkeypatch.setattr(subprocess, "Popen", boom)
    note = update._relaunch(["py", "-m", "magi", "ui", "--port", "8737"])
    assert "could not relaunch" in note


def test_the_upgrade_result_is_written_before_the_relaunch_is_attempted(home, monkeypatch):
    """The relaunch waits up to twenty seconds. A reader arriving during that
    wait must not find a file that still says the upgrade is running."""
    import subprocess
    import types

    seen = {}
    monkeypatch.setattr(update, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(update.time, "sleep", lambda *_: None)
    monkeypatch.setattr(update, "detect_install",
                        lambda *a, **k: update.Install("pipx", ["pipx", "upgrade", "x"]))
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: types.SimpleNamespace(
                            returncode=0, stdout="ok", stderr=""))
    monkeypatch.setattr(update, "_installed_version_on_disk", lambda: "9.9.9")
    monkeypatch.setattr(update, "_relaunch",
                        lambda argv: seen.update(state_at_relaunch=update.read_result().get("state")) or "")

    update._run_detached(1, ["py", "-m", "magi", "ui"])
    assert seen["state_at_relaunch"] == "done"
    assert update.read_result()["now"] == "9.9.9"


def test_the_narration_is_flushed_before_the_child_writes(home, monkeypatch, capsys):
    """Order matters, and it was wrong.

    Python block-buffers stdout when it is not a terminal — a pipe, a CI log,
    an agent's shell. `print()` therefore sat in the buffer while the child
    process wrote straight to the same descriptor, so a real run came out as:

        upgrading magi-research...
        upgraded package magi-research from 1.14.1 to 1.14.2
        magi 1.14.2 is available (you have 1.14.1).
        Running: pipx upgrade magi-research

    — pipx finishing before magi says it is about to start it.
    """
    import subprocess
    import sys
    import types

    flushed_before_run = []
    real_flush = sys.stdout.flush

    def spy_flush():
        flushed_before_run.append(True)
        real_flush()

    monkeypatch.setattr(update, "fetch_latest", lambda *a, **k: "99.0.0")
    monkeypatch.setattr(update, "detect_install",
                        lambda *a, **k: update.Install("pipx", ["pipx", "upgrade", "x"]))
    monkeypatch.setattr(sys.stdout, "flush", spy_flush)

    def fake_run(cmd, *a, **k):
        assert flushed_before_run, "the child started with output still buffered"
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    assert update.main([]) == 0
