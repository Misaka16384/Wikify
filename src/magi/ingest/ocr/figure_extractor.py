"""
Figure Extractor Module
图表提取：按标题锚定，裁剪页面渲染区域（矢量图 + 位图都适用）。

相比 pdfimages（只能导出嵌入位图、丢失矢量图、把多面板图碎片化），本模块：
  1. 用 PyMuPDF 读取页面的矢量绘制框 + 图片放置框 + 文本块（标题锚点）。
  2. 把图形框聚类成连通区域。
  3. 按"同栏、标题在图下方最近"的规则，将聚类归属到各个图标题。
  4. 仅渲染该裁剪区域并保存到 images/，并返回标题文本用于回填 Markdown。

经 4 篇论文（2005-2024，PRB/PRX/Nature 风格）验证：85/86 图正确，无误检、无重复。
"""
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional

try:
    import pymupdf as fitz  # modern import name; silences the fitz deprecation warning
except ImportError:
    import fitz  # PyMuPDF (legacy)

# Longer alternatives first; CASE-SENSITIVE on purpose (APS "FIG." vs ref "Fig.").
FIG_RE = re.compile(r'^\s*(FIGURE|Figure|FIG|Fig|TABLE|Table|SCHEME|Scheme)\b\.?\s*(\d+)([^\d].*)?$', re.S)

CROP_DPI = 200
PAD_PT = 4
MERGE_GAP = 12
MIN_AREA_FRAC = 0.012
MIN_DIM_PT = 40
MAX_BELOW_GAP = 530
MAX_ABOVE_GAP = 80
GUTTER = 12


@dataclass
class Figure:
    page: int               # 1-based PDF page
    index: int              # 1-based order within the page
    label: Optional[str]    # "Figure 5" / "Fig 16" / "Table 2" / None
    caption: str            # full caption text from the PDF text layer
    filename: str           # e.g. "fig_p005_1.png"
    path: str               # absolute path to the saved crop


def caption_label(text):
    """Return a caption label ('Figure 5' / 'Fig 16' / 'Table 2') or None.

    Distinguishes a real caption from an inline cross-reference ("Fig. 16,
    where we ...") via: standalone label block / uppercase prefix (APS "FIG.")
    / a delimiter (. : |) or Capitalized title after the number. A comma or a
    lowercase continuation word means it's a reference, not a caption.
    """
    m = FIG_RE.match(text.strip())
    if not m:
        return None
    prefix, num, rest = m.group(1), m.group(2), (m.group(3) or "")
    after = rest.lstrip()
    standalone = after == ""
    upper = prefix.isupper()
    delim = bool(after) and after[0] in ".:|"
    title = bool(after) and after[0].isalpha() and after[0].isupper()
    is_ref = bool(after) and (after[0] == "," or (after[0].isalpha() and after[0].islower()))
    if is_ref and not upper:
        return None
    if standalone or upper or delim or title:
        return f"{prefix.title()} {num}"
    return None


def block_text(b):
    return "".join(s["text"] for l in b.get("lines", []) for s in l.get("spans", []))


def merge_rects(rects, gap):
    """Iteratively union rects whose gap-expanded boxes intersect."""
    rects = [fitz.Rect(r) for r in rects if r.width > 0 and r.height > 0]
    changed = True
    while changed:
        changed = False
        out = []
        while rects:
            r = fitz.Rect(rects.pop())
            again = True
            while again:
                again = False
                rest = []
                exp = fitz.Rect(r.x0 - gap, r.y0 - gap, r.x1 + gap, r.y1 + gap)
                for o in rects:
                    if exp.intersects(o):
                        r |= o
                        again = True
                        changed = True
                    else:
                        rest.append(o)
                rects = rest
            out.append(r)
        rects = out
    return rects


def _markup_annot_rects(page):
    """Rects of text-markup annotations (Highlight/Underline/Squiggly/StrikeOut).

    Zotero highlights render as filled rects inside get_drawings() and otherwise
    merge into figure clusters, swallowing whole text columns. We drop drawings
    that sit inside these.
    """
    rects = []
    try:
        for a in page.annots(types=(8, 9, 10, 11)) or []:
            rects.append(fitz.Rect(a.rect))
    except Exception:
        pass
    return rects


def graphic_rects(page):
    """Return (vector_rects, image_rects), each clamped to the page box."""
    pr = page.rect
    annots = _markup_annot_rects(page)

    def in_annot(r):
        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        return any(a.x0 <= cx <= a.x1 and a.y0 <= cy <= a.y1 for a in annots)

    vec, imgs = [], []
    try:
        for d in page.get_drawings():
            r = fitz.Rect(d["rect"]) & pr
            if r.is_empty or r.is_infinite:
                continue
            if min(r.width, r.height) >= 2 and not in_annot(r):
                vec.append(r)
    except Exception as e:
        print(f"  get_drawings failed: {e}", file=sys.stderr)
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            for r in page.get_image_rects(xref):
                r = fitz.Rect(r) & pr
                if not r.is_empty:
                    imgs.append(r)
        except Exception:
            pass
    return vec, imgs


def find_captions(page):
    caps = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        t = block_text(b).strip()
        label = caption_label(t)
        if label:
            caps.append({"rect": fitz.Rect(b["bbox"]), "label": label, "text": t})
    return caps


def is_two_column(page):
    mid = page.rect.width / 2
    blocks = [b for b in page.get_text("dict")["blocks"] if b.get("type") == 0]
    if len(blocks) < 5:
        return False
    cross = sum(1 for b in blocks if b["bbox"][0] < mid - 30 and b["bbox"][2] > mid + 30)
    return cross / len(blocks) < 0.25


def column_of(r, mid, two_col):
    if not two_col:
        return "full"
    if r.x0 < mid - 20 and r.x1 > mid + 20:
        return "full"
    return "left" if (r.x0 + r.x1) / 2 < mid else "right"


def col_ok(a, b):
    return a == b or a == "full" or b == "full"


def _contains_center(box, r):
    cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
    return box.x0 <= cx <= box.x1 and box.y0 <= cy <= box.y1


#: How far outside the drawing a label may sit and still belong to it. An axis
#: label is a few points clear of the plot; a paragraph is a line further away.
LABEL_REACH_PT = 14

#: A label is short. Body prose is not. This is what keeps the reach above from
#: swallowing the sentence that happens to end just beside a figure.
LABEL_MAX_CHARS = 48


def _with_figure_text(page, rect, caps, ci):
    """Grow a figure rect to take in the text that is part of the figure.

    The rect is built from *drawing* boxes, and axis labels, tick values and
    panel letters are text — so they sit outside it and get cropped away.
    Measured: a plot came out without either axis label, `E/t'` and `U/t'` both
    sliced off and the tick values cut in half, which is most of what makes a
    plot readable. The panel letter `a)` of a four-panel figure went the same
    way.

    Only short runs of text, only close by, and never the caption itself —
    the caption is rendered as Markdown beside the image and would be
    duplicated inside it.
    """
    try:
        blocks = page.get_text("blocks")
    except Exception:  # noqa: BLE001 — a figure without its label beats no figure
        return rect

    cap_rect = caps[ci]["rect"] if ci < len(caps) else None
    grown = fitz.Rect(rect)
    for _ in range(3):          # a label next to a grown edge joins on the next pass
        before = fitz.Rect(grown)
        reach = fitz.Rect(grown.x0 - LABEL_REACH_PT, grown.y0 - LABEL_REACH_PT,
                          grown.x1 + LABEL_REACH_PT, grown.y1 + LABEL_REACH_PT)
        for b in blocks:
            if len(b) < 5 or not isinstance(b[4], str):
                continue
            text = b[4].strip()
            if not text or len(text) > LABEL_MAX_CHARS:
                continue
            br = fitz.Rect(b[:4])
            if cap_rect is not None and br.intersects(cap_rect):
                continue
            if br.intersects(reach):
                grown |= br
        if grown == before:
            break
    return grown


def detect_figures(page, page_area, keep_uncaptioned=False):
    """Return a list of {rect, label, caption} for one page."""
    pr = page.rect
    mid = pr.width / 2
    two_col = is_two_column(page)
    vec, imgs = graphic_rects(page)
    clusters = merge_rects(vec + imgs, MERGE_GAP)
    caps = find_captions(page)
    cap_col = [column_of(c["rect"], mid, two_col) for c in caps]

    # The size thresholds decide whether a cluster can stand alone as a figure.
    # They must NOT decide whether it is *part* of one: a panel of a stacked
    # multi-panel figure is small on its own and still belongs. Measured on a
    # real four-panel figure — panel (a) was 0.56% of the page (under the 1.2%
    # floor), panel (c) was 35pt tall (under the 40pt floor), panel (d) was
    # four dots — so three of the four were discarded before captions were
    # even looked at, and the survivor inherited the whole figure's caption.
    # So: keep every cluster, mark which ones qualify alone, and let the
    # caption decide the rest.
    cand = []
    for c in clusters:
        big = (c.width * c.height >= MIN_AREA_FRAC * page_area
               and min(c.width, c.height) >= MIN_DIM_PT)
        n_vec = sum(1 for r in vec if _contains_center(c, r))
        has_img = any(c.intersects(r) for r in imgs)
        cand.append({"rect": c, "col": column_of(c, mid, two_col),
                     "rich": has_img or n_vec >= 3, "big": big, "cap": None})

    # ownership: nearest caption below in same column (below < within-box < above)
    for k in cand:
        c = k["rect"]
        best, best_key = None, None
        for i in range(len(caps)):
            if not col_ok(k["col"], cap_col[i]):
                continue
            cy0, cy1 = caps[i]["rect"].y0, caps[i]["rect"].y1
            if cy0 >= c.y1 - 10:
                gap = cy0 - c.y1
                key = (0, gap) if gap <= MAX_BELOW_GAP else None
            elif cy0 >= c.y0 - 10:
                key = (1, 0.0)
            else:
                gap = c.y0 - cy1
                key = (2, gap) if 0 <= gap <= MAX_ABOVE_GAP else None
            if key is not None and (best_key is None or key < best_key):
                best, best_key = i, key
        k["cap"] = best

    # A caption is a real figure only if something under it qualifies on its
    # own; the small parts then join that figure rather than being dropped or
    # becoming figures of their own.
    anchored = {k["cap"] for k in cand if k["big"] and k["cap"] is not None}

    by_cap, figs = {}, []
    for k in cand:
        if k["cap"] is None:
            if keep_uncaptioned and k["rich"] and k["big"]:
                figs.append({"rect": k["rect"], "label": None, "caption": ""})
        elif k["big"] or k["cap"] in anchored:
            r = by_cap.get(k["cap"])
            by_cap[k["cap"]] = (r | k["rect"]) if r is not None else fitz.Rect(k["rect"])

    # backfill captions whose figure is built from many sub-threshold cells
    allr = vec + imgs
    for i in range(len(caps)):
        if i in by_cap:
            continue
        col, cy0 = cap_col[i], caps[i]["rect"].y0
        top = cy0 - MAX_BELOW_GAP
        for j in range(len(caps)):
            if j != i and col_ok(col, cap_col[j]) and caps[j]["rect"].y1 <= cy0:
                top = max(top, caps[j]["rect"].y1)
        u = None
        for r in allr:
            if top <= (r.y0 + r.y1) / 2 <= cy0 + 10 and col_ok(column_of(r, mid, two_col), col):
                u = (u | r) if u is not None else fitz.Rect(r)
        if u is not None and u.width * u.height >= MIN_AREA_FRAC * page_area \
           and min(u.width, u.height) >= MIN_DIM_PT:
            by_cap[i] = u

    for ci, r in by_cap.items():
        r = _with_figure_text(page, fitz.Rect(r), caps, ci)
        if two_col and cap_col[ci] == "left":
            r.x1 = min(r.x1, mid + GUTTER)
        elif two_col and cap_col[ci] == "right":
            r.x0 = max(r.x0, mid - GUTTER)
        if r.width > 0 and r.height > 0 and r.width * r.height <= 0.97 * page_area:
            figs.append({"rect": r, "label": caps[ci]["label"], "caption": caps[ci]["text"]})

    return figs


def extract_figures(pdf_path, images_dir, dpi=CROP_DPI,
                    keep_uncaptioned=False, prefix="fig") -> List[Figure]:
    """Extract figures from a PDF, saving cropped PNGs into images_dir.

    Returns a list of Figure (page, index, label, caption, filename, path).
    """
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    out: List[Figure] = []
    try:
        for pno in range(len(doc)):
            page = doc[pno]
            parea = page.rect.width * page.rect.height
            figs = detect_figures(page, parea, keep_uncaptioned)
            figs.sort(key=lambda f: (round(f["rect"].y0), round(f["rect"].x0)))
            for i, f in enumerate(figs, 1):
                r = fitz.Rect(f["rect"]) + (-PAD_PT, -PAD_PT, PAD_PT, PAD_PT)
                r &= page.rect
                pix = page.get_pixmap(clip=r, dpi=dpi)
                fname = f"{prefix}_p{pno + 1:03d}_{i}.png"
                fpath = images_dir / fname
                pix.save(str(fpath))
                out.append(Figure(page=pno + 1, index=i, label=f["label"],
                                  caption=f["caption"], filename=fname, path=str(fpath)))
    finally:
        doc.close()
    return out


def _alt_text(fig: Figure) -> str:
    cap = (fig.caption or "").strip().replace("\n", " ")
    cap = re.sub(r"\s+", " ", cap)
    if cap:
        return cap[:140]
    return fig.label or "Figure"


def figure_markdown(fig: Figure, images_dir_name="images") -> str:
    return f"![{_alt_text(fig)}]({images_dir_name}/{fig.filename})"


def inject_figures(page_md: str, figures: List[Figure], images_dir_name="images") -> str:
    """Insert each figure's image link into the OCR'd page markdown.

    Places the image immediately above the OCR'd caption line that starts with
    the same "Fig N" / "Table N"; figures whose caption line isn't found are
    appended at the end of the page so nothing is lost.
    """
    if not figures:
        return page_md
    lines = page_md.split("\n")
    used = [False] * len(figures)

    for fi, fig in enumerate(figures):
        if not fig.label:
            continue
        m = re.search(r"(\d+)", fig.label)
        if not m:
            continue
        num = m.group(1)
        kind = r"table" if fig.label.lower().startswith("tab") else r"fig(?:ure)?"
        # caption line begins (optionally bolded) with the figure token + number
        pat = re.compile(rf"^\s*[*_>#\s]*{kind}\.?\s*0*{num}\b", re.I)
        for li, l in enumerate(lines):
            if pat.match(l):
                lines[li] = figure_markdown(fig, images_dir_name) + "\n\n" + l
                used[fi] = True
                break

    md = "\n".join(lines)
    extra = [figure_markdown(f, images_dir_name) for fi, f in enumerate(figures) if not used[fi]]
    if extra:
        md = md.rstrip() + "\n\n" + "\n\n".join(extra) + "\n"
    return md


if __name__ == "__main__":
    pdf = sys.argv[1]
    outdir = Path(sys.argv[2] if len(sys.argv) > 2 else "fig_out")
    figs = extract_figures(pdf, outdir / "images")
    for f in figs:
        print(f"p{f.page} #{f.index} {f.label!r:14} {f.filename}  :: {f.caption[:60]!r}")
    print(f"\n{len(figs)} figures -> {outdir/'images'}")
