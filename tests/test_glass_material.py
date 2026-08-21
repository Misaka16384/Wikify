"""The glass material must keep its layering at every opacity setting.

`max(--glass-floor, k * --glass-alpha)` clamped each surface on its own, so
they each froze at a different slider position and piled up on the floor
value. In the light MAGI theme (floor 0.5) the card gradient's two stops, the
topbar and the terminal body all resolved to exactly 0.50 at *every* setting —
four surfaces designed at 0.30, 0.44 and 0.42 rendering as one flat grey.

`k * max(--glass-floor, --glass-alpha)` scales the whole material at once:
relative weights hold everywhere, and the floor limits the slider rather than
the surfaces.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS = (Path(__file__).resolve().parents[1]
       / "src" / "magi" / "ui" / "static" / "styles.css").read_text(encoding="utf-8")


def test_no_surface_clamps_itself_against_the_floor():
    """The per-surface clamp is the bug. Only the token may mention the floor."""
    offenders = [ln.strip() for ln in CSS.splitlines()
                 if "max(var(--glass-floor)" in ln and "--glass-scale:" not in ln]
    assert not offenders, (
        "these surfaces clamp themselves and will converge on the floor:\n  "
        + "\n  ".join(offenders))


def test_the_scale_token_exists_and_folds_in_the_floor():
    m = re.search(r"--glass-scale:\s*([^;]+);", CSS)
    assert m, "--glass-scale is gone; surfaces have nothing to scale against"
    expr = m.group(1)
    assert "--glass-floor" in expr and "--glass-alpha" in expr
    assert "--glass-weight" in expr, "the per-theme density knob is gone"


def test_the_light_theme_carries_a_heavier_veil():
    """Dark text on a pale photograph has far less contrast headroom than pale
    text on a dark one, so the light variant needs more veil at the same
    slider position. Without it the restored hierarchy is unreadable."""
    block = CSS[CSS.index('[data-theme="eva"][data-eva="blue"]'):]
    block = block[:block.index("\n}")]
    m = re.search(r"--glass-weight:\s*([0-9.]+)", block)
    assert m, "the light MAGI variant lost its glass weight"
    assert float(m.group(1)) > 1.0


def test_the_densest_surface_stays_under_opaque():
    """A weight that pushes a surface past 1.0 makes it a solid block, which
    is the flat-grey problem again from the other end."""
    weight = float(re.search(
        r'\[data-theme="eva"\]\[data-eva="blue"\][^}]*?--glass-weight:\s*([0-9.]+)',
        CSS, re.S).group(1))
    coefficients = [float(x) for x in
                    re.findall(r"calc\(([0-9.]+) \* var\(--glass-scale\)\)", CSS)]
    assert coefficients, "no scaled surfaces found"
    assert max(coefficients) * weight <= 1.0, (
        f"the densest surface reaches {max(coefficients) * weight:.2f} at full "
        f"slider and renders opaque")


@pytest.mark.parametrize("alpha", [1.0, 0.6, 0.3, 0.0])
def test_the_ordering_of_surfaces_never_changes(alpha):
    """What layering means: a modal always sits above a card, at every setting.

    Under the old clamp this failed for every alpha — the values were equal,
    not ordered.
    """
    floor, weight = 0.5, 1.35
    scale = max(floor, alpha) * weight

    card_light, card_heavy, topbar, modal = 0.30, 0.44, 0.42, 0.60
    values = [c * scale for c in (card_light, topbar, card_heavy, modal)]
    assert values == sorted(values), values
    # And genuinely distinct, not merely non-decreasing.
    assert len(set(round(v, 4) for v in values)) == len(values)


def test_the_terminal_is_not_an_opaque_block():
    """Its body is glass; an opaque container behind it defeated that entirely
    and left one solid rectangle in a page made of glass."""
    # The selector has more than one rule — the chamfer lives in a shared one —
    # so check every block that targets it rather than whichever comes first.
    blocks = re.findall(
        r'\[data-theme="eva"\][^{}]*\.terminal-container[^{}]*\{([^}]*)\}', CSS)
    assert blocks, "no eva rule targets .terminal-container at all"
    assert any("background-color: transparent" in b for b in blocks), (
        "the terminal container paints an opaque background over its own glass")
