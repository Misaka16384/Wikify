"""`magi review` — the second reader, and the limits on what it may do.

The rule is "记账靠近，评判远离": whoever is nearest records the state, and
somebody who does not share their context judges whether it holds. An agent
grading its own work is not a review — it was convinced once already, by the
same reasoning, and the second pass agrees for the same reasons.

So the two properties tested hardest here are about restraint rather than
capability. A rejection lands as `disputed` and stops: it is a question for a
person, not a finding, and nothing walks it back without one. And an answer
nobody can parse is `unclear`, never a pass — a broken adapter that reads as
approval is a rubber stamp, which is worse than no reviewer at all.

No test in this file runs a real CLI. What is being checked is the contract
around the call, which is the part that can be wrong in a way nobody notices.
"""

import subprocess

import pytest

from magi import review
from magi.core import vocab
from magi.kb import threads


@pytest.fixture(autouse=True)
def installed(monkeypatch):
    """What is on PATH is a fact about this machine, not about the code.

    Individual tests still override this where the point *is* what happens
    when a host is missing.
    """
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["claude", "codex"])


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    return tmp_path


def solved(ws, slug="p-gap"):
    path = threads.create(ws / "threads" / f"{slug}.md", vocab.PROPOSITION,
                          "The gap survives", "Decide before a month of numerics.")
    threads.set_status(path, "testing", "started", host="claude")
    threads.set_status(path, "supported", "converged", host="claude")
    return path


# --------------------------------------------------------------------------
# who reviews
# --------------------------------------------------------------------------

def test_the_reviewer_is_not_the_writer():
    """A different vendor is a cheap approximation of independence: another
    model, another system prompt, none of the conversation."""
    assert review.pick_host("claude", installed=["claude", "codex"]) == "codex"
    assert review.pick_host("codex", installed=["claude", "codex"]) == "claude"


def test_with_only_one_cli_it_still_runs_and_says_which(ws):
    """A fresh session with none of the conversation is not nothing. It is
    second choice, and the verdict records which one it was."""
    assert review.pick_host("claude", installed=["claude"]) == "claude"


def test_with_no_cli_at_all_nothing_is_approved():
    """The failure mode to avoid is a claim that counts as reviewed because no
    reviewer was available."""
    assert review.pick_host("claude", installed=[]) is None


def test_configuration_wins_but_only_over_something_installed():
    assert review.pick_host("claude", installed=["claude", "codex"],
                            configured="codex") == "codex"
    assert review.pick_host("claude", installed=["claude"], configured="qwen") is None


# --------------------------------------------------------------------------
# what a verdict is
# --------------------------------------------------------------------------

def test_a_clear_answer_is_read_as_given():
    verdict, reason = review.parse_verdict(
        "VERDICT: refuted\nREASON: raw/papers/x.md says p=0.11, the claim says 0.15.")
    assert verdict == review.VERDICT_REFUTED
    assert "0.11" in reason


def test_an_unparseable_answer_is_unclear_and_never_a_pass():
    """A reviewer that rambled has told us it could not answer in the required
    form. Reading that as approval is how a broken adapter becomes a rubber
    stamp."""
    verdict, reason = review.parse_verdict("I think this is probably fine, broadly.")
    assert verdict == review.VERDICT_UNCLEAR
    assert "required form" in reason


def test_an_empty_answer_is_unclear():
    assert review.parse_verdict("")[0] == review.VERDICT_UNCLEAR


# --------------------------------------------------------------------------
# what a verdict does
# --------------------------------------------------------------------------

def test_a_rejection_becomes_disputed_and_stops_there(ws):
    """`disputed` is a question for a person. `refuted` would be a finding, and
    the reviewer does not get to make findings."""
    path = solved(ws)
    review.apply_verdict(ws, review.Verdict(
        slug="p-gap", verdict=review.VERDICT_REFUTED, host="codex",
        reason="the quoted line is not in the source"))

    note = threads.read_note(path)
    assert note.status == "disputed"
    assert note.posts[-1].host == vocab.REVIEWER


def test_an_approval_posts_and_changes_nothing_else(ws):
    path = solved(ws)
    review.apply_verdict(ws, review.Verdict(
        slug="p-gap", verdict=review.VERDICT_STANDS, host="codex", reason="checks out"))

    note = threads.read_note(path)
    assert note.status == "supported"
    assert "stands" in note.posts[-1].text.lower()


def test_a_second_rejection_does_not_re_flip_an_already_disputed_note(ws):
    path = solved(ws)
    rejection = review.Verdict(slug="p-gap", verdict=review.VERDICT_REFUTED,
                               host="codex", reason="still no")
    review.apply_verdict(ws, rejection)
    review.apply_verdict(ws, rejection)

    note = threads.read_note(path)
    assert note.status == "disputed"
    assert threads.validate(note) == [], "the second verdict must not break the chain"


def test_the_verdict_says_who_gave_it(ws):
    path = solved(ws)
    review.apply_verdict(ws, review.Verdict(
        slug="p-gap", verdict=review.VERDICT_STANDS, host="gemini", reason="fine"))
    assert "gemini" in threads.read_note(path).posts[-1].text


# --------------------------------------------------------------------------
# what gets reviewed
# --------------------------------------------------------------------------

def test_only_claims_that_say_they_are_solved(ws):
    solved(ws, "p-done")
    threads.create(ws / "threads" / "p-open.md", vocab.PROPOSITION, "T", "Why.")

    assert review.pending(ws) == ["p-done"]


def test_a_claim_already_answered_is_not_asked_about_twice(ws):
    """Re-reviewing spends a call and buries the first verdict under a second
    one that says the same thing."""
    path = solved(ws)
    review.apply_verdict(ws, review.Verdict(
        slug="p-gap", verdict=review.VERDICT_STANDS, host="codex", reason="fine"))

    assert review.pending(ws) == []


def test_a_claim_re_supported_after_a_verdict_comes_back(ws):
    """The verdict was about the old evidence. New evidence is a new question."""
    path = solved(ws)
    review.apply_verdict(ws, review.Verdict(
        slug="p-gap", verdict=review.VERDICT_STANDS, host="codex", reason="fine"))
    threads.set_status(path, "testing", "found a gap in the argument", host="claude")
    threads.set_status(path, "supported", "closed it", host="claude")

    assert review.pending(ws) == ["p-gap"]


# --------------------------------------------------------------------------
# the call itself
# --------------------------------------------------------------------------

def test_the_prompt_points_at_the_note_and_forbids_the_context(ws):
    prompt = review.build_prompt(ws, "p-gap")
    assert "threads/p-gap.md" in prompt
    assert "did not write it" in prompt
    assert "VERDICT: <stands, refuted, or unclear>" in prompt
    assert "VERDICT: stands|refuted|unclear" not in prompt, (
        "the answer template must not itself read as an answer — a host that "
        "echoes the prompt would hand back an approval we wrote ourselves")


def test_a_reviewer_that_fails_leaves_the_claim_unreviewed(ws, monkeypatch):
    """A CLI that is missing, hangs or crashes must not read as approval."""
    solved(ws)

    def boom(*args, **kwargs):
        raise subprocess.SubprocessError("the CLI fell over")

    monkeypatch.setattr(review, "ask", boom)
    results = review.review_batch(ws, ["p-gap"], host="codex")

    assert results[0].verdict == review.VERDICT_UNCLEAR
    assert "could not run" in results[0].reason


def test_one_failure_does_not_stop_the_batch(ws, monkeypatch):
    solved(ws, "p-a")
    solved(ws, "p-b")
    calls = []

    def flaky(host, prompt, cwd, model=None, timeout=0, **kw):
        calls.append(prompt)
        if "p-a" in prompt:
            raise RuntimeError("nope")
        return "VERDICT: stands\nREASON: fine."

    monkeypatch.setattr(review, "ask", flaky)
    results = review.review_batch(ws, ["p-a", "p-b"], host="codex")

    assert [r.verdict for r in results] == [review.VERDICT_UNCLEAR, review.VERDICT_STANDS]
    assert len(calls) == 2


def test_the_model_flag_is_only_passed_when_asked_for():
    """Passing a model nobody configured is how an adapter starts failing with
    'unknown model' on a host that was working."""
    claude = review.catalog()["claude"]
    assert "--model" not in claude.headless("p")
    assert claude.headless("p", "haiku")[-2:] == ["--model", "haiku"]


def test_a_host_that_declares_no_headless_mode_is_not_a_reviewer():
    """opencode installs skills and its transcripts are read, but nothing here
    knows how to ask it a question. Half a host is not a reviewer, and finding
    that out mid-review is finding it out too late."""
    from magi.core import hosts

    assert "opencode" in hosts.catalog()
    assert "opencode" not in review.catalog()
    assert "opencode" not in review.host_names()


# --------------------------------------------------------------------------
# a review that did not happen
#
# The whole file is one property, and this is the half that was wrong: a
# claim stops being offered for review the moment a reviewer posts on it. So
# every path that ends in a post has to be a path where somebody actually
# read the claim. A missing binary, a timeout, a reply nobody can parse — none
# of those is a reading, and treating them as one retires the claim on the
# strength of a review that never happened.
# --------------------------------------------------------------------------

def failing(exc):
    def boom(*args, **kwargs):
        raise exc
    return boom


def test_a_review_that_could_not_run_writes_nothing(ws, monkeypatch):
    solved(ws)
    monkeypatch.setattr(review, "ask", failing(
        FileNotFoundError(2, "The system cannot find the file specified", "codex")))

    before = (ws / "threads" / "p-gap.md").read_text(encoding="utf-8")
    results = review.review_batch(ws, ["p-gap"], host="codex")
    lines = [review.apply_verdict(ws, result) for result in results]

    assert (ws / "threads" / "p-gap.md").read_text(encoding="utf-8") == before
    assert "not reviewed" in lines[0]
    assert review.pending(ws) == ["p-gap"], "still waiting for a reader"


def test_a_timeout_is_not_a_verdict(ws, monkeypatch):
    solved(ws)
    monkeypatch.setattr(review, "ask", failing(
        subprocess.TimeoutExpired(cmd="codex", timeout=300)))

    for result in review.review_batch(ws, ["p-gap"], host="codex"):
        assert not result.ran
        review.apply_verdict(ws, result)
    assert review.pending(ws) == ["p-gap"]


def test_an_unparseable_reply_is_posted_and_still_not_an_answer(ws, monkeypatch):
    """Two different things at once. The reply is evidence — a reader needs it
    to tell a broken adapter from a claim nobody can judge — but `unclear` is
    the reviewer saying it could not tell, and a non-answer must not retire the
    claim."""
    solved(ws)
    monkeypatch.setattr(review, "ask", lambda *a, **k: "I'm not sure I can help with that.")

    for result in review.review_batch(ws, ["p-gap"], host="codex"):
        review.apply_verdict(ws, result)

    note = threads.read_note(ws / "threads" / "p-gap.md")
    assert note.status == "supported"
    assert "I'm not sure I can help" in note.posts[-1].text, "the reply is quoted"
    assert review.pending(ws) == ["p-gap"]


def test_a_reviewer_that_says_nothing_at_all_is_not_a_pass(ws, monkeypatch):
    solved(ws)
    monkeypatch.setattr(review, "ask", lambda *a, **k: "")
    for result in review.review_batch(ws, ["p-gap"], host="codex"):
        review.apply_verdict(ws, result)
    assert review.pending(ws) == ["p-gap"]


def test_a_real_verdict_does_retire_the_claim(ws, monkeypatch):
    solved(ws)
    monkeypatch.setattr(review, "ask",
                        lambda *a, **k: "VERDICT: stands\nREASON: it does.")
    for result in review.review_batch(ws, ["p-gap"], host="codex"):
        review.apply_verdict(ws, result)
    assert review.pending(ws) == []


# --------------------------------------------------------------------------
# reading a verdict the way models write them
# --------------------------------------------------------------------------

def test_decoration_around_the_verdict_does_not_lose_it():
    """Bold and a trailing period are things models do constantly. Reading
    `**VERDICT: refuted**` as "unclear" throws away a refutation over
    asterisks — and, before the fix, silenced the claim for good."""
    for reply in ("**VERDICT: refuted**", "VERDICT: refuted.", "> VERDICT: refuted",
                  "- VERDICT: refuted", "VERDICT: refuted (the cited line is not there)",
                  "   VERDICT:refuted"):
        assert review.parse_verdict(reply)[0] == review.VERDICT_REFUTED, reply


def test_a_verdict_inside_a_sentence_is_still_not_a_verdict():
    assert review.parse_verdict("I would not say VERDICT: stands")[0] == \
        review.VERDICT_UNCLEAR


def test_two_different_verdicts_are_not_a_verdict():
    """There is no rule for picking the real one that does not sometimes pick
    a `stands` the reviewer went on to withdraw."""
    verdict, reason = review.parse_verdict(
        "VERDICT: stands\nREASON: fine.\n\nOn reflection:\nVERDICT: refuted")
    assert verdict == review.VERDICT_UNCLEAR
    assert "more than one verdict" in reason


# --------------------------------------------------------------------------
# what one bad slug costs the rest of the batch
# --------------------------------------------------------------------------

def test_a_verdict_on_a_note_that_cannot_be_disputed_is_still_posted(ws, monkeypatch):
    """`magi review <slug>` takes any slug, and `open → disputed` is not a
    move. The verdict was paid for; it goes where the note can be read, and
    the status is left for a person."""
    threads.create(ws / "threads" / "p-open.md", vocab.PROPOSITION,
                   "Open one", "Not started.")
    monkeypatch.setattr(review, "ask", lambda *a, **k: "VERDICT: refuted\nREASON: no.")

    result = review.review(ws, "p-open", host="codex")
    line = review.apply_verdict(ws, result)

    note = threads.read_note(ws / "threads" / "p-open.md")
    assert note.status == "open", "the status is a person's to move, not a crash"
    assert "VERDICT: refuted" in note.posts[-1].text
    assert "left at" in line


def test_one_bad_slug_does_not_discard_the_others(ws, monkeypatch):
    solved(ws, "p-a")
    solved(ws, "p-z")
    monkeypatch.setattr(review, "ask", lambda *a, **k: "VERDICT: refuted\nREASON: no.")

    # `p-nope` has no file. Verdicts are applied one at a time so its failure
    # cannot throw away the two that were paid for on either side of it.
    assert review.main(["p-a", "p-nope", "p-z", "--topic-dir", str(ws),
                        "--host", "codex"]) == 1
    for slug in ("p-a", "p-z"):
        note = threads.read_note(ws / "threads" / f"{slug}.md")
        assert note.status == "disputed", slug


def test_a_slug_with_a_separator_in_it_is_refused(ws):
    with pytest.raises(ValueError):
        review._note_path(ws, "../elsewhere/notes")


# --------------------------------------------------------------------------
# what the command reports
# --------------------------------------------------------------------------

def test_asking_for_a_host_that_is_not_installed_reviews_nothing(ws, monkeypatch, capsys):
    solved(ws)
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["claude"])
    called = []
    monkeypatch.setattr(review, "ask", lambda *a, **k: called.append(1) or "")

    code = review.main(["--topic-dir", str(ws), "--host", "codex"])

    assert code == 1 and not called
    assert "not installed" in capsys.readouterr().err
    assert review.pending(ws) == ["p-gap"]


def test_a_run_where_nothing_could_be_asked_is_a_failure(ws, monkeypatch):
    """Exiting 0 there is how a broken install looks like a reviewed library."""
    solved(ws)
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", failing(RuntimeError("codex exited 127")))
    assert review.main(["--topic-dir", str(ws), "--host", "codex"]) == 1


def test_a_reviewer_that_answered_properly_is_not_quoted_twice(ws, monkeypatch):
    """Measured against a real `codex exec` run: it answered `unclear` in the
    required form, and the post carried its sentence as the reason and again
    under "what it actually said"."""
    solved(ws)
    monkeypatch.setattr(review, "ask", lambda *a, **k: (
        "VERDICT: unclear\nREASON: the note cites no evidence at all."))

    for result in review.review_batch(ws, ["p-gap"], host="codex"):
        review.apply_verdict(ws, result)

    post = threads.read_note(ws / "threads" / "p-gap.md").posts[-1].text
    assert post.count("cites no evidence") == 1
    assert "What it actually said" not in post


# --------------------------------------------------------------------------
# what a review costs, and the two ways the budget says no
#
# The refusal has to happen *before* the subprocess. A gate that stops the call
# but lets the claim retire unreviewed would spend nothing and approve
# everything, which is the same rubber stamp this file spends the rest of its
# length avoiding.
# --------------------------------------------------------------------------

def test_a_review_is_written_into_the_ledger(ws, monkeypatch):
    from magi.core import ledger

    solved(ws)
    monkeypatch.setattr(review, "ask",
                        lambda *a, **k: "VERDICT: stands\nREASON: it does.")

    review.review(ws, "p-gap", host="codex")

    entry = ledger.entries(ws)[-1]
    assert (entry["kind"], entry["host"], entry["slug"]) == ("review", "codex", "p-gap")
    assert entry["ok"] is True


def test_a_review_that_failed_is_still_written_down(ws, monkeypatch):
    """It spent the wall clock and, on a metered account, the money. A budget
    that only counts successes is one a broken adapter walks through."""
    from magi.core import ledger

    solved(ws)
    monkeypatch.setattr(review, "ask", failing(RuntimeError("codex exited 127")))

    with pytest.raises(RuntimeError):
        review.review(ws, "p-gap", host="codex")

    entry = ledger.entries(ws)[-1]
    assert entry["ok"] is False and entry["note"] == "RuntimeError"


def test_over_budget_nothing_is_called(ws, monkeypatch):
    from magi.core import ledger

    solved(ws)
    (ws / "config.yaml").write_text("research:\n  weekly_calls: 2\n", encoding="utf-8")
    for index in range(2):
        ledger.record(ws, ledger.REVIEW, "codex", slug=f"old-{index}")
    called = []
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: called.append(1) or "")

    code = review.main(["--topic-dir", str(ws), "--host", "codex"])

    assert code == 1 and not called
    assert review.pending(ws) == ["p-gap"], "and it is still waiting for a reader"


def test_the_master_switch_stops_it_too(ws, monkeypatch, capsys):
    solved(ws)
    (ws / "config.yaml").write_text("research:\n  llm_calls: false\n", encoding="utf-8")
    called = []
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: called.append(1) or "")

    assert review.main(["--topic-dir", str(ws), "--host", "codex"]) == 1
    assert not called
    assert "switched off" in capsys.readouterr().err


def test_a_dry_run_says_what_is_left(ws, monkeypatch, capsys):
    """The one place to look before spending: who would be asked, about what,
    and how much of the week is gone."""
    import json as json_mod

    solved(ws)
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])

    review.main(["--topic-dir", str(ws), "--host", "codex", "--dry-run", "--json"])
    payload = json_mod.loads(capsys.readouterr().out)

    assert payload["slugs"] == ["p-gap"]
    assert payload["budget"]["left"] == payload["budget"]["limit"], "nothing spent yet"


def test_a_batch_stops_at_the_budget_instead_of_running_past_it(ws, monkeypatch):
    """The check was at the top of the batch and the spending was per slug, so
    one command could run sixty calls against a limit of forty. `ledger.check`
    calls itself "one call at the top of anything that spends"; the gate now
    lives in `review()`, where a new caller cannot leave it out."""
    from magi.core import ledger

    for index in range(5):
        solved(ws, f"p-{index}")
    (ws / "config.yaml").write_text("research:\n  weekly_calls: 3\n", encoding="utf-8")
    ledger.record(ws, ledger.REVIEW, "codex", slug="last-week")
    called = []
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: called.append(1) or
                        "VERDICT: stands\nREASON: fine.")

    review.main(["--topic-dir", str(ws), "--host", "codex"])

    assert len(called) == 2, "the budget was 3 and one call was already spent"
    assert ledger.spent(ws) == 3


def test_running_out_says_so_once_and_not_once_per_claim(ws, monkeypatch):
    """`OverBudget` subclasses `RuntimeError`, which `review_batch` catches to
    turn a failed review into a not-reviewed result. Caught in that order the
    loop ran on and produced one identical "budget is spent" result per
    remaining claim — and since the results then still numbered one per slug,
    nothing downstream could tell a run that stopped early from one that
    finished.

    Nothing was ever written to the notes: `apply_verdict` opens with
    `if not result.ran` and refuses to post a review that did not happen. The
    cost was the report, not the notes — which is worth stating precisely,
    because the first version of this test asserted the notes were clean and
    so passed against both implementations.
    """
    for index in range(4):
        solved(ws, f"p-{index}")
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: "VERDICT: stands\nREASON: fine.")

    results = review.review_batch(ws, [f"p-{i}" for i in range(4)], host="codex",
                                  settings=review.Settings(limit=2))

    assert len(results) == 2, "the loop kept going after the budget said no"
    assert all(r.ran for r in results), "and every result it did return is a real review"
    assert [r.slug for r in results] == ["p-0", "p-1"], "it stopped, it did not skip"


def test_it_says_which_ones_it_did_not_get_to(ws, monkeypatch, capsys):
    """A short list of results is the only sign the run stopped early, and
    counting it is not somebody's job."""
    from magi.core import ledger

    for index in range(3):
        solved(ws, f"p-{index}")
    (ws / "config.yaml").write_text("research:\n  weekly_calls: 1\n", encoding="utf-8")
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: "VERDICT: stands\nREASON: fine.")

    code = review.main(["--topic-dir", str(ws), "--host", "codex"])

    err = capsys.readouterr().err
    assert code == 1
    assert "stopped after 1 of 3" in err
    assert "still unreviewed" in err
    for slug in review.pending(ws):
        assert slug in err


def test_a_zero_limit_still_reports_what_the_week_cost(ws):
    """`OverBudget(0, limit, ...)` hardcoded the spend, so a workspace twelve
    calls into a switched-off week was told its budget was "spent (0/0)" —
    which reads as a fresh week rather than as a switch somebody threw."""
    from magi.core import ledger

    for index in range(12):
        ledger.record(ws, ledger.REVIEW, "codex", slug=f"old-{index}")

    with pytest.raises(ledger.OverBudget) as caught:
        ledger.check(ws, limit=0)

    assert caught.value.spent == 12
    assert "(12/0)" in str(caught.value)
