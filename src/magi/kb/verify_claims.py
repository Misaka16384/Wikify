"""magi verify — claim/evidence verification (provenance layer, v2).

Verifies CLAIM/FINDING blocks of the form:

    CLAIM: <assertion>            (FINDING: also accepted)
    EVIDENCE: "<quote>"
    SOURCE_TYPE: local_wiki | web
    SOURCE: <relative path | URL>

Verification semantics:
- local_wiki: the evidence quote must appear in the source file.
  Matching is whitespace-normalized (all runs of whitespace collapse to
  a single space) so OCR/reflow drift does not defeat honest quotes.
- web: URL format check by default ("url-format-ok", NOT verified).
  With --fetch-web the page is fetched and the normalized quote must
  appear in its (tag-stripped) text ("web-verified" / "web-mismatch").

Output: human report by default; --json emits one object per claim with
status in {verified, web-verified, url-format-ok, unverified} plus a
reason — the shape consumed by the graph's claims tables.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Case-insensitive to match the field regexes below. Known limitation: an
# EVIDENCE quote containing a line that itself starts with "CLAIM:"/"FINDING:"
# will split the block — quoting another claims report requires indenting it.
BLOCK_OPEN = re.compile(r"\n(?=(?:CLAIM|FINDING):)", re.IGNORECASE)
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


def parse_blocks(content: str) -> list[dict]:
    blocks = []
    for raw in BLOCK_OPEN.split(content.strip()):
        if not raw.strip():
            continue
        fields = {}
        for key, rx in FIELD.items():
            m = rx.search(raw)
            fields[key] = m.group(1).strip() if m else None
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
    return "unverified", "evidence string not found in file (exact or normalized)"


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
    parser = argparse.ArgumentParser(prog="magi verify", description="Verify CLAIM/FINDING evidence blocks")
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
    ok = {"verified", "web-verified", "url-format-ok"}
    n_ok = sum(1 for r in results if r["status"] in ok)
    n_bad = len(results) - n_ok

    if args.json:
        print(json.dumps({"results": results, "verified": n_ok, "unverified": n_bad},
                         ensure_ascii=False))
    else:
        print("=== Verification Report ===")
        for r in results:
            tag = r["status"].upper()
            print(f"[{tag}] {r['claim']}")
            print(f"  Source: {r['source']} ({r['source_type']})")
            if r["status"] == "unverified":
                print(f"  Reason: {r['reason']}")
        print(f"\nTotal Verified: {n_ok}\nTotal Unverified: {n_bad}")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
