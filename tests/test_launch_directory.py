"""Where `magi ui` was started must not decide what it shows or writes.

The server resolves an unspecified workspace from its own working directory.
That is the right default for a CLI and a trap for a long-running dashboard,
because the workspace the *reader* has chosen lives in a picker at the top of
the page and has nothing to do with where the process was launched.

Two things it used to decide, both found by asking the question:

* the Docs tab's English README was blank for everyone who did not launch from
  a git checkout, because the only packaged copy came from the wheel's
  long_description — which is README.md, and only README.md;
* an enqueue with no library named filed the paper into the launch directory,
  which a browser extension whose picker failed to load would do silently.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from magi.ui.api import create_app

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    home = tmp_path / "cfg"
    home.mkdir()
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(home))
    return TestClient(create_app())


# --------------------------------------------------------------------------
# the documents ship with the package
# --------------------------------------------------------------------------

def test_both_readmes_are_packaged():
    """`package-data` covers `docs/*.md`, so a copy there reaches every
    install. The repo-root originals stay where GitHub and PyPI need them."""
    docs = REPO / "src" / "magi" / "docs"
    for name in ("readme.zh.md", "readme.en.md"):
        assert (docs / name).is_file(), f"{name} is not packaged"


@pytest.mark.parametrize("packaged,original", [
    ("readme.zh.md", "README.md"),
    ("readme.en.md", "README_en.md"),
])
def test_the_packaged_copies_match_the_originals(packaged, original):
    """Two copies of a document drift the moment one is edited. Nothing here
    generates them at build time, so this test is what stops the drift."""
    a = (REPO / "src" / "magi" / "docs" / packaged).read_text(encoding="utf-8")
    b = (REPO / original).read_text(encoding="utf-8")
    assert a == b, (
        f"{packaged} has drifted from {original}. Re-copy it:\n"
        f"    copy {original} src\\magi\\docs\\{packaged}")


def test_the_readme_endpoint_serves_both_languages_from_the_package(client, tmp_path,
                                                                    monkeypatch):
    """Launched anywhere at all, both tabs must have content.

    Run from a directory that is neither a workspace nor a checkout — the
    situation of every ordinary user — and the endpoint still has to answer.
    """
    elsewhere = tmp_path / "nowhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    data = client.get("/api/docs/readme").json()
    assert data["source"] == "packaged", data.get("source")
    assert len(data["readme_zh"]) > 1000
    assert len(data["readme_en"]) > 1000, (
        "the English README is empty — this is the bug: metadata carries only "
        "README.md, so the second tab had nothing in it")


# --------------------------------------------------------------------------
# writes must name their destination
# --------------------------------------------------------------------------

def test_enqueue_refuses_to_guess_when_there_is_no_default(client):
    """Started outside any workspace, there is no sensible default.

    `_resolve_workspace` falls through to bare `Path.cwd()`, so the paper
    would be filed into whatever directory `magi ui` was launched in. That is
    the worst outcome: it is not lost, it is somewhere else, and nobody looks
    there. Started *inside* a workspace the omission is unambiguous and still
    allowed — see the tests in test_ui_ingest.py that rely on it.
    """
    res = client.post("/api/ingest/enqueue", json={"value": "https://arxiv.org/abs/2401.00506"})
    assert res.status_code == 400
    assert "name the library" in res.json()["detail"]


def test_enqueue_still_refuses_an_unknown_library(client):
    res = client.post("/api/ingest/enqueue",
                      json={"value": "https://arxiv.org/abs/2401.00506",
                            "library": "no-such-library"})
    assert res.status_code == 404


def test_enqueue_error_names_what_is_available(client, tmp_path):
    """A refusal that does not say what would work is a dead end."""
    from magi.kb_registry import register_kb

    ws = tmp_path / "somewhere"
    (ws / "wiki").mkdir(parents=True)
    (ws / "config.yaml").write_text("name: somewhere\n", encoding="utf-8")
    (ws / "log.md").write_text("# log\n", encoding="utf-8")
    name = register_kb(ws, quiet=True)

    detail = client.post("/api/ingest/enqueue",
                         json={"value": "https://arxiv.org/abs/2401.00506"}).json()["detail"]
    assert name in detail, f"the error does not name the library that would work: {detail}"


# --------------------------------------------------------------------------
# what the launch directory legitimately still decides
# --------------------------------------------------------------------------

def test_status_reports_the_launch_directory_honestly(client, tmp_path, monkeypatch):
    """It is allowed to affect the *initial* selection — that is a convenience,
    and the picker overrides it. What matters is that it says so, because the
    "Browsing" badge is driven by exactly this field."""
    elsewhere = tmp_path / "nowhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    data = client.get("/api/status").json()
    assert data["active_workspace"] is None, (
        "launched outside any workspace, the server must not claim one")
    assert Path(data["cwd"]).resolve() == elsewhere.resolve()


def test_every_workspace_panel_names_its_workspace():
    """The UI must not rely on the server's default for panel data.

    Each of these builds its query with URLSearchParams; the requirement is
    that `workspace` is in it, so what a panel shows follows the picker rather
    than the launch directory.
    """
    app_js = (REPO / "src" / "magi" / "ui" / "static" / "app.js").read_text(encoding="utf-8")
    for endpoint in ("/api/workspace/graph/browse", "/api/workspace/doc",
                     "/api/workspace/search", "/api/workspace/tasks",
                     "/api/workspace/pm", "/api/workspace/radar"):
        idx = app_js.find(endpoint)
        assert idx != -1, f"{endpoint} is no longer called"
        # The query is assembled in the ~20 lines above the call.
        window = app_js[max(0, idx - 1200):idx]
        assert "workspace" in window, (
            f"{endpoint} is called without naming a workspace — it would fall "
            f"back to wherever the server was started")


# --------------------------------------------------------------------------
# and the same question, asked of every command rather than of one server
# --------------------------------------------------------------------------

def test_no_command_that_takes_a_workspace_reads_config_from_the_cwd():
    r"""`load_config()` walks up from the process working directory.

    That is the right default for a command that was not told where to work,
    and wrong for every command that *was*. `magi ingest auto --topic-dir B`,
    run from workspace A, read A's `config.yaml` and wrote B's library: the OCR
    model, the MinerU token and the figure-extraction mode all came from the
    wrong place, and nothing said so.

    This is the shape v1.12.2 already fixed once for `magi ui` — "the launch
    directory decided two things it had no business deciding". A point fix with
    no guard came back within two releases, in six more places, so the guard is
    the deliverable and the fixes are its consequence.

    Reading ambient config is still fine in a module that has no workspace to
    read from. The scan is deliberately narrow: it asks only about modules that
    declare `--topic-dir`, i.e. modules that have been handed an answer and
    then went and looked somewhere else.
    """
    import re

    src = REPO / "src" / "magi"
    declares = re.compile(r"""add_argument\(\s*['"]--topic-dir['"]""")
    ambient = re.compile(r"""\bload_config\(\s*\)""")

    offenders = []
    for path in sorted(src.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if not declares.search(text):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            code = line.split("#", 1)[0]
            if ambient.search(code):
                offenders.append(f"{path.relative_to(src)}:{n}: {line.strip()}")

    assert not offenders, (
        "these accept --topic-dir and then load config from the process "
        "working directory instead; pass start=<workspace>:\n  "
        + "\n  ".join(offenders))
