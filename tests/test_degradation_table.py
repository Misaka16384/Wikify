"""`docs/degradation.md` is a design document and a checklist, so it is checked.

D6: MAGI leans on eleven things it does not control and none of them offers a
version to pin — seven network services, and the four ways v2 depends on other
people's programs on this machine (a reviewer CLI, its answer, five vendors'
session stores, and the call budget that pays for them). The table says what
the product degrades to when each one goes away, and what the user sees while
it happens.

A table nobody verifies rots into a promise. These tests keep two things true:
every row names a code path that still exists, and the fallbacks the rows
describe are still in the code. They cannot prove the fallback *works* against
a real outage — that gap is stated in the document itself rather than papered
over here.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "degradation.md"


@pytest.fixture(scope="module")
def rows():
    body = DOC.read_text(encoding="utf-8")
    table = [l for l in body.splitlines() if l.startswith("|")]
    assert len(table) > 5, "the degradation table is missing or empty"
    out = []
    for line in table[2:]:                     # skip header and separator
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == 5:
            out.append(cells)
    return out


def test_the_document_exists_and_has_rows(rows):
    assert len(rows) >= 11, "fewer upstreams listed than the project actually uses"


def test_every_row_says_what_the_user_sees(rows):
    """The rule the table encodes: an outage changes how well MAGI works, never
    whether the user is told."""
    silent = [r[0] for r in rows if not r[3] or r[3] == "—"]
    assert not silent, f"these rows do not say what the user sees: {silent}"


def test_every_named_code_path_still_exists(rows):
    """A row pointing at a file that has moved is worse than no row."""
    missing = []
    for row in rows:
        for path in re.findall(r"`([a-z_0-9/]+\.py)[^`]*`", row[4]):
            if not (REPO / "src" / "magi" / path).is_file():
                missing.append(f"{row[0]} -> {path}")
    assert not missing, f"named but absent: {missing}"


def test_the_ar5iv_fallback_is_still_there():
    body = (REPO / "src" / "magi" / "ingest" / "arxiv_html.py").read_text(encoding="utf-8")
    assert "ar5iv" in body


def test_the_mineru_download_still_retries():
    body = (REPO / "src" / "magi" / "ingest" / "mineru.py").read_text(encoding="utf-8")
    assert "DOWNLOAD_ATTEMPTS" in body
    assert "already spent" in body, "the billed-but-undelivered wording is the point"


def test_search_still_reports_a_degraded_vector_leg():
    body = (REPO / "src" / "magi" / "retrieval.py").read_text(encoding="utf-8")
    assert "vector_degraded" in body


def test_the_semantic_scholar_retry_still_matches_on_429():
    body = (REPO / "src" / "magi" / "radar.py").read_text(encoding="utf-8")
    assert '"429" in str(exc)' in body


def test_an_unparseable_verdict_is_still_unclear_and_never_a_pass():
    """The row promises a reviewer that rambles cannot become an approval."""
    from magi import review

    assert review.parse_verdict("I would rather not say.")[0] == review.VERDICT_UNCLEAR
    assert review.parse_verdict("VERDICT: stands\nVERDICT: refuted")[0] == \
        review.VERDICT_UNCLEAR


def test_a_review_still_falls_back_to_another_vendor_then_to_the_same_one():
    from magi import review

    assert review.pick_host("claude", installed=["claude", "codex"]) == "codex"
    assert review.pick_host("claude", installed=["claude"]) == "claude"
    assert review.pick_host("claude", installed=[]) is None


def test_one_unreadable_host_still_does_not_stop_the_sweep():
    body = (REPO / "src" / "magi" / "reflect" / "transcripts.py").read_text(encoding="utf-8")
    assert "result.unreadable[name]" in body, \
        "the sweep must report what it could not read rather than raise"


def test_the_budget_is_still_counted_in_calls():
    """Calls, not money: a headless CLI does not say what a request cost, and a
    budget denominated in a number nobody can measure never refuses anything."""
    body = (REPO / "src" / "magi" / "core" / "ledger.py").read_text(encoding="utf-8")
    assert "DEFAULT_WEEKLY" in body
    assert "budget is spent" in body


def test_the_document_states_its_own_gaps():
    body = re.sub(r"[*_`]", "", DOC.read_text(encoding="utf-8")).lower()
    assert "not covered" in body, "a table without its limits reads as a guarantee"
