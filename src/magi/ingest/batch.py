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

from magi.core.arxiv_id import abs_url, normalize_arxiv_id
from magi.core.workspace import find_workspace_root
from magi.ingest import image_refs, ledger, routing
from magi.ingest.convert_result import ConversionResult, Finding


def _resolve_topic(explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if path.is_dir() else None
    return find_workspace_root()


def _localize_textlayer_images(md: str, images_dir: Path, slug: str) -> str:
    """Make ``pymupdf4llm``'s output look like every other route's.

    ``to_markdown`` writes each image into whatever directory it is handed and
    references it by joining that directory string with the filename. Hand it
    the staging directory — which is what we must do, or the files land in the
    process's working directory — and every reference in the document is an
    absolute path into a temporary directory. It resolves for exactly as long
    as staging exists: commit copies the Markdown and the images into the
    library, changes neither, and every figure in the document goes dark.

    The rewrite works off the directory listing rather than a regex over the
    paths, because those paths are the machine's, not ours: a user profile with
    a space in it, or a parenthesis, makes any Markdown-link pattern wrong in a
    way that would only show up on someone else's computer. The filenames are
    the one part we can match exactly.

    Names are prefixed with the document slug for the same reason the arXiv and
    tex routes do it: ``raw/papers/images/`` is shared by the whole library, and
    two documents whose sources are both called ``paper.pdf`` produce the same
    ``paper.pdf-0001-01.png``.
    """
    if not images_dir.is_dir():
        return md

    renamed: dict[str, str] = {}
    for image in sorted(images_dir.iterdir()):
        if not image.is_file():
            continue
        new_name = image_refs.namespaced(slug, image.name)
        if new_name != image.name:
            target = images_dir / new_name
            if target.exists():  # truncation collided; keep the distinct name
                new_name = image.name
            else:
                image.rename(target)
        renamed[image.name] = new_name

    def resolve(target: str):
        return renamed.get(os.path.basename(target.replace("\\", "/")))

    # One pass over the document, not one per image: a 55-page paper can carry
    # 403 of these (see ROADMAP B1), and replacing a substring per file would
    # rebuild the whole document that many times.
    out, _ = image_refs.rewrite(md, resolve)
    return out


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
        # Report the images directory even though this route writes it itself.
        # Without it the image gates never run on OCR output at all, so the one
        # route that crops its own figures was the one nobody was checking.
        images_dir = staging / "images"
        return ConversionResult(success=True, markdown_path=str(produced[-1]),
                                images_dir=str(images_dir) if images_dir.is_dir() else None)

    if route == "textlayer":
        source = Path(entry.value)
        if not source.is_file():
            return ConversionResult.failed(
                "the text-layer route needs a PDF on disk; this item has none")

        # The same verdict `ingest auto` routes on, from the same function. It
        # answers two separate questions — is there readable text, and is
        # reading it enough — and a maths paper fails the second even when it
        # sails through the first. It also never raises: a rung that cannot run
        # has to fall to the next one, not end the batch.
        verdict = routing.text_layer_verdict(source)
        print(f"[textlayer] {verdict.why}")
        if not verdict.ok:
            return ConversionResult.failed(f"not a text-layer document: {verdict.why}")

        import pymupdf4llm  # the verdict above already proved this imports

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
        slug = slugify(title)
        md = _localize_textlayer_images(md, images_dir, slug)
        fm = {"title": title, "source": str(source), "type": "papers",
              "ingested": today, "tags": [],
              "summary": "Converted from the PDF's own text layer (no OCR)."}
        # The tex, MinerU and OCR routes all recover the arXiv id from the
        # filename; this one did not, and the consequence is not cosmetic —
        # the radar fingerprints a library by arxiv_id, so a paper ingested
        # here stayed invisible to it and kept being re-surfaced as a new
        # candidate. MinerU carries a comment about having had exactly this
        # bug. Fixing it there and not looking at the other routes is how one
        # bug becomes four.
        found_id = normalize_arxiv_id(source.stem)
        if found_id:
            fm["arxiv_id"] = found_id
            fm["arxiv_url"] = abs_url(found_id)
        out = staging / f"{today}-{slug}.md"
        atomic_write(out, "---\n" + yaml.safe_dump(
            fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
            + "---\n\n" + md, encoding="utf-8")

        outcome = ConversionResult(success=True, markdown_path=str(out),
                                   images_dir=str(images_dir), pages_processed=verdict.pages)
        outcome.flag("route-textlayer",
                     f"read {verdict.pages} page(s) straight from the text layer, no OCR",
                     severity="info")
        return outcome

    if route == "add":
        # The router's answer for something that is already text. The ladder
        # converts documents; this one needs filing, not converting, and saying
        # so beats handing a Markdown file to a PDF reader.
        return ConversionResult.failed(
            "this is already text — nothing on the conversion ladder applies. "
            "File it directly with `magi ingest add`.")

    return ConversionResult.failed(f"unknown route: {route}")


def _starting_route(entry) -> tuple[str, str]:
    """Which rung this queued item starts on, and why.

    A retry names its own rung — that is how "reject" means "try the next one
    down" — and otherwise the shared router decides. Sharing it is the point:
    this used to send every non-arXiv source to ``mineru``, and because
    ``textlayer`` sits *above* ``mineru`` on the ladder, a local PDF could
    never fall back up to the free route. `ingest auto` picked it correctly all
    along, from a second implementation of the same decision.
    """
    if entry.route:
        return entry.route, "the rung this retry was queued for"
    return routing.first_rung(entry.source_type, entry.value)


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def _source_census(value: str):
    """What the source holds, when the source is a PDF we can still look at.

    Only the PDF rungs have one: ``arxiv-html`` and ``tex`` start from an
    identifier, and there is nothing on disk to count. Those get an empty
    census, and the gates that need it stand down — which is right, because
    "the output is shorter than the source" is not a question that has an
    answer when no source document exists locally.
    """
    from magi.ingest.textlayer import Census

    try:
        path = Path(value)
        if path.suffix.lower() != ".pdf" or not path.is_file():
            return Census(False)
        from magi.ingest import textlayer
        return textlayer.census(path)
    except Exception:  # noqa: BLE001 — evidence is optional, the run is not
        return Census(False)


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
        route, why = _starting_route(entry)
        print(f"[batch] {n}/{len(queued)} {entry.value} via {route} — {why}")
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
            census = _source_census(entry.value)
            findings += gates.run_all(
                md, images_dir=result.images_dir or None,
                expected_arxiv_id=entry.value if "/" in entry.value or "." in entry.value else None,
                source_chars=census.chars, source_tables=census.tables,
                source_rows=census.table_rows)
            import re
            m = re.search(r"^arxiv_id:\s*['\"]?([^'\"\n]+)", md, re.MULTILINE)
            arxiv_id = m.group(1).strip() if m else None
            m = re.search(r"^title:\s*(.+)$", md, re.MULTILINE)
            title = title or (m.group(1).strip() if m else None)

        ledger.record_item(
            topic, batch_id, req_id=entry.req_id, route=route,
            source_type=entry.source_type, source_value=entry.value,
            title=title, arxiv_id=arxiv_id,
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
                # As what it actually is. This used to say "arxiv" for
                # everything, so a rejected local PDF was requeued as an arXiv
                # paper whose identifier was a file path. It did not break —
                # the route is passed explicitly, so nothing re-derived it —
                # but the ledger recorded something untrue, and the next piece
                # of code to branch on source_type would have inherited it.
                source_type = item.source_type or routing.infer_source_type(item.source_value)
                ledger.enqueue(topic, source_type=source_type, value=item.source_value,
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
            collisions = []
            if staged_images.is_dir():
                target = dest_dir / "images"
                target.mkdir(parents=True, exist_ok=True)
                for img in staged_images.iterdir():
                    if not img.is_file():
                        continue
                    dst = target / img.name
                    # raw/<type>/images/ is shared by every document in the
                    # library, so this copy is where a name collision between
                    # two papers actually does its damage: the second write
                    # wins, nothing errors, nothing goes missing, and one paper
                    # quietly starts displaying the other's figure. Routes are
                    # supposed to namespace their filenames; this is the check
                    # that says so out loud when one of them does not — the
                    # next route we have not written yet included.
                    if dst.is_file() and dst.read_bytes() != img.read_bytes():
                        collisions.append(img.name)
                        continue
                    shutil.copy2(img, dst)
            if collisions:
                print(f"    ! {len(collisions)} image(s) kept out of images/: a "
                      f"different file of the same name is already there "
                      f"({', '.join(sorted(collisions)[:5])}) — this document's "
                      "figures would have overwritten another document's")

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
