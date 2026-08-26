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
import re
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


#: How the sites people queue from decorate a browser tab's title. The
#: extension sends `tab.title` verbatim — deliberately, since parsing is the
#: server's job — and arXiv's abstract pages prefix the identifier, so a queued
#: paper arrives called "[2410.11942] Operator algebra and…".
_TITLE_NOISE = (
    re.compile(r"^\s*\[\s*(?:arXiv[:\s]*)?[0-9]{4}\.[0-9]{4,5}(?:v\d+)?\s*\]\s*", re.I),
    re.compile(r"^\s*\[\s*[a-z-]+(?:\.[A-Z]{2})?/[0-9]{7}(?:v\d+)?\s*\]\s*", re.I),
    re.compile(r"\s*[-|–—]\s*arXiv(?:\.org)?\s*$", re.I),
)


def clean_title(title: str | None) -> str | None:
    """The paper's title, without what the browser tab added to it.

    Done here rather than in the extension on purpose. The extension states
    that it parses nothing and decides nothing — that is what keeps it a
    button — so every rule about what a title looks like lives on this side,
    where it is one implementation with tests around it.

    It matters mainly on the way *down* the ladder. arXiv's own HTML carries a
    proper title that overwrites this one, so the prefix is invisible while
    rung 1 works; when rung 1 misses and the item falls through to a converter
    that has no metadata of its own, this is the title that reaches the
    library.
    """
    if not title:
        return None
    cleaned = title
    for pattern in _TITLE_NOISE:
        cleaned = pattern.sub("", cleaned)
    cleaned = cleaned.strip()
    # If stripping left nothing, the "noise" was the whole title. Keep the
    # original: a wrong title beats an empty one, and it is visible in review.
    return cleaned or title.strip()


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

    # One title cannot describe several papers. Applied to a multi-target call
    # it was given to every entry, and downstream it *overrides* the title
    # parsed out of the converted document (`ingest/batch.py`), so a review
    # list showed twenty papers under one name. For local PDFs it is worse:
    # the staging filename is built from that title, so N conversions land on
    # one path and overwrite each other before anyone reviews them.
    #
    # A single target keeps the override — someone naming one paper by hand
    # knows more than the parser, and that is the case the flag exists for.
    if args.title and len(args.targets) > 1:
        print(f"--title names one paper, and {len(args.targets)} were given. "
              "Queue them without it (each document is titled from its own "
              "content), or pass one target at a time.", file=sys.stderr)
        return 2

    queued = []
    for target in args.targets:
        source_type, value = classify(target)
        # Ask first so the line printed is true. `enqueue` collapses a repeat
        # into the request already waiting, and reporting that as "queued"
        # would hide the one thing the user needs to know.
        already = ledger.find_pending(topic, source_type, value)
        req_id = ledger.enqueue(topic, source_type=source_type, value=value,
                                library=args.library,
                                title=clean_title(args.title))
        status = "already-queued" if already else "queued"
        queued.append({"req_id": req_id, "source_type": source_type,
                       "value": value, "status": status})
        if not args.json:
            if already:
                print(f"already queued {source_type}: {value}")
            else:
                print(f"queued {source_type}: {value}")

    pending = len(ledger.pending(topic))
    if args.json:
        print(json.dumps({"workspace": str(topic), "queued": queued,
                          "pending": pending}, ensure_ascii=False))
    else:
        print(f"\n{pending} item(s) waiting in {topic}")
        # `batch-run` and everything after it take `--topic-dir` and have never
        # taken `--library`. Printing the bare command after queueing into a
        # library *by name* sent the reader to run the pipeline against
        # whichever workspace they happened to be standing in — so the queue
        # they had just filled sat untouched, and a different library's queue
        # got processed instead.
        where = f' --topic-dir "{topic}"' if args.library else ""
        print(f"Run them:  magi ingest batch-run{where}")
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
