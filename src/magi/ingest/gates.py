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


def run_all(md: str, *, payload: bytes | None = None, tex_source: str | None = None,
            figures_referenced: int = 0, figures_resolved: int = 0,
            images_dir=None, expected_arxiv_id: str | None = None) -> list[Finding]:
    """Every applicable check, in the order a reviewer would care about them."""
    checks = [
        check_payload_is_not_pdf(payload) if payload else None,
        check_identity_agrees(expected_arxiv_id, md),
        check_not_a_shell(md, tex_source),
        check_no_leftover_tex(md),
        check_figures(figures_referenced, figures_resolved),
        check_image_refs(md),
        check_broken_image_links(md, images_dir) if images_dir else None,
    ]
    return [c for c in checks if c is not None]
