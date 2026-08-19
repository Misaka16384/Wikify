"""Author threading through the radar pipeline: digest writer, parser, arXiv feed."""

from magi.radar import _arxiv_entry_authors, _candidate_lines, parse_digest_candidates


def _cand(authors: list[str] | None) -> dict:
    c = {
        "id": "2401.00001",
        "arxiv_id": "2401.00001",
        "doi": None,
        "title": "A Paper",
        "year": 2024,
        "abstract": "Short abstract.",
        "url": "https://arxiv.org/abs/2401.00001",
        "source": "arxiv-new:cs.CL",
    }
    if authors is not None:
        c["authors"] = authors
    return c


def _digest(*cands: dict) -> str:
    lines = ["---", "status: pending-review", "---", ""]
    for c in cands:
        lines += _candidate_lines(c)
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# _candidate_lines
# --------------------------------------------------------------------------

def test_candidate_lines_two_authors():
    lines = _candidate_lines(_cand(["Jane Q. Doe", "Wei Zhang"]))
    assert lines[0] == "## A Paper"
    id_idx = next(i for i, ln in enumerate(lines) if ln.startswith("- id: "))
    assert lines[id_idx + 1] == "- authors: Jane Q. Doe, Wei Zhang"
    assert lines[-1] != ""  # no trailing blank


def test_candidate_lines_eight_authors_truncates_with_et_al():
    names = [f"Author {i}" for i in range(8)]
    lines = _candidate_lines(_cand(names))
    auth = [ln for ln in lines if ln.startswith("- authors: ")]
    assert auth == ["- authors: " + ", ".join(names[:6]) + ", et al."]


def test_candidate_lines_no_authors_no_line():
    for c in (_cand(None), _cand([])):
        assert not [ln for ln in _candidate_lines(c) if ln.startswith("- authors:")]


# --------------------------------------------------------------------------
# parse_digest_candidates round-trip
# --------------------------------------------------------------------------

def test_round_trip_few_authors_exact():
    names = ["Jane Q. Doe", "Wei Zhang", "A. B. Cohen"]
    parsed = parse_digest_candidates(_digest(_cand(names)))
    assert len(parsed) == 1
    assert parsed[0]["authors"] == names
    assert parsed[0]["id"] == "2401.00001"
    assert parsed[0]["arxiv_id"] == "2401.00001"


def test_round_trip_many_authors_drops_et_al():
    names = [f"Author {i}" for i in range(8)]
    parsed = parse_digest_candidates(_digest(_cand(names)))
    assert parsed[0]["authors"] == names[:6]


def test_authorless_section_parses_with_empty_authors():
    parsed = parse_digest_candidates(_digest(_cand(None), _cand(["Solo Author"])))
    assert len(parsed) == 2
    assert parsed[0]["authors"] == []
    assert parsed[1]["authors"] == ["Solo Author"]
    assert parsed[0]["url"] == "https://arxiv.org/abs/2401.00001"


# --------------------------------------------------------------------------
# arXiv Atom author extraction
# --------------------------------------------------------------------------

ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>ArXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>First Paper</title>
    <published>2024-01-01T00:00:00Z</published>
    <author>
      <name>Jane Q.
        Doe</name>
    </author>
    <author><name>Wei Zhang</name><arxiv:affiliation>Some Lab</arxiv:affiliation></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v2</id>
    <title>Second Paper</title>
    <published>2024-01-02T00:00:00Z</published>
    <author>
      <name>Solo Author</name>
    </author>
  </entry>
</feed>
"""


def test_arxiv_entry_authors_extraction():
    entries = ATOM_FEED.split("<entry>")[1:]
    assert len(entries) == 2
    assert _arxiv_entry_authors(entries[0]) == ["Jane Q. Doe", "Wei Zhang"]
    assert _arxiv_entry_authors(entries[1]) == ["Solo Author"]


def test_arxiv_entry_authors_none():
    assert _arxiv_entry_authors("<id>x</id><title>t</title>") == []
