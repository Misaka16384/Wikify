"""The CLI's half of `AGENTS.md`, and the person's half.

The failure this prevents is the one every tool that appends to an instruction
file eventually causes: three copies of a protocol that changed twice, each
contradicting the next, and no way to tell which one the agent read. MAGI
rewrites its block whole and never looks outside it.

Both properties tested here are silent when broken. A block that is not
idempotent turns every `magi install` into a diff, so people stop reading the
diffs. A block that moves to the end of the file quietly reorders instructions
somebody arranged on purpose.
"""

from magi.core import managed


BODY = "Run `magi next` first.\nDo not edit `raw/`."
OTHER = "Run `magi next` first.\nDo not edit `raw/`.\nOne file, one temperature."


def test_a_fresh_file_is_just_the_block(tmp_path):
    path = tmp_path / "AGENTS.md"
    assert managed.write(path, BODY) is True
    assert managed.read(path.read_text(encoding="utf-8")) == BODY


def test_writing_the_same_body_twice_changes_nothing(tmp_path):
    path = tmp_path / "AGENTS.md"
    managed.write(path, BODY)
    before = path.read_bytes()

    assert managed.write(path, BODY) is False
    assert path.read_bytes() == before


def test_a_new_body_replaces_the_old_one_rather_than_joining_it(tmp_path):
    path = tmp_path / "AGENTS.md"
    managed.write(path, BODY)
    managed.write(path, OTHER)

    text = path.read_text(encoding="utf-8")
    assert text.count(managed.BEGIN) == 1
    assert managed.read(text) == OTHER
    assert "One file, one temperature." in text


def test_what_a_person_wrote_around_the_block_survives(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_text("# House rules\n\nWrite tests first.\n\n"
                    f"{managed.BEGIN}\nold protocol\n{managed.END}\n\n"
                    "## Notes\n\nAsk before deploying.\n", encoding="utf-8")

    managed.write(path, BODY)
    text = path.read_text(encoding="utf-8")

    assert "Write tests first." in text
    assert "Ask before deploying." in text
    assert "old protocol" not in text
    assert text.index("Write tests first.") < text.index(managed.BEGIN) < text.index("## Notes")


def test_a_file_with_no_block_keeps_its_content_and_gains_one(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_text("# House rules\n\nWrite tests first.\n", encoding="utf-8")

    managed.write(path, BODY)
    text = path.read_text(encoding="utf-8")

    assert "Write tests first." in text
    assert managed.read(text) == BODY


def test_a_half_deleted_marker_is_not_licence_to_guess(tmp_path):
    """Somebody mid-edit should get their file back with a block added, not
    with the rest of it treated as protocol and overwritten."""
    path = tmp_path / "AGENTS.md"
    path.write_text(f"{managed.BEGIN}\nstranded\n\n# House rules\n", encoding="utf-8")

    managed.write(path, BODY)
    text = path.read_text(encoding="utf-8")

    assert "stranded" in text
    assert "# House rules" in text
    assert managed.read(text) == BODY


def test_a_file_with_no_markers_reads_as_no_block():
    assert managed.read("# House rules\n") is None
    assert managed.read(f"{managed.BEGIN}\nunterminated\n") is None


# --------------------------------------------------------------------------
# files that already went wrong
# --------------------------------------------------------------------------

def test_a_second_block_is_absorbed_rather_than_left_to_rot(tmp_path):
    """Two blocks is the same disease as appending, arrived at differently:
    two protocols in one file and no way to know which the host obeyed."""
    path = tmp_path / "AGENTS.md"
    path.write_text(f"{managed.BEGIN}\nold one\n{managed.END}\n\n"
                    f"# Mine\n\n{managed.BEGIN}\nold two\n{managed.END}\n",
                    encoding="utf-8")

    managed.write(path, BODY)
    text = path.read_text(encoding="utf-8")

    assert text.count(managed.BEGIN) == 1
    assert text.count(managed.END) == 1
    assert "old one" not in text and "old two" not in text
    assert "# Mine" in text
    assert managed.read(text) == BODY


def test_a_fenced_example_of_the_markers_is_an_example(tmp_path):
    """`AGENTS.md` is exactly the file where somebody documents this format.
    Splicing the live protocol into their code fence would leave the real
    instructions rendered as sample text."""
    path = tmp_path / "AGENTS.md"
    path.write_text("# Notes\n\nThe block looks like this:\n\n"
                    f"```\n{managed.BEGIN}\nexample\n{managed.END}\n```\n\n"
                    "My real instructions.\n", encoding="utf-8")

    managed.write(path, BODY)
    text = path.read_text(encoding="utf-8")

    assert "example" in text, "the fenced example was overwritten"
    assert "My real instructions." in text
    assert managed.read(text) == BODY


def test_a_file_written_with_unix_endings_keeps_them(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_bytes(b"# House rules\n\nWrite tests first.\n")

    managed.write(path, BODY)

    assert b"\r\n" not in path.read_bytes()

