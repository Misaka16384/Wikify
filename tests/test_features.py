"""The optional-feature switches: radar and task tracking.

Two rules carry the weight here and both are about not surprising people:

*Absent means on.* Someone upgrading into this release has no
``optional_features`` entry for either key, and must not find a panel they use
every day greyed out because a newer version invented a switch.

*An off feature is not a fault.* It carries no weight in the sync ratio and
raises no hints. A workspace is not 33% unhealthy for declining a workflow.
"""

from __future__ import annotations

import json

import pytest

from magi import features


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    """An isolated global-settings dir. Never the developer's own."""
    home = tmp_path / "cfg"
    home.mkdir()
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(home))
    return home


def _workspace(tmp_path):
    """A directory `is_topic_root` actually recognises.

    It wants a content dir *and* a marker file; with only the content dir the
    report finds no topic at all and every score comes back None, which is not
    the thing these tests are about.
    """
    ws = tmp_path / "topic"
    (ws / "wiki").mkdir(parents=True)
    (ws / "config.yaml").write_text("name: topic\n", encoding="utf-8")
    (ws / "log.md").write_text("# log\n", encoding="utf-8")
    return ws


def _settings(config_home: object) -> dict:
    from magi.kb_registry import settings_path

    p = settings_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# --------------------------------------------------------------------------
# absent means on
# --------------------------------------------------------------------------

def test_a_machine_that_was_never_asked_has_everything_on(config_home):
    assert features.enabled_features() == {"radar": True, "tasks": True}


def test_an_unrelated_settings_file_still_means_on(config_home):
    from magi.kb_registry import save_settings

    save_settings({"profile": "full", "something_else": 1})
    assert features.feature_enabled("radar") is True
    assert features.feature_enabled("tasks") is True


def test_only_an_explicit_false_turns_something_off(config_home):
    from magi.kb_registry import save_settings

    save_settings({"optional_features": {"radar": False}})
    assert features.feature_enabled("radar") is False
    # The other key is still absent, so still on.
    assert features.feature_enabled("tasks") is True


# --------------------------------------------------------------------------
# the older kb-only profile
# --------------------------------------------------------------------------

def test_the_legacy_kb_only_profile_still_turns_tasks_off(config_home):
    """`profile: kb-only` predates this module and is how existing installs
    say "no task tracking". It has to keep working, or those machines grow a
    Balthasar panel back on upgrade."""
    from magi.kb_registry import save_settings

    save_settings({"profile": "kb-only"})
    assert features.feature_enabled("tasks") is False
    assert features.feature_enabled("radar") is True


def test_turning_tasks_on_clears_the_legacy_profile(config_home):
    """Otherwise the stale profile keeps overriding the answer just given, and
    the button in the WebUI looks broken: you click it, and nothing changes."""
    from magi.kb_registry import save_settings

    save_settings({"profile": "kb-only"})
    features.set_feature("tasks", True)

    assert features.feature_enabled("tasks") is True
    assert _settings(config_home)["profile"] == "full"


def test_turning_tasks_off_writes_the_legacy_profile_too(config_home):
    """The reverse: anything still reading `profile` must agree."""
    features.set_feature("tasks", False)
    assert _settings(config_home)["profile"] == "kb-only"
    assert features.feature_enabled("tasks") is False


def test_the_radar_switch_does_not_touch_the_profile(config_home):
    from magi.kb_registry import save_settings

    save_settings({"profile": "full"})
    features.set_feature("radar", False)
    assert _settings(config_home)["profile"] == "full"


# --------------------------------------------------------------------------
# round trip and guard rails
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", features.FEATURE_KEYS)
@pytest.mark.parametrize("value", [True, False])
def test_round_trip(config_home, key, value):
    features.set_feature(key, value)
    assert features.feature_enabled(key) is value


def test_an_unknown_feature_is_refused(config_home):
    """A typo must not silently write a key nothing ever reads."""
    with pytest.raises(ValueError):
        features.set_feature("radarr", True)


def test_setting_one_feature_leaves_the_other_alone(config_home):
    features.set_feature("radar", False)
    features.set_feature("tasks", False)
    assert features.enabled_features() == {"radar": False, "tasks": False}
    features.set_feature("radar", True)
    assert features.enabled_features() == {"radar": True, "tasks": False}


def test_setting_a_feature_preserves_unrelated_settings(config_home):
    from magi.kb_registry import save_settings

    save_settings({"optional_features": {"ollama": False}, "keep_me": "yes"})
    features.set_feature("radar", False)

    data = _settings(config_home)
    assert data["keep_me"] == "yes"
    # The external-tool answers live in the same dict and must survive.
    assert data["optional_features"]["ollama"] is False
    assert data["optional_features"]["radar"] is False


# --------------------------------------------------------------------------
# what the sync report does with them
# --------------------------------------------------------------------------

def test_an_off_feature_does_not_drag_the_sync_ratio_down(config_home, tmp_path):
    """A core you switched off is not a core that is failing.

    With task tracking off the balthasar core carries no weight, so the ratio
    is computed over the cores actually in use — otherwise declining a feature
    would cap every workspace's health at two thirds forever.
    """
    import magi.sync

    ws = _workspace(tmp_path)

    features.set_feature("tasks", True)
    with_tasks = magi.sync.build_report(ws)
    features.set_feature("tasks", False)
    without = magi.sync.build_report(ws)

    assert with_tasks["cores"]["balthasar"].get("state") != "disabled"
    assert without["cores"]["balthasar"]["state"] == "disabled"
    assert without["cores"]["balthasar"]["score"] is None
    assert without["sync_ratio"] >= with_tasks["sync_ratio"]


def test_radar_off_silences_radar_hints(config_home, tmp_path):
    import magi.sync

    ws = _workspace(tmp_path)

    features.set_feature("radar", False)
    codes = [h["code"] for h in magi.sync.build_report(ws)["hints_structured"]]
    assert not [c for c in codes if c.startswith("radar-")]


def test_unreadable_settings_leave_features_on(config_home, monkeypatch, tmp_path):
    """A read error is less information than "absent", and absent means on.

    Failing closed here would turn both panels off on any machine with a
    corrupt settings file — a config problem presenting as a missing product.
    """
    import magi.sync

    def boom(*_a, **_k):
        raise OSError("settings unreadable")

    monkeypatch.setattr(features, "feature_enabled", boom)

    ws = _workspace(tmp_path)
    report = magi.sync.build_report(ws)
    assert report["cores"]["balthasar"].get("state") != "disabled"
