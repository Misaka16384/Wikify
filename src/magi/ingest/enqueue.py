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


def resolve_library(name: str | None) -> tuple[Path | None, str | None]:
    """A registered knowledge base by name -> its path.

    Returns ``(path, error)``. The name has to already be registered: this is
    the same closed world the WebUI's library picker offers, so a browser
    extension and an agent both choose from what exists rather than inventing a
    destination.
    """
    if not name:
        return None, None
    from magi.kb_registry import load_registry

    kbs = load_registry().get("kbs", {})
    entry = kbs.get(name)
    if entry is None:
        # Be forgiving about case and separators; be strict about existence.
        wanted = name.strip().lower().replace("_", "-")
        for key, value in kbs.items():
            if key.strip().lower().replace("_", "-") == wanted:
                entry, name = value, key
                break
    if entry is None:
        known = ", ".join(sorted(kbs)) or "(none registered)"
        return None, f"no knowledge base named {name!r}. Registered: {known}"
    path = Path(entry["path"]).expanduser()
    if not path.is_dir():
        return None, f"{name!r} points at {path}, which does not exist"
    return path, None


def classify(target: str) -> tuple[str, str]:
    """What kind of thing this is, using no network.

    A Semantic Scholar lookup belongs to batch-run, where it can be batched with
    everything else queued alongside it rather than paid one request at a time.
    """
    ident = from_text(target)
    if ident.arxiv_id:
        return "arxiv", ident.arxiv_id
    if ident.doi:
        return "doi", ident.doi
    if Path(target).is_file():
        return "file", str(Path(target).resolve())
    return "url", target


def cmd_url(args) -> int:
    if args.library:
        topic, err = resolve_library(args.library)
        if err:
            print(err, file=sys.stderr)
            return 1
    else:
        topic = _resolve_topic(args.topic_dir)
    if topic is None:
        print("no workspace found — run this from a topic directory, pass "
              "--topic-dir, or name a registered library with --library "
              "(see 'magi kb list')", file=sys.stderr)
        return 1

    queued = []
    for target in args.targets:
        source_type, value = classify(target)
        req_id = ledger.enqueue(topic, source_type=source_type, value=value,
                                library=args.library, title=args.title)
        queued.append({"req_id": req_id, "source_type": source_type,
                       "value": value, "status": "queued"})
        if not args.json:
            print(f"queued {source_type}: {value}")

    pending = len(ledger.pending(topic))
    if args.json:
        print(json.dumps({"workspace": str(topic), "queued": queued,
                          "pending": pending}, ensure_ascii=False))
    else:
        print(f"\n{pending} item(s) waiting in {topic}")
        print("Run them:  magi ingest batch-run")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi ingest url",
        description="Queue a paper for deterministic acquisition. "
                    "Nothing is fetched or written until 'magi ingest batch-run'.")
    parser.add_argument("targets", nargs="+",
                        help="One or more URLs, DOIs, arXiv ids, or file paths")
    parser.add_argument("--topic-dir", help="Workspace root (default: discovered)")
    parser.add_argument("--library",
                        help="A registered knowledge base by name (see 'magi kb list'). "
                             "Queues into that library instead of the current directory.")
    parser.add_argument("--title", help="Title, when you already know it")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)
    return cmd_url(args)


if __name__ == "__main__":
    sys.exit(main())
