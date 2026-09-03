"""The slow loop's second stage: from patterns that recurred to proposals.

The first stage wrote down what keeps happening. This one asks what should
change about it — and almost everything here is a restraint on that question,
because a loop that can propose freely will propose constantly.

**Only patterns that recurred.** Two independent sessions, still current. One
bad afternoon is not evidence, and the gate is a query against files rather
than a sentence in a prompt (`patterns.ready`).

**One target per proposal.** A proposal that changes three things is three
proposals a person has to accept or reject together, which means they will
reject it or accept parts of it by hand — and either way the ledger stops
describing what actually happened.

**What was rejected comes back into the prompt, in full.** Being told no is the
loop's most useful input: it is the one place a person said what they actually
want. Hiding it would make the loop propose the same thing every week.

**Where a fix may land depends on where the problem was seen.** A pattern that
showed up on one host is that host's problem — putting its workaround in the
shared layer makes the other three read it every session for nothing
(design-v2 §12).
"""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..core import ledger
from . import patterns, proposals
from .cmd import ask

#: How many proposals one pass may make. From the design: a person can weigh
#: five things in a week. Six is a backlog, and a backlog is ignored.
MAX_PROPOSALS = 5

#: The path no proposal may mention. Reading the pattern library makes the
#: working agent defend against the patterns instead of following the rules,
#: and then nobody can tell whether the rules are doing anything (design-v2
#: §12; WikiSkill's ablation). A proposal that named it would smuggle it into
#: the decision queue and, if accepted, into the block.
FORBIDDEN = "output/reflect"

TIMEOUT = 900

PROMPT = """You are turning observations into at most {limit} proposals.

Each observation below has been seen in at least two independent sessions. Your
job is to say what should change — once per observation at most, and only where
you can name exactly what to change.

Rules:
- **One target per proposal.** A proposal that changes three things is three
  proposals somebody has to weigh as one.
- A proposal must cite the observation it comes from.
- Prefer nothing. Returning two good proposals is better than five.
- Where a fix may go depends on where the problem was seen. Each observation
  says which hosts showed it:
  - two or more hosts: it may target the shared protocol (`AGENTS.md`), a
    skill, or a test.
  - one host: it may target **only that host's own configuration**. A
    workaround for one CLI in the shared layer makes every other host read it
    every session for nothing.

These were proposed before and turned down. Do not propose them again. If your
idea is close to one of them, say in `text` what makes it different:

{rejected}

--- OBSERVATIONS ---

{observations}

Answer as JSON, one object per line, nothing else:

{{"pattern": "<observation slug>", "kind": "rule|patch|skill|fact",
  "target": "<file, skill or block>", "text": "<the change, in one or two lines>",
  "evidence": ["<verbatim quote from the observation>"],
  "patch": {{"op": "append|replace|insert_after", "target": "exact substring",
  "text": "..."}}}}

`kind: rule` is a line of prose for the protocol block — the most expensive kind,
because every session on every host reads it. `kind: fact` is something true about
the subject rather than about how to work; it belongs in the wiki. `patch` is
optional and only for `kind: patch` or `skill`.
"""


@dataclass
class Report:
    considered: list = field(default_factory=list)   # pattern slugs
    failed: bool = False
    made: list = field(default_factory=list)         # proposal ids
    skipped: list = field(default_factory=list)      # (pattern, why)
    host: str = ""
    model: str = ""
    effort: str = ""
    called: bool = False
    note: str = ""


def shared_layer_allowed(pattern) -> bool:
    """Whether this pattern's fix may touch what every host reads."""
    return len(set(pattern.hosts)) >= 2


def _is_host_local(pattern, target: str) -> bool:
    """Does this target belong to the one host that saw the problem?

    Named by the host, because that is the only thing a person and a checker
    can both verify: `.claude/settings.json` is Claude's, `~/.codex/config` is
    Codex's, and `AGENTS.md` is nobody's in particular — which is the point.
    """
    lowered = str(target or "").lower()
    return any(host.lower() in lowered for host in set(pattern.hosts))


def build_prompt(ready, turned_down, limit: int = MAX_PROPOSALS) -> str:
    blocks = []
    for pattern in ready:
        where = ("seen on " + ", ".join(sorted(set(pattern.hosts)))
                 + ("" if shared_layer_allowed(pattern)
                    else " — one host only, so a fix belongs in that host's config"))
        blocks.append(f"## OBSERVATION {pattern.slug}\n"
                      f"{pattern.title}\n({where}; "
                      f"{pattern.independent} independent sessions)\n\n"
                      f"{pattern.body}\n")
    rejected_text = "\n".join(
        f"- [{p.kind}] {p.target}: {p.text}"
        + (f"\n  they said: {p.note}" if p.note else "")
        for p in turned_down) or "(nothing has been turned down yet)"
    return PROMPT.format(limit=limit, rejected=rejected_text,
                         observations="\n\n".join(blocks))


def _names_the_library(value: str) -> bool:
    """Does this mention the pattern library, however it is spelled?"""
    return FORBIDDEN in str(value).replace("\\", "/").lower()


def parse(reply: str, ready_by_slug: dict, seen: set,
          limit: int = MAX_PROPOSALS) -> tuple:
    """`(rows, skipped)` — everything checked against the files, not trusted."""
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

        slug = str(row.get("pattern") or "").strip()
        pattern = ready_by_slug.get(slug)
        if pattern is None:
            skipped.append((slug or "?", "cites no observation from this pass"))
            continue
        kind = str(row.get("kind") or "").strip()
        if kind not in proposals.KINDS:
            skipped.append((slug, f"not a proposal kind: {kind!r}"))
            continue
        target = str(row.get("target") or "").strip()
        text = str(row.get("text") or "").strip()
        if not target or not text:
            skipped.append((slug, "a proposal needs a target and a change"))
            continue
        # Lowercased first. The guard is a substring test against a path the
        # model wrote, and `Output/Reflect/patterns/x.md` is the same directory
        # on every filesystem this runs on — Windows and macOS both match it
        # case-insensitively. A guard on the one spelling is not a guard.
        if _names_the_library(target) or _names_the_library(text):
            # The pattern library is not for the working agent (design-v2 §12).
            # A proposal naming it would put the path in the decision queue and,
            # if accepted as a rule, into the block every session reads.
            skipped.append((slug, "names the pattern library, which the working "
                                  "agent must not be pointed at"))
            continue
        if not shared_layer_allowed(pattern) and not _is_host_local(pattern, target):
            # One host saw it, so the fix belongs in that host's own
            # configuration — whatever kind it calls itself. Checking only
            # `rule` left the two kinds that actually edit files free to write
            # into the shared layer on one host's evidence.
            only = ", ".join(sorted(set(pattern.hosts))) or "one host"
            skipped.append((slug, f"seen on {only} only — a change everybody "
                                  f"reads cannot come from that"))
            continue
        key = proposals.fingerprint(kind, target, text)
        if key in seen:
            skipped.append((slug, "this exact change has been proposed before"))
            continue
        seen.add(key)
        kept.append({"pattern": slug, "kind": kind, "target": target, "text": text,
                     "evidence": [str(item) for item in (row.get("evidence") or [])],
                     "patch": row.get("patch") if isinstance(row.get("patch"), dict)
                     else {},
                     "hosts": sorted(set(pattern.hosts))})
        if len(kept) >= limit:
            break
    return kept, skipped


def run(root, *, host=None, model=None, effort=None, timeout: int = TIMEOUT,
        dry_run: bool = False, now=None) -> Report:
    from .. import review

    root = Path(root)
    report = Report()
    today = now or dt.date.today()

    ready = patterns.ready(root, now=today)
    report.considered = [pattern.slug for pattern in ready]
    if not ready:
        report.note = ("nothing has recurred yet — an observation needs two "
                       "independent sessions before it is worth acting on")
        return report

    settings = review._config(root)
    chosen = review.pick_host(None, configured=host or settings.host,
                              config=settings.config)
    report.host = chosen or ""
    if chosen is None:
        report.note = ("no CLI on PATH to think with "
                       f"(looked for {', '.join(review.host_names(settings.config))})")
        report.failed = True
        return report

    _entry, model, effort = review.plan(chosen, model, effort, settings)
    report.model, report.effort = model, effort

    if dry_run:
        report.note = (f"would ask {chosen}"
                       + (f" ({model}" if model else " (its own default")
                       + (f", effort {effort})" if effort else ")")
                       + f" about {len(ready)} observation(s): "
                       + ", ".join(report.considered))
        return report

    try:
        ledger.check(root, enabled=settings.enabled)
    except ledger.SwitchedOff as exc:
        report.note = str(exc)
        report.failed = True
        return report

    prompt = build_prompt(ready, proposals.rejected(root))
    started = time.monotonic()
    try:
        reply = ask(chosen, prompt, cwd=root, model=model, timeout=timeout,
                    effort=effort)
        ok = True
    except BaseException as exc:  # noqa: BLE001 — recorded, then reported
        reply, ok = "", False
        report.failed = True
        report.note = f"the pass could not run ({exc.__class__.__name__}: {exc})"
        if not isinstance(exc, Exception):
            # `KeyboardInterrupt` and `SystemExit` are the operator, not a
            # failed pass. Recorded like any other spend — the subprocess ran
            # and cost wall clock — and then re-raised, because absorbing
            # Ctrl+C during a fifteen-minute headless call leaves somebody
            # pressing it again and wondering what it is doing.
            # `review.review` has always done this; these two did not.
            raise
    finally:
        ledger.record(root, ledger.REFLECT, chosen, model=model, effort=effort,
                      ok=ok, seconds=time.monotonic() - started,
                      note=f"{len(ready)} observations")
    report.called = True
    if not ok:
        return report

    rows, skipped = parse(reply, {p.slug: p for p in ready},
                          proposals.already_proposed(root))
    report.skipped = skipped
    # Re-read rather than reuse the set from before the call: the model can
    # take a quarter of an hour, and a second run that started inside that
    # window has had every chance to file the same proposal. This narrows the
    # race to the loop below; closing it outright means checking inside the
    # ledger's append lock, which `proposals._append` does not expose.
    seen = proposals.already_proposed(root)
    for row in rows:
        if proposals.fingerprint(row["kind"], row["target"], row["text"]) in seen:
            # `skipped` is the list `parse()` returned, holding (slug, why)
            # pairs; `+= 1` on it raises TypeError and takes the whole run
            # down at exactly the moment this branch exists to handle — a
            # second run started inside the first one's model call.
            skipped.append((row["pattern"],
                            "this exact change has been proposed before"))
            report.skipped = skipped
            continue
        made = proposals.propose(root, kind=row["kind"], target=row["target"],
                                 text=row["text"], pattern=row["pattern"],
                                 hosts=row["hosts"], evidence=row["evidence"],
                                 patch=row["patch"])
        report.made.append(made.id)
        # The observation has been acted on. It stays on disk for provenance —
        # an accepted rule has to be able to point at what produced it.
        patterns.mark(root, row["pattern"], patterns.PROPOSED)
    return report


def render(report: Report) -> str:
    lines = [f"  {len(report.considered)} observation(s) worth acting on"]
    if report.note:
        lines.append(f"  {report.note}")
    for ident in report.made:
        lines.append(f"  proposed {ident}")
    for slug, why in report.skipped:
        lines.append(f"  skipped {slug}: {why}")
    return "\n".join(lines)
