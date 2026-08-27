"""Regression tests for the liquid-glass material in the WebUI.

These pin the specific defects that made the first cut of the material render
flat, unreachable, or wrong. Each test names the symptom it guards, because a
token being *present* proved nothing -- the previous version of this file
asserted that three SVG filters existed while no element referenced any of them,
and that app.js contained the string "--mouse-x" while that very property was
the cause of the cross-card specular bug.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "magi" / "ui" / "static"
CSS = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
HTML = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
APP_JS = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

# Selector-level assertions run against this: the comments explain which
# constructs were removed and why, and naming them there must not read as the
# construct still being present.
CSS_RULES = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)

THEME_BLOCKS = {
    "light": ":root {",
    "dark": '[data-theme="dark"] {',
    "eva": '[data-theme="eva"] {',
    "eva-blue": '[data-theme="eva"][data-eva="blue"] {',
}


def _block(selector: str) -> str:
    idx = CSS.find(selector)
    assert idx != -1, f"theme selector {selector} not found"
    return CSS[idx : CSS.index("\n}", idx)]


def test_every_css_url_filter_reference_resolves():
    """No CSS may point at an SVG filter id that nothing defines.

    The first cut shipped #glass-refraction, #glass-chromatic-aberration and
    #glass-surface-dither in index.html plus three classes referencing them, and
    not one element in the app ever carried those classes. Dead either way --
    this catches both directions.
    """
    referenced = set(re.findall(r"filter:\s*url\(#([\w-]+)\)", CSS))
    defined = set(re.findall(r'<filter[^>]*\bid="([\w-]+)"', HTML))
    assert referenced <= defined, f"CSS references undefined SVG filters: {referenced - defined}"

    for filter_id in defined:
        used_in_css = f"url(#{filter_id})" in CSS
        used_in_html = f"url(#{filter_id})" in HTML.replace(f'id="{filter_id}"', "")
        assert used_in_css or used_in_html, f"SVG filter #{filter_id} is defined but never used"


def test_specular_position_is_never_published_on_the_root_element():
    """The cross-card glint bug.

    Custom properties inherit. Writing the pointer position onto
    documentElement meant every .card resolved the same global value and lit up
    in unison, instead of only the card under the pointer. The position must be
    set on the hovered element and nowhere else.
    """
    for prop in ("--specular-x", "--specular-y"):
        bad = re.search(
            r"document(?:Element)?\.(?:documentElement\.)?style\.setProperty\(\s*[\"']" + prop,
            APP_JS,
        )
        assert bad is None, f"{prop} must not be set on the root element"

    assert "documentElement.style.setProperty(\"--mouse-x\"" not in APP_JS
    assert "documentElement.style.setProperty(\"--mouse-y\"" not in APP_JS

    # And the CSS must read the un-inheritable names, with an off-canvas default
    # so an un-hovered surface paints nothing.
    card = re.search(r"\n\.card \{(.+?)\n\}", CSS, re.S)
    assert card, ".card rule not found"
    assert "--specular-x, -999px" in card.group(1), "card specular must default off-canvas"


def test_card_does_not_clip_its_own_accent_rule():
    """`overflow: hidden` on .card ate the ::before accent bar, which is
    positioned on the border itself."""
    card = re.search(r"\n\.card \{(.+?)\n\}", CSS, re.S)
    assert card, ".card rule not found"
    assert "overflow: hidden" not in card.group(1)


def test_accent_rule_clears_the_corner_radius():
    """At top/left -1px against a 14px radius the bar floated detached above
    the card. It has to start past the corner arc."""
    before = re.search(r"\n\.card::before \{(.+?)\n\}", CSS, re.S)
    assert before, ".card::before rule not found"
    body = before.group(1)
    assert "left: var(--radius-glass" in body, "accent rule must start past the corner arc"
    assert "top: -1px" not in body


def test_refracting_rim_exists_and_is_scoped_off_magi_mode():
    """The rim is a masked band carrying its own backdrop-filter. MAGI MODE
    reuses .card::after for a corner bracket, so the rim must not land on it."""
    assert 'html:not([data-theme="eva"]) .card::after {' in CSS
    assert 'html:not([data-theme="eva"]) .modal-window::after,' in CSS

    rim = re.search(r'html:not\(\[data-theme="eva"\]\) \.card::after \{(.+?)\n\}', CSS, re.S)
    assert rim, "rim rule not found"
    body = rim.group(1)
    assert "backdrop-filter: var(--glass-edge-filter)" in body
    assert "mask-composite: exclude" in body
    assert "padding: var(--glass-edge-width" in body


def test_magi_mode_keeps_both_corner_brackets_and_gets_its_own_rim():
    """Freeing ::after for the rim moved both brackets onto ::before as four
    background bars. Losing one would silently drop a bracket."""
    before = re.search(r'\[data-theme="eva"\] \.card::before \{(.+?)\n\}', CSS, re.S)
    assert before, "eva .card::before not found"
    body = before.group(1)
    assert body.count("linear-gradient(var(--accent-primary)") == 4, "expected 4 bracket bars"
    assert "background-position: right top, right top, left bottom, left bottom;" in body
    # Full-bleed: a shrink-to-fit box collapses to zero width and stacks the
    # bars on the left edge.
    assert "inset: 0;" in body and "right: auto" not in body

    after = re.search(r'\[data-theme="eva"\] \.card::after \{(.+?)\n\}', CSS, re.S)
    assert after, "eva .card::after not found"
    assert "backdrop-filter: var(--glass-edge-filter)" in after.group(1)
    assert "right: auto" not in after.group(1)


def test_reduced_transparency_is_a_default_not_an_unreachable_hard_gate():
    """The material was force-killed by `--glass-blur: 0px !important` from both
    a media query and an html.reduced-transparency class. On Windows 11, which
    ships "Transparency effects" off in several states, that left the entire
    system dead with no way to opt in -- and it silently overrode the tuner's
    blur slider too, so dragging it did nothing.
    """
    assert "html.reduced-transparency" not in CSS_RULES
    assert re.search(r"--glass-blur:\s*0px\s*!important", CSS_RULES) is None

    # The OS preference seeds the default; an explicit choice wins and sticks.
    assert "function initialLiquidGlass()" in APP_JS
    assert 'prefers-reduced-transparency: reduce' in APP_JS
    assert 'safeStorageGet("magi-liquid-glass")' in APP_JS


def test_solid_fallback_still_reachable():
    """Turning the material off must actually strip the backdrop work."""
    assert "html.no-glass" in CSS
    assert re.search(r"html\.no-glass[^{]*\{[^}]*backdrop-filter:\s*none\s*!important", CSS, re.S)


def test_eva_artwork_stays_inside_magi_mode():
    """#app-bg used to be `display: none` outside MAGI MODE, and that was the
    only thing hiding its children. Turning the container on for the ambient
    field let the EVA artwork -- hex bloom, Unit-01 blueprint, vertical kanji,
    ribbon -- fall through into light and dark as unstyled static divs, with the
    two text layers painting over the brand in the top-left corner.
    """
    assert 'html:not([data-theme="eva"]) .app-bg > *:not(.app-bg-ambient)' in CSS_RULES

    artwork = ("app-bg-hex", "app-bg-unit", "app-bg-kanji", "app-bg-ribbon", "app-bg-photo")
    for name in artwork:
        assert f'class="{name}"' in HTML or f"{name}" in HTML, f"{name} missing from markup"
        # Every artwork layer must be positioned by a MAGI-scoped rule only.
        unscoped = re.search(rf"\n\.{name} \{{", CSS_RULES)
        assert unscoped is None, f".{name} has an unscoped base rule; it would leak outside MAGI"


def test_tuner_has_no_magic_default_value():
    """The blur knob used to treat its own default (10) as "no override", while
    each theme sets a different --glass-blur in CSS (light 20, dark 22,
    MAGI-blue 10). Once the readout was made honest by writing the computed
    value back into the slider, dragging *through* 10 snapped the knob to 22 out
    from under the pointer, and the rest of the drag was measured from the
    jumped position -- which is how values nobody chose kept landing in
    localStorage.

    Unset must mean "use the theme's CSS value"; any stored value is an explicit
    override. No slider position may be special.
    """
    assert "function glassSetting(key, min, max)" in APP_JS, "glassSetting must not take a fallback"
    assert re.search(r"blur\s*===\s*GLASS_DEFAULTS\.blur", APP_JS) is None, (
        "the slider default must not be used as a sentinel for 'no override'"
    )
    assert re.search(r"alpha\s*===\s*GLASS_DEFAULTS\.alpha", APP_JS) is None

    body = re.search(r"function applyGlassSettings\(\) \{(.+?)\n  \}", APP_JS, re.S)
    assert body, "applyGlassSettings not found"
    assert "blur === null" in body.group(1), "unset must be distinguished by null"
    assert "alpha === null" in body.group(1)

    # Reset clears the keys so the theme's own value comes back. Writing the
    # slider default back left the key present forever.
    reset = re.search(r"glassResetBtn\.addEventListener\(\"click\", \(\) => \{(.+?)\n    \}\)", APP_JS, re.S)
    assert reset, "reset handler not found"
    for key in ("magi-glass-blur", "magi-glass-alpha", "magi-crt"):
        assert f'safeStorageRemove("{key}")' in reset.group(1), f"reset must clear {key}"
    assert "safeStorageSet" not in reset.group(1), "reset must not write values back"


def test_glass_tokens_defined_for_every_theme():
    required = (
        "--glass-blur",
        "--glass-saturate",
        "--glass-bg",
        "--glass-border",
        "--glass-rim-top",
        "--glass-rim-bottom",
        "--glass-edge-filter",
        "--glass-edge-sheen",
    )
    for name, selector in THEME_BLOCKS.items():
        block = _block(selector)
        for token in required:
            assert f"{token}:" in block, f"{token} missing from the {name} theme"


def test_opacity_knob_reaches_every_theme():
    """--glass-alpha only fed --glass-scale inside MAGI MODE, so outside it the
    tuner's opacity slider moved and nothing happened."""
    for name in ("light", "dark"):
        block = _block(THEME_BLOCKS[name])
        assert "--glass-scale:" in block, f"{name} theme has no --glass-scale"
        assert "var(--glass-scale)" in block, f"{name} tints ignore the opacity knob"


def test_warn_border_defined_wherever_it_is_used():
    """It was dropped from :root while .update-badge still consumed it, which
    makes the whole `border` shorthand invalid and the badge loses its edge."""
    assert "var(--warn-border)" in CSS
    for name, selector in (("light", ":root {"), ("dark", '[data-theme="dark"] {')):
        assert "--warn-border:" in _block(selector), f"--warn-border missing from {name}"


def test_text_ramp_stays_distinct_within_each_theme():
    """A wholesale palette swap collapsed --text-muted onto --text-secondary in
    MAGI MODE, flattening the type hierarchy."""
    for name, selector in THEME_BLOCKS.items():
        block = _block(selector)
        found = dict(re.findall(r"(--text-(?:primary|secondary|muted|subtle)):\s*(#[0-9A-Fa-f]{3,8})", block))
        if len(found) < 2:
            continue
        assert len(set(found.values())) == len(found), (
            f"{name} theme reuses one colour across {found}"
        )


def test_glass_control_uses_theme_colours():
    """The toggle shipped a hardcoded cyan/green gradient belonging to no
    theme's palette."""
    active = re.search(r"\.glass-toggle-btn\.active \{(.+?)\n\}", CSS, re.S)
    assert active, ".glass-toggle-btn.active not found"
    body = active.group(1)
    assert "rgba(69, 213, 234" not in body
    assert "rgba(53, 239, 126" not in body
    assert "var(--accent-primary" in body
