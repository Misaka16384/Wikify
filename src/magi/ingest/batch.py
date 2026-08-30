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


def _textlayer_with_figures(source: Path, images_dir: Path, slug: str,
                            pages: int) -> tuple[str, str]:
    """Read the text layer page by page, cropping each figure by its caption.

    Returns the document and a sentence saying what happened to the figures,
    which becomes a finding either way — "no figures were found" and "figures
    were never looked for" are different facts and the reader needs to be able
    to tell them apart.

    Why per page rather than over the whole document: a figure is placed above
    the caption line that names it, and the search for "Figure 3" over a whole
    paper finds the sentence in the body that *mentions* Figure 3 long before
    it reaches the caption. Restricting each search to the page the figure was
    cropped from is what makes the anchor mean anything.

    ``page_chunks`` carries no page number in this version of ``pymupdf4llm``,
    so the mapping is positional, and positional mappings are exactly the kind
    that break silently when an upstream changes. Hence the count check: if the
    chunks are not one per page, the figures go at the end of the document
    instead of in the wrong places. Measured on a 34-page paper — 34 chunks, and
    concatenating them reproduces the plain output byte for byte.
    """
    import pymupdf4llm

    from magi.ingest.figures import extract_figures, inject_figures

    try:
        figures = extract_figures(str(source), str(images_dir), prefix=slug)
    except Exception as exc:  # noqa: BLE001 — a missing figure is not a lost paper
        return pymupdf4llm.to_markdown(str(source)), \
            f"figures could not be extracted ({exc}); the text is unaffected"

    chunks = pymupdf4llm.to_markdown(str(source), page_chunks=True)
    aligned = (isinstance(chunks, list) and len(chunks) == pages
               and all(isinstance(c, dict) and "text" in c for c in chunks))

    if not figures:
        md = "".join(c["text"] for c in chunks) if aligned \
            else pymupdf4llm.to_markdown(str(source))
        return md, ("no figures found: this route anchors on caption text, so a "
                    "document whose figures are uncaptioned yields none")

    by_page: dict[int, list] = {}
    for fig in figures:
        by_page.setdefault(fig.page, []).append(fig)

    if not aligned:
        md = pymupdf4llm.to_markdown(str(source))
        md = inject_figures(md, figures, image_refs.IMAGE_DIR_NAME)
        return md, (f"{len(figures)} figure(s) cropped, but appended rather than "
                    "placed: the extractor did not return one chunk per page")

    parts = []
    for index, chunk in enumerate(chunks, 1):
        text = chunk["text"]
        page_figs = by_page.get(index)
        if page_figs:
            text = inject_figures(text, page_figs, image_refs.IMAGE_DIR_NAME)
        parts.append(text)

    labelled = sum(1 for f in figures if f.label)
    return "".join(parts), (
        f"{len(figures)} figure(s) cropped by caption anchor, {labelled} with a "
        "caption, each placed above the caption line that names it")


#: What the three PDF rungs say when there is no PDF to work on. One
#: sentence, because three rungs inventing three ways to say "the file called
#: 2307.12008 is not here" is how a single missing download reads as four
#: unrelated faults.
NO_PDF = ("no PDF to read for this item — the identity has no LaTeX source "
          "and no PDF could be fetched for it")


def _local_pdf(entry, staging: Path) -> Path | None:
    """The PDF for this queued item, fetching it if the item is an identity.

    The gap this closes: `arxiv-html` and `tex` are handed an arXiv *id*, and
    `textlayer`, `mineru` and `ocr` all expect a *path*. Nothing on the ladder
    converted one into the other, so a PDF-only submission — an ordinary thing
    — failed every rung, three of them for the same reason wearing three
    different messages.

    Cached in staging, so falling from one PDF rung to the next costs one
    download rather than three.
    """
    from magi.core.http import http_download

    direct = Path(entry.value)
    if direct.is_file():
        return direct

    # Only a real arXiv identity. `IDENTITY_TYPES` also covers `url` and
    # `doi`, and `arxiv.org/pdf/<some url>` is not a thing.
    try:
        ident = normalize_arxiv_id(entry.value)
    except Exception:  # noqa: BLE001
        ident = ""
    if not ident:
        return None

    dest = staging / f"{ident.replace('/', '-')}.pdf"
    if dest.is_file() and dest.stat().st_size:
        return dest
    staging.mkdir(parents=True, exist_ok=True)
    try:
        http_download(f"https://arxiv.org/pdf/{ident}", dest)
    except Exception:  # noqa: BLE001 — a rung that cannot run falls to the next
        return None
    # arXiv answers /pdf/ for ids that have no PDF with an HTML error page.
    if dest.read_bytes()[:5] != b"%PDF-":
        try:
            dest.unlink()
        except OSError:
            pass
        return None
    return dest


def _run_route(route: str, entry, staging: Path, topic: Path | None = None) -> ConversionResult:
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
            # Keep it. This is the paper, and the rungs below this one all
            # want exactly this file — they used to go looking for it by the
            # arXiv id and fail three times over a document already on disk.
            kept = staging / f"{entry.value.replace('/', '-')}.pdf"
            try:
                dest.replace(kept)
            except OSError:
                pass
            return ConversionResult.failed(
                "arXiv served a PDF, not source — this submission has no "
                "LaTeX; the PDF was kept for the routes below")
        return tex2md.convert(str(dest), str(staging))

    if route == "mineru":
        from magi.ingest import mineru

        # Checked here, before the file is opened and long before anything is
        # uploaded. `ocr.use_mineru` was in `CONFIG_FIELDS`, in both shipped
        # config files and rendered as a checkbox in the WebUI, and nothing in
        # `ingest/` read it — so turning it off changed no behaviour and the
        # document went to a paid cloud service anyway. A knob wired to
        # nothing is worse than a missing one: the person believes they have
        # decided.
        from magi.core.config_loader import get as _cfg_get
        from magi.core.config_loader import load_config as _load_config

        if not _cfg_get(_load_config(start=topic), "ocr.use_mineru", True):
            return ConversionResult.failed(
                "the MinerU rung is switched off (`ocr.use_mineru: false`) — "
                "nothing was uploaded; the ladder continues below it")
        source = _local_pdf(entry, staging)
        if source is None:
            return ConversionResult.failed(NO_PDF)
        return mineru.convert(str(source), str(staging))

    if route == "ocr":
        source = _local_pdf(entry, staging)
        if source is None:
            return ConversionResult.failed(NO_PDF)
        result = subprocess.run(
            [sys.executable, "-m", "magi", "ingest", "ocr", str(source),
             "-o", str(staging)],
            capture_output=True, text=True)
        if result.returncode != 0:
            # The last line, not the traceback. A subprocess that died with a
            # stack trace put the whole thing — file paths and all — through
            # the batch report and out of the CLI, in plain output and in
            # `--json` alike.
            tail = [line for line in (result.stderr or "").strip().splitlines()
                    if line.strip()]
            return ConversionResult.failed("local OCR failed.",
                                           tail[-1].strip() if tail else "")
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
        source = _local_pdf(entry, staging)
        if source is None:
            return ConversionResult.failed(NO_PDF)

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

        from datetime import datetime

        import yaml

        from magi.core.config_loader import get as cfg_get, load_config
        from magi.core.wiki_common import atomic_write, slugify

        today = datetime.now().strftime("%Y-%m-%d")
        title = entry.title or source.stem.replace("_", " ").replace("-", " ").title()
        slug = slugify(title)

        # Two ways to get pictures out of a PDF, and they are not variations of
        # one setting -- they answer different questions. Cropping by caption
        # anchor asks "what does this paper call a figure"; `write_images=True`
        # asks "what image objects are embedded", and on a real paper with 4
        # figures that came to 117 files, the smallest a 40x24 strip that was a
        # display equation. So the flag selects between them rather than adding
        # to the default, and the default is the one that answers the question
        # a reader is actually asking.
        raw_objects = bool(cfg_get(load_config(start=topic),
                                   "ingest.textlayer_images", False))
        try:
            if raw_objects:
                md = pymupdf4llm.to_markdown(str(source), write_images=True,
                                             image_path=str(images_dir))
                md = _localize_textlayer_images(md, images_dir, slug)
                figure_note = ("every embedded image object was exported, because "
                               "`ingest.textlayer_images` is on -- expect strips of "
                               "equations and rules among the real figures")
            else:
                md, figure_note = _textlayer_with_figures(
                    source, images_dir, slug, verdict.pages)
        except Exception as exc:  # noqa: BLE001
            return ConversionResult.failed(f"text-layer extraction failed: {exc}")

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

        # An *empty* images directory is not an images directory. The extractor
        # creates it before it knows whether it will find anything, so testing
        # for existence would report one on every document and hand the image
        # gates a directory to have opinions about that no route filled.
        has_images = images_dir.is_dir() and any(images_dir.iterdir())
        outcome = ConversionResult(
            success=True, markdown_path=str(out),
            images_dir=str(images_dir) if has_images else None,
            pages_processed=verdict.pages)
        outcome.flag("route-textlayer",
                     f"read {verdict.pages} page(s) straight from the text layer, no OCR",
                     severity="info")
        # Say what happened to the figures either way. This route used to export
        # none at all and say so; now it crops them, and "8 figures, all with
        # captions" and "no figures found" are both facts the reviewer needs,
        # because only one of them means something went wrong.
        outcome.flag("figures", figure_note, severity="info")
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
            result = _run_route(route, entry, staging, topic)
        except Exception as exc:  # noqa: BLE001 — one bad item must not end the run
            result = ConversionResult.failed(f"{type(exc).__name__}: {exc}")

        findings = list(result.findings)
        # The net under every route: a route that came back successful while
        # carrying errors it never raised as a finding gets one here. See
        # ConversionResult.silent_about — this is the seam every route passes
        # through, so a route written later cannot quietly skip it.
        silent = result.silent_about
        if silent:
            findings.append(Finding(
                "route-errors-unreported",
                "%s reported success but recorded %d error(s) without flagging "
                "them: %s" % (route, len(silent), "; ".join(silent))))
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

        # A route can come back "successful" and still be carrying errors: the
        # OCR route converts page by page, and a page that failed leaves the
        # rest of the document intact. Gating the ledger's error field on
        # ``success`` meant those errors were recorded as ``None`` — the item
        # showed up in review as clean while missing whole pages. What the
        # route said went wrong is recorded whenever it said anything.
        error = "; ".join(result.errors) if result.errors else None
        if not result.success and not error:
            error = "failed"

        ledger.record_item(
            topic, batch_id, req_id=entry.req_id, route=route,
            source_type=entry.source_type, source_value=entry.value,
            title=title, arxiv_id=arxiv_id,
            staged_md=result.markdown_path if result.success else None,
            findings=findings,
            error=error,
            retry_of=entry.retry_of)

        status = "ok" if result.success else "FAILED"
        if result.success and result.errors:
            status = "ok (partial)"
        print(f"[batch]   {status}"
              + (f" — {len(findings)} finding(s)" if findings else ""))

    print(f"\nReview it:  magi ingest review --batch {batch_id}")
    print(f"Then:       magi ingest review --commit")
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

    known = ledger.list_batches(topic)
    if args.batch and args.batch not in known:
        # Not an empty batch — no such batch. Printing "0 items" for a typo
        # reads as "everything in it is already decided", which is the one
        # conclusion that makes a person stop looking.
        print(f"no batch {args.batch!r} — run without --batch to see them",
              file=sys.stderr)
        return 1
    batch_ids = [args.batch] if args.batch else known
    # The queue, not just the batches. A paper lives in one of two places
    # before it reaches the library — still queued, or claimed by a batch —
    # and this command only ever read the second. With two papers waiting it
    # said "no batches yet. Queue something", which is false about the
    # workspace and advises the thing the person has already done; after an
    # interrupted run it is how a paper appears to have vanished.
    waiting = len(ledger.pending(topic))
    if not batch_ids:
        if waiting:
            print(f"{waiting} item(s) queued and not yet run.")
            print("Run them:  magi ingest batch-run")
        else:
            print("no batches yet. Queue something with 'magi ingest url', "
                  "then run 'magi ingest batch-run'.")
        return 0
    if waiting:
        print(f"({waiting} more item(s) queued and not yet run — "
              f"'magi ingest batch-run')")

    payload = []
    for batch_id in batch_ids:
        # Flagged and undecided first. The order is the whole of the triage —
        # nothing is hidden and nothing is decided here, and an item with no
        # flags is not thereby checked. See `ledger.review_order`.
        items = ledger.review_order(ledger.load_batch(topic, batch_id))
        undecided = ledger.undecided(items)
        if not items:
            # `start_batch` writes its record before the first item is
            # converted, so a run that was interrupted leaves this behind. It
            # is not a batch whose items were all decided — it is a batch that
            # never got one, and saying "0 item(s)" let it read as the former.
            print(f"=== {batch_id} — started, nothing recorded "
                  f"(the run did not finish; anything queued is still queued) ===")
            continue
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
            nxt = ledger.requeue_next_rung(topic, item)
            if nxt:
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

def _finalize(argv: list, *, what: str) -> bool:
    """Run one `ingest finalize` pass and say so when it did not work.

    Both calls used to be fire-and-forget with ``capture_output=True``, which
    is the strongest possible way to lose an error: the return code was never
    read and the captured stderr was never printed, so a finalize that failed
    on a locked database looked exactly like one that succeeded.

    The copy into ``raw/`` has already happened by the time this runs, so a
    failure here does not mean "nothing was committed" — it means the document
    is on disk but was not linted, graphed or indexed. Say that, rather than
    implying either more or less than it does.

    Known limit: ``ingest.pipeline`` prints warnings and still returns 0 for
    several of its own sub-steps, so a zero return code is not proof that
    every stage ran. This catches the outer failure only.
    """
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode == 0:
        return True
    detail = (proc.stderr or proc.stdout or "").strip().splitlines()
    print(f"    ! finalize failed for {what} (exit {proc.returncode}) — the file "
          "is in raw/ but was not linted or indexed", file=sys.stderr)
    for line in detail[-5:]:
        print(f"      {line}", file=sys.stderr)
    return False


def cmd_commit(args) -> int:
    topic = _resolve_topic(args.topic_dir)
    if topic is None:
        print("no workspace found", file=sys.stderr)
        return 1

    # `--batch` means the same thing here as it does in the listing: this one.
    # It used to narrow what you looked at and then be dropped on the way to
    # the commit, so "land the batch I was just reviewing" landed all of them.
    wanted = getattr(args, "batch", None)
    known = ledger.list_batches(topic)
    if wanted and wanted not in known:
        print(f"no batch {wanted!r} — 'magi ingest review' lists them",
              file=sys.stderr)
        return 1

    committed = 0
    skipped_batches = []
    for batch_id in ([wanted] if wanted else known):
        items = ledger.load_batch(topic, batch_id)
        if not items:
            continue
        undecided = ledger.blocking_commit(items)
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
            # raw/ is ORIGINAL — nothing regenerates a document that is already
            # in the library. The image copy below has refused to overwrite a
            # different file of the same name for a while; the document itself
            # had no such check, so a second conversion landing on the same
            # slug — a v1/v2 re-ingest, two papers sharing a title, a route
            # that does not namespace its filenames — destroyed the earlier
            # one with no message at all. Keep both and say which is which;
            # an identical re-commit still just lands on itself.
            if dest.is_file() and dest.read_bytes() != src.read_bytes():
                dest = dest_dir / f"{src.stem}--{item.item_id}{src.suffix}"
                print(f"    ! raw/papers/{src.name} already exists with different "
                      f"content — kept both, this one as {dest.name}")
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

            _finalize(
                [sys.executable, "-m", "magi", "ingest", "finalize", "none",
                 "--topic-dir", str(topic), "--md-file", str(dest), "--skip-lint",
                 "--log-msg", f"batch ingest ({item.route}): {dest.name}"],
                what=dest.name)

            ledger.record_commit(topic, batch_id, item.item_id, str(dest))
            print(f"  + {dest.relative_to(topic)}")
            committed += 1

    if committed:
        # One lint/graph/reindex pass for the whole batch, the same shape
        # `ingest auto` already uses rather than paying it per file.
        _finalize(
            [sys.executable, "-m", "magi", "ingest", "finalize", "none",
             "--topic-dir", str(topic), "--lint-only"],
            what="the lint/graph/reindex pass")
        # "and indexed" was not true. The finalize pass runs lint, graph build
        # and wiki reindex, and deliberately not `magi index` — the expensive
        # embedding pass, and the only thing that makes a document findable by
        # `magi search`. Nor does committing compile anything into
        # `wiki/references/`. Both were left for the reader to discover by
        # noticing the paper they just committed could not be found.
        print(f"\n{committed} document(s) committed to raw/. Wiki tables and "
              "the concept graph are refreshed.")
        print("Next: 'magi index' to make them searchable, and the "
              "magi:compile skill to turn them into reference cards.")
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
               "Approve, reject or undo one item. **Rejecting is not "
               "discarding**: it requeues the item on the next rung of the "
               "conversion ladder (arxiv-html -> tex -> textlayer -> mineru "
               "-> ocr), which is how you walk a stubborn paper down it."),
    "commit": ("magi ingest batch-commit",
               "Move approved documents into raw/. Refuses a batch with undecided items."),
    "review": ("magi ingest review",
               "The approval step, in one command: list what is waiting, decide one "
               "item (--item/--decision), or commit what is approved (--commit)."),
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
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir", help="Workspace root (default: discovered)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    if verb == "run":
        parser.add_argument("--limit", type=int,
                            help="Process at most N queued items")
    if verb in ("list", "review"):
        parser.add_argument("--batch", help="Show only this batch id")
    if verb == "decide":
        parser.add_argument("--item", required=True, help="Item id (see the listing)")
        parser.add_argument("--decision", required=True,
                            choices=["approve", "reject", "reset"])
    if verb == "review":
        # One command for a three-step loop that is really one activity:
        # look at what is waiting, say yes or no to a row, and land the yeses.
        # Three separate commands made the middle step feel like a different
        # tool from the one that showed you the row.
        parser.add_argument("--item", help="Item id from the listing")
        parser.add_argument("--decision", choices=["approve", "reject", "reset"],
                            help="What to do with --item")
        parser.add_argument("--commit", action="store_true",
                            help="Move everything approved into raw/")

    args = parser.parse_args(argv[1:])
    # Verb-specific flags are absent from the other parsers; give every handler
    # the same shape so it does not have to know which verb it was reached by.
    for name in ("batch", "item", "decision", "limit"):
        if not hasattr(args, name):
            setattr(args, name, None)

    if verb == "review":
        if args.commit:
            return cmd_commit(args)
        if args.item or args.decision:
            if not (args.item and args.decision):
                print("magi ingest review: --item and --decision go together",
                      file=sys.stderr)
                return 2
            return cmd_decide(args)
        return cmd_list(args)

    return {"run": cmd_run, "list": cmd_list,
            "decide": cmd_decide, "commit": cmd_commit}[verb](args)


if __name__ == "__main__":
    sys.exit(main())
