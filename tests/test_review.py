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
    assert "VERDICT: <stands, restate, refuted, or unclear>" in prompt
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
    """A host that fails on one claim is followed by the next installed host
    for that claim, and the batch goes on. With only that one host on the
    machine the claim is `unclear` and the next one is still asked."""
    solved(ws, "p-a")
    solved(ws, "p-b")
    calls = []
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])

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
# what a review costs, and the one way it is refused
#
# There is no weekly budget any more (2026-09-03, the person's call; ledger.py
# says why). The master switch is the one refusal left, and it has to happen
# *before* the subprocess: a gate that stops the call but lets the claim retire
# unreviewed would spend nothing and approve everything, which is the same
# rubber stamp this file spends the rest of its length avoiding.
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



def test_the_switch_stops_a_batch_at_the_first_claim_not_once_per_claim(ws, monkeypatch):
    """`SwitchedOff` subclasses `RuntimeError`, which `review_batch` catches to
    turn a failed review into a not-reviewed result. Caught in that order the
    loop would run on and produce one identical "switched off" result per
    remaining claim — and with the results then numbering one per slug, nothing
    downstream could tell a run that stopped from one that finished."""
    for index in range(4):
        solved(ws, f"p-{index}")
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: pytest.fail("it called out"))

    results = review.review_batch(ws, [f"p-{i}" for i in range(4)], host="codex",
                                  settings=review.Settings(enabled=False))

    assert results == [], "it stopped, it did not skip"


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
    assert payload["spending"]["spent"] == 0, "nothing spent yet"
    assert payload["plans"][0]["host"] == "codex"
    assert payload["tier"], "and it says which tier would answer"






def test_pending_uses_the_notes_it_is_given(ws):
    """`state.close` runs inside the Stop hook holding the whole projection,
    and this used to open and re-parse every file in `threads/` to answer a
    question about notes it already had."""
    from magi import state

    solved(ws)
    projection = state.load(ws)

    # The files are gone; the answer comes from the notes in hand.
    for path in (ws / "threads").glob("*.md"):
        path.unlink()

    assert review.pending(ws, notes=projection.notes) == ["p-gap"]
    assert review.pending(ws) == [], "and with no notes given it reads the disk"


def test_the_close_gate_does_not_re_read_the_tree_for_it(ws, monkeypatch):
    """The count is the point: `rules.check`'s docstring calls a second reader
    of the same files "a second answer waiting to disagree", and the Stop hook
    is where paying for one hurts most."""
    from pathlib import Path

    from magi import state
    from magi.kb import threads as threads_mod

    solved(ws)
    seen = []
    real = threads_mod.read_note
    monkeypatch.setattr(threads_mod, "read_note",
                        lambda path: seen.append(Path(path).name) or real(path))

    state.close(ws, write=False)

    assert seen.count("p-gap.md") == 1, (
        f"the gate parsed p-gap.md {seen.count('p-gap.md')} times; the "
        f"projection reads it once and `pending` should reuse that")


# --------------------------------------------------------------------------
# a typo must not cost anything
# --------------------------------------------------------------------------

def test_a_slug_that_does_not_exist_costs_nothing(ws, monkeypatch, capsys):
    """Found by making the typo with a real CLI on the other end: `magi review
    p-gapp` spent a real fifteen-second call asking Antigravity about a file
    that was not there, threw the answer away with `verdict not written`, and
    exited 0. `--host` was checked before the subprocess and the slug was not.

    No dry run could have found it — `--dry-run` returns before the slug is
    resolved and prints `would ask claude (haiku) about: p-gapp` quite happily.
    """
    from magi.core import ledger

    solved(ws, "p-gap")
    called = []
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: called.append(1) or "")

    code = review.main(["--topic-dir", str(ws), "--host", "codex", "p-gapp"])

    assert code == 1
    assert not called, "it asked a model about a note that does not exist"
    assert ledger.entries(ws) == [], "and it charged for it"


def test_and_it_says_which_one_they_probably_meant(ws, monkeypatch, capsys):
    """The persona typed one extra letter. Telling them the note is missing
    without telling them what is there sends them to `ls`."""
    solved(ws, "p-gap")
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])

    review.main(["--topic-dir", str(ws), "--host", "codex", "p-gapp"])

    err = capsys.readouterr().err
    assert "no note at threads/p-gapp.md" in err
    assert "Did you mean: p-gap?" in err
    assert "nothing counts as reviewed" in err


def test_a_line_is_not_a_claim_and_is_not_asked_about(ws, monkeypatch):
    """`magi review qah` is one keystroke from a real slug. The prompt asks
    whether a claim holds, and `pending()` only ever offers propositions."""
    from magi.core import vocab as vocab_mod
    from magi.kb import threads as threads_mod

    threads_mod.create(ws / "threads" / "qah.md", vocab_mod.LINE, "QAH", "Whether.")
    called = []
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: called.append(1) or "")

    code = review.main(["--topic-dir", str(ws), "--host", "codex", "qah"])

    assert code == 1 and not called


def test_one_typo_is_dropped_and_the_rest_still_run(ws, monkeypatch):
    """Not all-or-nothing. `test_one_bad_slug_does_not_discard_the_others`
    settled that: naming ten slugs and getting nothing back because one had a
    typo is a worse command than one that does the nine. What changed is only
    where the bad name is caught — before the money instead of after."""
    solved(ws, "p-a")
    solved(ws, "p-b")
    called = []
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask",
                        lambda *a, **k: called.append(1) or "VERDICT: stands\nREASON: ok.")

    code = review.main(["--topic-dir", str(ws), "--host", "codex",
                        "p-a", "p-typo", "p-b"])

    assert len(called) == 2, "it paid for the typo as well"
    assert code == 1, "and it did not say the run was clean"


def test_a_real_slug_still_goes_through(ws, monkeypatch):
    """The guard has to let the ordinary case past, or it is just an outage."""
    solved(ws, "p-gap")
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: "VERDICT: stands\nREASON: it holds.")

    assert review.main(["--topic-dir", str(ws), "--host", "codex", "p-gap"]) == 0


def test_a_verdict_that_could_not_be_written_is_a_failure(ws, monkeypatch):
    """From the caller's side it is the same as no review: the call was spent
    and the claim is no better off. Exiting 0 says the opposite."""
    solved(ws, "p-gap")
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: "VERDICT: stands\nREASON: fine.")
    monkeypatch.setattr(review, "apply_verdict",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))

    assert review.main(["--topic-dir", str(ws), "--host", "codex", "p-gap"]) == 1


def test_a_real_call_says_what_it_cost_where_it_was_spent(ws, monkeypatch, capsys):
    """`MAP.md` carries the week's spend, and it is DERIVED — rewritten only at
    session close. Between a review and the next `sync --close` the one surface
    a person would check still showed the old number, so "did that just cost me
    something" had no answer where it was being asked."""
    solved(ws, "p-gap")
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask",
                        lambda *a, **k: "VERDICT: stands\nREASON: it holds.")

    review.main(["--topic-dir", str(ws), "--host", "codex", "p-gap"])

    out = capsys.readouterr().out
    assert "1 model calls this week" in out


def test_a_run_refused_by_the_switch_reports_no_spend(ws, monkeypatch, capsys):
    """Nothing was asked, so there is nothing to say about a spend.

    What this covers is the *top-level* refusal, which returns before the
    reporting block is reached at all — and that is worth saying plainly,
    because two earlier versions of this test claimed to cover the guard
    inside that block. They could not: by the time the block runs, something
    has always been attempted, so the guard is defensive and unreachable. A
    test whose name promises coverage it does not have is worse than no test.
    """
    solved(ws, "p-gap")
    (ws / "config.yaml").write_text("research:\n  llm_calls: false\n", encoding="utf-8")
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: pytest.fail("it called out"))

    review.main(["--topic-dir", str(ws), "--host", "codex", "p-gap"])

    assert "model calls this week" not in capsys.readouterr().out


def test_a_call_that_failed_still_says_what_it_cost(ws, monkeypatch, capsys):
    """A timeout spent the wall clock and, on a metered account, the money.
    The ledger records it, so that is exactly when somebody wants the number."""
    solved(ws, "p-gap")
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("codex exited 1")))

    review.main(["--topic-dir", str(ws), "--host", "codex", "p-gap"])

    assert "model calls this week" in capsys.readouterr().out


# --------------------------------------------------------------------------
# a batch wrapper would keep only the first line of the prompt
# --------------------------------------------------------------------------

def test_a_cmd_wrapper_with_a_multiline_prompt_is_refused(monkeypatch):
    """Measured, not reasoned about.

    A `.cmd` echoing its first argument, given "line one\nline two\nline
    three" through `subprocess.run` with no shell, prints `ARG1=[line one]`
    and exits 0. Windows ends the argument at the newline. So a host installed
    by npm — `gemini.CMD` and `opencode.CMD` on the machine this was found on —
    would be handed one line of a review prompt and answer confidently about
    it, with nothing reporting a problem.

    Raising is what this can honestly do. Feeding the prompt on stdin is the
    real fix and has to be settled per host, because each vendor's headless
    flag reads its prompt differently.
    """
    monkeypatch.setattr(review, "_host_os_name", lambda: "nt")
    with pytest.raises(RuntimeError) as caught:
        review._refuse_truncating_wrapper([r"C:\npm\claude.CMD", "line one\nline two"])
    assert "first line" in str(caught.value)
    # The wrapper is named by its basename, on whichever platform the guard is
    # exercised — `Path` on POSIX would quote the whole `C:\npm\claude.CMD`.
    assert str(caught.value).startswith("claude.CMD ")


def test_a_real_executable_takes_a_multiline_prompt(monkeypatch):
    monkeypatch.setattr(review, "_host_os_name", lambda: "nt")
    review._refuse_truncating_wrapper([r"C:\bin\claude.EXE", "line one\nline two"])


def test_a_wrapper_is_fine_when_nothing_is_multiline(monkeypatch):
    """The truncation needs a newline. A one-line argument survives cmd.exe."""
    monkeypatch.setattr(review, "_host_os_name", lambda: "nt")
    review._refuse_truncating_wrapper([r"C:\npm\claude.CMD", "one line only"])


def test_posix_has_no_batch_wrappers_to_refuse(monkeypatch):
    monkeypatch.setattr(review, "_host_os_name", lambda: "posix")
    review._refuse_truncating_wrapper(["/usr/bin/claude.cmd", "line one\nline two"])


def test_ask_itself_refuses_before_it_spawns_anything(monkeypatch):
    """Through `ask`, not by calling the guard.

    The three tests above hand argv straight to `_refuse_truncating_wrapper`,
    which proves the guard is right and proves nothing about whether `ask`
    calls it — delete the one line and they all stay green. It happened: the
    mutation case reported MISSED until this test existed.
    """
    class _Entry:
        def headless(self, prompt, model, effort, allow_run=False):
            return ["claude", prompt]

    monkeypatch.setattr(review, "_host_os_name", lambda: "nt")
    monkeypatch.setattr(review, "plan", lambda *a, **k: (_Entry(), "m", None))
    monkeypatch.setattr(review.shutil, "which", lambda *a, **k: r"C:\npm\claude.CMD")

    def _never(*a, **k):
        raise AssertionError("a truncated prompt was handed to the host")

    monkeypatch.setattr(review.subprocess, "run", _never)

    with pytest.raises(RuntimeError) as caught:
        review.ask("claude", "line one\nline two", cwd=".")
    assert "first line" in str(caught.value)
