"""`magi thread` — open a proposition, post to one, move one along, bet on one.

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


def via_name(host: str, explicit: str | None = None) -> str | None:
    """Who typed a post signed `human` — the CLI that transcribed it.

    A post signed `human` is the person's decision, and design-v2 §10 has the
    agent transcribe it. The record could not tell that transcription from a
    person's own keystrokes (2026-09-03), which overstates what it knows. So a
    `human` signature carries `via <cli>`: `--via` when given, else the host
    the environment names, else `cli`. Posts signed by an agent need none —
    the signature already says who wrote them.
    """
    if explicit:
        return explicit
    if host != vocab.HUMAN:
        return None
    return os.environ.get("MAGI_HOST") or DEFAULT_HOST


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
        raise Refused("no project found (run inside one, or pass --project-dir)")
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


def _in_library(root: Path, value: str, what: str) -> str:
    """A path to evidence, as the note will carry it: inside the project, and real.

    Fifteen verification scripts were written in a CLI's scratch directory in
    one day and cited from posts as `scratchpad b8_haah.m2`; the reviewer,
    reading inside the workspace, could open none of them. Evidence a reviewer
    cannot read is not evidence, so the path is checked at the moment it is
    written down rather than discovered at review time. Stored relative, in
    POSIX form, so the note reads the same on every machine.
    """
    raw = str(value or "").strip()
    if not raw:
        raise Refused(f"--{what} needs a path")
    candidate = Path(raw)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError:
        raise Refused(f"{raw} is outside the project ({root}). A reviewer can only "
                      "read what is inside it — move the file under tools/ or "
                      "drafts/ and cite that path.")
    if not resolved.exists():
        raise Refused(f"{raw} is not a file in the project; evidence is something a "
                      "reviewer can open")
    return relative.as_posix()


def _derivation_ref(root: Path, value: str) -> str:
    """A `derivation:` entry: a `[[wikilink]]` as written, or a checked path."""
    raw = str(value or "").strip()
    if raw.startswith("[[") and raw.endswith("]]"):
        return raw
    return _in_library(root, raw, "derivation")


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
    if getattr(args, "found", None) is not None:
        if args.kind != vocab.PROPOSITION:
            raise Refused("--found is for a proposition: it says the result came "
                          "before the note, and only a claim has a result to come")
        extra["found"] = _found_date(args.found)
    for flag in ("claim", "derivation", "evidence"):
        if getattr(args, flag, None) and args.kind != vocab.PROPOSITION:
            raise Refused(f"--{flag} is for a proposition: only a claim is reviewed")
    if getattr(args, "claim", None):
        extra["claim"] = " ".join(args.claim.split())
    root = _root(args)
    if getattr(args, "derivation", None):
        extra["derivation"] = [_derivation_ref(root, item) for item in args.derivation]
    if getattr(args, "evidence", None):
        extra["evidence"] = [_in_library(root, item, "evidence") for item in args.evidence]
    try:
        threads.create(path, args.kind, args.title, args.purpose,
                       lines=args.line, extra=extra or None)
    except FileExistsError:
        print(f"{path} already exists — a slug is an identity, pick another", file=sys.stderr)
        return 1

    note = threads.read_note(path)
    found = extra.get("found")
    return _report(args, {"slug": args.slug, "path": str(path), "kind": note.kind,
                          "status": note.status, "tier": note.tier, "found": found},
                   f"{args.kind} {args.slug} opened at {note.status} ({note.tier})"
                   + (f", found {found} — no prediction is asked for" if found else ""))


def _found_date(value: str) -> str:
    """`--found` as an ISO date. Bare `--found` is today.

    A finding is a proposition whose result came before the note (design-v2
    §4): the derivation was done, the number came out, and only then did
    somebody open a proposition about it. Asking for a bet on it produces a
    prediction placed after the answer, which is worth nothing and which a
    day of real work asked for five times. The date is what is recorded
    instead, because "when was this found" is the question a reader of the
    note has and "what did you expect" is one nobody can honestly answer.
    """
    import datetime as dt

    if value in ("", "today"):
        return dt.date.today().isoformat()
    try:
        return dt.date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        raise Refused(f"--found takes a date as YYYY-MM-DD (or nothing, for today), "
                      f"not {value!r}")


def cmd_bet(args) -> int:
    """Record the person's prediction on a proposition, as a post and a field.

    `bet:` was settable at `thread new` and through `magi decide --bet`, and
    nowhere else — so a prediction made after the note existed was written by
    hand-editing frontmatter, which is the one thing this command family
    exists to make unnecessary. Signed `human` unless told otherwise: a bet is
    the person's prediction, and the agent transcribes it.
    """
    path = _path(args, args.slug)
    try:
        note = threads.read_note(path)
    except FileNotFoundError:
        print(f"no note at {path} — `magi thread new` opens one", file=sys.stderr)
        return 1
    if note.kind != vocab.PROPOSITION:
        raise Refused(f"a bet is about a proposition; {args.slug} is a {note.kind}. "
                      "A prediction is about a claim that can turn out to be wrong.")
    host = args.host or vocab.HUMAN
    try:
        threads.set_field(path, "bet", args.value, host=host, text=args.text or "",
                          line=args.line, via=via_name(host, getattr(args, "via", None)))
    except (ValueError, OSError) as exc:
        print(f"{path.name} did not take the bet: {exc}", file=sys.stderr)
        return 1
    return _report(args, {"slug": args.slug, "path": str(path), "bet": args.value,
                          "host": host},
                   f"{args.slug}: bet {args.value} (signed {host})")


def cmd_found(args) -> int:
    """Mark an existing proposition as a finding: the result came before the note.

    `thread new --found` only covers a note being opened, and the propositions
    that most need this are the ones already sitting there being asked for a
    prediction they can no longer honestly give — which is exactly the case
    that produced this command (2026-09-03: ten of them, and the only way to
    fix one was to hand-edit its frontmatter).
    """
    path = _path(args, args.slug)
    try:
        note = threads.read_note(path)
    except FileNotFoundError:
        print(f"no note at {path} — `magi thread new` opens one", file=sys.stderr)
        return 1
    if note.kind != vocab.PROPOSITION:
        raise Refused(f"--found is a proposition's: it says the result came before "
                      f"the note, and {args.slug} is a {note.kind}")
    when = _found_date(args.date if args.date is not None else "today")
    host = host_name(args.host)
    threads.set_field(path, "found", when, host=host, text=args.text or "",
                      line=args.line, via=via_name(host, getattr(args, "via", None)))
    said = f"{args.slug}: found {when} — no prediction is asked for on it"
    if note.frontmatter.get("bet"):
        said += (f"\n  its `bet: {note.frontmatter['bet']}` is left as it is; a "
                 "prediction on record stays on record, and the scoreboard reads "
                 "it the same way")
    return _report(args, {"slug": args.slug, "path": str(path), "found": when,
                          "bet": note.frontmatter.get("bet")}, said)


def _warn_if_a_persons_call(args, path, host: str) -> None:
    """Say, at the keystroke, that this flip needs a person's signature.

    Not a refusal. design-v2 §6 keeps `vocab`'s enforcement in `sync --close`,
    where the decision can be shown to be on record, rather than here, where
    only the typist is known. But the close gate's message arrives after the
    fact, and an agent that read it as "try again" made the debt worse with
    every retry — each unsigned flip out of `disputed` is a separate decision
    owed. So the one thing worth saying is said here, before the retry: sign
    it, or transcribe it, and do not move it again. Never raises.
    """
    if host == vocab.HUMAN:
        return
    try:
        note = threads.read_note(path)
    except Exception:  # noqa: BLE001
        return
    if note.status == args.to or not vocab.is_human_only(note.kind, note.status, args.to):
        return
    print(f"note: {note.status} → {args.to} is a person's call, and this post is signed "
          f"`{host}`.", file=sys.stderr)
    print(f"      `magi sync --close` will hold the session until the decision is on "
          f"record. Either sign it now —", file=sys.stderr)
    print(f"        magi thread status {args.slug} {args.to} --host human "
          f"--text '<what they said>'", file=sys.stderr)
    print(f"      — or transcribe it: `magi decide --about {args.slug} --text "
          f"'<what they said>'`.", file=sys.stderr)
    print("      Do not repeat this move. A second unsigned flip is a second decision "
          "owed, not a fix for the first.", file=sys.stderr)


def cmd_post(args) -> int:
    path = _path(args, args.slug)
    host = host_name(args.host)
    via = via_name(host, getattr(args, "via", None))
    evidence = getattr(args, "evidence", None) or []
    if not (args.text or "").strip() and not evidence:
        raise Refused("a post says something: --text, or --evidence <path> to add a "
                      "file a reviewer must read")
    try:
        if evidence:
            # The list grows; it never shrinks from here. Recorded as a field
            # change so the post says what was added and by whom, the way a
            # `bet:` is — a path that appears in the frontmatter with no event
            # behind it cannot be told from one somebody typed by hand.
            note = threads.read_note(path)
            if note.kind != vocab.PROPOSITION:
                raise Refused(f"--evidence is for a proposition; {args.slug} is a {note.kind}")
            root = _root(args)
            merged = list(dict.fromkeys(
                [str(item) for item in threads.as_list(note.frontmatter.get("evidence"))]
                + [_in_library(root, item, "evidence") for item in evidence]))
            threads.set_field(path, "evidence", merged, host=host, text=args.text or "",
                              line=args.line, via=via)
        else:
            threads.append_post(path, args.text, host=host, line=args.line, via=via)
    except FileNotFoundError:
        print(f"no note at {path} — `magi thread new` opens one", file=sys.stderr)
        return 1
    return _report(args, {"slug": args.slug, "path": str(path), "posts":
                          len(threads.read_note(path).posts),
                          "evidence": list(threads.as_list(
                              threads.read_note(path).frontmatter.get("evidence")))},
                   f"posted to {args.slug}"
                   + (f" ({len(evidence)} evidence path(s) recorded)" if evidence else ""))


def cmd_claim(args) -> int:
    """Restate the claim through the CLI, so the change is a post.

    The claim is the statement a reviewer judges, and a `restate` verdict asks
    the author to change it. Editing the frontmatter by hand leaves a claim
    that changed with nobody saying so; this records the new wording as a
    field change, the way a bet is.
    """
    path = _path(args, args.slug)
    text = " ".join((args.text or "").split())
    if not text:
        raise Refused("--text is the statement itself, with its quantifiers")
    host = host_name(args.host)
    try:
        note = threads.read_note(path)
    except FileNotFoundError:
        print(f"no note at {path} — `magi thread new` opens one", file=sys.stderr)
        return 1
    if note.kind != vocab.PROPOSITION:
        raise Refused(f"a claim is a proposition's; {args.slug} is a {note.kind}")
    threads.set_field(path, "claim", text, host=host, text=args.why or "",
                      line=args.line, via=via_name(host, getattr(args, "via", None)))
    return _report(args, {"slug": args.slug, "path": str(path), "claim": text},
                   f"{args.slug}: claim restated")


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
    host = host_name(args.host)
    _warn_if_a_persons_call(args, path, host)

    try:
        threads.set_status(path, args.to, args.text, host=host, line=args.line,
                           via=via_name(host, getattr(args, "via", None)))
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
    common.add_argument("--project-dir", "--topic-dir", dest="topic_dir", help="Project directory (default: discovered from cwd)")
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
    new.add_argument("--found", nargs="?", const="today", metavar="DATE",
                     help="This result came before the note (a finding, not a "
                          "conjecture): record when, YYYY-MM-DD, default today. "
                          "No prediction is asked for on it.")
    new.add_argument("--claim",
                     help="The precise statement under review, quantifiers included. "
                          "The title stays a short name; the reviewer reads this.")
    new.add_argument("--derivation", action="append", default=[], metavar="PATH",
                     help="Where the argument lives: a [[drafts/...]] link or a path in "
                          "the project (repeatable)")
    new.add_argument("--evidence", action="append", default=[], metavar="PATH",
                     help="A file in the project a reviewer must read or run: a script, "
                          "data, a notebook (repeatable). Must exist, must be inside "
                          "the project — tools/ is the place for scripts.")
    new.set_defaults(func=cmd_new)

    via_help = ("Who typed this, when signing for a person (default: $MAGI_HOST, "
                "else 'cli'); written into the signature as `via <cli>`")

    bet = sub.add_parser("bet", parents=[common],
                         help="Record the person's prediction on a proposition")
    bet.add_argument("slug")
    bet.add_argument("value", choices=list(vocab.BETS),
                     help="What they expect; `unknown` is a real answer")
    bet.add_argument("--text", help="Their words, if they said why")
    bet.add_argument("--line", help="Which line this is written from")
    bet.add_argument("--host", help="Signature (default: human — a bet is the person's "
                                    "prediction, transcribed)")
    bet.add_argument("--via", help=via_help)
    bet.set_defaults(func=cmd_bet)

    found = sub.add_parser("found", parents=[common],
                           help="Mark an existing proposition as a finding (the result "
                                "came before the note); no prediction is asked for")
    found.add_argument("slug")
    found.add_argument("date", nargs="?", metavar="DATE",
                       help="When it was found, YYYY-MM-DD (default: today)")
    found.add_argument("--text", help="What was found, if worth saying")
    found.add_argument("--line")
    found.add_argument("--host", help="Signature (default: $MAGI_HOST, else 'cli')")
    found.add_argument("--via", help=via_help)
    found.set_defaults(func=cmd_found)

    claim = sub.add_parser("claim", parents=[common],
                           help="Restate a proposition's claim, as a recorded change")
    claim.add_argument("slug")
    claim.add_argument("--text", required=True,
                       help="The statement itself, quantifiers included")
    claim.add_argument("--why", help="What changed and why, if worth saying")
    claim.add_argument("--line")
    claim.add_argument("--host", help="Signature (default: $MAGI_HOST, else 'cli')")
    claim.add_argument("--via", help=via_help)
    claim.set_defaults(func=cmd_claim)

    post = sub.add_parser("post", parents=[common],
                          help="Add a signed post to the discussion")
    post.add_argument("slug")
    post.add_argument("--text", help="What happened (required unless --evidence)")
    post.add_argument("--evidence", action="append", default=[], metavar="PATH",
                      help="Add a file in the project a reviewer must read or run "
                           "(repeatable); recorded as a field change on the note")
    post.add_argument("--line", help="Which line this post is written from")
    post.add_argument("--host", help="Signature (default: $MAGI_HOST, else 'cli')")
    post.add_argument("--via", help=via_help)
    post.set_defaults(func=cmd_post)

    status = sub.add_parser("status", parents=[common],
                            help="Move a note along, with the reason")
    status.add_argument("slug")
    status.add_argument("to", help="The status to move to")
    status.add_argument("--text", required=True, help="Why — this becomes the post")
    status.add_argument("--line")
    status.add_argument("--host")
    status.add_argument("--via", help=via_help)
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
