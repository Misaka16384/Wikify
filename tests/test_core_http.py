"""Contracts for the shared HTTP layer.

The thing worth pinning here is that politeness is per host. arXiv asks for
Crawl-delay: 15 on /html but 3 s on the API, and Semantic Scholar wants ~1.1 s —
one global constant is either rude to one host or five times too slow for
another.
"""

import pytest

from magi.core import http as core_http


class FakeClock:
    """Monotonic time we control, so a 15 s delay costs no wall-clock seconds."""

    def __init__(self):
        self.now = 1000.0
        self.slept: list[float] = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(core_http.time, "monotonic", fake.monotonic)
    monkeypatch.setattr(core_http.time, "sleep", fake.sleep)
    return fake


# --------------------------------------------------------------------------
# Per-host delays
# --------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://arxiv.org/html/2608.16520", 15.0),
    ("https://ar5iv.labs.arxiv.org/html/cond-mat/0506438", 15.0),
    ("http://export.arxiv.org/api/query?search_query=cat:hep-th", 3.0),
    ("https://api.semanticscholar.org/graph/v1/paper/batch", 1.1),
])
def test_known_hosts_carry_their_own_delay(url, expected):
    assert core_http.Throttle().delay_for(url) == expected


def test_arxiv_html_is_five_times_stricter_than_the_api():
    """The one that is easy to get wrong: /html and the API are not the same host."""
    t = core_http.Throttle()
    assert t.delay_for("https://arxiv.org/html/2608.16520") == 15.0
    assert t.delay_for("http://export.arxiv.org/api/query") == 3.0


def test_an_unlisted_host_is_not_throttled():
    """Be explicit rather than inventing a default that is rude or slow."""
    assert core_http.Throttle().delay_for("https://example.com/x") == 0.0


def test_first_request_to_a_host_does_not_wait(clock):
    core_http.Throttle().wait("https://arxiv.org/html/2608.16520")
    assert clock.slept == []


def test_second_request_waits_out_the_remainder(clock):
    t = core_http.Throttle()
    t.wait("https://arxiv.org/html/a")
    clock.now += 4.0                      # 4 s of real work happened meanwhile
    t.wait("https://arxiv.org/html/b")
    assert clock.slept == [pytest.approx(11.0)]   # not the full 15


def test_no_wait_once_the_delay_has_already_elapsed(clock):
    t = core_http.Throttle()
    t.wait("https://arxiv.org/html/a")
    clock.now += 20.0
    t.wait("https://arxiv.org/html/b")
    assert clock.slept == []


def test_hosts_are_timed_independently(clock):
    """A slow arxiv.org request must not delay a Semantic Scholar one."""
    t = core_http.Throttle()
    t.wait("https://arxiv.org/html/a")
    t.wait("https://api.semanticscholar.org/graph/v1/paper/x")
    assert clock.slept == []


def test_delays_are_configurable_for_tests(clock):
    t = core_http.Throttle({"example.com": 2.0})
    t.wait("https://example.com/a")
    t.wait("https://example.com/b")
    assert clock.slept == [pytest.approx(2.0)]


def test_an_empty_delay_table_disables_throttling(clock):
    """radar opts out this way, so its own sleeps are not doubled."""
    t = core_http.Throttle({})
    for _ in range(3):
        t.wait("https://arxiv.org/html/a")
    assert clock.slept == []


# --------------------------------------------------------------------------
# retry_429
# --------------------------------------------------------------------------

def test_a_429_is_retried_once(monkeypatch):
    monkeypatch.setattr(core_http.time, "sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        return "ok"

    assert core_http.retry_429(flaky) == "ok"
    assert len(calls) == 2


def test_a_404_is_not_retried(monkeypatch):
    """Waiting does not turn a 404 into a 200; retrying only delays the caller."""
    monkeypatch.setattr(core_http.time, "sleep", lambda s: None)
    calls = []

    def missing():
        calls.append(1)
        raise RuntimeError("HTTP Error 404: Not Found")

    with pytest.raises(RuntimeError, match="404"):
        core_http.retry_429(missing)
    assert len(calls) == 1


def test_a_persistent_429_eventually_raises(monkeypatch):
    monkeypatch.setattr(core_http.time, "sleep", lambda s: None)
    calls = []

    def always_limited():
        calls.append(1)
        raise RuntimeError("HTTP Error 429: Too Many Requests")

    with pytest.raises(RuntimeError, match="429"):
        core_http.retry_429(always_limited, retries=2)
    assert len(calls) == 3


def test_a_clean_call_is_made_exactly_once(monkeypatch):
    monkeypatch.setattr(core_http.time, "sleep", lambda s: None)
    calls = []
    assert core_http.retry_429(lambda: calls.append(1) or "v") == "v"
    assert len(calls) == 1


# --------------------------------------------------------------------------
# Download atomicity
# --------------------------------------------------------------------------

def test_download_is_atomic_and_leaves_no_part_file(tmp_path, monkeypatch):
    monkeypatch.setattr(core_http, "http_get",
                        lambda url, timeout=120, throttle=None: (b"payload", "", url))
    dest = tmp_path / "nested" / "2608.16520.tar.gz"

    out = core_http.http_download("https://arxiv.org/e-print/2608.16520", dest)

    assert out == dest
    assert dest.read_bytes() == b"payload"
    assert not list(tmp_path.rglob("*.part"))


def test_a_failed_download_leaves_no_destination_file(tmp_path, monkeypatch):
    """An interrupted fetch must not look like a finished one to the next step."""
    def boom(url, timeout=120, throttle=None):
        raise RuntimeError("HTTP Error 500: Server Error")

    monkeypatch.setattr(core_http, "http_get", boom)
    dest = tmp_path / "2608.16520.tar.gz"

    with pytest.raises(RuntimeError):
        core_http.http_download("https://arxiv.org/e-print/2608.16520", dest)
    assert not dest.exists()


def test_user_agent_identifies_the_tool():
    assert "magi" in core_http.USER_AGENT.lower()
