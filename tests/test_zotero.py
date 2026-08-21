"""Contracts for reading a Zotero library.

Built against a synthetic database, never a real one — a test that reaches into
someone's actual Zotero install would be both slow and rude, and the schema is
stable enough to fake faithfully.

The identifier ladder's shape comes from measuring a real 758-item library:
91 items had an Archive ID, 107 had it only as free text in Extra, and 15 only
in the URL. Any one rung alone misses most of it.
"""

import sqlite3

import pytest

from magi.ingest import zotero


FIELDS = ["title", "DOI", "url", "extra", "archiveID", "date"]


@pytest.fixture
def library(tmp_path):
    """A minimal but faithful Zotero data directory."""
    data_dir = tmp_path / "Zotero"
    (data_dir / "storage").mkdir(parents=True)
    conn = sqlite3.connect(data_dir / "zotero.sqlite")
    conn.executescript("""
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INTEGER,
                            key TEXT, dateAdded TEXT);
        CREATE TABLE fieldsCombined (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
        CREATE TABLE collections (collectionID INTEGER PRIMARY KEY,
                                  collectionName TEXT, parentCollectionID INTEGER);
        CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
        CREATE TABLE itemAttachments (itemID INTEGER, parentItemID INTEGER,
                                      linkMode INTEGER, contentType TEXT, path TEXT);
    """)
    conn.execute("INSERT INTO itemTypes VALUES (1, 'journalArticle')")
    conn.execute("INSERT INTO itemTypes VALUES (2, 'attachment')")
    for i, name in enumerate(FIELDS, 1):
        conn.execute("INSERT INTO fieldsCombined VALUES (?, ?)", (i, name))
    conn.commit()
    conn.close()
    return data_dir


def _add(data_dir, item_id, key, **fields):
    conn = sqlite3.connect(data_dir / "zotero.sqlite")
    conn.execute("INSERT INTO items VALUES (?, 1, ?, '2026-01-01')", (item_id, key))
    for name, value in fields.items():
        if value is None:
            continue
        fid = FIELDS.index(name) + 1
        vid = abs(hash((item_id, name))) % 10_000_000
        conn.execute("INSERT OR IGNORE INTO itemDataValues VALUES (?, ?)", (vid, value))
        conn.execute("INSERT INTO itemData VALUES (?, ?, ?)", (item_id, fid, vid))
    conn.commit()
    conn.close()


def _attach(data_dir, att_id, parent_id, key, filename, *, content_type="application/pdf",
            create_file=True):
    conn = sqlite3.connect(data_dir / "zotero.sqlite")
    conn.execute("INSERT INTO items VALUES (?, 2, ?, '2026-01-01')", (att_id, key))
    conn.execute("INSERT INTO itemAttachments VALUES (?, ?, 1, ?, ?)",
                 (att_id, parent_id, content_type, f"storage:{filename}"))
    conn.commit()
    conn.close()
    if create_file:
        folder = data_dir / "storage" / key
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_bytes(b"%PDF-1.7")


# --------------------------------------------------------------------------
# The identifier ladder
# --------------------------------------------------------------------------

def test_the_archive_id_field_is_used(library):
    _add(library, 1, "AAA", title="A", archiveID="arXiv:2405.00208")
    assert zotero.read_items(library)[0].arxiv_id() == "2405.00208"


def test_a_free_text_extra_field_is_mined(library):
    """Older items keep it here — 107 of a real library's 213."""
    _add(library, 1, "AAA", title="A", extra="arXiv:1703.07038 [physics]")
    assert zotero.read_items(library)[0].arxiv_id() == "1703.07038"


def test_the_url_field_is_the_last_free_rung(library):
    _add(library, 1, "AAA", title="A", url="https://arxiv.org/abs/2405.00208")
    assert zotero.read_items(library)[0].arxiv_id() == "2405.00208"


def test_an_arxiv_minted_doi_carries_the_id(library):
    _add(library, 1, "AAA", title="A", DOI="10.48550/arXiv.2405.00208")
    assert zotero.read_items(library)[0].arxiv_id() == "2405.00208"


def test_a_legacy_identifier_survives(library):
    """18 of a real library's resolvable ids are pre-2007 format."""
    _add(library, 1, "AAA", title="A", extra="arXiv:cond-mat/0506438")
    assert zotero.read_items(library)[0].arxiv_id() == "cond-mat/0506438"


def test_a_plain_publisher_doi_yields_no_arxiv_id(library):
    _add(library, 1, "AAA", title="A", DOI="10.1103/PhysRevB.108.014301")
    item = zotero.read_items(library)[0]
    assert item.arxiv_id() is None
    assert item.doi == "10.1103/PhysRevB.108.014301"


def test_the_archive_id_wins_over_a_weaker_rung(library):
    _add(library, 1, "AAA", title="A", archiveID="arXiv:2405.00208",
         url="https://arxiv.org/abs/1111.11111")
    assert zotero.read_items(library)[0].arxiv_id() == "2405.00208"


def test_an_item_with_nothing_is_not_an_error(library):
    _add(library, 1, "AAA", title="A")
    item = zotero.read_items(library)[0]
    assert item.arxiv_id() is None and item.doi is None


# --------------------------------------------------------------------------
# Attachments
# --------------------------------------------------------------------------

def test_a_stored_pdf_path_is_assembled_from_the_attachment_key(library):
    """The path is not stored: itemAttachments.path holds `storage:<name>` and
    the directory is the *attachment* item's own key."""
    _add(library, 1, "PARENT", title="A")
    _attach(library, 2, 1, "K2X9ABCD", "paper.pdf")

    item = zotero.read_items(library)[0]
    assert item.pdf_path.endswith("storage/K2X9ABCD/paper.pdf".replace("/", "\\")) or \
           item.pdf_path.endswith("storage/K2X9ABCD/paper.pdf")


def test_an_attachment_recorded_but_missing_from_disk_is_not_offered(library):
    _add(library, 1, "PARENT", title="A")
    _attach(library, 2, 1, "GONE", "paper.pdf", create_file=False)
    assert zotero.read_items(library)[0].pdf_path is None


def test_a_broken_path_row_is_skipped_not_fatal(library):
    """A real library had a row whose filename was literally 'undefined'."""
    _add(library, 1, "PARENT", title="A")
    conn = sqlite3.connect(library / "zotero.sqlite")
    conn.execute("INSERT INTO items VALUES (9, 2, 'PBKRZUXN', '2026-01-01')")
    conn.execute("INSERT INTO itemAttachments VALUES (9, 1, 1, 'application/pdf', "
                 "'storage:undefined')")
    conn.commit()
    conn.close()

    assert zotero.read_items(library)[0].pdf_path is None


def test_a_linked_file_is_not_treated_as_stored(library):
    _add(library, 1, "PARENT", title="A")
    conn = sqlite3.connect(library / "zotero.sqlite")
    conn.execute("INSERT INTO items VALUES (9, 2, 'LINKED', '2026-01-01')")
    conn.execute("INSERT INTO itemAttachments VALUES (9, 1, 2, 'application/pdf', "
                 "'attachments:/elsewhere/paper.pdf')")
    conn.commit()
    conn.close()

    assert zotero.read_items(library)[0].pdf_path is None


# --------------------------------------------------------------------------
# Reading the library
# --------------------------------------------------------------------------

def test_attachments_and_notes_are_not_bibliographic_items(library):
    _add(library, 1, "AAA", title="A")
    _attach(library, 2, 1, "K1", "a.pdf")
    assert len(zotero.read_items(library)) == 1


def test_a_collection_filters_the_result(library):
    _add(library, 1, "AAA", title="In it")
    _add(library, 2, "BBB", title="Not in it")
    conn = sqlite3.connect(library / "zotero.sqlite")
    conn.execute("INSERT INTO collections VALUES (1, 'Duality', NULL)")
    conn.execute("INSERT INTO collectionItems VALUES (1, 1)")
    conn.commit()
    conn.close()

    titles = [i.title for i in zotero.read_items(library, collection="Duality")]
    assert titles == ["In it"]


def test_collections_are_listed_with_counts(library):
    conn = sqlite3.connect(library / "zotero.sqlite")
    conn.execute("INSERT INTO collections VALUES (1, 'Duality', NULL)")
    conn.execute("INSERT INTO collectionItems VALUES (1, 1)")
    conn.execute("INSERT INTO collectionItems VALUES (1, 2)")
    conn.commit()
    conn.close()

    cols = zotero.list_collections(library)
    assert cols[0]["collectionName"] == "Duality" and cols[0]["n"] == 2


def test_the_source_database_is_never_opened_directly(library, monkeypatch):
    """Zotero locks it while running, and the official guidance is never to
    write to it. Reading a copy sidesteps both."""
    real_connect = sqlite3.connect
    opened = []

    def spy(target, *a, **k):
        opened.append(str(target))
        return real_connect(target, *a, **k)

    _add(library, 1, "AAA", title="A")
    monkeypatch.setattr(zotero.sqlite3, "connect", spy)
    zotero.read_items(library)

    assert opened, "expected at least one connection"
    assert not any(str(library) in path for path in opened)


# --------------------------------------------------------------------------
# Coverage
# --------------------------------------------------------------------------

def test_coverage_counts_the_population_that_matters(library):
    """`both` is where preferring arXiv over the stored PDF changes anything."""
    _add(library, 1, "A1", title="arXiv and PDF", archiveID="arXiv:2405.00208")
    _attach(library, 11, 1, "K1", "a.pdf")
    _add(library, 2, "A2", title="PDF only", DOI="10.1103/x")
    _attach(library, 12, 2, "K2", "b.pdf")
    _add(library, 3, "A3", title="arXiv only", archiveID="arXiv:1111.11111")
    _add(library, 4, "A4", title="nothing at all")

    cov = zotero.coverage(zotero.read_items(library))

    assert cov["total"] == 4
    assert cov["arxiv"] == 2
    assert cov["pdf"] == 2
    assert cov["both"] == 1
    assert cov["pdf_only"] == 1
    assert cov["doi_only"] == 1
    assert cov["nothing"] == 1


# --------------------------------------------------------------------------
# Choosing a data directory
# --------------------------------------------------------------------------

def test_describe_distinguishes_a_live_library_from_a_stale_one(library):
    _add(library, 1, "AAA", title="A")
    info = zotero.describe(library)
    assert info["items"] == 1
    assert info["latest"] == "2026-01-01"


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Every discovery route pointed somewhere empty.

    A discovery test must never find the developer's own library. Each new way
    of locating one has to be closed off here too — adding the prefs.js reader
    reopened this the moment it landed.
    """
    monkeypatch.setattr(zotero, "SEARCH_DRIVES", ())
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS", {})
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS_DEFAULT", [tmp_path / "no-profile"])
    monkeypatch.setattr(zotero.Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_a_directory_without_a_database_is_not_a_candidate(isolated):
    (isolated / "Zotero").mkdir()
    assert zotero.candidate_data_dirs() == []


# --------------------------------------------------------------------------
# prefs.js — the authoritative answer, and the only cross-platform one
# --------------------------------------------------------------------------

def _write_profile(root, data_dir_literal):
    profile = root / "Profiles" / "abc123.default"
    profile.mkdir(parents=True)
    (profile / "prefs.js").write_text(
        '// Zotero prefs\n'
        'user_pref("extensions.zotero.autoSync", true);\n'
        f'user_pref("extensions.zotero.dataDir", "{data_dir_literal}");\n',
        encoding="utf-8")
    return profile


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_the_data_dir_is_read_from_prefs_on_every_platform(tmp_path, monkeypatch,
                                                           platform, library):
    """Zotero records where its library actually is. Guessing cannot find one
    someone moved to an external drive or a NAS; this can."""
    root = tmp_path / "profile-root"
    root.mkdir()
    _write_profile(root, str(library).replace("\\", "\\\\"))

    monkeypatch.setattr(zotero.sys, "platform", platform)
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS", {platform: [root]})
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS_DEFAULT", [root])

    assert zotero.data_dir_from_prefs() == [library]


def test_a_windows_path_in_prefs_is_unescaped(tmp_path, monkeypatch):
    """prefs.js is JavaScript source, so backslashes arrive doubled."""
    root = tmp_path / "r"
    root.mkdir()
    _write_profile(root, "D:\\\\Research\\\\Zotero")
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS", {zotero.sys.platform: [root]})
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS_DEFAULT", [root])

    assert str(zotero.data_dir_from_prefs()[0]).endswith("Zotero")
    assert "\\\\" not in str(zotero.data_dir_from_prefs()[0])


def test_a_profile_without_the_pref_is_skipped(tmp_path, monkeypatch):
    root = tmp_path / "r"
    profile = root / "Profiles" / "x.default"
    profile.mkdir(parents=True)
    (profile / "prefs.js").write_text(
        'user_pref("extensions.zotero.autoSync", true);\n', encoding="utf-8")
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS", {zotero.sys.platform: [root]})
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS_DEFAULT", [root])

    assert zotero.data_dir_from_prefs() == []


def test_no_profile_at_all_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS", {zotero.sys.platform: [tmp_path / "nope"]})
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS_DEFAULT", [tmp_path / "nope"])
    assert zotero.data_dir_from_prefs() == []


def test_prefs_is_preferred_over_a_guess(tmp_path, monkeypatch, library):
    """What Zotero itself records outranks anywhere we thought to look."""
    root = tmp_path / "r"
    root.mkdir()
    _write_profile(root, str(library).replace("\\", "\\\\"))
    monkeypatch.setattr(zotero, "SEARCH_DRIVES", ())
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS", {zotero.sys.platform: [root]})
    monkeypatch.setattr(zotero, "_PROFILE_ROOTS_DEFAULT", [root])
    monkeypatch.setattr(zotero.Path, "home", staticmethod(lambda: tmp_path))

    assert zotero.candidate_data_dirs()[0] == library


def test_windows_drive_sweep_does_not_run_off_windows(monkeypatch):
    """C:/D:/E: are meaningless on macOS and Linux."""
    import importlib

    monkeypatch.setattr("sys.platform", "darwin")
    reloaded = importlib.reload(zotero)
    try:
        assert reloaded.SEARCH_DRIVES == ()
    finally:
        monkeypatch.undo()
        importlib.reload(zotero)


def test_a_directory_with_a_database_is_found(isolated, library):
    assert zotero.candidate_data_dirs([str(library)]) == [library]


def test_candidates_come_back_newest_first(isolated, tmp_path):
    """The whole reason to list rather than pick: telling a live library from
    an abandoned sync folder is what the user is being asked to do."""
    import os
    import time

    older, newer = tmp_path / "old", tmp_path / "new"
    for path in (older, newer):
        path.mkdir()
        sqlite3.connect(path / "zotero.sqlite").close()
    old_time = time.time() - 86_400
    os.utime(older / "zotero.sqlite", (old_time, old_time))

    found = zotero.candidate_data_dirs([str(older), str(newer)])
    assert found == [newer, older]


def test_the_same_directory_is_not_listed_twice(isolated, library):
    found = zotero.candidate_data_dirs([str(library), str(library)])
    assert found == [library]
