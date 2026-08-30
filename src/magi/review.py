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
import time
from dataclasses import dataclass
from pathlib import Path

from .core import hosts as host_table
from .core import ledger, vocab
from .core.workspace import find_workspace_root
from .kb import threads

#: Long enough for a model to read a derivation, short enough that a hung CLI
#: does not hold a session's close hostage.
TIMEOUT = 300

VERDICT_STANDS = "stands"
VERDICT_REFUTED = "refuted"
VERDICT_UNCLEAR = "unclear"

#: A verdict line, as models actually write it. Anchored to the start of a
#: line — "I would not say VERDICT: stands" is not a verdict — but tolerant of
#: the decoration they put around it: bold, a quote marker, a list bullet, and
#: whatever clause follows the word. Refusing `**VERDICT: refuted**` and
#: reading it as "unclear" would throw away a real refutation over asterisks.
_VERDICT_RE = re.compile(
    r"^[\s>*\-#`]*\**\s*VERDICT\s*:?\s*\**\s*(stands|refuted|unclear)\b"
    r"(?![|/,])",
    re.IGNORECASE | re.MULTILINE)
_REASON_RE = re.compile(r"^[\s>*\-#`]*\**\s*REASON\s*:?\s*\**\s*(.+)",
                        re.IGNORECASE | re.MULTILINE | re.DOTALL)

#: What `apply_verdict` writes. `pending()` reads it back to tell a review that
#: happened from a post that merely mentions one.
_ANSWER_RE = re.compile(r"^VERDICT:\s*(stands|refuted)\b")

#: How much of a reason is kept. The post is the record — `raw` survives only
#: in `--json` — so this is the whole of what a reader gets. The prompt asks
#: for two or three sentences naming a file and a line, and one such citation
#: rendered as a link to a Windows path runs past 200 characters on its own.
REASON_CHARS = 1600


def _trim(text: str, limit: int = REASON_CHARS) -> str:
    """A reason, cut on a boundary and marked where it was cut.

    Cutting at a fixed offset landed mid-URL on the first real review this
    ever ran, which turns a citation into a broken link and reads as a
    reviewer that stopped mid-sentence. Cut at whitespace, and say so.
    """
    said = " ".join(str(text or "").split())
    if len(said) <= limit:
        return said
    cut = said.rfind(" ", 0, limit)
    return said[: cut if cut > limit // 2 else limit].rstrip() + " […truncated]"

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

Answer in exactly this form and nothing else — one word, not the list:

VERDICT: <stands, refuted, or unclear>
REASON: <two or three sentences, naming the file and the line you are talking about>
"""


@dataclass
class Verdict:
    slug: str
    verdict: str
    reason: str
    host: str
    raw: str = ""
    #: Set when the call never produced a reply — no CLI, a timeout, a crash.
    #: This is *not* a verdict, and the difference matters more than anything
    #: else in this file: a review that did not happen must leave the claim
    #: waiting for one, or a broken adapter silently approves the library.
    error: str = ""

    @property
    def ran(self) -> bool:
        return not self.error

    @property
    def rejected(self) -> bool:
        return self.ran and self.verdict == VERDICT_REFUTED


def catalog(config=None) -> dict:
    """Hosts that can be asked a question headless, by key.

    A record with no `argv` declares no non-interactive mode, so there is
    nothing to run and it is not a reviewer. Everything else about a host —
    where its skills go, whose transcripts we can read — lives in the same
    record and is none of this module's business.
    """
    return {key: host for key, host in host_table.catalog(config).items()
            if host.argv}


def host_names(config=None) -> list:
    """Reviewer keys in the table's own order, for messages and `--host`."""
    return [name for name in host_table.names(config) if name in catalog(config)]


def installed_hosts(config=None) -> list:
    """Which reviewer CLIs are on PATH, in a stable order.

    Probed by *binary*, not by key. A host's name and its command are two
    different strings — Antigravity's command is `agy` — and probing for the
    name answered "not installed" for a CLI that was sitting right there.
    """
    table = catalog(config)
    return [name for name in host_names(config)
            if shutil.which(table[name].command)]


def pick_host(author: str | None, installed=None, configured: str | None = None,
              config=None) -> str | None:
    """Which CLI reviews a claim written by `author`.

    Cross-vendor first: the point is a reader that does not share the writer's
    context, and the cheapest version of that is a different vendor's model. A
    same-host fallback is still worth running — a fresh session with none of
    the conversation is not nothing — but it is second choice, and the verdict
    says which one it was so a reader can weigh it.
    """
    available = installed if installed is not None else installed_hosts(config)
    if configured:
        return configured if configured in available else None
    others = [name for name in available if name != author]
    if others:
        return others[0]
    return available[0] if available else None


def build_prompt(root, slug: str) -> str:
    return PROMPT.format(root=Path(root).resolve(), slug=slug)


def unreviewable(root, slugs) -> list:
    """`[(slug, why, suggestions)]` for every named slug that cannot be read.

    Called before the subprocess, for the same reason the host check is: a
    reviewer that cannot be run and a claim that does not exist are the same
    refusal, and both have to happen before the money. A typo used to reach
    `apply_verdict`, which is after the call, so `magi review p-gapp` spent a
    real fifteen-second call asking a model about a file that was not there
    and then said `verdict not written`.
    """
    import difflib

    known = [path.stem for path in threads.note_paths(root)]
    out = []
    for slug in slugs:
        try:
            path = _note_path(root, slug)
        except ValueError:
            out.append((slug, "not a slug", []))
            continue
        if not path.is_file():
            out.append((slug, f"no note at {threads.DIRNAME}/{slug}.md",
                        difflib.get_close_matches(slug, known, n=3, cutoff=0.6)))
            continue
        try:
            kind = threads.read_note(path).kind
        except (OSError, ValueError) as exc:
            out.append((slug, f"cannot be read ({exc.__class__.__name__})", []))
            continue
        if kind != vocab.PROPOSITION:
            # `pending()` only ever offers propositions and the prompt asks
            # whether a claim holds. `magi review qah` is one keystroke from a
            # real slug and would otherwise spend a call on a line note.
            out.append((slug, f"is a {kind}, and a review answers a proposition",
                        []))
    return out


#: The last line of the prompt a host might echo. Everything up to and
#: including it is our own text coming back, not an answer.
_ECHO_MARKS = ("REASON: <two or three sentences",
               "Answer in exactly this form")


def _after_echo(text: str) -> str:
    """What the reviewer said, with our own instructions removed.

    A host that echoes the prompt hands back a reply containing the answer
    *template*, and a template that looks like an answer is an approval nobody
    gave. Cutting at the last occurrence keeps a real answer that happens to
    quote the instruction.
    """
    cut = 0
    for mark in _ECHO_MARKS:
        found = text.rfind(mark)
        if found >= 0:
            end = text.find("\n", found)
            cut = max(cut, len(text) if end < 0 else end + 1)
    return text[cut:] if cut else text


def parse_verdict(text: str) -> tuple:
    """`(verdict, reason)` from a reviewer's answer.

    An answer nobody can parse is `unclear`, not a crash and not a pass. A
    reviewer that rambled has told us it could not answer in the required form,
    and treating that as approval is how a broken adapter becomes a rubber
    stamp.
    """
    # Anything before the last `--- SESSIONS ---`-style echo of our own words
    # is not the reviewer talking. Hosts that print the instruction back
    # (codex does) otherwise hand us a verdict we wrote ourselves.
    text = _after_echo(text or "")
    said = {m.group(1).lower() for m in _VERDICT_RE.finditer(text)}
    reason = ""
    found = _REASON_RE.search(text or "")
    if found:
        reason = _trim(found.group(1))

    if len(said) == 1:
        return said.pop(), reason
    if len(said) > 1:
        # Two different verdicts in one reply. There is no rule for picking
        # the "real" one that does not sometimes pick a `stands` the reviewer
        # went on to withdraw, so the honest answer is that we cannot tell.
        return VERDICT_UNCLEAR, ("the reviewer gave more than one verdict "
                                 f"({', '.join(sorted(said))}); its reply is quoted below")
    return VERDICT_UNCLEAR, (reason or "the reviewer did not answer in the required "
                             "form; its reply is quoted below")


def plan(host: str, model=None, effort=None, settings: "Settings | None" = None,
         config=None) -> tuple:
    """`(entry, model, effort)` — what this call will actually ask for.

    The chain has four links and only the record can walk it: `--model`, then
    the host record, then `research.review_model`, then the record's cheap
    tier. Call sites used to write `model or settings.model`, which merges the
    first and third and leaves nowhere for the other two — so a workspace that
    configured nothing got whichever model that CLI charges most for, which is
    exactly what design-v2 §11 says not to do.
    """
    # The settings carry the config when the caller did not name one, which
    # is every caller: `plan` is reached from `ask`, `review` and `main`, and
    # all three have settings and none of them had a config to pass.
    if config is None and settings is not None:
        config = settings.config
    entry = catalog(config).get(host)
    if entry is None:
        raise RuntimeError(f"no headless mode declared for {host!r} "
                           f"(known: {', '.join(host_names(config))})")
    return (entry,
            entry.pick_model(model or "", (settings.model if settings else "") or ""),
            entry.pick_effort(effort or "", (settings.effort if settings else "") or ""))


def ask(host: str, prompt: str, cwd, model: str | None = None,
        timeout: int = TIMEOUT, effort: str | None = None,
        settings: "Settings | None" = None) -> str:
    """Run one headless review. Returns the reply, or raises."""
    entry, model, effort = plan(host, model, effort, settings)
    argv = entry.headless(prompt, model, effort)
    # The path `which` found, not the bare name. On Windows `CreateProcess`
    # completes `.exe` and nothing else, so an npm-installed host — `gemini`
    # is `gemini.CMD` — was never actually run: every review failed with
    # FileNotFoundError and the claim stayed on the list forever.
    found = shutil.which(argv[0])
    if found:
        argv = [found] + argv[1:]
    proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode != 0 and not (proc.stdout or "").strip():
        raise RuntimeError(f"{host} exited {proc.returncode}: "
                           f"{(proc.stderr or '').strip()[-300:]}")
    return proc.stdout or ""


def review(root, slug: str, author: str | None = None, host: str | None = None,
           model: str | None = None, timeout: int = TIMEOUT,
           effort: str | None = None, settings: "Settings | None" = None) -> Verdict:
    """Ask another CLI whether one proposition holds.

    The call is written into the ledger whether it worked or not: a review that
    timed out spent the wall clock and, on a metered account, the money, and a
    budget that only counts successes is a budget a broken adapter can walk
    straight through.
    """
    config = settings.config if settings else None
    chosen = host or pick_host(author, config=config)
    if chosen is None:
        raise RuntimeError("no reviewer CLI on PATH "
                           f"(looked for {', '.join(host_names(config))})")
    # Here, not in the caller. `ledger.check` calls itself "one call at the top
    # of anything that spends", and the batch path spent once per slug behind a
    # single check: a workspace 39 calls into a limit of 40 could run sixty
    # reviews and finish the week at 99/40. `reflect` and `propose` both gate
    # per call; this was the one path that did not.
    ledger.check(root, limit=(settings.limit if settings else None),
                 enabled=(settings.enabled if settings else True))
    # Resolved once, here, so the ledger records what was asked for rather than
    # what was typed. With nothing typed this is the cheap tier, and a ledger
    # entry saying `model: null` for it could not tell a Haiku review from an
    # Opus one afterwards.
    _entry, model, effort = plan(chosen, model, effort, settings)
    started = time.monotonic()
    try:
        reply = ask(chosen, build_prompt(root, slug), cwd=root, model=model,
                    timeout=timeout, effort=effort)
    except BaseException as exc:  # noqa: BLE001 - recorded, then re-raised
        _spend(root, chosen, slug, model, ok=False, since=started,
               note=exc.__class__.__name__, effort=effort)
        raise
    _spend(root, chosen, slug, model, ok=True, since=started, effort=effort)
    verdict, reason = parse_verdict(reply)
    return Verdict(slug=slug, verdict=verdict, reason=reason, host=chosen, raw=reply)


def _spend(root, host, slug, model, *, ok, since, note="", effort=None) -> None:
    """Record one call. Never the reason a review fails."""
    try:
        ledger.record(root, ledger.REVIEW, host, model=model, effort=effort,
                      slug=slug, ok=ok, seconds=time.monotonic() - since, note=note)
    except OSError:
        pass


def apply_verdict(root, result: Verdict) -> str:
    """Write the verdict into the note. Returns a line for the report.

    A rejection lands as `disputed` and stops there. It is not `refuted` —
    the reviewer's disagreement is not a finding — and nothing walks it back
    to `supported` without a person, which is what `vocab` means by that
    transition being a human's call.
    """
    if not result.ran:
        # Nothing is written. A note that carries a reviewer's post is a note
        # `pending()` stops offering, so posting "the review could not run"
        # would retire the claim on the strength of a review that never
        # happened — the exact rubber stamp this command exists to avoid.
        return f"{result.slug}: not reviewed — {result.error}"

    path = _note_path(root, result.slug)
    body = f"{result.reason}\n\n(reviewed headless by {result.host})"
    if result.verdict == VERDICT_UNCLEAR and _needs_evidence(result):
        # The fallback reason promises the reply is here. Without it a reader
        # cannot tell a broken adapter from a genuinely undecidable claim,
        # which is the one thing they need to know to act on an `unclear`.
        body += "\n\nWhat it actually said:\n\n" + _excerpt(result.raw)

    if not result.rejected:
        threads.append_post(path, f"VERDICT: {result.verdict}\n\n{body}",
                            host=vocab.REVIEWER)
        return f"{result.slug}: {result.verdict}"

    note = threads.read_note(path)
    posted = f"VERDICT: refuted\n\n{body}"
    if note.status == "disputed":
        threads.append_post(path, posted, host=vocab.REVIEWER)
        return f"{result.slug}: refuted (already disputed)"

    try:
        threads.set_status(path, "disputed", posted, host=vocab.REVIEWER)
    except threads.IllegalTransition:
        # `magi review <slug>` takes any slug, and `open → disputed` is not a
        # move. The verdict is still worth having: it is posted where the note
        # can be read, and the status is left for a person. Raising here would
        # throw away every verdict in the batch after this one, each of which
        # was paid for.
        threads.append_post(path, posted, host=vocab.REVIEWER)
        return (f"{result.slug}: refuted — left at `{note.status}` "
                "(nothing goes from there to disputed); posted for a person")
    return f"{result.slug}: refuted — now disputed, and on the decision queue"


def _is_answer(post) -> bool:
    """Did this post settle the question, or merely mention it?

    Only a reviewer's `stands` or `refuted` retires a claim. Everything else a
    reviewer might leave behind — an `unclear`, a note about a failed run — is
    a post, not an answer.

    Only the **first line** counts. An `unclear` post quotes the reviewer's
    own words underneath, and a reply that argued both sides would otherwise
    clear the claim on the strength of the word `stands` appearing inside the
    quotation.
    """
    if post.host != vocab.REVIEWER:
        return False
    first = (post.text or "").lstrip().splitlines()
    return bool(first) and bool(_ANSWER_RE.match(first[0]))


def _note_path(root, slug: str) -> Path:
    """`threads/<slug>.md`, refusing anything that is not a slug.

    A typo with a separator in it would otherwise append a forum post to a file
    outside `threads/` — quietly, and to a file that has no discussion to
    append to.
    """
    if not slug or slug != Path(slug).name or slug.startswith(".") or "\\" in slug:
        raise ValueError(f"not a slug: {slug!r}")
    return Path(root) / threads.DIRNAME / f"{slug}.md"


def _needs_evidence(result) -> bool:
    """Is the reason in the post the reviewer's own words, or ours?

    A reviewer that answered in the required form has already said why, and
    repeating its sentence under "what it actually said" is noise. A reviewer
    whose reply we could not parse has said nothing the post carries — that is
    the case the excerpt exists for.
    """
    raw = " ".join((result.raw or "").split())
    if not raw:
        return False
    return not (result.reason and result.reason in raw)


def _excerpt(raw: str, limit: int = 1200) -> str:
    """The reviewer's own words, fenced so they cannot be read as structure."""
    body = (raw or "").strip()
    if len(body) > limit:
        body = body[:limit].rstrip() + "\n…"
    fence = "`" * max(3, max((len(m) for m in re.findall(r"`+", body)), default=0) + 1)
    return f"{fence}text\n{body}\n{fence}"


def review_batch(root, slugs, author: str | None = None, host: str | None = None,
                 model: str | None = None, timeout: int = TIMEOUT,
                 effort: str | None = None, settings: "Settings | None" = None) -> list:
    """Review several propositions. One failure does not stop the rest.

    Running out of budget is not one of those failures. It stops the loop, and
    the shorter list of results is how the caller learns that — every slug
    after the last result is untouched and still unreviewed, which is the
    honest outcome and the one `ledger` is built to produce.
    """
    out = []
    for slug in slugs:
        try:
            result = review(root, slug, author=author, host=host, model=model,
                            timeout=timeout, effort=effort, settings=settings)
        except (ledger.OverBudget, ledger.SwitchedOff):
            # Before the `RuntimeError` clause, which `OverBudget` subclasses.
            # Nothing reaches the notes either way — `apply_verdict` refuses to
            # post a review that never happened — but falling through returns
            # one identical "budget is spent" result per remaining claim, and
            # then the count of results still matches the count of slugs, so
            # nothing downstream can tell a run that stopped early from one
            # that finished. Stopping is what makes the short list mean
            # something.
            break
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            out.append(Verdict(slug=slug, verdict=VERDICT_UNCLEAR, host=host or "?",
                               reason=f"the review could not run ({exc})",
                               error=str(exc) or exc.__class__.__name__))
            continue
        out.append(result)
    return out


def pending(root, notes=None) -> list:
    """Propositions claiming to be solved that no reviewer has answered on.

    "Answered" is a reviewer's post *after* the last flip to `supported`, in
    file order. Order and not timestamp: posts are stamped to the second, and a
    flip and its review land in the same second often enough that comparing
    times would call a fresh claim already-reviewed. The file is append-only,
    so its order is the authoritative sequence anyway.

    Re-reviewing something already judged spends a call and buries the first
    verdict under a second one saying the same thing. Re-supporting after a
    verdict is a different matter: that verdict was about the old evidence, and
    new evidence is a new question.

    An *answer* is a verdict of `stands` or `refuted`. An `unclear` post is a
    reviewer saying it could not tell, which is not an answer — the claim goes
    back on the list rather than retiring on a non-answer.
    """
    out = []
    # `notes` when the caller has them. `state.close` runs inside the Stop
    # hook with the whole projection already in memory, and this used to open
    # and re-parse every file in `threads/` to answer a question about notes
    # it was holding — a second reader of the same files, which `rules.check`
    # calls "a second answer waiting to disagree".
    source = notes if notes is not None else (
        threads.read_note(p) for p in threads.note_paths(root))
    for note in source:
        if note.kind != vocab.PROPOSITION or note.status != "supported":
            continue
        last_supported = -1
        for index, post in enumerate(note.posts):
            if post.is_transition and post.dst == "supported":
                last_supported = index
        reviewed = any(_is_answer(post)
                       for post in note.posts[last_supported + 1:])
        if not reviewed:
            out.append(note.slug)
    return out


@dataclass
class Settings:
    """What the workspace says about reviewing, in one object.

    `config` is the loaded file itself, kept because the host table is part of
    what the workspace says: `research.hosts` declares CLIs beyond the built-in
    five, and every function that reads it takes a `config` argument that
    nothing was passing. Carrying it here means one load per command and one
    place that can forget it, instead of six call sites that each could.
    """
    limit: int = ledger.DEFAULT_WEEKLY
    enabled: bool = True
    host: str | None = None
    model: str | None = None
    effort: str | None = None
    config: dict | None = None


def _config(root) -> Settings:
    """The review settings for this workspace.

    `host` and `model` are read here rather than only accepted as flags: a
    field the WebUI can set, the shipped config documents, and the command
    ignores is worse than a missing one — somebody sets it, nothing changes,
    and the config becomes a file they stop believing.
    """
    from .core.config_loader import get as config_get
    from .core.config_loader import load_config

    config = load_config(start=root)
    return Settings(
        limit=config_get(config, "research.weekly_calls", ledger.DEFAULT_WEEKLY),
        enabled=bool(config_get(config, "research.llm_calls", True)),
        host=(config_get(config, "research.review_host", "") or None),
        model=(config_get(config, "research.review_model", "") or None),
        effort=(config_get(config, "research.review_effort", "") or None),
        config=config)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi review",
        description="Have another agent CLI check a claim that says it is solved.")
    parser.add_argument("slug", nargs="*",
                        help="Propositions to review (default: everything unreviewed)")
    parser.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    # No `choices=` on purpose. The table depends on `research.hosts`, and the
    # workspace it comes from is not known until `--topic-dir` has been parsed
    # — so `choices=` could only ever list the built-in five, and rejected the
    # host a person had declared themselves before anything read their config.
    # Checked below instead, where the message can name their host.
    parser.add_argument("--host",
                        help="Reviewer CLI (default: any installed one that is not --author)")
    parser.add_argument("--author", help="The CLI that wrote the claim; the reviewer avoids it")
    parser.add_argument("--model", help="Pin the reviewer's model (default: this host's "
                                        "cheap tier, which is the point)")
    parser.add_argument("--effort", choices=host_table.EFFORTS,
                        help="Reasoning level, where the host takes one")
    parser.add_argument("--timeout", type=int, default=TIMEOUT)
    parser.add_argument("--dry-run", action="store_true",
                        help="Say who would be asked about what, and stop.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        print("no workspace found (run inside a topic or pass --topic-dir)", file=sys.stderr)
        return 1

    settings = _config(root)
    limit, enabled = settings.limit, settings.enabled
    # A flag beats the file, and the file beats the probe.
    known = host_names(settings.config)
    if args.host and args.host not in known:
        print(f"unknown host {args.host!r} — known: {', '.join(known)}. "
              f"Declare another under `research.hosts` in config.yaml.",
              file=sys.stderr)
        return 1

    wanted_host = args.host or settings.host

    slugs = args.slug or pending(root)
    if not slugs:
        print("nothing to review — no proposition is claiming to be solved unanswered.")
        return 0

    # Before the subprocess, like the host check above. A named slug that
    # cannot be reviewed is dropped here rather than paid for and discarded in
    # `apply_verdict`, which is where a typo used to land — after the call.
    refused = unreviewable(root, args.slug or [])
    for slug, why, near in refused:
        hint = f" Did you mean: {', '.join(near)}?" if near else ""
        print(f"{slug}: {why}.{hint}", file=sys.stderr)
    if refused:
        # Dropped, not fatal: naming ten slugs and getting nothing because one
        # had a typo is a worse command than one that does the nine. The exit
        # code still says the command did not do what it was asked.
        bad = {slug for slug, _why, _near in refused}
        slugs = [slug for slug in slugs if slug not in bad]
        if not slugs:
            print("Nothing was asked, and nothing counts as reviewed.",
                  file=sys.stderr)
            return 1

    # `--host` names a preference, not a fact. Sending it through `pick_host`
    # is what makes "you asked for codex and there is no codex" say so instead
    # of failing once per claim and calling each one reviewed.
    chosen = pick_host(args.author, configured=wanted_host, config=settings.config)
    if chosen is None:
        named = f"'{wanted_host}' is not installed" if wanted_host else \
            f"no reviewer CLI on PATH (looked for {', '.join(known)})"
        print(f"{named}. The claim stays unreviewed rather than self-approved.",
              file=sys.stderr)
        return 1

    # What the call will actually ask for, resolved the same way the call
    # resolves it. A four-link chain that only shows itself after the money is
    # spent is a chain nobody can check.
    _entry, model, effort = plan(chosen, args.model, args.effort, settings)

    if args.dry_run:
        payload = {"host": chosen, "model": model or None, "effort": effort or None,
                   "slugs": slugs, "budget": ledger.summary(root, limit=limit)}
        print(json.dumps(payload, ensure_ascii=False) if args.json
              else f"would ask {chosen}"
                   + (f" ({model}" if model else " (its own default")
                   + (f", effort {effort})" if effort else ")")
                   + f" about: {', '.join(slugs)}")
        return 0

    # Before the subprocess, not after: a budget that stops the call but lets
    # the claim retire unreviewed would spend nothing and approve everything.
    try:
        ledger.check(root, limit=limit, enabled=enabled)
    except (ledger.OverBudget, ledger.SwitchedOff) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    results = review_batch(root, slugs, author=args.author, host=chosen,
                           model=model, timeout=args.timeout, effort=effort,
                           settings=settings)
    lines = []
    for result in results:
        try:
            lines.append(apply_verdict(root, result))
        except (ValueError, OSError) as exc:
            lines.append(f"{result.slug}: verdict not written ({exc})")
            result.error = result.error or str(exc)

    if args.json:
        print(json.dumps([vars(r) for r in results], ensure_ascii=False, indent=2))
    else:
        for line in lines:
            print(f"  {line}")
        # Said at the moment it is spent. `MAP.md` carries this too, but it is
        # DERIVED and only rewritten at session close — so between a review and
        # the next `sync --close` the one surface a person would check still
        # shows the old number, and the question "did that just cost me
        # something" has no answer where it is being asked.
        # `results`, not "any of them succeeded": a call that was made and
        # then failed is recorded in the ledger too — a timeout spent the wall
        # clock and, on a metered account, the money — so that is exactly when
        # somebody most wants the number.
        if results:
            spend = ledger.summary(root, limit=limit)
            print(f"  ({spend['spent']}/{spend['limit']} model calls this week, "
                  f"{spend['left']} left)")

    # A short list is the only sign the budget stopped the run, so it is said
    # out loud rather than left for somebody to notice by counting.
    if len(results) < len(slugs):
        left = slugs[len(results):]
        try:
            ledger.check(root, limit=limit, enabled=enabled)
            why = "the weekly budget ran out"
        except (ledger.OverBudget, ledger.SwitchedOff) as exc:
            why = str(exc)
        print(f"stopped after {len(results)} of {len(slugs)} — {why}\n"
              f"still unreviewed: {', '.join(left)}", file=sys.stderr)
        return 1
    # A run where nothing could be asked is a failure, not a quiet success.
    # Exiting 0 there is how a broken install looks like a reviewed library.
    # `error` is in the condition because a verdict that came back and could
    # not be written is the same thing from the caller's side: the call was
    # spent and the claim is no better off than before. `refused` is in it
    # because a name that was dropped is a claim nobody looked at.
    return 1 if refused or any(r.rejected or not r.ran or r.error
                               for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
