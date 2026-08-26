"""Where an operation's button appears, and how many times.

The frontend used to render every non-danger op into one grid on the
Operations tab, minus a blacklist of two op ids written directly into
`app.js` — which is exactly the "frontend holds zero op-specific knowledge"
rule the ops catalog exists to keep, broken in the file that keeps it.

What that produced was a panel organised around "everything not excluded":
seven of its buttons already had a home on the tab they belong to,
`install-tasks` and `pull-models` appeared twice on the same screen, and what
remained was three separate index-rebuilding commands with names close enough
that nobody could tell them apart.

Placement is now a `home` field on the catalog entry, so these tests are about
that field being honoured and remaining honest.
"""

import re
from pathlib import Path

import pytest

from magi.ui.jobs import OPS

STATIC = Path(__file__).resolve().parents[1] / "src" / "magi" / "ui" / "static"
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8", errors="replace")
INDEX_HTML = (STATIC / "index.html").read_text(encoding="utf-8", errors="replace")


def _mounts() -> dict:
    """The home -> element-id table the frontend dispatches on."""
    block = APP_JS.split("const OPS_MOUNTS = {", 1)[1].split("};", 1)[0]
    return dict(re.findall(r"(\w+):\s*\"([\w-]+)\"", block))


# --------------------------------------------------------------------------
# every op is placed, deliberately
# --------------------------------------------------------------------------

@pytest.mark.parametrize("op", sorted(OPS))
def test_every_op_says_where_it_belongs(op):
    """`home` is required, including when the answer is None. Absent would
    mean "nobody decided", and the whole defect was a default that decided
    for you."""
    assert "home" in OPS[op], f"{op} does not declare a home"


@pytest.mark.parametrize("op", sorted(OPS))
def test_a_home_is_a_panel_the_frontend_can_render_into(op):
    home = OPS[op]["home"]
    if home is None:
        return
    assert home in _mounts(), f"{op} claims home {home!r}, which has no mount"


@pytest.mark.parametrize("home,element", sorted(_mounts().items()))
def test_every_mount_exists_in_the_page(home, element):
    assert f'id="{element}"' in INDEX_HTML, f"{home} mounts into a missing element"


def test_danger_ops_go_to_the_danger_zone():
    for op, spec in OPS.items():
        if spec["danger"]:
            assert spec["home"] == "danger", f"{op} is danger but homed at {spec['home']!r}"
        else:
            assert spec["home"] != "danger", f"{op} is not danger but sits in the Danger Zone"


# --------------------------------------------------------------------------
# the defect itself
# --------------------------------------------------------------------------

def test_the_frontend_names_no_operation():
    """The blacklist was `if (entry.op === "radar-harvest" || ...) return;`.
    Any op id appearing in the renderer is the same mistake returning."""
    start = APP_JS.index("function renderOpsPanels()")
    end = APP_JS.index("function openDangerConfirm(")
    renderer = APP_JS[start:end]
    named = sorted(op for op in OPS if f'"{op}"' in renderer)
    assert not named, f"renderOpsPanels() hardcodes op ids: {named}"


def test_the_operations_tab_no_longer_collects_everything():
    """It kept the ops that had nowhere else to be. Every one of them now has
    somewhere, so the grid is gone rather than sitting there nearly empty."""
    assert 'id="ops-common-grid"' not in INDEX_HTML
    assert "ops_common_title" not in APP_JS


@pytest.mark.parametrize("op", ["ingest-batch-run", "ingest-batch-commit",
                                "backlog-sync", "pm-init", "radar-harvest",
                                "radar-citation-gap", "install-tasks",
                                "pull-models"])
def test_an_op_with_its_own_control_gets_no_generic_twin(op):
    """These eight already have a purpose-built button on their own tab. A
    generic catalog button beside it is the duplication this all started as —
    two of them were duplicated within the Operations tab itself."""
    assert OPS[op]["home"] is None, (
        f"{op} has a bespoke control already; a generic button duplicates it")


def test_the_index_rebuilders_are_not_all_in_one_place():
    """`magi index`, `magi graph build` and `magi wiki reindex` write three
    different artefacts at three very different costs. Sitting in one grid
    under three near-identical names is what made them indistinguishable."""
    homes = {op: OPS[op]["home"] for op in ("index", "graph-build", "wiki-reindex")}
    assert homes["index"] != homes["graph-build"], homes
    assert all(h is not None for h in homes.values()), homes


def test_scheduling_lives_with_the_feature_it_schedules():
    assert OPS["radar-install-schedule"]["home"] == "radar"
