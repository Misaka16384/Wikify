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


def test_no_model_asked_for_means_no_model_flag():
    """MAGI does not know this account better than the person who configured
    it. With nothing pinned, the CLI uses whatever it uses interactively."""
    for host in hosts.BUILTIN:
        if not (host.argv and host.model_flag):
            continue
        assert host.model_flag not in host.headless("q"), host.key


def test_a_record_can_name_its_own_model():
    """`research.review_model` is one string and the reviewer host is picked
    automatically, so a name that is right for one vendor is an "unknown model"
    error on the next. The record says which host its model belongs to."""
    config = {"research": {"hosts": [dict(CUSTOM, model="mycli-fast")]}}
    entry = hosts.catalog(config)["mycli"]

    assert entry.pick_model() == "mycli-fast"
    assert entry.pick_model(configured="global-one") == "mycli-fast"
    assert entry.pick_model("asked-for", "global-one") == "asked-for"
    assert entry.headless("q", entry.pick_model())[-2:] == ["--model", "mycli-fast"]


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


# --------------------------------------------------------------------------
# and the commands that are supposed to read it
# --------------------------------------------------------------------------

#: A record whose binary really is on PATH, so `installed_hosts` finds it
#: without a stub. `argv` never runs — `ask` is replaced — but it has to be
#: there or the host declares no headless mode.
RUNNABLE = {
    "key": "mycli",
    "bin": "python",
    "argv": ["{bin}", "-c", "print({prompt!r})"],
    "model_flag": "--model",
    "model": "big-one",
}


@pytest.fixture
def declared(tmp_path):
    """A workspace with one proposition waiting and one host declared."""
    import yaml

    from magi.core import vocab as _vocab
    from magi.kb import threads as _threads

    (tmp_path / "threads").mkdir()
    path = _threads.create(tmp_path / "threads" / "p-gap.md", _vocab.PROPOSITION,
                           "The gap survives", "Decide before a month of numerics.")
    _threads.set_status(path, "testing", "started", host="claude")
    _threads.set_status(path, "supported", "converged", host="claude")
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"research": {"hosts": [RUNNABLE],
                                     "review_host": "mycli"}}), encoding="utf-8")
    return tmp_path


def test_magi_review_accepts_a_host_the_config_declares(declared, monkeypatch):
    """`--host` had `choices=host_names()`, built when the parser was built —
    before `--topic-dir` was parsed, so it could only ever list the built-in
    five. A person who wrote the documented record and named it was told by
    argparse that there is no such host."""
    seen = []
    monkeypatch.setattr(review, "ask",
                        lambda host, *a, **k: seen.append(host) or
                        "VERDICT: stands\nREASON: it holds.")

    code = review.main(["--topic-dir", str(declared), "--host", "mycli"])

    assert code == 0
    assert seen == ["mycli"]


def test_research_review_host_can_name_one_too(declared, monkeypatch):
    """The other way in, and the one a person configures once instead of
    typing every time."""
    seen = []
    monkeypatch.setattr(review, "ask",
                        lambda host, *a, **k: seen.append(host) or
                        "VERDICT: stands\nREASON: it holds.")

    assert review.main(["--topic-dir", str(declared)]) == 0
    assert seen == ["mycli"]


def test_the_declared_record_decides_the_model(declared, monkeypatch):
    """The whole point of `model:` on the record: one `review_model` string
    cannot be right for two vendors, so the model belongs to the host."""
    seen = {}
    monkeypatch.setattr(review, "ask",
                        lambda host, prompt, cwd, model=None, **k:
                        seen.update(model=model) or "VERDICT: stands\nREASON: ok.")

    review.main(["--topic-dir", str(declared), "--host", "mycli"])

    assert seen["model"] == "big-one"


def test_an_undeclared_host_is_still_refused_and_says_where_to_declare_one(
        declared, monkeypatch, capsys):
    """Dropping `choices=` must not drop the check. It moves to where the
    config is loaded, which is also where the message can be useful."""
    monkeypatch.setattr(review, "ask", lambda *a, **k: "VERDICT: stands\nREASON: ok.")

    code = review.main(["--topic-dir", str(declared), "--host", "nosuchcli"])

    err = capsys.readouterr().err
    assert code == 1
    assert "nosuchcli" in err and "mycli" in err
    assert "research.hosts" in err


def test_magi_install_installs_into_a_declared_host(tmp_path, monkeypatch):
    """`skills_cmd.HOSTS` is a snapshot taken at import: five records, forever.
    `magi install` read it to decide what was on the machine."""
    import yaml

    from magi import skills_cmd as _skills

    # `threads/` is what makes this a workspace; without it `load_config`
    # walks past the directory and the record is never read.
    (tmp_path / "threads").mkdir()
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"research": {"hosts": [RUNNABLE]}}), encoding="utf-8")
    from magi.core.config_loader import load_config

    config = load_config(start=tmp_path)

    assert "mycli" in [host.key for host in _skills.detected_hosts(config)], (
        "python is on PATH, so a record naming it is a detected host")
    assert "mycli" not in [host.key for host in _skills.detected_hosts()], (
        "and it is only detected because the config was passed")


def test_and_magi_install_is_the_one_that_has_to_pass_it(tmp_path, capsys):
    """The assertion above proves the helper works when handed a config, which
    was never in doubt — `install_cmd` called it without one. Testing the
    helper and calling that coverage is how the first version of this test
    stayed green with the bug put back."""
    import yaml

    from magi import install_cmd

    (tmp_path / "threads").mkdir()
    (tmp_path / "AGENTS.md").write_text("# House rules\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"research": {"hosts": [RUNNABLE]}}), encoding="utf-8")

    install_cmd.main(["--topic-dir", str(tmp_path), "--dry-run"])

    assert "mycli" in capsys.readouterr().out
