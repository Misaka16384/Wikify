"""What the project declares, CI installs.

`tests.yml`'s header has argued this in prose since the `pandoc`/`bd` decision:
"A skip that only ever fires in CI means the two sides are not running the same
suite: 21 tests ran on the author's machine and would never have run here."

`textlayer` violated it for its whole life. It was declared in `pyproject.toml`,
installed by neither workflow, and the ten tests that need it — including the
only coverage of the free conversion route a plain `pip install` sends prose
PDFs down — ran nowhere but one laptop. The route was broken there the entire
time: `_run_route` checked `verdict.ok`, ignored `verdict.available` and
imported anyway.

So the paragraph becomes a check. The property is "every declared extra is
installed wherever the suite runs" — no import-name-to-package map to keep,
and nothing to edit when an extra is added. Leaving one out is possible; it
just has to be said out loud in `_DELIBERATELY_NOT_IN_CI`, with why.
"""

from __future__ import annotations

import re
from importlib.metadata import metadata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Extras deliberately left out of a workflow, and why. Empty on purpose: an
#: extra that CI does not install is a suite that differs between two machines,
#: and that is a decision, not an oversight.
_DELIBERATELY_NOT_IN_CI: dict[str, str] = {}

#: Workflows that run the suite. `release.yml` runs it again before publishing,
#: so it has to install the same things or the tag is gated by a weaker check
#: than the branch was.
_WORKFLOWS = ("tests.yml", "release.yml")

_INSTALL_RE = re.compile(r'uv pip install -e "\.\[([^\]]*)\]"')


def _declared_extras() -> set[str]:
    """Asked of the built distribution, not of `pyproject.toml`.

    `tomllib` is stdlib only from 3.11 and CI pins the floor, 3.10 — reading
    the source file here took the whole collection down on the one interpreter
    that matters. `Provides-Extra` is the same declaration after the build, on
    every version the project claims to support.
    """
    declared = metadata("magi-research").get_all("Provides-Extra")
    assert declared, "magi-research is not installed; extras cannot be read"
    return set(declared)


def _installed_extras(workflow: str) -> set[str]:
    text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    found = _INSTALL_RE.search(text)
    assert found, f"{workflow} does not install the package the usual way"
    return {name.strip() for name in found.group(1).split(",") if name.strip()}


@pytest.mark.parametrize("workflow", _WORKFLOWS)
def test_every_declared_extra_is_installed_where_the_suite_runs(workflow):
    missing = _declared_extras() - _installed_extras(workflow)
    unexplained = missing - set(_DELIBERATELY_NOT_IN_CI)
    assert not unexplained, (
        f"{workflow} does not install {sorted(unexplained)}; every test that "
        "needs them skips there and runs only on a developer's machine")


def test_no_extra_is_excused_that_is_already_installed():
    """The ledger from its own side: an excuse that outlived what it excused is
    how a check quietly stops covering anything."""
    for extra, why in _DELIBERATELY_NOT_IN_CI.items():
        assert extra in _declared_extras(), f"{extra} is no longer declared"
        assert why.strip(), f"{extra} is excused without a reason"
        assert any(extra not in _installed_extras(w) for w in _WORKFLOWS), (
            f"{extra} is installed everywhere now — drop the excuse")


def test_the_suite_is_invoked_the_same_way_ci_invokes_it():
    """`pytest tests` and `python -m pytest tests` are not the same command:
    the second puts the working directory on `sys.path`. A release once failed
    here after a full green suite locally, because only CI's spelling reaches
    the import that was actually broken."""
    for workflow in _WORKFLOWS:
        text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
        assert "uv run pytest tests" in text, workflow
        assert "python -m pytest" not in text, workflow
