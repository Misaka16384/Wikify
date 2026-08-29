"""Conventions every shipped skill has to keep.

Two of them, both learned the expensive way.

**Capabilities, not tool names.** Naming a host's tool in a skill file is a
claim that goes stale and is often wrong to begin with: `edit_file` was asserted
for Antigravity for months and appears in none of its documentation, and
`AskUserQuestion` was named as *the* way to ask when it does not work from a
sub-agent at all. A wrong tool name is worse than none, because an agent that
cannot find it may conclude the capability is unavailable and skip the step.

**Only the main agent asks.** Researched across the four hosts MAGI supports:
Antigravity has no ask-tool, Codex's works only in Plan mode and errors in exec,
opencode denies its own by default when non-interactive, and Claude Code's does
not reach the human from a sub-agent. A sub-agent that tries to ask therefore
fails silently or hangs — it has to return the question instead, and one
orchestrator asks once for all of them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[1] / "src" / "magi" / "skills"

# Tool names belonging to a specific host. None of these may appear in a skill.
HOST_TOOL_NAMES = [
    "AskUserQuestion", "request_user_input",
    "invoke_subagent", "view_file", "edit_file", "write_to_file",
    "replace_file_content", "search_web", "code_search", "grep_search",
]

SKILL_FILES = sorted(
    p for p in SKILLS.glob("*/SKILL.md")
    # A skill may ship a fixture tree of deliberately broken sample files; the
    # SKILL.md inside one is a fixture, not a skill. (v1's `wiki_lint` had one;
    # nothing does today, and the guard costs nothing.)
    if "tests" not in p.parts
)


def _body(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_there_are_skills_to_check():
    """v2 ships eight. The floor guards against a glob that silently matches
    nothing, which would make every check below vacuously true."""
    assert len(SKILL_FILES) >= 8


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_no_skill_names_a_specific_hosts_tool(path):
    """Describe the capability; let the agent map it to whatever it has."""
    text = _body(path)
    found = [name for name in HOST_TOOL_NAMES if name in text]
    assert not found, (
        f"{path.parent.name} names host-specific tools {found}. "
        "Say what the capability is instead — the names differ per host, "
        "change between versions, and have already been wrong in this repo."
    )


@pytest.mark.parametrize(
    "path",
    [p for p in SKILL_FILES if "Tools — capabilities" in _body(p)],
    ids=lambda p: p.parent.name,
)
def test_a_skill_with_a_tooling_note_also_says_who_asks(path):
    """The two notes travel together: knowing you may ask is useless without
    knowing that, as a sub-agent, your asking will not arrive."""
    text = _body(path)
    assert "Questions go to the main agent" in text
    assert "NEEDS-DECISION" in text


def test_the_headless_case_is_covered():
    """A scheduled or piped run has nobody to answer. Guessing and waiting are
    both wrong there, and every host fails at it differently.

    Checked against the managed block rather than each skill: v2 states this
    once, in the file every host reads at the start of every session, because
    a rule repeated in eight skills is a rule that gets edited in one.
    """
    from magi.core import managed

    text = managed.body("T", "A topic.").lower()
    assert "scheduled run" in text and "piped run" in text
    assert "do not guess" in text


#: The canonical notes list "spawn a sub-agent" as a capability, so scanning the
#: whole file finds that phrase in every skill. Strip the boilerplate first: the
#: question is whether the *body* orchestrates a fan-out.
_NOTE_BLOCK = re.compile(r"^> \*\*(?:Tools —|Questions go to).*?(?:\n>.*)*",
                         re.MULTILINE)

_FANOUT = re.compile(
    r"(?:one|a)\s+[\"'\w -]{0,30}sub-?agent\s+per\b"     # one X sub-agent per Y
    r"|per\s+sub-?agent\b"                                 # ... per sub-agent
    r"|spawn(?:ing)?\s+(?:parallel|multiple|one or more)\b",
    re.IGNORECASE)


def _spawns_subagents(text: str) -> bool:
    return bool(_FANOUT.search(_NOTE_BLOCK.sub("", text)))


@pytest.mark.parametrize(
    "path",
    [p for p in SKILL_FILES if _spawns_subagents(_body(p))],
    ids=lambda p: p.parent.name,
)
def test_a_fanning_out_skill_says_to_collect_the_questions(path):
    """Declaring the convention in the header is not enough for a skill that
    actually fans out — the step that waits for sub-agents has to say to gather
    what they could not ask, or ten sub-agents become ten interruptions."""
    text = _body(path)
    if "NEEDS-DECISION" not in text:
        pytest.skip("skill mentions sub-agents but does not orchestrate them")
    assert text.count("NEEDS-DECISION") >= 2, (
        f"{path.parent.name} spawns sub-agents but never says to collect their "
        "NEEDS-DECISION lines when they report back."
    )


def test_the_workspace_protocol_carries_the_same_rule():
    """The one place a change reaches every host and every skill at once.

    Asserted against the rendered managed block rather than against whichever
    module currently holds the string: what matters is that a workspace's
    `AGENTS.md` states the rule, not where in the package the text lives.
    """
    from magi.core import managed

    block = managed.body("T", "A topic.")
    assert "NEEDS-DECISION" in block
    assert "sub-agent never asks the human" in block
    # Cost stated in the same breath as the question — "proceed?" is not a
    # question anyone can answer.
    assert "34 sub-agent calls" in block


# --------------------------------------------------------------------------
# D5: a skill is code with the highest cost per character, and no tests
#
# The checks above are about form — which tool names may appear, and who is
# allowed to ask a question. They could not have caught the incident that
# started this: `ingest/SKILL.md` listed MinerU first, native vision as
# its fallback, and local OCR "only if the user explicitly requests it". An
# unattended agent has no user to request anything, so it could never reach the
# cheap route, and one 99-page paper cost a weekly token quota.
#
# What follows cannot check behaviour either. It checks that the three failure
# modes this project has actually paid for are written down in the file an
# agent reads, which is the cheapest thing that would have helped.
# --------------------------------------------------------------------------

FANS_OUT = [p for p in SKILL_FILES
            if "sub-agent" in _body(p).lower() or "subagent" in _body(p).lower()]


def test_some_skills_fan_out():
    """Was ten, when there were twenty skills. The checks below only mean
    something if some skill actually orchestrates, so this guards the same
    thing at the new size: the fan-out rules are not being enforced against an
    empty list."""
    assert len(FANS_OUT) >= 3


@pytest.mark.parametrize("path", FANS_OUT, ids=lambda p: p.parent.name)
def test_a_skill_that_fans_out_carries_its_rules(path):
    """Anything that can start N agents can spend N times what its author
    imagined. The bar is that the file says so."""
    body = _body(path)
    assert re.search(r"^##+ Rules\s*$", body, re.MULTILINE) or \
        re.search(r"^##+ Quality [Rr]ules\s*$", body, re.MULTILINE), \
        f"{path.parent.name} spawns sub-agents but states no rules"


@pytest.mark.parametrize("path", FANS_OUT, ids=lambda p: p.parent.name)
def test_a_skill_that_fans_out_says_never_at_least_twice(path):
    body = _body(path)
    nevers = len(re.findall(r"\*\*Never\b", body))
    assert nevers >= 2, (
        f"{path.parent.name} has {nevers} explicit prohibition(s); the point of "
        "the rules block is what must not happen, not what should")


@pytest.mark.parametrize("path", FANS_OUT, ids=lambda p: p.parent.name)
def test_a_skill_that_fans_out_bounds_the_fan_out(path):
    """A number before the first agent starts, and a ceiling on concurrency.
    The quota incident was a fan-out nobody had counted.

    Forbidding the fan-out outright counts. `ingest` mentions sub-agents
    only to say it must never start any, and "never" is a bound — this asks
    that the ceiling be stated, not that it be greater than zero.
    """
    body = _body(path).lower()
    bounded = ("10 at once" in body or "10 concurrent" in body
               or "concurrency" in body
               or "do not transcribe pages" in body)
    assert bounded, \
        f"{path.parent.name} involves sub-agents without stating any ceiling"


@pytest.mark.parametrize("path", FANS_OUT, ids=lambda p: p.parent.name)
def test_a_skill_that_fans_out_forbids_reporting_partial_work_as_whole(path):
    """The shape this whole codebase is organised against: not a crash, not a
    gap, but a result that reads as complete while part of it is missing."""
    body = _body(path).lower()
    assert "partial" in body or "say so plainly" in body, \
        f"{path.parent.name} does not say what to do when part of the work fails"


def test_the_expensive_route_is_never_offered_as_an_automatic_fallback():
    """The incident itself, as a check.

    Per-page vision transcription may appear in a skill — it is a real last
    resort — but never as something an unattended agent falls into. Wherever
    it is mentioned, the same file must state the cost and require a person to
    have said yes.
    """
    offenders = []
    for path in SKILL_FILES:
        body = _body(path)
        if not re.search(r"(?i)\bnative[ -]vision|vision transcription|"
                         r"transcrib\w+ (?:the )?pages?\b", body):
            continue
        priced = re.search(r"(?i)one sub-?agent call per page", body)
        # An outright prohibition is a stronger answer than a gate, and one
        # skill gives it: `ingest` says never to transcribe pages at all.
        gated = re.search(r"(?i)explicit(?:ly)? (?:asked|requested|said)|"
                          r"after being told the page count|has said yes|"
                          r"do not transcribe pages", body)
        if not (priced and gated):
            offenders.append(
                f"{path.parent.name}: priced={bool(priced)} gated={bool(gated)}")

    assert not offenders, (
        "these mention per-page vision transcription without both stating its "
        "cost and requiring an explicit yes — which is exactly the wording that "
        "let an unattended agent spend a weekly quota:\n  " + "\n  ".join(offenders))


# --------------------------------------------------------------------------
# A skill may only name commands and flags that exist
# --------------------------------------------------------------------------
#
# Skills are prose that gets executed, and nothing type-checks prose. Every
# instance found so far was the same shape: a command that used to take a flag,
# or never took it. `ingest` told an agent to queue with `--library` and
# then to run `batch-run`, `batch-list`, `batch-decide` and `batch-commit`
# bare — none of which has ever accepted `--library` — so the queue it had just
# filled sat untouched while a different library's queue was processed.
# `compile` called `magi wiki reindex` "the concept builder" and said it
# generates missing concept files, which it has never done.

import functools
import subprocess
import sys

_MAGI_CMD_RE = re.compile(r"`?\bmagi ((?:[a-z][a-z0-9-]*)(?: [a-z][a-z0-9-]*)?)")
_FLAG_RE = re.compile(r"(--[a-z][a-z0-9-]*)")

# Placeholders and shell noise that are not commands.
_NOT_A_COMMAND = {"<command>", "<cmd>"}


def _commands():
    from magi.cli import _COMMANDS
    return _COMMANDS


@functools.lru_cache(maxsize=None)
def _accepted_flags(key: tuple) -> frozenset:
    """The long options `magi <key> --help` advertises."""
    res = subprocess.run([sys.executable, "-m", "magi", *key, "--help"],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=120)
    return frozenset(_FLAG_RE.findall(res.stdout or ""))


#: A line that exists to say a flag is *not* real — "there is no `magi migrate
#: --dry-run`". Reading one as usage would make a warning against inventing
#: flags the thing that fails this test.
_NEGATION_RE = re.compile(
    "there is no|no such|does not exist|never invent|not a real",
    re.IGNORECASE)


def _code_spans(text: str):
    """Every `backticked` span and fenced code line, with its line intact.

    A command reference is written as code. Prose is not: a description
    sentence containing the words "magi command errors" is English, and
    reading it as an invocation is how this test would spend its credibility
    on noise instead of on the real findings.
    """
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        # Judged on the whole line, before it is cut into spans: magi_guide
        # carries a deliberate list of flags that do NOT exist, and each one
        # is backticked, so a span-level check would never see the "there is
        # no" that governs them.
        if _NEGATION_RE.search(line):
            continue
        if fenced:
            yield line
        else:
            for span in re.findall(r"`([^`]+)`", line):
                yield span


def _invocations(text: str):
    """(command key, flags used) for every `magi ...` usage in a skill."""
    for line in _code_spans(text):
        hits = list(_MAGI_CMD_RE.finditer(line))
        for i, m in enumerate(hits):
            words = m.group(1).split()
            if not words or words[0] in _NOT_A_COMMAND:
                continue
            key = tuple(words[:2])
            if key not in _commands():
                key = (words[0],)
            # Stop at the next `magi ...`: one sentence naming two commands
            # used to hand the second one's flags to the first.
            end = hits[i + 1].start() if i + 1 < len(hits) else len(line)
            yield key, set(_FLAG_RE.findall(line[m.end():end]))


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_a_skill_only_names_commands_that_exist(path):
    unknown = sorted({" ".join(key) for key, _ in _invocations(_body(path))
                      if key not in _commands()})
    assert not unknown, (
        f"{path.parent.name} names commands that are not in the CLI: {unknown}")


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_a_skill_only_passes_flags_the_command_accepts(path):
    bad = []
    for key, flags in _invocations(_body(path)):
        if key not in _commands():
            continue        # the other test reports these
        accepted = _accepted_flags(key)
        if not accepted:
            continue        # --help produced nothing parseable; not this test's job
        for flag in sorted(flags - accepted):
            bad.append(f"magi {' '.join(key)} {flag}")
    assert not bad, (
        f"{path.parent.name} passes flags the command does not accept: {bad}")
