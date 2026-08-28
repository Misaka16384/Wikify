"""`threads/` notes: the forum format, and what lint can tell from a snapshot.

Two properties carry the design and both are tested here rather than assumed.

**No post is ever lost.** Posts only go at the end, and the append is taken
under a per-note lock. That lock was added because the version without it lost
data: `open(path, "a")` plus one small write is atomic on POSIX and not on
Windows, where the C runtime implements `O_APPEND` as seek-then-write. The
concurrency test below is the one that caught it, so it races for real rather
than hand-building the file state a race would produce.

**A note's history is readable from the note.** Every status flip carries a
post recording `src → dst`, so the whole chain can be validated against the
frontmatter without a journal, a database, or any memory of who was running.
The tests below are the cases that chain has to catch: a flip nobody posted, a
posted chain that does not end where the frontmatter says, and a move the
lifecycle does not allow.
"""

import subprocess
import sys

import pytest

from magi.core import vocab
from magi.kb import threads


NOTE = """---
kind: proposition
status: open
created: 2026-08-28
purpose: Whether the gap survives disorder.
line: [qec]
---

# The gap survives weak disorder

Statement.

## Discussion
"""


def write(tmp_path, name="p-gap.md", text=NOTE):
    path = tmp_path / "threads" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def messages(note):
    return [message for _, message, _ in threads.validate(note)]


def severities(note):
    return {severity for severity, _, _ in threads.validate(note)}


# --------------------------------------------------------------------------
# posts
# --------------------------------------------------------------------------

def test_a_post_round_trips_through_the_file(tmp_path):
    path = write(tmp_path)
    threads.append_post(path, "Numerics converged at L=64.", host="claude",
                        line="qec", at="2026-08-28T10:00:00Z",
                        src="open", dst="testing")

    note = threads.read_note(path)
    assert len(note.posts) == 1
    post = note.posts[0]
    assert post.at == "2026-08-28T10:00:00Z"
    assert post.host == "claude"
    assert post.line == "qec"
    assert (post.src, post.dst) == ("open", "testing")
    assert "Numerics converged" in post.text


def test_a_post_without_a_line_still_carries_a_signature(tmp_path):
    path = write(tmp_path)
    threads.append_post(path, "Observation.", host="codex")
    post = threads.read_note(path).posts[0]
    assert post.host == "codex"
    assert post.line is None


def test_appending_creates_the_discussion_section_when_it_is_missing(tmp_path):
    path = write(tmp_path, text=NOTE.replace("\n## Discussion\n", ""))
    threads.append_post(path, "First.", host="claude")
    threads.append_post(path, "Second.", host="codex")

    text = path.read_text(encoding="utf-8")
    assert text.count(threads.POST_HEADING) == 1
    assert len(threads.read_note(path).posts) == 2


def test_appending_to_a_file_with_no_trailing_newline_does_not_glue_lines(tmp_path):
    path = write(tmp_path, text=NOTE.rstrip("\n"))
    threads.append_post(path, "First.", host="claude")
    assert len(threads.read_note(path).posts) == 1


def test_a_plain_subsection_under_discussion_is_not_a_post(tmp_path):
    """Somebody's `### Setup` heading inside a post must not be read as a new
    signature — an invented post would invent a transition with it."""
    path = write(tmp_path)
    threads.append_post(path, "### Setup\nWe take L=64.", host="claude",
                        src="open", dst="testing")
    note = threads.read_note(path)
    assert len(note.posts) == 1
    assert "### Setup" in note.posts[0].text


def test_only_the_first_status_line_of_a_post_counts(tmp_path):
    """A post quoting an earlier flip must not be read as flipping again."""
    path = write(tmp_path)
    threads.append_post(path, "status: testing -> supported\nwas premature.",
                        host="claude", src="open", dst="testing")
    note = threads.read_note(path)
    assert threads.transitions(note.posts) == [("open", "testing")]


def test_arrow_and_ascii_arrow_are_the_same_flip(tmp_path):
    path = write(tmp_path)
    body = f"{threads.POST_HEADING}\n\n### 2026-08-28T10:00:00Z · codex\nstatus: open -> testing\n\ntext\n"
    path.write_text(NOTE.replace(threads.POST_HEADING + "\n", body), encoding="utf-8")
    assert threads.transitions(threads.read_note(path).posts) == [("open", "testing")]


# --------------------------------------------------------------------------
# creation
# --------------------------------------------------------------------------

def test_a_new_note_is_valid_and_ready_for_posts(tmp_path):
    path = threads.create(tmp_path / "threads" / "q-order.md", vocab.QUESTION,
                          "What is the order parameter?", "Pin down the phase.",
                          lines=["qec"])
    note = threads.read_note(path)
    assert note.kind == vocab.QUESTION
    assert note.status == vocab.INITIAL_STATUS[vocab.QUESTION]
    assert note.lines == ["qec"]
    assert threads.has_discussion(note.body)
    assert note.tier == vocab.HOT
    assert threads.validate(note) == []


def test_the_discussion_reads_as_a_conversation(tmp_path):
    """One blank line between the heading and the first post, and between
    posts. These files are read by people as often as by the parser, and a
    stray blank line multiplies over a long thread."""
    path = threads.create(tmp_path / "threads" / "p.md", vocab.PROPOSITION, "T", "Why.")
    threads.append_post(path, "first", host="claude")
    threads.append_post(path, "second", host="codex")

    text = path.read_text(encoding="utf-8")
    assert threads.POST_HEADING + chr(10) + chr(10) + "### " in text
    assert chr(10) * 3 not in text


def test_a_slug_is_an_identity_so_creation_never_overwrites(tmp_path):
    path = tmp_path / "threads" / "p-gap.md"
    threads.create(path, vocab.PROPOSITION, "Gap", "Why.")
    with pytest.raises(FileExistsError):
        threads.create(path, vocab.PROPOSITION, "Gap again", "Why.")


def test_frontmatter_keeps_its_written_order(tmp_path):
    text = threads.render(vocab.PROPOSITION, "T", "Why.", lines=["qec"])
    keys = [line.split(":")[0] for line in text.splitlines()[1:6] if ":" in line]
    assert keys[:4] == ["kind", "status", "created", "purpose"]


# --------------------------------------------------------------------------
# validation: the schema
# --------------------------------------------------------------------------

def test_a_note_with_no_kind_cannot_be_routed(tmp_path):
    path = write(tmp_path, text="---\nstatus: open\n---\n\n# X\n")
    assert "critical" in severities(threads.read_note(path))


def test_a_status_borrowed_from_another_kind_is_critical(tmp_path):
    path = write(tmp_path, text=NOTE.replace("status: open", "status: exploring"))
    note = threads.read_note(path)
    assert "critical" in severities(note)
    assert any("Invalid status" in message for message in messages(note))


def test_a_line_note_does_not_point_at_a_line(tmp_path):
    """Its own slug is the line; a `line:` field would make it a member of
    itself and every downstream projection would double-count it."""
    path = write(tmp_path, text="---\nkind: line\nstatus: exploring\n"
                                "created: 2026-08-28\npurpose: QEC.\nline: [qec]\n---\n\n# QEC\n")
    assert any("no line: field" in message for message in messages(threads.read_note(path)))


def test_an_unknown_field_is_advice_not_a_failure(tmp_path):
    path = write(tmp_path, text=NOTE.replace("line: [qec]", "line: [qec]\nmood: hopeful"))
    note = threads.read_note(path)
    assert "critical" not in severities(note)
    assert any("Unknown frontmatter field" in message for message in messages(note))


def test_a_single_valued_list_field_must_still_be_a_list(tmp_path):
    path = write(tmp_path, text=NOTE.replace("line: [qec]", "line: qec"))
    assert any("must be a list" in message for message in messages(threads.read_note(path)))


def test_a_bet_outside_the_vocabulary_is_reported(tmp_path):
    path = write(tmp_path, text=NOTE.replace("line: [qec]", "line: [qec]\nbet: maybe"))
    assert any("Invalid bet" in message for message in messages(threads.read_note(path)))


def test_key_move_is_written_when_a_proposition_closes(tmp_path):
    early = write(tmp_path, "p-a.md",
                  NOTE.replace("line: [qec]", "line: [qec]\nkey_move: brute-force"))
    assert any("when a proposition closes" in message
               for message in messages(threads.read_note(early)))


# --------------------------------------------------------------------------
# validation: the posted history
# --------------------------------------------------------------------------

def test_a_status_flip_with_no_post_is_reported(tmp_path):
    path = write(tmp_path, text=NOTE.replace("status: open", "status: supported"))
    assert any("no post records the transition" in message
               for message in messages(threads.read_note(path)))


def test_a_posted_chain_that_ends_elsewhere_is_reported(tmp_path):
    path = write(tmp_path)
    threads.append_post(path, "Started.", host="claude", src="open", dst="testing")
    assert any("the last post left the note at" in message
               for message in messages(threads.read_note(path)))


def test_a_consistent_chain_validates_clean(tmp_path):
    path = write(tmp_path)
    threads.append_post(path, "Started.", host="claude", src="open", dst="testing")
    threads.append_post(path, "Numerics hold.", host="claude",
                        src="testing", dst="supported")
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("status: open", "status: supported")
                    .replace("purpose: Whether the gap survives disorder.",
                             "purpose: Whether the gap survives disorder.\n"
                             "key_move: known-method-new-setting"),
                    encoding="utf-8")
    settled = threads.read_note(path)
    assert threads.validate(settled) == []
    assert settled.tier == vocab.WARM_LINE


def test_an_illegal_posted_move_is_critical(tmp_path):
    path = write(tmp_path)
    threads.append_post(path, "Done.", host="claude", src="open", dst="superseded")
    threads.append_post(path, "Undone.", host="claude", src="superseded", dst="testing")
    note = threads.read_note(path)
    assert "critical" in severities(note)
    assert any("Illegal transition" in message for message in messages(note))


def test_a_gap_between_two_posts_is_reported(tmp_path):
    path = write(tmp_path)
    threads.append_post(path, "One.", host="claude", src="open", dst="testing")
    threads.append_post(path, "Two.", host="codex", src="conjectured", dst="supported")
    assert any("left the note at" in message for message in messages(threads.read_note(path)))


def test_a_note_that_starts_mid_lifecycle_is_taken_at_its_word(tmp_path):
    """Migration and proposition splits both produce notes whose first post
    does not start at `open`; refusing those would fail every migrated file."""
    path = write(tmp_path, text=NOTE.replace("status: open", "status: supported"))
    threads.append_post(path, "Split off p-gap.", host="claude",
                        src="testing", dst="supported")
    assert "critical" not in severities(threads.read_note(path))


# --------------------------------------------------------------------------
# the raced heading, and its repair
# --------------------------------------------------------------------------

def test_two_discussion_headings_are_reported_and_never_repaired(tmp_path):
    """A second heading is a nuisance, not a fault: posts are read from the
    first one onward, so both sets still parse. Deleting the line would mean
    editing somebody's note unattended to fix nothing."""
    path = write(tmp_path)
    threads.append_post(path, "First.", host="claude")
    path.write_text(path.read_text(encoding="utf-8")
                    + f"\n{threads.POST_HEADING}\n\n### 2026-08-28T11:00:00Z · codex\n\nSecond.\n",
                    encoding="utf-8")
    before = path.read_bytes()

    assert any("More than one" in message for message in messages(threads.read_note(path)))
    assert len(threads.read_note(path).posts) == 2

    threads.lint(tmp_path)
    assert path.read_bytes() == before


def test_lint_walks_the_tree_and_skips_scaffolding(tmp_path):
    write(tmp_path, "p-a.md")
    write(tmp_path, "p-b.md", NOTE.replace("kind: proposition", "kind: nonsense"))
    (tmp_path / "threads" / "_index.md").write_text("# Threads\n", encoding="utf-8")

    issues = threads.lint(tmp_path)
    assert {issue[2].name for issue in issues} == {"p-b.md"}


def test_lint_on_a_workspace_without_threads_is_silent(tmp_path):
    assert threads.lint(tmp_path) == []


# --------------------------------------------------------------------------
# wired into the command
# --------------------------------------------------------------------------

def test_magi_lint_reports_a_broken_thread_note(tmp_path):
    """The check is only real if it runs from the command a host will call."""
    subprocess.run([sys.executable, "-m", "magi", "init",
                    "--topic-dir", str(tmp_path), "--name", "T"],
                   capture_output=True, text=True, check=True)
    write(tmp_path, "p-bad.md", NOTE.replace("status: open", "status: exploring"))

    result = subprocess.run([sys.executable, "-m", "magi", "lint", "."], cwd=tmp_path,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    assert "Traceback" not in result.stderr, result.stderr
    assert "Invalid status" in result.stdout
    assert result.returncode == 1


# --------------------------------------------------------------------------
# code fences
# --------------------------------------------------------------------------

FENCED = """---
kind: proposition
status: open
created: 2026-08-28
purpose: Whether the gap survives disorder.
---

# The gap survives weak disorder

The note format looks like this:

```markdown
## Discussion

### 2026-08-28T09:00:00Z · claude/qec
status: open -> supported
```

That block is an example, not a history.
"""


def test_a_heading_quoted_in_a_fence_is_not_the_discussion_section(tmp_path):
    """A note explaining the format must not be read as having used it."""
    path = write(tmp_path, "p-fenced.md", FENCED)
    note = threads.read_note(path)
    assert not threads.has_discussion(note.body)
    assert note.posts == []
    assert threads.transitions(note.posts) == []


def test_a_fenced_example_does_not_invent_a_transition(tmp_path):
    path = write(tmp_path, "p-fenced.md", FENCED)
    assert not any("no post records the transition" in message
                   for message in messages(threads.read_note(path)))


def test_appending_to_a_note_whose_only_heading_is_fenced_makes_a_real_one(tmp_path):
    path = write(tmp_path, "p-fenced.md", FENCED)
    threads.append_post(path, "Starting.", host="claude", src="open", dst="testing")

    note = threads.read_note(path)
    assert len(note.posts) == 1
    assert threads.transitions(note.posts) == [("open", "testing")]


def test_a_fenced_example_is_not_counted_as_a_second_heading(tmp_path):
    """The note explaining the format has `## Discussion` inside a fence. It
    must not be reported as a duplicate — a warning nobody can act on is a
    warning people learn to skip."""
    path = write(tmp_path, "p-fenced.md", FENCED)
    threads.append_post(path, "Starting.", host="claude")

    assert not any("More than one" in message
                   for message in messages(threads.read_note(path)))


def test_a_signature_quoted_inside_a_post_is_not_a_second_post(tmp_path):
    path = write(tmp_path)
    threads.append_post(
        path,
        "The earlier note read:\n\n```\n### 2026-08-01T00:00:00Z · codex\nstatus: open -> refuted\n```\n\nWhich was wrong.",
        host="claude", src="open", dst="testing")

    note = threads.read_note(path)
    assert len(note.posts) == 1
    assert threads.transitions(note.posts) == [("open", "testing")]


# --------------------------------------------------------------------------
# one file, one temperature
# --------------------------------------------------------------------------

def _one_tier_issues(tmp_path, rel, text):
    from magi.core.wiki_common import parse_frontmatter, split_frontmatter_text
    from magi.kb import llmwiki

    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

    split = split_frontmatter_text(text)
    ctx = llmwiki.LintContext(tmp_path)
    ctx.documents = {path.resolve(): llmwiki.Document(
        path=path, frontmatter=parse_frontmatter(text),
        body=split[1] if split else text, raw_text=text)}
    llmwiki.check_one_tier_per_file(ctx)
    return [issue.message for issue in ctx.issues]


def test_a_conjecture_smuggled_into_a_concept_card_is_reported(tmp_path):
    """A card that also holds a proposition changes for two unrelated reasons,
    and no reader can tell which half they are looking at."""
    issues = _one_tier_issues(tmp_path, "wiki/concepts/gap.md",
                              "---\ntitle: Gap\nbet: supported\n---\n\n# Gap\n")
    assert any("belongs to a proposition" in message for message in issues)


def test_a_prose_section_called_discussion_is_left_alone(tmp_path):
    """Synthesis notes have discussion sections. Flagging the heading itself
    would teach people to ignore this check, which costs more than it saves."""
    issues = _one_tier_issues(tmp_path, "wiki/topics/landscape.md",
                              "---\ntitle: Landscape\n---\n\n# Landscape\n\n"
                              "## Discussion\n\nThe field disagrees about disorder.\n")
    assert issues == []


def test_signed_posts_in_a_wiki_note_are_reported(tmp_path):
    issues = _one_tier_issues(tmp_path, "wiki/topics/landscape.md",
                              "---\ntitle: Landscape\n---\n\n# Landscape\n\n"
                              "## Discussion\n\n### 2026-08-28T10:00:00Z · claude/qec\n\nI think not.\n")
    assert any("Signed forum posts" in message for message in issues)


def test_a_thread_note_is_not_measured_against_the_wiki_rule(tmp_path):
    """A guard for M1 rather than for today: `threads/` is not in the walk that
    fills `ctx.documents`, so this path cannot arise yet through `magi lint`.
    It will the moment threads enter the corpus, and the skip has to be there
    already — every thread note carries the fields this check looks for."""
    issues = _one_tier_issues(tmp_path, "threads/p-gap.md", NOTE)
    assert issues == []


# --------------------------------------------------------------------------
# repairs that repair nothing
# --------------------------------------------------------------------------

def test_lint_never_writes_a_byte(tmp_path):
    """A note's body belongs to whoever wrote it and its discussion is
    append-only, so there is no repair here that would not mean editing one of
    those on somebody's behalf. Checked against a tree that has something to
    complain about, not a clean one."""
    write(tmp_path, "p-ok.md")
    write(tmp_path, "p-bad.md", NOTE.replace("status: open", "status: supported"))
    write(tmp_path, "p-fenced.md", FENCED)
    threads.create(tmp_path / "threads" / "qec.md", vocab.LINE, "QEC", "Why.")
    before = {path: path.read_bytes() for path in threads.note_paths(tmp_path)}

    assert threads.lint(tmp_path)
    assert {path: path.read_bytes() for path in threads.note_paths(tmp_path)} == before


# --------------------------------------------------------------------------
# junk in the directory
# --------------------------------------------------------------------------

def test_lint_reports_malformed_files_instead_of_crashing(tmp_path):
    """`threads/` is written by four hosts and edited by hand. A walker that
    raises on the first unreadable file takes the whole lint run down with it,
    and the run is what the Stop hook depends on."""
    directory = tmp_path / "threads"
    directory.mkdir()
    (directory / "prose.md").write_text("no frontmatter here\n", encoding="utf-8")
    (directory / "empty.md").write_text("", encoding="utf-8")
    (directory / "binary.md").write_bytes(b"\xff\xfe not utf8")

    issues = threads.lint(tmp_path)

    by_file = {path.name: message for _, message, path, _ in issues}
    assert "not valid UTF-8" in by_file["binary.md"]
    assert "kind" in by_file["prose.md"]
    assert "kind" in by_file["empty.md"]
    assert all(severity == "critical" for severity, _, _, _ in issues)


def test_a_dot_directory_under_threads_is_not_walked(tmp_path):
    """`.archive/` and friends are somebody's private stash, and lint reporting
    on files it was never meant to see is how people learn to stop reading it."""
    directory = tmp_path / "threads"
    (directory / ".archive").mkdir(parents=True)
    (directory / "p-live.md").write_text(NOTE, encoding="utf-8")
    (directory / ".archive" / "p-old.md").write_text("junk", encoding="utf-8")

    assert [path.name for path in threads.note_paths(tmp_path)] == ["p-live.md"]


# --------------------------------------------------------------------------
# the audit trail survives a damaged note
# --------------------------------------------------------------------------

def test_posts_are_read_even_when_the_frontmatter_is_gone(tmp_path):
    """Losing the header is exactly when somebody needs to read what happened
    to the note. If `read_note` gives up, a real posted transition sits in the
    file and no audit path can see it."""
    path = write(tmp_path)
    threads.append_post(path, "Started.", host="claude", src="open", dst="testing")
    body = path.read_text(encoding="utf-8").split("---", 2)[2]
    path.write_text(body, encoding="utf-8")

    note = threads.read_note(path)
    assert threads.transitions(note.posts) == [("open", "testing")]
    assert any("kind" in message for message in messages(note))


def test_a_post_needs_a_note_to_go_on(tmp_path):
    """Creating the file here would produce a note with no kind and no status:
    invisible to `next`, to MAP, and to every projection."""
    with pytest.raises(FileNotFoundError):
        threads.append_post(tmp_path / "threads" / "nope.md", "text", host="claude")


def test_a_hand_written_discussion_section_keeps_its_prose_and_its_posts(tmp_path):
    """A write-up may have its own `## Discussion` prose section — papers do.
    Prose before the first signature is skipped rather than parsed, so the two
    sections coexist and nothing has to be deleted to make posts readable."""
    path = write(tmp_path, "p-writeup.md", NOTE.replace(
        "\n## Discussion\n",
        "\n## Discussion\n\nWhat this would mean for the threshold.\n"))
    threads.append_post(path, "Starting.", host="claude", src="open", dst="testing")

    note = threads.read_note(path)
    assert len(note.posts) == 1
    assert threads.transitions(note.posts) == [("open", "testing")]
    assert "What this would mean for the threshold." in path.read_text(encoding="utf-8")


def test_two_writers_appending_at_once_lose_nothing(tmp_path):
    """This is a regression test, not a hypothetical. The first version of
    `append_post` took no lock, on the reasoning that a single small write in
    append mode is atomic — true on POSIX, false on Windows, where the C
    runtime turns `O_APPEND` into seek-then-write. Eight concurrent appends
    lost two posts on the first run of this test."""
    from concurrent.futures import ThreadPoolExecutor

    for round_number in range(5):
        path = write(tmp_path, f"p-{round_number}.md")
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(
                lambda n: threads.append_post(path, f"post {n}", host=f"host{n}"),
                range(12)))

        note = threads.read_note(path)
        assert {post.host for post in note.posts} == {f"host{n}" for n in range(12)}
        assert path.read_text(encoding="utf-8").count(threads.POST_HEADING) == 1


def test_the_new_directories_are_not_unexpected_files(tmp_path):
    """`check_unknown_files` is an allow-list, so a directory the design adds
    is a screenful of warnings until somebody remembers to list it — and the
    warnings arrive in the workspaces of people who did nothing wrong."""
    from magi.kb import llmwiki

    (tmp_path / "threads").mkdir()
    (tmp_path / "decisions.md").write_text("# Decisions\n", encoding="utf-8")
    (tmp_path / "drafts").mkdir()

    ctx = llmwiki.LintContext(tmp_path)
    llmwiki.check_unknown_files(ctx)

    unexpected = [issue for issue in ctx.issues if "Unexpected" in issue.message]
    assert unexpected == []


# --------------------------------------------------------------------------
# flipping a status is one action
# --------------------------------------------------------------------------

def test_a_flip_writes_the_status_and_the_reason_together(tmp_path):
    """Two writes that must agree are one function. Split them and a note ends
    up with a status nobody explained, or a post describing a flip that never
    happened — and the audit trail is exactly those two agreeing."""
    path = write(tmp_path)
    threads.set_status(path, "testing", "Numerics started at L=64.",
                       host="claude", line="qec")

    note = threads.read_note(path)
    assert note.status == "testing"
    assert threads.transitions(note.posts) == [("open", "testing")]
    assert "L=64" in note.posts[0].text
    assert threads.validate(note) == []


def test_the_rest_of_the_frontmatter_survives_the_flip(tmp_path):
    path = write(tmp_path, text=NOTE.replace("line: [qec]", "line: [qec]\nbet: supported"))
    threads.set_status(path, "conjectured", "Predicted.", host="claude")

    note = threads.read_note(path)
    assert note.frontmatter["bet"] == "supported"
    assert note.lines == ["qec"]
    assert note.frontmatter["purpose"] == "Whether the gap survives disorder."
    keys = list(note.frontmatter)
    assert keys[:4] == ["kind", "status", "created", "purpose"]


def test_an_illegal_flip_changes_nothing(tmp_path):
    path = write(tmp_path, text=NOTE.replace("status: open", "status: superseded"))
    before = path.read_bytes()

    with pytest.raises(threads.IllegalTransition) as caught:
        threads.set_status(path, "testing", "reopening", host="claude")

    assert "superseded" in str(caught.value)
    assert caught.value.allowed == list(vocab.allowed_targets(vocab.PROPOSITION, "superseded"))
    assert path.read_bytes() == before


def test_flipping_to_the_status_it_already_has_is_just_a_comment(tmp_path):
    path = write(tmp_path)
    threads.set_status(path, "open", "Still looking for a handle on this.",
                       host="codex")

    note = threads.read_note(path)
    assert note.status == "open"
    assert len(note.posts) == 1
    assert not note.posts[0].is_transition
    assert threads.validate(note) == []


def test_flipping_a_note_that_is_not_there(tmp_path):
    with pytest.raises(FileNotFoundError):
        threads.set_status(tmp_path / "threads" / "nope.md", "testing", "x", host="claude")


def test_flips_and_comments_race_without_losing_either(tmp_path):
    """`set_status` writes the file twice — rewrite then append — so it has to
    hold the same lock the plain appenders do."""
    from concurrent.futures import ThreadPoolExecutor

    path = write(tmp_path)

    def work(n):
        if n == 0:
            return threads.set_status(path, "testing", "flipping", host="claude")
        return threads.append_post(path, f"comment {n}", host=f"host{n}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, range(8)))

    note = threads.read_note(path)
    assert len(note.posts) == 8
    assert note.status == "testing"
    assert threads.transitions(note.posts) == [("open", "testing")]


# --------------------------------------------------------------------------
# frontmatter nobody in this module wrote
# --------------------------------------------------------------------------

FLOW = """---
{kind: proposition, status: open, created: 2026-08-28, purpose: Flow style is valid YAML}
---

# Flow

## Discussion
"""

DECOY = """---
kind: proposition
purpose: "one line
status: not-real
continued"
status: open
created: 2026-08-28
---

# Decoy

## Discussion
"""


def test_a_flip_works_on_flow_style_frontmatter(tmp_path):
    """The legality check parses YAML and the rewrite edited a line; on
    anything this module did not write those two readings disagree, and the
    disagreement is silent — the post says `open → testing` over a note that
    still says `open`."""
    path = write(tmp_path, "p-flow.md", FLOW)
    threads.set_status(path, "testing", "started", host="claude")

    note = threads.read_note(path)
    assert note.status == "testing"
    assert threads.validate(note) == []


def test_a_line_that_only_looks_like_the_status_is_not_the_status(tmp_path):
    """A multi-line quoted scalar can contain `status:` at the start of a
    continuation line. Rewriting that one corrupts the field it belongs to and
    leaves the real status untouched."""
    path = write(tmp_path, "p-decoy.md", DECOY)
    threads.set_status(path, "testing", "started", host="claude")

    note = threads.read_note(path)
    assert note.status == "testing"
    assert "not-real" in str(note.frontmatter["purpose"])


def test_a_note_written_with_unix_endings_keeps_them(tmp_path):
    """Notes travel between macOS and Windows sessions. Rewriting the whole
    file in this machine's ending turns a one-word edit into a diff of every
    line, on a file two people are appending to."""
    path = tmp_path / "threads" / "p-lf.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(NOTE.encode("utf-8"))

    threads.set_status(path, "testing", "started", host="claude")
    threads.append_post(path, "and again", host="codex")

    assert b"\r\n" not in path.read_bytes()
    assert len(threads.read_note(path).posts) == 2


def test_a_note_written_with_windows_endings_keeps_them(tmp_path):
    path = tmp_path / "threads" / "p-crlf.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(NOTE.replace("\n", "\r\n").encode("utf-8"))

    threads.set_status(path, "testing", "started", host="claude")

    raw = path.read_bytes()
    assert b"\r\n" in raw
    assert raw.replace(b"\r\n", b"").count(b"\n") == 0, "mixed endings"
    assert threads.read_note(path).status == "testing"

