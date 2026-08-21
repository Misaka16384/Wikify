"""`/api/features`: what is on, and what a button can honestly do about it.

The load-bearing distinction is between a *feature* — MAGI's own workflow,
which a button really can switch on — and a *tool*, which is someone else's
installer. Reporting `can_install: true` for Pandoc would put a button on
screen that cannot keep its promise, so these tests pin that apart.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from magi.ui.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client whose settings live in a throwaway dir, never the real one."""
    home = tmp_path / "cfg"
    home.mkdir()
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(home))
    return TestClient(create_app())


# --------------------------------------------------------------------------
# shape
# --------------------------------------------------------------------------

def test_reports_both_features_on_by_default(client):
    data = client.get("/api/features").json()
    by_key = {f["key"]: f for f in data["features"]}
    assert set(by_key) == {"radar", "tasks"}
    assert all(f["enabled"] for f in by_key.values())


def test_only_task_tracking_claims_magi_can_install_it(client):
    """bd is the one dependency MAGI installs itself.

    Everything in `tools` is another project's installer or a hosted signup,
    so a true here would promise a one-click install that does not exist.
    """
    data = client.get("/api/features").json()
    can = {f["key"] for f in data["features"] if f["can_install"]}
    assert can == {"tasks"}
    assert not [t for t in data["tools"] if t["can_install"]]


def test_the_radar_needs_nothing_installed(client):
    radar = next(f for f in client.get("/api/features").json()["features"]
                 if f["key"] == "radar")
    assert radar["needs"] is None
    assert radar["needs_installed"] is True
    # Nothing to run: flipping the switch is the whole job.
    assert radar["op"] is None


def test_every_tool_carries_a_url_to_go_and_get_it(client):
    """The button's only honest offer, so it cannot be missing."""
    for tool in client.get("/api/features").json()["tools"]:
        assert tool["url"], f"{tool['key']} has nowhere to send the user"
        assert tool["url"].startswith("https://")


def test_mineru_is_a_service_not_a_binary(client):
    """`installed` is not a question you can ask of a hosted service, and
    answering False would show it as missing on a machine that has a token."""
    mineru = next(t for t in client.get("/api/features").json()["tools"]
                  if t["key"] == "mineru")
    assert mineru["installed"] is None


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

def test_turning_a_feature_off_and_back_on(client):
    assert client.post("/api/features",
                       json={"key": "radar", "enabled": False}).status_code == 200
    off = client.get("/api/features").json()["features"]
    assert next(f for f in off if f["key"] == "radar")["enabled"] is False

    client.post("/api/features", json={"key": "radar", "enabled": True})
    on = client.get("/api/features").json()["features"]
    assert next(f for f in on if f["key"] == "radar")["enabled"] is True


def test_declining_a_tool_is_recorded_separately(client):
    client.post("/api/features",
                json={"key": "pandoc", "enabled": False, "kind": "tool"})
    tools = {t["key"]: t for t in client.get("/api/features").json()["tools"]}
    assert tools["pandoc"]["wanted"] is False
    # Declining a tool must not touch MAGI's own switches.
    feats = client.get("/api/features").json()["features"]
    assert all(f["enabled"] for f in feats)


def test_unknown_keys_are_refused(client):
    assert client.post("/api/features",
                       json={"key": "radarr", "enabled": True}).status_code == 404
    assert client.post("/api/features",
                       json={"key": "nope", "enabled": True,
                             "kind": "tool"}).status_code == 404
    assert client.post("/api/features",
                       json={"key": "radar", "enabled": True,
                             "kind": "wat"}).status_code == 400


def test_the_body_is_a_body_not_a_query_string(client):
    """FeatureRequest has to be resolvable from module globals.

    `from __future__ import annotations` makes the endpoint's annotation a
    string that FastAPI looks up in this module's namespace. Defined inside
    create_app() it is invisible, and the parameter silently degrades to a
    required *query* parameter — a POST with a perfectly good JSON body then
    fails with "field required" pointing at the query string.
    """
    res = client.post("/api/features", json={"key": "tasks", "enabled": False})
    assert res.status_code == 200, res.text
    assert res.json() == {"key": "tasks", "enabled": False, "kind": "feature"}


# --------------------------------------------------------------------------
# the ops the buttons call
# --------------------------------------------------------------------------

def test_the_turn_on_ops_exist_and_are_narrow(client):
    """A button labelled "turn on task tracking" must not run all of setup.

    Someone clicking it has not agreed to re-provision their machine: no model
    pulls, no plugin registration, no skills pass.
    """
    from magi.ui.jobs import OPS

    assert OPS["install-tasks"]["argv"] == ["setup", "--install-tasks"]
    assert OPS["pull-models"]["argv"] == ["setup", "--pull-models"]
    for op in ("install-tasks", "pull-models"):
        assert OPS[op]["danger"] is False
        # What they install is machine-wide, and the badge has to say so.
        assert OPS[op]["scope"] == "global"


def test_the_ops_named_by_the_api_are_real_ops(client):
    """A stale op id here is a button that 404s on click."""
    from magi.ui.jobs import OPS

    data = client.get("/api/features").json()
    named = [row["op"] for row in data["features"] + data["tools"] if row["op"]]
    assert named, "nothing offers an op — the wiring is gone"
    for op in named:
        assert op in OPS, f"{op} is offered by /api/features but is not in OPS"


def test_setup_knows_the_flags_the_ops_send(capsys):
    """The ops table and setup's parser have to agree on the flag names.

    A typo here is a button that spawns a job, the job exits 2 on an unknown
    argument, and the panel reports a failure with no clue why. `--help` makes
    argparse print every flag it accepts without running any of them.
    """
    from magi.setup_cmd import main
    from magi.ui.jobs import OPS

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code in (0, None)
    help_text = capsys.readouterr().out

    for op in ("install-tasks", "pull-models"):
        for flag in OPS[op]["argv"][1:]:
            if flag.startswith("--"):
                assert flag in help_text, f"{op} sends {flag}, setup does not accept it"
