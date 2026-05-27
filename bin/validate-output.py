#!/usr/bin/env python3
"""Validate LLM-generated wiki output files against structural schemas.

Checks frontmatter fields, citation existence, and body structure.
Exit code: 0 = valid, 1 = violations found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMAS = {"thesis", "research", "enrichment-log"}


def split_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    fm_text = text[4:end]
    body = text[end + 4:]
    data: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data, body


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


def validate_thesis(file_path: Path, fm: dict[str, str], body: str, wiki_root: Path) -> list[str]:
    issues: list[str] = []
    for field in ("title", "created"):
        if field not in fm:
            issues.append(f"frontmatter missing required field: {field}")
    fm_type = fm.get("type", "")
    if fm_type and fm_type.strip("\"'") != "thesis":
        issues.append(f"expected type: thesis, got: {fm_type}")

    raw = file_path.read_text(encoding="utf-8")
    sources = extract_sources_list(raw[:raw.find("\n---", 4)])
    if not sources:
        issues.append("frontmatter 'sources' list is empty or missing")

    if not re.search(r"^# ", body, re.MULTILINE):
        issues.append("body missing top-level heading (# )")

    wikilinks = extract_wikilinks(body)
    if not wikilinks:
        issues.append("body contains no [[wikilink]] citations")

    concepts_dir = wiki_root / "wiki" / "concepts"
    refs_dir = wiki_root / "wiki" / "references"
    for link in set(wikilinks):
        slug = link.replace(" ", "_")
        candidates = [
            concepts_dir / f"{slug}.md",
            concepts_dir / f"{link}.md",
            refs_dir / f"{slug}.md",
            refs_dir / f"{link}.md",
        ]
        if not any(c.exists() for c in candidates):
            issues.append(f"dangling wikilink: [[{link}]] — no matching file found")

    return issues


def validate_research(file_path: Path, fm: dict[str, str], body: str, wiki_root: Path) -> list[str]:
    issues: list[str] = []
    for field in ("title", "created"):
        if field not in fm:
            issues.append(f"frontmatter missing required field: {field}")

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


def validate_enrichment_log(file_path: Path, fm: dict[str, str], body: str, wiki_root: Path) -> list[str]:
    issues: list[str] = []
    wikilinks = extract_wikilinks(body)
    concepts_dir = wiki_root / "wiki" / "concepts"
    orphans: list[str] = []
    for link in set(wikilinks):
        slug = link.replace(" ", "_")
        candidates = [
            concepts_dir / f"{slug}.md",
            concepts_dir / f"{link}.md",
        ]
        if not any(c.exists() for c in candidates):
            orphans.append(link)
    if orphans:
        issues.append(f"{len(orphans)} concept(s) linked but have no file: {', '.join(sorted(orphans))}")
    return issues


def find_wiki_root(file_path: Path) -> Path:
    """Walk up from file_path to find a directory containing wiki/ and raw/."""
    current = file_path.parent
    for _ in range(10):
        if (current / "wiki").is_dir() or (current / "raw").is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent
    return file_path.parent


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="validate-output",
        description="Validate LLM-generated wiki output files against structural schemas.",
    )
    parser.add_argument("file", help="Markdown file to validate.")
    parser.add_argument(
        "--schema",
        required=True,
        choices=sorted(SCHEMAS),
        help="Schema to validate against.",
    )
    parser.add_argument("--wiki-root", help="Wiki root path (auto-detected if omitted).")
    args = parser.parse_args()

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
            "schema": args.schema,
            "valid": False,
            "issues": ["file has no YAML frontmatter (missing --- delimiters)"],
        }))
        return 1

    fm, body = parsed

    if args.schema == "thesis":
        issues = validate_thesis(file_path, fm, body, wiki_root)
    elif args.schema == "research":
        issues = validate_research(file_path, fm, body, wiki_root)
    elif args.schema == "enrichment-log":
        issues = validate_enrichment_log(file_path, fm, body, wiki_root)
    else:
        print(json.dumps({"error": f"unknown schema: {args.schema}"}))
        return 2

    report = {
        "file": str(file_path),
        "schema": args.schema,
        "valid": len(issues) == 0,
        "issues": issues,
    }
    print(json.dumps(report, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
