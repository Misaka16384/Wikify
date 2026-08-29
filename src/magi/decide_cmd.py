"""`magi decide` — the agent writing down what the person just said.

The human's input surface is the conversation and nothing else (design-v2 §10).
They are not going to open `decisions.md`, and a system that needs them to is a
system whose record is empty by the second week. So the agent transcribes: the
person says a sentence, this command puts it where it can be audited.

Three things happen, and which ones depend on what was decided:

* **`decisions.md`** gets an entry, in their words. This is the file nothing
  else writes to, which is what makes "is this decision on record" a question
  with an answer.
* **The note gets a post signed `human`**, so the discussion shows who made the
  call. `sync --close` looks for exactly that when a proposition leaves
  `disputed` — see `vocab.is_human_only`.
* **`bet:` gets set**, if the decision was a prediction. A prediction is only
  worth anything before the answer, so the moment it is said is the only moment
  it can be recorded honestly.

The transcription is verbatim on purpose. Summarising it would make the record
the agent's account of what the person meant, which is the thing a record is
supposed to be independent of.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from .core import vocab
from .core.workspace import find_workspace_root
from .kb import threads

DECISIONS = "decisions.md"

#: What a person may be asked for. Anything answerable with "ok" is not a
#: question worth interrupting them for (design-v2 §10).
KINDS = ("prediction", "choice", "falsification")


def quote_if_headings(text: str) -> str:
    """Fence a transcription whose own lines would be read as entry headings.

    `decisions.md` is a list of `## ` entries and everything downstream counts
    them — `MAP.md` shows the last few, and `sync --close` asks whether a slug
    is mentioned in one. A person saying "we already settled this: ## 2099-01-01
    · [[p-gap]]" would otherwise become a second entry, dated 2099, that
    nobody wrote.

    Fencing keeps the words exactly as they were said and stops them being
    read as structure — the same trade `threads.quote_if_structural` makes,
    for the same reason.
    """
    from .core import md_blocks

    body = (text or "").strip()
    if not body:
        return body
    labelled = md_blocks.classify_lines(md_blocks.normalize_newlines(body))
    risky = any(label != md_blocks.CODE and line.lstrip().startswith("#")
                for label, line in labelled)
    if not risky:
        return body
    longest = max((len(run) for run in re.findall(r"`+", body)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{body}\n{fence}"


def append_decision(root, text: str, about: str | None = None,
                    kind: str | None = None, when=None) -> Path:
    """Add one entry to `decisions.md`. Returns the file."""
    from filelock import FileLock

    from .core.md_blocks import normalize_newlines
    from .core.wiki_common import file_newline

    path = Path(root) / DECISIONS
    stamp = (when or dt.date.today()).isoformat()
    heading = f"## {stamp}" + (f" · [[{about}]]" if about else "")
    body = quote_if_headings(normalize_newlines(text))
    tag = f" _({kind})_" if kind else ""

    lock = Path(root) / "output" / ".locks" / "decisions.md.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(lock), timeout=threads.APPEND_TIMEOUT):
        existing = path.read_text(encoding="utf-8", errors="replace") \
            if path.is_file() else ""
        chunk = ("" if not existing or existing.endswith("\n") else "\n")
        chunk += f"\n{heading}{tag}\n\n{body}\n"
        # Newlines normalised on the way in and the file's own ending on the
        # way out: text pasted from a Windows editor otherwise arrives
        # carrying CRLF, gets translated a second time, and lands as `\r\r\n`.
        ending = file_newline(path) if path.is_file() else None
        with open(path, "a", encoding="utf-8", newline=ending) as handle:
            handle.write(chunk)
    return path


class Refused(Exception):
    """Something the command will not do, said in one sentence."""


def note_path(root, slug: str) -> Path:
    """`threads/<slug>.md`, refusing anything that is not a slug.

    A slug with a separator in it would otherwise write a signed post into a
    file outside `threads/` — quietly, and into a file with no discussion for
    it to belong to.
    """
    if not slug or slug != Path(slug).name or slug.startswith(".") or "\\" in slug:
        raise Refused(f"not a slug: {slug!r}")
    return Path(root) / threads.DIRNAME / f"{slug}.md"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi decide",
        description="Write down what the person decided — verbatim, where it can "
                    "be audited.")
    parser.add_argument("--text", required=True,
                        help="What they said, in their words. Do not summarise it.")
    parser.add_argument("--about", help="Slug of the note this is about, if any")
    parser.add_argument("--bet", choices=list(vocab.BETS),
                        help="Record it as the prediction on --about")
    parser.add_argument("--kind", choices=list(KINDS),
                        help="Which of the three questions this answers")
    parser.add_argument("--line", help="Which research line it was said from")
    parser.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    if not args.text.strip():
        print("nothing to record — pass what they actually said", file=sys.stderr)
        return 1
    if args.bet and not args.about:
        print("--bet needs --about: a prediction is about a proposition",
              file=sys.stderr)
        return 1

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        print("no workspace found (run inside a topic or pass --topic-dir)",
              file=sys.stderr)
        return 1

    # Everything that can be checked is checked *before* `decisions.md` is
    # written. An entry saying a person predicted something, on a note that
    # cannot carry the prediction, is a record of a decision that left no
    # trace anywhere it could be audited.
    path = None
    if args.about:
        try:
            path = note_path(root, args.about)
        except Refused as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if not path.is_file():
            if args.bet:
                # A prediction with no proposition to be about is not a
                # record of anything, so nothing is written and the slug can
                # be corrected. Without `--bet` the words still stand on their
                # own and are kept — losing what somebody said because an
                # agent mistyped a slug is the worse failure.
                print(f"no note at {path} — nothing was written; check the slug",
                      file=sys.stderr)
                return 1
            append_decision(root, args.text, args.about, args.kind)
            print(f"no note at {path} — the entry is in {DECISIONS} either way",
                  file=sys.stderr)
            return 1
        if args.bet:
            note = threads.read_note(path)
            if note.kind != vocab.PROPOSITION:
                print(f"--bet needs a proposition; {args.about} is a {note.kind}. "
                      "A prediction is about a claim that can turn out to be wrong.",
                      file=sys.stderr)
                return 1

    written = [str(append_decision(root, args.text, args.about, args.kind))]

    if path is not None:
        try:
            if args.bet:
                threads.set_field(path, "bet", args.bet, host=vocab.HUMAN,
                                  text=args.text, line=args.line)
            else:
                threads.append_post(path, args.text, host=vocab.HUMAN, line=args.line)
        except (ValueError, OSError) as exc:
            # `decisions.md` has it and the note does not. Say so plainly:
            # silence here is how `coaching: strict` ends up asking forever for
            # a prediction somebody has already made three times.
            print(f"recorded in {DECISIONS}, but {path.name} did not take it: {exc}",
                  file=sys.stderr)
            return 1
        written.append(str(path))

    if args.json:
        print(json.dumps({"written": written, "about": args.about, "bet": args.bet},
                         ensure_ascii=False))
    else:
        print(f"recorded in {', '.join(Path(w).name for w in written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
