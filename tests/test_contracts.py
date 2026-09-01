"""Contract locks: CLI --json shapes == WebUI API responses (== future MCP).

These tests exist to stop contract drift structurally: if either side
reshapes a payload, a lock here goes red before a user notices.
"""

from __future__ import annotations

import argparse
import re

import pytest
from fastapi.testclient import TestClient

from magi import cli, retrieval
from magi.radar import pending_names, scan_reports
from magi.sync import build_report
from magi.ui.api import create_app

def _emitted_hint_codes() -> set[str]:
    """Every hint code `magi sync` can emit, read out of its own source.

    This used to be a hand-copied set, which is a fourth place the same list
    lived. `radar-harvest-overdue` shipped in neither the copy nor the WebUI's
    HINT_ACTIONS table, so the guard below passed without ever seeing it and
    an overdue radar rendered untranslated English prose in a <code> element
    with nothing to click — while `radar-harvest` sat in the ops whitelist the
    whole time. Deriving the set means adding a hint to sync.py now fails here
    until the UI knows what to do with it.
    """
    import inspect
    import re

    from magi import sync

    codes = set(re.findall(r'_hint\(\s*"([a-z0-9-]+)"', inspect.getsource(sync)))
    assert codes, "no hint codes found — did _hint()'s call shape change?"
    return codes


KNOWN_HINT_CODES = _emitted_hint_codes()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGI_CONFIG_HOME", str(tmp_path / "cfg"))
    ws = tmp_path / "topic"
    (ws / "wiki" / "concepts").mkdir(parents=True)
    (ws / "inbox" / "radar").mkdir(parents=True)
    (ws / "config.yaml").write_text("topic: contract\n", encoding="utf-8")
    (ws / "wiki" / "concepts" / "alpha.md").write_text(
        "---\ntitle: alpha\ntype: concept\n---\n\n"
        "稀疏注意力降低复杂度。attention lowers complexity.\n",
        encoding="utf-8",
    )
    (ws / "inbox" / "radar" / "2026-08-18-digest.md").write_text(
        "---\nstatus: pending-review\n---\n# digest\n", encoding="utf-8")
    (ws / "inbox" / "radar" / "2026-08-18-citation-gaps.md").write_text(
        "---\nstatus: pending-review\n---\n# gaps\n", encoding="utf-8")
    args = argparse.Namespace(topic_dir=str(ws), no_vectors=True)
    assert retrieval.cmd_index(args) == 0
    return ws


def test_search_payload_identical_cli_vs_api(workspace):
    cli_payload = retrieval.run_search(
        "attention", mode="bm25", k=5, scope="local", topic_dir=str(workspace))
    assert cli_payload["results"], "fixture must produce at least one hit"

    client = TestClient(create_app())
    res = client.get(
        f"/api/workspace/search?q=attention&mode=bm25&limit=5&scope=local&workspace={workspace}")
    assert res.status_code == 200
    api_payload = res.json()

    # The API adds exactly one field (workspace); everything else must be
    # byte-identical in shape AND content to `magi search --json`.
    assert api_payload.pop("workspace")
    assert api_payload == cli_payload


def test_search_api_supports_cli_filters(workspace):
    client = TestClient(create_app())
    res = client.get(
        "/api/workspace/search?q=attention&mode=bm25&limit=5&scope=local"
        f"&collection=concepts&path=wiki/concepts/al*&workspace={workspace}")
    data = res.json()
    assert data["results"]
    assert all(r["collection"] == "concepts" for r in data["results"])

    res = client.get(
        "/api/workspace/search?q=attention&mode=bm25&limit=5&scope=local"
        f"&path=raw/nothing*&workspace={workspace}")
    assert res.json()["results"] == []


def test_hints_dual_track(workspace):
    rep = build_report(workspace)
    assert "hints_structured" in rep
    # text track is byte-identical to the legacy strings contract
    assert [h["text"] for h in rep["hints_structured"]] == rep["hints"]
    # every code is known (frontend HINT_ACTIONS + i18n must cover these)
    assert all(h["code"] in KNOWN_HINT_CODES for h in rep["hints_structured"])
    codes = {h["code"] for h in rep["hints_structured"]}
    assert "radar-digests-pending" in codes
    assert "radar-gaps-pending" in codes


def test_frontend_covers_all_hint_codes(workspace):
    client = TestClient(create_app())
    js = client.get("/app.js").text
    for code in KNOWN_HINT_CODES:
        assert f'"{code}"' in js, f"HINT_ACTIONS missing mapping for {code}"


def test_radar_reports_single_source_of_truth(workspace):
    reports = scan_reports(workspace)
    assert pending_names(reports, "digest") == ["2026-08-18-digest.md"]
    assert pending_names(reports, "citation-gap") == ["2026-08-18-citation-gaps.md"]

    client = TestClient(create_app())
    api = client.get(f"/api/workspace/radar?workspace={workspace}").json()
    assert api["pending_digests"] == pending_names(reports, "digest")
    assert api["pending_citation_gaps"] == pending_names(reports, "citation-gap")
    kinds = {d["name"]: d["kind"] for d in api["digests"]}
    assert kinds["2026-08-18-citation-gaps.md"] == "citation-gap"


# --------------------------------------------------------------------------
# Every WebUI button has to be a command the CLI will actually accept.
# `wiki reindex`, `link` and `stats` each shipped an argv the parser rejected
# with exit 2 — the button just went red with an argparse usage line in the log.
# --------------------------------------------------------------------------

def _cli_usage(argv):
    """`magi <argv> --help`, captured. SystemExit(0) proves the path dispatches."""
    import contextlib
    import io as _io

    from magi import cli as magi_cli

    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        # cli.main normalizes argparse's SystemExit into a return code.
        rc = magi_cli.main([a for a in argv if not a.startswith("-")] + ["--help"])
    assert rc == 0, f"magi {' '.join(argv)} --help exited {rc}"
    return buf.getvalue()


def _unfilled_positionals(usage: str, argv) -> list[str]:
    """Required arguments left over once the op's own argv is accounted for."""
    import re

    named = set(argv)

    text = " ".join(usage.split("\n\n")[0].split())
    text = text.split("usage:", 1)[-1].strip()
    # Leading bare words are the prog name ("magi pm backlog-sync" — note the
    # hyphen, so this has to be tokenwise); the spec starts at the first token
    # that opens a bracket, a brace, or a flag.
    tokens = text.split()
    for i, tok in enumerate(tokens):
        if tok[0] in "[{-":
            tokens = tokens[i:]
            break
    else:
        tokens = []
    spec = re.sub(r"\[[^\[\]]*\]", " ", " ".join(tokens))   # drop optionals
    leftover = [tok for tok in spec.split() if tok not in ("...", "|")]
    # A word the op already passes is satisfied, whether it lands as a plain
    # positional or as one of a {choices} subcommand group.
    return [tok for tok in leftover
            if tok not in named
            and not (tok.startswith("{") and named & set(tok.strip("{}").split(",")))]


@pytest.mark.parametrize("op", sorted(__import__("magi.ui.jobs", fromlist=["OPS"]).OPS))
def test_every_webui_op_is_a_command_the_cli_accepts(op):
    from magi.ui.jobs import OPS

    argv = OPS[op]["argv"]
    leftover = _unfilled_positionals(_cli_usage(argv), argv)
    assert not leftover, (
        f"op '{op}' runs `magi {' '.join(argv)}` but the parser still requires "
        f"{leftover} — the job exits 2 before doing anything"
    )


#: Verbs a module implements that `cli.py` deliberately does not route.
#: `batch-list`, `batch-decide` and `batch-commit` were retired in favour of
#: the single `magi ingest review`, which delegates to them (`cli.py:51`).
_INTERNAL_ONLY = {
    "magi.ingest.batch": {"list", "decide", "commit"},
}

#: Modules that advertise no verbs to ask for: `magi.state` dispatches on
#: `argv[0]` with an if-chain (`state.py:1635`), so there is no parser to
#: interrogate. Listed rather than skipped, so that a module which grows a
#: real subparser has to be looked at instead of quietly falling out of the
#: check.
_ADVERTISES_NOTHING = {"magi.state"}

_CHOICES_RE = re.compile(r"(?:choose from|expected one of) ([^)\n]*)")


def _advertised_verbs(module: str) -> set[str]:
    """The verbs this module's own front door names, asked of the module.

    Reading `add_parser(...)` out of the source instead reports verbs nested
    one level down — `wiki-summary` is under `stats`, not a top-level choice
    of `magi.kb.llmwiki` — so the answer has to come from the dispatcher.
    """
    import contextlib
    import importlib
    import io

    main = importlib.import_module(module).main
    err, out = io.StringIO(), io.StringIO()
    with contextlib.suppress(SystemExit), contextlib.redirect_stderr(err), \
            contextlib.redirect_stdout(out):
        main(["__no_such_verb__"])
    found = _CHOICES_RE.search(err.getvalue() + out.getvalue())
    if not found:
        return set()
    return {word.strip().strip("'\"") for word in found.group(1).split(",")
            if word.strip()}


@pytest.mark.parametrize("module", sorted({
    module for (module, argv, _help) in cli._COMMANDS.values() if argv}))
def test_every_verb_a_module_advertises_is_reachable_through_magi(module):
    """`cli._COMMANDS` is a second, hand-written copy of every command, so a
    verb added to a module's own dispatcher but not to that table is fully
    implemented and unreachable — which is exactly how `magi kb prune` first
    shipped, with its subparser wired and `magi kb prune` still unknown.

    The other direction too: a route to a verb the module no longer has fails
    only when somebody runs it.
    """
    routed = {argv[0] for (mod, argv, _help) in cli._COMMANDS.values()
              if mod == module and argv}
    advertised = _advertised_verbs(module)
    if module in _ADVERTISES_NOTHING:
        assert not advertised, (
            f"{module} now advertises {sorted(advertised)} — take it out of "
            "_ADVERTISES_NOTHING and let the check cover it")
        return
    assert advertised, f"{module} advertises nothing; _ADVERTISES_NOTHING?"
    assert advertised == routed | _INTERNAL_ONLY.get(module, set())


def test_no_module_is_excused_for_a_verb_it_no_longer_has():
    """The ledgers are checked from their own side as well: an excuse that has
    outlived the thing it excused is how a check quietly stops covering."""
    for module, verbs in _INTERNAL_ONLY.items():
        advertised = _advertised_verbs(module)
        stale = verbs - advertised
        assert not stale, f"{module} no longer has {sorted(stale)}"
    for module in _ADVERTISES_NOTHING:
        assert module in {m for (m, argv, _h) in cli._COMMANDS.values() if argv}


def test_no_test_imports_the_repository_root_as_a_package():
    """The suite must pass under the command CI actually runs.

    CI runs `uv run pytest tests -q`. Every local check in this project ran
    `python -m pytest`, and `-m` puts the working directory on `sys.path`
    while a bare `pytest` does not. So `from tests import …` resolved here and
    raised `ModuleNotFoundError` there — green on every machine that mattered
    to the person checking, red on the one that gates the release. It stopped
    v2.0.0 at the test step, which is the workflow doing its job, but the
    difference had been sitting there unnoticed because nobody ran the other
    command.

    There is no `tests/__init__.py`, so pytest puts `tests/` itself on the
    path under either invocation: a sibling test module is imported by its
    bare name. Anything that reaches for `tests.` needs the root, and the root
    is exactly what the two commands disagree about.
    """
    import re
    from pathlib import Path

    offenders = []
    for path in sorted((Path(__file__).resolve().parent).glob("test_*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"\s*(from tests(\.|\s+import)|import tests(\s|$|\.))", line):
                offenders.append(f"{path.name}:{number}: {line.strip()}")

    assert not offenders, (
        "these need the repository root on sys.path, which `pytest tests -q` "
        "does not provide — import the sibling module by its bare name:\n  "
        + "\n  ".join(offenders))
