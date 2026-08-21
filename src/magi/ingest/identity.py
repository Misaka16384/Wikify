"""Working out which paper a URL, DOI, or Zotero row actually refers to.

Acquisition needs one thing before it can do anything well: an arXiv identifier.
With one we can fetch LaTeXML HTML or the source tarball, both of which keep
formulas as formulas. Without one we are down to converting a PDF.

Measured against a real 758-item library, the identifier is sitting in plain
sight only 28% of the time. The largest single bucket — 46% — is items that have
a DOI and no arXiv id anywhere, and Semantic Scholar maps about 73% of those
back to arXiv. That lookup is therefore not a nicety; it roughly doubles how
often the good routes are available.

It is also nearly free, which is the part that is easy to get wrong. Semantic
Scholar's batch endpoint takes 500 ids per request, so a whole library is one
POST. Written as a 1.1 s serial loop it would be a quarter of an hour.
"""

from __future__ import annotations

import re
from typing import Iterable, NamedTuple

from magi.core.arxiv_id import find_arxiv_id, normalize_arxiv_id
from magi.core.http import http_json, retry_429

S2_BASE = "https://api.semanticscholar.org/graph/v1/paper"
S2_BATCH = f"{S2_BASE}/batch"
S2_BATCH_LIMIT = 500          # documented cap, and the whole point of using it

# A DOI as it appears in the wild. Deliberately loose on the suffix — publishers
# put almost anything there — but strict on the 10.NNNN/ prefix.
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>,]+)", re.IGNORECASE)

# arXiv mints DOIs for its own papers. When that is the DOI we have, the
# identifier is already in our hands and no lookup is needed.
_ARXIV_DOI_RE = re.compile(r"10\.48550/arxiv\.(.+)$", re.IGNORECASE)


class Identity(NamedTuple):
    """What we managed to learn about one item."""

    arxiv_id: str | None
    doi: str | None
    source: str          # how we got the arxiv_id: "url" | "text" | "doi-text" | "s2" | ""
    title: str | None = None

    @property
    def resolved(self) -> bool:
        return self.arxiv_id is not None


def find_doi(text: str | None) -> str | None:
    if not text:
        return None
    m = DOI_RE.search(text)
    if not m:
        return None
    # Trailing punctuation is nearly always the sentence, not the identifier.
    return m.group(1).rstrip(".,;)]}").lower()


def arxiv_from_doi_text(doi: str | None) -> str | None:
    """An arXiv id hiding inside the DOI itself — no network needed.

    Two real shapes, both measured in a live Zotero library: the official
    ``10.48550/arXiv.2405.00208``, and rows where an importer wrote something
    like ``None arxiv:1212.5121`` into the DOI field.
    """
    if not doi:
        return None
    m = _ARXIV_DOI_RE.search(doi)
    if m:
        return normalize_arxiv_id(m.group(1))
    return normalize_arxiv_id(doi) if "arxiv" in doi.lower() else None


def from_text(text: str | None) -> Identity:
    """Everything recoverable from a string, with no network at all.

    Handles a URL, a citation line, a Zotero ``Extra`` field, a bare id, or a
    filename. This is the cheap pass; run it before spending a request.
    """
    arxiv = find_arxiv_id(text)
    doi = find_doi(text)
    if arxiv:
        return Identity(normalize_arxiv_id(arxiv), doi, "text")
    embedded = arxiv_from_doi_text(doi)
    if embedded:
        return Identity(embedded, doi, "doi-text")
    return Identity(None, doi, "")


def _batch_lookup(dois: list[str], *, timeout: int = 60) -> dict[str, dict]:
    """One POST for up to 500 DOIs. Returns {doi: paper-record}."""
    if not dois:
        return {}
    url = f"{S2_BATCH}?fields=externalIds,title,year"
    payload = {"ids": [f"DOI:{d}" for d in dois]}
    data = retry_429(lambda: http_json(url, payload, timeout=timeout))
    # The response is a list positionally aligned with the request, with null
    # for anything Semantic Scholar does not know. Zipping is the contract.
    out: dict[str, dict] = {}
    if not isinstance(data, list):
        return out
    for doi, record in zip(dois, data):
        if record:
            out[doi] = record
    return out


def _titles_match(ours: str | None, theirs: str | None) -> bool:
    """Loose comparison, because a DOI lookup returning the wrong paper is
    worse than no answer — it would ingest a different paper under our title.

    Case, punctuation, and whitespace vary constantly between a Zotero row and
    a Semantic Scholar record; the words do not.
    """
    if not ours or not theirs:
        return True          # nothing to contradict; the DOI is the evidence
    norm = lambda s: re.sub(r"[^a-z0-9 ]+", " ", s.lower()).split()
    a, b = norm(ours), norm(theirs)
    if not a or not b:
        return True
    overlap = len(set(a) & set(b))
    return overlap >= max(3, min(len(a), len(b)) // 2)


def resolve_dois(dois: Iterable[str], titles: dict[str, str] | None = None,
                 *, timeout: int = 60) -> dict[str, Identity]:
    """Map DOIs to arXiv identifiers, in batches of 500.

    ``titles`` lets the caller pass what it believes each DOI is, so a lookup
    that comes back describing a different paper can be rejected rather than
    silently followed.
    """
    titles = titles or {}
    unique = list(dict.fromkeys(d.lower() for d in dois if d))
    resolved: dict[str, Identity] = {}

    for start in range(0, len(unique), S2_BATCH_LIMIT):
        chunk = unique[start:start + S2_BATCH_LIMIT]
        try:
            found = _batch_lookup(chunk, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 — a lookup failure is not fatal
            print(f"[identity] Semantic Scholar lookup failed for "
                  f"{len(chunk)} DOI(s): {exc}")
            found = {}
        for doi in chunk:
            record = found.get(doi)
            if not record:
                resolved[doi] = Identity(None, doi, "")
                continue
            arxiv = normalize_arxiv_id(
                (record.get("externalIds") or {}).get("ArXiv") or "")
            their_title = record.get("title")
            if arxiv and not _titles_match(titles.get(doi), their_title):
                print(f"[identity] {doi}: Semantic Scholar returned a different "
                      f"paper ({their_title!r}); not using its arXiv id")
                resolved[doi] = Identity(None, doi, "", their_title)
                continue
            resolved[doi] = Identity(arxiv, doi, "s2" if arxiv else "", their_title)
    return resolved


def resolve(text: str | None, *, allow_network: bool = True,
            title: str | None = None) -> Identity:
    """Best identity for one thing, spending a request only if it would help."""
    local = from_text(text)
    if local.resolved or not local.doi or not allow_network:
        return local
    found = resolve_dois([local.doi], {local.doi: title} if title else None)
    return found.get(local.doi, local)
