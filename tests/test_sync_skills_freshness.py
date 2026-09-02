"""`magi sync` notices when a workspace's skills are older than the CLI.

A skill file is documentation of the CLI's own command surface. A copy written
by an older magi keeps naming commands that no longer exist, and the drift is
silent: the stale file is perfectly valid markdown, just wrong. It happened for
four months — a plugin pinned at an old snapshot served v1 skills the whole
time and nothing ever said so.

`skills_cmd` already computed this exactly, comparing bytes against what the
current package would write. What was missing is that nothing running
automatically ever asked. These tests hold that question in place.

Names rather than a count, deliberately: `magi skills where` reported "1
outdated", the bare number got waved off as a display quirk, and the file
behind it was a v1 skill that had survived two cleanups.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from magi import skills_cmd, sync


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A scaffolded workspace with one host's skills installed into it."""
    from magi import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    dest = tmp_path / ".claude" / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    for sk in skills_cmd.load_skills():
        target = _claude_skill_target()
        path, text = skills_cmd.files_for(sk, target, dest)[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    # `_skills_hint` only walks hosts it detects; pin detection so the test
    # does not depend on which agent CLIs happen to be on this machine.
    monkeypatch.setattr(skills_cmd, "detected_hosts",
                        lambda *a, **k: [skills_cmd.catalog(None)["claude"]])
    return tmp_path


def _claude_skill_target():
    host = skills_cmd.catalog(None)["claude"]
    return next(t for t in host.drops if t.kind == "skill")


def _hints(root: Path) -> dict[str, str]:
    got: dict[str, str] = {}
    sync._skills_hint(root, lambda code, text, **kw: got.__setitem__(code, text))
    return got


def _a_skill_file(root: Path) -> Path:
    return next((root / ".claude" / "skills").glob("*/SKILL.md"))


# --------------------------------------------------------------------------

def test_a_workspace_whose_skills_match_says_nothing(project):
    assert _hints(project) == {}


def test_a_copy_from_an_older_magi_is_reported_by_name(project):
    """A count is dismissible. A path is not."""
    stale = _a_skill_file(project)
    stale.write_text(stale.read_text(encoding="utf-8") + "\nan older line\n",
                     encoding="utf-8")

    got = _hints(project)
    assert "skills-stale" in got
    assert stale.relative_to(project).as_posix() in got["skills-stale"]
    assert "magi install" in got["skills-stale"]


def test_a_copy_with_no_origin_mark_is_not_answered_with_run_install(project):
    """`magi install` treats an unmarked file as the person's own and refuses
    to overwrite it, so "run install" would be advice that cannot work. This
    is the shape the real leftover had: a v1 `radar_review` that install would
    not replace and uninstall would not remove."""
    frozen = _a_skill_file(project)
    frozen.write_text(
        frozen.read_text(encoding="utf-8").replace(skills_cmd.ORIGIN_MARK,
                                                   "origin: mine"),
        encoding="utf-8")

    got = _hints(project)
    assert "skills-unmanaged" in got
    assert "skills-stale" not in got, "install cannot fix this one"
    assert frozen.relative_to(project).as_posix() in got["skills-unmanaged"]


def test_a_skill_this_workspace_never_installed_is_not_called_stale(project):
    """Absent is not outdated — a workspace may deliberately carry only some."""
    shutil.rmtree(_a_skill_file(project).parent)
    assert _hints(project) == {}


def test_outside_a_project_the_check_asks_nothing():
    got: dict = {}
    sync._skills_hint(None, lambda code, text, **kw: got.__setitem__(code, text))
    assert got == {}


def test_sync_itself_asks_the_question(project):
    """Through `build_report`, not by calling the helper.

    Every other test here hands the root to `_skills_hint` directly, which
    proves the function works and proves nothing about whether anything calls
    it — delete the one line in `build_report` and they all stay green. That
    is the failure design-v2 §4 names: a check written at a layer that cannot
    be wrong, while the six call sites that were never wired go untested and
    the feature does not exist.
    """
    stale = _a_skill_file(project)
    stale.write_text(stale.read_text(encoding="utf-8") + "\nan older line\n",
                     encoding="utf-8")

    report = sync.build_report(project)
    codes = {h["code"] for h in report["hints_structured"]}
    assert "skills-stale" in codes, "sync computed it but never asked"
    assert any(stale.name in h for h in report["hints"])


def test_the_check_never_takes_sync_down(project, monkeypatch):
    """`sync` is what the session-start hook and `--close` both run. A
    convenience check that raises would take the gate with it."""
    monkeypatch.setattr(skills_cmd, "load_skills",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert _hints(project) == {}
