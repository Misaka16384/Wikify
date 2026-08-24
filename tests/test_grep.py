"""`magi grep` bounds its own runtime, and says so when it stopped early.

The guard this replaces wrapped `re.compile` in a five-second timeout and
reported `possible ReDoS attack` if it fired. It could not fire: compiling is
fast, and the exponential backtracking happens in `pattern.search`, which ran
unguarded. A defence that names a threat and does not stop it is worse than no
defence, because it answers the question for whoever reads it next.

What is tested here is what the replacement actually promises: a wall-clock
budget between lines, partial results labelled as partial, and no claim to
interrupt a single pathological match — nothing in the standard library can do
that, because a running `re` holds the GIL.
"""

import json

import pytest

from magi.kb import grep


def _run(capsys, *argv):
    grep.main(list(argv))
    return json.loads(capsys.readouterr().out)


@pytest.fixture
def corpus(tmp_path):
    (tmp_path / "a.md").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("Beta again\n", encoding="utf-8")
    return tmp_path


def test_a_plain_match(capsys, corpus):
    out = _run(capsys, "beta", str(corpus / "a.md"))
    assert [m["line"] for m in out["matches"]] == [2]


def test_case_insensitive(capsys, corpus):
    out = _run(capsys, "-i", "beta", str(corpus / "a.md"), str(corpus / "b.md"))
    assert len(out["matches"]) == 2


def test_a_clean_search_is_not_labelled_truncated(capsys, corpus):
    assert "truncated" not in _run(capsys, "beta", str(corpus / "a.md"))


def test_an_invalid_regex_is_an_error_not_a_crash(capsys, corpus):
    with pytest.raises(SystemExit):
        grep.main(["(unclosed", str(corpus / "a.md")])
    assert "Invalid regex" in json.loads(capsys.readouterr().out)["error"]


def test_a_missing_file_is_skipped(capsys, corpus):
    out = _run(capsys, "beta", str(corpus / "nope.md"), str(corpus / "a.md"))
    assert len(out["matches"]) == 1


def test_the_match_cap_is_reported_rather_than_implied(capsys, tmp_path):
    """A caller reading "no more matches" out of a list that was cut short
    draws exactly the wrong conclusion, and this output is a machine contract."""
    big = tmp_path / "big.md"
    big.write_text("hit\n" * (grep.MAX_RESULTS + 50), encoding="utf-8")

    out = _run(capsys, "hit", str(big))
    assert len(out["matches"]) == grep.MAX_RESULTS
    assert "limit" in out["truncated"]


def test_an_exhausted_budget_returns_what_it_found(capsys, tmp_path, monkeypatch):
    big = tmp_path / "big.md"
    big.write_text("hit\nmiss\n" * 500, encoding="utf-8")

    # A clock that is already past the deadline by the second line checked.
    ticks = iter([0.0, 0.0, 0.0, 100.0] + [100.0] * 10_000)
    monkeypatch.setattr(grep.time, "monotonic", lambda: next(ticks))

    out = _run(capsys, "hit", str(big))
    assert "partial" in out["truncated"]
    assert len(out["matches"]) < grep.MAX_RESULTS


def test_the_budget_can_be_turned_off(capsys, corpus):
    out = _run(capsys, "--timeout", "0", "beta", str(corpus / "a.md"))
    assert len(out["matches"]) == 1
    assert "truncated" not in out


def test_compiling_a_pathological_pattern_is_not_the_slow_part():
    """The premise of the fix, kept as an executable statement: compiling
    `(a+)+$` is instant, so a timeout around compilation guards nothing."""
    import re
    import time

    start = time.monotonic()
    re.compile(r"(a+)+$")
    assert time.monotonic() - start < 0.5
