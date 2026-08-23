"""Deterministic checks on a converted document, before a human looks at it.

None of these block anything. A batch review shows every item either way; what
these decide is which ones a reviewer should look at first, and what to tell
them. The alternative — the state before this existed — is a route that exits 0
while having silently dropped every figure in the paper.

Every check here is a string or byte operation on output we already have. There
is no I/O and no model, so running them on a hundred items costs nothing worth
measuring.
"""

from __future__ import annotations

import re
from collections import Counter

from magi.core.arxiv_id import normalize_arxiv_id
from magi.ingest import image_refs
from magi.ingest.convert_result import Finding

# Anything shorter than this is not a paper. Deliberately generous: an erratum
# or a Comment really can be three paragraphs, and a false alarm on a real short
# document is cheaper than a missed empty one.
MIN_PLAUSIBLE_WORDS = 100

# TeX that survived into the output means pandoc met a macro it could not read
# and passed it through. This is the silent counterpart of a failed conversion:
# exit code 0, garbage inline.
_LEFTOVER_TEX_RE = re.compile(
    r"\\(?:begin|end|cite[a-z]*|ref|label|newcommand|renewcommand|usepackage|"
    r"documentclass|includegraphics|bibliography|footnote|textbf|textit)\s*[\{\[]")

_FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_MATH_RE = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$", re.DOTALL)
_INPUT_RE = re.compile(r"\\(?:input|include)\s*\{")


def _prose_only(md: str) -> str:
    """Strip the places TeX is supposed to live before hunting for stray TeX."""
    without_code = _FENCE_RE.sub(" ", md)
    return _MATH_RE.sub(" ", without_code)


def _body_of(md: str) -> str:
    """Everything after the YAML frontmatter."""
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[end + 4:]
    return md


def check_payload_is_not_pdf(payload: bytes, expected: str = "LaTeX") -> Finding | None:
    """A PDF where source was expected.

    arXiv serves the PDF for submissions that were uploaded as PDF only. Five
    bytes settle it, and settling it here saves a pointless pandoc run.
    """
    if payload[:5] == b"%PDF-":
        return Finding("payload-is-pdf",
                       f"the download is a PDF, not {expected} — this submission has "
                       "no source; fall through to a PDF route")
    return None


def check_not_a_shell(md: str, tex_source: str | None = None) -> Finding | None:
    """Output implausibly short for its input.

    Named for the failure it looks for: an \\input-heavy submission where the
    main file is a stub and the conversion produced its preamble and nothing
    else. Flag, never block — a genuine four-paragraph Comment exists.
    """
    body = _body_of(md)
    words = len(body.split())
    if words >= MIN_PLAUSIBLE_WORDS:
        return None
    detail = f"the converted body is only {words} words"
    if tex_source:
        n_inputs = len(_INPUT_RE.findall(tex_source))
        if n_inputs:
            detail += (f", and the source has {n_inputs} \\input/\\include "
                       "directive(s) — the main file may not have been assembled")
    return Finding("suspiciously-short", detail)


def check_no_leftover_tex(md: str) -> Finding | None:
    """Raw TeX commands outside math and code.

    This is pandoc exiting 0 while leaving the macro it choked on inline, which
    is harder to notice than an outright failure and just as wrong.
    """
    hits = _LEFTOVER_TEX_RE.findall(_prose_only(_body_of(md)))
    if not hits:
        return None
    shown = ", ".join(sorted({h.strip() for h in hits})[:6])
    return Finding("leftover-tex",
                   f"{len(hits)} raw TeX command(s) survived into the prose "
                   f"({shown}) — pandoc could not read them")


def check_figures(referenced: int, resolved: int) -> Finding | None:
    """Figures the source referenced that the output does not have.

    Measured on arXiv 2401.00506: six referenced, zero survived, and the run
    reported success.
    """
    dropped = referenced - resolved
    if dropped <= 0:
        return None
    return Finding("figure-count-mismatch",
                   f"the source references {referenced} figure(s) but only "
                   f"{resolved} reached the output — {dropped} were dropped")


def check_image_refs(md: str) -> Finding | None:
    """Image references that will not survive the move out of staging.

    This is the check that has to be shape-aware rather than pattern-aware.
    The earlier version looked for ``](images/…)`` and nothing else, which
    means an absolute staging path — the exact failure it existed to catch —
    matched nothing and the document was reported clean. A gate that only
    recognises the correct answer cannot report a wrong one.

    So the question here is not "does this look like a broken link" but "is
    this reference of the shape every route is supposed to emit", and anything
    that is not gets named with the reason it is not.
    """
    offenders: dict[str, list[str]] = {}
    for target in image_refs.iter_targets(md):
        kind = image_refs.classify(target)
        if kind in ("portable", "external"):
            continue
        offenders.setdefault(kind, []).append(target)
    if not offenders:
        return None

    why = {
        "absolute": "absolute path — resolves only while staging exists",
        "backslash": "Windows separator — not a path to a Markdown reader",
        "escaping": "climbs out of the document's directory",
        "bare": "no directory — the file is expected to sit next to the document",
        "elsewhere": f"not under {image_refs.IMAGE_DIR_NAME}/",
        "nested": f"more than one level below {image_refs.IMAGE_DIR_NAME}/",
    }
    n = sum(len(v) for v in offenders.values())
    parts = [f"{why.get(k, k)}: {', '.join(v[:3])}" for k, v in sorted(offenders.items())]
    return Finding("image-path-not-portable",
                   f"{n} image reference(s) are not {image_refs.IMAGE_DIR_NAME}/<name> "
                   "and will break when this document is committed — "
                   + "; ".join(parts))


def check_broken_image_links(md: str, images_dir) -> Finding | None:
    """Well-formed references pointing at files that are not there.

    Rewriting a path without fetching the file leaves a wiki full of broken
    links, which looks complete and is not. Only ``images/<name>`` references
    are judged here — a malformed one is `check_image_refs`'s to report, and
    reporting it twice would say the same problem is two problems.
    """
    from pathlib import Path

    images_dir = Path(images_dir)
    targets = {t.split("/", 1)[1] for t in image_refs.iter_targets(md)
               if image_refs.classify(t) == "portable"}
    missing = sorted(t for t in targets if not (images_dir / t).is_file())
    if not missing:
        return None
    return Finding("broken-image-links",
                   f"{len(missing)} image reference(s) have no file on disk: "
                   + ", ".join(missing[:5]))


def check_identity_agrees(expected: str | None, md: str) -> Finding | None:
    """The arXiv id we asked for versus the one the output claims.

    A disagreement means a misnamed download or a wrong metadata match, and
    either way the wrong paper may have just been filed under the right name.
    """
    if not expected:
        return None
    m = re.search(r"^arxiv_id:\s*['\"]?([^'\"\n]+)", md, re.MULTILINE)
    if not m:
        return None
    found = normalize_arxiv_id(m.group(1).strip())
    if found and normalize_arxiv_id(expected) != found:
        return Finding("identity-mismatch",
                       f"asked for {expected} but the output is labelled {found}")
    return None


#: A table row, in either notation anyone here writes one in. Markdown is a row
#: of pipes; HTML is what `glm-ocr` produces no matter what it is asked for, and
#: while `ocr/tables.py` converts it, a gate that only knew Markdown would call
#: a document full of tables a document that dropped them — the loudest possible
#: false alarm, on the route where a real dropped table is the thing to catch.
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$|<tr\b", re.MULTILINE | re.IGNORECASE)

#: The environments whose openings must be matched by a closing.
_ENV_OPEN_RE = re.compile(r"\\begin\s*\{([A-Za-z*]+)\}")
_ENV_CLOSE_RE = re.compile(r"\\end\s*\{([A-Za-z*]+)\}")

#: Below this share of the source's own characters, the output is not a
#: transcription of the page — something was dropped wholesale. Set from
#: measurement: pages that converted fully recovered 96-102%, pages that lost
#: their tables recovered 41-63%, and the page that stopped mid-formula 37%.
COVERAGE_FLOOR = 0.80

#: Above this multiple of the source's characters the converter is generating
#: rather than reading. Measured: a looping page produced 17.9x its own source.
#: Set well clear of that and of legitimate expansion — LaTeX markup for dense
#: mathematics can genuinely run to several times the plain text it replaces.
INFLATION_CEILING = 4.0

#: A repeated block this long is not prose that happens to recur.
_REPEAT_WINDOW = 200

#: …provided the block is built from a unit at least this long. Below it the
#: text is uniform filler, which repeats for reasons that are not a loop.
_MIN_VARIED_PERIOD = 40

#: How far apart the scan's windows sit. A restated block of length L is only
#: visible when some window lands wholly inside it, so the stride bounds the
#: shortest restatement that can be seen — at 25 that is a short paragraph.
_REPEAT_STRIDE = 25


def check_tables_survived(md: str, source_tables: int, source_rows: int) -> Finding | None:
    """Tables the source has and the output does not.

    Measured on ``glm-ocr``: across three pages carrying two tables each,
    PyMuPDF found 151 rows and the transcription contained none — while the
    *captions* came through correctly, so the output reads as a complete page
    and the data is simply gone. That is the shape worth naming: not a
    conversion that failed, but one that succeeded around the table.
    """
    if source_tables <= 0:
        return None
    if _TABLE_ROW_RE.search(md):
        return None
    return Finding("tables-dropped",
                   f"the source page(s) contain {source_tables} table(s) with "
                   f"{source_rows} row(s) and the output has no table markup — "
                   "the caption may still be there, which is what makes this "
                   "easy to miss")


def check_environments_closed(md: str) -> Finding | None:
    """``\\begin{…}`` with no matching ``\\end{…}``.

    A model that stops mid-structure leaves exactly this. Measured on the page
    that defeated every quantisation of ``glm-ocr``: the output ends
    ``\\begin{array}{cccccccc…`` and simply stops, so the document carries an
    unclosed environment into the wiki, where it swallows everything after it
    when rendered.
    """
    opened = Counter(_ENV_OPEN_RE.findall(md))
    closed = Counter(_ENV_CLOSE_RE.findall(md))
    unclosed = {k: n - closed.get(k, 0) for k, n in opened.items() if n > closed.get(k, 0)}
    unopened = {k: n - opened.get(k, 0) for k, n in closed.items() if n > opened.get(k, 0)}
    if not unclosed and not unopened:
        return None
    parts = []
    if unclosed:
        parts.append("never closed: " + ", ".join(f"{k}×{n}" for k, n in sorted(unclosed.items())))
    if unopened:
        parts.append("closed but never opened: "
                     + ", ".join(f"{k}×{n}" for k, n in sorted(unopened.items())))
    return Finding("unclosed-environment",
                   "LaTeX environments do not balance — " + "; ".join(parts))


def _min_period(s: str) -> int:
    """Shortest unit the string is built from, via the KMP failure function.

    ``"ab" * 100`` has period 2. Real prose has a period equal to its own
    length. This is what separates a converter restating a paragraph from text
    that is merely uniform, and without it the check fires on any repetitive
    passage — a column of identical values, a list of near-identical citations.
    """
    n = len(s)
    fail = [0] * n
    k = 0
    for i in range(1, n):
        while k and s[i] != s[k]:
            k = fail[k - 1]
        if s[i] == s[k]:
            k += 1
        fail[i] = k
    return n - fail[-1] if n else 0


def check_repetition(md: str) -> Finding | None:
    """A substantial passage emitted more than once.

    A vision model that loses its place restates what it has already read.
    Measured on ``glm-ocr`` before Ollama 0.32.15: one page came back with its
    entire body twice. Kept after that fix, because the fix lives in a
    dependency the user controls and not in this repository.

    The block must be *varied* to count. Uniform filler repeats trivially and
    says nothing — flagging it would mean flagging every table of identical
    values — so a chunk built from a short unit is skipped and only genuine
    restatement is reported.
    """
    # Strip the blank lines after the frontmatter before scanning: they belong
    # to no repeated unit, so leaving them in shifts every window out of
    # alignment with the repeat and the shortest restatements slip through.
    body = _body_of(md).strip()
    if len(body) < _REPEAT_WINDOW * 2:
        return None
    for start in range(0, len(body) - _REPEAT_WINDOW, _REPEAT_STRIDE):
        chunk = body[start:start + _REPEAT_WINDOW]
        if _min_period(chunk) < _MIN_VARIED_PERIOD:
            continue
        n = body.count(chunk)
        if n > 1:
            return Finding("repetition-loop",
                           f"a {_REPEAT_WINDOW}-character passage appears {n} times — "
                           "the converter restated the page rather than finishing it")
    return None


def check_output_inflation(md: str, source_chars: int) -> Finding | None:
    """Far more text came out than the source could possibly hold.

    The other end of ``check_text_coverage``'s ratio, and the one that catches
    degenerate generation: measured at 27,281 output characters from a page
    holding 1,526 — an eighteen-fold inflation of ``& 0 & \\cdots``, produced in
    181 seconds against a normal page's 17. Uniform enough that the repetition
    check above deliberately ignores it, which is exactly why this exists.
    """
    if source_chars <= 0:
        return None
    out = len(re.sub(r"\s+", "", _body_of(md)))
    ratio = out / source_chars
    if ratio <= INFLATION_CEILING:
        return None
    return Finding("output-inflated",
                   f"the output is {ratio:.1f}x the size of the source page(s) "
                   f"({out} vs {source_chars} characters) — a converter cannot "
                   "read more text than the page contains, so this is generated, "
                   "not transcribed")


def check_text_coverage(md: str, source_chars: int) -> Finding | None:
    """Far less text came out than the source holds.

    The generic form of the two checks above, and it catches what they miss:
    it needs no table to be detected and no environment to be left open, only
    a page that arrived short. It is the reason a silently truncated page is
    reportable at all — nothing else about that output looks wrong.
    """
    if source_chars <= 0:
        return None
    out = len(re.sub(r"\s+", "", re.sub(r"\\[A-Za-z]+|[${}&\\|]", "", _body_of(md))))
    ratio = out / source_chars
    if ratio >= COVERAGE_FLOOR:
        return None
    return Finding("output-much-shorter-than-source",
                   f"the output carries {ratio:.0%} of the characters the source "
                   f"page(s) hold ({out} vs {source_chars}) — below the {COVERAGE_FLOOR:.0%} "
                   "floor, so something was dropped rather than converted")


def run_all(md: str, *, payload: bytes | None = None, tex_source: str | None = None,
            figures_referenced: int = 0, figures_resolved: int = 0,
            images_dir=None, expected_arxiv_id: str | None = None,
            source_chars: int = 0, source_tables: int = 0,
            source_rows: int = 0) -> list[Finding]:
    """Every applicable check, in the order a reviewer would care about them.

    The ``source_*`` counts come from ``textlayer.census`` and are zero when
    the source is not a local PDF — an arXiv identifier has nothing to count —
    in which case the checks that need them stand down rather than guess.
    """
    checks = [
        check_payload_is_not_pdf(payload) if payload else None,
        check_identity_agrees(expected_arxiv_id, md),
        check_not_a_shell(md, tex_source),
        check_no_leftover_tex(md),
        check_figures(figures_referenced, figures_resolved),
        check_image_refs(md),
        check_broken_image_links(md, images_dir) if images_dir else None,
        check_environments_closed(md),
        check_repetition(md),
        check_tables_survived(md, source_tables, source_rows),
        check_text_coverage(md, source_chars),
        check_output_inflation(md, source_chars),
    ]
    return [c for c in checks if c is not None]
