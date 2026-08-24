"""The dashboard's browser tab shows the MAGI mark, not a blank page icon.

Two things here are worth a test rather than a glance.

**Both files must actually ship.** They live under `src/magi/ui/static/`, which
is packaged by a glob — a new file type in there is exactly the kind of thing
that works from a checkout and is missing from the wheel.

**The artwork is deliberately not the header emblem.** That one draws three
1.3px lines between the cores; at sixteen pixels they are grey mush. The
favicon keeps the hexagon and the three cores and drops the rest, and its shell
is a single mid grey rather than a `prefers-color-scheme` pair — the
theme-aware version was rendered at a true 16px and disappeared against a white
tab strip whenever the browser reported a dark scheme, and a light browser
theme on a dark OS is an ordinary setup.
"""

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src" / "magi" / "ui" / "static"


def test_both_icon_files_exist():
    assert (STATIC / "favicon.svg").is_file()
    assert (STATIC / "favicon.png").is_file()


def test_the_page_links_the_svg_first_and_the_png_as_a_fallback():
    head = (STATIC / "index.html").read_text(encoding="utf-8")[:2000]
    svg = re.search(r'<link rel="icon"[^>]*href="/favicon\.svg"', head)
    png = re.search(r'<link rel="alternate icon"[^>]*href="/favicon\.png"', head)
    assert svg, "no SVG icon link"
    assert png, "no PNG fallback"
    assert head.index(svg.group(0)) < head.index(png.group(0)), \
        "the fallback is listed first"


def _svg_markup() -> str:
    """The file with its comments removed.

    The comment explains at length *why* there is no `prefers-color-scheme`
    rule, so a naive grep over the whole file finds the phrase it is checking
    for and fails. Strip the prose, check the markup.
    """
    svg = (STATIC / "favicon.svg").read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", svg, flags=re.DOTALL)


def test_the_shell_does_not_depend_on_the_browser_colour_scheme():
    """It vanished on a white tab strip. Looked at, at 16px, and rejected."""
    markup = _svg_markup()
    assert "prefers-color-scheme" not in markup
    assert "#6C767E" in markup


def test_the_connecting_lines_are_left_out():
    """They are the part that turns to mush when shrunk."""
    markup = _svg_markup()
    assert "<line" not in markup
    assert markup.count("<circle") == 3


def test_the_three_cores_keep_their_identities():
    """Melchior blue, Balthasar sage, Casper red — the same three the header
    mark and the core band use."""
    markup = _svg_markup()
    for colour in ("#3E7F88", "#67824E", "#AE4339"):
        assert colour in markup, colour


def test_the_png_is_a_real_32px_image():
    Image = pytest.importorskip("PIL.Image", reason="Pillow not installed")
    with Image.open(STATIC / "favicon.png") as img:
        assert img.size == (32, 32)
        assert img.mode == "RGBA", "a favicon needs a transparent ground"


def test_the_server_serves_both(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from magi.ui.api import create_app

    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path))
    client = TestClient(create_app())
    for name, kind in (("favicon.svg", "image/svg+xml"), ("favicon.png", "image/png")):
        res = client.get("/" + name)
        assert res.status_code == 200, name
        assert kind in res.headers["content-type"], name


def test_the_icons_are_packaged():
    """`static/*` in package-data covers them, and this is the test that says
    so — a checkout would pass every other test in this file regardless."""
    # Read as text rather than parsed: `tomllib` is 3.11+, and this project
    # still supports 3.10 — the pipx install on the author's machine runs it.
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    line = re.search(r'^"magi\.ui"\s*=\s*\[(.+)\]$', pyproject, re.MULTILINE)
    assert line, "no package-data entry for magi.ui"
    assert "static/" in line.group(1), line.group(1)
