"""`magi review` — a second reader for a proposition that claims to be solved.

The rule this exists to enforce is design-v2's "记账靠近，评判远离": the writer
nearest a piece of work records its state, and somebody who does not share
their context judges whether it holds. An agent grading its own output is not
a review — it has already been convinced once, by the same reasoning, and the
second pass agrees for the same reasons the first one did.

So the reviewer runs **headless, in another vendor's CLI**. Cross-vendor by
default and by probe, not by configuration: whichever installed CLI is not the
one that wrote the claim. That is a cheap approximation of independence — a
different model, a different system prompt, no shared conversation — and it
costs nothing to arrange, which is the only reason it will actually happen on
every claim rather than on the ones somebody remembered.

**What it sees is deliberately narrow.** The proposition, its derivation, and
the cold layer it cites. Not the chat that produced it, not the research line's
own narrative of how well things are going. "Far" means not sharing context; it
does not mean not having evidence.

**What it may do is narrower still.** It posts a verdict. A rejection moves the
proposition to `disputed`, which is a question for a person — never back to
`refuted`, and never silently back to `supported` on the next run. The reviewer
is a second opinion, not a second author.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .core import vocab
from .core.workspace import find_workspace_root
from .kb import threads

#: How each host is asked one question and gives one answer back. Every entry
#: is a documented non-interactive mode: these are not guesses at an internal
#: flag, and a host whose print mode is not documented does not belong here.
HOSTS = {
    "claude": lambda prompt, model: (
        ["claude", "-p", prompt] + (["--model", model] if model else [])),
    "codex": lambda prompt, model: (
        ["codex", "exec", prompt] + (["-m", model] if model else [])),
    "gemini": lambda prompt, model: (
        ["gemini", "-p", prompt] + (["-m", model] if model else [])),
    "qwen": lambda prompt, model: (
        ["qwen", "-p", prompt] + (["-m", model] if model else [])),
}

#: Long enough for a model to read a derivation, short enough that a hung CLI
#: does not hold a session's close hostage.
TIMEOUT = 300

VERDICT_STANDS = "stands"
VERDICT_REFUTED = "refuted"
VERDICT_UNCLEAR = "unclear"

_VERDICT_RE = re.compile(r"^\s*VERDICT:\s*(stands|refuted|unclear)\s*$",
                         re.IGNORECASE | re.MULTILINE)
_REASON_RE = re.compile(r"^\s*REASON:\s*(.+)", re.IGNORECASE | re.MULTILINE | re.DOTALL)

PROMPT = """You are reviewing one claim in a research library. You did not write it.

Workspace: {root}
Proposition: threads/{slug}.md

Read that file. Read whatever it names under `derivation:`. Read the sources it
cites under `raw/`. Do not read anything else about how the project is going —
your value here is that you have no stake in the answer.

Decide one thing: does the claim, as written, follow from the evidence it cites?

- Cited evidence that does not say what the claim says it says: refuted.
- A step in the derivation that does not follow: refuted.
- A claim broader than its evidence supports: refuted, and say which part.
- You cannot tell without something that is not here: unclear.
- Otherwise: stands.

Answer in exactly this form and nothing else:

VERDICT: stands|refuted|unclear
REASON: <two or three sentences, naming the file and the line you are talking about>
"""


@dataclass
class Verdict:
    slug: str
    verdict: str
    reason: str
    host: str
    raw: str = ""

    @property
    def rejected(self) -> bool:
        return self.verdict == VERDICT_REFUTED


def installed_hosts() -> list:
    """Which reviewer CLIs are on PATH, in a stable order."""
    return [name for name in HOSTS if shutil.which(name)]


def pick_host(author: str | None, installed=None, configured: str | None = None) -> str | None:
    """Which CLI reviews a claim written by `author`.

    Cross-vendor first: the point is a reader that does not share the writer's
    context, and the cheapest version of that is a different vendor's model. A
    same-host fallback is still worth running — a fresh session with none of
    the conversation is not nothing — but it is second choice, and the verdict
    says which one it was so a reader can weigh it.
    """
    available = installed if installed is not None else installed_hosts()
    if configured:
        return configured if configured in available else None
    others = [name for name in available if name != author]
    if others:
        return others[0]
    return available[0] if available else None


def build_prompt(root, slug: str) -> str:
    return PROMPT.format(root=Path(root).resolve(), slug=slug)


def parse_verdict(text: str) -> tuple:
    """`(verdict, reason)` from a reviewer's answer.

    An answer nobody can parse is `unclear`, not a crash and not a pass. A
    reviewer that rambled has told us it could not answer in the required form,
    and treating that as approval is how a broken adapter becomes a rubber
    stamp.
    """
    match = _VERDICT_RE.search(text or "")
    verdict = match.group(1).lower() if match else VERDICT_UNCLEAR
    reason = ""
    found = _REASON_RE.search(text or "")
    if found:
        reason = " ".join(found.group(1).split())[:600]
    elif not match:
        reason = ("the reviewer did not answer in the required form; its reply is "
                  "in the post below")
    return verdict, reason


def ask(host: str, prompt: str, cwd, model: str | None = None,
        timeout: int = TIMEOUT) -> str:
    """Run one headless review. Returns the reply, or raises."""
    argv = HOSTS[host](prompt, model)
    proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode != 0 and not (proc.stdout or "").strip():
        raise RuntimeError(f"{host} exited {proc.returncode}: "
                           f"{(proc.stderr or '').strip()[-300:]}")
    return proc.stdout or ""


def review(root, slug: str, author: str | None = None, host: str | None = None,
           model: str | None = None, timeout: int = TIMEOUT) -> Verdict:
    """Ask another CLI whether one proposition holds."""
    chosen = host or pick_host(author)
    if chosen is None:
        raise RuntimeError("no reviewer CLI on PATH "
                           f"(looked for {', '.join(HOSTS)})")
    reply = ask(chosen, build_prompt(root, slug), cwd=root, model=model, timeout=timeout)
    verdict, reason = parse_verdict(reply)
    return Verdict(slug=slug, verdict=verdict, reason=reason, host=chosen, raw=reply)


def apply_verdict(root, result: Verdict) -> str:
    """Write the verdict into the note. Returns a line for the report.

    A rejection lands as `disputed` and stops there. It is not `refuted` —
    the reviewer's disagreement is not a finding — and nothing walks it back
    to `supported` without a person, which is what `vocab` means by that
    transition being a human's call.
    """
    path = Path(root) / threads.DIRNAME / f"{result.slug}.md"
    body = f"{result.reason}\n\n(reviewed headless by {result.host})"

    if not result.rejected:
        threads.append_post(path, f"VERDICT: {result.verdict}\n\n{body}",
                            host=vocab.REVIEWER)
        return f"{result.slug}: {result.verdict}"

    note = threads.read_note(path)
    if note.status == "disputed":
        threads.append_post(path, f"VERDICT: refuted\n\n{body}", host=vocab.REVIEWER)
        return f"{result.slug}: refuted (already disputed)"

    threads.set_status(path, "disputed", body, host=vocab.REVIEWER)
    return f"{result.slug}: refuted — now disputed, and on the decision queue"


def review_batch(root, slugs, author: str | None = None, host: str | None = None,
                 model: str | None = None, timeout: int = TIMEOUT) -> list:
    """Review several propositions. One failure does not stop the rest."""
    out = []
    for slug in slugs:
        try:
            result = review(root, slug, author=author, host=host, model=model,
                            timeout=timeout)
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            out.append(Verdict(slug=slug, verdict=VERDICT_UNCLEAR, host=host or "?",
                               reason=f"the review could not run ({exc})"))
            continue
        out.append(result)
    return out


def pending(root) -> list:
    """Propositions claiming to be solved that no reviewer has answered on.

    "Answered" is a post signed by the reviewer after the last flip to
    `supported`. Re-reviewing something already judged wastes a call and buries
    the first verdict under a second one that says the same thing.
    """
    from . import state as state_mod

    out = []
    for note in (threads.read_note(p) for p in threads.note_paths(root)):
        if note.kind != vocab.PROPOSITION or note.status != "supported":
            continue
        supported_at = None
        for post in note.posts:
            if post.is_transition and post.dst == "supported":
                supported_at = state_mod.parse_at(post.at)
        reviewed = any(post.host == vocab.REVIEWER
                       and (supported_at is None
                            or (state_mod.parse_at(post.at) or supported_at) >= supported_at)
                       for post in note.posts)
        if not reviewed:
            out.append(note.slug)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi review",
        description="Have another agent CLI check a claim that says it is solved.")
    parser.add_argument("slug", nargs="*",
                        help="Propositions to review (default: everything unreviewed)")
    parser.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    parser.add_argument("--host", choices=list(HOSTS),
                        help="Reviewer CLI (default: any installed one that is not --author)")
    parser.add_argument("--author", help="The CLI that wrote the claim; the reviewer avoids it")
    parser.add_argument("--model", help="Pin the reviewer's model (a cheap one is the point)")
    parser.add_argument("--timeout", type=int, default=TIMEOUT)
    parser.add_argument("--dry-run", action="store_true",
                        help="Say who would be asked about what, and stop.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        print("no workspace found (run inside a topic or pass --topic-dir)", file=sys.stderr)
        return 1

    slugs = args.slug or pending(root)
    if not slugs:
        print("nothing to review — no proposition is claiming to be solved unanswered.")
        return 0

    chosen = args.host or pick_host(args.author)
    if chosen is None:
        print(f"no reviewer CLI on PATH (looked for {', '.join(HOSTS)}). "
              "The claim stays unreviewed rather than self-approved.", file=sys.stderr)
        return 1

    if args.dry_run:
        payload = {"host": chosen, "slugs": slugs}
        print(json.dumps(payload, ensure_ascii=False) if args.json
              else f"would ask {chosen} about: {', '.join(slugs)}")
        return 0

    results = review_batch(root, slugs, author=args.author, host=chosen,
                           model=args.model, timeout=args.timeout)
    lines = [apply_verdict(root, result) for result in results]

    if args.json:
        print(json.dumps([vars(r) for r in results], ensure_ascii=False, indent=2))
    else:
        for line in lines:
            print(f"  {line}")
    return 1 if any(r.rejected for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
