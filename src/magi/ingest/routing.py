"""Which rung of the ladder a source starts on — decided in one place.

The ladder is ``arxiv-html → tex → textlayer → mineru → ocr``, and choosing
where to enter it is one decision. It used to be two implementations that
disagreed:

* ``magi ingest auto`` asked whether a PDF had a readable, maths-free text
  layer and used it when it did;
* ``magi ingest batch-run`` sent every non-arXiv source straight to ``mineru``,
  and since ``textlayer`` sits *above* ``mineru`` on the ladder, nothing could
  ever fall back up to it. A local PDF could not reach that rung at all.

Which mattered: of 758 items in the library this was built for, 567 carry a
stored PDF, and every one of them queued through a batch skipped the free,
faithful route and spent a MinerU token or a GPU minute instead.

The split this module keeps is between two questions that look like one:

    **What should run?**  — this module. Format and content decide it, and the
    answer does not depend on what happens to be installed.
    **What can run here?** — the caller's. ``batch-run`` never asks: a rung
    that cannot run fails and the ladder falls to the next one. ``ingest auto``
    must ask, because it has no ladder to fall down.

Keeping the second out of here is what lets both callers share the first.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import NamedTuple

from magi.core.arxiv_id import normalize_arxiv_id


class TextLayerVerdict(NamedTuple):
    """Whether a PDF should be read without a model, why, and how big it is.

    Carries ``pages`` because the caller that acts on a yes wants to report it
    and would otherwise open the document a second time to find out.

    ``ok`` and ``available`` are the module's two questions, kept apart. ``ok``
    is about the document: born-digital, readable, no mathematics. ``available``
    is about this machine: is ``pymupdf4llm`` installed. Folding the second into
    the first is exactly the leak this module exists to prevent, and it showed
    up as a CI failure — a prose PDF routed to ``textlayer`` on a developer's
    machine and to ``mineru`` on a runner without the extra, from the same code
    and the same file.
    """

    ok: bool
    why: str
    pages: int = 0
    available: bool = True
    unavailable_why: str = ""


#: Suffixes that mean LaTeX source rather than a rendered document.
TEX_SUFFIXES = (".tex", ".tar.gz", ".tgz")

#: Already text — nothing to convert, so not a ladder source at all.
TEXT_SUFFIXES = (".md", ".markdown", ".txt")

#: Source types that name a paper rather than a file on disk. All three resolve
#: to an arXiv identity before anything is fetched, so all three start at the
#: rung that reads arXiv's own LaTeXML rendering.
IDENTITY_TYPES = ("arxiv", "url", "doi")

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_DOI_RE = re.compile(r"^(?:doi:)?10\.\d{4,9}/", re.IGNORECASE)

#: Verdicts already reached this process, keyed on the file's identity rather
#: than its name. A queued PDF is asked about twice — once to choose its rung,
#: once by the rung itself, which re-checks because a retry can force a route —
#: and inspecting means opening the document and enumerating its fonts. Under a
#: second each on a 115-page scan, which is nothing once and real across a
#: hundred-item batch.
_VERDICTS: dict[tuple, "TextLayerVerdict"] = {}


def _fingerprint(path):
    """Identity of the bytes, not of the name. None when it cannot be taken.

    Size and mtime rather than the path alone: staging directories get reused,
    and answering from cache about a file that has since been replaced would be
    worse than not caching at all.
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (os.path.abspath(str(path)), st.st_mtime_ns, st.st_size)


def _suffix_of(value: str) -> str:
    """Lowercased suffix, with ``.tar.gz`` treated as one."""
    name = os.path.basename(str(value).replace("\\", "/")).lower()
    return ".tar.gz" if name.endswith(".tar.gz") else os.path.splitext(name)[1]


def infer_source_type(value: str) -> str:
    """What kind of thing this is, for a record that did not say.

    Only used for queue entries written before the ledger stored the type.
    Guessing is not great, but recording ``arxiv`` for a local file — which is
    what happened before — is worse: it is a guess that has already been made
    and then written down as fact.
    """
    value = str(value)
    if _URL_RE.match(value):
        return "url"
    if _DOI_RE.match(value):
        return "doi"
    # Ask the id parser rather than looking for a dot: `2401.00506` has one and
    # is not a file, `cond-mat/0001002` has a slash and is not a path.
    if normalize_arxiv_id(value):
        return "arxiv"
    return "file"


def text_layer_verdict(path) -> TextLayerVerdict:
    """Can this PDF be read straight out of its own text layer?

    Anything that goes wrong answers *no* with a reason a person can act on,
    and never raises: this is a routing question, and routing must not be the
    thing that fails.

    ``except ImportError`` was too narrow to hold that promise. ``pymupdf4llm``
    pulls in ``onnxruntime``, and an ``onnxruntime`` too old for the models it
    ships raises ``onnxruntime.capi.onnxruntime_pybind11_state.Fail`` at import
    — not an ``ImportError``. That escaped the handler and took down the whole
    of ``ingest auto``, which had merely been *asking a question* about one
    file.

    The gate is asked *before* the extractor is checked for, even though a
    missing extractor sends the file down the ladder either way. The order is
    what makes the reason worth reading: "this PDF has a clean, maths-free text
    layer and could have been read for free, but the extractor is missing"
    tells someone to install it. "the extractor is missing" does not say
    whether installing it would have helped this file at all. The gate itself
    runs on PyMuPDF, a hard dependency, so asking first costs nothing.

    A missing extractor makes ``available`` false and leaves ``ok`` alone. The
    document did not change because this machine is missing a package, and a
    caller with a ladder underneath it should still start here and fall — it
    gets the sentence naming the package that way, instead of silently
    spending a MinerU token on something that is free once installed.
    """
    key = _fingerprint(path)
    if key is not None and key in _VERDICTS:
        return _VERDICTS[key]

    try:
        from magi.ingest import textlayer
        verdict = textlayer.inspect(Path(path))
    except Exception as exc:  # noqa: BLE001
        return TextLayerVerdict(False, f"could not inspect the PDF ({type(exc).__name__}: {exc})")

    pages = getattr(verdict, "pages", 0) or 0
    if not verdict.route_here:
        return _remember(key, TextLayerVerdict(False, verdict.reason, pages))

    missing = ""
    try:
        import pymupdf4llm  # noqa: F401 — presence check only
    except ImportError:
        missing = ("pymupdf4llm is not installed "
                   "(pip install 'magi-research[textlayer]')")
    except Exception as exc:  # noqa: BLE001
        hint = ("its onnxruntime is too old — pip install -U 'onnxruntime>=1.18'"
                if "IR version" in str(exc) else "reinstall it")
        missing = (f"pymupdf4llm could not be loaded "
                   f"({type(exc).__name__}: {exc}); {hint}")

    if missing:
        return _remember(key, TextLayerVerdict(
            True,
            f"{verdict.reason}, so this can be read without OCR — but {missing}",
            pages, available=False, unavailable_why=missing))

    return _remember(key, TextLayerVerdict(True, verdict.reason, pages))


def _remember(key, verdict: TextLayerVerdict) -> TextLayerVerdict:
    if key is not None:
        _VERDICTS[key] = verdict
    return verdict


def forget_verdicts() -> None:
    """Empty the verdict cache. For tests, which stub the gate underneath it."""
    _VERDICTS.clear()


def first_rung(source_type: str, value: str) -> tuple[str, str]:
    """The rung this source starts on, and why, as a sentence for a log line.

    Never consults configuration or installed tooling. A caller with a ladder
    beneath it wants the *best* rung and will fall to the next one when this
    one fails; a caller without one has to check availability itself, and can,
    because the two questions are separate.
    """
    if source_type in IDENTITY_TYPES:
        return "arxiv-html", ("an arXiv identity — its LaTeXML rendering carries "
                              "the original TeX verbatim")

    suffix = _suffix_of(value)
    if suffix in TEXT_SUFFIXES:
        # Not a ladder source at all. Saying so here beats letting it fall to
        # a converter that would hand a Markdown file to a PDF reader.
        return "add", "already text — there is nothing to convert"

    if suffix in TEX_SUFFIXES:
        return "tex", "LaTeX source — nothing to recognise, only to convert"

    if suffix == ".pdf":
        # Before spending a MinerU token or a GPU minute, ask whether this PDF
        # needs either. A born-digital document with no mathematics can be read
        # straight out of its own text layer — free, fast and faithful. One
        # with mathematics cannot: the characters come out fine and the
        # two-dimensional structure does not, so it goes to a model regardless.
        verdict = text_layer_verdict(value)
        if verdict.ok:
            return "textlayer", f"PDF — {verdict.why}"
        return "mineru", f"PDF — {verdict.why}"

    return "mineru", (f"no signal from {suffix or 'this source'} — starting at the "
                      "cloud converter and letting the ladder fall")
