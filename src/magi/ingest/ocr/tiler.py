"""Hand the model one part of a page at a time, at full resolution.

Measured on a 49-row table page, `glm-ocr:q8_0`, temperature 0:

    whole page                     24 of 49 rows, and it stops mid-sentence
    2 tiles, left and right        49 of 49
    2x2 tiles                      49 of 49
    3 horizontal bands             40 of 49  (a band boundary cuts rows in half)

The stop is not a budget. ``num_ctx`` at 16384, 32768 and 65536, and
``num_predict`` at 8192, all produce byte-identical output — the model emits an
end-of-sequence token because it considers itself finished, having covered
about half the table. What it has is a fixed appetite per image, so the lever
is how much page one image contains.

Resolution is the wrong lever, and testing it is what showed why. Shrinking the
*image* of the same page also makes it write more — 0.7 MP produced 56 rows
against the 49 that exist — but only 12 were right, and seven were invented.
Less page at full resolution is right; the same page at less resolution is the
failure mode this whole ladder exists to avoid.

Tiling is applied only to pages whose source PDF actually contains a table.
That is not a guess: across the nine measured pages PyMuPDF reports tables on
exactly the three where tiling helps and on none of the six where it does not,
including the one page where splitting makes things dramatically worse (a
32,785-character repetition loop, against 559 characters whole-page).
"""

from __future__ import annotations

from pathlib import Path

# Enough overlap that a row sitting on the seam is whole in one of the two
# tiles; small enough that the duplicated band stays cheap to stitch back.
OVERLAP = 0.06


def tile(image_path, nx: int, ny: int, out_dir=None,
         overlap: float = OVERLAP) -> list[Path]:
    """Cut one page image into ``nx * ny`` overlapping tiles, in reading order.

    Tiles keep the page's own pixels — no resampling — because a tile exists to
    give the model *less page*, not a smaller picture of the same page.

    Written as PNG, deliberately. The engine's ``_preprocess_image`` encodes
    JPEG on its way out, so writing JPEG here would compress the same pixels
    twice. That is not merely wasteful: the doubly-encoded right-hand tile of a
    measured page came back with 146 table rows where 25 exist — the model
    inventing rows off degraded pixels — while the same crop encoded once
    returned all 25 correctly. One lossy step, at the boundary that already
    owns it.
    """
    from PIL import Image

    src = Path(image_path)
    out_dir = Path(out_dir) if out_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    made: list[Path] = []
    with Image.open(src) as img:
        img = img.convert("RGB")
        w, h = img.size
        ox = int(w / nx * overlap)
        oy = int(h / ny * overlap)
        for j in range(ny):
            for i in range(nx):
                box = (max(0, i * w // nx - ox), max(0, j * h // ny - oy),
                       min(w, (i + 1) * w // nx + ox), min(h, (j + 1) * h // ny + oy))
                dest = out_dir / f"{src.stem}__tile{j}{i}.png"
                img.crop(box).save(dest, format="PNG")
                made.append(dest)
    return made


def stitch(parts: list[str], window: int = 40) -> str:
    """Join tile transcriptions, dropping what the overlap said twice.

    Only the *leading* run of a tile is examined, and only against the tail of
    what is already assembled: that is where a duplicate can come from. A line
    repeated later in the document is the document repeating itself, which is a
    thing papers do, and deleting it would be a converter quietly editing.
    """
    parts = [p for p in parts if p and p.strip()]
    if not parts:
        return ""

    out = parts[0].splitlines()
    for part in parts[1:]:
        lines = part.splitlines()
        tail = {l.strip() for l in out[-window:] if l.strip()}
        i = 0
        while i < len(lines) and (not lines[i].strip() or lines[i].strip() in tail):
            i += 1
        if i:
            out.append("")
        out.extend(lines[i:])
    return "\n".join(out)


def pages_with_tables(pdf_path) -> set[int]:
    """1-based page numbers whose text layer contains a table.

    Best effort by nature: a scan has no text layer, so this returns nothing
    and those pages are read whole, exactly as before. Being wrong here costs
    accuracy on one page; being wrong the other way — tiling everything — costs
    every page a third more time and makes the repetition loop worse where it
    happens, so the quiet default is not to tile.
    """
    found: set[int] = set()
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - legacy import name
        try:
            import fitz as pymupdf
        except ImportError:
            return found

    try:
        with pymupdf.open(str(pdf_path)) as doc:
            for n, page in enumerate(doc, 1):
                try:
                    if len(page.find_tables().tables):
                        found.add(n)
                except Exception:  # noqa: BLE001 — one odd page is not an answer
                    continue
    except Exception:  # noqa: BLE001 — no PDF, no tiling, no crash
        return set()
    return found
