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


def _tokens(selector: str) -> dict:
    block = CSS[CSS.index(selector):]
    block = block[:block.index("\n}")]
    return {k: float(v) for k, v in
            re.findall(r"--glass-(weight|brightness|saturate|floor):\s*([0-9.]+)", block)}


def test_only_the_lift_is_mirrored_between_the_variants():
    """Three numbers separate the light MAGI variant from the dark one. Exactly
    one of them was ever wrong, and each attempt to "make it symmetric" broke
    something visible. The history is the point of this test.

    **The lift — mirrored, and this was the whole bug.** Dark pulls luminance
    down to 0.8; light was lifting by 1.08, which is not enough for a panel to
    read as sitting *above* the picture rather than smeared over it. The mirror
    of 0.8 is 1/0.8. 1.7 was tried on the way and blew the photograph out.

    **The veil — not mirrored, and must not be.** Dark text over a photograph
    has far less headroom than pale text over the same photograph darkened: in
    a dark theme the veil and the text push the same way, in a light theme they
    push opposite ways. Setting the weights equal was tried; below full slider
    the panels stopped separating from the picture and the graph beneath them
    became unreadable. Raising it instead was tried too, to 1.95, and turned
    the glass into frosted plastic.

    **Saturation — not mirrored either.** It exists to replace the chroma a
    blur destroys, and this theme's blur is small (2px at the setting people
    use). Dark can carry 1.8 because it crushes everything toward black
    afterwards and the excess never shows; light lifts toward white, a white
    veil does not hide an over-saturated backdrop, and at a low slider the veil
    is thin — the photograph came through turquoise.
    """
    dark = _tokens('[data-theme="eva"] {')
    light = _tokens('[data-theme="eva"][data-eva="blue"] {')

    assert dark["brightness"] < 1.0, (
        f"dark must pull luminance down; it is {dark['brightness']}")
    assert 0.98 <= light["brightness"] <= 1.02, (
        f"light brightness is {light['brightness']} and must be neutral. "
        "brightness() is a multiply: on a pale backdrop the high channels clip "
        "at 255 before red does, and the panel comes out cyan. 1.25 was "
        "reported as 'obviously cyan'; the original 1.08 was the same fault in "
        "a smaller dose. The lift belongs to the white veil.")

    assert light["weight"] > dark["weight"], (
        "the light variant needs more veil than the dark one — dark text has "
        "less headroom over a photograph than pale text over a darkened one")

    assert 1.0 < light["saturate"] <= dark["saturate"], (
        f"light saturation is {light['saturate']} against dark's "
        f"{dark['saturate']}: it must restore some chroma, and it must not "
        "exceed dark's, because a white veil cannot hide the excess the way a "
        "near-black one does")


#: The only MAGI surfaces allowed a fixed alpha, and why. Everything else is
#: part of the material and moves with the slider.
FIXED_ALPHA_ALLOWED = {
    # Not a panel: the ground the glass sits on. Thinning it with the slider
    # would just uncover more photograph everywhere at once.
    ".app-bg-shade",
    # Not a panel either: the scrim that has to dim the page behind a modal
    # whatever the glass is set to.
    ".modal-backdrop",
    # The control you move the slider with. If it tracked the slider, dragging
    # opacity to zero would make it disappear out from under the cursor.
    ".glass-tuner-btn",
    ".glass-tuner-panel",
}


def test_every_magi_surface_tracks_the_slider():
    """A surface pinned at a fixed alpha is invisible as a bug in the dark
    variant and obvious in the light one.

    `rgba(5, 6, 8, 0.96)` over a near-black panel *is* the panel, so the sticky
    table header looked correct for as long as anyone only used MAGI dark. The
    identical rule in the light variant is `rgba(244, 248, 252, 0.96)` over
    glass: a solid bright band across a translucent card, and it stays solid
    while everything around it thins out. Reported as "these header bars have
    no transparency at all, very jarring", and there were ten of them.
    """
    offenders = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS):
        sel = m.group(1).strip().splitlines()[-1].strip()
        if '[data-theme="eva"]' not in sel:
            continue
        if any(a in sel for a in FIXED_ALPHA_ALLOWED):
            continue
        for b in re.finditer(r"background(?:-color)?\s*:\s*([^;]+);", m.group(2)):
            for a in re.findall(
                    r"rgba\(var\(--eva-bg-rgb\),\s*([0-9.]+)\s*\)", b.group(1)):
                line = CSS[:m.start(2)].count("\n") + 1
                offenders.append(f"styles.css:{line} {sel[:44]} alpha={a}")
    assert not offenders, (
        "MAGI surfaces pinned at a fixed alpha — they will read as solid "
        "blocks inside glass at any slider setting below full:\n  "
        + "\n  ".join(offenders))


def test_shadow_is_a_theme_token_not_a_literal():
    """Eight rules in MAGI cast near-black at 0.4 to 0.95 and none was mirrored
    for the light variant. On a pale ground that is a smudge, not depth — and
    `.card:hover` stepping 0.5 -> 0.75 is why hovering a panel visibly
    *darkened* it, which took three passes to find because the search kept
    going to background fills instead.

    They go through --eva-shadow-rgb / --eva-shadow-strength now, so a new one
    written as a literal is a new unmirrored device.
    """
    offenders = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS):
        sel = m.group(1).strip().splitlines()[-1].strip()
        if '[data-theme="eva"]' not in sel or sel.endswith(('{', '"eva"]')):
            continue
        for d in re.finditer(
                r"(?:box-shadow|filter|text-shadow)\s*:\s*([^;]+);", m.group(2)):
            for a in re.findall(r"rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*([0-9.]+)\)",
                                d.group(1)):
                if float(a) >= 0.4:
                    line = CSS[:m.start(2)].count("\n") + 1
                    offenders.append(f"styles.css:{line} {sel[:46]} a={a}")
    assert not offenders, (
        "near-black shadows hard-coded in MAGI, invisible in dark and a smudge "
        "in light:\n  " + "\n  ".join(offenders))


def test_the_densest_surface_stays_under_opaque():
    """A weight that pushes a surface past 1.0 makes it a solid block, which
    is the flat-grey problem again from the other end.

    Briefly replaced by a laxer rule to allow a weight of 1.95 in the light
    variant. That weight was the wrong answer to "the panels look like grey
    film" — the answer was to mirror dark's parameters instead of inflating
    the veil — so the ceiling is back and unchanged.
    """
    weight = float(re.search(
        r'\[data-theme="eva"\]\[data-eva="blue"\][^}]*?--glass-weight:\s*([0-9.]+)',
        CSS, re.S).group(1))
    coefficients = [float(x) for x in
                    re.findall(r"calc\(([0-9.]+) \* var\(--glass-scale\)\)", CSS)]
    assert coefficients, "no scaled surfaces found"
    assert max(coefficients) * weight <= 1.0, (
        f"the densest surface reaches {max(coefficients) * weight:.2f} at full "
        f"slider and renders opaque")


def test_magi_hover_is_never_an_opaque_fill():
    """Every surface in MAGI mode is glass, so a hover has to be a tint *in*
    the material. An opaque colour on glass is a hole cut in it — and in the
    light variant it is also darker than the plate it lands on, which is what
    "hovering still darkens it" was. Five rules had no MAGI override and
    inherited `--bg-hover` or `--bg-surface`, both opaque.
    """
    block = CSS[CSS.index('[data-theme="eva"]'):]
    offenders = []
    for rule in re.finditer(
            r'(\[data-theme="eva"\][^{}]*:hover[^{}]*)\{([^}]*)\}', block, re.S):
        sel, body = rule.group(1).strip(), rule.group(2)
        m = re.search(r"background(?:-color)?\s*:\s*([^;]+);", body)
        if not m:
            continue
        value = m.group(1).strip()
        if value in ("none", "transparent") or value.startswith("linear-gradient"):
            continue
        if "rgba(" in value or "color-mix(" in value:
            continue
        offenders.append(f"{sel.splitlines()[-1].strip()} -> {value}")
    assert not offenders, (
        "opaque hover fills on glass:\n  " + "\n  ".join(offenders))


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
