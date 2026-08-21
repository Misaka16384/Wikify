"""Reading a Zotero library, so a collection can be queued for ingest.

Zotero is the list of papers you care about. It is a poor source of *files*:
what it stores is the publisher's typeset PDF, where a formula has already
become glyphs on a page. When the same paper is on arXiv, its LaTeX source is
strictly better, and this module exists to find out which papers those are.

Measured against a real 758-item library: 28% carry an arXiv id somewhere in
their metadata, 74.8% have a stored PDF on disk, and 198 items have both — that
overlap is where preferring arXiv actually changes anything. The other 369
PDF-bearing items will always use the local file, which is fine: it is already
on disk, no download and no paywall.

All Zotero SQL lives here. Nowhere else in MAGI knows this schema.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Iterable, NamedTuple

from magi.core.arxiv_id import normalize_arxiv_id

# Zotero holds the database open while it runs, so a second reader gets
# "database is locked". Copying first is the documented way around it and costs
# a second on an 80 MB file.
_COPY_SUFFIXES = ("", "-wal", "-shm", "-journal")

LOCAL_API = "http://localhost:23119/api/users/0"


class ZoteroItem(NamedTuple):
    item_id: int
    key: str
    item_type: str
    title: str | None
    doi: str | None
    url: str | None
    extra: str | None
    archive_id: str | None
    date: str | None
    pdf_path: str | None

    def arxiv_id(self) -> str | None:
        """First identifier the ladder finds, cheapest rung first.

        There is no single field for this. Newer items use Archive ID; older
        ones have it as free text in Extra; almost everything arXiv-derived has
        it in the URL. A real library needs all three: measured, 91 items came
        from Archive ID, 107 from Extra, 15 from the URL.
        """
        for candidate in (self.archive_id, self.extra, self.url):
            found = normalize_arxiv_id(candidate)
            if found:
                return found
        # arXiv mints its own DOIs, so sometimes the id is sitting in there.
        if self.doi and "arxiv" in self.doi.lower():
            return normalize_arxiv_id(self.doi)
        return None


# --------------------------------------------------------------------------
# Finding the data directory
# --------------------------------------------------------------------------

# Zotero's own default is under the home directory, but people move it — a
# second drive is the usual reason. Kept as a module constant so a test can
# empty it: scanning real drives from a test would find the developer's own
# library, which is exactly what a test about someone's private data must not do.
SEARCH_DRIVES: tuple[str, ...] = ("C:", "D:", "E:")


def candidate_data_dirs(extra: Iterable[str] = ()) -> list[Path]:
    """Every plausible Zotero data directory, newest first.

    Never guessed silently. A machine can easily have two — an active one and an
    abandoned sync folder — and picking the stale one would import a library
    frozen years ago while looking like it worked.
    """
    home = Path.home()
    guesses = [
        home / "Zotero",
        home / "Documents" / "Zotero",
        Path(os.environ.get("USERPROFILE", str(home))) / "Zotero",
    ]
    guesses += [Path(p) for p in extra]
    for drive in SEARCH_DRIVES:
        guesses.append(Path(f"{drive}/Zotero"))
        guesses.append(Path(f"{drive}/OneDrive/Zotero"))

    seen: set[Path] = set()
    found: list[Path] = []
    for path in guesses:
        try:
            db = path / "zotero.sqlite"
            resolved = path.resolve()
            if resolved in seen or not db.is_file():
                continue
        except OSError:
            continue
        seen.add(resolved)
        found.append(path)
    return sorted(found, key=lambda p: (p / "zotero.sqlite").stat().st_mtime, reverse=True)


def describe(data_dir: Path) -> dict:
    """Enough to tell an active library from an abandoned one."""
    db = Path(data_dir) / "zotero.sqlite"
    info = {"path": str(data_dir), "size": db.stat().st_size,
            "items": 0, "collections": 0, "latest": None}
    try:
        with open_readonly(data_dir) as conn:
            info["items"] = conn.execute(
                "SELECT COUNT(*) FROM items i JOIN itemTypes t USING (itemTypeID) "
                "WHERE t.typeName NOT IN ('attachment','note','annotation')"
            ).fetchone()[0]
            info["collections"] = conn.execute(
                "SELECT COUNT(*) FROM collections").fetchone()[0]
            info["latest"] = conn.execute(
                "SELECT MAX(dateAdded) FROM items").fetchone()[0]
    except sqlite3.Error as exc:
        info["error"] = str(exc)
    return info


class open_readonly:
    """A connection to a *copy* of the database.

    Read-only is not enough on its own: Zotero keeps the file locked while it is
    running, and the official guidance is to never write to it under any
    circumstances. Copying sidesteps both.
    """

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self._tmp: tempfile.TemporaryDirectory | None = None
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._tmp = tempfile.TemporaryDirectory(prefix="magi-zotero-")
        target = Path(self._tmp.name) / "zotero.sqlite"
        for suffix in _COPY_SUFFIXES:
            src = self.data_dir / f"zotero.sqlite{suffix}"
            if src.is_file():
                shutil.copy2(src, Path(self._tmp.name) / src.name)
        if not target.is_file():
            raise FileNotFoundError(f"no zotero.sqlite in {self.data_dir}")
        self._conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row
        return self._conn

    def __exit__(self, *exc):
        if self._conn:
            self._conn.close()
        if self._tmp:
            self._tmp.cleanup()
        return False


# --------------------------------------------------------------------------
# Reading it
# --------------------------------------------------------------------------

_FIELDS = ("title", "DOI", "url", "extra", "archiveID", "date")

_ITEM_SQL = """
SELECT i.itemID, i.key, t.typeName, f.fieldName, v.value
FROM items i
JOIN itemTypes t         ON t.itemTypeID = i.itemTypeID
LEFT JOIN itemData d     ON d.itemID = i.itemID
LEFT JOIN fieldsCombined f ON f.fieldID = d.fieldID
LEFT JOIN itemDataValues v ON v.valueID = d.valueID
WHERE t.typeName NOT IN ('attachment', 'note', 'annotation')
"""


def list_collections(data_dir) -> list[dict]:
    with open_readonly(data_dir) as conn:
        rows = conn.execute(
            "SELECT c.collectionID, c.collectionName, c.parentCollectionID, "
            "       (SELECT COUNT(*) FROM collectionItems ci "
            "        WHERE ci.collectionID = c.collectionID) AS n "
            "FROM collections c ORDER BY c.collectionName").fetchall()
    return [dict(r) for r in rows]


def _attachments(conn) -> dict[int, str]:
    """Parent item id -> stored PDF path.

    The path is assembled, not stored: ``itemAttachments.path`` holds
    ``storage:<filename>`` and the directory is the *attachment* item's own key.
    """
    out: dict[int, str] = {}
    rows = conn.execute(
        "SELECT a.parentItemID, a.path, i.key, a.contentType "
        "FROM itemAttachments a JOIN items i ON i.itemID = a.itemID "
        "WHERE a.parentItemID IS NOT NULL AND a.path IS NOT NULL").fetchall()
    for row in rows:
        path = row["path"] or ""
        if not path.startswith("storage:"):
            continue                      # a linked file, not one Zotero stores
        filename = path[len("storage:"):]
        # A real library had a row whose filename was literally "undefined".
        # Skipping it is right; crashing the whole import over it is not.
        if not filename or filename == "undefined":
            continue
        if (row["contentType"] or "").lower() not in ("application/pdf", ""):
            continue
        out.setdefault(row["parentItemID"], f"storage/{row['key']}/{filename}")
    return out


def read_items(data_dir, collection: str | None = None) -> list[ZoteroItem]:
    """Every bibliographic item, or just one collection's."""
    data_dir = Path(data_dir)
    with open_readonly(data_dir) as conn:
        sql = _ITEM_SQL
        params: tuple = ()
        if collection:
            sql += (" AND i.itemID IN (SELECT ci.itemID FROM collectionItems ci "
                    "JOIN collections c USING (collectionID) WHERE c.collectionName = ?)")
            params = (collection,)

        gathered: dict[int, dict] = {}
        for row in conn.execute(sql, params):
            rec = gathered.setdefault(row["itemID"], {
                "key": row["key"], "type": row["typeName"], "fields": {}})
            if row["fieldName"]:
                rec["fields"][row["fieldName"]] = row["value"]

        pdfs = _attachments(conn)

    items = []
    for item_id, rec in gathered.items():
        fields = rec["fields"]
        rel = pdfs.get(item_id)
        pdf = str(data_dir / rel) if rel else None
        if pdf and not Path(pdf).is_file():
            pdf = None                    # recorded but gone from disk
        items.append(ZoteroItem(
            item_id=item_id, key=rec["key"], item_type=rec["type"],
            title=fields.get("title"), doi=fields.get("DOI"),
            url=fields.get("url"), extra=fields.get("extra"),
            archive_id=fields.get("archiveID"), date=fields.get("date"),
            pdf_path=pdf))
    return sorted(items, key=lambda i: (i.title or "").lower())


def coverage(items: Iterable[ZoteroItem]) -> dict:
    """What the ladder can reach, before spending any network."""
    items = list(items)
    with_arxiv = [i for i in items if i.arxiv_id()]
    with_pdf = [i for i in items if i.pdf_path]
    doi_only = [i for i in items if not i.arxiv_id() and i.doi]
    return {
        "total": len(items),
        "arxiv": len(with_arxiv),
        "pdf": len(with_pdf),
        "both": len([i for i in with_pdf if i.arxiv_id()]),
        "pdf_only": len([i for i in with_pdf if not i.arxiv_id()]),
        "doi_only": len(doi_only),
        "nothing": len([i for i in items if not i.arxiv_id() and not i.doi and not i.pdf_path]),
    }


# --------------------------------------------------------------------------
# CLI: magi ingest zotero-dirs
# --------------------------------------------------------------------------

def cmd_dirs(args) -> int:
    from magi.kb_registry import load_settings, save_settings

    settings = load_settings()
    configured = settings.get("zotero_data_dir")

    found = candidate_data_dirs([configured] if configured else [])
    if not found:
        print("No Zotero data directory found.")
        print("Zotero shows it under Settings -> Advanced -> Files and Folders.")
        print("Point at it with:  magi ingest zotero-dirs --set <PATH>")
        return 1

    if args.set:
        chosen = Path(args.set).expanduser().resolve()
        if not (chosen / "zotero.sqlite").is_file():
            print(f"no zotero.sqlite in {chosen}", file=sys.stderr)
            return 1
        settings["zotero_data_dir"] = str(chosen)
        save_settings(settings)
        print(f"[zotero] using {chosen}")
        return 0

    print("Zotero libraries found (newest first):\n")
    for path in found:
        info = describe(path)
        mark = "*" if configured and Path(configured) == path else " "
        size_mb = info["size"] / (1024 * 1024)
        print(f" {mark} {path}")
        print(f"     {info['items']} items, {info['collections']} collections, "
              f"{size_mb:.1f} MB, newest entry {info.get('latest') or 'unknown'}")
        if info.get("error"):
            print(f"     could not read it: {info['error']}")
    print()
    if configured:
        print(f"Currently using: {configured}")
    else:
        # Never pick for them, even when there is only one. A machine with a
        # live library and a stale OneDrive copy is common, and importing the
        # frozen one looks exactly like success.
        print("None chosen yet. Pick one:  magi ingest zotero-dirs --set <PATH>")
    return 0


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="magi ingest zotero-dirs",
        description="List Zotero libraries on this machine and choose one.")
    parser.add_argument("--set", help="Use this data directory from now on")
    args = parser.parse_args(argv)
    return cmd_dirs(args)


if __name__ == "__main__":
    sys.exit(main())
