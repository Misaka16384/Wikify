"""app.js must survive being loaded, not merely parsed.

`node --check` proves the file is syntactically valid. It does not prove it
runs, and the gap between those is where the worst class of bug in this file
lives: a call to a helper that does not exist is valid syntax, passes every
Python test in this suite (none of which execute JavaScript), and leaves the
entire dashboard frozen on "Loading…" with one ReferenceError in a console
nobody has open.

That has now happened twice in this file — once as two functions that called
themselves into a stack overflow, and once as `on(el, "click", …)` in a codebase
whose only event-binding idiom is addEventListener. Both shipped past
`node --check`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).with_name("app_js_smoke.js")
APP = (Path(__file__).resolve().parents[1]
       / "src" / "magi" / "ui" / "static" / "app.js")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_app_js_runs_without_throwing():
    result = subprocess.run(["node", str(HARNESS)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, (
        "app.js throws while loading — the dashboard would be dead:\n"
        + (result.stderr or result.stdout)
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_harness_actually_catches_an_undefined_helper(tmp_path):
    """A guard nobody has seen fail is not a guard.

    Inject the exact bug that got past `node --check` and reached the browser,
    and assert the harness refuses it.
    """
    broken = APP.read_text(encoding="utf-8").replace(
        "  const ingestRunBtn =",
        '  on(document.getElementById("x"), "click", () => {});\n  const ingestRunBtn =',
        1)
    assert "on(document.getElementById" in broken, "injection point moved"

    sabotaged = tmp_path / "app.js"
    sabotaged.write_text(broken, encoding="utf-8")
    harness = tmp_path / "smoke.js"
    harness.write_text(
        HARNESS.read_text(encoding="utf-8").replace(
            'path.join(__dirname, "..", "src", "magi", "ui", "static", "app.js")',
            f'{str(sabotaged)!r}'.replace("\\", "\\\\")),
        encoding="utf-8")

    # node --check would pass this file; that is the whole point.
    assert subprocess.run(["node", "--check", str(sabotaged)],
                          capture_output=True).returncode == 0

    result = subprocess.run(["node", str(harness)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode != 0
    assert "is not defined" in (result.stderr + result.stdout)
