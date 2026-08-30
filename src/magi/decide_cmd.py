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
    # A fence the quotation opens and never closes belongs to the whole file
    # once it is pasted in: every later entry renders inside it. That text
    # looks safe by the test above — everything after the fence is `CODE`, so
    # no heading is ever "at risk" — which made the one body that most needed
    # fencing the one body that did not get it.
    risky = risky or md_blocks.has_unclosed_fence(body)
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


def record(root, text: str, about: str | None = None, bet: str | None = None,
           kind: str | None = None, line: str | None = None) -> dict:
    """Write one decision down. Returns what was written.

    The whole command, minus the argument parsing — so the browser and the CLI
    reach the same three writes rather than two implementations that agree
    until one of them is changed.

    Everything checkable is checked before `decisions.md` is touched: an entry
    saying a person predicted something, on a note that cannot carry the
    prediction, is a record of a decision that left no trace anywhere it can be
    audited.
    """
    if not (text or "").strip():
        raise Refused("nothing to record — pass what they actually said")
    if bet and not about:
        raise Refused("--bet needs --about: a prediction is about a proposition")
    if bet and bet not in vocab.BETS:
        raise Refused(f"a bet is one of {', '.join(vocab.BETS)}")
    if kind and kind not in KINDS:
        raise Refused(f"a decision is one of {', '.join(KINDS)}")

    root = Path(root)
    path = None
    if about:
        path = note_path(root, about)
        if not path.is_file():
            if bet:
                raise Refused(f"no note at {path} — nothing was written; check the slug")
            append_decision(root, text, about, kind)
            raise Refused(f"no note at {path} — the entry is in {DECISIONS} either way")
        if bet and threads.read_note(path).kind != vocab.PROPOSITION:
            raise Refused(
                f"--bet needs a proposition; {about} is a "
                f"{threads.read_note(path).kind}. A prediction is about a claim "
                "that can turn out to be wrong.")

    written = [str(append_decision(root, text, about, kind))]
    if path is not None:
        try:
            if bet:
                threads.set_field(path, "bet", bet, host=vocab.HUMAN, text=text,
                                  line=line)
            else:
                threads.append_post(path, text, host=vocab.HUMAN, line=line)
        except (ValueError, OSError) as exc:
            raise Refused(f"recorded in {DECISIONS}, but {path.name} did not "
                          f"take it: {exc}")
        written.append(str(path))
    return {"written": written, "about": about, "bet": bet, "kind": kind}


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
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir", help="Project directory (default: discovered from cwd)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    # Before the workspace lookup: "you passed no words" is true wherever you
    # are standing, and answering "no workspace found" to it sends somebody to
    # fix the wrong thing.
    if not args.text.strip():
        print("nothing to record — pass what they actually said", file=sys.stderr)
        return 1

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        print("no project found (run inside one, or pass --project-dir)",
              file=sys.stderr)
        return 1

    try:
        result = record(root, args.text, about=args.about, bet=args.bet,
                        kind=args.kind, line=args.line)
    except Refused as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        names = ", ".join(Path(w).name for w in result["written"])
        print(f"recorded in {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
