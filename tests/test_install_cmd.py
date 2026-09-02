"""`magi install` — skills, the protocol block, and the end-of-session gate.

The gate is the reason this command exists. `magi sync --close` can refuse to
let a session end while bookkeeping is missing, but only if the host actually
runs it, and a hook a person has to wire up by hand is a hook that exists in
one workspace out of five.

Two properties are load-bearing and both are about somebody else's file. An
agent's `settings.json` belongs to the person: MAGI owns one entry in it and
nothing else, so installing twice must update that entry rather than add a
second, and a hook they wrote themselves must survive an install of ours.

Enforcement is not symmetric across hosts and the command says so. Claude Code
has a documented Stop hook; the others do not, and there the rule lives in the
managed block as an instruction an agent can ignore. A uniform-looking install
that quietly does less on three hosts out of four would be worse than the
asymmetry.
"""

import json

import pytest

from magi import init_workspace, install_cmd


def settings(ws):
    return json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "AGENTS.md").write_text("# House rules\n\nAsk first.\n", encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------------
# the hook
# --------------------------------------------------------------------------

def test_the_gate_is_installed_once(ws):
    install_cmd.install_hook(ws, "claude")
    install_cmd.install_hook(ws, "claude")

    stops = settings(ws)["hooks"]["Stop"]
    commands = [entry["command"] for group in stops for entry in group["hooks"]]
    assert commands == [install_cmd.STOP_COMMAND]


def test_a_hook_somebody_else_wrote_survives(ws):
    """Dropping a person's own hook to install ours is the kind of
    helpfulness nobody asks for twice."""
    path = ws / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text(json.dumps({
        "hooks": {"Stop": [{"matcher": "", "hooks": [
            {"type": "command", "command": "notify-send done"}]}]},
        "theirs": {"keep": True},
    }), encoding="utf-8")

    install_cmd.install_hook(ws, "claude")

    data = settings(ws)
    commands = [entry["command"] for group in data["hooks"]["Stop"]
                for entry in group["hooks"]]
    assert "notify-send done" in commands and install_cmd.STOP_COMMAND in commands
    assert data["theirs"] == {"keep": True}


def test_the_previous_settings_are_kept_where_they_can_be_found(ws):
    path = ws / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text('{"theirs": 1}', encoding="utf-8")

    install_cmd.install_hook(ws, "claude")

    backup = ws / ".claude" / "settings.json.magi-backup"
    assert backup.is_file()
    assert json.loads(backup.read_text(encoding="utf-8")) == {"theirs": 1}


def test_a_settings_file_nobody_can_parse_is_not_overwritten(ws):
    path = ws / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text("{ this is not json", encoding="utf-8")

    with pytest.raises(SystemExit) as caught:
        install_cmd.install_hook(ws, "claude")

    assert "not readable JSON" in str(caught.value)
    assert path.read_text(encoding="utf-8") == "{ this is not json"


def test_a_hooks_key_of_the_wrong_shape_stops_rather_than_guesses(ws):
    with pytest.raises(SystemExit):
        install_cmd.merge_stop_hook({"hooks": "surprise"})
    with pytest.raises(SystemExit):
        install_cmd.merge_stop_hook({"hooks": {"Stop": "surprise"}})


def test_a_dry_run_changes_nothing(ws):
    line = install_cmd.install_hook(ws, "claude", dry_run=True)
    assert "would install" in line
    assert not (ws / ".claude").exists()


def test_a_host_with_no_stop_hook_says_so_instead_of_pretending(ws):
    """Reporting an install that did nothing is worse than reporting the
    asymmetry.

    The example moved from codex to opencode, and that is the point rather
    than an edit of convenience: codex documented a Stop hook and MAGI now
    writes one, so using it here would have been asserting something false
    about somebody else's product. opencode still has no declarative hooks at
    all — only a plugin API whose session.idle cannot refuse a stop.
    """
    line = install_cmd.install_hook(ws, "opencode")
    assert "no declarative hooks" in line
    assert "AGENTS.md" in line


# --------------------------------------------------------------------------
# the protocol
# --------------------------------------------------------------------------

def test_installing_refreshes_the_block_and_keeps_what_is_around_it(ws):
    install_cmd.install_protocol(ws)

    text = (ws / "AGENTS.md").read_text(encoding="utf-8")
    assert "Ask first." in text, "the person's own text is not ours to move"
    assert "magi next" in text
    assert (ws / "CLAUDE.md").read_text(encoding="utf-8").strip() == "@AGENTS.md"


def test_installing_twice_reports_no_change(ws):
    install_cmd.install_protocol(ws)
    assert "already current" in install_cmd.install_protocol(ws)


def test_the_coaching_level_reaches_the_block(ws):
    install_cmd.install_protocol(ws, coaching="strict")
    assert "do not start" in (ws / "AGENTS.md").read_text(encoding="utf-8")


def test_the_workspace_name_comes_from_its_own_config(ws):
    (ws / "config.md").write_text(
        '---\ntitle: "QEC under disorder"\nscope: "Threshold behaviour."\n---\n',
        encoding="utf-8")

    install_cmd.install_protocol(ws)

    text = (ws / "AGENTS.md").read_text(encoding="utf-8")
    assert "QEC under disorder" in text and "Threshold behaviour." in text


# --------------------------------------------------------------------------
# the level the agent is told and the level the gate enforces
#
# `--coaching strict` used to reach only the protocol text. The gate reads
# `research.coaching` out of `config.yaml`, which nothing wrote — so the agent
# was told strict and the gate computed light, which is the one arrangement
# where the two readings of "which level are we on" can disagree.
# --------------------------------------------------------------------------

def test_the_level_is_written_where_the_gate_reads_it(tmp_path):
    from magi.core.config_loader import get as config_get
    from magi.core.config_loader import load_config

    root = tmp_path / "topic"
    init_workspace.main(["--topic-dir", str(root), "--name", "T", "--scope", "S",
                         "--coaching", "strict"])

    assert config_get(load_config(start=root), "research.coaching") == "strict"


def test_install_moves_the_level_too(tmp_path):
    """The workspace exists; somebody changed their mind about the level."""
    from magi.core.config_loader import get as config_get
    from magi.core.config_loader import load_config

    root = tmp_path / "topic"
    init_workspace.main(["--topic-dir", str(root), "--name", "T", "--scope", "S"])
    assert config_get(load_config(start=root), "research.coaching") == "light"

    install_cmd.write_coaching(root, "strict")
    assert config_get(load_config(start=root), "research.coaching") == "strict"


def test_a_dry_run_changes_nothing(tmp_path):
    root = tmp_path / "topic"
    init_workspace.main(["--topic-dir", str(root), "--name", "T", "--scope", "S"])
    before = (root / "config.yaml").read_bytes()

    install_cmd.install_protocol(root, "strict", dry_run=True)
    assert (root / "config.yaml").read_bytes() == before


# --------------------------------------------------------------------------
# the file somebody may have written in
# --------------------------------------------------------------------------

def test_installing_keeps_what_was_in_claude_md(tmp_path):
    """`migrate` collapsing this file keeps a copy and says where. `install`
    is the one people run again and again, so it is the one that must not eat
    what a person wrote."""
    root = tmp_path / "topic"
    init_workspace.main(["--topic-dir", str(root), "--name", "T", "--scope", "S"])
    (root / "CLAUDE.md").write_text("# House rules\n\nAlways ask before deleting.\n",
                                    encoding="utf-8")

    note = install_cmd.install_protocol(root, "light")

    assert (root / "CLAUDE.md").read_text(encoding="utf-8").strip() == "@AGENTS.md"
    kept = list((root / ".backup").glob("CLAUDE_*.md"))
    assert kept, "the old text is somewhere recoverable"
    assert "Always ask before deleting" in kept[0].read_text(encoding="utf-8")
    assert "CLAUDE.md held text" in note, "and the operator is told where"


def test_a_pointer_that_is_already_a_pointer_is_left_alone(tmp_path):
    root = tmp_path / "topic"
    init_workspace.main(["--topic-dir", str(root), "--name", "T", "--scope", "S"])

    install_cmd.install_protocol(root, "light")

    assert not (root / ".backup").exists(), "nothing to keep, nothing kept"


# --------------------------------------------------------------------------
# three hosts, three shapes
# --------------------------------------------------------------------------

def test_codex_gets_the_same_shape_in_a_file_of_its_own(ws):
    """Codex's hooks.json is Claude's `hooks` wrapper under a different name,
    confirmed against two real installed Codex plugins on the machine this was
    written on, so one writer serves both."""
    import json

    install_cmd.install_hook(ws, "codex")
    got = json.loads((ws / ".codex" / "hooks.json").read_text(encoding="utf-8"))

    assert set(got["hooks"]) == {"Stop", "PreToolUse", "SessionStart"}
    stop = got["hooks"]["Stop"][0]["hooks"][0]
    assert stop["command"] == install_cmd.STOP_COMMAND
    assert stop["type"] == "command"


def test_antigravity_gets_its_own_shape_not_a_copy_of_claudes(ws):
    """Its own bundled docs, which ship inside the CLI: the top-level key is a
    hook *name*, `Stop` is a flat array with no matcher, and there is no
    SessionStart event at all. Writing Claude's shape here would produce a
    file that parses and never fires."""
    import json

    install_cmd.install_hook(ws, "antigravity")
    got = json.loads((ws / ".agents" / "hooks.json").read_text(encoding="utf-8"))

    assert "hooks" not in got, "that is Claude's wrapper, not this one's"
    ours = got["magi"]
    assert set(ours) == {"Stop", "PreToolUse"}, "antigravity has no SessionStart"
    assert ours["Stop"][0]["command"].startswith(install_cmd.STOP_COMMAND)
    assert "matcher" not in ours["Stop"][0], "Stop takes a flat array"
    assert "matcher" in ours["PreToolUse"][0], "tool events do take groups"


def test_antigravity_is_told_to_refuse_in_its_own_word(ws):
    """It blocks a stop with `decision: continue`; the others say `block`, and
    its docs say any other value lets the agent stop. The command has to carry
    the dialect or the gate is installed and inert."""
    import json

    install_cmd.install_hook(ws, "antigravity")
    got = json.loads((ws / ".agents" / "hooks.json").read_text(encoding="utf-8"))

    assert "--dialect antigravity" in got["magi"]["Stop"][0]["command"]


def test_installing_twice_adds_nothing(ws):
    import json

    install_cmd.install_hook(ws, "antigravity")
    first = (ws / ".agents" / "hooks.json").read_text(encoding="utf-8")
    line = install_cmd.install_hook(ws, "antigravity")

    assert "already installed" in line
    assert (ws / ".agents" / "hooks.json").read_text(encoding="utf-8") == first


def test_a_hook_somebody_else_put_there_survives(ws):
    """The file is theirs. Ours goes under its own name beside whatever is
    already in it."""
    import json

    (ws / ".agents").mkdir(parents=True, exist_ok=True)
    (ws / ".agents" / "hooks.json").write_text(json.dumps(
        {"their-linter": {"PostToolUse": [{"matcher": "run_command",
                                           "hooks": [{"command": "./lint.sh"}]}]}}),
        encoding="utf-8")

    install_cmd.install_hook(ws, "antigravity")
    got = json.loads((ws / ".agents" / "hooks.json").read_text(encoding="utf-8"))

    assert "their-linter" in got
    assert "magi" in got
