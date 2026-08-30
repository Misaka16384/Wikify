"""Evidence points at `raw/`, never at a card compiled from it.

A reference card looks like a source and is not one: an LLM built it out of
`raw/`, and it can be wrong in precisely the way a claim citing it is trying to
rule out. Cite the card and the mistake gets laundered — the card says it, the
concept card cites the card, and nobody opens the paper again. So the rule is
mechanical, and this is where it is enforced.

The derived number is deliberately `None` rather than `0.0` for a note with no
claims: a concept card that states a definition makes no empirical claim and is
not deficient for it. Scoring it zero would drop it to the bottom of every list
it ever appears in.
"""

from magi.core import vocab
from magi.kb import backing


COLD = """CLAIM: The gap closes at p=0.11.
EVIDENCE: "we observe a closing gap at p = 0.11"
SOURCE_TYPE: local_wiki
SOURCE: raw/papers/2601.00001.md
"""

LAUNDERED = """CLAIM: The gap closes at p=0.11.
EVIDENCE: "the gap closes at p = 0.11"
SOURCE_TYPE: local_wiki
SOURCE: wiki/references/kitaev-2003.md
"""

WEB = """CLAIM: The library shipped in 2025.
EVIDENCE: "released 2025"
SOURCE_TYPE: web
SOURCE: https://example.org/release
"""


def test_a_claim_on_raw_is_cold_backed():
    assert backing.backing(COLD) == {"claims": 1, "cold": 1, "rate": 1.0}


def test_a_claim_on_a_compiled_card_is_not():
    assert backing.backing(LAUNDERED)["cold"] == 0


def test_a_web_claim_is_counted_but_not_cold():
    result = backing.backing(WEB)
    assert result["claims"] == 1
    assert result["cold"] == 0


def test_a_note_with_no_claims_has_no_rate_rather_than_zero():
    assert backing.backing("# A card\n\nProse only.\n")["rate"] is None


def test_the_rate_is_the_fraction_that_rests_on_the_cold_layer():
    result = backing.backing(COLD + "\n" + LAUNDERED)
    assert (result["claims"], result["cold"]) == (2, 1)
    assert result["rate"] == 0.5


def test_laundered_sources_names_the_claim_and_the_card():
    found = backing.laundered_sources(COLD + "\n" + LAUNDERED)
    assert len(found) == 1
    claim, source = found[0]
    assert "gap closes" in claim
    assert source == "wiki/references/kitaev-2003.md"


def test_a_url_has_no_tier_and_is_never_reported_as_laundered():
    assert backing.source_tier("https://arxiv.org/abs/2601.00001") is None
    assert backing.laundered_sources(WEB) == []


def test_the_tier_of_a_source_is_the_workspace_tier():
    assert backing.source_tier("raw/papers/x.md") == vocab.COLD
    assert backing.source_tier("wiki/references/x.md") == vocab.COLD_DERIVED
    assert backing.source_tier("") is None


# --------------------------------------------------------------------------
# wired into `magi lint`
# --------------------------------------------------------------------------

def _cold_backing_issues(tmp_path, rel, text):
    from magi.core.wiki_common import parse_frontmatter, split_frontmatter_text
    from magi.kb import llmwiki

    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

    split = split_frontmatter_text(text)
    ctx = llmwiki.LintContext(tmp_path)
    ctx.documents = {path.resolve(): llmwiki.Document(
        path=path, frontmatter=parse_frontmatter(text),
        body=split[1] if split else text, raw_text=text)}
    llmwiki.check_cold_backing(ctx)
    return [issue.message for issue in ctx.issues]


def test_the_lint_check_names_the_card_and_the_claim(tmp_path):
    issues = _cold_backing_issues(tmp_path, "wiki/concepts/gap.md",
                                  "---\ntitle: Gap\n---\n\n# Gap\n\n" + LAUNDERED)
    assert len(issues) == 1
    assert "wiki/references/kitaev-2003.md" in issues[0]
    assert "gap closes" in issues[0]


def test_a_claim_on_raw_passes_the_lint_check(tmp_path):
    assert _cold_backing_issues(tmp_path, "wiki/concepts/gap.md",
                                "---\ntitle: Gap\n---\n\n# Gap\n\n" + COLD) == []


def test_a_lowercase_claim_is_still_checked(tmp_path):
    """`verify_claims` parses field names case-insensitively, so a gate that
    only recognises `SOURCE:` skips notes the verifier would happily check —
    a false negative that looks exactly like a clean note."""
    lowered = LAUNDERED.replace("CLAIM:", "Claim:").replace("SOURCE:", "Source:") \
                       .replace("EVIDENCE:", "Evidence:").replace("SOURCE_TYPE:", "Source_type:")
    issues = _cold_backing_issues(tmp_path, "wiki/concepts/gap.md",
                                  "---\ntitle: Gap\n---\n\n# Gap\n\n" + lowered)
    assert len(issues) == 1


def test_a_note_with_no_claims_is_not_parsed_at_all(tmp_path):
    assert _cold_backing_issues(tmp_path, "wiki/concepts/gap.md",
                                "---\ntitle: Gap\n---\n\n# Gap\n\nProse.\n") == []


# --------------------------------------------------------------------------
# a sources: field that points out of the project
# --------------------------------------------------------------------------

def test_a_source_ref_cannot_resolve_outside_the_project(tmp_path):
    """`sources:` travels from an ingested paper through the compile
    pipeline, so it is not the user's typing.

    The `../`-relative branch resolved it with no containment check: a value
    of `../../../secret.md` in a card under `wiki/concepts/` resolved to, and
    stat'd, a real file outside the project. No caller read those bytes —
    each re-checked `is_under(..., root/"raw")` first — but the `.exists()`
    here is itself observable, and safety by every caller remembering is the
    arrangement `verify_claims.verify_local` was just moved off.
    """
    from magi.kb import llmwiki

    root = tmp_path / "project"
    (root / "wiki" / "concepts").mkdir(parents=True)
    owner = root / "wiki" / "concepts" / "a.md"
    owner.write_text("---\ntitle: A\n---\n\nBody.\n", encoding="utf-8")

    outside = tmp_path / "secret.md"
    outside.write_text("not yours\n", encoding="utf-8")

    ctx = llmwiki.LintContext(root)
    got = llmwiki.resolve_source_ref(ctx, owner, "../../../secret.md", wiki_source=False)

    assert got is None, f"resolved to {got}, which is outside {root}"


def test_a_source_ref_inside_the_project_still_resolves(tmp_path):
    """The other side, so the boundary cannot be widened into refusing
    everything a card legitimately cites."""
    from magi.kb import llmwiki

    root = tmp_path / "project"
    (root / "wiki" / "concepts").mkdir(parents=True)
    (root / "raw").mkdir(parents=True)
    owner = root / "wiki" / "concepts" / "a.md"
    owner.write_text("---\ntitle: A\n---\n\nBody.\n", encoding="utf-8")
    paper = root / "raw" / "paper.md"
    paper.write_text("# P\n", encoding="utf-8")

    ctx = llmwiki.LintContext(root)
    got = llmwiki.resolve_source_ref(ctx, owner, "raw/paper.md", wiki_source=False)

    assert got is not None and got.name == "paper.md"
