"""Which Zotero items an import actually picks up.

Selection was one line — `WHERE c.collectionName = ?` — and it got two things
wrong without saying so.

It did not descend. A collection is a folder and people put folders in it, so
selecting "Fractons" and getting none of the papers filed under
"Fractons/2024" is not a filter, it is a surprise.

And it matched on the *name*, so two collections called "Reading" in different
parts of the tree were one collection as far as the import was concerned — the
queue quietly contained a second, unrelated pile.

There was also no way to say "these five". Granularity was whole-library or
one folder, which meant the way to import a handful of papers was to go and
make a temporary collection in Zotero first.
"""

import sqlite3

import pytest

from magi.ingest import zotero

SCHEMA = """
CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, collectionName TEXT,
                          parentCollectionID INTEGER, libraryID INTEGER DEFAULT 1);
CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, itemTypeID INTEGER,
                    libraryID INTEGER DEFAULT 1);
CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
CREATE TABLE fieldsCombined (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
CREATE TABLE itemAttachments (itemID INTEGER, parentItemID INTEGER, path TEXT,
                              contentType TEXT);
CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);
CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);
"""

#: (id, name, parent). Two "Reading" folders on purpose, in different places.
COLLECTIONS = [
    (1, "Fractons", None),
    (2, "2024", 1),          # nested under Fractons
    (3, "Reading", None),
    (4, "Symmetry", None),
    (5, "Reading", 4),       # a second folder with the same name
]

#: (itemID, key, title, collectionIDs, tags)
ITEMS = [
    (10, "AAAA1111", "Fracton overview", [1], ["survey"]),
    (11, "BBBB2222", "Fracton in 2024", [2], []),
    (12, "CCCC3333", "Top-level reading", [3], ["survey"]),
    (13, "DDDD4444", "Symmetry reading", [5], []),
    (14, "EEEE5555", "Filed nowhere", [], ["survey"]),
]


@pytest.fixture
def library(tmp_path):
    db = tmp_path / "zotero.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO itemTypes VALUES (1, 'journalArticle')")
    conn.execute("INSERT INTO fieldsCombined VALUES (110, 'title')")
    conn.executemany("INSERT INTO collections (collectionID, collectionName, "
                     "parentCollectionID) VALUES (?,?,?)", COLLECTIONS)
    tag_ids = {}
    for item_id, key, title, cols, tags in ITEMS:
        conn.execute("INSERT INTO items (itemID, key, itemTypeID) VALUES (?,?,1)",
                     (item_id, key))
        conn.execute("INSERT INTO itemDataValues VALUES (?,?)", (item_id, title))
        conn.execute("INSERT INTO itemData VALUES (?,110,?)", (item_id, item_id))
        for c in cols:
            conn.execute("INSERT INTO collectionItems VALUES (?,?)", (c, item_id))
        for t in tags:
            if t not in tag_ids:
                tag_ids[t] = len(tag_ids) + 1
                conn.execute("INSERT INTO tags VALUES (?,?)", (tag_ids[t], t))
            conn.execute("INSERT INTO itemTags VALUES (?,?)", (item_id, tag_ids[t]))
    conn.commit()
    conn.close()
    return tmp_path


def _titles(items):
    return sorted(i.title for i in items)


# --------------------------------------------------------------------------
# the two silent wrongs
# --------------------------------------------------------------------------

def test_a_collection_includes_what_is_filed_beneath_it(library):
    got = zotero.read_items(library, collection="Fractons")
    assert _titles(got) == ["Fracton in 2024", "Fracton overview"], (
        "the papers in the nested folder were left out")


def test_two_folders_of_the_same_name_can_be_told_apart(library, capsys):
    """Matching by name made these one collection. They are not."""
    both = zotero.read_items(library, collection="Reading")
    assert _titles(both) == ["Symmetry reading", "Top-level reading"]
    assert "2 collections are called" in capsys.readouterr().err

    only_one = zotero.read_items(library, collection_id=3)
    assert _titles(only_one) == ["Top-level reading"]


# --------------------------------------------------------------------------
# saying "these ones"
# --------------------------------------------------------------------------

def test_a_tag_selects_across_the_whole_library(library):
    got = zotero.read_items(library, tag="survey")
    assert _titles(got) == ["Filed nowhere", "Fracton overview", "Top-level reading"]


def test_keys_select_exactly_those_items(library):
    got = zotero.read_items(library, keys=["AAAA1111", "DDDD4444"])
    assert _titles(got) == ["Fracton overview", "Symmetry reading"]


def test_selectors_narrow_each_other(library):
    """A tag inside one folder, rather than either alone."""
    got = zotero.read_items(library, collection="Fractons", tag="survey")
    assert _titles(got) == ["Fracton overview"]


def test_no_selector_still_means_the_whole_library(library):
    assert len(zotero.read_items(library)) == len(ITEMS)


# --------------------------------------------------------------------------
# refusing rather than widening
# --------------------------------------------------------------------------

def test_a_collection_nobody_has_returns_nothing_not_everything(library):
    """The dangerous failure: an unmatched name falling through to no filter
    would queue the entire library under the impression it was one folder."""
    assert zotero.read_items(library, collection="Does Not Exist") == []


def test_an_unknown_tag_returns_nothing(library):
    assert zotero.read_items(library, tag="nope") == []


def test_an_unknown_key_returns_nothing(library):
    assert zotero.read_items(library, keys=["ZZZZ9999"]) == []


def test_the_tree_walk_terminates_on_a_cycle(library):
    """A parent pointer loop is corrupt data, not a reason to hang."""
    conn = sqlite3.connect(library / "zotero.sqlite")
    conn.execute("UPDATE collections SET parentCollectionID = 2 WHERE collectionID = 1")
    conn.commit()
    conn.close()

    assert zotero.read_items(library, collection="Fractons") is not None
