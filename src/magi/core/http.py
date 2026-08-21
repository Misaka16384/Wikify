"""Shared HTTP for the parts of MAGI that reach the network.

There was no such module: radar.py owned the only client, and politeness was a
bare ``time.sleep(3)`` sitting inside one loop and a bare ``time.sleep(1.1)``
repeated at five call sites. A second caller could only import a private
function or copy the sleeps, and both roads end with two throttles that
disagree.

Politeness here is **per host**, because the hosts do not agree either:

  * ``export.arxiv.org``      1 request / 3 s   (arXiv API guidance)
  * ``arxiv.org``            1 request / 15 s   (``Crawl-delay: 15`` in robots.txt for /html)
  * ``ar5iv.labs.arxiv.org``  1 request / 15 s   (same pipeline, treat it the same)
  * ``api.semanticscholar.org`` 1 request / 1.1 s

Still urllib, deliberately, not requests: :func:`retry_429` decides whether to
retry by looking for ``"429"`` in ``str(exc)``, which matches how urllib's
``HTTPError`` renders itself. requests formats its exceptions differently and
that check would quietly stop firing.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "magi-radar/0.1 (research workspace tool)"

# Seconds between requests to a host. A host not listed here is not throttled —
# be explicit rather than inventing a default that is either rude or slow.
HOST_DELAYS: dict[str, float] = {
    "arxiv.org": 15.0,
    "www.arxiv.org": 15.0,
    "ar5iv.labs.arxiv.org": 15.0,
    "ar5iv.org": 15.0,
    "export.arxiv.org": 3.0,
    "api.semanticscholar.org": 1.1,
}


class Throttle:
    """Per-host request spacing, shared across threads.

    Records when a host was last hit and sleeps out the remainder of its delay
    before the next one. Process-local: it bounds *our* politeness, not a
    global rate limit.
    """

    def __init__(self, delays: dict[str, float] | None = None):
        self._delays = dict(delays if delays is not None else HOST_DELAYS)
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def delay_for(self, url: str) -> float:
        host = urllib.parse.urlsplit(url).hostname or ""
        return self._delays.get(host.lower(), 0.0)

    def wait(self, url: str) -> None:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        delay = self._delays.get(host, 0.0)
        if delay <= 0:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                earliest = self._last.get(host, 0.0) + delay
                if now >= earliest:
                    self._last[host] = now
                    return
                sleep_for = earliest - now
            # Sleep outside the lock so a slow host cannot block another one.
            time.sleep(sleep_for)


#: Module-level default so callers share one set of timers rather than each
#: creating a Throttle that knows nothing about the others' requests.
THROTTLE = Throttle()


def _request(url: str, data: bytes | None = None, *, json_body: bool = False):
    headers = {"User-Agent": USER_AGENT}
    if json_body:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(url, data=data, headers=headers)


def http_json(url: str, payload: dict | None = None, timeout: int = 60,
              *, throttle: Throttle | None = None) -> dict:
    """GET (or POST, when ``payload`` is given) and parse JSON."""
    (throttle or THROTTLE).wait(url)
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    with urllib.request.urlopen(
            _request(url, data, json_body=True), timeout=timeout) as r:
        return json.load(r)


def http_text(url: str, timeout: int = 60,
              *, throttle: Throttle | None = None) -> str:
    (throttle or THROTTLE).wait(url)
    with urllib.request.urlopen(_request(url), timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def http_get(url: str, timeout: int = 60,
             *, throttle: Throttle | None = None) -> tuple[bytes, str, str]:
    """Fetch raw bytes.

    Returns ``(body, content_type, final_url)``. The final URL matters: arXiv's
    HTML endpoint answers a missing paper by redirecting to the abstract page,
    so a 200 alone does not mean the thing you asked for exists.
    """
    (throttle or THROTTLE).wait(url)
    with urllib.request.urlopen(_request(url), timeout=timeout) as r:
        return (r.read(),
                r.headers.get("Content-Type", ""),
                r.geturl())


def http_download(url: str, dest: Path | str, timeout: int = 120,
                  *, throttle: Throttle | None = None) -> Path:
    """Fetch to a file, atomically. Returns the destination path.

    Writes to a sibling ``.part`` and renames, so an interrupted download can
    never be mistaken for a complete one by whatever runs next.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    body, _, _ = http_get(url, timeout=timeout, throttle=throttle)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    return dest


def retry_429(fn, *, retries: int = 1, backoff: float = 5.0):
    """Call ``fn``, retrying only on a rate-limit response.

    Any other failure is raised immediately: a 404 will not become a 404 by
    waiting, and burning the retry budget on it delays the caller for nothing.
    """
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — urllib raises a family of these
            if attempt < retries and "429" in str(exc):
                time.sleep(backoff)
                continue
            raise
