"""Which model, at which effort, and who decided.

design-v2 §11 says the reviewer runs on a cheap tier. Nothing implemented it:
`review_model` was free text, empty meant "that CLI's own default", and on
Claude Code that default may well be Opus. A rule that costs nothing to state
and nothing to enforce is not a rule.

So the chain has four links and this file is about where each one wins:

    --model  >  the host record  >  research.review_model  >  the cheap tier

Effort is the same shape with no cheap tier at the end, because the model id
usually carries the level already — and where it does, asking twice is only a
new way to be wrong.

The last property here is the ledger's: a review at `high` and one at `low` are
not the same call. A budget counted in calls that cannot tell them apart cannot
explain itself afterwards.
"""

import json

import pytest

from magi import review
from magi.core import hosts, ledger


CUSTOM = {
    "key": "mycli", "bin": "mycli", "marker": "{home}/.mycli",
    "drops": [{"global_dir": "{home}/.mycli/skills"}],
    "argv": ["{bin}", "-p", "{prompt}"], "model_flag": "--model",
    "effort_argv": ["--effort", "{effort}"],
}


def _host(**over):
    return hosts.host_from(dict(CUSTOM, **over))


# --------------------------------------------------------------------------
# the chain
# --------------------------------------------------------------------------

def test_nothing_configured_gets_the_strong_tier():
    """"I set nothing" means the reader that reads. It meant the cheap tier
    until 2026-09-03, when a day of real reviews showed the cheap reader
    waving substantive errors through; the last link is `strong` now, and
    `cheap` is an option somebody names."""
    assert _host(strong="mycli-max", cheap="mycli-mini").pick_model() == "mycli-max"
    assert _host(cheap="mycli-mini").pick_model() == "", "no strong tier, no guess"
    assert _host(strong="mycli-max", cheap="mycli-mini").pick_model("mycli-mini") == "mycli-mini"


def test_the_workspace_setting_beats_the_cheap_tier():
    entry = _host(cheap="mycli-mini")
    assert entry.pick_model(configured="mycli-max") == "mycli-max"


def test_the_record_beats_the_workspace_setting():
    """`research.review_model` is one string for every vendor and the host is
    picked automatically. The record is the only place that knows which CLI a
    name belongs to, so it wins."""
    entry = _host(model="mycli-exact", cheap="mycli-mini")
    assert entry.pick_model(configured="claude-sonnet-5") == "mycli-exact"


def test_the_command_line_beats_everything():
    entry = _host(model="mycli-exact", cheap="mycli-mini")
    assert entry.pick_model("asked", "configured") == "asked"


def test_effort_has_no_cheap_fallback():
    entry = _host(effort="")
    assert entry.pick_effort() == ""
    assert entry.pick_effort(configured="low") == "low"
    assert entry.pick_effort("high", "low") == "high"


# --------------------------------------------------------------------------
# the command line it builds
# --------------------------------------------------------------------------

def test_the_builtin_cheap_tiers_are_what_each_vendor_calls_them():
    table = hosts.catalog()
    assert table["claude"].cheap == "haiku", "an alias, so it cannot rot"
    assert table["antigravity"].cheap == "gemini-3.7-flash-low"
    assert table["codex"].cheap == "", (
        "Codex does not list its models and its ids are dated; a name written "
        "here becomes an unknown-model error on some future release")


def test_effort_is_a_template_not_a_flag():
    """Codex takes `-c model_reasoning_effort=<level>`, Claude Code and agy
    take `--effort <level>`. One field cannot be both, so it is the template."""
    table = hosts.catalog()
    assert table["codex"].headless("q", "", "low")[-2:] == \
        ["-c", "model_reasoning_effort=low"]
    assert table["claude"].headless("q", "", "low")[-2:] == ["--effort", "low"]


def test_a_model_that_names_its_own_effort_suppresses_the_flag():
    """agy's Gemini ids end in -low/-medium/-high. Sending both asks for two
    different things in one command."""
    agy = hosts.catalog()["antigravity"]
    assert "--effort" not in agy.headless("q", "gemini-3.7-flash-low", "high")
    assert "--effort" in agy.headless("q", "claude-sonnet-4-6", "high")
    assert hosts.names_its_effort("gemini-3.1-pro-high")
    assert not hosts.names_its_effort("claude-sonnet-4-6")


def test_a_host_with_no_effort_template_is_simply_not_asked():
    entry = hosts.host_from(dict(CUSTOM, effort_argv=[]))
    assert entry.headless("q", "", "high") == ["mycli", "-p", "q"]


# --------------------------------------------------------------------------
# what the caller resolves, and what the ledger records
# --------------------------------------------------------------------------

def test_plan_walks_the_chain_for_a_named_host():
    settings = review.Settings(model="ignored-by-the-record", effort="low")
    entry, model, effort = review.plan("claude", None, None, settings)

    assert entry.key == "claude"
    assert model == "ignored-by-the-record", "no record model, so the config wins"
    assert effort == "low"


def test_plan_reaches_the_strong_tier_when_nothing_is_set():
    _entry, model, effort = review.plan("claude", None, None, review.Settings())
    assert model == "opus"
    assert effort == "high", "the strong tier brings its own level"


def test_plan_refuses_a_host_with_no_headless_mode():
    with pytest.raises(RuntimeError):
        review.plan("opencode")


def test_the_ledger_records_the_effort_next_to_the_model(tmp_path):
    ledger.record(tmp_path, ledger.REVIEW, "claude", model="haiku", effort="low",
                  slug="p-a")
    line = json.loads(ledger.path_for(tmp_path).read_text(encoding="utf-8").strip())
    assert line["model"] == "haiku" and line["effort"] == "low"


# --------------------------------------------------------------------------
# listing what a host offers
# --------------------------------------------------------------------------

AGY_OUTPUT = (
    "Fetching available models...\n"
    "gemini-3.7-flash-low\tGemini 3.7 Flash (Low)\n"
    "gemini-3.1-pro-high\tGemini 3.1 Pro (High)\n"
    "\n"
    "claude-sonnet-4-6\tClaude Sonnet 4.6 (Thinking)\n"
)


def test_the_listing_parser_takes_what_it_recognises_and_drops_the_rest():
    """This parses another program's stdout, which is a format nobody promised
    us. Its failure has to be "fewer models than there are", never a crash that
    takes the config panel down."""
    found = hosts.parse_models(AGY_OUTPUT)

    assert [m["id"] for m in found] == [
        "gemini-3.7-flash-low", "gemini-3.1-pro-high", "claude-sonnet-4-6"]
    assert found[0]["label"] == "Gemini 3.7 Flash (Low)"
    assert hosts.parse_models("") == []
    assert hosts.parse_models("total nonsense with spaces") == []


def test_a_host_that_cannot_list_says_so_rather_than_guessing():
    assert hosts.models(hosts.catalog()["codex"])["source"] == "none"


def test_a_host_with_a_static_list_never_shells_out(monkeypatch):
    def explode(*a, **k):
        raise AssertionError("Claude Code has no listing command to call")

    monkeypatch.setattr(hosts.subprocess, "run", explode)
    answer = hosts.models(hosts.catalog()["claude"])

    assert answer["source"] == "static"
    assert [m["id"] for m in answer["models"]] == ["haiku", "sonnet", "opus"]


class _Proc:
    def __init__(self, out="", code=0):
        self.stdout, self.stderr, self.returncode = out, "", code


def test_a_live_listing_is_cached_and_then_reused(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(hosts.subprocess, "run",
                        lambda *a, **k: calls.append(1) or _Proc(AGY_OUTPUT))
    agy = hosts.catalog()["antigravity"]

    first = hosts.models(agy, home=tmp_path, now=1000.0)
    second = hosts.models(agy, home=tmp_path, now=1000.0 + hosts.MODELS_TTL - 1)

    assert first["source"] == "live" and second["source"] == "cache"
    assert len(calls) == 1
    assert (tmp_path / ".config" / "magi" / "models-antigravity.json").is_file()


def test_a_cache_older_than_a_day_is_asked_again(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(hosts.subprocess, "run",
                        lambda *a, **k: calls.append(1) or _Proc(AGY_OUTPUT))
    agy = hosts.catalog()["antigravity"]

    hosts.models(agy, home=tmp_path, now=1000.0)
    again = hosts.models(agy, home=tmp_path, now=1000.0 + hosts.MODELS_TTL + 1)

    assert again["source"] == "live"
    assert len(calls) == 2


def test_a_stale_cache_beats_nothing_when_the_listing_fails(tmp_path, monkeypatch):
    """A day-old list of real names is more use than an empty dropdown because
    the network was down for a second."""
    monkeypatch.setattr(hosts.subprocess, "run", lambda *a, **k: _Proc(AGY_OUTPUT))
    agy = hosts.catalog()["antigravity"]
    hosts.models(agy, home=tmp_path, now=1000.0)

    def fails(*a, **k):
        raise OSError("no network")

    monkeypatch.setattr(hosts.subprocess, "run", fails)
    answer = hosts.models(agy, home=tmp_path, now=1000.0 + hosts.MODELS_TTL + 1)

    assert answer["source"] == "cache" and answer["models"]
    assert "no network" in answer["error"]


def test_a_listing_that_fails_with_no_cache_is_a_text_box(tmp_path, monkeypatch):
    def fails(*a, **k):
        raise OSError("no network")

    monkeypatch.setattr(hosts.subprocess, "run", fails)
    answer = hosts.models(hosts.catalog()["antigravity"], home=tmp_path)

    assert answer["source"] == "none" and answer["models"] == []


# --------------------------------------------------------------------------
# what the panel and the dry run show
# --------------------------------------------------------------------------

def test_the_panel_can_ask_one_host_what_it_offers():
    from fastapi.testclient import TestClient

    from magi.ui.api import create_app

    answer = TestClient(create_app()).get("/api/workspace/models?host=claude")

    assert answer.status_code == 200
    body = answer.json()["hosts"]["claude"]
    assert body["cheap"] == "haiku" and body["takes_effort"] is True
    assert [m["id"] for m in body["models"]] == ["haiku", "sonnet", "opus"]


def test_the_panel_is_told_gemini_is_a_spelling_not_a_host():
    from fastapi.testclient import TestClient

    from magi.ui.api import create_app

    answer = TestClient(create_app()).get("/api/workspace/models?host=gemini")
    assert "antigravity" in answer.json()["hosts"]


def test_a_host_that_cannot_be_asked_at_all_is_a_404():
    from fastapi.testclient import TestClient

    from magi.ui.api import create_app

    answer = TestClient(create_app()).get("/api/workspace/models?host=opencode")
    assert answer.status_code == 404


# --------------------------------------------------------------------------
# what the live smoke test found
# --------------------------------------------------------------------------

def test_a_long_reason_is_cut_on_a_boundary_and_says_so():
    """The first real `agy -p` review refuted a claim correctly and cited three
    files by line. What landed in the thread stopped mid-URL, inside the third
    link — because the cut was at a fixed offset. The post is the record: `raw`
    survives only in `--json`, so the sentence naming the line that settled it
    was simply gone."""
    long = "VERDICT: refuted\nREASON: " + ("evidence " * 400)

    verdict, reason = review.parse_verdict(long)

    assert verdict == review.VERDICT_REFUTED
    assert reason.endswith("[…truncated]"), "a cut that hides itself reads as a stutter"
    assert not reason.replace(" […truncated]", "").endswith("eviden"), \
        "cut at whitespace, never mid-token"


def test_a_reason_that_fits_is_left_alone():
    _v, reason = review.parse_verdict(
        "VERDICT: stands\nREASON: raw/a.md line 9 says exactly this.")
    assert reason == "raw/a.md line 9 says exactly this."
    assert "truncated" not in reason


def test_there_is_room_for_the_citations_the_prompt_asks_for():
    """`PROMPT` asks for two or three sentences naming a file and a line. One
    such citation rendered as a link to a Windows path runs past 200 characters
    on its own, and 600 was the whole budget."""
    assert review.REASON_CHARS >= 1200
