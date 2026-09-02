import argparse
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import yaml
from datetime import datetime
from pathlib import Path

from magi.core.arxiv_id import ARXIV_ID_RE, abs_url, normalize_arxiv_id
from magi.core.config_loader import load_config, get as cfg_get
from magi.ingest.convert_result import ConversionResult

#: `\title`, with the optional short-title argument LaTeX allows and which
#: the old pattern could not see past: `\title[Short]{Long}` matched nothing,
#: so the paper was filed under its arXiv id.
_TITLE_START_RE = re.compile(r"\\title\s*(?:\[[^\]]*\]\s*)?\{")


def _balanced(text: str, open_at: int) -> str | None:
    """The contents of the brace group starting at `open_at`.

    Counted rather than matched to the first `}`: a title with any markup in
    it — `\title{A \textbf{B} C}` — was truncated at the inner brace, which
    produced a title that looked deliberate and was half a sentence.
    """
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_at + 1:i]
    return None


def extract_title(tex_content):
    m = _TITLE_START_RE.search(tex_content)
    if not m:
        return None
    body = _balanced(tex_content, m.end() - 1)
    if body is None:
        return None
    # Drop the commands, keep their arguments: `\textbf{Foo}` is "Foo", and a
    # line break in a two-line title is a space rather than nothing.
    body = re.sub(r"\\\\", " ", body)
    body = re.sub(r"\\[a-zA-Z]+\s*", " ", body)
    body = body.replace("{", " ").replace("}", " ")
    return " ".join(body.split()) or None

# Archive suffixes arXiv actually serves. Kept as one predicate used at every
# decision point: this used to be tested twice with two different expressions
# (`.tar.gz` for the slug, `.tar.gz` again for whether to extract), so a .tgz —
# which auto.py's TEX_SUFFIXES happily routes here — passed routing, failed the
# extract test, and got handed to pandoc as raw gzip.
_TAR_SUFFIXES = ('.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz', '.tar')


def _is_tar_archive(path):
    return str(path).lower().endswith(_TAR_SUFFIXES)


def _archive_slug(base_name):
    """Filename stem, with multi-part archive suffixes removed whole."""
    lowered = base_name.lower()
    for suffix in _TAR_SUFFIXES:
        if lowered.endswith(suffix):
            return base_name[:-len(suffix)]
    if lowered.endswith('.tex'):
        return base_name[:-4]
    return os.path.splitext(base_name)[0]


# \input{foo} / \include{foo} / plain-TeX \input foo — the .tex is usually omitted.
_INPUT_RE = re.compile(r'\\(?:input|include)\s*(?:\{([^}]+)\}|([A-Za-z0-9_./-]+))')

# An arXiv bundle routinely carries more than one \documentclass: supplementary
# material, a response-to-referee letter, a \documentclass{standalone} TikZ
# figure. Names that betray a non-paper role.
_NOT_MAIN_HINTS = ("supp", "si_", "_si", "appendix", "response", "referee",
                   "cover", "letter", "reply", "readme", "diff")
_MAIN_HINTS = ("main", "paper", "ms", "manuscript", "article", "root")


def _tex_files(directory):
    for root, _, files in os.walk(directory):
        for name in files:
            if name.lower().endswith('.tex'):
                yield os.path.join(root, name)


def _read_text(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except OSError:
        return ""


def _included_stems(text):
    """Bare stems this file pulls in via \\input / \\include."""
    stems = set()
    for m in _INPUT_RE.finditer(text):
        target = (m.group(1) or m.group(2) or "").strip()
        if not target:
            continue
        stem = os.path.basename(target)
        if stem.lower().endswith('.tex'):
            stem = stem[:-4]
        if stem:
            stems.add(stem.lower())
    return stems


def find_main_tex(directory, slug=None):
    """Pick the main .tex of an unpacked source bundle.

    First-match-wins on the literal string ``\\documentclass`` picks whichever
    file ``os.walk`` happens to reach first, which on a real submission is as
    likely to be the supplement or a standalone figure as the paper. Rank
    instead: a file that another file \\input's is by definition not the root,
    a shallower file beats a nested one, and the filename itself is evidence.
    """
    candidates = []
    included = set()
    for path in _tex_files(directory):
        text = _read_text(path)
        included |= _included_stems(text)
        if r'\documentclass' in text:
            candidates.append((path, text))

    if not candidates:
        # No \documentclass anywhere: fall back to any .tex, deterministically.
        anything = sorted(_tex_files(directory),
                          key=lambda p: (p.count(os.sep), len(p), p.lower()))
        return anything[0] if anything else None

    slug_stem = (os.path.basename(slug).lower() if slug else None)

    def score(item):
        path, text = item
        stem = os.path.splitext(os.path.basename(path))[0].lower()
        rel_depth = os.path.relpath(path, directory).count(os.sep)
        s = 0
        # Being \input by something else disqualifies a file as the root.
        if stem in included:
            s -= 100
        # A real paper has a body; a standalone figure wrapper usually does not.
        if r'\begin{document}' in text:
            s += 50
        if slug_stem and stem == slug_stem:
            s += 30
        if any(h == stem or stem.startswith(h) for h in _MAIN_HINTS):
            s += 20
        if any(h in stem for h in _NOT_MAIN_HINTS):
            s -= 40
        # A standalone/subfiles class is a figure or fragment, not the paper.
        if re.search(r'\\documentclass[^\n]*\{(standalone|subfiles)\}', text):
            s -= 60
        s -= rel_depth * 5
        return s

    # Sort by score, then by the deterministic tie-breaks the docstring promises.
    ranked = sorted(candidates,
                    key=lambda it: (-score(it), it[0].count(os.sep),
                                    len(it[0]), it[0].lower()))
    return ranked[0][0]

# Figure extensions we can resolve from a \includegraphics target.
_IMG_EXTS = (".pdf", ".eps", ".ps", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".svg")


#: TeX's ``true`` dimension prefix (``0.3truein``), which pandoc's dimension
#: parser does not know. It fails two different ways depending on a space:
#: ``\vskip 0.3truein`` is a hard parse error that loses the whole document,
#: while ``\vskip 0.3 truein`` parses and emits the word "truein" into the body
#: as text. One breaks loudly, the other quietly.
_TRUE_DIMEN_RE = re.compile(r"(\d)\s*true(in|cm|mm|pt|bp|pc|dd|cc|sp)\b")

#: How papers referenced figures before ``graphicx`` won. ``\epsfbox`` takes the
#: filename directly; ``\epsfig``/``\psfig`` take ``file=`` among key-values.
_EPSFBOX_RE = re.compile(r"\\epsfbox\s*\{([^{}]*)\}")
_EPSFIG_RE = re.compile(r"\\(?:epsfig|psfig)\s*\{([^{}]*)\}")


def modernise_tex(tex_content):
    """Rewrite the pre-``graphicx`` dialect into the one pandoc reads.

    arXiv's back catalogue is full of papers that predate the packages pandoc
    assumes. Measured on cond-mat/0001002 (submitted 2000, ``\\documentstyle``
    rather than ``\\documentclass``):

    * ``\\vskip 0.3truein`` — pandoc stops with a parse error and returns
      **nothing at all**. The same glue written ``0.3 truein`` parses, and puts
      the literal word "truein" in the body instead. Normalising the unit fixes
      both: 0 characters out becomes 79,090.
    * ``\\epsfbox`` and ``\\epsfig`` — the figure macros of that era. Pandoc
      knows neither, so all thirteen figures in that paper were invisible to it
      even after the document parsed. Translated to ``\\includegraphics``, which
      is what they mean.

    Returns ``(tex, counts)``; pure, so the caller decides what to write.
    """
    def _file_from_kv(m):
        for part in m.group(1).split(","):
            key, _, value = part.partition("=")
            if key.strip().lower() == "file":
                return "\\includegraphics{" + value.strip() + "}"
        return m.group(0)          # no file= to find: leave it exactly as it was

    counts = {}
    tex_content, counts["true_dimens"] = _TRUE_DIMEN_RE.subn(r"\1\2", tex_content)
    tex_content, counts["epsfbox"] = _EPSFBOX_RE.subn(
        lambda m: "\\includegraphics{" + m.group(1).strip() + "}", tex_content)
    tex_content, counts["epsfig"] = _EPSFIG_RE.subn(_file_from_kv, tex_content)
    return tex_content, counts


#: Macros whose braced argument is not a figure wrapper even when a figure is
#: inside it. Pandoc understands these and unwrapping would lose meaning.
_KEEP_WRAPPED = {"includegraphics", "caption", "subcaption", "label",
                 "href", "url", "begin", "end"}

_MACRO_CALL_RE = re.compile(r"\\([a-zA-Z@]+)\s*(?:\[[^\]]*\]\s*)*\{")

#: A macro being *defined*, not called. ``\newcommand\frm[1]{\includegraphics{#1}}``
#: matches the call pattern exactly, and unwrapping it destroys the definition —
#: on a real paper it produced ``\newcommand\includegraphics{#1}``, redefining
#: the very command everything downstream depends on, and pandoc then failed on
#: a line 200 lines away. A wrapper is something a figure is *passed to*; the
#: name right after a definition command is not that.
_DEFINING_RE = re.compile(
    r"\\(?:new|renew|provide)command\*?\s*$|\\def\s*$|\\let\s*$"
    r"|\\DeclareRobustCommand\*?\s*$|\\newenvironment\*?\s*$")


def unwrap_figure_macros(tex_content):
    """Strip macros that merely wrap an ``\\includegraphics``, keeping the inside.

    Pandoc's LaTeX reader discards a macro it does not know **together with its
    arguments**, so a figure wrapped in one vanishes and its caption does not.
    That is the whole of arXiv 2401.00506's missing figures, and the mechanism
    is worth stating exactly because the note it replaces blamed the route:

        \\includegraphics[width=0.5\\textwidth]{sbs}          -> ![](sbs.jpg)
        \\subfigure[]{\\includegraphics[...]{disp}}           -> <figure> with
                                                               only a caption

    ``\\subfigure`` (package ``subfigure``) and ``\\subfloat`` (package
    ``subfig``) are the two standard ways to build a multi-panel figure, which
    is most figures in a physics paper. Rather than enumerate them, this
    unwraps *any* macro whose braced argument contains an ``\\includegraphics``
    — the same trap with a different package name is then already handled.

    Returns ``(tex, n_unwrapped)``. Pure; the caller decides what to write.
    """
    marker = "\\includegraphics"
    total = 0
    for _ in range(4):          # a panel can be wrapped more than once
        out, i, n = [], 0, 0
        while True:
            m = _MACRO_CALL_RE.search(tex_content, i)
            if not m:
                out.append(tex_content[i:])
                break
            # The figure is not always in the first argument:
            # `\resizebox{2cm}{!}{\includegraphics{...}}` puts it in the third,
            # and pandoc drops that one too — measured, along with \scalebox,
            # \makebox and \raisebox. (\parbox is the odd one out and keeps it.)
            # So read the consecutive braced groups and take whichever holds the
            # graphic; in every one of these macros that is the content group.
            groups, k = [], m.end() - 1
            while len(groups) < 3 and k < len(tex_content) and tex_content[k] == "{":
                depth, j = 1, k + 1
                while j < len(tex_content) and depth:
                    if tex_content[j] == "{":
                        depth += 1
                    elif tex_content[j] == "}":
                        depth -= 1
                    j += 1
                if depth:       # unbalanced source; leave it exactly as it was
                    groups = []
                    break
                groups.append((tex_content[k + 1:j - 1], j))
                k = j
                while k < len(tex_content) and tex_content[k] in " \t":
                    k += 1

            hit = next(((inner, end) for inner, end in groups if marker in inner), None)
            defining = _DEFINING_RE.search(tex_content[:m.start()])
            if hit and m.group(1) not in _KEEP_WRAPPED and not defining:
                out.append(tex_content[i:m.start()])
                out.append(hit[0])
                n += 1
                i = hit[1]
            else:
                # Step just past the brace so nested wrappers are still seen.
                out.append(tex_content[i:m.end()])
                i = m.end()
        tex_content = "".join(out)
        total += n
        if not n:
            break
    return tex_content, total


def _graphics_search_dirs(tex_content, tex_dir):
    """Directories to look for figures in: tex dir + \\graphicspath + common subdirs."""
    dirs = [tex_dir]
    for m in re.finditer(r'\\graphicspath\s*\{((?:\s*\{[^{}]*\}\s*)+)\}', tex_content, re.S):
        for p in re.findall(r'\{([^{}]*)\}', m.group(1)):
            p = p.strip().replace('\\', '/')
            if p:
                dirs.append(os.path.normpath(os.path.join(tex_dir, p)))
    for sub in ('figures', 'figs', 'fig', 'images', 'img', 'plots', 'graphics'):
        d = os.path.join(tex_dir, sub)
        if os.path.isdir(d):
            dirs.append(d)
    seen, out = set(), []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _resolve_figure(target, search_dirs):
    """Resolve a possibly extension-less / sub-pathed \\includegraphics target to a real file."""
    target = target.strip().strip('"').replace('\\', '/')
    base, ext = os.path.splitext(target)
    for d in search_dirs:
        if ext.lower() in _IMG_EXTS and os.path.isfile(os.path.join(d, target)):
            return os.path.join(d, target)
        for e in _IMG_EXTS:                       # handle missing or wrong extension
            cand = os.path.join(d, base + e)
            if os.path.isfile(cand):
                return cand
    return None


def _convert_figure(src, images_dir, out_stem):
    """Copy/convert a figure into images_dir as a web-renderable file. Returns (filename, warning)."""
    ext = os.path.splitext(src)[1].lower()
    if ext == ".pdf":
        try:
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz
            doc = fitz.open(src)
            pix = doc[0].get_pixmap(dpi=200)
            name = out_stem + ".png"
            pix.save(os.path.join(images_dir, name))
            doc.close()
            return name, None
        except Exception as e:
            return None, f"PDF figure conversion failed ({os.path.basename(src)}): {e}"
    if ext in (".eps", ".ps"):
        try:
            from PIL import Image
            img = Image.open(src)
            try:
                img.load(scale=3)                 # higher-res EPS raster (needs Ghostscript)
            except Exception:
                pass
            name = out_stem + ".png"
            img.convert("RGB").save(os.path.join(images_dir, name))
            return name, None
        except Exception as e:
            name = out_stem + ext                 # Ghostscript missing: keep raw so it isn't lost
            shutil.copy2(src, os.path.join(images_dir, name))
            return name, f"EPS not rasterized (install Ghostscript); copied raw {name}"
    name = out_stem + ext                         # raster / svg: copy as-is
    shutil.copy2(src, os.path.join(images_dir, name))
    return name, None


def handle_figures(md_content, tex_content, tex_dir, output_dir, slug):
    """Copy/convert every figure referenced in the Pandoc markdown into output_dir/images/
    and rewrite the links. Covers markdown images AND the raw-HTML forms Pandoc
    emits for complex figures (<img src=...> for rasters, <embed src=...> for
    PDF graphics). Figure files are prefixed with the doc slug to avoid
    collisions between papers sharing one raw/<type>/images/ folder.
    Returns (md, n_ok, n_missing)."""
    search_dirs = _graphics_search_dirs(tex_content, tex_dir)
    images_dir = os.path.join(output_dir, "images")
    img_re = re.compile(r'!\[([^\]]*)\]\(([^)]+?)\)(\{[^}]*\})?')
    html_re = re.compile(r'<(img|embed)\b([^>]*?)\bsrc="([^"]+)"([^>]*?)/?>', re.IGNORECASE)
    cache, used = {}, set()
    stats = {"ok": 0, "missing": 0}

    def _localize(target):
        """Resolve+convert one figure target. Returns images/-relative name or None."""
        if target in cache:
            return cache[target]
        src = _resolve_figure(target, search_dirs)
        if not src:
            stats["missing"] += 1
            cache[target] = None
            print(f"  [fig] WARNING: could not resolve figure '{target}'")
            return None
        os.makedirs(images_dir, exist_ok=True)
        base = re.sub(r'[^\w.-]+', '_', os.path.splitext(os.path.basename(src))[0])
        stem, i = f"{slug}-{base}", 2
        while stem in used:
            stem = f"{slug}-{base}-{i}"
            i += 1
        used.add(stem)
        name, warn = _convert_figure(src, images_dir, stem)
        if warn:
            print(f"  [fig] {warn}")
        if name:
            cache[target] = name
            stats["ok"] += 1
            return name
        stats["missing"] += 1
        cache[target] = None
        return None

    def repl(m):
        cap, target = m.group(1), m.group(2)
        if target.startswith(("http://", "https://", "images/")):
            return m.group(0)
        name = _localize(target)
        if name:
            return f'![{cap}](images/{name}){m.group(3) or ""}'
        return m.group(0)

    def html_repl(m):
        target = m.group(3)
        if target.startswith(("http://", "https://", "images/", "data:")):
            return m.group(0)
        name = _localize(target)
        if name:
            # Emit a plain markdown image so downstream tools (wiki, index,
            # Obsidian) treat HTML-figure output the same as native figures.
            return f'![](images/{name})'
        return m.group(0)

    md_content = img_re.sub(repl, md_content)
    md_content = html_re.sub(html_repl, md_content)

    # Safety net: figures that vanished during conversion (neither markdown
    # nor HTML output) would otherwise disappear silently. Measured on a real
    # submission (arXiv 2401.00506): 6 referenced, 0 survived, while the run
    # still reported success. Returned as well as printed now, because a print
    # inside a captured subprocess is not a signal anyone downstream can act on.
    n_tex_figs = len(re.findall(r'\\includegraphics', tex_content))
    n_seen = stats["ok"] + stats["missing"]
    n_dropped = max(0, n_tex_figs - n_seen)
    if n_dropped:
        print(f"  [fig] WARNING: TeX source references {n_tex_figs} figure(s) but only "
              f"{n_seen} survived conversion — some figures were dropped by Pandoc; "
              "check the output against the original PDF")

    return md_content, stats["ok"], stats["missing"], n_dropped


def convert(input_path, output_dir) -> ConversionResult:
    """Convert a .tex or arXiv source archive to Markdown.

    Returns a result instead of calling sys.exit, so a caller running this
    in-process can see *what* went wrong. `main` keeps the old stdout and exit
    code exactly, so nothing invoking `magi ingest tex` notices the change.
    """
    # Pandoc runs with cwd=tex_dir, so a relative output dir would make it
    # write the temp file somewhere we would never find it again.
    output_dir = os.path.abspath(output_dir)

    if not os.path.isfile(input_path):
        print(f"Error: File '{input_path}' not found.")
        return ConversionResult.failed(f"File '{input_path}' not found.")

    base_name = os.path.basename(input_path)
    slug = _archive_slug(base_name)

    temp_dir_obj = None
    if _is_tar_archive(input_path):
        temp_dir_obj = tempfile.TemporaryDirectory()
        extract_dir = temp_dir_obj.name
        # The temporary directory exists from the line above, and unpacking
        # can throw: a truncated tarball, a member that tries to escape the
        # extraction root, an unreadable file. Those used to leave this
        # function without touching the cleanup below — which starts a good
        # 150 lines further down — and without producing a ConversionResult,
        # so the caller learnt what happened from a traceback rather than
        # from the contract every other exit here honours.
        try:
            print(f"Extracting {base_name} to {extract_dir}...")
            # "r:*" not "r:gz": arXiv serves .tgz and the occasional uncompressed
            # .tar, and guessing the compression by suffix is how this broke before.
            with tarfile.open(input_path, "r:*") as tar:
                # Safe extraction: prevent path traversal (CVE-2007-4559)
                norm_extract = os.path.realpath(extract_dir)
                for member in tar.getmembers():
                    member_path = os.path.realpath(os.path.join(extract_dir, member.name))
                    if member_path != norm_extract and not member_path.startswith(norm_extract + os.sep):
                        raise ValueError(f"Attempted path traversal in tar: {member.name}")
                    if member.issym() or member.islnk() or member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                        raise ValueError(f"Refusing unsafe tar member: {member.name}")
                try:
                    tar.extractall(path=extract_dir, filter='data')
                except TypeError:
                    # Python < 3.12 fallback
                    safe_members = [m for m in tar.getmembers() if m.isreg() or m.isdir()]
                    tar.extractall(path=extract_dir, members=safe_members)
            tex_path = find_main_tex(extract_dir, slug=slug)
            if not tex_path:
                print("Error: Could not find main .tex file in the archive.")
                temp_dir_obj.cleanup()
                return ConversionResult.failed(
                    "Could not find main .tex file in the archive.")
            tex_dir = os.path.dirname(tex_path)
        except Exception as exc:  # noqa: BLE001 — reported, not swallowed
            temp_dir_obj.cleanup()
            print(f"Error: could not unpack {base_name}: {exc}")
            return ConversionResult.failed(f"could not unpack {base_name}: {exc}")
    else:
        tex_path = input_path
        tex_dir = os.path.dirname(os.path.abspath(tex_path))

    print(f"Using main TeX file: {tex_path}")

    with open(tex_path, 'r', encoding='utf-8', errors='ignore') as f:
        tex_content = f.read()

    title = extract_title(tex_content)
    if not title:
        title = slug.replace('_', ' ').replace('-', ' ').title()

    # Look for a .bib file next to the main tex (walk the whole tree — arXiv
    # packages sometimes keep it in a subdirectory).
    bib_files = []
    bbl_files = []
    for root_dir, _, files in os.walk(tex_dir):
        for f in files:
            if f.endswith(".bib"):
                bib_files.append(os.path.join(root_dir, f))
            elif f.endswith(".bbl"):
                bbl_files.append(os.path.join(root_dir, f))
    bib_arg = ""
    bib_path = ""
    use_citeproc = True
    inlined_tex_path = None
    if bib_files:
        bib_path = bib_files[0]
        bib_arg = f"--bibliography=\"{bib_path}\""
        print(f"Found bibliography: {bib_path}")
    elif bbl_files:
        # arXiv source packages routinely ship only the compiled .bbl. Inline
        # its thebibliography into the tex so Pandoc renders a real reference
        # list, and skip citeproc (which needs .bib and would otherwise turn
        # every citation into a (**key?**) placeholder — or fail outright on
        # the missing .bib).
        bbl_path = bbl_files[0]
        try:
            with open(bbl_path, "r", encoding="utf-8", errors="ignore") as f:
                bbl_content = f.read()
            patched = re.sub(r"\\bibliographystyle\{[^{}]*\}", "", tex_content)
            patched, n_sub = re.subn(r"\\bibliography\{[^{}]*\}", lambda _m: bbl_content, patched, count=1)
            if n_sub == 0 and "thebibliography" not in patched:
                patched = patched.replace("\\end{document}", bbl_content + "\n\\end{document}", 1)
            inlined_tex_path = os.path.join(tex_dir, "_magi_inlined.tex")
            with open(inlined_tex_path, "w", encoding="utf-8") as f:
                f.write(patched)
            tex_path = inlined_tex_path
            use_citeproc = False
            print(f"No .bib in package; inlined precompiled bibliography {os.path.basename(bbl_path)} "
                  "— citations render as [@key] with a full References list.")
        except OSError as exc:
            print(f"Warning: found {os.path.basename(bbl_path)} but could not inline it ({exc}); "
                  "citations may render as (**key?**) placeholders.")

    # Unwrap figure macros before Pandoc sees them. Written as a sibling file
    # in tex_dir so relative image paths still resolve from the same cwd.
    try:
        with open(tex_path, "r", encoding="utf-8", errors="ignore") as f:
            _pre = f.read()
        _pre, _old = modernise_tex(_pre)
        if any(_old.values()):
            bits = []
            if _old["true_dimens"]:
                bits.append(f"{_old['true_dimens']} true-prefixed dimension(s)")
            if _old["epsfbox"] or _old["epsfig"]:
                bits.append(f"{_old['epsfbox'] + _old['epsfig']} epsf/psfig figure(s)")
            print("  [tex] modernised " + " and ".join(bits)
                  + " — this package predates the packages Pandoc assumes")
        _pre, _n_unwrapped = unwrap_figure_macros(_pre)
        if _n_unwrapped or any(_old.values()):
            prepared = os.path.join(tex_dir, "_magi_prepared.tex")
            with open(prepared, "w", encoding="utf-8") as f:
                f.write(_pre)
            tex_path = prepared
            if _n_unwrapped:
                print(f"  [fig] unwrapped {_n_unwrapped} figure macro(s) "
                      r"(\subfigure / \subfloat and the like) so Pandoc can "
                      "see the graphics inside them")
    except OSError as exc:
        print(f"Warning: could not pre-process the TeX for figures ({exc}); "
              "figures wrapped in macros may be dropped")

    doc_type = os.path.basename(os.path.normpath(output_dir))
    if doc_type not in ['papers', 'articles', 'notes', 'repos']:
        doc_type = 'papers'

    today = datetime.now().strftime("%Y-%m-%d")
    output_filename = f"{today}-{slug}.md"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)

    temp_md_path = output_path + ".tmp"

    import shutil

    # Load unified config for tool paths
    _cfg = load_config()

    # 查找 pandoc-crossref：环境变量 > 统一配置 > PATH
    pandoc_crossref_exec = os.environ.get("PANDOC_CROSSREF_PATH")
    if not pandoc_crossref_exec or not os.path.exists(pandoc_crossref_exec):
        pandoc_crossref_exec = cfg_get(_cfg, "tools.pandoc_crossref_path", "") or None
    if not pandoc_crossref_exec or not os.path.exists(pandoc_crossref_exec):
        pandoc_crossref_exec = shutil.which("pandoc-crossref")

    # 查找 pandoc：环境变量 > 统一配置 > PATH > LOCALAPPDATA
    pandoc_exec = os.environ.get("PANDOC_PATH")
    if not pandoc_exec or not os.path.exists(pandoc_exec):
        pandoc_exec = cfg_get(_cfg, "tools.pandoc_path", "") or None
    if not pandoc_exec or not os.path.exists(pandoc_exec):
        pandoc_exec = shutil.which("pandoc")
    if not pandoc_exec:
        # Fallback to standard local installation path
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        fallback = os.path.join(local_appdata, "Pandoc", "pandoc.exe")
        if os.path.exists(fallback):
            pandoc_exec = fallback
        else:
            pandoc_exec = "pandoc" # Will likely fail, but last resort

    cmd = [pandoc_exec, tex_path]
    if pandoc_crossref_exec:
        cmd.extend(["--filter", pandoc_crossref_exec])
    else:
        print("Warning: pandoc-crossref not found. Cross-references may not render correctly. Set tools.pandoc_crossref_path in config.yaml or add pandoc-crossref to PATH.")
    if use_citeproc:
        cmd.append("--citeproc")
    # Pandoc's default Markdown writer emits *simple* tables — space-aligned
    # columns under a row of dashes. Nothing in the library renders those:
    # Obsidian and every GFM reader want pipes, so a converted table arrived
    # looking like a mangled paragraph, and `tables-dropped` flagged it as
    # missing because it could not see one either. Ask for pipes explicitly.
    # A table too complex for pipes falls through to raw HTML, which both the
    # readers and the gate do understand.
    cmd.extend(["-t", "markdown-simple_tables-multiline_tables-grid_tables"
                      "+pipe_tables"])
    if bib_arg:
        cmd.extend(["--bibliography", bib_path])

    cmd.extend(["-o", temp_md_path])

    print(f"Running Pandoc: {' '.join(cmd)}")
    
    # Run from the tex directory to resolve image paths correctly.
    #
    # Pandoc is an external binary and a stated prerequisite, but "stated" is
    # not "present": on a machine without it this raised a bare
    # FileNotFoundError naming the executable, which reads like a missing input
    # document rather than a missing tool.
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=tex_dir)
    except FileNotFoundError:
        detail = (f"pandoc was not found (tried {cmd[0]!r}). It is required for the "
                  "LaTeX route; install it or set pandoc.path in config.yaml.")
        print(f"Error: {detail}", file=sys.stderr)
        if temp_dir_obj:
            temp_dir_obj.cleanup()
        return ConversionResult.failed(detail)
    except OSError as exc:
        detail = f"could not run pandoc: {exc}"
        print(f"Error: {detail}", file=sys.stderr)
        if temp_dir_obj:
            temp_dir_obj.cleanup()
        return ConversionResult.failed(detail)

    try:
        if result.returncode != 0:
            print("Pandoc conversion failed:")
            print(result.stderr)
            if os.path.exists(temp_md_path):
                os.remove(temp_md_path)
            # Old TeX is a real failure mode here: measured, pandoc dies on a
            # plain-TeX primitive like \vskip 0.3truein and produces nothing.
            return ConversionResult.failed(
                "Pandoc conversion failed.", result.stderr.strip())

        with open(temp_md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        os.remove(temp_md_path)

        # Copy/convert figures into output_dir/images/ and rewrite links.
        # MUST run before the temp dir (containing the extracted figures) is cleaned up.
        md_content, n_fig_ok, n_fig_missing, n_fig_dropped = handle_figures(
            md_content, tex_content, tex_dir, output_dir, slug)
        print(f"Figures: {n_fig_ok} embedded into images/, {n_fig_missing} unresolved")

        # `source:` has to outlive staging. `input_path` is the downloaded
        # tarball under output/ingest/staging/…, which is deleted when the
        # batch is committed, so the committed card pointed at nothing. When
        # the identity is known the arXiv page is the honest source; the HTML
        # rung already writes the URL it fetched.
        source = abs_url(normalize_arxiv_id(base_name) or "") or input_path
        fm_data = {"title": title, "source": source, "type": doc_type, "ingested": today, "tags": [], "summary": "Converted from LaTeX/arXiv source."}
        # Preserve the arXiv identity (usually in the downloaded filename) so
        # the literature radar can recognize this paper as library-owned.
        # Legacy ids (cond-mat/0506438) matter here: a real physics library has
        # them, and the pattern this replaced only knew the modern form.
        found_id = normalize_arxiv_id(base_name)
        if found_id:
            fm_data["arxiv_id"] = found_id
            fm_data["arxiv_url"] = abs_url(found_id)
        frontmatter = "---\n" + yaml.safe_dump(fm_data, allow_unicode=True, sort_keys=False, default_flow_style=False) + "---\n"

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter + "\n" + md_content)

        # Preserve the citation asset next to the markdown — `magi bib` and
        # future writing workflows need it, and the temp dir is about to go.
        for asset in ([bib_path] if bib_path else bbl_files[:1]):
            try:
                sidecar = os.path.join(output_dir, slug + os.path.splitext(asset)[1])
                shutil.copy2(asset, sidecar)
                print(f"Citation asset preserved: {os.path.basename(sidecar)}")
            except OSError as exc:
                print(f"Warning: could not preserve citation asset ({exc})")

        print(f"Successfully converted and saved to {output_path}")

        outcome = ConversionResult(
            success=True,
            markdown_path=str(output_path),
            images_dir=os.path.join(output_dir, "images"),
            pages_processed=0,          # not a paginated route
        )
        if n_fig_dropped:
            outcome.flag(
                "figure-count-mismatch",
                f"TeX references {n_fig_dropped + n_fig_ok + n_fig_missing} figure(s); "
                f"{n_fig_dropped} were dropped by Pandoc and are absent from the output",
            )
        if n_fig_missing:
            outcome.flag(
                "figure-unresolved",
                f"{n_fig_missing} figure reference(s) could not be resolved to a file",
            )
        return outcome
    finally:
        if inlined_tex_path and not temp_dir_obj and os.path.exists(inlined_tex_path):
            os.remove(inlined_tex_path)
        if temp_dir_obj:
            temp_dir_obj.cleanup()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi ingest tex", description="Convert TeX/arXiv tar.gz to Markdown using Pandoc.")
    parser.add_argument("input_path", help="Path to the .tex or .tar.gz file.")
    parser.add_argument("-o", "--output_dir", required=True, help="Output directory for the raw Markdown file.")
    args = parser.parse_args(argv)

    result = convert(args.input_path, args.output_dir)
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
