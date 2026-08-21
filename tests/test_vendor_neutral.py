"""MAGI supports four agent CLIs. Text and behaviour must not favour one.

Claude Code, Codex, Antigravity and opencode are all first-class hosts — the
skills install into every one of them, and the doctor reports on all four. Two
things are genuinely Claude-specific and correctly named: the Claude Code
plugin marketplace, which no other host has, and the legacy-Wikify cleanup,
which scans `~/.claude` and `~/.gemini` because legacy Wikify predates the
other hosts. Everything else that names Claude alone is a bug.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
APP_JS = REPO / "src" / "magi" / "ui" / "static" / "app.js"


def _i18n_block(lang: str) -> str:
    js = APP_JS.read_text(encoding="utf-8")
    m = re.search(rf"{lang}:\s*\{{(.*?)^\s*\}},", js, re.DOTALL | re.MULTILINE)
    assert m, f"{lang} dictionary not found"
    return m.group(1)


def _value(block: str, key: str) -> str:
    m = re.search(rf'^\s*{key}:\s*"(.*?)",\s*$', block, re.MULTILINE)
    assert m, f"{key} not found"
    return m.group(1)


# --------------------------------------------------------------------------
# every host MAGI supports
# --------------------------------------------------------------------------

def test_all_four_hosts_are_registered():
    """The premise of every other test here."""
    from magi.skills_cmd import HOSTS

    assert {h.binary for h in HOSTS.values()} == {"claude", "codex", "agy", "opencode"}


def test_the_doctor_reports_on_every_host_or_none():
    """`agent_cli_rows` iterates HOSTS — reporting only Claude would imply the
    others are unsupported, which is exactly backwards."""
    from magi.setup_cmd import agent_cli_rows
    from magi.skills_cmd import HOSTS

    names = {r.name if hasattr(r, "name") else r[0] for r in agent_cli_rows()}
    for host in HOSTS.values():
        assert host.binary in names, f"{host.binary} missing from the doctor table"


def test_setup_reports_hosts_generically():
    """The scan that runs during `magi setup` must not be Claude-only."""
    import inspect

    from magi.setup_cmd import report_agent_skills

    src = inspect.getsource(report_agent_skills)
    assert "detected_hosts" in src, "the host scan is no longer generic"
    # A hardcoded "claude" here would mean the summary line names one vendor.
    assert '"claude"' not in src and "'claude'" not in src


# --------------------------------------------------------------------------
# the WebUI copy that started this
# --------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["zh", "en"])
def test_the_setup_danger_description_names_every_host(lang):
    """It described the one Claude-specific step as if it were the whole job.

    `magi setup` scans for all four CLIs; the plugin registration is the only
    part that is Claude Code's alone, and the copy has to make that boundary
    visible instead of implying the operation is Claude-only.
    """
    desc = _value(_i18n_block(lang), "danger_setup_desc")
    for host in ("Codex", "Antigravity", "opencode"):
        assert host in desc, f"{lang}: danger_setup_desc does not mention {host}"


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_the_legacy_description_says_why_it_is_two_directories(lang):
    """`find_legacy_copies` really does scan only ~/.claude and ~/.gemini.

    That is correct — legacy Wikify predates the other hosts, so there is
    nothing of theirs to clean up — but stated bare it reads as favouritism.
    """
    desc = _value(_i18n_block(lang), "danger_remove_legacy_desc")
    assert ".claude" in desc and ".gemini" in desc
    mentions_why = any(w in desc for w in ("predates", "早于"))
    assert mentions_why, f"{lang}: says which directories, never says why only those"


def test_the_legacy_scan_still_matches_what_the_text_claims():
    """If the scan grows a directory, the copy above is now wrong."""
    import inspect

    from magi.setup_cmd import find_legacy_copies

    src = inspect.getsource(find_legacy_copies)
    homes = set(re.findall(r'"\.(\w+)"', src))
    assert homes <= {"claude", "gemini"}, (
        f"the legacy scan now covers {sorted(homes)}; danger_remove_legacy_desc "
        "still tells the user it is only .claude and .gemini"
    )


# --------------------------------------------------------------------------
# the guide's command extractor
# --------------------------------------------------------------------------

def test_the_command_whitelist_covers_every_host():
    """An asymmetric list silently drops examples written for other CLIs."""
    from magi.guide import _CMD_TOOLS
    from magi.skills_cmd import HOSTS

    for host in HOSTS.values():
        assert host.binary in _CMD_TOOLS, (
            f"{host.binary} is a supported host but the guide's extractor "
            f"would not recognise a command starting with it"
        )
