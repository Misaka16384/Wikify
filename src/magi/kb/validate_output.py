#!/usr/bin/env python3
"""Check one long-form document an agent wrote.

**One schema, because v2 produces one kind of long-form output.** A research
pass lands as propositions in `threads/` — which `threads.validate` checks on
every read — plus at most one synthesis in `wiki/topics/`. There used to be
three schemas here, from when there were three things to write; `wiki/theses/`
is retired and nothing has written an enrichment log since the compile pass was
rewritten. A required `--schema` flag with one legal value is a flag that
exists only to be typed.

Scope is why this is not part of `magi lint`: lint answers for a whole
workspace, this answers for one file. Merging them would grow a flag to say
which one you meant, which is the thing merging was supposed to remove.

Exit code: 0 = valid, 1 = violations found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from magi.core.wiki_common import split_frontmatter_text, parse_frontmatter_text

#: What `wiki/topics/` cards declare themselves to be. Checked rather than
#: assumed: a card that says it is something else is a card somebody filed in
#: the wrong place, and saying so is more useful than validating it anyway.
SYNTHESIS = "synthesis"


def split_frontmatter(text: str) -> tuple[dict, str] | None:
    parts = split_frontmatter_text(text)
    if parts is None:
        return None
    fm_text, body = parts
    return parse_frontmatter_text(fm_text), body


def extract_wikilinks(text: str) -> list[str]:
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text)


def extract_sources_list(text: str) -> list[str]:
    """Extract sources list from raw frontmatter text."""
    in_sources = False
    sources: list[str] = []
    for line in text.splitlines():
        if line.startswith("sources:"):
            in_sources = True
            continue
        if in_sources:
            if line.startswith("  - "):
                val = line[4:].strip().strip("\"'")
                sources.append(val)
            elif not line.startswith(" "):
                break
    return sources


def validate_synthesis(file_path: Path, fm: dict[str, str], body: str,
                       wiki_root: Path) -> list[str]:
    """Everything the two live schemas each got right, in one pass."""
    issues: list[str] = []
    for field in ("title", "created"):
        if field not in fm:
            issues.append(f"frontmatter missing required field: {field}")
    declared = fm.get("type", "").strip("\"'")
    if declared and declared != SYNTHESIS:
        issues.append(f"expected type: {SYNTHESIS}, got: {declared}")

    if not re.search(r"^# ", body, re.MULTILINE):
        issues.append("body missing top-level heading (# )")

    wikilinks = extract_wikilinks(body)
    if not wikilinks:
        issues.append("body contains no [[wikilink]] citations")

    # Links that go nowhere. `threads/` and `drafts/` count: a synthesis
    # citing the proposition it came from, or the derivation behind it, is the
    # normal case in v2.
    for link in set(wikilinks):
        slug = link.replace(" ", "_")
        candidates = [wiki_root / base / f"{name}.md"
                      for base in ("wiki/concepts", "wiki/references",
                                   "wiki/topics", "threads", "drafts")
                      for name in (slug, link)]
        if not any(c.exists() for c in candidates):
            issues.append(f"dangling wikilink: [[{link}]] — no matching file found")

    raw = file_path.read_text(encoding="utf-8")
    sources = extract_sources_list(raw[:raw.find("\n---", 4)])
    for source in sources:
        if source.startswith(("http://", "https://")):
            continue
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = wiki_root / source
        if not source_path.exists():
            if source_path.is_absolute():
                parts = source_path.parts
                for i, p in enumerate(parts):
                    if p in ("wiki", "raw", "inventory", "datasets"):
                        fallback = wiki_root / Path(*parts[i:])
                        if fallback.exists():
                            source_path = fallback
                            break
            if not source_path.exists():
                issues.append(f"source does not exist: {source}")

    # Strip HTML comments (e.g. the skill-mandated <!-- magi:claims --> block)
    # so their contents are not counted as uncited paragraphs.
    body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)

    paragraphs = re.split(r"\n\n+", body)
    unsupported = 0
    for para in paragraphs:
        stripped = para.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|") or stripped.startswith(">"):
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            continue
        if len(stripped) < 50:
            continue
        
        # Exempt math derivations and logical proofs
        is_math = ("$$" in stripped or 
                   "\\begin{" in stripped or
                   "\\int" in stripped or
                   "\\sum" in stripped)
        math_keywords = {"proof", "substituting", "let", "integrating", "differentiating", "we have", "where", "hence", "therefore", "using"}
        first_word = stripped.split()[0].lower().strip(".,:;()") if stripped.split() else ""
        is_derivation = first_word in math_keywords
        
        if is_math or is_derivation:
            continue
            
        has_wikilink = bool(re.search(r"\[\[", stripped))
        has_mdlink = bool(re.search(r"\]\(", stripped))
        if not has_wikilink and not has_mdlink:
            unsupported += 1
    if unsupported > 0:
        issues.append(f"{unsupported} paragraph(s) contain no citations — may be unsupported claims")

    return issues


def find_wiki_root(file_path: Path) -> Path:
    """Nearest topic workspace root for *file_path* (unified discovery)."""
    from magi.core.workspace import find_workspace_root

    return find_workspace_root(file_path) or file_path.parent


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi validate",
        description="Check one long-form document an agent wrote: a `wiki/topics/` synthesis.",
    )
    parser.add_argument("file", help="Markdown file to validate.")
    # Kept so an old command line still runs, hidden so nobody learns to type
    # it: there is one schema, and a flag with one legal value is a flag that
    # exists only to be typed.
    parser.add_argument("--schema", default=SYNTHESIS, choices=[SYNTHESIS],
                        help=argparse.SUPPRESS)
    parser.add_argument("--wiki-root", help="Wiki root path (auto-detected if omitted).")
    args = parser.parse_args(argv)

    file_path = Path(args.file).resolve()
    if not file_path.exists():
        print(json.dumps({"error": f"file not found: {file_path}"}))
        return 2

    wiki_root = Path(args.wiki_root).resolve() if args.wiki_root else find_wiki_root(file_path)

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(json.dumps({"error": f"could not read file: {exc}"}))
        return 2

    parsed = split_frontmatter(text)
    if parsed is None:
        print(json.dumps({
            "file": str(file_path),
            "schema": SYNTHESIS,
            "valid": False,
            "issues": ["file has no YAML frontmatter (missing --- delimiters)"],
        }))
        return 1

    fm, body = parsed

    issues = validate_synthesis(file_path, fm, body, wiki_root)

    report = {
        "file": str(file_path),
        "schema": SYNTHESIS,
        "valid": len(issues) == 0,
        "issues": issues,
    }
    print(json.dumps(report, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
