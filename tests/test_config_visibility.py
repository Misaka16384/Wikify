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


def _editable_keys() -> set:
    """The dotted keys `POST /api/workspace/config` accepts."""
    api = (ROOT / "src" / "magi" / "ui" / "api.py").read_text(
        encoding="utf-8", errors="replace")
    block = api.split("CONFIG_FIELDS: Dict[str, dict] = {", 1)[1].split("\n    }", 1)[0]
    return set(re.findall(r'"([\w.]+)":\s*\{', block))


def _shipped_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def _workspace_template() -> dict:
    """The config.yaml `magi init` scaffolds, parsed."""
    src = (ROOT / "src" / "magi" / "hub" / "init_workspace.py").read_text(
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


EDITABLE = sorted(_editable_keys())

#: Secrets are deliberately absent from the workspace template — an explicit
#: "" there shadows a token the user set once in the user-level file and leaves
#: every new workspace unable to reach the service for no visible reason. The
#: template says so in a comment where the key would have been.
SECRET_KEYS = {"ocr.mineru_api_token", "embedding.api_key"}


def test_there_are_editable_fields_to_check():
    assert len(EDITABLE) >= 10, EDITABLE


@pytest.mark.parametrize("key", EDITABLE)
def test_an_editable_field_appears_in_the_shipped_config(key):
    if key in SECRET_KEYS:
        return
    assert _has(_shipped_config(), key), (
        f"{key} is editable in the WebUI but absent from config.yaml, so a "
        f"reader opening the file cannot tell the setting exists")


@pytest.mark.parametrize("key", [k for k in EDITABLE if k.startswith("radar.")])
def test_a_radar_field_appears_in_the_workspace_template(key):
    """Radar config is per-topic — that is the whole point of it being in the
    workspace file — so a new workspace should show every radar knob it has."""
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
