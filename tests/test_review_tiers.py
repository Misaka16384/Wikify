"""The 2026-09-03 review contract: four verdicts, the strong tier, a fallback host.

One day of real use produced the numbers these tests encode. Twelve verdicts
from the cheap tier found one useful remark and waved four substantive errors
through, reporting line numbers it had not read; the strong tier found the one
real proof gap. Five interruptions of the person, four of them over wording
the reviewer agreed with. Four calls failed on one vendor's quota while two
other CLIs sat idle.

So: the last link of the model chain is `strong`, a verdict may be `restate`
and go back to the author rather than to a person, a host that does not
answer is not the end of the review, and the post says which tier answered so
a later reader can weigh it. No test here runs a real CLI.
"""

import subprocess

import pytest

from magi import review, state
from magi.core import hosts, vocab
from magi.kb import threads


@pytest.fixture(autouse=True)
def installed(monkeypatch):
    monkeypatch.setattr(review, "installed_hosts",
                        lambda *_a, **_k: ["claude", "codex", "antigravity"])


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    return tmp_path


def solved(ws, slug="p-gap", author="claude"):
    # With a bet, so the line is not "spoken for" by a missing prediction and
    # `next` still routes ordinary work on it.
    path = threads.create(ws / "threads" / f"{slug}.md", vocab.PROPOSITION,
                          "The gap survives", "Decide before a month of numerics.",
                          extra={"bet": "supported"})
    threads.set_status(path, "testing", "started", host=author)
    threads.set_status(path, "supported", "converged", host=author)
    return path


def answer(verdict, reason="drafts/x.md line 12 says so.", checked=None, assumption=None):
    lines = [f"VERDICT: {verdict}"]
    if checked:
        lines.append(f"CHECKED: {checked}")
    if assumption:
        lines.append(f"ASSUMPTION: {assumption}")
    lines.append(f"REASON: {reason}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# the tier
# --------------------------------------------------------------------------

def test_nothing_configured_means_the_strong_tier():
    """The cheap tier was measured manufacturing confidence. The default is
    the reader that reads."""
    claude = hosts.catalog()["claude"]
    assert claude.pick_model() == claude.strong == "opus"
    assert hosts.catalog()["antigravity"].pick_model() == "gemini-3.8-flash-high"


def test_the_strong_tier_brings_its_own_effort_and_a_pinned_model_does_not():
    """`opus` at `high` is the reader that found the gap. Somebody who pinned
    `haiku` asked for a cheap call and should not be handed `--effort high`
    on top of it."""
    claude = hosts.catalog()["claude"]
    assert claude.pick_effort(model=claude.pick_model()) == "high"
    assert claude.pick_effort(model="haiku") == ""
    assert claude.pick_effort("low", model=claude.strong) == "low"


def test_codex_has_no_strong_model_but_a_strong_effort():
    """Its ids are dated and it lists nothing, so no model is written down; its
    own default is its strongest, and the tier is "no flag, high effort"."""
    codex = hosts.catalog()["codex"]
    assert codex.strong == ""
    assert codex.pick_model() == ""
    assert codex.pick_effort(model="") == "high"
    assert "model_reasoning_effort=high" in codex.headless("q", "", "high")


def test_a_model_is_classified_by_the_record():
    claude = hosts.catalog()["claude"]
    assert claude.tier_of("opus") == "strong"
    assert claude.tier_of("haiku") == "cheap"
    assert claude.tier_of("sonnet") == "pinned"
    assert claude.tier_of("") == "default"


def test_the_cheap_tier_is_still_there_by_name():
    """Cancelling the default is not removing the option."""
    claude = hosts.catalog()["claude"]
    assert claude.cheap == "haiku"
    assert claude.pick_model("haiku") == "haiku"


def test_plan_resolves_effort_against_the_model_it_picked():
    entry, model, effort = review.plan("claude")
    assert (model, effort) == ("opus", "high")
    entry, model, effort = review.plan("claude", model="haiku")
    assert (model, effort) == ("haiku", "")


def test_allow_run_adds_the_hosts_own_flag_and_nothing_where_there_is_none():
    claude = hosts.catalog()["claude"]
    assert claude.headless("q", allow_run=True)[-2:] == ["--allowedTools", "Bash"]
    assert "--allowedTools" not in claude.headless("q")
    agy = hosts.catalog()["antigravity"]
    assert not agy.can_run
    assert agy.headless("q", allow_run=True) == agy.headless("q")


# --------------------------------------------------------------------------
# the reply
# --------------------------------------------------------------------------

def test_restate_is_a_verdict():
    verdict, parts = review.parse_reply(answer("restate", "line 3 says 'all h'; the proof does h=1."))
    assert verdict == review.VERDICT_RESTATE
    assert "all h" in parts["REASON"]


def test_the_checked_and_assumption_sections_are_read_whatever_their_order():
    """Models put the sections in their own order; each runs to the next
    label, not to the end of the text."""
    text = ("VERDICT: stands\n"
            "REASON: drafts/d.md:40 carries the step.\n"
            "CHECKED: recomputed eq. 7, got 3/2 as written.\n"
            "ASSUMPTION: the support algebra is GNVW's; a local variant gives the same index.\n")
    verdict, parts = review.parse_reply(text)
    assert verdict == review.VERDICT_STANDS
    assert parts["REASON"] == "drafts/d.md:40 carries the step."
    assert parts["CHECKED"].startswith("recomputed eq. 7")
    assert parts["ASSUMPTION"].startswith("the support algebra")


def test_a_missing_section_is_absent_not_invented():
    _verdict, parts = review.parse_reply(answer("stands"))
    assert "CHECKED" not in parts and "ASSUMPTION" not in parts


def test_the_prompt_asks_for_the_check_and_the_assumption_and_names_the_four_words():
    prompt = review.build_prompt("/w", "p")
    for word in review.VERDICTS:
        assert f"- {word}:" in prompt
    assert "CHECKED:" in prompt and "ASSUMPTION:" in prompt
    # Discussion is commentary; only drafts and raw ground a refutation.
    assert "Discussion" in prompt and "`drafts/` and `raw/`" in prompt
    # The template line must not read as an answer.
    assert review.parse_verdict(prompt)[0] == review.VERDICT_UNCLEAR


def test_parse_verdict_still_returns_the_pair_it_always_did():
    assert review.parse_verdict(answer("refuted", "no."))[0] == review.VERDICT_REFUTED


# --------------------------------------------------------------------------
# what a verdict does
# --------------------------------------------------------------------------

def test_restate_goes_back_to_the_author_not_to_a_person(ws):
    """The reviewer agreed with the conclusion and not with the words. That
    is `testing`, for the author to fix — never `disputed`."""
    path = solved(ws)
    result = review.Verdict(slug="p-gap", verdict=review.VERDICT_RESTATE,
                            reason="title says all h; proof does h=1", host="codex",
                            model="", effort="high", tier="default")
    line = review.apply_verdict(ws, result)
    note = threads.read_note(path)
    assert note.status == "testing"
    assert "restate" in line and "supported" in line
    assert note.posts[-1].host == vocab.REVIEWER
    assert note.posts[-1].text.startswith("VERDICT: restate")
    assert not [item for item in state.load(ws).queue if item.kind == "disputed"]


def test_a_restated_claim_is_on_the_authors_list_until_they_act(ws):
    path = solved(ws)
    review.apply_verdict(ws, review.Verdict(slug="p-gap", verdict=review.VERDICT_RESTATE,
                                            reason="r", host="codex"))
    assert review.restating(ws) == ["p-gap"]
    threads.append_post(path, "fixed the quantifier", host="claude")
    assert review.restating(ws) == []


def test_restating_shows_up_in_next_ahead_of_the_rest_of_the_work(ws):
    solved(ws)
    review.apply_verdict(ws, review.Verdict(slug="p-gap", verdict=review.VERDICT_RESTATE,
                                            reason="r", host="codex"))
    actions = state.candidates(state.load(ws))
    keys = [a.key for a in actions]
    assert "restate" in keys
    assert keys.index("restate") < keys.index("work")
    assert actions[keys.index("restate")].cost == "llm"


def test_re_supporting_after_a_restate_asks_for_a_review_again(ws):
    path = solved(ws)
    review.apply_verdict(ws, review.Verdict(slug="p-gap", verdict=review.VERDICT_RESTATE,
                                            reason="r", host="codex"))
    assert review.pending(ws) == []
    threads.set_status(path, "supported", "reworded", host="claude")
    assert review.pending(ws) == ["p-gap"]


def test_the_post_says_host_model_effort_and_tier(ws):
    path = solved(ws)
    review.apply_verdict(ws, review.Verdict(
        slug="p-gap", verdict=review.VERDICT_STANDS, reason="fine", host="claude",
        model="opus", effort="high", tier="strong", checked="recomputed eq. 7",
        assumption="GNVW support algebra; a local variant survives"))
    text = threads.read_note(path).posts[-1].text
    assert "reviewed headless by claude · model opus · effort high · strong tier" in text
    assert "Checked: recomputed eq. 7" in text
    assert "Load-bearing: GNVW" in text


def test_a_cheap_tier_verdict_is_listed_as_weak_and_a_strong_one_is_not(ws):
    solved(ws)
    review.apply_verdict(ws, review.Verdict(slug="p-gap", verdict=review.VERDICT_STANDS,
                                            reason="fine", host="claude", model="haiku",
                                            tier="cheap"))
    assert review.pending(ws) == []
    assert review.weakly_reviewed(ws) == ["p-gap"]
    solved(ws, "p-two")
    review.apply_verdict(ws, review.Verdict(slug="p-two", verdict=review.VERDICT_STANDS,
                                            reason="fine", host="claude", model="opus",
                                            tier="strong"))
    assert review.weakly_reviewed(ws) == ["p-gap"]


def test_an_old_post_with_no_tier_is_not_called_weak(ws):
    """Putting a library's whole history on the list the day the feature
    shipped would be noise, and noise is how a list stops being read."""
    path = solved(ws)
    threads.append_post(path, "VERDICT: stands\n\nfine\n\n(reviewed headless by claude)",
                        host=vocab.REVIEWER)
    assert review.weakly_reviewed(ws) == []


def test_next_offers_a_strong_reader_for_a_weakly_reviewed_claim(ws):
    """One item for the person naming every such claim, not one per claim:
    which of them deserves a second, stronger reader is their call."""
    solved(ws)
    review.apply_verdict(ws, review.Verdict(slug="p-gap", verdict=review.VERDICT_STANDS,
                                            reason="fine", host="claude", model="haiku",
                                            tier="cheap"))
    actions = state.candidates(state.load(ws))
    offered = [a for a in actions if a.key == "reread"]
    assert len(offered) == 1 and offered[0].cost == "human"
    assert "cheap tier" in offered[0].why and "p-gap" in offered[0].why
    assert offered[0].run == "magi review <slug>"
    assert not [a for a in actions if a.key == "review" and a.slug == "p-gap"]


def test_the_close_report_lists_weak_and_restating_without_blocking(ws):
    solved(ws)
    review.apply_verdict(ws, review.Verdict(slug="p-gap", verdict=review.VERDICT_STANDS,
                                            reason="fine", host="claude", model="haiku",
                                            tier="cheap"))
    solved(ws, "p-two")
    review.apply_verdict(ws, review.Verdict(slug="p-two", verdict=review.VERDICT_RESTATE,
                                            reason="r", host="codex"))
    report = state.close(ws, write=False)
    assert report.ok
    assert report.weakly_reviewed == ["p-gap"]
    assert report.restating == ["p-two"]
    text = state.render_close(report)
    assert "cheap tier" in text and "restating" in text


# --------------------------------------------------------------------------
# who is asked, and who is asked next
# --------------------------------------------------------------------------

def test_the_author_is_read_off_the_claim(ws):
    solved(ws, author="codex")
    assert review.author_of(threads.read_note(ws / "threads" / "p-gap.md")) == "codex"


def test_a_signature_that_is_not_a_host_is_nobodys_vendor(ws):
    solved(ws, author="human")
    assert review.author_of(threads.read_note(ws / "threads" / "p-gap.md")) is None


def test_reviewers_puts_the_pick_first_then_the_others_then_the_author():
    order = review.reviewers("claude", installed=["claude", "codex", "antigravity"])
    assert order == ["codex", "antigravity", "claude"]


def test_a_configured_host_that_is_missing_does_not_empty_the_list():
    """`main` has already told the person. The claim is still better read by
    the second choice than by nobody."""
    order = review.reviewers("claude", installed=["claude", "codex"], configured="qwen")
    assert order == ["codex", "claude"]


def test_a_host_that_fails_is_followed_by_the_next_and_the_post_says_so(ws, monkeypatch):
    solved(ws)
    asked = []

    def fake_ask(host, prompt, cwd, model=None, timeout=300, effort=None,
                 settings=None, allow_run=False):
        asked.append(host)
        if host == "codex":
            raise RuntimeError("codex exited 1: quota exceeded")
        return answer("stands")

    monkeypatch.setattr(review, "ask", fake_ask)
    result = review.review(ws, "p-gap", author="claude")
    assert asked == ["codex", "antigravity"]
    assert result.host == "antigravity"
    assert result.fell_back == [("codex", "RuntimeError: codex exited 1: quota exceeded")]
    line = review.signature(result)
    assert "antigravity" in line and "codex was asked first and failed" in line


def test_a_fallback_host_walks_its_own_model_chain(ws, monkeypatch):
    """`--model opus` means nothing to agy. The fallback gets its own tier."""
    solved(ws)
    seen = {}

    def fake_ask(host, prompt, cwd, model=None, timeout=300, effort=None,
                 settings=None, allow_run=False):
        seen[host] = model
        if host == "codex":
            raise subprocess.TimeoutExpired(cmd="codex", timeout=300)
        return answer("stands")

    monkeypatch.setattr(review, "ask", fake_ask)
    result = review.review(ws, "p-gap", author="claude", model="gpt-5-codex")
    assert seen["codex"] == "gpt-5-codex"
    assert seen["antigravity"] == "gemini-3.8-flash-high"
    assert result.fell_back[0][1] == "timed out after 300s"


def test_when_every_host_fails_nothing_is_written(ws, monkeypatch):
    path = solved(ws)
    monkeypatch.setattr(review, "ask", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(RuntimeError, match="no reviewer answered"):
        review.review(ws, "p-gap", author="claude")
    assert all(post.host != vocab.REVIEWER for post in threads.read_note(path).posts)
    assert review.pending(ws) == ["p-gap"]


def test_a_batch_stops_asking_a_host_that_failed_once(ws, monkeypatch):
    solved(ws, "p-one")
    solved(ws, "p-two")
    asked = []

    def fake_ask(host, prompt, cwd, model=None, timeout=300, effort=None,
                 settings=None, allow_run=False):
        asked.append(host)
        if host == "codex":
            raise RuntimeError("quota")
        return answer("stands")

    monkeypatch.setattr(review, "ask", fake_ask)
    results = review.review_batch(ws, ["p-one", "p-two"], author="claude")
    assert [r.host for r in results] == ["antigravity", "antigravity"]
    assert asked.count("codex") == 1


def test_every_attempt_is_in_the_ledger_with_its_tier(ws, monkeypatch):
    from magi.core import ledger

    solved(ws)

    def fake_ask(host, prompt, cwd, model=None, timeout=300, effort=None,
                 settings=None, allow_run=False):
        if host == "codex":
            raise RuntimeError("quota")
        return answer("stands")

    monkeypatch.setattr(review, "ask", fake_ask)
    review.review(ws, "p-gap", author="claude")
    rows = ledger.entries(ws)
    assert [(r["host"], r["ok"]) for r in rows] == [("codex", False), ("antigravity", True)]
    assert rows[1]["tier"] == "strong"
    assert ledger.summary(ws)["failed"] == 1


def test_the_switch_is_the_only_refusal(ws, monkeypatch):
    from magi.core import ledger

    solved(ws)
    monkeypatch.setattr(review, "ask", lambda *a, **k: answer("stands"))
    for _ in range(45):
        review.review(ws, "p-gap", author="claude")
    assert ledger.summary(ws)["spent"] == 45
    with pytest.raises(ledger.SwitchedOff):
        review.review(ws, "p-gap", author="claude",
                      settings=review.Settings(enabled=False))


# --------------------------------------------------------------------------
# a host that keeps its own clock
#
# Reported from real use on 2026-09-03: `agy --print-timeout` defaults to 5m0s
# and MAGI never passed it, so raising TIMEOUT to 600 did nothing — two real
# reviews died at ~310 s and fell through to another vendor. With the flag the
# same two finished in 214 s and 373 s.
# --------------------------------------------------------------------------

def test_a_host_with_its_own_ceiling_is_told_the_number_magi_is_waiting():
    agy = hosts.catalog()["antigravity"]
    assert agy.keeps_its_own_clock
    argv = agy.headless("Q", "gemini-3.8-flash-high", "", timeout=900)
    assert argv[-2:] == ["--print-timeout", "900s"], "Go duration syntax"
    assert "--print-timeout" not in agy.headless("Q", "gemini-3.8-flash-high", "")


def test_a_host_without_one_is_unchanged():
    claude = hosts.catalog()["claude"]
    assert not claude.keeps_its_own_clock
    assert claude.headless("Q", "opus", "high", timeout=900) == \
        claude.headless("Q", "opus", "high")


def test_a_config_record_can_declare_its_own_clock():
    entry = hosts.host_from({
        "key": "mycli", "bin": "mycli", "marker": "{home}/.mycli",
        "drops": [{"global_dir": "{home}/.mycli/skills"}],
        "argv": ["{bin}", "-p", "{prompt}"],
        "timeout_argv": ["--wait", "{timeout}"],
    })
    assert entry.headless("Q", timeout=120)[-2:] == ["--wait", "120"]


def test_magi_waits_longer_than_the_host_it_set(ws, monkeypatch):
    """Two clocks on the same second race. The host's should win: it knows it
    gave up, says so in its own words, and may have printed something first."""
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"] = argv
        seen["timeout"] = kw.get("timeout")
        return __import__("types").SimpleNamespace(returncode=0, stdout="VERDICT: stands\nREASON: ok", stderr="")

    monkeypatch.setattr(review.shutil, "which", lambda *a, **k: None)
    monkeypatch.setattr(review.subprocess, "run", fake_run)
    review.ask("antigravity", "Q", cwd=ws, model="gemini-3.8-flash-high", timeout=600)
    assert "--print-timeout" in seen["argv"] and "600s" in seen["argv"]
    assert seen["timeout"] == 600 + review._CLOCK_MARGIN

    review.ask("claude", "Q", cwd=ws, model="opus", timeout=600)
    assert seen["timeout"] == 600, "a host with no clock of its own gets no margin"


# --------------------------------------------------------------------------
# --no-fallback
# --------------------------------------------------------------------------

def test_no_fallback_asks_one_host_and_stops():
    order = review.reviewers("claude", installed=["claude", "codex", "antigravity"],
                             configured="antigravity", fallback=False)
    assert order == ["antigravity"]


def test_no_fallback_still_refuses_a_host_that_is_not_installed():
    assert review.reviewers("claude", installed=["claude"], configured="qwen",
                            fallback=False) == []


def test_without_fallback_a_failure_is_a_failure(ws, monkeypatch):
    """The comparison this exists for: a verdict labelled `antigravity` that
    Claude actually produced is worse than no row at all."""
    solved(ws)
    asked = []

    def fake_ask(host, prompt, cwd, model=None, timeout=None, effort=None,
                 settings=None, allow_run=False):
        asked.append(host)
        raise RuntimeError("quota")

    monkeypatch.setattr(review, "ask", fake_ask)
    with pytest.raises(RuntimeError, match="no reviewer answered"):
        review.review(ws, "p-gap", author="claude", host="antigravity", fallback=False)
    assert asked == ["antigravity"], "it did not go looking for another vendor"
