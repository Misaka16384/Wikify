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

from magi import install_cmd


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
    """Three of the four hosts have no equivalent. Reporting an install that
    did nothing is worse than reporting the asymmetry."""
    line = install_cmd.install_hook(ws, "codex")
    assert "no documented stop hook" in line
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
