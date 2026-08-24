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
# the older kb-only profile, deleted
#
# `profile: kb-only` was a second spelling of `optional_features["tasks"]`,
# kept in step by `set_feature`. That is a maintenance obligation which has to
# be discharged correctly at every write site forever, and it was not: `magi
# setup --full` assigned `profile` on its own, the newer key still said False,
# and the command printed "profile set to full" while changing nothing.
#
# It is gone rather than migrated — a clean break, per locked decision D9. What
# these tests pin is that it is gone in every direction: not read, not written,
# and not resurrected by the one function that rewrites the block.
# --------------------------------------------------------------------------

def test_the_legacy_profile_key_no_longer_decides_anything(config_home):
    """A machine that was kb-only and never touched the newer key reads as
    "never asked", which is on. That is the cost of the break, stated."""
    from magi.kb_registry import save_settings

    save_settings({"profile": "kb-only"})
    assert features.feature_enabled("tasks") is True


def test_the_newer_key_is_the_only_answer(config_home):
    """Both present and disagreeing used to be a state that needed resolving.
    Now there is nothing to resolve, because only one of them is consulted."""
    from magi.kb_registry import save_settings

    save_settings({"profile": "full", "optional_features": {"tasks": False}})
    assert features.feature_enabled("tasks") is False

    save_settings({"profile": "kb-only", "optional_features": {"tasks": True}})
    assert features.feature_enabled("tasks") is True


def test_writing_a_feature_removes_a_stale_profile(config_home):
    """`set_feature` is the one function that rewrites this block, so it is the
    cheapest place to make sure the dead key does not survive to confuse
    somebody reading the file by hand."""
    from magi.kb_registry import save_settings

    save_settings({"profile": "kb-only"})
    features.set_feature("tasks", False)
    assert "profile" not in _settings(config_home)


def test_nothing_writes_the_profile_key_back(config_home):
    features.set_feature("tasks", True)
    features.set_feature("radar", False)
    assert "profile" not in _settings(config_home)


def test_no_module_reads_or_writes_the_profile_key():
    """The structural guard, turned around.

    It used to say "only `features.py` may assign `profile`", because the two
    spellings had to be kept in step. With one spelling left, *reading* it is
    the bug — a reader would be consulting a key nothing maintains.
    """
    import pathlib
    import re

    src = pathlib.Path(features.__file__).resolve().parent
    touches = re.compile(r"""\[\s*['"]profile['"]\s*\]|"""
                         r"""\.get\(\s*['"]profile['"]""")
    offenders = []
    for path in src.rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if touches.search(code) and "pop(" not in code:
                offenders.append(f"{path.relative_to(src)}:{n}: {line.strip()}")

    assert not offenders, (
        "`profile` is a dead key — nothing maintains it, so nothing may consult "
        "it. Use features.feature_enabled('tasks'):\n  " + "\n  ".join(offenders))


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


# --------------------------------------------------------------------------
# the two setup flags, which are now one spelling of one fact
# --------------------------------------------------------------------------

@pytest.fixture
def quiet_setup(config_home, monkeypatch):
    """`magi setup` with every side effect on the machine stubbed out."""
    import magi.setup_cmd as setup

    monkeypatch.setattr(setup, "_which", lambda name: None)
    monkeypatch.setattr(setup, "agent_cli_rows", lambda _ws=None: [])
    monkeypatch.setattr(setup, "wanted_optionals", lambda: {})
    return setup


NO_SIDE_EFFECTS = ["--yes", "--no-beads", "--no-models", "--no-plugin", "--no-skills"]


def test_setup_full_actually_turns_task_tracking_back_on(quiet_setup, config_home):
    """It used to print "profile set to full" and change nothing.

    `--full` wrote `profile` alone, but `feature_enabled` only lets
    `profile: kb-only` *veto* — so once the newer `optional_features["tasks"]`
    key held False, flipping the profile could not undo it. The command
    reported success and task tracking stayed off, with no way to tell from
    the output. Two representations of one fact, drifting exactly where D2
    said they would.
    """
    features.set_feature("tasks", False)
    assert features.feature_enabled("tasks") is False

    quiet_setup.main(["--full"] + NO_SIDE_EFFECTS)

    assert features.feature_enabled("tasks") is True
    assert _settings(config_home)["optional_features"]["tasks"] is True
    assert "profile" not in _settings(config_home)


def test_setup_kb_only_turns_task_tracking_off(quiet_setup, config_home):
    features.set_feature("tasks", True)
    quiet_setup.main(["--kb-only"] + NO_SIDE_EFFECTS)

    assert features.feature_enabled("tasks") is False
    assert _settings(config_home)["optional_features"]["tasks"] is False
    assert "profile" not in _settings(config_home)


def test_the_two_profile_flags_round_trip(quiet_setup, config_home):
    """The property that matters: whichever you ran last is what you get."""
    for flag, want in (("--kb-only", False), ("--full", True),
                       ("--kb-only", False), ("--full", True)):
        quiet_setup.main([flag] + NO_SIDE_EFFECTS)
        assert features.feature_enabled("tasks") is want, flag


def test_passing_both_flags_keeps_the_safer_one(quiet_setup, config_home):
    """--kb-only won before this change and still does. Ambiguous input should
    not be the one case that turns something on."""
    quiet_setup.main(["--kb-only", "--full"] + NO_SIDE_EFFECTS)
    assert features.feature_enabled("tasks") is False


def test_the_radar_choice_survives_a_profile_flag(quiet_setup, config_home):
    features.set_feature("radar", False)
    quiet_setup.main(["--full"] + NO_SIDE_EFFECTS)
    assert features.feature_enabled("radar") is False


def test_only_one_module_writes_the_legacy_profile_key():
    """The drift D2 predicted, made structurally hard to repeat.

    `profile` and `optional_features["tasks"]` are two spellings of one fact,
    kept in step by `set_feature`. That works exactly as long as `set_feature`
    is the only writer — and it stopped being true the moment `magi setup
    --full` assigned `profile` on its own, which is how a command came to
    report success and change nothing.

    Reading is fine anywhere; this only looks for assignment.
    """
    import pathlib
    import re

    src = pathlib.Path(features.__file__).resolve().parent
    writes = re.compile(r"""\[\s*['"]profile['"]\s*\]\s*=""")
    offenders = []
    for path in src.rglob("*.py"):
        if path.name == "features.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if writes.search(line):
                offenders.append(f"{path.relative_to(src)}:{n}: {line.strip()}")

    assert not offenders, (
        "these assign `profile` directly instead of calling "
        "features.set_feature('tasks', ...), so the two representations can "
        "disagree again:\n  " + "\n  ".join(offenders))
