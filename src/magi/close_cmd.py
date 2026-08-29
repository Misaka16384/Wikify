"""`magi close <line>` — the one command that ends a research line.

A line is a *view* over the project, not a folder, so closing one moves no
files and deletes nothing. What it changes is attention: `magi next` skips a
closed line entirely, which is the point of closing it and also the whole
danger. Every proposition still open on that line stops being offered — not
archived, not answered, just never mentioned again.

So this command's real job is not the status flip, which `magi thread status`
could do. It is the survey it runs first. Closing a line with three open
propositions is a decision about those three propositions, and a person who
has not been shown them has not made it.

**Why it is a command and not a flag.** design-v2 §6: closing a line is one of
the things only a person calls, and `vocab` enforces it — `line → closed` is a
human-only target, so the post carries the `human` signature that `sync --close`
looks for. An agent may type the command, the way `magi decide` is typed by an
agent; what it may not do is decide.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import vocab
from .core.workspace import find_workspace_root
from .kb import threads

#: Statuses that mean "still somebody's problem". Same set `state` ranks work
#: by, and the reason a closed line's members would go quiet.
OPEN = frozenset({"open", "conjectured", "testing"})


def survey(root, line: str) -> dict:
    """What closing this line would leave behind.

    Questions count alongside propositions: an unanswered question on a closed
    line is exactly as forgotten as an untested claim, and the whole reason to
    look before closing is that neither of them raises its hand afterwards.
    """
    out = {"line": line, "open": [], "settled": 0, "status": None, "exists": False}
    directory = Path(root) / "threads"
    header = directory / f"{line}.md"
    if header.is_file():
        note = threads.read_note(header)
        out["exists"] = note.kind == vocab.LINE
        out["status"] = note.status

    # `threads.note_paths`, not a flat glob: it is what `state` walks to build
    # the projection, so a workspace that files notes as `threads/qec/p-1.md`
    # has them counted by `magi next` and — before this — invisible to the one
    # survey that exists to show a person what closing the line would silence.
    # It also skips `_index.md` and dotfiles, which the flat glob handed to
    # `read_note` to fail on.
    for path in threads.note_paths(root):
        if path == header:
            continue
        try:
            note = threads.read_note(path)
        except (OSError, ValueError):
            continue
        if line not in (note.lines or []):
            continue
        if note.status in OPEN:
            out["open"].append({"slug": note.slug, "kind": note.kind,
                                "status": note.status})
        else:
            out["settled"] += 1
    return out


def _settle_line(item: dict) -> str:
    """The command that would deal with one leftover, by kind."""
    if item["kind"] == vocab.QUESTION:
        return (f"magi thread status {item['slug']} <answered|abandoned> "
                f"--text '<what came of it>'")
    return (f"magi thread status {item['slug']} <supported|refuted|superseded> "
            f"--text '<what came of it>'")


def close(root, line: str, text: str, anyway: bool = False,
          host: str = vocab.HUMAN) -> dict:
    """Close one line. Returns what happened; raises nothing a caller expects.

    With work still open and `anyway` unset, nothing is written and the report
    says what is in the way. With `anyway`, the post names every slug that was
    left open — the record has to say what was orphaned, because after this the
    router never will.
    """
    found = survey(root, line)
    if not found["exists"]:
        return dict(found, ok=False,
                    error=f"no line note at threads/{line}.md "
                          f"(`magi thread new {line} --kind line …` opens one)")
    if found["status"] == "closed":
        return dict(found, ok=True, changed=False,
                    error="", note=f"{line} is already closed")
    if found["open"] and not anyway:
        return dict(found, ok=False,
                    error=f"{len(found['open'])} still open on {line}")

    said = text.strip()
    if found["open"]:
        said += ("\n\nLeft open at close, and no longer offered by `magi next`: "
                 + ", ".join(item["slug"] for item in found["open"]))
    try:
        threads.set_status(Path(root) / "threads" / f"{line}.md", "closed",
                           said, host=host, line=line)
    except (threads.IllegalTransition, OSError, ValueError) as exc:
        return dict(found, ok=False, error=str(exc))
    return dict(found, ok=True, changed=True, error="", note=f"{line} → closed")


def render(result: dict) -> str:
    lines = []
    if not result.get("ok"):
        lines.append(f"not closed: {result.get('error')}")
        for item in result.get("open") or []:
            lines.append(f"  {item['slug']} ({item['status']})")
            lines.append(f"      {_settle_line(item)}")
        if result.get("open"):
            lines.append("")
            lines.append("Settle them, or close anyway and the post will record "
                         "which ones were left:")
            lines.append(f"  magi close {result['line']} --anyway --text '<why>'")
        return "\n".join(lines)

    lines.append(result.get("note") or f"{result['line']} → closed")
    if result.get("open"):
        lines.append(f"  left open: "
                     + ", ".join(item["slug"] for item in result["open"]))
        lines.append("  `magi next` will not offer them again; the closing post "
                     "says so.")
    if result.get("settled"):
        lines.append(f"  {result['settled']} settled note(s) stay where they are — "
                     f"closing a line moves no files.")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi close",
        description="Close a research line. Shows what is still open first.")
    parser.add_argument("line", help="Slug of the line note")
    parser.add_argument("--text", help="Why it is closing — this is the record")
    parser.add_argument("--anyway", action="store_true",
                        help="Close even with work still open; the post names it")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what closing would leave behind, and stop")
    parser.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        print("no workspace found (run inside a topic or pass --topic-dir)",
              file=sys.stderr)
        return 1

    if args.dry_run:
        found = survey(root, args.line)
        if args.json:
            print(json.dumps(found, ensure_ascii=False, indent=2))
        elif not found["exists"]:
            print(f"no line note at threads/{args.line}.md", file=sys.stderr)
            return 1
        else:
            print(f"{args.line} is {found['status']}; closing would leave "
                  f"{len(found['open'])} open and {found['settled']} settled")
            for item in found["open"]:
                print(f"  {item['slug']} ({item['status']})")
        return 0

    # Required here rather than in argparse so `--dry-run` can survey without
    # somebody having to invent a reason for a close they may not go through
    # with. A close that does happen always carries one: "closed" with nothing
    # said is a line nobody can reopen on purpose.
    if not (args.text or "").strip():
        print("say why: magi close <line> --text '<why>'", file=sys.stderr)
        return 1

    result = close(root, args.line, args.text, anyway=args.anyway)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
