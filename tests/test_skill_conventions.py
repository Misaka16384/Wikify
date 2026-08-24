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
    # wiki_lint ships a fixture tree of deliberately broken sample files.
    if "tests" not in p.parts
)


def _body(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_there_are_skills_to_check():
    assert len(SKILL_FILES) >= 15


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


@pytest.mark.parametrize(
    "path",
    [p for p in SKILL_FILES if "NEEDS-DECISION" in _body(p)],
    ids=lambda p: p.parent.name,
)
def test_the_headless_case_is_covered(path):
    """A scheduled or piped run has nobody to answer. Guessing and waiting are
    both wrong there, and every host fails at it differently."""
    text = _body(path).lower()
    assert "scheduled run" in text or "piped run" in text


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
    """The one place a change reaches every host and every skill at once."""
    from magi.hub import init_workspace

    source = Path(init_workspace.__file__).read_text(encoding="utf-8")
    assert "NEEDS-DECISION" in source
    assert "Only the agent talking to the human asks the human" in source
    # Cost stated in the same breath as the question — "proceed?" is not a
    # question anyone can answer.
    assert "34 sub-agent calls" in source


# --------------------------------------------------------------------------
# D5: a skill is code with the highest cost per character, and no tests
#
# The checks above are about form — which tool names may appear, and who is
# allowed to ask a question. They could not have caught the incident that
# started this: `wiki_ingest/SKILL.md` listed MinerU first, native vision as
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
    assert len(FANS_OUT) >= 10


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

    Forbidding the fan-out outright counts. `wiki_inbox` mentions sub-agents
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
        # skill gives it: `wiki_inbox` says never to transcribe pages at all.
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
