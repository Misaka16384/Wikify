"""`magi thread` — open a proposition, post to one, move one along.

Plumbing, in the git sense: an agent runs these, a person almost never does.
They exist because the alternative is agents editing `threads/*.md` by hand,
and two of the guarantees the format makes cannot survive that.

* **A post is never lost.** Appending takes a lock (see `kb/threads.py`), and
  an editor writing the whole file does not take it.
* **A status flip carries its reason.** `thread status` writes both or
  neither. Hand-editing the frontmatter is how a note ends up with a status
  nobody explained, which is bookkeeping debt `next` then has to chase.

Every post is signed with a host name so the discussion reads as a
conversation rather than a log. `--host` sets it; otherwise `$MAGI_HOST`,
which `magi install --host` writes into the host's environment. The fallback
is `cli` — deliberately not a guess at which vendor's CLI is running, because
the environment variables that would tell us are undocumented and change.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ..core import vocab
from ..core.wiki_common import slugify
from ..core.workspace import find_workspace_root
from . import threads

DEFAULT_HOST = "cli"


def host_name(explicit: str | None = None) -> str:
    return explicit or os.environ.get("MAGI_HOST") or DEFAULT_HOST


class Refused(SystemExit):
    """Bad input, already phrased for the person or agent who typed it.

    A `SystemExit` because that is what the rest of the CLI raises for this —
    `cli.py` already knows how to print one without a traceback. `main` still
    catches it so the exit code is the ordinary 1 rather than a string status,
    but a caller reaching past `main` (an orchestrator, later) gets the
    behaviour it would get from any other command instead of a stack trace.
    """


def _root(args) -> Path:
    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        raise Refused("no workspace found (run inside a topic or pass --topic-dir)")
    return Path(root)


def _slug(value: str) -> str:
    """The slug, or a refusal naming the one it would have to be.

    A slug becomes a filename, so anything that is not already canonical is
    refused rather than quietly repaired: `../p-gap` would write outside
    `threads/`, an empty slug produces a hidden `.md` that the walker then
    skips, and `P Gap` and `p-gap` would be two notes about one claim.
    Canonical means `slugify` leaves it alone — the same rule the rest of the
    workspace uses for filenames.
    """
    canonical = slugify(value or "")
    if not canonical:
        raise Refused("a slug is the note's permanent id and cannot be empty")
    if canonical != value:
        raise Refused(f"{value!r} is not a usable slug — use {canonical!r}")
    return value


def _path(args, slug: str) -> Path:
    return _root(args) / threads.DIRNAME / f"{_slug(slug)}.md"


def _report(args, payload: dict, human: str) -> int:
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(human)
    return 0


def cmd_new(args) -> int:
    if not args.title.strip():
        raise Refused("a note needs a title — it is what every list of them shows")
    if not args.purpose.strip():
        raise Refused("a note needs a purpose — one line on why it is worth opening, "
                      "for whoever reads it in three months")
    path = _path(args, args.slug)
    extra = {}
    if args.bet:
        extra["bet"] = args.bet
    try:
        threads.create(path, args.kind, args.title, args.purpose,
                       lines=args.line, extra=extra or None)
    except FileExistsError:
        print(f"{path} already exists — a slug is an identity, pick another", file=sys.stderr)
        return 1

    note = threads.read_note(path)
    return _report(args, {"slug": args.slug, "path": str(path), "kind": note.kind,
                          "status": note.status, "tier": note.tier},
                   f"{args.kind} {args.slug} opened at {note.status} ({note.tier})")


def cmd_post(args) -> int:
    path = _path(args, args.slug)
    try:
        threads.append_post(path, args.text, host=host_name(args.host), line=args.line)
    except FileNotFoundError:
        print(f"no note at {path} — `magi thread new` opens one", file=sys.stderr)
        return 1
    return _report(args, {"slug": args.slug, "path": str(path), "posts":
                          len(threads.read_note(path).posts)},
                   f"posted to {args.slug}")


def _warn_if_closing_a_line(args, path) -> None:
    """Name what a line-closing flip through this command would silence.

    `magi close` surveys first because closing a line with three open
    propositions is a decision about those three propositions. This path
    reaches the same status without the survey, so the least it can do is say
    which notes stop being routed. Never raises: a warning that can break the
    command it is warning about is worse than no warning.
    """
    if args.to != "closed":
        return
    try:
        from .. import close_cmd

        if threads.read_note(path).kind != vocab.LINE:
            return
        found = close_cmd.survey(_root(args), args.slug)
    except Exception:  # noqa: BLE001
        return
    if not found["open"]:
        return
    names = ", ".join(item["slug"] for item in found["open"])
    print(f"warning: {len(found['open'])} note(s) on {args.slug} stop being "
          f"routed and nothing will mention them again: {names}", file=sys.stderr)
    print(f"         `magi close {args.slug}` shows this before it flips, and "
          f"signs the decision as a person's.", file=sys.stderr)


def cmd_status(args) -> int:
    path = _path(args, args.slug)

    # Closing a line through this command is allowed and lands as debt for
    # `sync --close` to report — that is the decided shape, and refusing here
    # would move `vocab`'s enforcement to the keystroke, which is the layer
    # design-v2 §10 keeps it out of: a `human` signature means the decision
    # belongs to a person, not that a person typed it.
    #
    # What is missing is the survey. `magi close` shows what would go quiet
    # before flipping, and after this flip nothing ever mentions those notes
    # again. So they are named here. A report, not a gate.
    _warn_if_closing_a_line(args, path)

    try:
        threads.set_status(path, args.to, args.text, host=host_name(args.host), line=args.line)
    except FileNotFoundError:
        print(f"no note at {path} — `magi thread new` opens one", file=sys.stderr)
        return 1
    except threads.IllegalTransition as exc:
        print(str(exc), file=sys.stderr)
        return 1

    note = threads.read_note(path)
    return _report(args, {"slug": args.slug, "path": str(path), "status": note.status,
                          "tier": note.tier},
                   f"{args.slug} → {note.status} ({note.tier})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magi thread",
        description="Propositions, questions and research lines")
    sub = parser.add_subparsers(dest="command", required=True)

    # Shared options go on each subcommand rather than in front of it: the CLI
    # dispatches `magi thread new ...` as `main(["new", ...])`, so anything
    # declared before the subparser can only be written in a position nobody
    # types.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    common.add_argument("--json", action="store_true", help="Machine-readable output")

    new = sub.add_parser("new", parents=[common],
                         help="Open a proposition, question or line")
    new.add_argument("slug", help="Stable id; becomes the filename and never changes")
    new.add_argument("--kind", required=True, choices=list(vocab.KINDS))
    new.add_argument("--title", required=True, help="The claim or question, in one line")
    new.add_argument("--purpose", required=True,
                     help="Why this is worth opening — one line, for whoever reads it later")
    new.add_argument("--line", action="append", default=[],
                     help="Research line this belongs to (repeatable)")
    new.add_argument("--bet", choices=list(vocab.BETS),
                     help="The prediction recorded before the work, if there is one")
    new.set_defaults(func=cmd_new)

    post = sub.add_parser("post", parents=[common],
                          help="Add a signed post to the discussion")
    post.add_argument("slug")
    post.add_argument("--text", required=True)
    post.add_argument("--line", help="Which line this post is written from")
    post.add_argument("--host", help="Signature (default: $MAGI_HOST, else 'cli')")
    post.set_defaults(func=cmd_post)

    status = sub.add_parser("status", parents=[common],
                            help="Move a note along, with the reason")
    status.add_argument("slug")
    status.add_argument("to", help="The status to move to")
    status.add_argument("--text", required=True, help="Why — this becomes the post")
    status.add_argument("--line")
    status.add_argument("--host")
    status.set_defaults(func=cmd_status)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Refused as refusal:
        print(str(refusal), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
