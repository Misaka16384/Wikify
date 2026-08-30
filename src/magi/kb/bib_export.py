"""magi bib — export BibTeX from reference cards.

Reference cards carry the citation metadata a paper draft needs (title,
authors, year, venue, arxiv_id/doi) in their frontmatter. This command turns
them back into BibTeX so writing never has to leave the workspace:

    magi bib pretko-2020            # one card (slug or path), entry to stdout
    magi bib --all                  # every card under wiki/references/
    magi bib --all -o refs.bib      # write a .bib file
    magi bib pretko-2020 --fetch    # prefer arXiv's official BibTeX (network)

Entries are built offline from frontmatter; --fetch upgrades any card with an
arxiv_id to the official record from arxiv.org/bibtex/<id>.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from magi.core.workspace import find_workspace_root


def _read_frontmatter(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1)) or {}
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def _authors_list(fm: dict) -> list[str]:
    raw = fm.get("authors") or fm.get("author") or []
    if isinstance(raw, str):
        parts = re.split(r";| and |,", raw)
        return [p.strip() for p in parts if p.strip()]
    if isinstance(raw, list):
        return [str(a).strip() for a in raw if str(a).strip()]
    return []


def _bib_key(fm: dict, slug: str) -> str:
    authors = _authors_list(fm)
    year = str(fm.get("year") or "")
    if authors:
        last = authors[0].split()[-1] if authors[0] else slug
        last = re.sub(r"[^A-Za-z0-9]", "", last).lower() or slug
        return f"{last}{year}" if year else last
    return slug


def _escape(value) -> str:
    return str(value).replace("{", "\\{").replace("}", "\\}").strip()


def build_entry(card: Path, fm: dict) -> str:
    slug = re.sub(r"[^\w-]", "-", card.stem)
    key = _bib_key(fm, slug)
    authors = _authors_list(fm)
    fields: list[tuple[str, str]] = []
    if fm.get("title"):
        fields.append(("title", "{" + _escape(fm["title"]) + "}"))
    if authors:
        fields.append(("author", "{" + " and ".join(_escape(a) for a in authors) + "}"))
    if fm.get("year"):
        fields.append(("year", "{" + _escape(fm["year"]) + "}"))
    venue = fm.get("venue") or fm.get("journal")
    entry_type = "article" if venue else "misc"
    if venue:
        fields.append(("journal", "{" + _escape(venue) + "}"))
    if fm.get("doi"):
        fields.append(("doi", "{" + _escape(fm["doi"]) + "}"))
    if fm.get("arxiv_id"):
        fields.append(("eprint", "{" + _escape(fm["arxiv_id"]) + "}"))
        fields.append(("archivePrefix", "{arXiv}"))
        fields.append(("url", "{https://arxiv.org/abs/" + _escape(fm["arxiv_id"]) + "}"))
    elif fm.get("url") or fm.get("source", "").startswith(("http://", "https://")):
        fields.append(("url", "{" + _escape(fm.get("url") or fm.get("source")) + "}"))
    if not fields:
        return ""
    body = ",\n".join(f"  {k} = {v}" for k, v in fields)
    return f"@{entry_type}{{{key},\n{body}\n}}"


def fetch_arxiv_bibtex(arxiv_id: str, timeout: int = 20) -> str | None:
    try:
        import urllib.request

        req = urllib.request.Request(
            f"https://arxiv.org/bibtex/{arxiv_id}",
            headers={"User-Agent": "magi-bib/1.0 (research project tool)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode("utf-8", errors="replace").strip()
        return text if text.startswith("@") else None
    except Exception:
        return None


def _find_cards(root: Path, target: str | None, all_cards: bool) -> list[Path]:
    refs_dir = root / "wiki" / "references"
    if all_cards:
        if not refs_dir.is_dir():
            return []
        return sorted(p for p in refs_dir.rglob("*.md") if p.name != "_index.md")
    assert target is not None
    p = Path(target)
    if p.is_file():
        return [p]
    p2 = root / target
    if p2.is_file():
        return [p2]
    # slug lookup under wiki/references (with or without .md)
    slug = target[:-3] if target.endswith(".md") else target
    if refs_dir.is_dir():
        matches = [c for c in refs_dir.rglob("*.md")
                   if c.stem == slug or slug in c.stem]
        exact = [c for c in matches if c.stem == slug]
        if exact:
            return exact[:1]
        if len(matches) == 1:
            return matches
        if len(matches) > 1:
            print(f"error: '{target}' matches several cards: "
                  + ", ".join(c.stem for c in matches[:6]), file=sys.stderr)
            return []
    return []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi bib", description="Export BibTeX from reference-card frontmatter.")
    parser.add_argument("target", nargs="?",
                        help="Reference card: path or slug under wiki/references/")
    parser.add_argument("--all", action="store_true",
                        help="Export every card under wiki/references/")
    parser.add_argument("--fetch", action="store_true",
                        help="Prefer arXiv's official BibTeX when the card has an arxiv_id (network)")
    parser.add_argument("-o", "--output", help="Write entries to this .bib file instead of stdout")
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir", help="Project directory (default: discovered from cwd)")
    args = parser.parse_args(argv)

    if not args.all and not args.target:
        parser.error("give a card slug/path, or use --all")

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        print("error: no project found (run inside one, or pass --project-dir)", file=sys.stderr)
        return 1

    cards = _find_cards(root, args.target, args.all)
    if not cards:
        where = "wiki/references/" if args.all else f"'{args.target}'"
        print(f"error: no reference card found for {where}", file=sys.stderr)
        return 1

    entries: list[str] = []
    skipped = 0
    for card in cards:
        fm = _read_frontmatter(card)
        entry = None
        if args.fetch and fm.get("arxiv_id"):
            entry = fetch_arxiv_bibtex(str(fm["arxiv_id"]))
            if entry is None:
                print(f"note: arXiv fetch failed for {card.stem}; using frontmatter",
                      file=sys.stderr)
        if not entry:
            entry = build_entry(card, fm)
        if entry:
            entries.append(entry)
        else:
            skipped += 1
            print(f"note: {card.stem} has no citable frontmatter (title/authors/year) — skipped",
                  file=sys.stderr)

    if not entries:
        print("error: nothing exportable", file=sys.stderr)
        return 1

    blob = "\n\n".join(entries) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(blob, encoding="utf-8")
        print(f"bib: wrote {len(entries)} entrie(s) to {out}"
              + (f" ({skipped} skipped)" if skipped else ""))
    else:
        print(blob, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
