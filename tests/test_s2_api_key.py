"""The Semantic Scholar key: where it comes from, and where it must not go.

`magi.core.http` had no way to send a header at all — every caller got a fixed
User-Agent and nothing else — so an API that authenticates by header could not
be reached through these helpers without a second HTTP layer beside them.

The property that matters more than the feature: `radar.py` talks to Semantic
Scholar and to arXiv through the *same two* helper functions. A key attached
at the helper, or read once and passed down, is a key mailed to arxiv.org on
every harvest. So the decision is made per host, at the point of sending, and
that is what most of these tests are about.
"""

import pytest

from magi import radar
from magi.core import http

CFG = {"radar": {"s2_api_key": "sk-secret"}}


# --------------------------------------------------------------------------
# where the key must not go
# --------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://export.arxiv.org/api/query?search_query=cat:hep-th",
    "https://arxiv.org/abs/2608.11111",
    "https://ar5iv.labs.arxiv.org/html/2608.11111",
    "https://example.com/api.semanticscholar.org",       # host is example.com
    "https://api.semanticscholar.org.evil.test/x",       # suffix, not the host
])
def test_no_other_host_is_ever_sent_the_key(url):
    assert radar._auth_headers(url, CFG) is None, url


def test_the_semantic_scholar_host_is_sent_the_key():
    got = radar._auth_headers("https://api.semanticscholar.org/graph/v1/paper/x", CFG)
    assert got == {"x-api-key": "sk-secret"}


def test_no_key_configured_sends_no_header():
    """Unauthenticated is the supported default, not a degraded mode."""
    assert radar._auth_headers("https://api.semanticscholar.org/x", {}) is None


def test_an_empty_key_is_not_a_key():
    assert radar._auth_headers("https://api.semanticscholar.org/x",
                               {"radar": {"s2_api_key": "   "}}) is None


# --------------------------------------------------------------------------
# where it comes from
# --------------------------------------------------------------------------

def test_the_environment_wins_over_the_file(monkeypatch):
    """A key in config.yaml is a key in a file people put in git."""
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "from-env")
    assert radar.s2_api_key(CFG) == "from-env"


def test_the_file_is_the_fallback(monkeypatch):
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    assert radar.s2_api_key(CFG) == "sk-secret"


def test_the_variable_name_is_configurable(monkeypatch):
    monkeypatch.setenv("MY_OWN_VAR", "elsewhere")
    cfg = {"radar": {"s2_api_key": "sk-secret", "s2_api_key_env": "MY_OWN_VAR"}}
    assert radar.s2_api_key(cfg) == "elsewhere"


def test_whitespace_around_a_key_is_not_part_of_it(monkeypatch):
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "  padded  ")
    assert radar.s2_api_key({}) == "padded"


# --------------------------------------------------------------------------
# the transport
# --------------------------------------------------------------------------

def test_headers_reach_the_request():
    req = http._request("https://example.test/x", headers={"x-api-key": "k"})
    assert req.get_header("X-api-key") == "k"


def test_the_user_agent_survives_a_custom_header():
    req = http._request("https://example.test/x", headers={"x-api-key": "k"})
    assert req.get_header("User-agent") == http.USER_AGENT


def test_an_empty_header_value_is_dropped_not_sent_blank():
    req = http._request("https://example.test/x", headers={"x-api-key": ""})
    assert req.get_header("X-api-key") is None


def test_sending_no_headers_is_unchanged():
    req = http._request("https://example.test/x")
    assert req.get_header("User-agent") == http.USER_AGENT
    assert req.get_header("X-api-key") is None


# --------------------------------------------------------------------------
# end to end through radar's own wrappers
# --------------------------------------------------------------------------

def test_radars_json_helper_authenticates_only_semantic_scholar(monkeypatch):
    seen = {}

    def fake(url, payload=None, timeout=60, *, throttle=None, headers=None):
        seen[url] = headers
        return {}

    monkeypatch.setattr(radar, "core_http_json", fake)
    radar._http_json("https://api.semanticscholar.org/graph/v1/paper/x", cfg=CFG)
    radar._http_json("https://export.arxiv.org/api/query?x=1", cfg=CFG)

    assert seen["https://api.semanticscholar.org/graph/v1/paper/x"] == {"x-api-key": "sk-secret"}
    assert seen["https://export.arxiv.org/api/query?x=1"] is None


def test_radars_text_helper_does_the_same(monkeypatch):
    seen = {}

    def fake(url, timeout=60, *, throttle=None, headers=None):
        seen[url] = headers
        return ""

    monkeypatch.setattr(radar, "core_http_text", fake)
    radar._http_text("https://export.arxiv.org/api/query?x=1", cfg=CFG)
    assert seen["https://export.arxiv.org/api/query?x=1"] is None


# --------------------------------------------------------------------------
# the third leg: the only one that can look backwards
# --------------------------------------------------------------------------

def test_bulk_search_is_off_until_somebody_writes_a_query():
    """A query list is a statement about what you are looking for. Guessing
    one from the library would produce confident noise, so empty means off and
    costs nothing."""
    assert radar.harvest_s2_bulk([], 40) == ([], [])


def test_bulk_search_asks_the_endpoint_that_can_see_old_papers(monkeypatch):
    seen = {}

    def fake(url, payload=None, timeout=60, cfg=None):
        seen["url"] = url
        return {"data": [{"title": "Fractons", "year": 2021,
                          "externalIds": {"ArXiv": "2101.00001"},
                          "abstract": "a", "authors": [{"name": "A"}]}]}

    monkeypatch.setattr(radar, "_http_json", fake)
    out, failed = radar.harvest_s2_bulk(["fracton order"], 40, years="2020-")

    assert "/paper/search/bulk" in seen["url"], seen["url"]
    assert "year=2020-" in seen["url"]
    assert failed == []
    assert out[0]["arxiv_id"] == "2101.00001"
    assert out[0]["source"] == "s2-bulk-search"


def test_a_failing_query_does_not_lose_the_others(monkeypatch):
    calls = {"n": 0}

    def fake(url, payload=None, timeout=60, cfg=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return {"data": [{"title": "Kept", "externalIds": {}, "authors": []}]}

    monkeypatch.setattr(radar, "_http_json", fake)
    monkeypatch.setattr(radar.time, "sleep", lambda _s: None)
    out, failed = radar.harvest_s2_bulk(["bad", "good"], 40)

    assert [c["title"] for c in out] == ["Kept"]
    assert failed == ["s2-bulk:bad"]


def test_a_result_with_no_title_cannot_be_triaged_so_it_is_dropped(monkeypatch):
    monkeypatch.setattr(radar, "_http_json",
                        lambda *a, **k: {"data": [{"title": "  ", "externalIds": {}}]})
    out, _ = radar.harvest_s2_bulk(["q"], 40)
    assert out == []


def test_the_key_is_not_read_from_wherever_the_process_happens_to_stand(tmp_path,
                                                                        monkeypatch):
    """The first version called `load_config()` with no `start=`, which reads
    the current directory. The key lives in the *workspace* config, and the
    radar's whole point is unattended scheduled runs whose working directory is
    wherever the scheduler put them — so it would have quietly gone back to
    being unauthenticated exactly when nobody was watching.

    A repo guard caught it; this is the behaviour that guard is standing in
    for."""
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    (tmp_path / "config.yaml").write_text(
        "radar:\n  s2_api_key: from-the-cwd\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    # No cfg passed: the surrounding directory must not supply one.
    assert radar.s2_api_key() == ""
    assert radar._auth_headers("https://api.semanticscholar.org/x") is None

    # The workspace's own config still works, because it is handed in.
    assert radar.s2_api_key({"radar": {"s2_api_key": "from-the-workspace"}}) \
        == "from-the-workspace"


def test_the_environment_still_works_without_a_config(monkeypatch):
    """It is the one source that does not depend on where the process stands,
    which is why it stays available when cfg is absent."""
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "from-env")
    assert radar.s2_api_key() == "from-env"
