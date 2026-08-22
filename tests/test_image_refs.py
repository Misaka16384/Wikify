"""The one convention every route's images must satisfy.

Five routes produce Markdown, and before this module existed each of them
decided for itself what an image reference looked like. They disagreed, and
every disagreement was a bug that only showed up after the document had been
committed — which is to say, after it was too late to notice cheaply.

These tests pin the convention itself. The per-route tests check that each
route obeys it; this file checks that the convention says something.
"""

from magi.ingest import image_refs as ir


# --------------------------------------------------------------------------
# What counts as a reference at all
# --------------------------------------------------------------------------

def test_both_spellings_are_found():
    """Pandoc leaves any figure it cannot express in Markdown as raw HTML, which
    is what happens to essentially every real arXiv figure. A checker that knows
    only ![]() is blind to the majority of them."""
    md = ('![cap](images/a.png)\n'
          '<img src="images/b.png" class="ltx_graphics"/>\n'
          '<embed src="images/c.png"/>\n')
    assert set(ir.iter_targets(md)) == {"images/a.png", "images/b.png", "images/c.png"}


def test_either_html_quote_style_is_read():
    """Pandoc only writes double quotes; HTML permits both. A narrow pattern
    would not mis-parse the single-quoted form — it would miss it, and a
    reference the checker cannot see is a document it calls clean."""
    assert ir.iter_targets("<img src='images/a.png' id='x'/>") == ["images/a.png"]
    md, _ = ir.rewrite("<img src='old/f.png' id='x'/>", lambda t: "p-f.png")
    assert md == "<img src='images/p-f.png' id='x'/>"


def test_a_repeated_reference_is_reported_twice():
    """A document that references the same file twice has two chances to be
    wrong about it, so the caller gets to decide whether to deduplicate."""
    assert ir.iter_targets("![](images/a.png)\n![](images/a.png)\n") == \
        ["images/a.png", "images/a.png"]


def test_a_title_attribute_does_not_swallow_the_target():
    assert ir.iter_targets('![c](images/a.png "A title")') == ["images/a.png"]


def test_angle_bracketed_targets_are_unwrapped():
    assert ir.iter_targets("![c](<images/a.png>)") == ["images/a.png"]


def test_a_target_containing_a_space_is_still_seen():
    """Legal Markdown when wrapped in angle brackets, and a pattern that only
    handled the bare form would not mis-parse it — it would fail to match at
    all, and a checker that cannot see a reference calls the document clean.
    That is the failure this module exists to stop repeating."""
    found = ir.iter_targets("![](<C:/Temp/my staging/images/a.png>)")
    assert found == ["C:/Temp/my staging/images/a.png"]
    assert ir.classify(found[0]) == "absolute"


# --------------------------------------------------------------------------
# classify — the question the old gate could not ask
# --------------------------------------------------------------------------

def test_the_convention_is_the_only_acceptable_local_shape():
    assert ir.classify("images/fig1.png") == "portable"
    assert ir.is_portable("images/fig1.png")


def test_remote_and_inline_images_are_left_to_themselves():
    for target in ("https://x.test/a.png", "http://x.test/a.png",
                   "data:image/png;base64,AAA", "//cdn.test/a.png"):
        assert ir.classify(target) == "external"
        assert ir.is_portable(target)


def test_an_absolute_staging_path_is_named_as_one():
    """The exact reference `pymupdf4llm` produced, and the exact one the old
    gate reported as a clean document."""
    assert ir.classify(
        "C:/Users/x/AppData/Local/Temp/tmp1/images/paper.pdf-0001-01.png") == "absolute"
    assert ir.classify("/tmp/staging/images/a.png") == "absolute"


def test_a_windows_separator_is_not_a_path_to_a_markdown_reader():
    assert ir.classify(r"images\a.png") == "backslash"
    assert ir.classify(r"C:\tmp\a.png") == "absolute"


def test_the_other_ways_to_be_wrong_each_get_their_own_name():
    assert ir.classify("../images/a.png") == "escaping"
    assert ir.classify("a.png") == "bare"
    assert ir.classify("figs/a.png") == "elsewhere"
    assert ir.classify("images/sub/a.png") == "nested"


# --------------------------------------------------------------------------
# namespaced — why a filename carries a slug
# --------------------------------------------------------------------------

def test_two_documents_cannot_produce_the_same_filename():
    """The whole point. raw/papers/images/ is shared by the library, so
    uniqueness within one document is not uniqueness."""
    assert ir.namespaced("2401.00506", "fig1.png") != ir.namespaced("2502.11111", "fig1.png")


def test_namespacing_is_idempotent():
    """`pymupdf4llm` already names files after the source PDF, and a route that
    ran twice must not produce slug-slug-name."""
    once = ir.namespaced("a-survey", "fig1.png")
    assert ir.namespaced("a-survey", once) == once


def test_truncation_keeps_the_end_of_the_name():
    """Figure names differ at the tail — fig1/fig2, -0001-01/-0001-02 — so
    trimming from the front is what preserves what tells two files apart."""
    a = ir.namespaced("s" * 60, "x" * 90 + "-0001-01.png")
    b = ir.namespaced("s" * 60, "x" * 90 + "-0001-02.png")
    assert a != b
    assert len(a) <= ir.NAME_MAX
    assert a.endswith("-0001-01.png")


def test_a_slug_that_leaves_no_room_still_yields_a_usable_name():
    name = ir.namespaced("s" * 400, "fig.png")
    assert len(name) <= ir.NAME_MAX and name.endswith(".png")


def test_path_separators_never_survive_into_a_filename():
    assert "/" not in ir.namespaced("cond-mat/0001002", "a/b/fig.png")
    assert "\\" not in ir.namespaced("x", r"a\b\fig.png")


def test_a_name_made_entirely_of_junk_still_produces_something_openable():
    assert ir.sanitize("...") == "image"
    assert ir.sanitize("") == "image"


# --------------------------------------------------------------------------
# rewrite
# --------------------------------------------------------------------------

def test_rewriting_reports_what_it_did_so_the_caller_need_not_recompute_it():
    """The document and the directory must agree on a name. Handing back the
    mapping is what makes disagreeing impossible; deriving 'the same' name
    twice is how two derivations drift apart."""
    md, mapping = ir.rewrite('![a](old/fig1.png)\n<img src="old/fig2.png"/>\n',
                             lambda t: "p-" + t.split("/")[-1])
    assert mapping == {"old/fig1.png": "p-fig1.png", "old/fig2.png": "p-fig2.png"}
    assert "![a](images/p-fig1.png)" in md
    assert 'src="images/p-fig2.png"' in md


def test_resolving_to_none_leaves_a_reference_untouched():
    src = '![a](old/fig1.png)\n'
    md, mapping = ir.rewrite(src, lambda t: None)
    assert md == src and mapping == {}


def test_already_correct_and_external_references_are_never_resolved():
    asked = []

    def resolve(target):
        asked.append(target)
        return "x.png"

    src = '![a](images/fig.png)\n![b](https://x.test/y.png)\n'
    md, mapping = ir.rewrite(src, resolve)
    assert md == src and mapping == {} and asked == []


def test_the_surrounding_markup_survives_the_rewrite():
    md, _ = ir.rewrite('<img src="old/f.png" id="S2.F1" class="ltx_graphics"/>',
                       lambda t: "p-f.png")
    assert 'id="S2.F1"' in md and 'class="ltx_graphics"' in md
