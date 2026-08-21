"""One arXiv identifier regex for the whole codebase.

There were two copies of this pattern (radar.py and tex2md.py) and both matched
only the modern ``YYMM.NNNNN`` form. Measuring a real 758-item library found 18
of 213 resolvable identifiers in the pre-2007 ``archive/YYMMNNN`` form —
``cond-mat/0506438``, ``hep-th/9711200`` — so a modern-only pattern silently
drops most of a physics library's older half.

Both forms carry an optional ``vN`` suffix, which is part of the identifier for
fetching but not for identity: two versions are the same paper.
"""

from __future__ import annotations

import re

# Modern: 0704.0001 onwards. Four digits, dot, four or five digits.
_MODERN = r"\d{4}\.\d{4,5}"

# Legacy: archive[.subject-class]/YYMMNNN, used until March 2007.
#
# Enumerated, not shape-matched. arXiv stopped issuing these in 2007, so the
# list is closed and can never grow — enumerating it is exact, not brittle.
# Shape-matching (`[a-z-]+/\d{7}`) is what would be brittle: it happily reads
# `figures/1234567` out of a markdown body as a paper identifier, and radar
# scans free text for exactly this.
_LEGACY_ARCHIVES = (
    "acc-phys", "adap-org", "alg-geom", "ao-sci", "astro-ph", "atom-ph",
    "bayes-an", "chao-dyn", "chem-ph", "cmp-lg", "comp-gas", "cond-mat",
    "cs", "dg-ga", "funct-an", "gr-qc", "hep-ex", "hep-lat", "hep-ph",
    "hep-th", "math", "math-ph", "mtrl-th", "nlin", "nucl-ex", "nucl-th",
    "patt-sol", "physics", "plasm-ph", "q-alg", "q-bio", "quant-ph",
    "solv-int", "supr-con",
)
# Longest first so `math-ph` cannot be shadowed by `math`.
_ARCHIVE_ALT = "|".join(sorted(_LEGACY_ARCHIVES, key=len, reverse=True))
# Case-insensitive on the way in: these arrive from Zotero fields and URLs
# where COND-MAT/0506438 is a real thing people have typed.
_LEGACY = rf"(?i:{_ARCHIVE_ALT})(?:\.[A-Za-z]{{2}})?/\d{{7}}"

ARXIV_ID_RE = re.compile(rf"\b({_MODERN}|{_LEGACY})(v\d+)?\b")

# For pulling an id out of a URL or a free-text field such as Zotero's `Extra`
# (`arXiv:1703.07038 [physics]`) or a DOI (`10.48550/arXiv.2405.00208`).
ARXIV_IN_TEXT_RE = re.compile(
    rf"(?:arxiv[:.\s/]*|abs/|pdf/|e-print/)({_MODERN}|{_LEGACY})(v\d+)?",
    re.IGNORECASE,
)


def find_arxiv_id(text: str | None, *, keep_version: bool = False) -> str | None:
    """First arXiv id in ``text``, or None.

    Tries the labelled forms first (``arXiv:…``, ``/abs/…``) because a bare
    match can pick up something that merely looks like an identifier; falls
    back to the bare pattern, which is what a download filename gives us.
    """
    if not text:
        return None
    for pattern in (ARXIV_IN_TEXT_RE, ARXIV_ID_RE):
        m = pattern.search(text)
        if m:
            return m.group(0) if keep_version and m.group(2) else m.group(1)
    return None


def normalize_arxiv_id(raw: str | None) -> str | None:
    """Canonical, version-stripped id, or None if this is not one.

    ``arXiv:2405.00208v3`` -> ``2405.00208``; ``COND-MAT/0506438`` ->
    ``cond-mat/0506438``; ``math.ag/0601001`` -> ``math.AG/0601001``.

    Canonical legacy form is a lowercase archive with an UPPERCASE two-letter
    subject class (``math.AG``, ``astro-ph.CO``) — lowercasing the whole thing
    produces an id arXiv will not resolve. The serial is never touched.
    """
    found = find_arxiv_id(raw)
    if not found:
        return None
    if "/" not in found:
        return found
    archive, _, serial = found.partition("/")
    if "." in archive:
        base, _, subject = archive.partition(".")
        return f"{base.lower()}.{subject.upper()}/{serial}"
    return f"{archive.lower()}/{serial}"


def abs_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/abs/{arxiv_id}"


def is_legacy(arxiv_id: str) -> bool:
    return "/" in arxiv_id
