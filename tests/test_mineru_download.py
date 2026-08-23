"""The download is where a finished, billed job gets lost.

MinerU converts on its own servers and charges for it there. By the time the
zip URL exists the work is done and paid for — and it was fetched once, with no
retry, so a network blip threw the whole job away. Measured: seven jobs in one
round, every one reported `Status: done`, every one lost.

The other half is what the failure says. "SSLError" sends the reader to look at
their document; the truth is that the extraction succeeded and one host is
unreachable, which sends them to look at their network.
"""

import types

import pytest

requests = pytest.importorskip("requests")

from magi.ingest import mineru  # noqa: E402


def _a_real_zip():
    """The smallest thing `convert` will accept: a zip holding one Markdown
    file. Anything less and the tests fail on unpacking rather than on the
    behaviour they are about."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("full.md", "# A paper\n\nSome converted text.\n")
    return buf.getvalue()


class _Resp:
    def __init__(self, status=200, content=None):
        self.status_code = status
        self.content = _a_real_zip() if content is None else content


def _downloads(monkeypatch, outcomes):
    """Stub requests.get for the download, counting the attempts."""
    seen = []

    def fake_get(url, **kw):
        seen.append(url)
        outcome = outcomes[min(len(seen) - 1, len(outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(mineru.requests, "get", fake_get)
    monkeypatch.setattr(mineru.time, "sleep", lambda _s: None)
    return seen


def _run_download(monkeypatch, outcomes, tmp_path):
    """Drive just the download half of `convert`, via a stubbed poll."""
    seen = _downloads(monkeypatch, outcomes)
    # Everything before the download is stubbed to succeed.
    monkeypatch.setattr(mineru, "load_config",
                        lambda *a, **k: {"ocr": {"mineru_api_token": "t"}})
    monkeypatch.setattr(mineru.requests, "post", lambda *a, **k: types.SimpleNamespace(
        status_code=200,
        json=lambda: {"code": 0, "data": {"batch_id": "b",
                                          "file_urls": ["https://up.example/1"]}}))
    monkeypatch.setattr(mineru.requests, "put", lambda *a, **k: _Resp())

    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(b"%PDF-1.7")

    calls = {"n": 0}
    real_get = mineru.requests.get

    def get_router(url, **kw):
        # The poll endpoint answers "done" once; everything else is the download.
        if "extract-results" in url:
            calls["n"] += 1
            return types.SimpleNamespace(
                status_code=200,
                json=lambda: {"code": 0, "data": {"extract_result": [
                    {"state": "done",
                     "full_zip_url": "https://cdn.example/r.zip"}]}})
        return real_get(url, **kw)

    monkeypatch.setattr(mineru.requests, "get", get_router)
    result = mineru.convert(str(pdf), str(tmp_path / "out"))
    return result, [u for u in seen if "extract-results" not in u]


# --------------------------------------------------------------------------
# Retrying
# --------------------------------------------------------------------------

def test_a_transient_failure_is_retried(monkeypatch, tmp_path, capsys):
    """One blip must not throw away work that is already done and billed."""
    result, downloads = _run_download(
        monkeypatch,
        [requests.exceptions.SSLError("EOF in violation of protocol"), _Resp()],
        tmp_path)

    assert len(downloads) == 2
    assert "retrying" in capsys.readouterr().out


def test_it_gives_up_after_a_bounded_number_of_attempts(monkeypatch, tmp_path):
    """Bounded, because an unreachable host stays unreachable and the caller
    has a ladder underneath it."""
    result, downloads = _run_download(
        monkeypatch, [requests.exceptions.SSLError("nope")], tmp_path)

    assert len(downloads) == mineru.DOWNLOAD_ATTEMPTS
    assert not result.success


def test_an_http_error_is_retried_too(monkeypatch, tmp_path):
    """A 502 from a CDN is exactly as transient as a dropped handshake."""
    _, downloads = _run_download(monkeypatch, [_Resp(status=502), _Resp()], tmp_path)
    assert len(downloads) == 2


def test_a_first_time_success_does_not_retry(monkeypatch, tmp_path):
    _, downloads = _run_download(monkeypatch, [_Resp()], tmp_path)
    assert len(downloads) == 1


# --------------------------------------------------------------------------
# What the failure says
# --------------------------------------------------------------------------

def test_the_error_says_the_extraction_already_succeeded(monkeypatch, tmp_path):
    """Otherwise the reader debugs their PDF. The quota is spent either way,
    and knowing that is what makes the next decision different."""
    result, _ = _run_download(
        monkeypatch, [requests.exceptions.SSLError("boom")], tmp_path)

    detail = " ".join(result.errors).lower()
    assert "succeeded" in detail
    assert "quota" in detail


def test_the_error_names_the_host_that_could_not_be_reached(monkeypatch, tmp_path):
    """The API host and the result host are different machines, and only one of
    them was down. Naming it is the difference between a five-minute proxy rule
    and an afternoon."""
    result, _ = _run_download(
        monkeypatch, [requests.exceptions.SSLError("boom")], tmp_path)

    assert "cdn.example" in " ".join(result.errors)


# --------------------------------------------------------------------------
# The workaround that never ran
# --------------------------------------------------------------------------

def test_the_conversion_does_not_touch_the_process_proxy_settings(monkeypatch, tmp_path):
    """Two lines used to pop `http_proxy`/`https_proxy` here, commented "unset
    proxy to avoid SSLEOFError". They never executed anything: the variables
    are spelled in upper case, which is what `requests` reads.

    And the intent was wrong anyway — the API host works *through* the proxy
    and only the result host fails, so dropping it would break the half that
    works. Mutating os.environ inside a conversion would also reroute every
    other request in the process.
    """
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7890")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")

    _run_download(monkeypatch, [_Resp()], tmp_path)

    import os
    assert os.environ.get("HTTP_PROXY") == "http://127.0.0.1:7890"
    assert os.environ.get("HTTPS_PROXY") == "http://127.0.0.1:7890"


def test_no_proxy_environment_variable_is_popped_anywhere_in_the_module():
    """Structural, so the workaround cannot come back in the other case."""
    import inspect

    src = inspect.getsource(mineru)
    live = [l for l in src.splitlines()
            if l.strip() and not l.strip().startswith("#")]
    for line in live:
        assert "environ.pop" not in line, line
