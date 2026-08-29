"""The docs describe what the code does, checked mechanically.

`test_docs_in_sync` verifies that every command group is *mentioned* somewhere.
That is a much weaker property than it sounds, and the v2 guide audit showed how
much it lets through: of eight false-statement clusters, six were about what the
docs said a thing *is* or *does*, not about whether it was named. The worst of
them — the directory tree under "what `magi init` generates" — listed `log.md`
and `wiki/theses/` and omitted `threads/` and `decisions.md`, and had been wrong
for an entire major version. It is the first thing a new reader looks at.

design-v2 §1.4: a rule that can be written as a test is not written as prose.
`RELEASING.md` now asks a human to check every "X is Y" sentence against the
design, which is the right instrument for prose. These two tests take the part
of that job a machine can do and make it impossible to get wrong again:

1. **Every `magi <cmd>` in the docs is a command that exists** — with an
   explicit allowlist for retired commands named in historical context, because
   the migration chapter has to be able to say what you are migrating *from*.
2. **The generated-directory tree equals what the scaffolder actually makes** —
   compared against a real `magi init` into a temp directory, never against a
   list somebody typed here.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Every document that shows commands to a person. The packaged README copies
#: are byte-identical to the originals (`test_launch_directory` enforces that)
#: and are checked anyway: this test is about what ships in the wheel, and
#: "another test guarantees it" is how a pair of files starts drifting.
DOCS = (
    "src/magi/docs/guide.en.md",
    "src/magi/docs/guide.zh.md",
    "src/magi/docs/readme.en.md",
    "src/magi/docs/readme.zh.md",
    "README.md",
    "README_en.md",
)

#: Commands that no longer exist and are named on purpose. Each needs a reason,
#: because an allowlist without one becomes the place stale entries go to hide.
#:
#: The test *records* these rather than failing on them. A doc-sync test that
#: fails the first time somebody legitimately writes "the old `magi hub`" is a
#: test that gets deleted rather than fixed, and then nothing checks anything.
RETIRED = {
    "hub": "v1's hub is what `magi migrate` migrates away from; the migration "
           "chapter cannot describe that without naming it",
}

#: Words that follow `magi` without being a claim that a command exists. Kept
#: apart from RETIRED because the reason is different and so is the fix: a
#: RETIRED entry that comes back is a bug, one of these is just prose.
#:
#: `compile` is the instructive one. The guide says "`magi compile` does not
#: exist and will not; this is understanding, not a pipeline" — a sentence that
#: is *correct about the absence*, and that the first version of this test
#: flagged as a false claim.
NEVER_A_COMMAND = {
    "compile": "named only to say it does not exist — compiling needs an LLM, "
               "so it is a skill and never a command",
    "mcp": "a forward reference: the `--json` shapes are described as the "
           "future MCP tool contracts, which are not built",
}

#: Not commands: placeholders, flags, and anything not spelled like a command.
#: The lowercase rule is what separates the invocation `magi next` from the
#: noun phrase "the magi CLI", which no reader has ever mistaken for a command
#: and which appears in every one of these documents.
_NOT_A_COMMAND = re.compile(r"^(?:--|<|\.\.\.|[^a-z])")

#: `magi <word>` wherever it appears — in a fence, inline in backticks, or in
#: running prose. Deliberately loose about what precedes it and strict about
#: what counts as the word after, because a missed occurrence is a missed bug.
_INVOKED = re.compile(r"\bmagi\s+([A-Za-z0-9_<>-]+)")

#: `` `family *` `` — how these docs say "this whole command family". It is a
#: claim that the family exists, and it is the form the `hub *` bug took: in
#: "`magi init`, `hub *`, `sync`, ... have no buttons" only the first item
#: carries the word `magi`, so the pattern above slept straight through the one
#: bug this test was written for. Verified by putting the bug back.
_FAMILY = re.compile(r"`([a-z][a-z-]*) \*`")


def _commands():
    from magi.cli import _COMMANDS

    singles = {key[0] for key in _COMMANDS if len(key) == 1}
    groups = {key[0] for key in _COMMANDS if len(key) == 2}
    pairs = {" ".join(key) for key in _COMMANDS if len(key) == 2}
    return singles, groups, pairs


def _mentions(path: Path):
    """`(command, line number, form)` for every command this document names.

    `form` is `"prose"` for `magi <cmd>` and `"family"` for `` `<cmd> *` ``,
    and the difference decides whether a retired name is forgivable.
    """
    out = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for found in _INVOKED.finditer(line):
            word = found.group(1).strip("`*_.,:;)")
            if not word or _NOT_A_COMMAND.match(word):
                continue
            out.append((word, number, "prose"))
        for found in _FAMILY.finditer(line):
            out.append((found.group(1), number, "family"))
    return out


@pytest.mark.parametrize("doc", DOCS)
def test_every_command_the_docs_name_is_a_command_that_exists(doc):
    """The `hub *` entry in the WebUI chapter survived the whole of v2 this
    way: hubs were retired in M3 and the sentence listing `magi hub` among
    commands-without-buttons was never touched, so it read as a real command
    that merely lacked a button."""
    singles, groups, _pairs = _commands()
    known = singles | groups

    excused = set(RETIRED) | set(NEVER_A_COMMAND)
    unknown = [(word, number) for word, number, form in _mentions(REPO / doc)
               # A retired name is forgiven in prose and never in the family
               # form: `` `hub *` `` only ever appears in a list of commands
               # that exist, so there is no historical reading of it. Forgiving
               # it everywhere is what let the original bug survive two
               # attempts to catch it here.
               if word not in known and (word not in excused or form == "family")]

    assert not unknown, (
        f"{doc} names commands that do not exist: {unknown}\n"
        f"Either the command was retired (add it to RETIRED with a reason) or "
        f"the docs are describing something that was never built.")


@pytest.mark.parametrize("doc", DOCS)
def test_a_retired_command_is_only_named_where_history_needs_it(doc):
    """Recorded, not forbidden — but visible, so an entry that stops being
    historical is noticed rather than inherited."""
    named = {word for word, _, _form in _mentions(REPO / doc) if word in RETIRED}
    for word in named:
        assert RETIRED[word], f"{doc} names retired `magi {word}` with no reason on file"


def test_the_allowlists_have_no_entries_that_are_actually_commands():
    """An entry that comes back to life must leave the list, or the list starts
    excusing real commands from the check above. `compile` is the one to watch:
    if it ever becomes a command, this fails and says so."""
    singles, groups, _pairs = _commands()
    for name, table in (("RETIRED", RETIRED), ("NEVER_A_COMMAND", NEVER_A_COMMAND)):
        alive = sorted(set(table) & (singles | groups))
        assert not alive, f"these are real commands and do not belong in {name}: {alive}"


def test_every_excuse_has_a_reason_on_file():
    """An allowlist without reasons is where stale entries go to hide."""
    for table in (RETIRED, NEVER_A_COMMAND):
        for word, why in table.items():
            assert why and len(why) > 20, f"`magi {word}` is excused with no real reason"


# --------------------------------------------------------------------------
# the tree
# --------------------------------------------------------------------------

#: The fenced block that claims to show a scaffolded workspace. Recognised by
#: its first line being a bare `<something>/` — a stable marker that does not
#: depend on the surrounding prose, which is translated.
_TREE_FIRST_LINE = re.compile(r"^[A-Za-z0-9_.-]+/$")

#: A top-level entry in that tree: `├─ name` or `└─ name`. Nested lines are
#: indented and are deliberately not matched — the claim under test is about
#: what `magi init` puts at the root.
_TREE_ENTRY = re.compile(r"^[├└]─\s+(\S+)")


def _documented_trees(path: Path):
    """Every workspace tree in one document, as a set of top-level names."""
    trees, block, inside = [], [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            if inside:
                first = next((b for b in block if b.strip()), "")
                if _TREE_FIRST_LINE.match(first.strip()):
                    trees.append({m.group(1).rstrip("/") + ("/" if m.group(1).endswith("/") else "")
                                  for m in (_TREE_ENTRY.match(b) for b in block) if m})
                block, inside = [], False
            else:
                inside = True
            continue
        if inside:
            block.append(line)
    return trees


@pytest.fixture(scope="module")
def scaffolded(tmp_path_factory):
    """What `magi init` really creates. Never a list typed into this file."""
    path = tmp_path_factory.mktemp("scaffold")
    done = subprocess.run(
        [sys.executable, "-m", "magi", "init", "--topic-dir", str(path),
         "--name", "T"], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return {entry.name + ("/" if entry.is_dir() else "")
            for entry in path.iterdir() if not entry.name.startswith(".")}


@pytest.mark.parametrize("doc", ["src/magi/docs/guide.en.md",
                                 "src/magi/docs/guide.zh.md"])
def test_the_generated_tree_matches_what_init_actually_creates(doc, scaffolded):
    """Wrong for an entire major version, in the first thing a new reader
    looks at: the English tree listed `log.md` (nothing writes to it any more)
    and `wiki/theses/` (retired), and omitted `threads/` and `decisions.md` —
    the two directories the whole of v2 is about."""
    trees = _documented_trees(REPO / doc)
    assert trees, f"{doc} has no workspace tree — the marker or the fence moved"

    for tree in trees:
        # `_index.md` is generated per directory and described in the prose
        # under the tree rather than listed in it.
        claimed = {name for name in tree if name != "_index.md"}
        invented = claimed - scaffolded
        missing = {name for name in scaffolded if name != "_index.md"} - claimed

        assert not invented, (
            f"{doc} claims `magi init` creates {sorted(invented)}, and it does not")
        assert not missing, (
            f"{doc} omits {sorted(missing)} from what `magi init` creates")


def test_the_family_idiom_is_checked_too():
    """A guard on the guard. If `_FAMILY` ever stops matching, the command
    check silently narrows to the `magi <cmd>` form and the exact bug it was
    written for walks back in."""
    found = {word for word, _, form in _mentions(REPO / "src/magi/docs/guide.en.md")
             if form == "family"}
    assert "tags" in found and "math" in found, (
        "the `family *` idiom is no longer being read out of the guide")


def test_the_tree_marker_is_stable_enough_to_find(scaffolded):
    """If the parser silently found nothing, the two tests above would pass on
    an empty set and the tree could rot again unwatched."""
    for doc in ("src/magi/docs/guide.en.md", "src/magi/docs/guide.zh.md"):
        trees = _documented_trees(REPO / doc)
        assert len(trees) == 1, f"{doc}: expected exactly one workspace tree, saw {len(trees)}"
        assert len(trees[0]) >= 8, f"{doc}: the tree parsed to {trees[0]}, which is too small to be it"
