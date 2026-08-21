"""magi ingest batch-* — run the queue, review what came out, commit the keepers.

The shape this enforces is the point of the whole exercise: acquisition and
conversion are deterministic and happen without asking anyone anything, and then
*nothing reaches the library* until a person says so, once, for a whole batch.

The gate is at commit, not at review. Waiting for every item to finish before
anyone can look would let one slow conversion — MinerU's timeout is thirty
minutes — hold a hundred good ones hostage. An item becomes reviewable the
moment it is written to the log; it becomes real only at commit.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from magi.core.workspace import find_workspace_root
from magi.ingest import ledger
from magi.ingest.convert_result import ConversionResult, Finding


def _resolve_topic(explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if path.is_dir() else None
    return find_workspace_root()


def _run_route(route: str, entry, staging: Path) -> ConversionResult:
    """Convert one queued item on one rung.

    Each rung is a function call returning a ConversionResult, which is what the
    Phase 0 refactor bought: before it, tex and mineru exited the process and the
    caller had to infer what happened by diffing a directory listing.
    """
    staging.mkdir(parents=True, exist_ok=True)

    if route == "arxiv-html":
        from magi.ingest import arxiv_html
        return arxiv_html.convert(entry.value, staging)

    if route == "tex":
        from magi.core.http import http_download
        from magi.ingest import tex2md
        # Name the download after the id: tex2md recovers the arXiv identity
        # from the filename, so this is how identity reaches the frontmatter.
        dest = staging / f"{entry.value.replace('/', '-')}.tar.gz"
        try:
            http_download(f"https://arxiv.org/e-print/{entry.value}", dest)
        except Exception as exc:  # noqa: BLE001
            return ConversionResult.failed(f"could not fetch e-print: {exc}")
        head = dest.read_bytes()[:5]
        if head == b"%PDF-":
            return ConversionResult.failed(
                "arXiv served a PDF, not source — this submission has no LaTeX")
        return tex2md.convert(str(dest), str(staging))

    if route == "mineru":
        from magi.ingest import mineru
        return mineru.convert(entry.value, str(staging))

    if route == "ocr":
        result = subprocess.run(
            [sys.executable, "-m", "magi", "ingest", "ocr", entry.value,
             "-o", str(staging)],
            capture_output=True, text=True)
        if result.returncode != 0:
            return ConversionResult.failed("local OCR failed.", result.stderr.strip())
        produced = sorted(staging.glob("*.md"), key=lambda p: p.stat().st_mtime)
        if not produced:
            return ConversionResult.failed("local OCR produced no markdown.")
        return ConversionResult(success=True, markdown_path=str(produced[-1]))

    if route == "textlayer":
        from magi.ingest import textlayer

        source = Path(entry.value)
        if not source.is_file():
            return ConversionResult.failed(
                "the text-layer route needs a PDF on disk; this item has none")

        # The gate is the cheap half and runs on PyMuPDF alone. It answers two
        # separate questions — is there readable text, and is reading it enough —
        # and a maths paper fails the second even when it sails through the first.
        verdict = textlayer.inspect(source)
        print(f"[textlayer] {verdict.reason}")
        if not verdict.route_here:
            return ConversionResult.failed(
                f"not a text-layer document: {verdict.reason}")

        try:
            import pymupdf4llm
        except ImportError:
            return ConversionResult.failed(
                "this PDF has a clean, math-free text layer and could be read "
                "without OCR, but pymupdf4llm is not installed. "
                "Install it with: pip install 'magi-research[textlayer]'")

        staging.mkdir(parents=True, exist_ok=True)
        images_dir = staging / "images"
        try:
            md = pymupdf4llm.to_markdown(
                str(source), write_images=True, image_path=str(images_dir))
        except Exception as exc:  # noqa: BLE001
            return ConversionResult.failed(f"text-layer extraction failed: {exc}")

        from datetime import datetime

        import yaml

        from magi.core.wiki_common import atomic_write, slugify

        today = datetime.now().strftime("%Y-%m-%d")
        title = entry.title or source.stem.replace("_", " ").replace("-", " ").title()
        fm = {"title": title, "source": str(source), "type": "papers",
              "ingested": today, "tags": [],
              "summary": "Converted from the PDF's own text layer (no OCR)."}
        out = staging / f"{today}-{slugify(title)}.md"
        atomic_write(out, "---\n" + yaml.safe_dump(
            fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
            + "---\n\n" + md, encoding="utf-8")

        outcome = ConversionResult(success=True, markdown_path=str(out),
                                   images_dir=str(images_dir), pages_processed=verdict.pages)
        outcome.flag("route-textlayer",
                     f"read {verdict.pages} page(s) straight from the text layer, no OCR",
                     severity="info")
        return outcome

    return ConversionResult.failed(f"unknown route: {route}")


def _starting_route(entry) -> str:
    if entry.route:
        return entry.route
    if entry.source_type in ("arxiv", "url", "doi"):
        return "arxiv-html"
    return "mineru"


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def cmd_run(args) -> int:
    topic = _resolve_topic(args.topic_dir)
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1

    # Snapshot before doing anything. A "reject and retry" that lands mid-run
    # belongs to the *next* batch; sweeping it into this one would blur the two.
    queued = ledger.pending(topic)
    if args.limit:
        queued = queued[:args.limit]
    if not queued:
        print("nothing queued.")
        return 0

    batch_id = ledger.start_batch(topic)
    print(f"[batch] {batch_id}: {len(queued)} item(s)")

    for n, entry in enumerate(queued, 1):
        route = _starting_route(entry)
        print(f"[batch] {n}/{len(queued)} {entry.value} via {route}")
        staging = ledger.staging_dir(topic, batch_id) / entry.req_id
        try:
            result = _run_route(route, entry, staging)
        except Exception as exc:  # noqa: BLE001 — one bad item must not end the run
            result = ConversionResult.failed(f"{type(exc).__name__}: {exc}")

        findings = list(result.findings)
        arxiv_id = None
        title = entry.title
        if result.success and result.markdown_path:
            from magi.ingest import gates
            md = Path(result.markdown_path).read_text(encoding="utf-8", errors="replace")
            findings += gates.run_all(
                md, images_dir=result.images_dir or None,
                expected_arxiv_id=entry.value if "/" in entry.value or "." in entry.value else None)
            import re
            m = re.search(r"^arxiv_id:\s*['\"]?([^'\"\n]+)", md, re.MULTILINE)
            arxiv_id = m.group(1).strip() if m else None
            m = re.search(r"^title:\s*(.+)$", md, re.MULTILINE)
            title = title or (m.group(1).strip() if m else None)

        ledger.record_item(
            topic, batch_id, req_id=entry.req_id, route=route,
            source_value=entry.value, title=title, arxiv_id=arxiv_id,
            staged_md=result.markdown_path if result.success else None,
            findings=findings,
            error=None if result.success else "; ".join(result.errors) or "failed",
            retry_of=entry.retry_of)

        status = "ok" if result.success else "FAILED"
        print(f"[batch]   {status}"
              + (f" — {len(findings)} finding(s)" if findings else ""))

    print(f"\nReview it:  magi ingest batch-list --batch {batch_id}")
    print(f"Then:       magi ingest batch-commit")
    if args.json:
        print(json.dumps({"batch_id": batch_id, "items": len(queued)}))
    return 0


# --------------------------------------------------------------------------
# list
# --------------------------------------------------------------------------

def cmd_list(args) -> int:
    topic = _resolve_topic(args.topic_dir)
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1

    batch_ids = [args.batch] if args.batch else ledger.list_batches(topic)
    if not batch_ids:
        print("no batches yet. Queue something with 'magi ingest url', "
              "then run 'magi ingest batch-run'.")
        return 0

    payload = []
    for batch_id in batch_ids:
        items = ledger.load_batch(topic, batch_id)
        undecided = [i for i in items if not i.decided]
        payload.append({
            "batch_id": batch_id,
            "items": [i._asdict() for i in items],
            "undecided": len(undecided),
        })
        if args.json:
            continue
        print(f"\n=== {batch_id} — {len(items)} item(s), {len(undecided)} undecided ===")
        for item in items:
            mark = {"approve": "+", "reject": "-", None: " "}.get(item.decision, "?")
            state = "FAILED" if item.error else (item.route)
            print(f"  [{mark}] {item.item_id}  {state:<12} {(item.title or item.source_value)[:56]}")
            if item.error:
                print(f"        error: {item.error[:100]}")
            for f in item.findings:
                print(f"        [{f.get('severity', 'flag')}] {f.get('code')}: "
                      f"{str(f.get('detail'))[:90]}")
            if item.committed_path:
                print(f"        committed: {item.committed_path}")

    if args.json:
        print(json.dumps({"batches": payload}, ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------------
# decide
# --------------------------------------------------------------------------

def cmd_decide(args) -> int:
    topic = _resolve_topic(args.topic_dir)
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1

    for batch_id in ledger.list_batches(topic):
        items = {i.item_id: i for i in ledger.load_batch(topic, batch_id)}
        item = items.get(args.item)
        if item is None:
            continue

        ledger.record_decision(topic, batch_id, args.item, args.decision)
        print(f"{args.item}: {args.decision}")

        if args.decision == "reject":
            nxt = ledger.next_rung(item.route)
            if nxt:
                ledger.enqueue(topic, source_type="arxiv", value=item.source_value,
                               route=nxt, retry_of=item.item_id, title=item.title)
                print(f"  requeued on the next route down: {nxt} "
                      "(it will appear in the next batch)")
            else:
                # Never silently escalate to the per-page vision fan-out — that
                # is the failure this pipeline exists to prevent. Say what it
                # would cost and let a person choose it.
                print(f"  {item.route} is the last automatic route. Nothing below it "
                      "runs on its own.")
                print("  To transcribe it page by page with your agent, ask for that "
                      "explicitly — it costs roughly one subagent call per page.")
        return 0

    print(f"no such item: {args.item}", file=sys.stderr)
    return 1


# --------------------------------------------------------------------------
# commit
# --------------------------------------------------------------------------

def cmd_commit(args) -> int:
    topic = _resolve_topic(args.topic_dir)
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1

    committed = 0
    skipped_batches = []
    for batch_id in ledger.list_batches(topic):
        items = ledger.load_batch(topic, batch_id)
        if not items:
            continue
        undecided = [i for i in items if not i.decided and not i.committed_path]
        if undecided:
            skipped_batches.append((batch_id, len(undecided)))
            continue

        for item in items:
            if item.decision != "approve" or item.committed_path or not item.staged_md:
                continue
            src = Path(item.staged_md)
            if not src.is_file():
                print(f"  {item.item_id}: staged file is gone ({src})")
                continue
            dest_dir = topic / "raw" / "papers"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            shutil.copy2(src, dest)

            staged_images = Path(src).parent / "images"
            if staged_images.is_dir():
                target = dest_dir / "images"
                target.mkdir(parents=True, exist_ok=True)
                for img in staged_images.iterdir():
                    if img.is_file():
                        shutil.copy2(img, target / img.name)

            subprocess.run(
                [sys.executable, "-m", "magi", "ingest", "finalize", "none",
                 "--topic-dir", str(topic), "--md-file", str(dest), "--skip-lint",
                 "--log-msg", f"batch ingest ({item.route}): {dest.name}"],
                capture_output=True, text=True)

            ledger.record_commit(topic, batch_id, item.item_id, str(dest))
            print(f"  + {dest.relative_to(topic)}")
            committed += 1

    if committed:
        # One lint/graph/index pass for the whole batch, the same shape
        # `ingest auto` already uses rather than paying it per file.
        subprocess.run(
            [sys.executable, "-m", "magi", "ingest", "finalize", "none",
             "--topic-dir", str(topic), "--lint-only"],
            capture_output=True, text=True)
        print(f"\n{committed} document(s) committed and indexed.")
    else:
        print("nothing to commit.")
    for batch_id, n in skipped_batches:
        print(f"  {batch_id}: left alone, {n} item(s) still undecided")
    return 0


# --------------------------------------------------------------------------

_VERBS = {
    "run": ("magi ingest batch-run",
            "Acquire, convert and gate-check everything in the queue."),
    "list": ("magi ingest batch-list",
             "Show batches awaiting approval, with findings."),
    "decide": ("magi ingest batch-decide",
               "Approve, reject or undo one item. Rejecting requeues it a rung down."),
    "commit": ("magi ingest batch-commit",
               "Move approved documents into raw/. Refuses a batch with undecided items."),
}


def main(argv=None) -> int:
    """Dispatch one verb.

    The CLI table routes `magi ingest batch-run` here with "run" prepended, so
    each verb gets a parser whose prog name is the command the user actually
    typed. A single shared parser advertised `magi ingest batch {run,list,...}`
    in its usage line — a command that does not exist, since there is no
    ("ingest", "batch") entry to dispatch it.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    verb = argv[0] if argv and argv[0] in _VERBS else None
    if verb is None:
        print(f"magi ingest batch: expected one of {', '.join(_VERBS)}",
              file=sys.stderr)
        return 2

    prog, description = _VERBS[verb]
    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("--topic-dir", help="Workspace root (default: discovered)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    if verb == "run":
        parser.add_argument("--limit", type=int,
                            help="Process at most N queued items")
    if verb == "list":
        parser.add_argument("--batch", help="Show only this batch id")
    if verb == "decide":
        parser.add_argument("--item", required=True, help="Item id (see batch-list)")
        parser.add_argument("--decision", required=True,
                            choices=["approve", "reject", "reset"])

    args = parser.parse_args(argv[1:])
    # Verb-specific flags are absent from the other parsers; give every handler
    # the same shape so it does not have to know which verb it was reached by.
    for name in ("batch", "item", "decision", "limit"):
        if not hasattr(args, name):
            setattr(args, name, None)

    return {"run": cmd_run, "list": cmd_list,
            "decide": cmd_decide, "commit": cmd_commit}[verb](args)


if __name__ == "__main__":
    sys.exit(main())
