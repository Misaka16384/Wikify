"""A setting the WebUI lets you change has to be visible in the file too.

`radar.min_relevance` was editable in the dashboard's config card and appeared
in neither the shipped `config.yaml` nor the workspace template `magi init`
writes. So the knob existed, changing it worked, and a reader opening the file
to see what the radar was configured to do found no trace of it — the two
places people look for configuration disagreed about which configuration
there is.

The template is where someone learns what can be tuned. If a field is worth a
form control, it is worth a line there, even when the line is the field name
and a comment saying what leaving it empty means.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _config_fields_block() -> str:
    """The source text of the CONFIG_FIELDS whitelist."""
    api = (ROOT / "src" / "magi" / "ui" / "api.py").read_text(
        encoding="utf-8", errors="replace")
    return api.split("CONFIG_FIELDS: Dict[str, dict] = {", 1)[1].split("\n    }", 1)[0]


def _editable_keys() -> set:
    """The dotted keys `POST /api/workspace/config` accepts."""
    return set(re.findall(r'"([\w.]+)":\s*\{', _config_fields_block()))


def _shipped_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def _workspace_template() -> dict:
    """The config.yaml `magi init` scaffolds, parsed."""
    src = (ROOT / "src" / "magi" / "init_workspace.py").read_text(
        encoding="utf-8", errors="replace")
    body = src.split('config_yaml = """', 1)[1].split('"""', 1)[0]
    return yaml.safe_load(body)


def _has(tree, dotted: str) -> bool:
    cur = tree
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True


def _secret_keys() -> set:
    """Which editable fields are secrets, asked rather than restated.

    Secrets are deliberately absent from the config files — an explicit "" is
    a value, and it shadows a token the user set once in the user-level file,
    leaving every new workspace unable to reach the service for no visible
    reason. Both templates say so in a comment where the key would have been.

    Hand-listing them here would be a fourth copy of the same fact, and the
    first new secret added would be checked against the wrong rule.
    """
    return set(re.findall(r'"([\w.]+)":\s*\{"type":\s*"secret"\}',
                          _config_fields_block()))


EDITABLE = sorted(_editable_keys())
SECRET_KEYS = _secret_keys()


def test_there_are_editable_fields_to_check():
    assert len(EDITABLE) >= 10, EDITABLE


@pytest.mark.parametrize("key", EDITABLE)
def test_an_editable_field_appears_in_the_shipped_config(key):
    if key in SECRET_KEYS:
        return
    assert _has(_shipped_config(), key), (
        f"{key} is editable in the WebUI but absent from config.yaml, so a "
        f"reader opening the file cannot tell the setting exists")


@pytest.mark.parametrize("key", [k for k in EDITABLE
                                 if k.startswith("radar.") and k not in SECRET_KEYS])
def test_a_radar_field_appears_in_the_workspace_template(key):
    """Radar config is per-topic — that is the whole point of it being in the
    workspace file — so a new workspace should show every radar knob it has.

    Secrets are the exception, for the reason the next test states."""
    assert _has(_workspace_template(), key), (
        f"{key} is editable in the WebUI but `magi init` does not scaffold it")


def test_a_secret_is_deliberately_absent_from_the_workspace_template():
    """Not an oversight: an explicit empty value here overrides the user-level
    token key by key, so every new workspace would silently lose it."""
    template = _workspace_template()
    for key in SECRET_KEYS:
        assert not _has(template, key), (
            f"{key} is set in the workspace template; an explicit value there "
            f"shadows the one in ~/.config/magi/config.yaml")


# --------------------------------------------------------------------------
# and the values in it are the values the code uses
# --------------------------------------------------------------------------

def test_the_shipped_numbers_are_the_ones_the_constants_argue_for():
    """The template shipped `wip_limit: 3` and `stall_days: 14` while
    `state.WIP_LIMIT` was 7 and `state.STALL_DAYS` 21 — so a new workspace
    nagged at a different point from a pre-v2 one with no `research:` block,
    and a reader could see the docstring arguing for seven next to a file
    saying three."""
    from magi import state
    from magi.init_workspace import main  # noqa: F401 — imported for the module

    import magi.init_workspace as init

    source = Path(init.__file__).read_text(encoding="utf-8")
    assert f"wip_limit: {state.WIP_LIMIT}" in source
    assert f"stall_days: {state.STALL_DAYS}" in source


def test_every_whitelisted_field_type_has_a_validator():
    """`research.rules` and `research.hosts` were declared `list_of_maps` and
    the validation chain had no branch for it, so any shape was accepted and
    written. The UI reported success for a setting that never took effect."""
    import re

    block = _config_fields_block()
    declared = set(re.findall(r'"type":\s*"(\w+)"', block))

    api = Path(ROOT / "src" / "magi" / "ui" / "api.py").read_text(encoding="utf-8")
    body = api.split("def post_workspace_config", 1)[1].split("def ", 1)[0]
    handled = set(re.findall(r'ftype == "(\w+)"', body))

    # `choices` and `nullable` are checked ahead of the chain, and a bare
    # `str` field with choices is still a `str`.
    missing = declared - handled
    assert not missing, (
        f"CONFIG_FIELDS declares {sorted(missing)} with nothing that validates it")
