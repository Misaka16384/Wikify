"""One table, and the three questions it has to answer at once.

There used to be three lists of hosts — where a skill installs, what to run
headless, whose transcripts we can read — edited separately, and they drifted
exactly the way separately-edited lists do: the same vendor under two names, a
PATH probe looking for a binary another table spelled differently. The property
here is that they cannot drift again, because there is nowhere for them to
drift *to*.

The second property is the one the user asked for: **there are too many CLIs in
the world**, so adding one is adding a record, not editing code. A host
declared in `research.hosts` has to reach the same places a built-in does.
"""

from pathlib import Path

import pytest

from magi import review, skills_cmd
from magi.core import hosts
from magi.reflect import transcripts


# --------------------------------------------------------------------------
# the record
# --------------------------------------------------------------------------

def test_every_builtin_record_is_complete_enough_to_use():
    for host in hosts.BUILTIN:
        assert host.key and host.label and host.command
        assert host.marker, f"{host.key}: nothing to detect it by"
        assert host.drops, f"{host.key}: nowhere to install"
        assert host.tier in (hosts.TIER_VERIFIED, hosts.TIER_BEST_EFFORT)


def test_a_key_and_a_binary_are_two_different_strings():
    """The bug this table exists to end: `installed_hosts` probed PATH for the
    host's *name*, so Antigravity — whose command is `agy` — read as "not
    installed" while sitting right there on PATH."""
    entry = hosts.catalog()["antigravity"]
    assert entry.command == "agy"
    assert entry.key != entry.command


def test_the_headless_line_comes_from_the_record():
    codex = hosts.catalog()["codex"]
    assert codex.headless("hello") == ["codex", "exec", "hello"]
    assert codex.headless("hello", "o3") == ["codex", "exec", "hello", "-m", "o3"]


def test_a_record_with_no_argv_declares_no_headless_mode():
    """Not "we forgot" — "this is not verified", which is a different claim and
    the reviewer must not paper over it with a guessed flag."""
    assert hosts.catalog()["opencode"].headless("hi") == []


def test_the_tiers_say_what_was_measured():
    tiers = {host.key: host.tier for host in hosts.BUILTIN}
    assert tiers["claude"] == tiers["codex"] == tiers["antigravity"] == hosts.TIER_VERIFIED
    assert tiers["qwen"] == tiers["opencode"] == hosts.TIER_BEST_EFFORT


# --------------------------------------------------------------------------
# path templates
# --------------------------------------------------------------------------

def test_templates_expand_against_a_given_home(tmp_path):
    dest = hosts.expand("{home}/.claude/skills", home=tmp_path)
    assert dest == tmp_path / ".claude" / "skills"


def test_a_project_template_with_no_root_is_nowhere_not_the_cwd(tmp_path):
    """"This host has no project scope" and "we are not in a workspace" are the
    same answer to the caller. Falling back to the cwd would write skills into
    whatever directory somebody happened to be standing in."""
    assert hosts.expand("{root}/.agents/skills") is None
    assert hosts.expand("", root=tmp_path) is None
    assert hosts.expand("{root}/.agents/skills", root=tmp_path) == tmp_path / ".agents" / "skills"


def test_a_template_naming_something_we_do_not_substitute_is_nowhere():
    assert hosts.expand("{nonsense}/skills") is None


# --------------------------------------------------------------------------
# the three questions, one answer each
# --------------------------------------------------------------------------

def test_the_reviewer_and_the_installer_agree_on_who_exists():
    for key in review.host_names():
        assert key in skills_cmd.HOSTS, f"{key} is reviewable but cannot be installed into"


def test_every_declared_reader_is_a_reader_that_exists():
    """A record names its reader; this is where the name is redeemed. A typo
    here would be a host that silently reports no sessions forever."""
    for host in hosts.BUILTIN:
        if host.reader:
            assert host.reader in transcripts.ADAPTERS, host.key


def test_the_hook_field_is_where_hookable_comes_from():
    from magi import install_cmd

    assert install_cmd.HOOKABLE == tuple(
        host.key for host in hosts.BUILTIN if host.hook)


# --------------------------------------------------------------------------
# hosts as data
# --------------------------------------------------------------------------

CUSTOM = {
    "key": "mycli",
    "label": "My CLI",
    "bin": "mycli",
    "marker": "{home}/.mycli",
    "drops": [{"kind": "skill",
               "global_dir": "{home}/.mycli/skills",
               "project_dir": "{root}/.agents/skills",
               "invoke": "/{name}"}],
    "argv": ["{bin}", "--print", "{prompt}"],
    "model_flag": "--model",
}


def test_a_host_from_config_is_a_host():
    table = hosts.catalog({"research": {"hosts": [CUSTOM]}})
    assert "mycli" in table
    assert table["mycli"].headless("q", "m") == ["mycli", "--print", "q", "--model", "m"]
    assert "mycli" in hosts.names({"research": {"hosts": [CUSTOM]}})


def test_a_host_from_config_can_be_reviewed_and_installed_into(tmp_path):
    config = {"research": {"hosts": [CUSTOM]}}
    assert "mycli" in review.host_names(config)
    entry = skills_cmd.catalog(config)["mycli"]
    assert skills_cmd.target_dir(entry.drops[0], "project", tmp_path) == \
        tmp_path / ".agents" / "skills"


def test_a_host_from_config_with_no_reader_is_simply_unreadable():
    """The one thing a record cannot declare is how to parse a session store.
    That is not an error — it is one host that contributes nothing to a sweep."""
    config = {"research": {"hosts": [CUSTOM]}}
    assert "mycli" not in transcripts.readable_hosts(config)
    assert transcripts.sweep(Path.cwd(), config=config).unreadable == {}


def test_a_config_record_can_replace_a_builtin():
    """Somebody whose Codex is installed somewhere else has the CLI in front of
    them; this file does not."""
    config = {"research": {"hosts": [dict(CUSTOM, key="codex", bin="codex-next")]}}
    assert hosts.catalog(config)["codex"].command == "codex-next"


@pytest.mark.parametrize("bad", [
    None, "codex", [], {}, {"key": ""}, {"key": "has space"},
])
def test_a_malformed_record_costs_you_that_record_and_nothing_else(bad):
    """A typo in a hand-written host should not take down every command that
    reads the table."""
    assert hosts.host_from(bad) is None
    table = hosts.catalog({"research": {"hosts": [bad]}})
    assert set(table) == {host.key for host in hosts.BUILTIN}


def test_a_record_that_is_not_a_list_is_ignored():
    assert set(hosts.catalog({"research": {"hosts": "codex"}})) == \
        {host.key for host in hosts.BUILTIN}


def test_a_drop_naming_no_directory_is_dropped():
    record = dict(CUSTOM, drops=[{"kind": "skill"}, {"kind": "nonsense",
                                                     "global_dir": "{home}/x"}])
    assert hosts.host_from(record).drops == ()
