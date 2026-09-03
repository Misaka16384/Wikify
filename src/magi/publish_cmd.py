"""`magi publish <paper> --line <line>` — the work is written up; file it.

The end of a research line, when it ends well: the paper goes into `raw/` and
becomes cold layer like any other source, every proposition the line was about
gets `superseded_by:` pointing at it, and the line closes. From then on the
paper is the answer and the propositions are the working-out that led to it.

**`superseded` is terminal.** `vocab` gives it no transitions out, which is
what makes this command worth having a survey in front of it. Two things it
will not bury without being told twice:

* a `disputed` proposition — a reviewer objected and nobody ruled, and
  publishing over it makes the objection disappear rather than answering it;
* work still `open` — the paper claims to be the end of a line that has not
  finished.

Both are legitimate: papers do ship with loose ends. What is not legitimate is
shipping them silently, so `--anyway` writes each one into the closing record.

**Only a person calls this** (design-v2 §6). Like `magi close`, an agent may
type it; the posts are signed as a person's decision because that is whose
decision it is.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import close_cmd
from .core import vocab
from .core.workspace import find_workspace_root
from .kb import threads
from .kb.thread_cmd import via_name

#: Where a published paper lands. The same shelf as everything else we read:
#: our own result is cold layer on the day it exists, not a special category.
DEST = ("raw", "papers")

#: Statuses that mean somebody is still owed something. Kept apart from
#: `disputed`, which is a different objection with a different answer.
UNFINISHED = frozenset({"open", "conjectured", "testing"})


def members(root, lines) -> list:
    """Every proposition and question on any of these lines, in slug order."""
    wanted = set(lines)
    out = []
    # Recursive, for the reason `close_cmd.survey` is: a note this misses is
    # one that keeps its old status on a line that just closed, so nothing
    # routes it and nothing says the paper superseded it.
    for path in threads.note_paths(root):
        try:
            note = threads.read_note(path)
        except (OSError, ValueError):
            continue
        if note.kind == vocab.LINE or not (wanted & set(note.lines or [])):
            continue
        out.append(note)
    return out


def survey(root, paper: Path, lines) -> dict:
    """What publishing would do, before it does any of it."""
    found = {
        "paper": str(paper), "lines": list(lines), "missing_lines": [],
        "supersede": [], "disputed": [], "unfinished": [], "already": 0,
        "dest": str(Path(root).joinpath(*DEST) / Path(paper).name),
        "readable": Path(paper).suffix.lower() in (".md", ".markdown"),
    }
    directory = Path(root) / "threads"
    for line in lines:
        header = directory / f"{line}.md"
        if not header.is_file():
            found["missing_lines"].append(line)
            continue
        try:
            if threads.read_note(header).kind != vocab.LINE:
                found["missing_lines"].append(line)
        except (OSError, ValueError):
            found["missing_lines"].append(line)

    for note in members(root, lines):
        if note.status == "superseded":
            found["already"] += 1
            continue
        found["supersede"].append({"slug": note.slug, "kind": note.kind,
                                   "status": note.status})
        if note.status == "disputed":
            found["disputed"].append(note.slug)
        elif note.status in UNFINISHED:
            found["unfinished"].append(note.slug)
    return found


def _candidates(paper: Path):
    """Names to try for a paper, in order, until one is free or is itself.

    Endless on purpose: the caller stops at the first name that is either
    unused or already holds this exact file, and a bounded list would have to
    decide what to do when it ran out. Overwriting is the one answer `raw/`
    does not allow.
    """
    yield paper.name
    yield f"{paper.stem}--published{paper.suffix}"
    nth = 2
    while True:
        yield f"{paper.stem}--published-{nth}{paper.suffix}"
        nth += 1


def file_paper(root, paper: Path) -> Path:
    """Copy the paper onto the cold shelf. Returns where it landed.

    `raw/` is ORIGINAL — nothing regenerates what is already in the library —
    so a name already taken by *different* content is kept rather than
    overwritten, the same rule the ingest commit follows. Publishing the same
    file twice still lands on itself.
    """
    dest_dir = Path(root).joinpath(*DEST)
    dest_dir.mkdir(parents=True, exist_ok=True)
    body = paper.read_bytes()

    # Every candidate is tested, not just the first. Guarding one collision
    # and then trusting `--published` meant the third paper of that name
    # silently overwrote the second: the fallback was computed but never
    # re-checked, on the one directory this module's docstring calls the
    # immutable cold shelf.
    for name in _candidates(paper):
        dest = dest_dir / name
        if not dest.is_file() or dest.read_bytes() == body:
            break
    shutil.copy2(paper, dest)
    return dest


def publish(root, paper, lines, text: str, anyway: bool = False,
            host: str = vocab.HUMAN, via: str | None = None) -> dict:
    """File the paper, supersede the line's work, close the line.

    `via` is who typed it for the person — see `close_cmd.close`.
    """
    root = Path(root)
    paper = Path(paper)
    if not paper.is_file():
        return {"ok": False, "error": f"no such file: {paper}"}

    found = survey(root, paper, lines)
    if found["missing_lines"]:
        return dict(found, ok=False,
                    error="no line note for: " + ", ".join(found["missing_lines"]))
    if not anyway and (found["disputed"] or found["unfinished"]):
        return dict(found, ok=False, error="work is not finished")

    landed = file_paper(root, paper)
    link = "[[" + landed.relative_to(root).as_posix() + "]]"

    said = text.strip()
    if found["disputed"]:
        said += ("\n\nPublished over an unresolved objection: "
                 + ", ".join(found["disputed"]))
    if found["unfinished"]:
        said += "\n\nPublished with these unfinished: " + ", ".join(found["unfinished"])

    superseded, refused = [], []
    for item in found["supersede"]:
        path = root / "threads" / f"{item['slug']}.md"
        try:
            # The field first, then the status. A crash between them leaves a
            # note that points at the paper and has not been retired, which a
            # person can finish; the other order leaves a terminal `superseded`
            # with nothing saying what replaced it, and `superseded` has no way
            # back out.
            if item["kind"] == vocab.PROPOSITION:
                threads.set_field(path, "superseded_by", link, host=host,
                                  text=f"published as {link}", via=via)
            threads.set_status(path, "superseded" if item["kind"] == vocab.PROPOSITION
                               else "answered", said, host=host, via=via)
            superseded.append(item["slug"])
        except (threads.IllegalTransition, OSError, ValueError) as exc:
            refused.append({"slug": item["slug"], "why": str(exc)})

    closed = []
    for line in lines:
        result = close_cmd.close(root, line, said, anyway=True, host=host, via=via)
        if result.get("ok"):
            closed.append(line)
        else:
            refused.append({"slug": line, "why": result.get("error", "")})

    return dict(found, ok=not refused, error="", paper_at=str(landed),
                link=link, superseded=superseded, closed=closed, refused=refused)


def render(result: dict) -> str:
    out = []
    if not result.get("ok") and not result.get("paper_at"):
        out.append(f"not published: {result.get('error')}")
        for slug in result.get("disputed") or []:
            out.append(f"  {slug}: a reviewer objected and nobody has ruled — "
                       f"publishing over it makes the objection vanish")
        for slug in result.get("unfinished") or []:
            out.append(f"  {slug}: still unfinished")
        if result.get("disputed") or result.get("unfinished"):
            out.append("")
            out.append("Settle them, or publish anyway and the record will say "
                       "which ones were buried:")
            out.append("  magi publish <paper> --line <line> --anyway --text '<why>'")
        return "\n".join(out)

    out.append(f"filed {result['paper_at']}")
    if not result.get("readable", True):
        out.append("  note: not markdown — the cold layer holds the file, but "
                   "`magi search` and the graph cannot read it. `magi ingest add` "
                   "converts one first.")
    if result.get("superseded"):
        out.append(f"  superseded {len(result['superseded'])}: "
                   + ", ".join(result["superseded"]))
    if result.get("already"):
        out.append(f"  {result['already']} already superseded")
    if result.get("closed"):
        out.append(f"  closed: {', '.join(result['closed'])}")
    for item in result.get("refused") or []:
        out.append(f"  ! {item['slug']}: {item['why']}")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi publish",
        description="File our own paper into raw/, retire the work it reports, "
                    "and close the line.")
    parser.add_argument("paper", help="The paper, as a file on disk")
    parser.add_argument("--line", action="append", default=[],
                        help="Research line this paper reports (repeatable)")
    parser.add_argument("--text", help="What this paper is — this is the record")
    parser.add_argument("--anyway", action="store_true",
                        help="Publish over unresolved or unfinished work; the "
                             "record names it")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be superseded, and stop")
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir", help="Project directory (default: discovered from cwd)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        print("no project found (run inside one, or pass --project-dir)",
              file=sys.stderr)
        return 1
    if not args.line:
        print("which line does this paper report? "
              "magi publish <paper> --line <line>", file=sys.stderr)
        return 1

    if args.dry_run:
        found = survey(root, Path(args.paper), args.line)
        if args.json:
            print(json.dumps(found, ensure_ascii=False, indent=2))
        else:
            print(f"would file {found['dest']}")
            print(f"would supersede {len(found['supersede'])}, "
                  f"close {', '.join(args.line)}")
            for item in found["supersede"]:
                print(f"  {item['slug']} ({item['status']})")
        return 0

    if not (args.text or "").strip():
        print("say what this paper is: magi publish <paper> --line <line> "
              "--text '<what it reports>'", file=sys.stderr)
        return 1

    result = publish(root, args.paper, args.line, args.text, anyway=args.anyway,
                     via=via_name(vocab.HUMAN))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
