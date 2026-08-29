"""`magi reflect` — the pass that reads the sessions and writes down patterns.

This is the first of the slow loop's two stages (design-v2 §12). It looks at
what MAGI already knows went wrong or right, picks the sessions those things
happened in, and asks one model to say what keeps happening. What comes back
lands in `output/reflect/patterns/` — not as proposals, and not in anything the
working agent reads.

Three restraints are structural rather than stylistic:

**One call per pass.** Eight excerpts in one prompt rather than eight prompts,
because a pattern is a thing that repeats and a reader who sees one session at
a time cannot notice repetition. It also costs one call instead of eight, and
the budget is counted in calls.

**The model may only name sessions it was given.** The ≥2-independent-sessions
gate is the loop's only defence against turning one bad afternoon into a
permanent rule, and a model that could invent a second sighting could walk
straight through it.

**Nothing is proposed here.** A pattern page is an observation. Whether it
should change anything is the second stage's question, and keeping them apart
is what lets the first sighting sit on disk until a second one arrives.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..core import ledger
from ..core.workspace import find_workspace_root
from . import patterns, signals, transcripts

#: Long enough to read eight excerpts and think; short enough that a hung CLI
#: does not hold a terminal all afternoon.
TIMEOUT = 900

PROMPT = """You are reading sessions from one research workspace to find what keeps
going wrong, and what keeps going right.

MAGI already knows *that* these things happened — the events are listed under each
session. What it cannot see is why. That is what you are for.

Write down PATTERNS: things that recur, or would recur. Not incidents. "The sweep
at L=24 stalled" is an incident; "sweeps are started before the boundary condition
is checked, and stall" is a pattern.

Rules:
- A pattern must be visible in the sessions below. Quote the words, verbatim.
- Name only sessions from this list: {labels}
- Say which sessions showed it. One session is enough to write it down; it is
  not enough to act on, and that is handled elsewhere.
- Include the good ones. A session where the work went well is the only evidence
  that can support "keep doing it this way", and you are given some on purpose.
- At most {limit} patterns. Fewer is better.

Answer as JSON, one object per line, nothing else:

{{"slug": "kebab-case-name", "title": "one line", "sessions": ["host/id", ...],
 "body": "## What happened\\n\\n...\\n\\n## Why\\n\\n...\\n\\n## Quotes\\n\\n> ...",
 "patch": {{"op": "append|replace|insert_after", "target": "exact substring",
 "text": "what to write"}}}}

`patch` is optional and usually absent — include it only when you can name the
exact text to change and what to change it to. `target` must be a substring that
appears exactly once in what it is patching.

--- SESSIONS ---

{sessions}
"""

#: How many patterns one pass may write. The proposal gate downstream is ≤5;
#: observations are cheaper than proposals, but a pass that returns thirty has
#: stopped distinguishing patterns from incidents.
MAX_PATTERNS = 8


@dataclass
class Report:
    """What one pass did, for a person and for `--json`."""
    sampled: list = field(default_factory=list)      # labels
    signals: int = 0
    #: Set when the pass could not do its job — no host, no budget, switched
    #: off, the call itself failed. Distinct from "ran and found nothing new",
    #: which is a success and the common case.
    failed: bool = False
    written: list = field(default_factory=list)      # slugs
    skipped: list = field(default_factory=list)      # (slug, why)
    unreadable: dict = field(default_factory=dict)   # host -> why
    host: str = ""
    called: bool = False
    note: str = ""


def label(session) -> str:
    return f"{session.host}/{session.session_id}"


def build_prompt(samples, limit: int = MAX_PATTERNS) -> str:
    blocks = []
    for item in samples:
        events = "\n".join(f"  - {signal.kind}: {signal.slug} — {signal.why}"
                           for signal in item.signals)
        blocks.append(
            f"## SESSION {label(item.session)} ({item.kind})\n"
            f"What MAGI recorded around this session:\n{events}\n\n"
            f"{item.session.excerpt()}\n")
    return PROMPT.format(labels=", ".join(label(item.session) for item in samples),
                         limit=limit, sessions="\n\n".join(blocks))


def parse(reply: str, allowed: set, limit: int = MAX_PATTERNS) -> tuple:
    """`(patterns, skipped)` from a model's answer.

    Everything is checked rather than trusted. A line that will not parse is
    skipped, not fatal — the other seven patterns in the reply are still worth
    having, and a pass that throws away a good answer because one line had a
    stray comma is a pass nobody runs twice.
    """
    kept, skipped = [], []
    for line in (reply or "").splitlines():
        line = line.strip().strip("`")
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            skipped.append(("?", "the line is not JSON"))
            continue
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "").strip()
        if not patterns.is_slug(slug):
            skipped.append((slug or "?", "not a slug"))
            continue
        named = [str(item) for item in (row.get("sessions") or [])]
        seen = [item for item in named if item in allowed]
        if not seen:
            # A pattern attributed to no session we handed over is a pattern
            # about something else, and the two-session gate downstream would
            # be counting sightings nobody can check.
            skipped.append((slug, "names no session from this pass"))
            continue
        body = str(row.get("body") or "").strip()
        if not body:
            skipped.append((slug, "no body"))
            continue
        patch = row.get("patch")
        kept.append({
            "slug": slug,
            "title": str(row.get("title") or slug),
            "sessions": seen,
            "body": body,
            "patch": patch if isinstance(patch, dict) else {},
        })
        if len(kept) >= limit:
            break
    return kept, skipped


def ask(host: str, prompt: str, cwd, model=None, timeout: int = TIMEOUT) -> str:
    """One headless call. Shares `review`'s adapters — same hosts, same modes."""
    from .. import review

    return review.ask(host, prompt, cwd=cwd, model=model, timeout=timeout)


def run(root, *, host=None, model=None, timeout: int = TIMEOUT, dry_run: bool = False,
        home=None, now=None) -> Report:
    """One pass. Returns what it did."""
    from .. import review
    from ..state import loaded

    root = Path(root)
    report = Report()

    state = loaded(root)
    found = signals.collect(state)
    report.signals = len(found)

    swept = transcripts.sweep(root, home=home)
    report.unreadable = swept.unreadable
    samples = signals.sample(swept.sessions, found)
    report.sampled = [label(item.session) for item in samples]

    if not samples:
        report.note = ("nothing to read — no recorded event lines up with a session "
                       "in this workspace")
        return report

    settings = review._config(root)
    chosen = review.pick_host(None, configured=host or settings.host)
    report.host = chosen or ""
    if chosen is None:
        report.note = ("no CLI on PATH to read with "
                       f"(looked for {', '.join(review.HOSTS)})")
        report.failed = True
        return report

    if dry_run:
        report.note = f"would ask {chosen} to read {len(samples)} session(s)"
        return report

    try:
        ledger.check(root, limit=settings.limit, enabled=settings.enabled)
    except (ledger.OverBudget, ledger.SwitchedOff) as exc:
        report.note = str(exc)
        report.failed = True
        return report

    prompt = build_prompt(samples)
    started = time.monotonic()
    try:
        reply = ask(chosen, prompt, cwd=root, model=model or settings.model,
                    timeout=timeout)
        ok = True
    except BaseException as exc:  # noqa: BLE001 — recorded, then reported
        reply, ok = "", False
        report.failed = True
        report.note = f"the pass could not run ({exc.__class__.__name__}: {exc})"
    finally:
        ledger.record(root, ledger.REFLECT, chosen, model=model or settings.model,
                      ok=ok, seconds=time.monotonic() - started,
                      note=f"{len(samples)} sessions")
    report.called = True
    if not ok:
        return report

    kept, skipped = parse(reply, allowed=set(report.sampled))
    report.skipped = skipped
    today = now or dt.date.today()
    for row in kept:
        for name in row["sessions"]:
            patterns.observe(root, row["slug"], title=row["title"], body=row["body"],
                             session=name, host=name.split("/", 1)[0],
                             patch=row["patch"], when=today)
        report.written.append(row["slug"])
    return report


def render(report: Report) -> str:
    lines = []
    if report.unreadable:
        for host, why in sorted(report.unreadable.items()):
            lines.append(f"  {host}: could not be read ({why})")
    lines.append(f"  {report.signals} recorded event(s), "
                 f"{len(report.sampled)} session(s) worth reading")
    if report.note:
        lines.append(f"  {report.note}")
    for slug in report.written:
        page = f"output/reflect/patterns/{slug}.md"
        lines.append(f"  wrote {page}")
    for slug, why in report.skipped:
        lines.append(f"  skipped {slug}: {why}")
    return "\n".join(lines)


VERBS = ("read", "propose", "list", "accept", "reject", "promote", "retire")


def _decide(root, verb: str, ident: str, note: str, as_json: bool) -> int:
    """One of the three buttons. The CLI is the only thing that writes a verdict."""
    from . import proposals

    # `retire` is not `reject`. Rejecting says "this was a bad idea", and the
    # next pass is told never to propose it again. Retiring says "this was a
    # good idea and its reason has gone" — the rule comes out, and the same
    # idea may well come back if the pattern does.
    verdicts = {"accept": proposals.ACCEPTED, "reject": proposals.REJECTED,
                "promote": proposals.PROMOTED, "retire": proposals.RETIRED}
    proposal = proposals.get(root, ident)
    if proposal is None:
        print(f"no proposal with id {ident!r} — `magi reflect list` shows them",
              file=sys.stderr)
        return 1

    if verb == "accept" and proposal.kind == proposals.RULE:
        # The block is read at the start of every session on every host, so a
        # rule going in has to be worth what every later session pays to read
        # it. Refusing here rather than truncating at render time: the ledger
        # is the truth, and the block must never say less than the ledger.
        from ..core.config_loader import get as config_get
        from ..core.config_loader import load_config
        from ..core import managed

        raw = config_get(load_config(start=root), "research.rule_budget",
                         managed.RULE_BUDGET)
        try:
            budget = int(raw)
        except (TypeError, ValueError):
            print(f"research.rule_budget is {raw!r}, which is not a number of "
                  "lines — fix config.yaml", file=sys.stderr)
            return 1
        live = [p for p in proposals.live_rules(root) if p.id != ident]
        if len(live) >= budget:
            if not live:
                # A budget of zero. Not a mistake to route around: somebody set
                # it, and it means this workspace does not want earned rules.
                print(f"research.rule_budget is {budget} — this workspace takes "
                      "no earned rules. Raise it, or leave this as prose.",
                      file=sys.stderr)
                return 1
            oldest = live[0]
            print(f"the rule section is full ({len(live)}/{budget}). Retire one "
                  f"first — the oldest is {oldest.id}: {oldest.text}",
                  file=sys.stderr)
            return 1

    made = ""
    if verb in ("reject", "retire") and proposal.verdict == proposals.PROMOTED:
        # Turning down something already promoted is how a rule is retired:
        # the instance comes out of `config.yaml` and stops being checked.
        try:
            _retire_rule(root, ident)
        except OSError as exc:
            print(f"the rule could not be removed ({exc})", file=sys.stderr)
            return 1

    if verb == "accept" and proposal.kind == proposals.SKILL:
        try:
            made = _apply_to_skill(root, proposal)
        except _PackageLevel as exc:
            # MAGI does not edit its own package: the change would be lost at
            # the next upgrade, and it would be made to a file every workspace
            # on this machine shares, on one library's evidence.
            made = str(exc)
        except (ValueError, OSError) as exc:
            print(f"the skill could not be patched ({exc})", file=sys.stderr)
            return 1

    if verb == "accept" and proposal.kind == proposals.FACT:
        # A fact goes where a person's own unfiled thought goes. `magi next`
        # already routes that to one of the five writing surfaces, and it does
        # it by reading the library — which the slow loop has not.
        from ..state import dump

        dump(root, f"{proposal.text}  (from the slow loop, "
                   f"pattern {proposal.pattern})")
        made = "inbox/notes.md"

    if verb == "promote":
        # The prose comes out of the block and something that runs goes in.
        # Only what fits the closed vocabulary can: a promotion that produced a
        # file somebody might write a check into one day would leave the ledger
        # saying `promoted` while nothing checks anything.
        from ..core import rules as rules_mod

        rule = rules_mod.from_proposal(proposal)
        if rule is None:
            print(f"{ident} cannot be promoted: it does not name one of "
                  f"{', '.join(rules_mod.VOCABULARY)}. Leave it as a rule, or "
                  "propose adding a predicate for it.", file=sys.stderr)
            return 1
        try:
            made = _add_rule(root, rule)
        except OSError as exc:
            print(f"the rule could not be written ({exc})", file=sys.stderr)
            return 1

    proposals.decide(root, ident, verdicts[verb], note=note)
    # Whoever changed the ledger re-renders, rather than waiting for the next
    # install: the block and the ledger disagreeing is the one state neither
    # of them can be read in.
    written = _rerender(root)
    if as_json:
        print(json.dumps({"id": ident, "verdict": verdicts[verb], "note": note,
                          "rendered": written, "check": made}, ensure_ascii=False))
    else:
        print(f"{ident}: {verdicts[verb]}" + (f" — {written}" if written else ""))
        if made == "inbox/notes.md":
            print("  filed into inbox/notes.md — `magi next` puts it where it goes")
        elif made:
            print(f"  {made}")
    return 0


class _PackageLevel(Exception):
    """The target is a skill MAGI ships. Recorded, not applied."""


def _apply_to_skill(root, proposal) -> str:
    """Patch the person's own copy of a skill, or say it is package-level.

    The patch has to name what comes out as well as what goes in. A loop that
    only appends makes every skill longer every week, and a skill is loaded
    into a context window on every session that uses it — length is a tax, and
    the ratchet that keeps it at forty lines is the same argument.
    """
    from .. import skills_cmd
    from . import patterns as pattern_pages

    name = str(proposal.target or "").strip().split("/")[-1].replace(".md", "")
    mine = skills_cmd.user_skills_dir() / name / "SKILL.md"
    if not mine.is_file():
        raise _PackageLevel(
            f"{name} is a skill MAGI ships — the change is recorded in the "
            "ledger and belongs upstream, not in this workspace")

    patch = proposal.patch or {}
    if not patch.get("text") or not patch.get("target"):
        raise ValueError("a skill change has to name what goes in and what "
                         "comes out")
    current = mine.read_text(encoding="utf-8")
    updated = pattern_pages.apply_patch(current, patch)
    mine.write_text(updated, encoding="utf-8", newline="\n")
    return (f"patched {mine} — run `magi install` to put it back into your "
            "agent CLIs")


def _add_rule(root, rule) -> str:
    """Append one rule instance to `config.yaml`. Returns what to tell a person.

    Appended rather than replacing the list, because the list is a person's
    file: they may have written rules by hand, and a promotion is not a reason
    to lose them.
    """
    from ..core import rules as rules_mod
    from ..core.config_edit import set_config_value
    from ..core.config_loader import get as config_get
    from ..core.config_loader import load_config

    current = config_get(load_config(start=root), "research.rules", []) or []
    entry = rules_mod.to_entry(rule)
    if entry in current:
        return f"{rule.describe()} was already in config.yaml"
    set_config_value(Path(root) / "config.yaml", "research.rules",
                     list(current) + [entry])
    return f"{rule.describe()} — `magi lint` and `sync --close` check it now"


def _retire_rule(root, proposal_id: str) -> None:
    """Take a promoted rule back out. Rejecting a promotion means this."""
    from ..core.config_edit import set_config_value
    from ..core.config_loader import get as config_get
    from ..core.config_loader import load_config

    current = config_get(load_config(start=root), "research.rules", []) or []
    kept = [entry for entry in current
            if not (isinstance(entry, dict) and entry.get("from") == proposal_id)]
    if len(kept) != len(current):
        set_config_value(Path(root) / "config.yaml", "research.rules", kept)


def _rerender(root) -> str:
    """Rewrite the managed block from template + ledger. Returns a note."""
    try:
        from .. import install_cmd

        return install_cmd.install_protocol(Path(root))
    except Exception as exc:  # noqa: BLE001
        return f"the block could not be rewritten ({exc})"


def _list(root, as_json: bool) -> int:
    from . import proposals

    rows = proposals.open_proposals(root)
    if as_json:
        print(json.dumps([{"id": p.id, "kind": p.kind, "target": p.target,
                           "text": p.text, "pattern": p.pattern, "hosts": p.hosts}
                          for p in rows], ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("nothing waiting. `magi reflect` reads the sessions; "
              "`magi reflect propose` turns what recurred into proposals.")
        return 0
    for proposal in rows:
        print(f"  {proposal.id}  [{proposal.kind}] {proposal.target}")
        print(f"      {proposal.text}")
        print(f"      from {proposal.pattern} "
              f"({', '.join(proposal.hosts) or 'unknown host'})")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="magi reflect",
        description="Read the sessions where something happened, write down what "
                    "keeps happening, and decide what to do about it.")
    parser.add_argument("verb", nargs="?", default="read", choices=VERBS,
                        help="read (default) | propose | list | accept | reject "
                             "| promote | retire")
    parser.add_argument("id", nargs="?",
                        help="Proposal id, for accept/reject/promote/retire")
    parser.add_argument("--note", default="", help="What you said when deciding")
    parser.add_argument("--topic-dir", help="Workspace (default: discovered from cwd)")
    parser.add_argument("--host", help="Which CLI reads (default: config, then PATH)")
    parser.add_argument("--model", help="Pin the reader's model")
    parser.add_argument("--timeout", type=int, default=TIMEOUT)
    parser.add_argument("--dry-run", action="store_true",
                        help="Say what would be read, and stop.")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.topic_dir).resolve() if args.topic_dir else find_workspace_root()
    if root is None:
        print("no workspace found (run inside a topic or pass --topic-dir)",
              file=sys.stderr)
        return 1

    if args.verb in ("accept", "reject", "promote", "retire"):
        if not args.id:
            print(f"{args.verb} needs a proposal id — `magi reflect list` shows them",
                  file=sys.stderr)
            return 1
        return _decide(root, args.verb, args.id, args.note, args.json)

    if args.verb == "list":
        return _list(root, args.json)

    if args.verb == "propose":
        from . import propose as stage_two

        report = stage_two.run(root, host=args.host, model=args.model,
                               timeout=args.timeout, dry_run=args.dry_run)
        if args.json:
            print(json.dumps({"considered": report.considered, "made": report.made,
                              "skipped": report.skipped, "host": report.host,
                              "called": report.called, "note": report.note},
                             ensure_ascii=False, indent=2))
        else:
            print(stage_two.render(report))
        return 1 if report.failed else 0

    report = run(root, host=args.host, model=args.model, timeout=args.timeout,
                 dry_run=args.dry_run)
    if args.json:
        print(json.dumps({
            "sampled": report.sampled, "signals": report.signals,
            "written": report.written, "skipped": report.skipped,
            "unreadable": report.unreadable, "host": report.host,
            "called": report.called, "note": report.note,
        }, ensure_ascii=False, indent=2))
    else:
        print(render(report))
        # Stage two is a second model call. Saying so beats spending it.
        from . import patterns as pages

        ready = pages.ready(root)
        if ready:
            print(f"  {len(ready)} observation(s) have recurred — "
                  "`magi reflect propose` turns them into proposals")
    # A pass that could not run is a failure; a pass that ran and found nothing
    # new is not. The distinction is `failed`, because "nothing to read" and
    # "switched off" both leave a note and only one of them is a problem.
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
