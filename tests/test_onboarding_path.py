"""The path a new workspace actually walks: init -> ingest -> compile -> search.

Each test here is a place that path used to stop without saying so.

The worst of them: once a source landed in `raw/`, nothing anywhere told the
reader to compile it. `magi sync` emitted `ingest-start` only while the
workspace was *completely* empty, and the moment a document arrived the only
remaining hint was "track them as tasks". A user who ingested eighteen papers
through the WebUI was told to file eighteen issues about them, did, and ended
up with an empty `wiki/concepts/`.
"""

import pytest

from magi.sync import FIXABLE, build_report, run_fixes


def _codes(report):
    return [h["code"] for h in report["hints_structured"]]


@pytest.fixture
def ingested(tmp_path, monkeypatch):
    """A workspace with a source in raw/ and nothing compiled from it."""
    from magi import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    (tmp_path / "raw" / "papers" / "a-paper.md").write_text(
        "---\ntitle: A Paper\n---\n\n" + "word " * 300, encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------------
# ingest -> compile
# --------------------------------------------------------------------------

def test_an_uncompiled_source_says_to_compile_it(ingested):
    report = build_report(ingested)
    assert "compile-pending" in _codes(report), (
        "raw/ has a source no reference card was made from, and the report "
        "does not mention compiling")


def test_the_compile_hint_carries_the_count(ingested):
    hint = next(h for h in build_report(ingested)["hints_structured"]
                if h["code"] == "compile-pending")
    assert hint["params"]["backlog"] == 1


def test_compiling_is_not_something_sync_fix_will_do_for_you(ingested):
    """It is an LLM authoring step, not a deterministic repair. `--fix` must
    not claim to have done it."""
    assert "compile-pending" not in FIXABLE


def test_an_empty_workspace_still_says_to_ingest_first(tmp_path):
    from magi import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    codes = _codes(build_report(tmp_path))
    assert "ingest-start" in codes
    assert "compile-pending" not in codes


def test_task_tracking_is_not_suggested_when_tasks_are_off(ingested, monkeypatch):
    """With the feature off, `magi pm backlog-sync` needs a beads store the
    reader deliberately never created — so telling them to run it is telling
    them to go and fail."""
    monkeypatch.setattr("magi.features.feature_enabled",
                        lambda name: name != "tasks")
    codes = _codes(build_report(ingested))
    assert "backlog-untracked" not in codes
    assert "compile-pending" in codes, "the real work must still be named"


# --------------------------------------------------------------------------
# magi sync --fix ordering
# --------------------------------------------------------------------------

def test_the_task_store_is_created_before_anything_syncs_into_it(capsys):
    """The report emits melchior's hints before balthasar's, and `--fix` used
    to follow that order — so `pm backlog-sync` ran first, exited 1 because
    there was no store yet, and `magi sync --fix` reported a failure on the
    exact situation it exists to repair."""
    report = {"hints_structured": [
        {"code": "backlog-untracked", "text": "", "params": {}},
        {"code": "pm-uninit", "text": "", "params": {}},
    ]}
    run_fixes(report, dry_run=True)

    out = capsys.readouterr().out
    assert out.index("magi pm init") < out.index("magi pm backlog-sync")


def test_ordering_does_not_drop_a_code_it_has_never_heard_of(capsys):
    """FIX_ORDER is about dependencies, not about being an allow-list."""
    from magi.sync import FIX_ORDER

    assert "graph-stale" in FIX_ORDER
    report = {"hints_structured": [{"code": "graph-stale", "text": "", "params": {}}]}
    ran, _ = run_fixes(report, dry_run=True)
    assert ran == 1


# --------------------------------------------------------------------------
# init -> visible
# --------------------------------------------------------------------------

def test_a_new_workspace_is_registered_immediately(tmp_path):
    """Registration used to happen only as a side effect of the first
    `magi index`, so until then the workspace was absent from /api/kb — the
    WebUI picker and the browser extension, the two surfaces for getting
    material *into* a library, could not see the library."""
    from magi import init_workspace
    from magi.kb_registry import load_registry

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])

    paths = [str(tmp_path.resolve())]
    registered = [e["path"] for e in load_registry()["kbs"].values()]
    assert any(p in registered for p in paths), registered


def test_registering_twice_does_not_make_a_second_entry(tmp_path):
    from magi import init_workspace
    from magi.kb_registry import load_registry

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T", "--force"])

    assert len(load_registry()["kbs"]) == 1


# --------------------------------------------------------------------------
# what a workspace tells git about itself
# --------------------------------------------------------------------------

@pytest.fixture
def git_workspace(tmp_path):
    """A scaffolded workspace that is also a git repo, so check-ignore works."""
    import subprocess

    from magi import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True,
                   capture_output=True)
    for rel in ("output/graph.db", "output/index.db", "output/.lint_cache.json",
                "scratch/chunk.md", "output/ingest/queue.jsonl",
                "output/radar/triage.jsonl", "wiki/concepts/.backup/a.md"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    return tmp_path


def _ignored(ws, rel):
    import subprocess

    return subprocess.run(["git", "check-ignore", "-q", rel], cwd=ws,
                          capture_output=True).returncode == 0


def test_a_new_workspace_gets_a_gitignore(git_workspace):
    """A topic workspace is a directory of markdown a researcher will very
    reasonably push somewhere, and nothing said which parts of it are
    rebuildable."""
    assert (git_workspace / ".gitignore").is_file()


@pytest.mark.parametrize("rel", ["output/graph.db", "output/index.db",
                                 "output/.lint_cache.json", "scratch/chunk.md",
                                 "wiki/concepts/.backup/a.md"])
def test_what_magi_will_make_again_is_ignored(git_workspace, rel):
    assert _ignored(git_workspace, rel), rel


@pytest.mark.parametrize("rel", ["output/ingest/queue.jsonl",
                                 "output/radar/triage.jsonl"])
def test_the_two_ledgers_that_record_decisions_are_kept(git_workspace, rel):
    """`output/` looks entirely generated and mostly is. These two are not:
    they record what a person queued, approved and rejected, and a re-run
    returns a different world rather than the same records. A blanket
    `output/` would drop both without anyone noticing until they were gone."""
    assert not _ignored(git_workspace, rel), rel


@pytest.mark.parametrize("rel", ["config.yaml", "config.md", "log.md",
                                 "wiki/concepts/_index.md"])
def test_nothing_a_person_wrote_is_ignored(git_workspace, rel):
    assert not _ignored(git_workspace, rel), rel
