"""How much of a warm note actually rests on the cold layer.

`raw/` is the only tier nobody rewrites, so it is the only tier a claim can
safely stand on. A reference card under `wiki/references/` looks like a source
and is not one: it is a compiled view of `raw/`, produced by an LLM, and it can
be wrong in exactly the way the claim citing it is trying to rule out. Citing a
reference card is how a mistake gets laundered into a fact — the card says it,
the concept card cites the card, and the original paper is never opened again.

So: **evidence points at `raw/`.** This module is that rule in a form code can
check, plus the derived number that comes out of it. The number is derived and
never stored; it is recomputed on demand like every other MAGI metric.

A note with no claims has no backing rate. That is `None`, not zero — a concept
card that states definitions makes no empirical claims and is not deficient for
it, and reporting 0% would put it at the bottom of every list it appears in.
"""

from __future__ import annotations

from ..core import vocab
from . import verify_claims


def source_tier(source: str) -> str | None:
    """Tier of a claim's `SOURCE:`, or `None` for a URL or an unknown path."""
    if not source:
        return None
    text = source.strip()
    if "://" in text:
        return None
    return vocab.tier_of(text)


def is_cold_backed(block: dict) -> bool:
    """A local claim whose evidence points into `raw/`."""
    source_type = (block.get("source_type") or "").strip().lower()
    if source_type and source_type != "local_wiki":
        return False
    return source_tier(block.get("source") or "") == vocab.COLD


def backing(text: str) -> dict:
    """`{"claims": n, "cold": n, "rate": float | None}` for one note's text."""
    blocks = verify_claims.parse_blocks(text)
    total = len(blocks)
    cold = sum(1 for block in blocks if is_cold_backed(block))
    return {
        "claims": total,
        "cold": cold,
        "rate": (cold / total) if total else None,
    }


def laundered_sources(text: str) -> list:
    """Claims that cite a derived view instead of the source it was built from.

    Returned as `[(claim, source), ...]` so the caller can name both — "this
    claim cites that card" is actionable, "3 bad claims" is not.
    """
    out = []
    for block in verify_claims.parse_blocks(text):
        source = (block.get("source") or "").strip()
        if source_tier(source) == vocab.COLD_DERIVED:
            out.append(((block.get("claim") or "").strip(), source))
    return out
