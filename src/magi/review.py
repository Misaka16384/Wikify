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
the cold layer it cites; the drafts and cards the argument leans on. Not the
chat that produced it, not the research line's own narrative of how well
things are going. "Far" means not sharing context; it does not mean not
having evidence. The one thing it is told to *discount* is the note's own
Discussion: those posts are commentary, and a slip in one is not a flaw in the
claim (2026-09-03, after a day on which a reviewer refuted a proposition over a
typo in a comment).

**What it may do is narrower still.** It posts a verdict. A rejection moves the
proposition to `disputed`, which is a question for a person — never back to
`refuted`, and never silently back to `supported` on the next run. A `restate`
— the conclusion holds, the words do not — sends the claim back to `testing`
for its author to fix and re-claim, and never near a person. The reviewer is a
second opinion, not a second author.

**It runs on the strong tier.** The first version ran on the cheap one, on the
theory that reading one claim does not need much model. One measured day said
otherwise: the cheap reader passed every substantive error and reported line
numbers it had not read; the strong reader found the one real proof gap. A
review that manufactures confidence is worse than none, so the default is the
model that reads, and the post says which tier answered so a later reader can
weigh it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

from .core import hosts as host_table
from .core import ledger, vocab
from .core.workspace import find_workspace_root
from .kb import threads

#: Long enough for a strong model to read a derivation and run what it names.
#: Was 300; a strong reader at high effort on a four-hundred-line derivation
#: ran past that (2026-09-03), and the review is not in the stop hook any
#: more, so nothing is held hostage by a longer wait. `timeout_for` adds to
#: this when the derivation and evidence are long.
TIMEOUT = 600

#: Extra seconds per size band of what the reviewer has to read.
_LONG_BYTES = 20_000
_VERY_LONG_BYTES = 60_000

VERDICT_STANDS = "stands"
VERDICT_RESTATE = "restate"
VERDICT_REFUTED = "refuted"
VERDICT_UNCLEAR = "unclear"
VERDICTS = (VERDICT_STANDS, VERDICT_RESTATE, VERDICT_REFUTED, VERDICT_UNCLEAR)

_WORDS = "|".join(VERDICTS)

#: A verdict line, as models actually write it. Anchored to the start of a
#: line — "I would not say VERDICT: stands" is not a verdict — but tolerant of
#: the decoration they put around it: bold, a quote marker, a list bullet, and
#: whatever clause follows the word. Refusing `**VERDICT: refuted**` and
#: reading it as "unclear" would throw away a real refutation over asterisks.
_VERDICT_RE = re.compile(
    rf"^[\s>*\-#`]*\**\s*VERDICT\s*:?\s*\**\s*({_WORDS})\b"
    r"(?![|/,])",
    re.IGNORECASE | re.MULTILINE)

#: The labelled sections after the verdict. Each runs to the next label or to
#: the end of the reply, so a model that puts REASON before CHECKED is still
#: read correctly — the old REASON regex ran to the end of the text and would
#: have swallowed the sections after it.
SECTIONS = ("CHECKED", "ASSUMPTION", "REASON")
_SECTION_RE = re.compile(
    rf"^[\s>*\-#`]*\**\s*({'|'.join(SECTIONS)})\s*:?\s*\**[ \t]*",
    re.IGNORECASE | re.MULTILINE)
_REASON_RE = re.compile(r"^[\s>*\-#`]*\**\s*REASON\s*:?\s*\**\s*(.+)",
                        re.IGNORECASE | re.MULTILINE | re.DOTALL)

#: What `apply_verdict` writes. `pending()` reads it back to tell a review that
#: happened from a post that merely mentions one. `restate` is not here: it
#: does not retire a claim, it returns one to its author.
_ANSWER_RE = re.compile(r"^VERDICT:\s*(stands|refuted)\b")
_RESTATE_RE = re.compile(r"^VERDICT:\s*restate\b")

#: The tier, read back off the signature line `apply_verdict` writes. A post
#: from before tiers were recorded has none and is classified as nothing —
#: not as weak, because that would put every old review on the list at once.
_TIER_RE = re.compile(r"·\s*(strong|cheap|pinned|default) tier\b")

#: How much of a reason is kept. The post is the record — `raw` survives only
#: in `--json` — so this is the whole of what a reader gets. The prompt asks
#: for two or three sentences naming a file and a line, and one such citation
#: rendered as a link to a Windows path runs past 200 characters on its own.
REASON_CHARS = 1600

#: The two shorter sections. One or two sentences each; the same citation
#: arithmetic as above, at half the length.
SECTION_CHARS = 800


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

Read that file. Its `claim:` is the statement under review, quantifiers and
all; where there is none, the title is the claim. Whatever it names under
`derivation:` is the recorded argument. The files under `evidence:` are what
checks it — scripts, data, notebooks: read them, and run them if you are able
to. The sources it cites under `raw/` are the evidence. You may also read other
files under `drafts/`, `wiki/`, `tools/` and `raw/` when the argument leans on
them. The `## Discussion` section is commentary: read it for context, but a
slip in a post is not a flaw in the claim, and nothing in a post counts as
evidence for or against it. Do not read other notes under `threads/`, and
nothing about how the project is going — your value here is that you have no
stake in the answer.

Check these, in this order; they are where claims of this kind actually fail:
1. Scope. Does the title claim more than the derivation shows — "for all h"
   where one case is done, "every non-root ideal" where only the maximal ones
   are?
2. Definitions. Is each object what it is called? A "complex" whose
   differentials do not square to zero is not one.
3. Counts and indices. Four where the derivation has three; l−j written j−l.
4. Coverage. Does the proof cover the whole claimed domain, or one slice of
   representatives passed off as the general case?
5. Numerics. If a step fails, does the numerical evidence stand on its own
   (the conclusion survives and the proof needs repair) or was it computed
   through that step (the claim falls)?
6. The load-bearing assumption. Name the one definition or hypothesis the
   claim leans on most, and say whether the conclusion survives a reasonable
   alternative to it.

Verify at least one thing yourself: recompute one formula, re-derive one step,
or, if you are able to run code, rerun one script the derivation names and
report what it printed. A review that only reports where the proof says
something is has not reviewed anything.

Verdicts:
- stands: the claim as written follows from the recorded argument and the
  evidence it cites.
- restate: the conclusion holds but the statement or the written derivation
  must change — a quantifier written too wide, a wrong index, a mislabelled
  object. Say exactly what to change. The author can fix this alone.
- refuted: give a counterexample, or name the specific step that does not hold
  and why. Only `drafts/` and `raw/` count as grounds; a Discussion post does
  not.
- unclear: you cannot tell without something that is not here — including a
  file named under `evidence:` or `derivation:` that is not inside the
  workspace. Say what is missing.

Answer in exactly this form and nothing else — one word, not the list:

VERDICT: <stands, restate, refuted, or unclear>
CHECKED: <one or two sentences: what you recomputed, re-derived or ran, and what came out>
ASSUMPTION: <one sentence: the load-bearing definition or hypothesis, and whether the conclusion survives an alternative>
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
    #: What was actually asked for. Written into the post, because a verdict
    #: from a cheap reader and one from a strong reader are different evidence
    #: and the post is the only record that outlives the ledger.
    model: str = ""
    effort: str = ""
    tier: str = ""
    #: The two sections the prompt asks for besides the reason.
    checked: str = ""
    assumption: str = ""
    #: Hosts asked before this one that failed to answer, as `(host, why)`.
    #: Recorded in the post: a reader weighing a same-vendor verdict deserves
    #: to know the cross-vendor one was tried.
    fell_back: list = field(default_factory=list)

    @property
    def ran(self) -> bool:
        return not self.error

    @property
    def rejected(self) -> bool:
        return self.ran and self.verdict == VERDICT_REFUTED

    @property
    def restated(self) -> bool:
        return self.ran and self.verdict == VERDICT_RESTATE


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


def reviewers(author: str | None, installed=None, configured: str | None = None,
              config=None, skip=()) -> list:
    """Every host to try for one claim, in order. Empty when none is installed.

    The first entry is `pick_host`'s answer. The rest are the fallbacks for
    when it fails to answer — a vendor's quota, a timeout, a crashed process —
    cross-vendor ones first, the author's own CLI last. A configured host that
    is not installed contributes nothing and the list continues without it;
    `main` has already told the person, and a claim is better read by the
    second choice than by nobody.

    `skip` is what a batch has already watched fail this run. Five minutes is
    the timeout, and a host that has just spent five minutes not answering
    should not be asked the same question about the next claim.
    """
    available = [name for name in
                 (installed if installed is not None else installed_hosts(config))
                 if name not in skip]
    first = pick_host(author, installed=available, configured=configured, config=config)
    order = [first] if first else []
    order += [name for name in available if name != author and name not in order]
    order += [name for name in available if name not in order]
    return order


def author_of(note, config=None) -> str | None:
    """Which reviewer host wrote the claim, read off the flip to `supported`.

    The reviewer avoids the author. `--author` says who that is; when nothing
    does, the post that moved the note to `supported` is signed by the CLI
    that was running, and that is the answer. Only a name the host table knows
    counts — `human`, `cli` and a hand-edited signature are nobody's vendor.
    """
    if note is None:
        return None
    who = None
    for post in note.posts:
        if post.is_transition and post.dst == "supported":
            who = post.host
    if not who:
        return None
    key = host_table.resolve(who)
    return key if key in catalog(config) else None


def _note(root, slug: str):
    try:
        return threads.read_note(_note_path(root, slug))
    except (OSError, ValueError):
        return None


def build_prompt(root, slug: str) -> str:
    return PROMPT.format(root=Path(root).resolve(), slug=slug)


def timeout_for(root, slug: str, base: int = TIMEOUT) -> int:
    """How long to wait for a review of this claim.

    Scaled by what the reviewer has to read: the bytes under `derivation:` and
    `evidence:`. A flat ceiling was measured too short for a strong model on a
    long derivation, and a flat ceiling long enough for that one makes every
    hung CLI cost ten minutes. So the ceiling grows with the reading.
    """
    note = _note(root, slug)
    if note is None:
        return base
    try:
        from .state import _link_index, _resolve
    except Exception:  # noqa: BLE001
        return base
    links = _link_index(root)
    total = 0
    for field in ("derivation", "evidence"):
        for link in threads.as_list(note.frontmatter.get(field)):
            target = _resolve(root, str(link), links)
            if target is None or not target.is_file():
                continue
            try:
                total += target.stat().st_size
            except OSError:
                continue
    if total > _VERY_LONG_BYTES:
        return base + 600
    if total > _LONG_BYTES:
        return base + 300
    return base


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


def sections(text: str) -> dict:
    """`{"REASON": ..., "CHECKED": ..., "ASSUMPTION": ...}` from a reply.

    Each section runs from its label to the next label or the end, whatever
    order the model wrote them in. Missing ones are absent, not empty strings,
    so a caller can tell "the reviewer said nothing here" from "it said
    nothing worth keeping".
    """
    found = list(_SECTION_RE.finditer(text or ""))
    out: dict = {}
    for index, match in enumerate(found):
        label = match.group(1).upper()
        end = found[index + 1].start() if index + 1 < len(found) else len(text)
        body = text[match.end():end]
        # A verdict line inside a section is the next answer, not this
        # section's text — models sometimes restate the verdict at the end.
        cut = _VERDICT_RE.search(body)
        if cut:
            body = body[:cut.start()]
        if label not in out:
            out[label] = " ".join(body.split())
    return out


def parse_verdict(text: str) -> tuple:
    """`(verdict, reason)` from a reviewer's answer.

    An answer nobody can parse is `unclear`, not a crash and not a pass. A
    reviewer that rambled has told us it could not answer in the required form,
    and treating that as approval is how a broken adapter becomes a rubber
    stamp.
    """
    verdict, parts = parse_reply(text)
    return verdict, parts.get("REASON", "")


def parse_reply(text: str) -> tuple:
    """`(verdict, {"REASON": ..., "CHECKED": ..., "ASSUMPTION": ...})`.

    The reason carries the parser's own sentence when the reply could not be
    read — that is what gets posted, and a post has to say why it is empty.
    """
    # Anything before the last `--- SESSIONS ---`-style echo of our own words
    # is not the reviewer talking. Hosts that print the instruction back
    # (codex does) otherwise hand us a verdict we wrote ourselves.
    text = _after_echo(text or "")
    said = {m.group(1).lower() for m in _VERDICT_RE.finditer(text)}
    parts = sections(text)
    trimmed = {}
    if parts.get("REASON"):
        trimmed["REASON"] = _trim(parts["REASON"])
    for label in ("CHECKED", "ASSUMPTION"):
        if parts.get(label):
            trimmed[label] = _trim(parts[label], SECTION_CHARS)

    if len(said) == 1:
        return said.pop(), trimmed
    if len(said) > 1:
        # Two different verdicts in one reply. There is no rule for picking
        # the "real" one that does not sometimes pick a `stands` the reviewer
        # went on to withdraw, so the honest answer is that we cannot tell.
        trimmed["REASON"] = ("the reviewer gave more than one verdict "
                             f"({', '.join(sorted(said))}); its reply is quoted below")
        return VERDICT_UNCLEAR, trimmed
    trimmed["REASON"] = trimmed.get("REASON") or (
        "the reviewer did not answer in the required form; its reply is quoted below")
    return VERDICT_UNCLEAR, trimmed


def plan(host: str, model=None, effort=None, settings: "Settings | None" = None,
         config=None) -> tuple:
    """`(entry, model, effort)` — what this call will actually ask for.

    The chain has four links and only the record can walk it: `--model`, then
    the host record, then `research.review_model`, then the record's strong
    tier. Call sites used to write `model or settings.model`, which merges the
    first and third and leaves nowhere for the other two.
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
    picked = entry.pick_model(model or "", (settings.model if settings else "") or "")
    return (entry, picked,
            entry.pick_effort(effort or "", (settings.effort if settings else "") or "",
                              model=picked))


def _host_os_name() -> str:
    """`os.name`, read through a seam a test can replace.

    Faking Windows by setting `os.name` itself makes `pathlib.Path`
    uninstantiable everywhere else on a POSIX machine, and pytest builds a
    `Path` while formatting a failure — so one failed assertion inside such a
    test aborts the whole session with an INTERNALERROR instead of reporting
    the one case. It happened: the guard below raised `NotImplementedError`
    where the test expected `RuntimeError`, and the Linux and macOS runs died
    on the spot with a thousand tests unrun. Patch this and the platform is
    fake for the guard and for nothing else.
    """
    return os.name


def _refuse_truncating_wrapper(argv: list[str]) -> None:
    """A batch wrapper silently keeps the first line of a multiline argument.

    Windows runs `.cmd`/`.bat` through the command processor, which ends an
    argument at the newline. Measured, not reasoned: a wrapper echoing its
    first argument given "line one\\nline two\\nline three" prints
    `ARG1=[line one]` and exits 0. So a host installed by npm — `gemini.CMD`,
    `opencode.CMD`, and Claude Code or Codex too if installed that way — would
    be asked to review one line of a prompt and answer confidently about it,
    with nothing anywhere reporting a problem.

    Raising is the fix this can honestly make. Feeding the prompt on stdin is
    the real one, and it has to be settled per host — each vendor's headless
    flag reads its prompt differently, and guessing would trade a loud failure
    for a quiet one again.
    """
    if _host_os_name() != "nt" or not argv:
        return
    if not argv[0].lower().endswith((".cmd", ".bat")):
        return
    if not any("\n" in str(a) for a in argv[1:]):
        return
    raise RuntimeError(
        # Windows semantics are already established by the guard above, so say
        # so: `Path` on POSIX reads `C:\npm\claude.CMD` as one long filename.
        f"{PureWindowsPath(argv[0]).name} is a batch wrapper, and Windows "
        "would cut the prompt at its first line without saying so. Install "
        "this host as a real executable (its native installer rather than "
        "npm), or review with a host that is one — "
        "`magi review --host <other>`.")


def ask(host: str, prompt: str, cwd, model: str | None = None,
        timeout: int = TIMEOUT, effort: str | None = None,
        settings: "Settings | None" = None, allow_run: bool = False) -> str:
    """Run one headless review. Returns the reply, or raises."""
    entry, model, effort = plan(host, model, effort, settings)
    argv = entry.headless(prompt, model, effort, allow_run=allow_run)
    # The path `which` found, not the bare name. On Windows `CreateProcess`
    # completes `.exe` and nothing else, so an npm-installed host — `gemini`
    # is `gemini.CMD` — was never actually run: every review failed with
    # FileNotFoundError and the claim stayed on the list forever.
    found = shutil.which(argv[0])
    if found:
        argv = [found] + argv[1:]
    _refuse_truncating_wrapper(argv)
    proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    if proc.returncode != 0 and not (proc.stdout or "").strip():
        raise RuntimeError(f"{host} exited {proc.returncode}: "
                           f"{(proc.stderr or '').strip()[-300:]}")
    return proc.stdout or ""


def _brief(exc: BaseException) -> str:
    """One line on why a host did not answer, fit for a post."""
    said = " ".join(str(exc).split())
    name = exc.__class__.__name__
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"timed out after {int(exc.timeout)}s"
    return f"{name}: {said[:160]}" if said else name


def review(root, slug: str, author: str | None = None, host: str | None = None,
           model: str | None = None, timeout: int | None = None,
           effort: str | None = None, settings: "Settings | None" = None,
           skip=(), allow_run: bool = False) -> Verdict:
    """Ask another CLI whether one proposition holds.

    Every call is written into the ledger whether it worked or not: a review
    that timed out spent the wall clock and, on a metered account, the money.

    A host that fails to answer is not the end of the review. A vendor's own
    quota, a timeout, a crashed process — each is a reason to ask the next
    installed CLI, not a reason to leave the claim unread: on the day this was
    added four reviews in a row failed on one vendor's quota while two other
    CLIs sat installed and idle. The verdict records who was asked first and
    why they did not answer, so a same-vendor fallback reads as what it is.
    """
    config = settings.config if settings else None
    if author is None:
        author = author_of(_note(root, slug), config)
    if timeout is None:
        timeout = timeout_for(root, slug)
    order = reviewers(author, configured=host, config=config, skip=skip)
    if not order:
        raise RuntimeError("no reviewer CLI on PATH "
                           f"(looked for {', '.join(host_names(config))})")
    # Here, not in the caller. Every path that spends checks the switch itself,
    # so a batch cannot run sixty calls behind one check at its top.
    ledger.check(root, enabled=(settings.enabled if settings else True))
    prompt = build_prompt(root, slug)
    failures: list = []
    for index, chosen in enumerate(order):
        # `--model` names a model on the host it was written for; `opus` means
        # nothing to agy. A fallback host walks its own chain instead. Effort
        # words are the same on every host and travel.
        asked_model = model if index == 0 else None
        # Resolved once, here, so the ledger records what was asked for rather
        # than what was typed. With nothing typed this is the strong tier, and
        # a ledger entry saying `model: null` for it could not tell a Haiku
        # review from an Opus one afterwards.
        entry, picked, level = plan(chosen, asked_model, effort, settings)
        tier = entry.tier_of(picked)
        started = time.monotonic()
        try:
            reply = ask(chosen, prompt, cwd=root, model=picked, timeout=timeout,
                        effort=level, settings=settings, allow_run=allow_run)
        except (KeyboardInterrupt, SystemExit):
            _spend(root, chosen, slug, picked, ok=False, since=started,
                   note="interrupted", effort=level, tier=tier)
            raise
        except Exception as exc:  # noqa: BLE001 - recorded, then the next host
            _spend(root, chosen, slug, picked, ok=False, since=started,
                   note=exc.__class__.__name__, effort=level, tier=tier)
            failures.append((chosen, _brief(exc)))
            continue
        _spend(root, chosen, slug, picked, ok=True, since=started, effort=level,
               tier=tier)
        verdict, parts = parse_reply(reply)
        return Verdict(slug=slug, verdict=verdict, reason=parts.get("REASON", ""),
                       host=chosen, raw=reply, model=picked, effort=level, tier=tier,
                       checked=parts.get("CHECKED", ""),
                       assumption=parts.get("ASSUMPTION", ""),
                       fell_back=failures)
    raise RuntimeError("no reviewer answered — "
                       + "; ".join(f"{name}: {why}" for name, why in failures))


def _spend(root, host, slug, model, *, ok, since, note="", effort=None,
           tier=None) -> None:
    """Record one call. Never the reason a review fails."""
    try:
        ledger.record(root, ledger.REVIEW, host, model=model, effort=effort,
                      slug=slug, ok=ok, seconds=time.monotonic() - since, note=note,
                      tier=tier)
    except OSError:
        pass


def signature(result: Verdict) -> str:
    """The line under a verdict saying who answered and on what.

    Host, model, effort and tier, in that order, because that is the order a
    reader weighs them in. `weakly_reviewed` reads the tier back off this line
    — the post is the record, and a verdict whose tier is not in the post is a
    verdict nobody can later weigh.
    """
    parts = [f"reviewed headless by {result.host}"]
    parts.append(f"model {result.model}" if result.model else "its default model")
    if result.effort:
        parts.append(f"effort {result.effort}")
    if result.tier:
        parts.append(f"{result.tier} tier")
    text = " · ".join(parts)
    if result.fell_back:
        text += "; " + ", ".join(f"{name} was asked first and failed ({why})"
                                 for name, why in result.fell_back)
    return text


def apply_verdict(root, result: Verdict) -> str:
    """Write the verdict into the note. Returns a line for the report.

    A rejection lands as `disputed` and stops there. It is not `refuted` —
    the reviewer's disagreement is not a finding — and nothing walks it back
    to `supported` without a person, which is what `vocab` means by that
    transition being a human's call.

    A `restate` lands as `testing`. The reviewer has said the conclusion holds
    and the words do not, and that is the author's to fix: they change the
    statement or the derivation as the post says, move the note back to
    `supported`, and the next review reads the new words. Nothing on this
    path touches a person — five of five human interruptions on the day this
    was added were for exactly this, a claim the reviewer agreed with and
    would have phrased differently.
    """
    if not result.ran:
        # Nothing is written. A note that carries a reviewer's post is a note
        # `pending()` stops offering, so posting "the review could not run"
        # would retire the claim on the strength of a review that never
        # happened — the exact rubber stamp this command exists to avoid.
        return f"{result.slug}: not reviewed — {result.error}"

    path = _note_path(root, result.slug)
    body = result.reason
    if result.checked:
        body += f"\n\nChecked: {result.checked}"
    if result.assumption:
        body += f"\n\nLoad-bearing: {result.assumption}"
    body += f"\n\n({signature(result)})"
    if result.verdict == VERDICT_UNCLEAR and _needs_evidence(result):
        # The fallback reason promises the reply is here. Without it a reader
        # cannot tell a broken adapter from a genuinely undecidable claim,
        # which is the one thing they need to know to act on an `unclear`.
        body += "\n\nWhat it actually said:\n\n" + _excerpt(result.raw)
    posted = f"VERDICT: {result.verdict}\n\n{body}"

    if result.verdict in (VERDICT_STANDS, VERDICT_UNCLEAR):
        threads.append_post(path, posted, host=vocab.REVIEWER)
        return f"{result.slug}: {result.verdict}"

    note = threads.read_note(path)

    if result.restated:
        if note.status == "supported":
            threads.set_status(path, "testing", posted, host=vocab.REVIEWER)
            return (f"{result.slug}: restate — back to testing. Change the statement "
                    f"or the derivation as the post says, then `magi thread status "
                    f"{result.slug} supported --text '<what changed>'` and it is "
                    "reviewed again. Nobody needs to be asked.")
        threads.append_post(path, posted, host=vocab.REVIEWER)
        return (f"{result.slug}: restate — left at `{note.status}`; the post says "
                "what to change")

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
    reviewer might leave behind — an `unclear`, a `restate`, a note about a
    failed run — is a post, not an answer.

    Only the **first line** counts. An `unclear` post quotes the reviewer's
    own words underneath, and a reply that argued both sides would otherwise
    clear the claim on the strength of the word `stands` appearing inside the
    quotation.
    """
    if post.host != vocab.REVIEWER:
        return False
    first = (post.text or "").lstrip().splitlines()
    return bool(first) and bool(_ANSWER_RE.match(first[0]))


def _is_restate(post) -> bool:
    if post.host != vocab.REVIEWER:
        return False
    first = (post.text or "").lstrip().splitlines()
    return bool(first) and bool(_RESTATE_RE.match(first[0]))


def tier_of_post(post) -> str:
    """Which tier answered in this post, or "" for a post that does not say."""
    found = _TIER_RE.search(post.text or "")
    return found.group(1) if found else ""


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
                 model: str | None = None, timeout: int | None = None,
                 effort: str | None = None, settings: "Settings | None" = None,
                 allow_run: bool = False) -> list:
    """Review several propositions. One failure does not stop the rest.

    The master switch is the one thing that does. It stops the loop, and the
    shorter list of results is how the caller learns that — every slug after
    the last result is untouched and still unreviewed, which is the honest
    outcome.

    A host that failed to answer one claim is not asked about the next: the
    timeout is five minutes, and a batch of twelve behind a dead CLI would
    spend an hour learning the same thing twelve times.
    """
    out = []
    dead: set = set()
    for slug in slugs:
        try:
            result = review(root, slug, author=author, host=host, model=model,
                            timeout=timeout, effort=effort, settings=settings,
                            skip=dead, allow_run=allow_run)
        except ledger.SwitchedOff:
            # Before the `RuntimeError` clause, which it subclasses. Nothing
            # reaches the notes either way — `apply_verdict` refuses to post a
            # review that never happened — but falling through returns one
            # identical "switched off" result per remaining claim, and then
            # the count of results still matches the count of slugs, so
            # nothing downstream can tell a run that stopped early from one
            # that finished. Stopping is what makes the short list mean
            # something.
            break
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            out.append(Verdict(slug=slug, verdict=VERDICT_UNCLEAR, host=host or "?",
                               reason=f"the review could not run ({exc})",
                               error=str(exc) or exc.__class__.__name__))
            continue
        dead.update(name for name, _why in result.fell_back)
        out.append(result)
    return out


def _notes(root, notes):
    # `notes` when the caller has them. `state.close` runs inside the Stop
    # hook with the whole projection already in memory, and this used to open
    # and re-parse every file in `threads/` to answer a question about notes
    # it was holding — a second reader of the same files, which `rules.check`
    # calls "a second answer waiting to disagree".
    if notes is not None:
        return notes
    return (threads.read_note(p) for p in threads.note_paths(root))


def _last_claim(note) -> int:
    """Index of the last flip to `supported`, or -1."""
    last = -1
    for index, post in enumerate(note.posts):
        if post.is_transition and post.dst == "supported":
            last = index
    return last


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
    for note in _notes(root, notes):
        if note.kind != vocab.PROPOSITION or note.status != "supported":
            continue
        reviewed = any(_is_answer(post)
                       for post in note.posts[_last_claim(note) + 1:])
        if not reviewed:
            out.append(note.slug)
    return out


def weakly_reviewed(root, notes=None) -> list:
    """Supported propositions whose only answers came from the cheap tier.

    Not on `pending()`: a cheap-tier verdict is a review that happened, and
    treating it as none would re-spend a call on every one of them at once.
    Listed separately so `magi next` can offer a strong reader and a person
    can see which of their "reviewed" claims were read by the model that,
    measured, missed four substantive errors in twelve verdicts.

    A post that does not name its tier — every review from before tiers were
    written into posts — is not counted as weak. Putting a library's whole
    history on this list on the day the feature shipped would be noise, and
    noise is how a list stops being read.
    """
    out = []
    for note in _notes(root, notes):
        if note.kind != vocab.PROPOSITION or note.status != "supported":
            continue
        answers = [post for post in note.posts[_last_claim(note) + 1:]
                   if _is_answer(post)]
        if answers and all(tier_of_post(post) == "cheap" for post in answers):
            out.append(note.slug)
    return out


def restating(root, notes=None) -> list:
    """Propositions a reviewer sent back for restating, still waiting on the author.

    The `restate` verdict flips `supported → testing` and its post is the last
    word until the author acts. Once anybody posts after it or moves the note,
    the claim is ordinary open work again and `magi next` routes it as such.
    """
    out = []
    for note in _notes(root, notes):
        if note.kind != vocab.PROPOSITION or note.status != "testing":
            continue
        if not note.posts:
            continue
        last = note.posts[-1]
        if last.is_transition and last.dst == "testing" and _is_restate(last):
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
        enabled=bool(config_get(config, "research.llm_calls", True)),
        host=(config_get(config, "research.review_host", "") or None),
        model=(config_get(config, "research.review_model", "") or None),
        effort=(config_get(config, "research.review_effort", "") or None),
        config=config)


def describe(host: str, model: str, effort: str, tier: str = "") -> str:
    """`claude (opus, effort high; strong tier)` — one call, for a person."""
    inner = model or "its own default"
    if effort:
        inner += f", effort {effort}"
    if tier:
        inner += f"; {tier} tier"
    return f"{host} ({inner})"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi review",
        description="Have another agent CLI check a claim that says it is solved.")
    parser.add_argument("slug", nargs="*",
                        help="Propositions to review (default: everything unreviewed)")
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir", help="Project directory (default: discovered from cwd)")
    # No `choices=` on purpose. The table depends on `research.hosts`, and the
    # workspace it comes from is not known until `--topic-dir` has been parsed
    # — so `choices=` could only ever list the built-in five, and rejected the
    # host a person had declared themselves before anything read their config.
    # Checked below instead, where the message can name their host.
    parser.add_argument("--host",
                        help="Reviewer CLI (default: any installed one that is not "
                             "the claim's author; the others are fallbacks)")
    parser.add_argument("--author",
                        help="The CLI that wrote the claim; the reviewer avoids it "
                             "(default: read off the post that claimed it solved)")
    parser.add_argument("--model", help="Pin the reviewer's model (default: this host's "
                                        "strong tier — the one that reads)")
    parser.add_argument("--effort", choices=host_table.EFFORTS,
                        help="Reasoning level, where the host takes one")
    parser.add_argument("--allow-run", action="store_true",
                        help="Let the reviewer execute scripts the derivation names, "
                             "where the host has a way to allow that")
    parser.add_argument("--timeout", type=int, default=None,
                        help=f"Seconds to wait for one review (default {TIMEOUT}, "
                             "more when the derivation and evidence are long)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Say who would be asked about what, and stop.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        print("no project found (run inside one, or pass --project-dir)", file=sys.stderr)
        return 1

    settings = _config(root)
    enabled = settings.enabled
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
    entry, model, effort = plan(chosen, args.model, args.effort, settings)
    tier = entry.tier_of(model)
    if args.allow_run and not entry.can_run:
        print(f"note: {chosen} has no way to let a headless call run code; the "
              "reviewer reads only, and `--allow-run` changes nothing here.",
              file=sys.stderr)

    if args.dry_run:
        # Per claim, because the author is read off each note and the pick
        # avoids the author. One headline is fine when they all agree, and
        # wrong when they do not.
        plans = []
        for slug in slugs:
            author = args.author or author_of(_note(root, slug), settings.config)
            order = reviewers(author, configured=wanted_host, config=settings.config)
            first = order[0] if order else chosen
            entry_s, model_s, effort_s = plan(first, args.model if first == chosen else None,
                                              args.effort, settings)
            plans.append({"slug": slug, "host": first, "model": model_s or None,
                          "effort": effort_s or None, "tier": entry_s.tier_of(model_s),
                          "author": author, "fallbacks": order[1:]})
        payload = {"host": chosen, "model": model or None, "effort": effort or None,
                   "tier": tier, "slugs": slugs, "plans": plans,
                   "spending": ledger.summary(root)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            # One headline when every claim gets the same reviewer — which is
            # the per-claim answer, not the author-blind pick above. The first
            # version printed the blind pick and then contradicted it one line
            # down for every claim whose author it had just read.
            keys = {(p["host"], p["model"], p["effort"], p["tier"]) for p in plans}
            if len(keys) == 1:
                one = plans[0]
                who = f" (its author is {one['author']})" if one["author"] else ""
                print(f"would ask {describe(one['host'], one['model'] or '', one['effort'] or '', one['tier'])}"
                      f" about: {', '.join(slugs)}{who}")
            else:
                print("would ask, per claim:")
                for item in plans:
                    who = f" — its author is {item['author']}" if item["author"] else ""
                    print(f"  {item['slug']}: {describe(item['host'], item['model'] or '', item['effort'] or '', item['tier'])}{who}")
            if plans and plans[0]["fallbacks"]:
                print(f"  if that fails: {', '.join(plans[0]['fallbacks'])}")
        return 0

    # Before the subprocess, not after: a switch that stops the call but lets
    # the claim retire unreviewed would spend nothing and approve everything.
    try:
        ledger.check(root, enabled=enabled)
    except ledger.SwitchedOff as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Also before the subprocess: evidence the reviewer cannot open. Said now,
    # because the review will run and come back `unclear` after minutes and
    # money, and the note's author is the one reading this line.
    try:
        from .state import evidence_outside

        for slug in slugs:
            for why in evidence_outside(root, _note(root, slug)):
                print(f"warning: {slug}: {why}", file=sys.stderr)
    except Exception:  # noqa: BLE001 - a warning must not stop the review
        pass

    results = review_batch(root, slugs, author=args.author,
                           host=wanted_host, model=args.model,
                           timeout=args.timeout, effort=args.effort,
                           settings=settings, allow_run=args.allow_run)
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
        for result, line in zip(results, lines):
            print(f"  {line}")
            if result.ran:
                print(f"    ({signature(result)})")
        # Said at the moment it is spent. `MAP.md` carries this too, but it is
        # DERIVED and only rewritten at session close — so between a review and
        # the next `sync --close` the one surface a person would check still
        # shows the old number. Failed calls are in the count: a timeout spent
        # the wall clock and, on a metered account, the money.
        if results:
            spend = ledger.summary(root)
            failed = f", {spend['failed']} failed" if spend.get("failed") else ""
            print(f"  ({spend['spent']} model calls this week{failed})")

    # A short list is the only sign the switch stopped the run, so it is said
    # out loud rather than left for somebody to notice by counting.
    if len(results) < len(slugs):
        left = slugs[len(results):]
        try:
            ledger.check(root, enabled=enabled)
            why = "the run stopped early"
        except ledger.SwitchedOff as exc:
            why = str(exc)
        print(f"stopped after {len(results)} of {len(slugs)} — {why}\n"
              f"still unreviewed: {', '.join(left)}", file=sys.stderr)
        return 1
    # A run where nothing could be asked is a failure, not a quiet success.
    # Exiting 0 there is how a broken install looks like a reviewed library.
    # `error` is in the condition because a verdict that came back and could
    # not be written is the same thing from the caller's side: the call was
    # spent and the claim is no better off than before. `refused` is in it
    # because a name that was dropped is a claim nobody looked at. `restated`
    # is in it because the claim now needs its author.
    return 1 if refused or any(r.rejected or r.restated or not r.ran or r.error
                               for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
