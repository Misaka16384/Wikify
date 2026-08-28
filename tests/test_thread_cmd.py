"""`magi thread` — the commands that keep the format's promises.

An agent could write these files with an editor, and that is exactly the
problem. Two guarantees do not survive hand-editing: appends take a lock, and a
status flip carries its reason. Both are the command's job, so the command has
to be the easy path — which means it has to fail clearly when the note is not
there, when the slug is taken, and when the lifecycle says no.

The other thing tested here is the signature. A post says who wrote it, and
`$MAGI_HOST` is how the host tells us: guessing from undocumented vendor
environment variables would be wrong quietly, and a discussion where every post
is signed the same way is a log, not a conversation.
"""

import json

import pytest

from magi.kb import thread_cmd, threads


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "threads").mkdir()
    return tmp_path


def run(ws, *argv, json_out=False):
    args = list(argv) + ["--topic-dir", str(ws)] + (["--json"] if json_out else [])
    return thread_cmd.main(args)


def note(ws, slug):
    return threads.read_note(ws / "threads" / f"{slug}.md")


def open_proposition(ws, slug="p-gap"):
    run(ws, "new", slug, "--kind", "proposition", "--title", "The gap survives",
        "--purpose", "Decide before a month of numerics.", "--line", "qec")
    return slug


# --------------------------------------------------------------------------
# opening
# --------------------------------------------------------------------------

def test_new_writes_a_note_that_lints_clean(ws, capsys):
    assert run(ws, "new", "qec", "--kind", "line", "--title", "QEC under disorder",
               "--purpose", "Whether disorder kills the threshold.") == 0

    assert threads.validate(note(ws, "qec")) == []
    assert "exploring" in capsys.readouterr().out


def test_new_records_the_bet_at_the_moment_it_is_made(ws):
    """The prediction is only worth anything before the work. The flag exists
    so recording it costs nothing at the one moment it is honest."""
    run(ws, "new", "p-gap", "--kind", "proposition", "--title", "T",
        "--purpose", "Why.", "--bet", "refuted")
    assert note(ws, "p-gap").frontmatter["bet"] == "refuted"


def test_a_taken_slug_is_refused_rather_than_overwritten(ws, capsys):
    open_proposition(ws)
    assert run(ws, "new", "p-gap", "--kind", "proposition", "--title", "Other",
               "--purpose", "Different thing.") == 1
    assert "identity" in capsys.readouterr().err


def test_json_carries_the_derived_temperature(ws, capsys):
    run(ws, "new", "p-gap", "--kind", "proposition", "--title", "T",
        "--purpose", "Why.", json_out=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "open"
    assert payload["tier"] == "hot"


# --------------------------------------------------------------------------
# posting
# --------------------------------------------------------------------------

def test_a_post_is_signed_by_the_host_the_environment_names(ws, monkeypatch):
    monkeypatch.setenv("MAGI_HOST", "codex")
    open_proposition(ws)
    run(ws, "post", "p-gap", "--text", "Tried the obvious thing.")

    assert note(ws, "p-gap").posts[0].host == "codex"


def test_an_explicit_host_wins_over_the_environment(ws, monkeypatch):
    monkeypatch.setenv("MAGI_HOST", "codex")
    open_proposition(ws)
    run(ws, "post", "p-gap", "--text", "x", "--host", "claude")

    assert note(ws, "p-gap").posts[0].host == "claude"


def test_without_a_host_the_signature_is_not_a_guess(ws, monkeypatch):
    """Vendor environment variables are undocumented and change. Signing
    everything `cli` is honest; signing it `claude` because a variable happened
    to be set is a fabricated attribution in an audit trail."""
    monkeypatch.delenv("MAGI_HOST", raising=False)
    assert thread_cmd.host_name() == "cli"


def test_posting_to_a_note_that_is_not_there_says_so(ws, capsys):
    assert run(ws, "post", "nope", "--text", "x") == 1
    assert "magi thread new" in capsys.readouterr().err


# --------------------------------------------------------------------------
# moving a note along
# --------------------------------------------------------------------------

def test_status_writes_the_flip_and_the_reason_together(ws):
    open_proposition(ws)
    assert run(ws, "status", "p-gap", "testing", "--text", "Numerics started at L=64.") == 0

    settled = note(ws, "p-gap")
    assert settled.status == "testing"
    assert threads.transitions(settled.posts) == [("open", "testing")]
    assert threads.validate(settled) == []


def test_an_illegal_move_is_refused_and_says_what_was_possible(ws, capsys):
    """The error has to carry the allowed set. "Not legal" leaves an agent
    guessing, and a guessing agent writes the frontmatter by hand instead."""
    open_proposition(ws)
    run(ws, "status", "p-gap", "superseded", "--text", "done")

    assert run(ws, "status", "p-gap", "open", "--text", "reopening") == 1
    message = capsys.readouterr().err
    assert "superseded → open" in message
    assert "conflict" in message


def test_moving_a_note_that_is_not_there_says_so(ws, capsys):
    assert run(ws, "status", "nope", "testing", "--text", "x") == 1
    assert "magi thread new" in capsys.readouterr().err


# --------------------------------------------------------------------------
# what a slug is allowed to be
# --------------------------------------------------------------------------

def test_a_slug_cannot_walk_out_of_the_threads_directory(ws, capsys):
    """It becomes a filename. `../p-gap` writes a note where nothing looks for
    it, and the walker that feeds `next` never sees it again."""
    assert run(ws, "new", "../escaped", "--kind", "proposition",
               "--title", "T", "--purpose", "Why.") == 1

    assert not (ws / "escaped.md").exists()
    assert list((ws / "threads").iterdir()) == []
    assert "not a usable slug" in capsys.readouterr().err


def test_an_empty_slug_is_refused_rather_than_making_a_hidden_file(ws, capsys):
    """`"" + ".md"` is `.md`, which the walker skips as a dotfile — a note
    that exists on disk and does not exist to the system."""
    assert run(ws, "new", "", "--kind", "proposition",
               "--title", "T", "--purpose", "Why.") == 1
    assert "cannot be empty" in capsys.readouterr().err


def test_a_near_miss_is_refused_with_the_slug_it_should_have_been(ws, capsys):
    """`P Gap` and `p-gap` would be two notes about one claim. Refusing and
    naming the canonical form costs one retry; repairing it silently costs the
    agent its own id back."""
    assert run(ws, "new", "P Gap", "--kind", "proposition",
               "--title", "T", "--purpose", "Why.") == 1
    assert "'p-gap'" in capsys.readouterr().err


def test_a_note_needs_a_title(ws, capsys):
    assert run(ws, "new", "p-gap", "--kind", "proposition",
               "--title", "   ", "--purpose", "Why.") == 1
    assert "needs a title" in capsys.readouterr().err


def test_outside_a_workspace_the_command_explains_itself(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert thread_cmd.main(["new", "p-gap", "--kind", "proposition",
                            "--title", "T", "--purpose", "Why."]) == 1
    assert "no workspace found" in capsys.readouterr().err

