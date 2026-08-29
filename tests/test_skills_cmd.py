"""`magi skills` — the same skills, installed into whichever agent CLI you use.

These lock the two things that make it cross-CLI rather than Claude-only:
the skills ship inside the wheel, and every host's target directory and
invocation are declared explicitly instead of assumed.
"""

from __future__ import annotations

import json

import pytest

from magi.skills_cmd import (
    HOSTS,
    Skill,
    files_for,
    install_host,
    load_skills,
    main,
    render_command,
    target_dir,
    uninstall_host,
)


def test_skills_are_packaged_and_well_formed():
    skills = load_skills()
    assert len(skills) >= 8, "the whole skill set must ship inside the package"
    names = {s.name for s in skills}
    assert {"magi", "ingest", "compile", "radar_review"} <= names

    for s in skills:
        text = s.text
        assert text.startswith("---"), f"{s.name}: SKILL.md needs YAML frontmatter"
        assert s.description, f"{s.name}: description is what every host matches on"
        assert f"name: {s.name}" in text, f"{s.name}: frontmatter name must match its directory"
        assert "magi " in text, f"{s.name}: a MAGI skill should drive the magi CLI"
        # Legacy Wikify script paths would send agents to files that no longer exist.
        assert "llm-wiki.py" not in text, f"{s.name}: stale pre-CLI script reference"


def test_skills_are_host_neutral():
    """No skill may assume one CLI's tool names without offering the generic form."""
    for s in load_skills():
        text = s.text
        if "Read tool" in text or "`Read`" in text:
            assert "tool-agnostic" in text or "framework-agnostic" in text or "your agent's" in text, (
                f"{s.name}: names a Claude-specific tool with no generic fallback"
            )


def test_every_host_declares_scopes_and_invocation():
    assert set(HOSTS) == {"claude", "codex", "antigravity", "opencode"}
    for host in HOSTS.values():
        assert host.targets, f"{host.key}: no target directory declared"
        assert any(t.project_dir is not None for t in host.targets), (
            f"{host.key}: must support project scope"
        )
        for t in host.targets:
            assert t.kind in {"skill", "command"}
            assert t.layout in {"dir", "flat"}
            assert t.invoke, f"{host.key}: every target must say how it is triggered"
            assert target_dir(t, "global") is not None


def test_project_scope_is_under_the_given_root(tmp_path):
    (tmp_path / ".git").mkdir()          # repo-root anchored hosts look for this
    for host in HOSTS.values():
        for t in host.targets:
            if t.project_dir is None:
                continue
            dest = target_dir(t, "project", tmp_path)
            assert str(dest).startswith(str(tmp_path)), f"{host.key}: project scope escaped the root"


def test_layouts_render_what_each_host_expects(tmp_path):
    skill = next(s for s in load_skills() if s.name == "radar_review")

    dir_target = HOSTS["claude"].targets[0]
    (path, text), = files_for(skill, dir_target, tmp_path)
    assert path.name == "SKILL.md" and path.parent.name == "radar_review"
    assert text == skill.text

    cmd_target = next(t for t in HOSTS["opencode"].targets if t.kind == "command")
    (cpath, ctext), = files_for(skill, cmd_target, tmp_path)
    assert cpath.name == "radar_review.md"
    assert ctext.startswith("---\ndescription: ")
    assert "$ARGUMENTS" in ctext, "an opencode command must accept the user's arguments"
    assert "name: radar_review" not in ctext, "command files take no name key"


def test_render_command_keeps_the_body_but_not_the_old_frontmatter():
    skill = next(s for s in load_skills() if s.name == "ingest")
    out = render_command(skill)
    body = out.split("---\n", 2)[2]
    assert len(body) > 800, "the whole skill body must be inlined into the command"
    assert "name: ingest" not in out, "old frontmatter must not leak through"
    assert out.rstrip().endswith("$ARGUMENTS")


def test_install_is_idempotent_and_reversible(tmp_path):
    skills = [s for s in load_skills() if s.name in {"radar_review", "ask"}]
    host = HOSTS["claude"]

    first = install_host(host, skills, "global", force=False, dry_run=False, override_dir=tmp_path)
    assert first["counts"]["created"] == 2
    assert (tmp_path / "radar_review" / "SKILL.md").is_file()

    second = install_host(host, skills, "global", force=False, dry_run=False, override_dir=tmp_path)
    assert second["counts"]["unchanged"] == 2
    assert second["counts"]["created"] == 0

    removed = uninstall_host(host, skills, "global", dry_run=False, override_dir=tmp_path)
    assert len(removed["removed"]) == 2
    assert not (tmp_path / "radar_review").exists()


def test_dry_run_writes_nothing(tmp_path):
    skills = load_skills()[:2]
    report = install_host(HOSTS["codex"], skills, "global", force=False, dry_run=True,
                          override_dir=tmp_path)
    assert report["counts"]["created"] >= 2
    assert not any(tmp_path.iterdir())


def test_a_foreign_file_is_not_clobbered(tmp_path):
    skills = [s for s in load_skills() if s.name == "radar_review"]
    victim = tmp_path / "radar_review" / "SKILL.md"
    victim.parent.mkdir(parents=True)
    victim.write_text("someone else's skill, unrelated content\n", encoding="utf-8")

    report = install_host(HOSTS["claude"], skills, "global", force=False, dry_run=False,
                          override_dir=tmp_path)
    assert report["counts"]["skipped"] == 1
    assert "someone else" in victim.read_text(encoding="utf-8")

    forced = install_host(HOSTS["claude"], skills, "global", force=True, dry_run=False,
                          override_dir=tmp_path)
    assert forced["counts"]["updated"] == 1


def test_cli_surface(capsys, tmp_path):
    assert main(["list", "--json"]) == 0
    listing = json.loads(capsys.readouterr().out)
    assert listing["count"] >= 8
    assert all(s["description"] for s in listing["skills"])

    assert main(["where", "--json"]) == 0
    where = json.loads(capsys.readouterr().out)
    assert {r["host"] for r in where["hosts"]} == set(HOSTS)
    assert all({"scope", "kind", "dir", "invoke", "total"} <= set(r) for r in where["hosts"])

    assert main(["install", "--host", "claude", "--dir", str(tmp_path),
                 "--only", "radar_review", "--dry-run", "--json"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["dry_run"] is True
    assert plan["results"][0]["counts"]["created"] == 1
    assert not any(tmp_path.iterdir())


def test_unknown_host_is_rejected():
    with pytest.raises(SystemExit):
        main(["install", "--host", "not-a-real-cli", "--dry-run"])


def test_registered_in_the_dispatch_table():
    from magi.cli import _COMMANDS, _GROUP_HELP
    from magi.core.cli_i18n import command_help_zh, group_help_zh

    for sub in ("list", "where", "install", "uninstall"):
        key = ("skills", sub)
        assert key in _COMMANDS
        assert _COMMANDS[key][0] == "magi.skills_cmd"
        assert command_help_zh(key), f"{key}: missing Chinese help"
    assert _GROUP_HELP.get("skills") and group_help_zh("skills")


def test_default_scope_is_the_workspace_not_the_machine(tmp_path, monkeypatch):
    """Workspace-specific skills must not land in every unrelated project."""
    import argparse
    import inspect

    from magi import skills_cmd

    src = inspect.getsource(skills_cmd.main)
    assert '"--scope", choices=["project", "global"], default="project"' in src, (
        "installing globally by default puts 18 workspace skills in front of every repo"
    )


def test_project_scope_anchors_at_the_workspace_root(tmp_path, monkeypatch):
    from magi.skills_cmd import workspace_anchor

    topic = tmp_path / "topics" / "demo"
    (topic / "wiki").mkdir(parents=True)
    (topic / "config.yaml").write_text("ollama: {}\n", encoding="utf-8")
    deep = topic / "raw" / "papers"
    deep.mkdir(parents=True)

    monkeypatch.chdir(deep)
    assert workspace_anchor() == topic.resolve(), (
        "running from inside raw/ must still install at the workspace root"
    )

    outside = tmp_path / "elsewhere"
    outside.mkdir()
    monkeypatch.chdir(outside)
    assert workspace_anchor() == outside.resolve()


def test_setup_reports_hosts_without_installing(tmp_path, monkeypatch):
    """`magi setup` must never write skills anywhere."""
    import inspect

    from magi import setup_cmd

    assert not hasattr(setup_cmd, "setup_agent_skills"), (
        "setup must not install skills machine-wide"
    )
    src = inspect.getsource(setup_cmd.report_agent_skills)
    assert "install_host" not in src
    assert "magi skills install" in src

    monkeypatch.chdir(tmp_path)
    out = setup_cmd.report_agent_skills()
    assert isinstance(out, str)
    assert not any(tmp_path.iterdir()), "reporting must not create files"


def test_migration_carries_the_old_config(tmp_path):
    """A migration that loses your MinerU token is not lossless."""
    import yaml

    from magi.migrate import carry_legacy_config, find_legacy_config

    hub = tmp_path / "hub"
    topic = hub / "topics" / "demo"
    (topic / "wiki").mkdir(parents=True)
    (hub / ".agents").mkdir(parents=True)

    (hub / ".agents" / "config.yaml").write_text(
        "ocr:\n  mineru_api_token: \"secret-token\"\n  dpi: 111\n"
        "models:\n  embedding: \"my-model\"\n", encoding="utf-8")
    (topic / "config.yaml").write_text(
        "ocr:\n  mineru_api_token: \"\"\n  dpi: 130\n"
        "models:\n  embedding: \"qwen3-embedding:0.6b\"\n", encoding="utf-8")

    found = find_legacy_config(topic, hub)
    assert found == hub / ".agents" / "config.yaml"

    carried = carry_legacy_config(topic, found)
    assert set(carried) == {"ocr.mineru_api_token", "ocr.dpi", "models.embedding"}
    data = yaml.safe_load((topic / "config.yaml").read_text(encoding="utf-8"))
    assert data["ocr"]["mineru_api_token"] == "secret-token"
    assert data["ocr"]["dpi"] == 111

    # Re-running changes nothing, and a deliberate edit is never clobbered.
    assert carry_legacy_config(topic, found) == []
    from magi.core.config_edit import set_config_value
    set_config_value(topic / "config.yaml", "ocr.dpi", 150)
    assert "ocr.dpi" not in carry_legacy_config(topic, found)
    assert yaml.safe_load((topic / "config.yaml").read_text(encoding="utf-8"))["ocr"]["dpi"] == 150
