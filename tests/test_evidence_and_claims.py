"""Evidence stays in the library, the claim is its own field, a signature says
who typed it, and the bets are scored where they are seen.

Second batch of one day's use (2026-09-03). Fifteen verification scripts were
written in a CLI's scratch directory and cited from posts as `scratchpad
<name>`; the reviewer, reading inside the workspace, could open none of them.
A title written as two lines of formula so it could be judged literally was
judged literally, and called too broad, twice. A person's words transcribed
with `--host human` were indistinguishable from their own keystrokes. Eight
bets were placed and nothing paired them with their outcomes.
"""

import datetime as dt

import pytest

from magi import review, state
from magi.core import project, vocab
from magi.kb import thread_cmd, threads


NOW = dt.datetime(2026, 9, 3, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def ws(tmp_path):
    for sub in ("threads", "drafts", "tools", "raw"):
        (tmp_path / sub).mkdir()
    (tmp_path / "tools" / "check.m2").write_text("-- checks the index\n", encoding="utf-8")
    (tmp_path / "drafts" / "d.md").write_text("# D\n\nthe argument\n", encoding="utf-8")
    return tmp_path


def run(ws, *argv):
    return thread_cmd.main(list(argv) + ["--topic-dir", str(ws)])


def note(ws, slug):
    return threads.read_note(ws / "threads" / f"{slug}.md")


def proposition(ws, slug="p-gap", **extra):
    return threads.create(ws / "threads" / f"{slug}.md", vocab.PROPOSITION,
                          slug.upper(), f"Why {slug}.", extra=extra or None)


# --------------------------------------------------------------------------
# tools/ is a directory of the library
# --------------------------------------------------------------------------

def test_tools_is_in_the_layout_and_the_scaffold(tmp_path):
    from magi import init_workspace

    assert "tools" in project.LAYOUT
    row = project.LAYOUT["tools"]
    assert not (row.rewritten or row.searchable or row.documents or row.graphed)
    assert row.note, "a row that is False everywhere says why"
    src = (project.__file__ and __import__("pathlib").Path(init_workspace.__file__)
           .read_text(encoding="utf-8"))
    assert '"tools",' in src


# --------------------------------------------------------------------------
# evidence and claim, at the keystroke
# --------------------------------------------------------------------------

def test_new_records_claim_derivation_and_evidence(ws):
    assert run(ws, "new", "p-idx", "--kind", "proposition", "--title", "Index is 3",
               "--claim", "For h = 1, the twisted index equals 3.",
               "--purpose", "Why.", "--derivation", "drafts/d.md",
               "--evidence", "tools/check.m2") == 0
    fm = note(ws, "p-idx").frontmatter
    assert fm["claim"] == "For h = 1, the twisted index equals 3."
    assert fm["derivation"] == ["drafts/d.md"]
    assert fm["evidence"] == ["tools/check.m2"]
    assert threads.validate(note(ws, "p-idx")) == []


def test_a_wikilink_derivation_is_kept_as_written(ws):
    run(ws, "new", "p-idx", "--kind", "proposition", "--title", "T", "--purpose", "Why.",
        "--derivation", "[[drafts/d]]")
    assert note(ws, "p-idx").frontmatter["derivation"] == ["[[drafts/d]]"]


def test_evidence_outside_the_library_is_refused_at_the_keystroke(ws, tmp_path, capsys):
    elsewhere = tmp_path.parent / f"{tmp_path.name}-scratch"
    elsewhere.mkdir()
    (elsewhere / "b8.m2").write_text("x", encoding="utf-8")
    assert run(ws, "new", "p-idx", "--kind", "proposition", "--title", "T",
               "--purpose", "Why.", "--evidence", str(elsewhere / "b8.m2")) == 1
    err = capsys.readouterr().err
    assert "outside the project" in err and "tools/" in err
    assert not (ws / "threads" / "p-idx.md").exists()


def test_evidence_that_does_not_exist_is_refused(ws, capsys):
    assert run(ws, "new", "p-idx", "--kind", "proposition", "--title", "T",
               "--purpose", "Why.", "--evidence", "tools/missing.m2") == 1
    assert "not a file in the project" in capsys.readouterr().err


def test_post_evidence_appends_and_is_a_recorded_field_change(ws):
    proposition(ws, "p-gap", evidence=["tools/check.m2"])
    (ws / "tools" / "more.py").write_text("print(1)\n", encoding="utf-8")
    assert run(ws, "post", "p-gap", "--evidence", "tools/more.py",
               "--evidence", "tools/check.m2", "--text", "second check") == 0
    got = note(ws, "p-gap")
    assert got.frontmatter["evidence"] == ["tools/check.m2", "tools/more.py"]
    last = got.posts[-1]
    assert last.field == "evidence" and "more.py" in str(last.value)
    assert "second check" in last.text


def test_post_needs_text_or_evidence(ws, capsys):
    proposition(ws)
    assert run(ws, "post", "p-gap") == 1
    assert "--evidence" in capsys.readouterr().err


def test_thread_claim_restates_through_the_cli(ws):
    proposition(ws, claim="For every h, the index is 3.")
    assert run(ws, "claim", "p-gap", "--text", "For h = 1,\n the index is 3.",
               "--why", "the reviewer said so") == 0
    got = note(ws, "p-gap")
    assert got.frontmatter["claim"] == "For h = 1, the index is 3."
    assert got.posts[-1].field == "claim"


def test_the_reviewer_is_told_the_claim_is_the_statement_and_evidence_must_be_read():
    prompt = review.build_prompt("/w", "p")
    assert "`claim:` is the statement under review" in prompt
    assert "`evidence:`" in prompt and "run them if you are able" in prompt
    assert "that is not inside the" in prompt and "workspace. Say what is missing" in prompt


# --------------------------------------------------------------------------
# evidence outside, found afterwards
# --------------------------------------------------------------------------

def test_an_absolute_path_in_a_post_is_reported_as_outside(ws):
    path = proposition(ws)
    threads.append_post(path, r"verified with C:\Users\x\AppData\Local\Temp\claude\b8.m2 and it holds",
                        host="claude")
    threads.append_post(path, "also see /tmp/haah/check.py", host="claude")
    found = state.evidence_outside(ws, note(ws, "p-gap"))
    assert len(found) == 2
    assert all("outside the project" in why for why in found)


def test_a_scratchpad_mention_is_reported_even_without_a_full_path(ws):
    path = proposition(ws)
    threads.append_post(path, "the script is scratchpad b8_haah.m2", host="claude")
    found = state.evidence_outside(ws, note(ws, "p-gap"))
    assert found and "scratch" in found[0]


def test_a_path_inside_the_library_is_not(ws):
    path = proposition(ws, evidence=["tools/check.m2"], derivation=["[[drafts/d]]"])
    threads.append_post(path, f"see {ws / 'tools' / 'check.m2'} and tools/check.m2",
                        host="claude")
    assert state.evidence_outside(ws, note(ws, "p-gap")) == []


def test_a_field_naming_no_file_is_reported(ws):
    proposition(ws, evidence=["tools/gone.m2"])
    found = state.evidence_outside(ws, note(ws, "p-gap"))
    assert found == ["`evidence:` names tools/gone.m2, which is not a file in the project"]


def test_next_and_the_close_gate_say_so_without_blocking(ws):
    path = proposition(ws, bet="supported")
    threads.set_status(path, "testing", "go", host="claude")
    threads.append_post(path, "proof in /tmp/x/proof.m2", host="claude")
    st = state.load(ws, now=NOW)
    actions = state.candidates(st, now=NOW)
    ev = [a for a in actions if a.key == "evidence"]
    assert ev and ev[0].cost == "llm" and "--evidence" in ev[0].run
    report = state.close(ws, write=False)
    assert report.ok
    assert report.outside and report.outside[0][0] == "p-gap"
    assert "outside the project" in state.render_close(report)


def test_review_warns_before_spending(ws, monkeypatch, capsys):
    path = proposition(ws, bet="supported")
    threads.set_status(path, "testing", "go", host="claude")
    threads.set_status(path, "supported", "done; script at /tmp/x/proof.m2", host="claude")
    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", lambda *a, **k: "VERDICT: unclear\nREASON: cannot open /tmp/x/proof.m2")
    review.main(["--topic-dir", str(ws), "--host", "codex", "p-gap"])
    assert "outside the project" in capsys.readouterr().err


# --------------------------------------------------------------------------
# who typed it
# --------------------------------------------------------------------------

def test_a_human_signature_carries_who_typed_it(ws, monkeypatch):
    monkeypatch.setenv("MAGI_HOST", "claude")
    proposition(ws)
    run(ws, "post", "p-gap", "--text", "keep it", "--host", "human")
    last = note(ws, "p-gap").posts[-1]
    assert (last.host, last.via) == ("human", "claude")
    assert "· via claude" in (ws / "threads" / "p-gap.md").read_text(encoding="utf-8")


def test_an_agents_own_post_carries_no_via(ws, monkeypatch):
    monkeypatch.setenv("MAGI_HOST", "claude")
    proposition(ws)
    run(ws, "post", "p-gap", "--text", "working")
    last = note(ws, "p-gap").posts[-1]
    assert (last.host, last.via) == ("claude", None)


def test_via_can_be_named_and_a_bet_carries_it_too(ws, monkeypatch):
    monkeypatch.delenv("MAGI_HOST", raising=False)
    proposition(ws)
    run(ws, "bet", "p-gap", "refuted", "--via", "codex")
    assert note(ws, "p-gap").posts[-1].via == "codex"
    run(ws, "status", "p-gap", "testing", "--text", "they said go", "--host", "human")
    assert note(ws, "p-gap").posts[-1].via == "cli"


def test_the_signature_still_counts_as_the_persons(ws, monkeypatch):
    """`via` is provenance, not a different signer: the close gate reads a
    `human` post out of `disputed` as the decision being on record."""
    monkeypatch.setenv("MAGI_HOST", "claude")
    path = proposition(ws, bet="supported")
    threads.set_status(path, "testing", "go", host="claude")
    threads.set_status(path, "supported", "done", host="claude")
    threads.set_status(path, "disputed", "VERDICT: refuted\n\nno", host=vocab.REVIEWER)
    run(ws, "status", "p-gap", "testing", "--text", "they said rework it", "--host", "human")
    assert not [d for d in state.load(ws, now=NOW).debt if d.slug == "p-gap"]


def test_magi_decide_records_who_transcribed(ws, monkeypatch):
    from magi import decide_cmd

    monkeypatch.setenv("MAGI_HOST", "codex")
    proposition(ws)
    decide_cmd.record(ws, "I expect it holds", about="p-gap", bet="supported")
    last = note(ws, "p-gap").posts[-1]
    assert (last.host, last.via, last.field) == ("human", "codex", "bet")


def test_an_old_heading_without_via_still_parses(ws):
    path = proposition(ws)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n### 2026-09-01T10:00:00Z · human/qec\n\nold style\n")
    last = note(ws, "p-gap").posts[-1]
    assert (last.host, last.line, last.via) == ("human", "qec", None)


# --------------------------------------------------------------------------
# the scoreboard
# --------------------------------------------------------------------------

def test_open_and_unknown_bets_are_listed_and_superseded_is_not_scored(ws):
    def settled(slug, bet, status):
        path = proposition(ws, slug, bet=bet)
        threads.set_status(path, "testing", "go", host="claude")
        threads.set_status(path, status, "done", host="claude")
        return path

    settled("p-won", "supported", "supported")
    settled("p-lost", "supported", "refuted")
    path = settled("p-gone", "supported", "supported")
    threads.set_status(path, "superseded", "replaced", host="human")
    a = proposition(ws, "p-open", bet="unknown")
    threads.set_status(a, "testing", "go", host="claude")
    proposition(ws, "p-open2", bet="refuted")

    back = state.retrospective(state.load(ws, now=NOW))
    assert (back["hits"], back["scored"]) == (1, 2)
    assert back["open"] == ["p-open", "p-open2"]
    assert back["unknown_open"] == ["p-open"]
    assert back["superseded"] == ["p-gone"]


def test_next_prints_one_line_of_scoreboard_and_asks_about_the_dont_knows_once(ws):
    path = proposition(ws, "p-open", bet="unknown")
    threads.set_status(path, "testing", "go", host="claude")
    st = state.load(ws, now=NOW)
    actions = state.candidates(st, now=NOW)
    text = state.render(st, actions)
    assert "Bets:" in text and "1 open" in text
    bets = [a for a in actions if a.key == "bets"]
    assert len(bets) == 1 and bets[0].cost == "human" and "p-open" in bets[0].why
    assert "For the person" in text


def test_no_bets_no_scoreboard(ws):
    proposition(ws, "p-x")
    st = state.load(ws, now=NOW)
    assert "Bets:" not in state.render(st, state.candidates(st, now=NOW))


def test_weakly_reviewed_claims_are_one_item_for_the_person(ws):
    path = proposition(ws, bet="supported")
    threads.set_status(path, "testing", "go", host="claude")
    threads.set_status(path, "supported", "done", host="claude")
    review.apply_verdict(ws, review.Verdict(slug="p-gap", verdict=review.VERDICT_STANDS,
                                            reason="fine", host="claude", model="haiku",
                                            tier="cheap"))
    st = state.load(ws, now=NOW)
    actions = state.candidates(st, now=NOW)
    reread = [a for a in actions if a.key == "reread"]
    assert len(reread) == 1 and reread[0].cost == "human" and "p-gap" in reread[0].why
    assert not [a for a in actions if a.key == "review"]


# --------------------------------------------------------------------------
# the timeout
# --------------------------------------------------------------------------

def test_the_ceiling_grows_with_what_there_is_to_read(ws):
    proposition(ws, "p-short", derivation=["[[drafts/d]]"])
    assert review.timeout_for(ws, "p-short") == review.TIMEOUT == 600
    (ws / "drafts" / "long.md").write_text("x" * 25_000, encoding="utf-8")
    proposition(ws, "p-long", derivation=["drafts/long.md"])
    assert review.timeout_for(ws, "p-long") == review.TIMEOUT + 300
    (ws / "tools" / "big.dat").write_text("y" * 70_000, encoding="utf-8")
    proposition(ws, "p-huge", derivation=["drafts/long.md"], evidence=["tools/big.dat"])
    assert review.timeout_for(ws, "p-huge") == review.TIMEOUT + 600


def test_an_explicit_timeout_is_not_scaled(ws, monkeypatch):
    path = proposition(ws, bet="supported")
    threads.set_status(path, "testing", "go", host="claude")
    threads.set_status(path, "supported", "done", host="claude")
    seen = {}

    def fake_ask(host, prompt, cwd, model=None, timeout=None, effort=None,
                 settings=None, allow_run=False):
        seen["timeout"] = timeout
        return "VERDICT: stands\nREASON: fine"

    monkeypatch.setattr(review, "installed_hosts", lambda *_a, **_k: ["codex"])
    monkeypatch.setattr(review, "ask", fake_ask)
    review.review(ws, "p-gap", host="codex", timeout=42)
    assert seen["timeout"] == 42
    review.review(ws, "p-gap", host="codex")
    assert seen["timeout"] == review.TIMEOUT
