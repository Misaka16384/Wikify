"""The part of `AGENTS.md` the CLI owns, and the part it must never touch.

Every host reads an instruction file at the top of a session — `AGENTS.md` for
Codex and most others, `CLAUDE.md` for Claude Code, which in a MAGI workspace
holds nothing but `@AGENTS.md` so there is one text and not two. That file is
shared property: MAGI needs to keep its protocol current across upgrades, and
the person needs to write project instructions that survive the next upgrade.

So the file is split by two markers. Between them belongs to the CLI and is
rewritten whole on every `magi install`; everything outside belongs to whoever
wrote it and is never read, moved or reflowed. The alternative — appending, the
way most tools do it — is how an instruction file ends up with four copies of a
protocol that changed three times, each contradicting the last.

Three properties this has to have, because all three failure modes are silent:

* **Idempotent.** Writing the same body twice leaves identical bytes. A block
  that grows a newline per run turns every upgrade into a diff nobody reads.
* **Order-preserving.** The block stays where it was — it does not migrate to
  the end of the file when the body changes, because a person put their own
  text around it deliberately.
* **Self-healing.** A file that somehow ends up with two blocks converges to
  one. Two blocks is the same disease as appending, arrived at differently:
  two protocols in one file and no way to know which the host obeyed.

Markers are read the way the rest of the repo reads markdown structure —
`md_blocks.classify_lines`, so a fenced example of what the markers look like
is an example and not a block. Without that, documenting this format inside
`AGENTS.md` would cause the next `install` to splice the live protocol into the
middle of the code fence, where a host reads it as sample text.
"""

from __future__ import annotations

from pathlib import Path

from . import md_blocks
from .wiki_common import atomic_write, file_newline, normalize_newlines

BEGIN = "<!-- magi:begin -->"
END = "<!-- magi:end -->"


def block(body: str) -> str:
    """One managed block: markers plus the body, no trailing whitespace."""
    return f"{BEGIN}\n{body.strip()}\n{END}"


def _pairs(labelled) -> list:
    """`[(begin_index, end_index), ...]` for every complete block.

    Markers inside a code fence are examples. An opener with no closer, or a
    closer with no opener, is somebody mid-edit: it is left exactly where it
    is rather than treated as licence to decide where their file ends.
    """
    found: list = []
    start = None
    for index, (label, line) in enumerate(labelled):
        if label == md_blocks.CODE:
            continue
        stripped = line.strip()
        if stripped == BEGIN and start is None:
            start = index
        elif stripped == END and start is not None:
            found.append((start, index))
            start = None
    return found


def _labelled(text: str) -> list:
    return md_blocks.classify_lines(normalize_newlines(text or ""))


def read(text: str) -> str | None:
    """The body of the first managed block, or `None` when there is none."""
    labelled = _labelled(text)
    pairs = _pairs(labelled)
    if not pairs:
        return None
    start, end = pairs[0]
    return "\n".join(line for _, line in labelled[start + 1:end]).strip()


def apply(text: str, body: str) -> str:
    """`text` with exactly one managed block, set to `body`.

    Every complete block is removed and one is put back where the first one
    was, so a file that picked up a duplicate converges instead of carrying the
    stale copy forever. Text outside the blocks comes back as it went in, with
    one exception: the blank lines at the two seams normalise to exactly one,
    which is what makes writing the same body twice a byte-for-byte no-op.
    """
    labelled = _labelled(text)
    pairs = _pairs(labelled)
    lines = [line for _, line in labelled]

    if not pairs:
        existing = "\n".join(lines).strip()
        if not existing:
            return block(body) + "\n"
        return f"{block(body)}\n\n{existing}\n"

    removed = set()
    for start, end in pairs:
        removed.update(range(start, end + 1))

    at = pairs[0][0]
    head = "\n".join(lines[index] for index in range(at) if index not in removed).rstrip("\n")
    tail = "\n".join(lines[index] for index in range(at, len(lines))
                     if index not in removed).strip("\n")

    parts = [part for part in (head, block(body), tail) if part]
    return "\n\n".join(parts) + "\n"


def read_tolerantly(path) -> str:
    """`AGENTS.md` as text, whatever a person's editor saved it as.

    `state.block_drift` reads this same file with replacements, reports
    "AGENTS.md is missing N accepted rule(s) — `magi install` rewrites it",
    and blocks the session on it. So `magi install` has to survive the file
    that gate is complaining about, or the gate names a fix that cannot run.

    Not `errors="replace"`, which is right for a reader and wrong here: the
    text goes straight back to disk, and replacement would turn one smart
    quote in somebody's project instructions into U+FFFD permanently.
    `surrogateescape` carries undecodable bytes through `str` untouched, and
    the matching `errors` on the write puts them back exactly as they were.
    """
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="surrogateescape")


def write(path, body: str) -> bool:
    """Set the managed block in `path`. Returns True when the file changed.

    Reporting "changed" rather than always rewriting is what lets `install` be
    run on every session start without touching mtimes, which editors and file
    watchers both react to. The file keeps whatever line endings it already
    had: these files travel between macOS and Windows sessions, and rewriting
    all of them to suit this machine turns one edit into a whole-file diff.
    """
    path = Path(path)
    existing = read_tolerantly(path)
    updated = apply(existing, body)
    if normalize_newlines(existing) == updated:
        return False
    atomic_write(path, updated, newline=file_newline(path),
                 errors="surrogateescape")
    return True


# ---------------------------------------------------------------- the body


#: What the human is asked for, per coaching level. The block is read at the
#: start of every session on every host, so this is the one place the protocol
#: is stated — a skill repeating it is a skill charging for it again.
_COACHING = {
    "off": "",
    "light": ("When a proposition opens or closes, ask the human for a one-line prediction "
              "and transcribe it (`bet:` or `decisions.md`). \"Don't know\" is an answer."),
    "strict": ("Ask the human for a prediction before a derivation starts, and do not start "
               "without one. Transcribe it (`bet:` or `decisions.md`). \"Don't know\" is an "
               "answer; silence is not."),
}

_BODY = """# MAGI workspace: {name}

Scope: {scope}

Run `magi next` first — it reads the notes and says what to do, and never acts.
`magi --help` is the command surface; `magi guide --search "<error>"` is the manual.

## Where things live
- `raw/` — sources. Never edit by hand: re-ingest instead. The pipeline does
  repair them (`magi math format` fixes OCR math artifacts here) — that is
  tooling, not you.
- `wiki/references/` — compiled from `raw/`. Rebuild, never hand-edit.
- `wiki/concepts/`, `wiki/topics/` — shared knowledge. Edit freely.
- `drafts/` — the working out. `threads/` — propositions, questions, lines.
- `inbox/notes.md` — anything, unsorted. `decisions.md` — what a person decided.
- `output/` — derived and rebuildable, **except** `ingest/ radar/ reflect/
  adopt/ llm-ledger.jsonl`: those record what a person decided, what it cost,
  and how to undo a move. Nothing rebuilds those.

## Invariants
1. Evidence points at `raw/`, never at a card compiled from it.
2. One file, one temperature — a conjecture inside a concept card is a
   proposition; open one and leave a wikilink.
3. A status flip carries a post: `magi thread status`, never an editor.
4. A sub-agent never asks the human. Return one line instead:
   `NEEDS-DECISION: <question> | options: <a> / <b> | default if unanswered: <x>`
   Whoever spawned it asks once, for all of them. In a scheduled run or a
   piped run there is nobody: do not guess and do not wait — stop and say
   what you would have asked.
5. Before a fan-out, say what it costs: "34 pages, so about 34 sub-agent calls".

## Before you stop
`magi sync --close` — it refuses while something happened that nobody wrote down.
{coaching_section}
Never answer a research question from memory: retrieve, then cite `[[wikilinks]]`.
"""


#: How many earned rules the block may carry. Separate from the template's
#: forty lines, and small: every line here is read at the start of every
#: session on every host, so a rule that goes in has to be worth what all of
#: them pay to read it. When it is full, something comes out before something
#: goes in.
RULE_BUDGET = 7


def template(name: str, scope: str, coaching: str = "light") -> str:
    """The part of the block that ships with MAGI.

    This is what the ratchet measures and what a hash guards. It is the same
    for every workspace at a given version; what differs is the rules a person
    accepted, and those are rendered separately from a file that records who
    decided each one.
    """
    prompt = _COACHING.get(coaching, _COACHING["light"])
    section = f"\n## When the human is here\n{prompt}\n" if prompt else ""
    return _BODY.format(name=name, scope=scope, coaching_section=section)


def rules_section(rules) -> str:
    """The rules a person accepted, one line each.

    Rendered, never truncated. The ledger is the truth and the block may not
    say less than it — a budget that silently dropped the eighth rule would
    leave somebody sure they had accepted something the agent never sees.
    Refusing a new one is `magi reflect accept`'s job.
    """
    # Every kind of line break, not just `\n`: a rule carrying a stray `\r`
    # rendered as two lines, which made `write` see a difference every time and
    # rewrite the file on every run forever.
    lines = [" ".join(str(getattr(rule, "text", rule)).split())
             for rule in (rules or [])]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    return "\n## Rules this workspace earned\n" + "\n".join(
        f"- {line}" for line in lines) + "\n"


def body(name: str, scope: str, coaching: str = "light", rules=None) -> str:
    """The managed block's contents. Nothing in here explains itself.

    Every line is read at the start of every session on every host, so the
    reasons live in `docs/design-v2.md` and the guide, and this says only what
    to do. Forty lines is the template's budget
    (`tests/test_v2_ratchets.py`); the way to add something is to take
    something out.

    `rules` are what a person accepted from the slow loop — passed in rather
    than read here, so this function stays pure and the one place that knows
    where the ledger lives is the one that writes files.
    """
    return template(name, scope, coaching) + rules_section(rules)
