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

from magi.core.config_loader import load_config, get as cfg_get

def extract_title(tex_content):
    match = re.search(r'\\title\{([^}]+)\}', tex_content)
    if match:
        return match.group(1).strip()
    return None

def find_main_tex(directory):
    # Find the main tex file by looking for \documentclass
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.tex'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if r'\documentclass' in content:
                        return path
    # Fallback to any .tex if no documentclass is found
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.tex'):
                return os.path.join(root, file)
    return None

# Figure extensions we can resolve from a \includegraphics target.
_IMG_EXTS = (".pdf", ".eps", ".ps", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".svg")


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
    # nor HTML output) would otherwise disappear silently.
    n_tex_figs = len(re.findall(r'\\includegraphics', tex_content))
    n_seen = stats["ok"] + stats["missing"]
    if n_tex_figs > n_seen:
        print(f"  [fig] WARNING: TeX source references {n_tex_figs} figure(s) but only "
              f"{n_seen} survived conversion — some figures were dropped by Pandoc; "
              "check the output against the original PDF")

    return md_content, stats["ok"], stats["missing"]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="magi ingest tex", description="Convert TeX/arXiv tar.gz to Markdown using Pandoc.")
    parser.add_argument("input_path", help="Path to the .tex or .tar.gz file.")
    parser.add_argument("-o", "--output_dir", required=True, help="Output directory for the raw Markdown file.")
    args = parser.parse_args(argv)

    input_path = args.input_path
    # Pandoc runs with cwd=tex_dir, so a relative output dir would make it
    # write the temp file somewhere we would never find it again.
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.isfile(input_path):
        print(f"Error: File '{input_path}' not found.")
        sys.exit(1)

    base_name = os.path.basename(input_path)
    if base_name.endswith('.tar.gz'):
        slug = base_name[:-7]
    elif base_name.endswith('.tex'):
        slug = base_name[:-4]
    else:
        slug = os.path.splitext(base_name)[0]

    temp_dir_obj = None
    if input_path.endswith('.tar.gz'):
        temp_dir_obj = tempfile.TemporaryDirectory()
        extract_dir = temp_dir_obj.name
        print(f"Extracting tar.gz to {extract_dir}...")
        with tarfile.open(input_path, "r:gz") as tar:
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
        tex_path = find_main_tex(extract_dir)
        if not tex_path:
            print("Error: Could not find main .tex file in the archive.")
            sys.exit(1)
        tex_dir = os.path.dirname(tex_path)
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
    cmd.extend(["-t", "markdown"])
    if bib_arg:
        cmd.extend(["--bibliography", bib_path])

    cmd.extend(["-o", temp_md_path])

    print(f"Running Pandoc: {' '.join(cmd)}")
    
    # Run from the tex directory to resolve image paths correctly
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=tex_dir)

    try:
        if result.returncode != 0:
            print("Pandoc conversion failed:")
            print(result.stderr)
            if os.path.exists(temp_md_path):
                os.remove(temp_md_path)
            sys.exit(1)

        with open(temp_md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        os.remove(temp_md_path)

        # Copy/convert figures into output_dir/images/ and rewrite links.
        # MUST run before the temp dir (containing the extracted figures) is cleaned up.
        md_content, n_fig_ok, n_fig_missing = handle_figures(
            md_content, tex_content, tex_dir, output_dir, slug)
        print(f"Figures: {n_fig_ok} embedded into images/, {n_fig_missing} unresolved")

        fm_data = {"title": title, "source": input_path, "type": doc_type, "ingested": today, "tags": [], "summary": "Converted from LaTeX/arXiv source."}
        # Preserve the arXiv identity (usually in the downloaded filename) so
        # the literature radar can recognize this paper as library-owned.
        arxiv_m = re.search(r"\b(\d{4}\.\d{4,5})(?:v\d+)?\b", base_name)
        if arxiv_m:
            fm_data["arxiv_id"] = arxiv_m.group(1)
            fm_data["arxiv_url"] = f"https://arxiv.org/abs/{arxiv_m.group(1)}"
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
    finally:
        if inlined_tex_path and not temp_dir_obj and os.path.exists(inlined_tex_path):
            os.remove(inlined_tex_path)
        if temp_dir_obj:
            temp_dir_obj.cleanup()

if __name__ == "__main__":
    sys.exit(main())
