"""Settings layer: user file underneath, workspace file on top.

Before this, `find_config_yaml` returned the *first* config it found walking
up and the user file was only a fallback — and since every `magi init`
workspace writes a config.yaml at its root, the user file was never reached by
anyone who had a workspace, which is everyone. Anything belonging to the person
rather than the topic had to be copied into each one: measured on a real
machine, the same MinerU token stored three times with no single place to
change it.
"""

import textwrap

import pytest

from magi.core.config_loader import get, load_config


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """An isolated config home, plus a workspace to load from."""
    cfg_home = tmp_path / "cfghome"
    cfg_home.mkdir()
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(cfg_home))

    ws = tmp_path / "topic"
    (ws / "wiki").mkdir(parents=True)
    (ws / "raw").mkdir()
    return cfg_home, ws


def _write(path, text):
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def test_the_user_file_is_read_even_though_a_workspace_config_exists(home):
    cfg_home, ws = home
    _write(cfg_home / "config.yaml", """
        ocr:
          mineru_api_token: "user-level-token"
    """)
    _write(ws / "config.yaml", """
        models:
          ocr: "glm-ocr:q8_0"
    """)
    cfg = load_config(start=ws)
    assert get(cfg, "ocr.mineru_api_token") == "user-level-token"
    assert get(cfg, "models.ocr") == "glm-ocr:q8_0"


def test_the_workspace_wins_where_the_two_disagree(home):
    cfg_home, ws = home
    _write(cfg_home / "config.yaml", 'models:\n  ocr: "from-user"\n')
    _write(ws / "config.yaml", 'models:\n  ocr: "from-workspace"\n')
    assert get(load_config(start=ws), "models.ocr") == "from-workspace"


def test_merging_is_per_key_not_per_section(home):
    """The whole point. A workspace naming one model must not drop a token
    from the same section of the user file."""
    cfg_home, ws = home
    _write(cfg_home / "config.yaml", """
        ocr:
          mineru_api_token: "tok"
          timeout: 999
    """)
    _write(ws / "config.yaml", 'ocr:\n  timeout: 30\n')
    cfg = load_config(start=ws)
    assert get(cfg, "ocr.timeout") == 30
    assert get(cfg, "ocr.mineru_api_token") == "tok"


def test_an_explicit_empty_value_shadows_the_layer_below(home):
    """This is not a bug, and it bit during the migration.

    "" is a value, not an absence, so a workspace saying `mineru_api_token: ""`
    genuinely means "no token here" and overrides the user's. It is why the
    `magi init` template leaves the key commented out rather than empty — an
    empty default would have shadowed the user-level token in every new
    workspace, silently.
    """
    cfg_home, ws = home
    _write(cfg_home / "config.yaml", 'ocr:\n  mineru_api_token: "tok"\n')
    _write(ws / "config.yaml", 'ocr:\n  mineru_api_token: ""\n')
    assert get(load_config(start=ws), "ocr.mineru_api_token") == ""


def test_the_key_being_absent_inherits(home):
    cfg_home, ws = home
    _write(cfg_home / "config.yaml", 'ocr:\n  mineru_api_token: "tok"\n')
    _write(ws / "config.yaml", 'ocr:\n  use_mineru: true\n')
    assert get(load_config(start=ws), "ocr.mineru_api_token") == "tok"


def test_the_init_template_does_not_ship_a_shadowing_empty_token():
    """Guards the fix at its source: every workspace `magi init` creates would
    otherwise override a token the user set once."""
    from magi.hub import init_workspace

    import inspect

    src = inspect.getsource(init_workspace)
    body = src[src.index("ocr:"):src.index("semantic_link:")]
    live = [l for l in body.split("\n") if l.strip() and not l.strip().startswith("#")]
    assert not any("mineru_api_token" in l for l in live), (
        "the template sets mineru_api_token; an explicit value shadows the "
        "user-level one in every new workspace")


def test_no_user_file_is_not_an_error(home):
    cfg_home, ws = home
    _write(ws / "config.yaml", 'models:\n  ocr: "only-here"\n')
    assert get(load_config(start=ws), "models.ocr") == "only-here"


def test_the_config_home_override_is_honoured_by_both_readers(home):
    """`find_config_yaml` hardcoded ~/.config/magi while the registry honoured
    MAGI_CONFIG_HOME, so an isolated test still read real settings."""
    cfg_home, _ = home
    from magi.core import workspace
    from magi import kb_registry

    assert workspace.config_home() == cfg_home
    assert kb_registry.registry_path().parent == cfg_home
