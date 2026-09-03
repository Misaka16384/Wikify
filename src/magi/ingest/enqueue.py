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


def fetch_title(source_type: str, value: str, timeout: int = 20) -> str | None:
    """The paper's title from its own authority, or None.

    arXiv's export API for an arXiv id, Semantic Scholar for a DOI. Only on
    request (`--expect`, `--fetch-title`): the queue is otherwise offline by
    design, and the browser extension's endpoint stays that way. The reason it
    exists at all is one remembered-wrong arXiv id that was one `batch-run`
    away from filing somebody else's paper, caught by the agent's own fetch
    rather than by anything here (2026-09-03).
    """
    try:
        if source_type == "arxiv":
            from magi.core.http import http_text

            xml = http_text(f"http://export.arxiv.org/api/query?id_list={value}",
                            timeout=timeout)
            _feed, _sep, entry = xml.partition("<entry>")
            found = re.search(r"<title>(.*?)</title>", entry, re.DOTALL) if entry else None
            return " ".join(found.group(1).split()) if found else None
        if source_type == "doi":
            from magi.core.http import http_json
            from magi.ingest.identity import S2_BASE

            data = http_json(f"{S2_BASE}/DOI:{value}?fields=title", timeout=timeout)
            title = data.get("title") if isinstance(data, dict) else None
            return " ".join(title.split()) if title else None
    except Exception:  # noqa: BLE001 — a title is a check, and "could not check" is reported
        return None
    return None


def title_matches(expect: str, title: str) -> bool:
    """Whether the fragment somebody remembers is in the title, loosely.

    Case, punctuation and spacing are the parts of a title nobody remembers
    right, so they are not what the check is about.
    """
    def norm(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (text or "").casefold()).strip()

    wanted = norm(expect)
    return bool(wanted) and wanted in norm(title)


def cmd_url(args) -> int:
    if args.library:
        topic, err = resolve_library(args.library)
        if err:
            print(err, file=sys.stderr)
            return 1
    else:
        topic = _resolve_topic(args.topic_dir)
    if topic is None:
        print("no project found — run this from inside one, pass "
              "--topic-dir, or name a registered project with --library "
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
    refused = 0
    expect = getattr(args, "expect", None)
    for target in args.targets:
        source_type, value = classify(target)
        fetched = None
        if (expect or getattr(args, "fetch_title", False)) and source_type in ("arxiv", "doi"):
            fetched = fetch_title(source_type, value)
            if not args.json:
                print(f"{value}: " + (f"title: {fetched}" if fetched
                                      else "no title could be fetched"))
        if expect:
            # Refused before it is queued. A queue entry is inert, but the
            # next `batch-run` is not, and an id remembered one digit wrong
            # is a different paper filed under the wrong belief.
            if fetched is None:
                print(f"{value}: could not fetch a title to check against --expect; "
                      "not queued", file=sys.stderr)
                refused += 1
                continue
            if not title_matches(expect, fetched):
                print(f"{value}: its title is {fetched!r}, which does not contain "
                      f"{expect!r}; not queued", file=sys.stderr)
                refused += 1
                continue
        # Ask first so the line printed is true. `enqueue` collapses a repeat
        # into the request already waiting, and reporting that as "queued"
        # would hide the one thing the user needs to know.
        already = ledger.find_pending(topic, source_type, value)
        req_id = ledger.enqueue(topic, source_type=source_type, value=value,
                                library=args.library,
                                title=clean_title(args.title))
        status = "already-queued" if already else "queued"
        queued.append({"req_id": req_id, "source_type": source_type,
                       "value": value, "status": status, "title": fetched})
        if not args.json:
            if already:
                print(f"already queued {source_type}: {value}")
            else:
                print(f"queued {source_type}: {value}")
            if source_type == "doi" and not already:
                # Said here, at the moment of queuing, because the failure it
                # forestalls used to arrive one batch-run later with a message
                # about arXiv identifiers that named no remedy.
                print("  batch-run maps a DOI to its arXiv id via Semantic Scholar; "
                      "one with no arXiv version needs its PDF (`magi ingest add`)")

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
    # A refused target is a target not queued, and the exit code says so
    # even when the others went in.
    return 1 if refused else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi ingest url",
        description="Queue a paper for deterministic acquisition. "
                    "Nothing is fetched or written until 'magi ingest batch-run'.")
    parser.add_argument("targets", nargs="+",
                        help="One or more URLs, DOIs, arXiv ids, or file paths")
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir", help="Project root (default: discovered)")
    parser.add_argument("--library",
                        help="A registered project by name (see 'magi kb list'). "
                             "Queues into that project instead of the current directory.")
    parser.add_argument("--title", help="Title, when you already know it")
    parser.add_argument("--expect", metavar="FRAGMENT",
                        help="Fetch the paper's title (arXiv, Semantic Scholar) and refuse "
                             "to queue it unless the title contains this. For an id you "
                             "typed from memory.")
    parser.add_argument("--fetch-title", action="store_true",
                        help="Fetch and print the title before queuing; no check")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)
    return cmd_url(args)


if __name__ == "__main__":
    sys.exit(main())
