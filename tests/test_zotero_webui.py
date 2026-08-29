"""Importing from Zotero without opening a terminal.

Zotero import was CLI-only, which made it the one source of papers the
dashboard could not touch — and for most researchers it is the source their
papers are already in. The two surfaces built for feeding a library, the
dashboard and the browser extension, both took identifiers; the pile of PDFs
somebody had spent years collecting was reachable only from a shell.

The door is the same shape as every other one on that panel: it writes queue
entries and nothing else, so the existing convert → approve → commit gate
applies to a Zotero import exactly as it does to a pasted arXiv link.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from magi.ui.api import create_app

from test_zotero_selection import COLLECTIONS, ITEMS, SCHEMA


@pytest.fixture
def zotero_library(tmp_path, monkeypatch):
    lib = tmp_path / "Zotero"
    lib.mkdir()
    conn = sqlite3.connect(lib / "zotero.sqlite")
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO itemTypes VALUES (1, 'journalArticle')")
    conn.execute("INSERT INTO fieldsCombined VALUES (110, 'title')")
    conn.execute("INSERT INTO fieldsCombined VALUES (111, 'DOI')")
    conn.executemany("INSERT INTO collections (collectionID, collectionName, "
                     "parentCollectionID) VALUES (?,?,?)", COLLECTIONS)
    tag_ids = {}
    for item_id, key, title, cols, tags in ITEMS:
        conn.execute("INSERT INTO items (itemID, key, itemTypeID) VALUES (?,?,1)",
                     (item_id, key))
        conn.execute("INSERT INTO itemDataValues VALUES (?,?)", (item_id, title))
        conn.execute("INSERT INTO itemData VALUES (?,110,?)", (item_id, item_id))
        # A DOI on every item, so each one has something to be queued by.
        conn.execute("INSERT INTO itemDataValues VALUES (?,?)",
                     (900 + item_id, f"10.1000/{key.lower()}"))
        conn.execute("INSERT INTO itemData VALUES (?,111,?)", (item_id, 900 + item_id))
        for c in cols:
            conn.execute("INSERT INTO collectionItems VALUES (?,?)", (c, item_id))
        for t in tags:
            if t not in tag_ids:
                tag_ids[t] = len(tag_ids) + 1
                conn.execute("INSERT INTO tags VALUES (?,?)", (tag_ids[t], t))
            conn.execute("INSERT INTO itemTags VALUES (?,?)", (item_id, tag_ids[t]))
    conn.commit()
    conn.close()

    monkeypatch.setattr("magi.kb_registry.load_settings",
                        lambda: {"zotero_data_dir": str(lib)})
    return lib


@pytest.fixture
def ws(tmp_path):
    from magi import init_workspace

    target = tmp_path / "topic"
    init_workspace.main(["--topic-dir", str(target), "--name", "T"])
    return target


@pytest.fixture
def client():
    return TestClient(create_app())


# --------------------------------------------------------------------------
# choosing what to import
# --------------------------------------------------------------------------

def test_the_folder_tree_can_be_read(client, zotero_library):
    res = client.get("/api/zotero/collections")
    assert res.status_code == 200

    names = {c["collectionName"] for c in res.json()["collections"]}
    assert {"Fractons", "2024", "Reading", "Symmetry"} <= names


def test_the_tree_carries_the_parent_links_a_picker_needs(client, zotero_library):
    cols = {c["collectionID"]: c for c in
            client.get("/api/zotero/collections").json()["collections"]}
    assert cols[2]["parentCollectionID"] == 1, "nesting is not visible to the UI"


def test_importing_a_collection_takes_what_is_beneath_it(client, zotero_library, ws):
    from magi.ingest import ledger

    res = client.post("/api/zotero/import",
                      json={"collection_id": 1, "workspace": str(ws)})
    assert res.status_code == 200, res.text
    assert len(res.json()["queued"]) == 2, "the nested folder's paper was left out"
    assert len(ledger.pending(ws)) == 2


def test_importing_by_tag_works(client, zotero_library, ws):
    res = client.post("/api/zotero/import",
                      json={"tag": "survey", "workspace": str(ws)})
    assert {q["title"] for q in res.json()["queued"]} == {
        "Filed nowhere", "Fracton overview", "Top-level reading"}


def test_importing_named_items_works(client, zotero_library, ws):
    res = client.post("/api/zotero/import",
                      json={"keys": ["AAAA1111"], "workspace": str(ws)})
    assert [q["title"] for q in res.json()["queued"]] == ["Fracton overview"]


# --------------------------------------------------------------------------
# what it must not do
# --------------------------------------------------------------------------

def test_it_refuses_to_guess_when_nothing_is_named(client, zotero_library, ws):
    """`all` is a word somebody has to type. Defaulting to it would turn a
    mis-click into an entire bibliography in the queue."""
    res = client.post("/api/zotero/import", json={"workspace": str(ws)})
    assert res.status_code == 400
    assert "name what to import" in res.json()["detail"]


def test_the_whole_library_is_available_but_only_on_request(client, zotero_library, ws):
    res = client.post("/api/zotero/import",
                      json={"all": True, "workspace": str(ws)})
    assert len(res.json()["queued"]) == len(ITEMS)


def test_importing_twice_does_not_duplicate(client, zotero_library, ws):
    from magi.ingest import ledger

    body = {"collection_id": 1, "workspace": str(ws)}
    client.post("/api/zotero/import", json=body)
    again = client.post("/api/zotero/import", json=body)

    assert all(q["status"] == "already-queued" for q in again.json()["queued"])
    assert len(ledger.pending(ws)) == 2


def test_it_only_queues_and_never_fetches(client, zotero_library, ws):
    """Nothing enters the library here — the panel's existing approve gate is
    what does that, and a Zotero import must not route around it."""
    client.post("/api/zotero/import", json={"all": True, "workspace": str(ws)})

    # `magi init` scaffolds an _index.md in each directory; a document is
    # anything else.
    for d in (ws / "raw" / "papers", ws / "wiki" / "references"):
        assert [p.name for p in d.glob("*.md") if p.name != "_index.md"] == []


def test_a_directory_that_is_not_a_workspace_is_refused(client, zotero_library, tmp_path):
    res = client.post("/api/zotero/import",
                      json={"all": True, "workspace": str(tmp_path / "nope")})
    assert res.status_code == 400


@pytest.mark.parametrize("candidates", [
    ["/one", "/two"],
    # The one that was missed. A lone candidate is the *more* dangerous case,
    # not the safe one: a machine whose only discovered directory is an
    # abandoned OneDrive sync folder, while the real library sits somewhere the
    # fallback list does not guess, imports a bibliography frozen years ago and
    # looks exactly like success. The CLI refuses to pick here and says so in a
    # comment; the WebUI picked, under a docstring claiming it did not.
    ["/only-one"],
    [],
])
def test_no_chosen_library_asks_rather_than_picking_one(client, monkeypatch, candidates):
    monkeypatch.setattr("magi.kb_registry.load_settings", lambda: {})
    monkeypatch.setattr("magi.ingest.zotero.candidate_data_dirs",
                        lambda *a, **k: list(candidates))

    res = client.get("/api/zotero/collections")
    assert res.status_code == 409
    assert "zotero-dirs" in res.json()["detail"]


def test_a_stored_setting_whose_library_moved_is_refused_up_front(client, tmp_path,
                                                                  monkeypatch):
    """The directory still being there is not the same as the library being
    there. Accepting it on `is_dir()` alone turned a fixable misconfiguration
    into a 502 out of sqlite with no mention of how to re-point it."""
    stale = tmp_path / "moved-away"
    stale.mkdir()                      # exists, but holds no zotero.sqlite
    monkeypatch.setattr("magi.kb_registry.load_settings",
                        lambda: {"zotero_data_dir": str(stale)})
    monkeypatch.setattr("magi.ingest.zotero.candidate_data_dirs", lambda *a, **k: [])

    res = client.get("/api/zotero/collections")
    assert res.status_code == 409
    assert "zotero-dirs" in res.json()["detail"]


def test_the_webui_and_the_cli_resolve_the_library_the_same_way(monkeypatch):
    """Not "the same rules" — the same function. The first version restated
    the rules and got both halves wrong."""
    import inspect

    from magi.ui import api

    src = inspect.getsource(api)
    body = src.split("def _zotero_data_dir(", 1)[1].split("@app.get", 1)[0]
    assert "_chosen_data_dir" in body, (
        "the WebUI resolves the Zotero library on its own again")
    assert "candidate_data_dirs" not in body, (
        "the WebUI is re-deciding what to do with the candidate list")
