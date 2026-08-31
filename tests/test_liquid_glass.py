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
    # so an un-hovered surface paints nothing. That default lives in the shared
    # --glass-specular-layer token every surface resolves.
    layer = re.search(r"--glass-specular-layer:(.+?);", CSS, re.S)
    assert layer, "--glass-specular-layer not defined"
    assert "--specular-x, -999px" in layer.group(1), "specular must default off-canvas"
    assert "--specular-y, -999px" in layer.group(1)

    card = re.search(r"\n\.card \{(.+?)\n\}", CSS, re.S)
    assert card, ".card rule not found"
    assert "var(--glass-specular-layer)" in card.group(1)


def test_every_tracked_surface_actually_paints_a_specular():
    """The engine's list and the CSS have to agree in both directions. Tracking a
    surface that paints nothing is invisible work; leaving one out is a dead
    patch the pointer skates over. Before this was pinned, the engine tracked ten
    selectors and only three of them painted."""
    listed = re.search(r"const SPECULAR_SURFACES =\s*(.+?);", APP_JS, re.S)
    assert listed, "SPECULAR_SURFACES not found"
    selectors = re.findall(r"\.[\w-]+", listed.group(1).replace('" +', "").replace('"', ""))

    for sel in selectors:
        painted = re.search(
            re.escape(sel) + r"(?![\w-])[^{}]*\{[^{}]*var\(--glass-specular-layer\)",
            CSS_RULES,
        )
        assert painted, f"{sel} is tracked by the engine but paints no specular"


def test_theme_overrides_never_reset_the_specular_with_the_shorthand():
    """`background:` resets background-image. MAGI MODE's .card and
    .doc-preview-side both used the shorthand, which silently dropped the
    specular the base rule paints -- in that theme the effect survived only on
    the HUD monolith, whose rule happened to spell the layer out again."""
    tracked = (".card", ".modal-window", ".modal-content", ".glass-tuner-panel",
               ".doc-preview-side", ".pane-list", ".pane-view", ".topbar",
               ".core-band", ".eva-hud-frame")
    offenders = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS_RULES):
        sel, body = m.group(1).strip(), m.group(2)
        if "::" in sel or not re.search(r"(?m)^\s*background:\s", body):
            continue
        if any(re.search(re.escape(t) + r"(?![\w-])", sel) for t in tracked):
            offenders.append(sel.splitlines()[-1].strip())
    assert not offenders, (
        "these reset background-image on a specular surface; use background-color:\n  "
        + "\n  ".join(offenders)
    )


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
    assert "prefers-reduced-transparency" not in CSS_RULES, (
        "the OS preference is handled in app.js as a default, not as a CSS override"
    )
    # Zeroing the blur is legitimate under the user's own off switch, and only
    # there. Anywhere else it is the unreachable hard gate coming back.
    for m in re.finditer(r"--glass-blur:\s*0px\s*!important", CSS_RULES):
        owner = CSS_RULES.rfind("{", 0, m.start())
        selector = CSS_RULES[:owner].rsplit("}", 1)[-1].strip()
        assert selector == "html.no-glass", (
            f"--glass-blur is force-zeroed outside the explicit toggle, under: {selector!r}"
        )

    # The OS preference seeds the default; an explicit choice wins and sticks.
    assert "function initialLiquidGlass()" in APP_JS
    assert 'prefers-reduced-transparency: reduce' in APP_JS
    assert 'safeStorageGet("magi-liquid-glass")' in APP_JS


def test_solid_fallback_is_blanket_not_a_surface_list():
    """The off switch listed seven selectors, and went stale the moment anything
    else got the material: with glass "off", .tabs-nav, .lang-toggle,
    .eva-hud-frame, .pane-list, the graph overlays and every .btn were still
    sampling the backdrop -- so the blur slider went on moving half the page
    while the other half was inert.
    """
    blanket = re.search(
        r"html\.no-glass \*,\s*html\.no-glass \*::before,\s*html\.no-glass \*::after \{([^}]+)\}",
        CSS_RULES,
    )
    assert blanket, "no-glass must kill backdrop-filter with a blanket rule"
    assert "backdrop-filter: none !important" in blanket.group(1)


def test_solid_fallback_does_not_blank_background_image():
    """`background-image: none !important` was written for light/dark, where the
    specular is a background-image. MAGI MODE's card background *is* a
    linear-gradient, so the same rule left its cards with no background at all --
    transparent panels over the artwork. The specular is switched off at its
    colour stop instead."""
    block = re.search(r"(?m)^html\.no-glass \{([^}]+)\}", CSS_RULES)
    assert block, "html.no-glass token block not found"
    body = block.group(1)
    assert "--glass-specular-color: transparent !important" in body
    assert "--glass-scale:" in body, "opacity must be forced through the shared scale"
    assert "--glass-blur: 0px !important" in body

    assert re.search(r"html\.no-glass[^{]*\{[^}]*background-image:\s*none\s*!important", CSS_RULES) is None, (
        "blanking background-image erases MAGI MODE's card gradient"
    )


#: Surfaces whose visible fill is `background-image` in at least one theme.
#: `[data-theme="eva"] .card` is the clearest case: `background-color:
#: transparent` plus a gradient, so removing the image leaves a hole.
FILL_IS_AN_IMAGE = ("card", "modal-window", "modal-content", "topbar",
                    "core-band", "toast", "stat-pill", "icon-btn",
                    "doc-preview-side", "glass-tuner-panel")


def _rules_blanking_background_image():
    """Every rule that sets `background-image: none !important`, anywhere."""
    for match in re.finditer(r"([^{}]*)\{([^{}]*)\}", CSS_RULES):
        selector, body = match.group(1).strip(), match.group(2)
        if re.search(r"background-image:\s*none\s*!important", body):
            yield selector, body


def test_nothing_blanks_a_fill_without_supplying_one():
    """The rule, not the instance.

    `html.no-glass` learned this and wrote the reason down; two media queries
    kept doing it anyway, and the guard above could not see them because it
    named a selector instead of naming the property. In MAGI MODE a machine
    with "reduce motion" switched on showed cards as holes over the artwork —
    the third time this defect shipped.

    A rule may blank `background-image`. What it may not do is blank it on a
    surface whose fill lives there and leave nothing behind: either it sets a
    `background-color` in the same rule, or it is not this rule's business.
    """
    offenders = []
    for selector, body in _rules_blanking_background_image():
        touches_fill = any(f".{name}" in selector for name in FILL_IS_AN_IMAGE)
        if not touches_fill:
            continue
        if re.search(r"background-color:\s*[^;]+", body):
            continue
        offenders.append(selector.replace("\n", " ")[:120])

    assert not offenders, (
        "these rules blank the fill of a surface that has no other background "
        "and put nothing in its place — in MAGI MODE the card becomes a hole:\n  "
        + "\n  ".join(offenders))


def test_reduced_motion_asks_for_less_movement_not_less_material():
    """Reduced motion and forced colours want different things, and treating
    them as one is how the specular kill turned into a fill kill. The moving
    part is the pointer specular; it goes at its colour stop, the way
    `html.no-glass` does it. Opacity and blur are nobody's business here."""
    block = re.search(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}",
                      CSS_RULES, re.S)
    assert block, "the reduced-motion block moved or was removed"
    body = block.group(1)

    assert "--glass-specular-color: transparent !important" in body, (
        "reduced motion must kill the specular at the token, not by blanking "
        "the surfaces that are painted with it")
    assert "--glass-blur" not in body, (
        "reduced motion is not a request for opacity — that is what the GLASS "
        "control and html.no-glass are for")


def test_backdrop_layer_sits_behind_unpositioned_content():
    """#app-bg is fixed. At z-index 0 it painted *above* the background of any
    static block, because a positioned box outranks one. The core band is
    static, so with the material on it only cleared the artwork by accident --
    backdrop-filter made it a stacking context, which promoted it. Switch the
    material off and the promotion went too: the artwork painted over the band
    and its text became unreadable.
    """
    for sel in (".app-bg", '[data-theme="eva"] .app-bg'):
        m = re.search(r"(?m)^" + re.escape(sel) + r"\s*\{([^}]+)\}", CSS_RULES)
        assert m, f"{sel} rule not found"
        assert "z-index: -1;" in m.group(1), f"{sel} must sit behind static content"


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


def test_no_var_carries_a_fallback_for_a_token_that_always_exists():
    """A fallback that can never fire is documentation that lies.

    `--glass-specular-color` is defined on `:root` and again in every theme
    block, so the second argument of `var(--glass-specular-color, X)` is
    unreachable. Four call sites carried one anyway, typed four different ways
    — 0.25, 0.15, 0.12, 0.15 — and not one of them matched a real theme value
    (0.65 / 0.25 / 0.24 / 0.55). A reader checking "what colour is the
    specular here" found four answers, all wrong, none used.
    """
    root = re.search(r"(?m)^:root \{(.*?)\n\}", CSS_RULES, re.S)
    assert root, ":root token block not found"
    always_defined = set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:", root.group(1), re.M))
    assert always_defined, "no tokens parsed out of :root"

    offenders = []
    for name, fallback in re.findall(r"var\((--[a-z0-9-]+)\s*,\s*([^)]+(?:\([^)]*\))?[^)]*)\)",
                                     CSS_RULES):
        if name in always_defined:
            offenders.append(f"{name} -> {fallback.strip()[:40]}")

    assert not offenders, (
        "these var() fallbacks can never be reached, because the token is "
        "defined on :root — and each one is a different answer to a question "
        "it never gets asked:\n  " + "\n  ".join(sorted(set(offenders))[:12]))


#: The three MAGI cores, in both variants, as they are written in the token
#: definitions. Any other appearance of these numbers is a colour that will
#: not follow `[data-eva="blue"]` when the palette swaps.
CORE_LITERALS = {
    "#45D5EA": "--eva-melchior (red)",   "69, 213, 234": "--eva-melchior (red)",
    "#35EF7E": "--eva-balthasar (red)",  "53, 239, 126": "--eva-balthasar (red)",
    "#FF4A57": "--eva-casper (red)",     "255, 74, 87": "--eva-casper (red)",
    "#086080": "--eva-melchior (blue)",  "#0E6E3E": "--eva-balthasar (blue)",
    "#A81F2A": "--eva-casper (blue)",
}

#: The core colours written out in a *rule*, as they stand today. Each one
#: cannot follow `[data-eva="blue"]` when the palette swaps — a bug where
#: the colour means "this core", and correct where it means something else.
#: About sixteen sit in the Operations & Danger Zone panel. The author
#: settled it (2026-08-31): that red is *danger's* red, not casper's. A
#: danger zone is red in every palette, so those literals are correct and
#: changing them to follow `[data-eva="blue"]` would be the defect. They stay
#: on this list because the check is mechanical, not because they are open.
#:
#: A ledger of open questions, not a list of blessings. Checked both ways:
#: a new one is not here and fails, and fixing one leaves a stale entry
#: that also fails — so somebody prunes it instead of letting it become a
#: permanent excuse.
CORE_LITERAL_LEDGER = [
    'background: linear-gradient(180deg, #FF4A57, #C91526);',
    'filter: drop-shadow(0 0 6px rgba(255, 74, 87, 0.4));',
    'filter: drop-shadow(0 0 12px rgba(255, 74, 87, 0.6));',
    'border-color: rgba(255, 74, 87, 0.35);',
    'linear-gradient(150deg, rgba(255, 74, 87, 0.13), rgba(255, 74, 87, 0.0',
    'border: 1px solid rgba(255, 74, 87, 0.35);',
    'border-left: 4px solid #FF4A57;',
    'filter: drop-shadow(0 4px 14px rgba(var(--eva-shadow-rgb), calc(0.4 * ',
    'color: rgba(255, 74, 87, 0.1);',
    'color: #FF4A57;',
    'text-shadow: 0 0 8px rgba(255, 74, 87, 0.4);',
    'border-color: rgba(255, 74, 87, 0.55);',
    'filter: drop-shadow(0 16px 34px rgba(var(--eva-shadow-rgb), calc(0.95 ',
    'border-color: rgba(255, 74, 87, 0.55);',
    'filter: drop-shadow(0 16px 34px rgba(var(--eva-shadow-rgb), calc(0.95 ',
    'color: #FF4A57;',
    'border-bottom-color: rgba(255, 74, 87, 0.3);',
    'fill: rgba(255, 74, 87, 0.08);',
    '.eva-boot-core.c1 { color: #45D5EA; text-shadow: 0 0 10px rgba(69, 213',
    '.eva-boot-core.c2 { color: #35EF7E; text-shadow: 0 0 10px rgba(53, 239',
    '.eva-boot-core.c3 { color: #FF4A57; text-shadow: 0 0 10px rgba(255, 74',
]


def test_the_ledger_of_hardcoded_core_colours_is_exact():
    """Both directions, so neither growth nor silent shrinkage passes."""
    found = []
    for line in CSS_RULES.splitlines():
        stripped = line.strip()
        if re.match(r"--[a-z0-9-]+\s*:", stripped):
            continue
        if any(lit.lower() in line.lower() for lit in CORE_LITERALS):
            found.append(stripped[:70])

    added = [s for s in found if s not in CORE_LITERAL_LEDGER]
    assert not added, (
        "a core colour was written out in a new rule; inside a core tab use "
        "var(--core), elsewhere var(--eva-<core>):\n  " + "\n  ".join(added[:8]))

    gone = [s for s in CORE_LITERAL_LEDGER if s not in found]
    assert not gone, (
        "these were fixed — good — but the ledger still lists them, and a "
        "ledger nobody prunes turns into a permanent excuse:\n  "
        + "\n  ".join(gone[:8]))


#: The named recipes. A surface asks for one of these; it does not compose
#: its own out of the tokens underneath.
FX_PRESETS = ("--fx-surface-sm", "--fx-surface-md", "--fx-surface-lg", "--fx-rim")

#: The non-glass shadow family, for surfaces that are not made of glass.
PLAIN_SHADOWS = ("--shadow-sm", "--shadow-md", "--shadow-lg")


def test_no_surface_composes_its_own_glass_recipe():
    """Presets only stay presets if nothing may hand-write a new one.

    Eight compositions of the same four tokens were in use and which one a
    surface got was arbitrary: at the same size tier `.pane-list` had a bottom
    rim and `.toast` did not, `.modal-window` had one and `.glass-tuner-panel`
    did not. Naming the four that remain is worth nothing on its own — without
    this, a year from now there are four presets and six new recipes, and the
    grep is worse than before because the tokens are one level further away.

    A glass surface names a preset. A non-glass one uses the plain shadow
    family. Anything that spells out `--glass-rim-*` or `--glass-shadow-*` in
    a `box-shadow` is composing a recipe by hand.
    """
    offenders = []
    for number, line in enumerate(CSS_RULES.splitlines(), 1):
        match = re.search(r"box-shadow:\s*([^;]+)", line)
        if not match:
            continue
        value = match.group(1)
        if "--glass-rim" in value or "--glass-shadow" in value:
            offenders.append(f"line {number}: {line.strip()[:80]}")

    assert not offenders, (
        "these compose a glass recipe instead of naming one — use "
        f"{', '.join(FX_PRESETS)}:\n  " + "\n  ".join(offenders[:10]))


def test_every_preset_carries_both_rims():
    """The author's rule, in one place: if any surface has a bottom rim, all
    of them do. Held on the definitions rather than on the 19 call sites, so
    it stays true for a preset added later."""
    root = re.search(r"(?m)^:root \{(.*?)\n\}", CSS_RULES, re.S)
    assert root, ":root not found"
    body = root.group(1)

    for preset in FX_PRESETS:
        m = re.search(rf"{re.escape(preset)}:\s*([^;]+);", body)
        assert m, f"{preset} is not defined on :root"
        value = m.group(1)
        assert "--glass-rim-top" in value and "--glass-rim-bottom" in value, (
            f"{preset} has one rim and not the other: {value.strip()[:70]}")


def test_every_textarea_is_given_a_width():
    """A textarea with no width falls back to `cols`, which defaults to 20.

    `#dump-text` — the "say it here" box, the one surface whose whole job is
    to be easy to type into — sat at about 194px inside a 1432px card,
    because `.text-input` sets `min-width` and `max-width` and never `width`.
    That works for an `<input>` in a flex row, where flex supplies the size,
    and not at all for a textarea standing on its own: the fallback is a
    character count from the 1990s that knows nothing about the layout.

    Held on the stylesheet rather than on one id: either the shared rule gives
    every textarea a width, or the row it sits in gives it a flex basis.
    """
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8", errors="replace")

    shared = re.search(r"textarea\.text-input\s*\{([^}]*)\}", CSS_RULES)
    assert shared and re.search(r"\bwidth:\s*100%", shared.group(1)), (
        "textarea.text-input must set a width; without one every textarea "
        "that is not a flex item falls back to cols=20")

    for match in re.finditer(r"<textarea([^>]*)>", html):
        attrs = match.group(1)
        ident = re.search(r'id="([^"]+)"', attrs)
        assert "class=" in attrs and "text-input" in attrs, (
            f"textarea {ident.group(1) if ident else '?'} does not use "
            ".text-input, so nothing gives it a width")
