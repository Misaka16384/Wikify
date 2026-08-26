"""The WebUI's door for a document that only exists on the reader's own disk.

Every ingest door the dashboard had took an identifier — a URL, a DOI, an
arXiv id. Someone holding a PDF that is not on arXiv, which is most PDFs, had
no way into their own library without opening a terminal: the two surfaces
built for feeding a library, the dashboard and the browser extension, were the
two that could not accept a file.

The door is deliberately narrow. It writes one file into `inbox/` and imports
no converter, no subprocess and no job manager, so what a loopback server
exposes is "a file can appear in inbox/" and nothing more. Everything after
that stays a visible step somebody chooses.
"""

import pytest
from fastapi.testclient import TestClient

from magi.ui.api import create_app, safe_upload_name


@pytest.fixture
def ws(tmp_path):
    from magi.hub import init_workspace

    init_workspace.main(["--topic-dir", str(tmp_path), "--name", "T"])
    return tmp_path


@pytest.fixture
def client():
    return TestClient(create_app())


def _put(client, ws, name, body=b"%PDF-1.4 hello"):
    return client.post(f"/api/ingest/upload?name={name}&workspace={ws}", content=body)


# --------------------------------------------------------------------------
# the happy path
# --------------------------------------------------------------------------

def test_a_pdf_lands_in_inbox(client, ws):
    res = _put(client, ws, "paper.pdf")
    assert res.status_code == 200, res.text

    body = res.json()
    assert body["name"] == "paper.pdf"
    assert body["bytes"] == len(b"%PDF-1.4 hello")
    assert (ws / "inbox" / "paper.pdf").read_bytes() == b"%PDF-1.4 hello"


def test_it_reports_what_is_now_waiting(client, ws):
    _put(client, ws, "a.pdf")
    assert _put(client, ws, "b.pdf").json()["inbox_pending"] == 2


@pytest.mark.parametrize("name", ["p.pdf", "notes.md", "src.tex", "paper.tar.gz"])
def test_every_kind_ingest_can_route_is_accepted(client, ws, name):
    assert _put(client, ws, name).status_code == 200


def test_a_chinese_filename_keeps_its_name(client, ws):
    """An ASCII allow-list is not sanitising, it is losing the title."""
    res = _put(client, ws, "拓扑序.pdf")
    assert res.status_code == 200
    assert res.json()["name"] == "拓扑序.pdf"


# --------------------------------------------------------------------------
# what it refuses
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("../../etc/passwd.pdf", "passwd.pdf"),
    ("a/b/c.pdf", "c.pdf"),
    (r"C:\Windows\evil.pdf", "evil.pdf"),
])
def test_a_path_can_only_ever_name_a_file_inside_inbox(client, ws, name, expected):
    res = _put(client, ws, name)
    assert res.status_code == 200
    assert res.json()["name"] == expected
    assert (ws / "inbox" / expected).is_file()


def test_the_accepted_kinds_are_exactly_the_routable_ones(client):
    """Hand-listing them here accepted `.zip` and `.ltx`, which no route
    reads — the file would land in inbox/ and be skipped forever, which reads
    to whoever uploaded it exactly like a silent failure."""
    from magi.ingest import routing
    from magi.ui.api import UPLOAD_SUFFIXES

    assert UPLOAD_SUFFIXES == (set(routing.TEXT_SUFFIXES)
                               | set(routing.TEX_SUFFIXES) | {".pdf"})


@pytest.mark.parametrize("name", ["archive.zip", "paper.ltx", "thesis.docx"])
def test_an_unroutable_kind_is_refused_rather_than_parked(client, ws, name):
    assert _put(client, ws, name).status_code == 415


def test_an_unroutable_kind_leaves_nothing_behind(client, ws):
    """A .docx in inbox/ would be skipped by every route forever, which reads
    to the uploader exactly like the upload having failed silently."""
    res = _put(client, ws, "thesis.docx")
    assert res.status_code == 415
    assert not any((ws / "inbox").glob("thesis*"))


def test_an_empty_body_is_refused(client, ws):
    assert _put(client, ws, "paper.pdf", b"").status_code == 400
    assert not (ws / "inbox" / "paper.pdf").exists()


def test_a_directory_that_is_not_a_workspace_is_refused(client, tmp_path):
    res = _put(client, tmp_path / "nowhere", "paper.pdf")
    assert res.status_code == 400
    assert "workspace" in res.json()["detail"]


def test_an_unusable_name_is_refused(client, ws):
    assert _put(client, ws, "..").status_code == 400


# --------------------------------------------------------------------------
# what it must not destroy
# --------------------------------------------------------------------------

def test_a_second_file_of_the_same_name_does_not_replace_the_first(client, ws):
    """inbox/ is ORIGINAL: the file already sitting there is a document
    waiting to be ingested, not a cache entry."""
    _put(client, ws, "paper.pdf", b"FIRST")
    res = _put(client, ws, "paper.pdf", b"SECOND")

    assert res.json()["renamed"] is True
    assert (ws / "inbox" / "paper.pdf").read_bytes() == b"FIRST"
    assert (ws / "inbox" / res.json()["name"]).read_bytes() == b"SECOND"


def test_nothing_partial_is_left_behind_when_a_upload_is_refused(client, ws):
    _put(client, ws, "paper.pdf", b"")
    leftovers = [p.name for p in (ws / "inbox").iterdir() if p.name.startswith(".upload")]
    assert leftovers == []


# --------------------------------------------------------------------------
# the sanitiser on its own
# --------------------------------------------------------------------------

def test_a_long_name_is_trimmed_without_losing_its_extension(client):
    """`name[:180]` cut the suffix off, and a document with no extension is
    one every router downstream answers "no route for this"."""
    out = safe_upload_name("a" * 300 + ".pdf")
    assert out.endswith(".pdf")
    assert len(out) <= 180


def test_a_reserved_device_name_cannot_be_created(client):
    assert safe_upload_name("CON.pdf") != "CON.pdf"


# --------------------------------------------------------------------------
# the two-step the dashboard actually performs
# --------------------------------------------------------------------------

def test_an_uploaded_file_can_be_queued_by_the_door_that_already_exists(client, ws):
    """The panel uploads and then makes the same enqueue call its link field
    makes, so an uploaded PDF reaches the library through the existing
    convert -> approve -> commit gate rather than a second path with its own
    rules. If `classify` stopped recognising a local path as a file source,
    the dashboard would silently start queuing PDFs as URLs."""
    from magi.ingest import ledger
    from magi.kb_registry import register_kb

    name = register_kb(ws, quiet=True)
    up = _put(client, ws, "paper.pdf").json()

    res = client.post("/api/ingest/enqueue",
                      json={"value": up["path"], "library": name})
    assert res.status_code == 200, res.text
    assert res.json()["source_type"] == "file"

    pending = ledger.pending(ws)
    assert [p.value for p in pending] == [up["path"]]


def test_a_compound_suffix_survives_a_collision_rename(client, ws):
    """`dest.stem` strips only the last suffix, so a second `paper.tar.gz`
    landed as `paper.tar-2.tar.gz`. `safe_upload_name` right above already
    slices compound suffixes correctly — the two places in one function that
    take a filename apart have to agree about where it ends."""
    _put(client, ws, "paper.tar.gz", b"FIRST")
    res = _put(client, ws, "paper.tar.gz", b"SECOND")

    assert res.json()["renamed"] is True
    assert res.json()["name"] == "paper-2.tar.gz"
    assert (ws / "inbox" / "paper.tar.gz").read_bytes() == b"FIRST"
