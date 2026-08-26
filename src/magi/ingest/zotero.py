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
import re
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

# There was a `LOCAL_API = "http://localhost:23119/api/users/0"` here, unused by
# anything in the tree. It read as a supported second access path — one that
# would need Zotero to be running and its local API switched on — beside the
# one that is actually implemented. Everything here goes through a copy of
# `zotero.sqlite`, which works whether or not Zotero is open.


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

# Extra drives to sweep, Windows only, for the common case of a library moved
# off C:. Kept as a module constant so a test can empty it: sweeping real drives
# from a test finds the developer's own library, which is exactly what a test
# about someone's private data must not do.
SEARCH_DRIVES: tuple[str, ...] = ("C:", "D:", "E:") if sys.platform == "win32" else ()

# Where Zotero keeps its Firefox-style profile. The profile is not the library,
# but prefs.js inside it records where the library actually is — which beats
# guessing, and is the only thing that finds a library somebody moved.
_PROFILE_ROOTS = {
    "win32": [Path(os.environ.get("APPDATA", "")) / "Zotero" / "Zotero"],
    "darwin": [Path.home() / "Library" / "Application Support" / "Zotero"],
}
_PROFILE_ROOTS_DEFAULT = [Path.home() / ".zotero" / "zotero",
                          Path.home() / ".zotero"]

_DATA_DIR_PREF = re.compile(
    r'user_pref\(\s*["\']extensions\.zotero\.dataDir["\']\s*,\s*["\'](.+?)["\']\s*\)')


def _profile_roots() -> list[Path]:
    roots = _PROFILE_ROOTS.get(sys.platform, list(_PROFILE_ROOTS_DEFAULT))
    return [r for r in roots if str(r) and r.is_dir()]


def data_dir_from_prefs() -> list[Path]:
    """Data directories Zotero itself records in prefs.js.

    Authoritative when present: it is where the running application looks. A
    library moved to an external drive or a NAS is invisible to any amount of
    guessing and obvious here.
    """
    found: list[Path] = []
    for root in _profile_roots():
        for prefs in root.glob("Profiles/*/prefs.js"):
            try:
                text = prefs.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            m = _DATA_DIR_PREF.search(text)
            if not m:
                continue
            # prefs.js is JS source, so a Windows path arrives escaped.
            raw = m.group(1).replace("\\\\", "\\")
            found.append(Path(raw).expanduser())
    return found


def candidate_data_dirs(extra: Iterable[str] = ()) -> list[Path]:
    """Every plausible Zotero data directory, newest first.

    Never guessed silently. A machine can easily have two — an active one and an
    abandoned sync folder — and picking the stale one would import a library
    frozen years ago while looking like it worked.
    """
    home = Path.home()
    guesses = list(data_dir_from_prefs())
    guesses += [Path(p) for p in extra]
    # Zotero's default on every platform is ~/Zotero; the rest are places people
    # actually move it to.
    guesses += [
        home / "Zotero",
        home / "Documents" / "Zotero",
        home / "OneDrive" / "Zotero",
    ]
    if sys.platform == "darwin":
        guesses += [Path("/Volumes") / "Zotero",
                    home / "Library" / "CloudStorage"]
        guesses += [p / "Zotero" for p in Path("/Volumes").glob("*")
                    if p.is_dir()] if Path("/Volumes").is_dir() else []
    elif sys.platform != "win32":
        guesses += [home / ".zotero" / "data"]
        for mount in (Path("/mnt"), Path("/media")):
            if mount.is_dir():
                guesses += [p / "Zotero" for p in mount.glob("*/*") if p.is_dir()]
                guesses += [p / "Zotero" for p in mount.glob("*") if p.is_dir()]
    else:
        guesses.append(Path(os.environ.get("USERPROFILE", str(home))) / "Zotero")
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
        # Python does not call __exit__ when __enter__ itself raises, and this
        # one has three ways to raise after the temporary directory exists: a
        # permission error on copy2, a Zotero directory with no database, and
        # a connect that fails. The finalizer usually catches the leak; "usually"
        # is not a resource policy, and the failing paths are exactly the ones
        # a user hits repeatedly while pointing this at the wrong folder.
        self._tmp = tempfile.TemporaryDirectory(prefix="magi-zotero-")
        try:
            return self._open()
        except Exception:
            self._tmp.cleanup()
            self._tmp = None
            raise

    def _open(self) -> sqlite3.Connection:
        target = Path(self._tmp.name) / "zotero.sqlite"
        for suffix in _COPY_SUFFIXES:
            src = self.data_dir / f"zotero.sqlite{suffix}"
            if src.is_file():
                shutil.copy2(src, Path(self._tmp.name) / src.name)
        if not target.is_file():
            raise FileNotFoundError(f"no zotero.sqlite in {self.data_dir}")
        # as_uri(), not an f-string. SQLite parses this as a URI, so a literal
        # '#' in the path truncates it at the fragment and silently opens a
        # different, empty database — every query then returns nothing instead
        # of failing. '%XX' percent-decodes into a path that does not exist.
        # Temp directories carry the username, so neither is exotic.
        self._conn = sqlite3.connect(target.as_uri() + "?mode=ro", uri=True)
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


def collection_tree_ids(conn, name: str) -> list[int]:
    """Every collectionID under *name*, including *name* itself.

    Two things the old `WHERE c.collectionName = ?` got wrong, both silently.

    It did not descend. A collection is a folder and people put folders in it;
    selecting "Fractons" and getting none of the papers filed under
    "Fractons/2024" is not a filter, it is a surprise.

    And it matched on the name, so two collections called "Reading" in
    different parts of the tree were one collection as far as this was
    concerned — the import quietly contained a second, unrelated pile.
    Matching by id and walking down is the same query without either.
    """
    rows = conn.execute(
        "SELECT collectionID, parentCollectionID, collectionName FROM collections"
    ).fetchall()
    children: dict = {}
    roots = []
    for r in rows:
        children.setdefault(r["parentCollectionID"], []).append(r["collectionID"])
        if r["collectionName"] == name:
            roots.append(r["collectionID"])
    if len(roots) > 1:
        print(f"warning: {len(roots)} collections are called {name!r}; importing "
              f"all of them. Rename one, or pass --collection-id.", file=sys.stderr)
    out: list[int] = []
    stack = list(roots)
    while stack:
        cid = stack.pop()
        if cid in out:
            continue
        out.append(cid)
        stack.extend(children.get(cid, ()))
    return out


def read_items(data_dir, collection: str | None = None, *,
               collection_id: int | None = None,
               tag: str | None = None,
               keys: list[str] | None = None) -> list[ZoteroItem]:
    """Every bibliographic item, or the subset the selectors name.

    Selectors are ANDed. `collection` names a folder and includes everything
    beneath it; `collection_id` does the same without the name lookup, for when
    two folders share a name. `tag` and `keys` were the two ways people
    actually pick a handful of papers and neither existed, so "import these
    five" meant "make a temporary collection in Zotero first".
    """
    data_dir = Path(data_dir)
    with open_readonly(data_dir) as conn:
        sql = _ITEM_SQL
        params: tuple = ()
        ids = ([collection_id] if collection_id is not None
               else collection_tree_ids(conn, collection) if collection else [])
        if (collection or collection_id is not None) and not ids:
            return []
        if ids:
            marks = ",".join("?" * len(ids))
            sql += (f" AND i.itemID IN (SELECT ci.itemID FROM collectionItems ci "
                    f"WHERE ci.collectionID IN ({marks}))")
            params = params + tuple(ids)
        if tag:
            sql += (" AND i.itemID IN (SELECT it.itemID FROM itemTags it "
                    "JOIN tags t USING (tagID) WHERE t.name = ?)")
            params = params + (tag,)
        if keys:
            marks = ",".join("?" * len(keys))
            sql += f" AND i.key IN ({marks})"
            params = params + tuple(keys)

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
    from magi.kb_registry import edit_settings, load_settings

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
        with edit_settings() as data:
            data["zotero_data_dir"] = str(chosen)
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
