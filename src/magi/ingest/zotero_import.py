"""magi ingest zotero — queue a Zotero collection through the normal pipeline.

Zotero is treated as the list of papers you care about, not as a source of
files. What it stores is the publisher's typeset PDF, where a formula is already
glyphs on a page; when the same paper is on arXiv, its LaTeX is strictly better.
So this resolves an identifier per item and queues that, falling back to the
stored PDF — which is already on disk, needing no download and crossing no
paywall — only when there is no identifier to be had.

Measured on a real 758-item library: 28% carry an arXiv id in their metadata,
and a batched Semantic Scholar lookup over the 46% that have only a DOI lifts
that to roughly 62-65%. The remainder use their local PDF, which is not a
failure — those papers were never on arXiv.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from magi.ingest import ledger, zotero
from magi.ingest.enqueue import resolve_library, _resolve_topic
from magi.ingest.identity import resolve_dois


def _chosen_data_dir(explicit: str | None) -> tuple[Path | None, str | None]:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not (path / "zotero.sqlite").is_file():
            return None, f"no zotero.sqlite in {path}"
        return path, None

    from magi.kb_registry import load_settings
    configured = load_settings().get("zotero_data_dir")
    if configured and (Path(configured) / "zotero.sqlite").is_file():
        return Path(configured), None

    found = zotero.candidate_data_dirs()
    if not found:
        return None, ("no Zotero library found. Point at one with "
                      "'magi ingest zotero-dirs --set <PATH>'")
    # Never pick, even when there is only one candidate. A machine with a live
    # library and an abandoned sync folder is ordinary, and importing the frozen
    # one looks exactly like success.
    listing = "\n".join(f"    {p}" for p in found)
    return None, ("no Zotero library chosen yet. Candidates:\n" + listing +
                  "\n  Choose with: magi ingest zotero-dirs --set <PATH>")


def plan_routes(items, resolved_by_doi: dict[str, str] | None = None):
    """Decide how each item should be acquired. Returns (plan, skipped).

    *plan* is a list of ``(item, source_type, value)``; *skipped* is the items
    carrying nothing to fetch them by.

    The order is a preference ladder, and it is the reason this is one function
    rather than a rule each caller reimplements: arXiv source beats a publisher
    PDF because the conversion routes above it read LaTeX rather than a
    rendering of it, and Zotero's stored PDF beats a bare DOI because the file
    is already on disk.
    """
    resolved_by_doi = resolved_by_doi or {}
    plan, skipped = [], []
    for item in items:
        arxiv = item.arxiv_id() or resolved_by_doi.get((item.doi or "").lower())
        if arxiv:
            plan.append((item, "arxiv", arxiv))
        elif item.pdf_path:
            plan.append((item, "file", item.pdf_path))
        elif item.doi:
            plan.append((item, "doi", item.doi))
        else:
            skipped.append(item)
    return plan, skipped


def cmd_import(args) -> int:
    data_dir, err = _chosen_data_dir(args.data_dir)
    if err:
        print(err, file=sys.stderr)
        return 1

    if args.library:
        topic, lib_err = resolve_library(args.library)
        if lib_err:
            print(lib_err, file=sys.stderr)
            return 1
    else:
        topic = _resolve_topic(args.topic_dir)
    if topic is None:
        print("no project found — pass --project <NAME> (see 'magi kb list') "
              "or run this from inside a project directory", file=sys.stderr)
        return 1

    if args.list_collections:
        for col in zotero.list_collections(data_dir):
            print(f"  {col['n']:>5}  {col['collectionName']}")
        return 0

    selectors = (args.collection, args.collection_id, args.tag, args.keys)
    if not any(v for v in selectors) and not args.all:
        print("name what to import: --collection NAME, --collection-id N, --tag NAME,\n"
              "--key KEY (repeatable), or --all for the whole Zotero library.\n"
              "Collections available:", file=sys.stderr)
        for col in zotero.list_collections(data_dir):
            print(f"  {col['n']:>5}  {col['collectionName']}", file=sys.stderr)
        return 1

    print(f"[zotero] reading {data_dir}...")
    items = zotero.read_items(data_dir, collection=args.collection,
                              collection_id=args.collection_id,
                              tag=args.tag, keys=args.keys)
    if not items:
        named = [w for w in (
            f"collection {args.collection!r}" if args.collection else None,
            f"collection id {args.collection_id}" if args.collection_id else None,
            f"tag {args.tag!r}" if args.tag else None,
            f"{len(args.keys)} key(s)" if args.keys else None,
        ) if w]
        print(f"nothing matched {' + '.join(named) if named else 'this project'}.")
        return 0

    cov = zotero.coverage(items)
    print(f"[zotero] {cov['total']} item(s): {cov['arxiv']} with an arXiv id, "
          f"{cov['pdf']} with a stored PDF, {cov['doi_only']} with only a DOI")

    # One request for up to 500 DOIs. A serial loop over the same set would be a
    # quarter of an hour; this is a few seconds.
    resolved_by_doi: dict[str, str] = {}
    if not args.no_lookup:
        doi_only = {i.doi.lower(): i for i in items if not i.arxiv_id() and i.doi}
        if doi_only:
            print(f"[zotero] asking Semantic Scholar about {len(doi_only)} DOI(s)...")
            titles = {doi: item.title for doi, item in doi_only.items()}
            found = resolve_dois(list(doi_only), titles)
            resolved_by_doi = {doi: ident.arxiv_id
                               for doi, ident in found.items() if ident.arxiv_id}
            print(f"[zotero] {len(resolved_by_doi)} of them are on arXiv")

    plan, skipped = plan_routes(items, resolved_by_doi)

    queued = []
    for item, source_type, value in plan:
        if args.dry_run:
            queued.append({"title": item.title, "source_type": source_type,
                           "value": value})
            continue
        req_id = ledger.enqueue(topic, source_type=source_type, value=value,
                                library=args.library, title=item.title)
        queued.append({"req_id": req_id, "title": item.title,
                       "source_type": source_type, "value": value})

    by_kind: dict[str, int] = {}
    for q in queued:
        by_kind[q["source_type"]] = by_kind.get(q["source_type"], 0) + 1

    if args.json:
        print(json.dumps({"workspace": str(topic), "queued": queued,
                          "skipped": len(skipped), "by_route": by_kind,
                          "dry_run": bool(args.dry_run)}, ensure_ascii=False))
        return 0

    verb = "would queue" if args.dry_run else "queued"
    print(f"\n{verb} {len(queued)} item(s):")
    for kind, n in sorted(by_kind.items(), key=lambda kv: -kv[1]):
        label = {"arxiv": "arXiv source (best fidelity)",
                 "file": "Zotero's stored PDF",
                 "doi": "DOI, route decided at run time"}.get(kind, kind)
        print(f"  {n:>5}  {label}")
    if skipped:
        print(f"  {len(skipped):>5}  skipped — no identifier and no stored file")
        # Show the Zotero key alongside, because an item with no title is
        # exactly the one you cannot find again by searching for its title.
        titled = [i for i in skipped if i.title]
        for item in (titled or skipped)[:5]:
            label = item.title or "(no title in Zotero)"
            print(f"           [{item.key}] {label[:64]}")
        blank = len(skipped) - len(titled)
        if blank and titled:
            print(f"           ...and {blank} record(s) with no title at all")
    if not args.dry_run:
        print(f"\nRun them:  magi ingest batch-run"
              + (f" --topic-dir \"{topic}\"" if args.library else ""))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi ingest zotero",
        description="Queue a Zotero collection through the deterministic ingest "
                    "pipeline, preferring arXiv source over Zotero's stored PDF.")
    parser.add_argument("--collection", help="Collection name, including everything "
                                             "filed beneath it (see --list-collections)")
    parser.add_argument("--collection-id", type=int,
                        help="Collection by id, for when two share a name")
    parser.add_argument("--tag", help="Only items carrying this Zotero tag")
    parser.add_argument("--key", action="append", dest="keys", metavar="KEY",
                        help="A single item by its Zotero key; repeatable")
    parser.add_argument("--all", action="store_true", help="The whole Zotero library")
    parser.add_argument("--list-collections", action="store_true",
                        help="Show collections and their item counts, then stop")
    parser.add_argument("--data-dir", help="Zotero data directory (default: the "
                                           "one chosen with 'magi ingest zotero-dirs')")
    parser.add_argument("--project", "--library", dest="library",
                        help="Target project by name (see 'magi kb list')")
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir", help="Target project root")
    parser.add_argument("--no-lookup", action="store_true",
                        help="Skip the Semantic Scholar DOI lookup (offline)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be queued, queue nothing")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)
    return cmd_import(args)


if __name__ == "__main__":
    sys.exit(main())
