"""magi ingest url / zotero — put something in the queue, and stop there.

This is the one door. The CLI below and the WebUI endpoint the browser
extension talks to both call :func:`magi.ingest.ledger.enqueue` and nothing
else, so "everything still works without the extension" is true structurally
rather than by two parallel implementations that drift.

Queueing does no network, no conversion, and no writing into the library. That
is what keeps the extension's blast radius at one appended line.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from magi.core.arxiv_id import normalize_arxiv_id
from magi.core.workspace import find_workspace_root
from magi.ingest import ledger
from magi.ingest.identity import from_text


def _resolve_topic(explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if path.is_dir() else None
    return find_workspace_root()


def cmd_url(args) -> int:
    topic = _resolve_topic(args.topic_dir)
    if topic is None:
        print("no workspace found — run this from a topic directory, "
              "or pass --topic-dir", file=sys.stderr)
        return 1

    # The cheap local pass only. A Semantic Scholar lookup belongs to batch-run,
    # where it can be batched with everything else queued alongside it.
    ident = from_text(args.target)
    if ident.arxiv_id:
        source_type, value = "arxiv", ident.arxiv_id
    elif ident.doi:
        source_type, value = "doi", ident.doi
    elif Path(args.target).is_file():
        source_type, value = "file", str(Path(args.target).resolve())
    else:
        source_type, value = "url", args.target

    req_id = ledger.enqueue(topic, source_type=source_type, value=value,
                            library=args.library, title=args.title)

    if args.json:
        print(json.dumps({"req_id": req_id, "source_type": source_type,
                          "value": value, "status": "queued"}))
    else:
        print(f"queued {source_type}: {value}")
        pending = len(ledger.pending(topic))
        print(f"{pending} item(s) waiting. Run them:  magi ingest batch-run")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi ingest url",
        description="Queue a paper for deterministic acquisition. "
                    "Nothing is fetched or written until 'magi ingest batch-run'.")
    parser.add_argument("target", help="A URL, DOI, arXiv id, or local file path")
    parser.add_argument("--topic-dir", help="Workspace root (default: discovered)")
    parser.add_argument("--library", help="Which knowledge base this is for")
    parser.add_argument("--title", help="Title, when you already know it")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)
    return cmd_url(args)


if __name__ == "__main__":
    sys.exit(main())
