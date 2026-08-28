"""magi ingest auto — one command for "get this into the library".

Picking between `ingest tex`, `ingest mineru`, `ingest ocr` and `ingest add`
is a decision about file format and what happens to be configured, not about
research. This routes by extension and available tooling, then runs the
`finalize` pass every route needs — including the batch pattern (per-file
work with --skip-lint, one global lint/graph/index pass at the end).

    magi ingest auto paper.pdf
    magi ingest auto            # everything in inbox/
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from magi.core.config_loader import load_config
from magi.core.workspace import INBOX_NON_SOURCES, find_workspace_root
from magi.ingest import routing

# Re-exported rather than redefined: two lists of "what counts as LaTeX source"
# is how two commands come to disagree about one file.
TEX_SUFFIXES = routing.TEX_SUFFIXES
TEXT_SUFFIXES = routing.TEXT_SUFFIXES
SKIP_NAMES = INBOX_NON_SOURCES


def _cfg_get(cfg: dict, dotted: str, default=None):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def classify(path: Path, cfg: dict) -> Tuple[str, str]:
    """(route, why) for one file. route is a subcommand name or 'skip'.

    Two questions, and only the second belongs to this command. *What should
    run* is `routing.first_rung`, shared with `batch-run` — deciding it twice
    is how the two commands came to disagree about local PDFs, with this one
    right and the batch ladder wrong. *What can run here* is this function's
    own, because `ingest auto` converts immediately and has no ladder to fall
    down: a rung whose tooling is missing has to become `skip` with a sentence
    saying what to install, not a failure three steps later.
    """
    name = path.name.lower()
    if name.endswith(TEXT_SUFFIXES):
        return "add", "already text — filed as-is"
    if not name.endswith(TEX_SUFFIXES) and not name.endswith(".pdf"):
        return "skip", f"no route for {path.suffix or 'this file'}"

    route, why = routing.first_rung("file", str(path))

    if route == "tex":
        if shutil.which("pandoc") or _cfg_get(cfg, "tools.pandoc_path"):
            return "tex", why
        return "skip", "LaTeX source, but pandoc is not installed"

    if route == "textlayer":
        # `first_rung` says this document *should* be read from its own text
        # layer and deliberately does not care whether the extractor is here.
        # This command has no ladder to fall down, so it is the one that has to
        # look — and when it is missing, the honest move is the next rung with
        # the reason attached, not a failure that never names the package.
        verdict = routing.text_layer_verdict(path)
        if verdict.available:
            return "textlayer", why
        why = (f"{why}; falling to a model instead — "
               f"install it to read this one for free")

    # Everything else is a PDF needing a model. Which model is available is a
    # local question the ladder would answer by falling; here it is answered by
    # looking, so the reason a file was skipped names the thing to fix.
    if _cfg_get(cfg, "ocr.mineru_api_token"):
        return "mineru", f"{why}; MinerU token configured"
    if shutil.which("ollama"):
        return "ocr", f"{why}; no MinerU token, using local OCR"
    return "skip", ("PDF, but neither a MinerU token nor Ollama is available "
                    "(set ocr.mineru_api_token, or install Ollama)")


def default_type(route: str) -> str:
    return "notes" if route == "add" else "papers"


def _run(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "magi", *cmd], cwd=str(cwd),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def _newest_markdown(dest: Path, before: set) -> Optional[Path]:
    """Which file the converter just produced (routes name their own output)."""
    now = {p for p in dest.glob("*.md")} if dest.is_dir() else set()
    fresh = now - before
    if not fresh:
        return None
    return max(fresh, key=lambda p: p.stat().st_mtime)


def ingest_one(path: Path, topic: Path, cfg: dict, raw_type: Optional[str],
               dry_run: bool) -> dict:
    route, why = classify(path, cfg)
    result = {"file": str(path), "route": route, "why": why, "ok": route != "skip",
              "output": None}
    if route == "skip" or dry_run:
        return result

    rtype = raw_type or default_type(route)
    dest = topic / "raw" / rtype
    dest.mkdir(parents=True, exist_ok=True)
    before = {p for p in dest.glob("*.md")}

    if route == "add":
        proc = _run(["ingest", "add", "--file", str(path), "--type", rtype,
                     "--topic-dir", str(topic), "--move"], topic)
    else:
        proc = _run(["ingest", route, str(path), "-o", str(dest)], topic)

    result["ok"] = proc.returncode == 0
    result["log"] = (proc.stdout or "") + (proc.stderr or "")
    if not result["ok"]:
        return result

    produced = _newest_markdown(dest, before)
    result["output"] = str(produced) if produced else None

    # Every route funnels into finalize; --skip-lint so a batch does the
    # lint/graph/index pass once at the end rather than per file.
    fin = ["ingest", "finalize", str(path) if route != "add" else "none",
           "--topic-dir", str(topic), "--skip-lint",
           "--log-msg", f"auto-ingest ({route}): {path.name}"]
    if produced:
        fin += ["--md-file", str(produced)]
    fp = _run(fin, topic)
    result["finalized"] = fp.returncode == 0
    return result


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi ingest auto",
        description="Route each file to the right ingestion command and finalize it.")
    parser.add_argument("paths", nargs="*",
                        help="Files or directories (default: the workspace's inbox/).")
    parser.add_argument("--topic-dir", default=None, help="Workspace root (default: discovered).")
    parser.add_argument("--type", dest="raw_type", default=None,
                        help="raw/ subdirectory to file into (default: papers, or notes for text).")
    parser.add_argument("--dry-run", action="store_true", help="Show the routing, convert nothing.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    args = parser.parse_args(argv)

    topic = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if topic is None:
        msg = "no workspace found (run inside a topic directory or pass --topic-dir)"
        print(json.dumps({"error": msg}, ensure_ascii=False) if args.json else f"error: {msg}",
              file=None if args.json else sys.stderr)
        return 1

    targets: List[Path] = []
    for raw in (args.paths or [str(topic / "inbox")]):
        p = Path(raw)
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        if p.is_dir():
            targets += [f for f in sorted(p.iterdir())
                        if f.is_file() and f.name not in SKIP_NAMES and not f.name.startswith(".")]
        elif p.is_file():
            targets.append(p)
        else:
            print(f"warning: not found: {p}", file=sys.stderr)

    if not targets:
        msg = f"nothing to ingest (looked in {args.paths or [str(topic / 'inbox')]})"
        print(json.dumps({"error": msg, "ingested": []}, ensure_ascii=False) if args.json else msg)
        return 1

    # From the workspace this command was pointed at, not from wherever the
    # shell happens to be. `magi ingest auto --topic-dir B`, run from A,
    # used to read A's config and write B's library.
    cfg = load_config(start=topic)
    results = [ingest_one(p, topic, cfg, args.raw_type, args.dry_run) for p in targets]
    done = [r for r in results if r["ok"] and r["route"] != "skip"]

    # One lint/graph/index pass for the whole batch.
    if done and not args.dry_run:
        _run(["ingest", "finalize", "none", "--topic-dir", str(topic), "--lint-only"], topic)

    if args.json:
        print(json.dumps({"topic": str(topic), "dry_run": args.dry_run,
                          "results": results}, ensure_ascii=False))
        return 0 if done or args.dry_run else 1

    verb = "would ingest" if args.dry_run else "ingested"
    for r in results:
        if r["route"] == "skip":
            print(f"  skip  {Path(r['file']).name}  — {r['why']}")
        elif r["ok"]:
            out = f" -> {Path(r['output']).name}" if r.get("output") else ""
            print(f"  {r['route']:<7}{Path(r['file']).name}{out}")
        else:
            print(f"  FAIL  {Path(r['file']).name}  ({r['route']})")
            for line in (r.get("log") or "").strip().splitlines()[-2:]:
                print(f"        {line}")
    failed = sum(1 for r in results if not r["ok"] and r["route"] != "skip")
    skipped = sum(1 for r in results if r["route"] == "skip")
    print(f"\n{verb} {len(done)}/{len(results)}"
          + (f", {skipped} skipped" if skipped else "")
          + (f", {failed} failed" if failed else ""))
    if done and not args.dry_run:
        print("compile them into cards next: ask your agent for the wiki_compile skill")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
