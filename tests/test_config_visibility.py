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


# --------------------------------------------------------------------------
# and it has to be readable once you find it
# --------------------------------------------------------------------------

APP_JS = ROOT / "src" / "magi" / "ui" / "static" / "app.js"


def _label_keys() -> dict:
    """`CONFIG_FIELDS` key -> i18n key, out of `CFG_LABEL_KEYS` in app.js."""
    js = APP_JS.read_text(encoding="utf-8", errors="replace")
    start = js.index("const CFG_LABEL_KEYS = {")
    block = js[start:js.index("}", start)]
    return dict(re.findall(r'"([\w.]+)":\s*"([\w.]+)"', block))


def _i18n_keys(lang: str) -> set:
    """Every key defined under one language in app.js's I18N table."""
    js = APP_JS.read_text(encoding="utf-8", errors="replace")
    start = js.index(f"    {lang}: {{")
    end = js.index("\n    },", start)
    return set(re.findall(r"^\s{6}(\w+):", js[start:end], re.MULTILINE))


def test_every_editable_field_says_what_it_is():
    """A field whose description is its own dotted key name is not configured
    in the WebUI in any sense a person would recognise.

    design-v2 §13 puts the weekly budget, the per-work model and the master
    switch in the WebUI. All three, and the whole `research.*` group v2 added
    with them, rendered as `research.weekly_calls` described as
    "research.weekly_calls" — because `CFG_LABEL_KEYS` had no entry and the
    lookup falls back to the key itself.
    """
    fields = set(re.findall(r'"([\w.]+)":\s*\{"type"', _config_fields_block()))
    labelled = _label_keys()

    missing = sorted(key for key in fields if key not in labelled)

    assert not missing, (
        f"these render their own key name as their description: {missing}")


def test_every_description_exists_in_both_languages():
    """An entry pointing at a key no language defines falls back to the key
    too, which is the same failure with an extra step."""
    used = set(_label_keys().values())
    for lang in ("zh", "en"):
        missing = sorted(key for key in used if key not in _i18n_keys(lang))
        assert not missing, f"{lang} has no text for: {missing}"


def test_the_kb_table_shows_which_workspaces_are_gone():
    """`/api/kb` has always returned `exists` per row and the renderer never
    read it, so a directory deleted months ago drew exactly like a real
    workspace that merely has no index yet — in the one table that answers
    "what is on this machine"."""
    api = (ROOT / "src" / "magi" / "ui" / "api.py").read_text(encoding="utf-8")
    assert '"exists": p.is_dir()' in api, "the backend stopped computing it"

    js = APP_JS.read_text(encoding="utf-8", errors="replace")
    start = js.index("function renderKBTable(")
    body = js[start:start + 3000]

    # Two distinct uses, and the test names both because they are two
    # different promises: the row says so, and the table can put them away.
    # A source-level check is the ceiling here — app.js is an IIFE and the
    # smoke harness only proves it loads — so what is pinned is that both
    # still read `exists` and that the badge is still rendered from it.
    assert body.count("kb.exists === false") >= 2, (
        "the row rendering or the filter stopped reading `exists`")
    assert "badge_kb_gone" in body, "the row no longer marks a dead workspace"
    assert "kb_hide_gone" in body, "there is no way to put the dead rows away"


def test_the_server_decides_which_workspace_opens():
    """`magi ui` run inside a workspace reports that directory as
    `active_workspace`, and that is a deliberate act — somebody stood in a
    workspace and started a server there. A path remembered in this browser
    from a previous session used to win anyway, so from the second workspace
    onward the dashboard opened on the wrong one, showing notes the person had
    never written."""
    js = APP_JS.read_text(encoding="utf-8", errors="replace")
    start = js.index("const savedView = viewWorkspaceGet();")
    guard = js[start:start + 260]

    assert "!state.serverWorkspace" in guard, (
        "the remembered workspace overrides the one the server was started in")


def test_the_week_s_spending_is_shown_where_it_is_configured():
    """design-v2 §13 asks for the weekly budget to be configured in the WebUI
    and explained when it runs out. It was configurable there and never
    displayed, so the one number the configuration governs could only be read
    by opening `MAP.md` or the ledger by hand."""
    js = APP_JS.read_text(encoding="utf-8", errors="replace")

    assert "function renderSpending(" in js, "nothing draws the week's spend"
    assert "renderSpending(data.budget" in js, "it is defined and never called"
    assert "dash_spending_line" in js, "the figure has no words around it"


def test_the_graph_empty_state_carries_its_own_button():
    """`graphMissingBox` puts a build button under "no knowledge graph yet"
    and the graph tab printed the same sentence as inert text — so which tab
    you were standing on decided whether the thing the sentence tells you to
    do was something you could do. The comment above `graphMissingBox` says
    this was fixed once; this was the third place."""
    js = APP_JS.read_text(encoding="utf-8", errors="replace")

    # The exact line, not a slice. Two earlier attempts at this test passed
    # with the fix removed: one anchored on the first `graphMapNote.textContent`
    # in the file, which is the unrelated "no d3" branch, and one took a slice
    # wide enough to contain `graphMissingBox`'s own definition.
    assert "els.graphMapNote.appendChild(graphMissingBox(" in js, (
        "the graph tab is back to printing the sentence with no way to act on it")


def test_a_job_that_stays_put_changes_something_where_you_clicked():
    """Clicking "Rebuild the concept graph" and staying on the tab left every
    visible thing saying exactly what it had said before, including the "no
    knowledge graph yet" line. The job had finished."""
    js = APP_JS.read_text(encoding="utf-8", errors="replace")
    start = js.index('if (state.activeTab === "radar") loadRadar();')
    after = js[start:start + 400]
    assert "loadGraphMap()" in after and "loadMelchior()" in after


def test_handing_the_directory_to_bd_is_announced_first():
    """`magi sync` offers `magi pm init` as its very first suggestion, and it
    hands the directory to another program that git-inits it and commits under
    the person's own identity. That was said afterwards, under bd's output, by
    which point the commit is in their history."""
    pm = (ROOT / "src" / "magi" / "pm.py").read_text(encoding="utf-8")
    start = pm.index("def _agreed_to_hand_over(")
    body = pm[start:start + 1800]

    assert "your own git identity" in body
    assert "isatty" in body, "it would hang an agent that cannot answer"

    # The call, not the definition — `def _agreed_to_hand_over(root: Path`
    # matches a looser search and sits above `_run_bd` either way, so the
    # first version of this test passed with the call deleted.
    called = pm.index('_agreed_to_hand_over(root, getattr')
    ran = pm.index('_run_bd(["init"')
    assert called < ran, "asked after handing it over"
