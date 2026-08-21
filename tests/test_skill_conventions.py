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
