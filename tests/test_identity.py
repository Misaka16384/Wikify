"""Contracts for identity resolution.

The numbers these encode came from measuring a real 758-item Zotero library:
28% of items carry an arXiv id in plain sight, 46% have only a DOI, and
Semantic Scholar maps ~73% of those back to arXiv. The batch endpoint takes 500
ids per request, which is the difference between one call and a quarter of an
hour of serial politeness.
"""

import pytest

from magi.ingest import identity as ident


# --------------------------------------------------------------------------
# The free pass: everything recoverable with no network
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("https://arxiv.org/abs/2405.00208", "2405.00208"),
    ("arXiv:1703.07038 [physics]", "1703.07038"),
    ("2608.16520.tar.gz", "2608.16520"),
    ("https://arxiv.org/abs/cond-mat/0506438", "cond-mat/0506438"),
])
def test_an_arxiv_id_in_the_text_costs_nothing(text, expected):
    got = ident.from_text(text)
    assert got.arxiv_id == expected
    assert got.source == "text"


@pytest.mark.parametrize("doi_text,expected", [
    ("10.48550/arXiv.2405.00208", "2405.00208"),
    ("10.48550/arxiv.1411.5815", "1411.5815"),
    ("None arxiv:1212.5121", "1212.5121"),
])
def test_an_arxiv_id_inside_the_doi_costs_nothing_either(doi_text, expected):
    """Seven of a real library's 351 DOI-only items are recoverable this way."""
    assert ident.arxiv_from_doi_text(doi_text) == expected


def test_a_plain_doi_yields_a_doi_and_no_arxiv_id():
    got = ident.from_text("https://doi.org/10.1103/PhysRevB.108.014301")
    assert got.doi == "10.1103/physrevb.108.014301"
    assert got.arxiv_id is None
    assert not got.resolved


def test_trailing_sentence_punctuation_is_not_part_of_the_doi():
    assert ident.find_doi("see 10.1103/PhysRevB.108.014301.") == \
        "10.1103/physrevb.108.014301"


def test_nothing_in_the_text_is_not_an_error():
    got = ident.from_text("just some prose")
    assert got == ident.Identity(None, None, "")


def test_empty_input_is_handled():
    assert ident.from_text(None).arxiv_id is None
    assert ident.find_doi(None) is None


# --------------------------------------------------------------------------
# The batch endpoint
# --------------------------------------------------------------------------

def test_a_whole_library_is_a_handful_of_requests_not_hundreds(monkeypatch):
    """The entire reason to use the batch endpoint.

    351 DOIs one at a time, at the 1.1 s politeness this repo already keeps,
    is a quarter of an hour. Batched it is four requests.
    """
    calls = []

    def fake_json(url, payload=None, timeout=60, throttle=None):
        calls.append(len(payload["ids"]))
        return [{"externalIds": {"ArXiv": "1303.4301"}, "title": "T"}
                for _ in payload["ids"]]

    monkeypatch.setattr(ident, "http_json", fake_json)
    ident.resolve_dois([f"10.1103/PhysRevB.{i}" for i in range(351)])

    assert len(calls) == 4
    assert sum(calls) == 351


def test_the_batch_size_stays_under_the_rate_limit_not_the_documented_cap(monkeypatch):
    """500 per request is documented and 500 per request gets a 429.

    Measured against a real library: a batch of 295 was refused outright, and
    100 goes through. The cap that matters is the anonymous rate limit, not the
    number in the API reference.
    """
    calls = []

    def fake_json(url, payload=None, timeout=60, throttle=None):
        calls.append(len(payload["ids"]))
        return [None] * len(payload["ids"])

    monkeypatch.setattr(ident, "http_json", fake_json)
    ident.resolve_dois([f"10.1/{i}" for i in range(250)])

    assert calls == [100, 100, 50]
    assert max(calls) <= ident.S2_BATCH_LIMIT < ident.S2_DOCUMENTED_LIMIT


def test_dois_are_sent_with_the_doi_prefix(monkeypatch):
    sent = {}

    def fake_json(url, payload=None, timeout=60, throttle=None):
        sent["ids"] = payload["ids"]
        return [None]

    monkeypatch.setattr(ident, "http_json", fake_json)
    ident.resolve_dois(["10.1103/PhysRevB.28.3110"])

    assert sent["ids"] == ["DOI:10.1103/physrevb.28.3110"]


def test_a_null_record_means_unresolved_not_an_error(monkeypatch):
    """Semantic Scholar returns null in-place for ids it does not know."""
    monkeypatch.setattr(ident, "http_json",
                        lambda url, payload=None, timeout=60, throttle=None: [None])
    got = ident.resolve_dois(["10.1/unknown"])
    assert got["10.1/unknown"].arxiv_id is None


def test_the_response_is_matched_positionally(monkeypatch):
    """The batch response is aligned with the request, not keyed."""
    monkeypatch.setattr(
        ident, "http_json",
        lambda url, payload=None, timeout=60, throttle=None: [
            None,
            {"externalIds": {"ArXiv": "1234.5678"}, "title": "Second"},
        ])
    got = ident.resolve_dois(["10.1/a", "10.1/b"])

    assert got["10.1/a"].arxiv_id is None
    assert got["10.1/b"].arxiv_id == "1234.5678"


def test_duplicate_dois_are_looked_up_once(monkeypatch):
    sent = {}

    def fake_json(url, payload=None, timeout=60, throttle=None):
        sent["n"] = len(payload["ids"])
        return [None] * len(payload["ids"])

    monkeypatch.setattr(ident, "http_json", fake_json)
    ident.resolve_dois(["10.1/a", "10.1/A", "10.1/a"])
    assert sent["n"] == 1


def test_a_lookup_failure_degrades_instead_of_raising(monkeypatch):
    """A Semantic Scholar outage should cost coverage, not the whole import."""
    def boom(url, payload=None, timeout=60, throttle=None):
        raise RuntimeError("HTTP Error 503: Service Unavailable")

    monkeypatch.setattr(ident, "http_json", boom)
    got = ident.resolve_dois(["10.1/a"])

    assert got["10.1/a"].arxiv_id is None
    assert got["10.1/a"].doi == "10.1/a"


# --------------------------------------------------------------------------
# The wrong-paper guard
# --------------------------------------------------------------------------

def test_a_lookup_describing_a_different_paper_is_rejected(monkeypatch):
    """Silently following a bad DOI would ingest the wrong paper under our title,
    which is worse than not resolving at all."""
    monkeypatch.setattr(
        ident, "http_json",
        lambda url, payload=None, timeout=60, throttle=None: [
            {"externalIds": {"ArXiv": "9999.99999"},
             "title": "Completely Unrelated Work On Sheep Farming"}])

    got = ident.resolve_dois(["10.1/a"],
                             {"10.1/a": "String-net condensation and topological order"})

    assert got["10.1/a"].arxiv_id is None


def test_a_matching_title_is_accepted_despite_formatting_noise(monkeypatch):
    """Case and punctuation differ constantly between Zotero and S2."""
    monkeypatch.setattr(
        ident, "http_json",
        lambda url, payload=None, timeout=60, throttle=None: [
            {"externalIds": {"ArXiv": "1234.5678"},
             "title": "Anomalous Symmetry Fractionalization and Surface Topological Order"}])

    got = ident.resolve_dois(
        ["10.1/a"],
        {"10.1/a": "Anomalous symmetry fractionalization and surface topological order"})

    assert got["10.1/a"].arxiv_id == "1234.5678"


def test_no_local_title_means_the_doi_is_trusted(monkeypatch):
    """With nothing to compare against, the DOI itself is the evidence."""
    monkeypatch.setattr(
        ident, "http_json",
        lambda url, payload=None, timeout=60, throttle=None: [
            {"externalIds": {"ArXiv": "1234.5678"}, "title": "Whatever"}])

    got = ident.resolve_dois(["10.1/a"])
    assert got["10.1/a"].arxiv_id == "1234.5678"


@pytest.mark.parametrize("ours,theirs", [
    ("Fractons", "Fractons"),                       # one word, identical
    ("Fractons", "fractons"),                       # case only
    ("Anyons", "Anyons."),                          # trailing punctuation
    ("Quantum Hall", "Quantum Hall"),               # two words
])
def test_a_short_title_that_matches_exactly_is_accepted(monkeypatch, ours, theirs):
    """A fixed overlap floor cannot work: a one-word title can never produce
    three matching words, so identical short titles were rejected outright and
    quietly cost coverage on every paper with a terse name."""
    monkeypatch.setattr(
        ident, "http_json",
        lambda url, payload=None, timeout=60, throttle=None: [
            {"externalIds": {"ArXiv": "1234.5678"}, "title": theirs}])

    got = ident.resolve_dois(["10.1/a"], {"10.1/a": ours})
    assert got["10.1/a"].arxiv_id == "1234.5678"


def test_a_short_title_that_differs_is_still_rejected(monkeypatch):
    monkeypatch.setattr(
        ident, "http_json",
        lambda url, payload=None, timeout=60, throttle=None: [
            {"externalIds": {"ArXiv": "1234.5678"}, "title": "Anyons"}])

    got = ident.resolve_dois(["10.1/a"], {"10.1/a": "Fractons"})
    assert got["10.1/a"].arxiv_id is None


def test_a_zotero_title_with_a_leaked_journal_name_still_matches(monkeypatch):
    """Real row: 'Topological order in an exactly solvable 3D spin model, Ann'."""
    monkeypatch.setattr(
        ident, "http_json",
        lambda url, payload=None, timeout=60, throttle=None: [
            {"externalIds": {"ArXiv": "1234.5678"},
             "title": "Topological order in an exactly solvable 3D spin model"}])

    got = ident.resolve_dois(
        ["10.1/a"],
        {"10.1/a": "Topological order in an exactly solvable 3D spin model, Ann"})

    assert got["10.1/a"].arxiv_id == "1234.5678"


# --------------------------------------------------------------------------
# resolve() spends a request only when it would help
# --------------------------------------------------------------------------

def test_no_request_when_the_id_is_already_in_the_text(monkeypatch):
    monkeypatch.setattr(ident, "http_json",
                        lambda *a, **k: pytest.fail("should not have called out"))
    got = ident.resolve("https://arxiv.org/abs/2405.00208")
    assert got.arxiv_id == "2405.00208"


def test_no_request_when_there_is_no_doi_to_look_up(monkeypatch):
    monkeypatch.setattr(ident, "http_json",
                        lambda *a, **k: pytest.fail("should not have called out"))
    assert ident.resolve("just prose").arxiv_id is None


def test_network_can_be_refused(monkeypatch):
    monkeypatch.setattr(ident, "http_json",
                        lambda *a, **k: pytest.fail("should not have called out"))
    got = ident.resolve("10.1103/PhysRevB.108.014301", allow_network=False)
    assert got.doi and got.arxiv_id is None


def test_a_doi_only_input_does_reach_semantic_scholar(monkeypatch):
    monkeypatch.setattr(
        ident, "http_json",
        lambda url, payload=None, timeout=60, throttle=None: [
            {"externalIds": {"ArXiv": "1303.4301"}, "title": "T"}])

    got = ident.resolve("https://doi.org/10.1038/ncomms4507")
    assert got.arxiv_id == "1303.4301"
    assert got.source == "s2"
