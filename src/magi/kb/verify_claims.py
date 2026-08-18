"""magi verify — claim/evidence verification (provenance layer, v2).

Verifies CLAIM/FINDING blocks of the form:

    CLAIM: <assertion>            (FINDING: also accepted)
    EVIDENCE: "<quote>"
    SOURCE_TYPE: local_wiki | web
    SOURCE: <relative path | URL>

Verification semantics:
- local_wiki: the evidence quote must appear in the source file.
  Matching is tiered: exact, then whitespace-normalized (runs of
  whitespace collapse to a single space), then loose — NFKC-folded,
  quote/dash punctuation unified, hyphenation and ALL whitespace
  removed, casefolded. The loose tier absorbs the layout artifacts of
  PDF-extracted text (ligatures like ﬁ, line-break hyphenation,
  full-width CJK punctuation, spaces injected between CJK characters)
  so honest quotes still verify.
- web: URL format check by default ("url-format-ok", NOT verified).
  With --fetch-web the page is fetched and the same tiered matching is
  applied to its (tag-stripped) text ("web-verified" / "web-mismatch").

Output: human report by default; --json emits one object per claim with
status in {verified, web-verified, url-format-ok, unverified} plus a
reason — the shape consumed by the graph's claims tables.

Multiline EVIDENCE: a double-quoted EVIDENCE value may span multiple
lines; the closing quote must be the last character on its line. While
the quote is open, lines that look like field openers (CLAIM:/FINDING:)
are treated as quote continuation, not as a new block. An unterminated
quote swallows the remainder of the file into a single block, so always
close the quote.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata

# Case-insensitive to match the field regexes below.
BLOCK_OPEN = re.compile(r"(?:CLAIM|FINDING):", re.IGNORECASE)
EVIDENCE_LINE = re.compile(r"EVIDENCE:\s*(.*)", re.IGNORECASE)
# Double-quoted EVIDENCE, possibly multiline: closing quote must end its line.
QUOTED_EVIDENCE = re.compile(
    r'^EVIDENCE:\s*"(.*?)"[ \t]*$',
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
FIELD = {
    "claim": re.compile(r"(?:CLAIM|FINDING):\s*(.*)", re.IGNORECASE),
    "evidence": re.compile(
        r"^EVIDENCE:\s*(.*?)(?=\n^(?:CLAIM|SOURCE_TYPE|SOURCE|CONTRADICTS_SOURCE|SEVERITY|FINDING|STATUS):|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    ),
    "source_type": re.compile(r"SOURCE_TYPE:\s*(.*)", re.IGNORECASE),
    "source": re.compile(r"^SOURCE:\s*(.*)", re.IGNORECASE | re.MULTILINE),
    "status": re.compile(r"^STATUS:\s*(.*)", re.IGNORECASE | re.MULTILINE),
}


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# Punctuation that NFKC does not fold: curly quotes, dash family, and the
# CJK ideographic stops (、 。 are not compatibility characters).
_PUNCT_MAP = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-",
    "、": ",", "。": ".",
})


def normalize_loose(text: str) -> str:
    """Aggressive fold for PDF-layout artifacts.

    NFKC handles ligatures (ﬁ→fi) and full-width forms (，→,); on top of
    that we unify quote/dash punctuation, drop soft hyphens, and remove
    hyphens and ALL whitespace so line-break hyphenation and spaces
    injected between CJK characters cannot defeat an honest quote.
    """
    text = unicodedata.normalize("NFKC", text).translate(_PUNCT_MAP)
    text = text.replace("­", "")
    text = re.sub(r"[\s\-]+", "", text)
    return text.casefold()


def split_blocks(content: str) -> list[str]:
    """Split into blocks at CLAIM:/FINDING: opener lines, quote-aware.

    An opener line inside an unclosed double-quoted EVIDENCE (the quote
    opened but has not yet closed at end of a line) is treated as quote
    continuation, not as a new block.
    """
    raw_blocks: list[list[str]] = []
    in_quote = False
    for line in content.split("\n"):
        if not in_quote and BLOCK_OPEN.match(line):
            raw_blocks.append([line])
        elif raw_blocks:
            raw_blocks[-1].append(line)
        else:
            raw_blocks.append([line])
        if in_quote:
            if line.rstrip().endswith('"'):
                in_quote = False
        else:
            m = EVIDENCE_LINE.match(line)
            if m:
                rest = m.group(1).strip()
                if rest.startswith('"') and not (len(rest) > 1 and rest.endswith('"')):
                    in_quote = True
    return ["\n".join(b) for b in raw_blocks]


def parse_blocks(content: str) -> list[dict]:
    blocks = []
    for raw in split_blocks(content.strip()):
        if not raw.strip():
            continue
        # Card prose / frontmatter around embedded claim blocks is not a
        # malformed claim — only segments containing an actual CLAIM:/FINDING:
        # opener are claims.
        if not BLOCK_OPEN.search(raw):
            continue
        fields = {}
        for key, rx in FIELD.items():
            m = rx.search(raw)
            fields[key] = m.group(1).strip() if m else None
        # Prefer quote-aware extraction so a multiline quoted EVIDENCE is not
        # truncated at an inner line that looks like a field opener.
        qm = QUOTED_EVIDENCE.search(raw)
        if qm:
            fields["evidence"] = qm.group(1).strip()
        else:
            ev = fields.get("evidence")
            if ev and ev.startswith('"') and ev.endswith('"'):
                fields["evidence"] = ev[1:-1]
        fields["raw"] = raw
        blocks.append(fields)
    return blocks


def verify_local(evidence: str, source: str, topic_dir: str) -> tuple[str, str]:
    abs_path = source if os.path.isabs(source) else os.path.join(topic_dir, source)
    real_path = os.path.normcase(os.path.realpath(abs_path))
    real_topic = os.path.normcase(os.path.realpath(topic_dir))
    if not real_path.startswith(real_topic + os.sep) and real_path != real_topic:
        return "unverified", f"path traversal: {abs_path} resolves outside {topic_dir}"
    if not os.path.exists(real_path):
        return "unverified", f"file not found: {abs_path}"
    try:
        with open(real_path, "r", encoding="utf-8", errors="replace") as f:
            file_content = f.read()
    except OSError as exc:
        return "unverified", f"cannot read source: {exc}"
    if evidence in file_content:
        return "verified", "exact match"
    if normalize_ws(evidence) and normalize_ws(evidence) in normalize_ws(file_content):
        return "verified", "whitespace-normalized match"
    if normalize_loose(evidence) and normalize_loose(evidence) in normalize_loose(file_content):
        return "verified", "loose match (case/punctuation/hyphenation-insensitive)"
    return "unverified", "evidence string not found in file (exact, normalized, or loose)"


def verify_web(evidence: str, source: str, fetch: bool) -> tuple[str, str]:
    if not (source.startswith("http://") or source.startswith("https://")):
        return "unverified", f"invalid URL format: {source}"
    if not fetch:
        return "url-format-ok", "URL format valid; content NOT fetched (use --fetch-web)"
    try:
        import urllib.request

        req = urllib.request.Request(
            source, headers={"User-Agent": "magi-verify/0.1 (research workspace tool)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read(2_000_000).decode("utf-8", errors="replace")
    except Exception as exc:
        return "unverified", f"fetch failed: {type(exc).__name__}: {exc}"
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    if normalize_ws(evidence) and normalize_ws(evidence) in normalize_ws(text):
        return "web-verified", "quote found in fetched page text"
    if normalize_loose(evidence) and normalize_loose(evidence) in normalize_loose(text):
        return "web-verified", "quote found in fetched page text (loose match)"
    return "unverified", "quote not found in fetched page text (web-mismatch)"


def verify_claims_file(filepath: str, topic_dir: str, fetch_web: bool) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().replace("\r\n", "\n")
    results = []
    for b in parse_blocks(content):
        if not all(b.get(k) for k in ("claim", "evidence", "source_type", "source")):
            results.append({"claim": b.get("claim"), "status": "unverified",
                            "reason": "malformed block (missing field)",
                            "source_type": b.get("source_type"), "source": b.get("source"),
                            "evidence": b.get("evidence")})
            continue
        st = b["source_type"].lower()
        if st == "local_wiki":
            status, reason = verify_local(b["evidence"], b["source"], topic_dir)
        elif st == "web":
            status, reason = verify_web(b["evidence"], b["source"], fetch_web)
        else:
            status, reason = "unverified", f"unknown SOURCE_TYPE: {st}"
        results.append({"claim": b["claim"], "status": status, "reason": reason,
                        "source_type": st, "source": b["source"], "evidence": b["evidence"]})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="magi verify", description="Verify CLAIM/FINDING evidence blocks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "exit codes:\n"
            "  0  no unverified claims\n"
            "  1  at least one unverified claim\n"
            "  2  claims file not found\n"
        ))
    parser.add_argument("claims_file", help="Path to text file containing claims")
    parser.add_argument("--topic-dir", required=True, help="Topic workspace directory")
    parser.add_argument("--fetch-web", action="store_true",
                        help="Actually fetch web sources and check the quote in page text")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.claims_file):
        print(f"Error: claims file not found: {args.claims_file}", file=sys.stderr)
        return 2

    results = verify_claims_file(args.claims_file, args.topic_dir, args.fetch_web)
    n_verified = sum(1 for r in results if r["status"] == "verified")
    n_web = sum(1 for r in results if r["status"] == "web-verified")
    n_url = sum(1 for r in results if r["status"] == "url-format-ok")
    n_bad = sum(1 for r in results if r["status"] == "unverified")
    # url-format-ok is deliberately NOT counted as verified: only content
    # checks (local match or fetched-page match) count.
    n_ok = n_verified + n_web

    if args.json:
        print(json.dumps({
            "results": results,
            "counts": {"verified": n_verified, "web_verified": n_web,
                       "url_format_ok": n_url, "unverified": n_bad},
            "verified": n_ok, "unverified": n_bad,
        }, ensure_ascii=False))
    else:
        print("=== Verification Report ===")
        for r in results:
            tag = r["status"].upper()
            print(f"[{tag}] {r['claim']}")
            print(f"  Source: {r['source']} ({r['source_type']})")
            if r["status"] == "unverified":
                print(f"  Reason: {r['reason']}")
        print(f"\nTotal Verified: {n_ok}")
        if n_url:
            print(f"URL Format OK (content not fetched): {n_url}")
        print(f"Total Unverified: {n_bad}")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
