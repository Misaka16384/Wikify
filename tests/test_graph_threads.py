"""`threads/` on the same graph as the library it is about.

A proposition names the concepts it is stated in terms of, cites the sources it
rests on, and points at the derivation that argues it. Those are edges. A map
of the library without them is a map of half the picture — it can show which
cards link to which, but not which parts of the library the open questions are
actually touching, which is the question somebody opens a graph to ask.

What the columns mean here follows what they already mean elsewhere in the
table: `type` is the kind of node, `category` is the subgroup within it. So a
note's kind is its type and its status is its category. Temperature and line
go in as tags, because the graph already filters on tags and a second
mechanism for the same job is a second answer to the same question.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys

import pytest

from magi.core import vocab
from magi.kb import threads


@pytest.fixture
def built(tmp_path):
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "threads").mkdir()
    (tmp_path / "wiki" / "concepts" / "gap.md").write_text(
        "---\ntitle: Spectral gap\ntype: concept\n---\nA gap.\n", encoding="utf-8")

    note = threads.create(tmp_path / "threads" / "p-gap.md", vocab.PROPOSITION,
                          "The gap survives", "Decide before the numerics.",
                          lines=["qec"], extra={"depends_on": ["[[Spectral gap]]"]})
    threads.set_status(note, "testing", "started the sweep", host="claude")
    threads.create(tmp_path / "threads" / "qec.md", vocab.LINE, "QEC",
                   "Whether the code survives disorder.")

    proc = subprocess.run([sys.executable, "-m", "magi", "graph", "build",
                           str(tmp_path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr
    conn = sqlite3.connect(tmp_path / "output" / "graph.db")
    yield conn
    conn.close()


def test_a_note_is_a_node_of_its_own_kind(built):
    rows = dict((row[0], row[1:]) for row in built.execute(
        "SELECT id, type, category, title FROM nodes").fetchall())

    assert rows["threads/p-gap"][:2] == (vocab.PROPOSITION, "testing")
    assert rows["threads/p-gap"][2] == "The gap survives"
    assert rows["threads/qec"][:2] == (vocab.LINE, "exploring")


def test_what_a_proposition_depends_on_is_an_edge(built):
    """`depends_on` is a link like any other. Reading it only out of the body
    would miss the one place the schema asks for it."""
    edges = built.execute(
        "SELECT target_id FROM edges WHERE source_id = 'threads/p-gap' "
        "AND type = 'wikilink'").fetchall()
    assert ("wiki/concepts/gap",) in edges


def test_temperature_and_line_arrive_as_tags(built):
    tags = {row[0] for row in built.execute(
        "SELECT tag FROM tags WHERE node_id = 'threads/p-gap'").fetchall()}
    assert tags == {"tier:hot", "line:qec"}


def test_the_library_is_still_there(built):
    """The point was to add the research state, not to replace the library
    with it."""
    kinds = {row[0] for row in built.execute("SELECT type FROM nodes").fetchall()}
    assert {"concept", vocab.PROPOSITION, vocab.LINE} <= kinds


def open_ro_from(conn):
    """The same connection, with rows addressable by column name.

    `browse_map` reads `r["type"]`, which a default connection does not
    support — the fixture opens one for writing so a test can add a node.
    """
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------------------------------
# reading the map at two sizes
#
# At 800 nodes a graph is a texture, and a texture answers no question. The
# skeleton is the same graph with only the shape left, and which nodes make up
# that shape is the server's call — a second answer computed in the browser
# would be a second answer.
# --------------------------------------------------------------------------

def test_the_map_can_show_only_the_research_state(built):
    from magi.kb.graph_browse import browse_map

    conn = open_ro_from(built)
    result = browse_map(conn, kinds=["proposition", "question", "line"])
    kinds = {node["type"] for node in result["nodes"]}

    assert kinds <= {"proposition", "question", "line", "ghost"}
    assert "concept" not in kinds


def test_a_node_carries_its_status(built):
    """`category` is the subgroup within the kind everywhere else in this
    table, and for a note that is its status."""
    from magi.kb.graph_browse import browse_map

    conn = open_ro_from(built)
    rows = {node["id"]: node for node in browse_map(conn)["nodes"]}
    assert rows["threads/p-gap"]["category"] == "testing"


def test_the_skeleton_drops_the_links_nobody_has_written_yet(built):
    """A dangling link is not part of the shape — it is a note that does not
    exist."""
    from magi.kb.graph_browse import browse_map

    conn = open_ro_from(built)
    conn.execute("INSERT INTO edges VALUES('threads/p-gap', 'Nothing Yet', 'wikilink')")

    assert any(n["type"] == "ghost" for n in browse_map(conn)["nodes"])
    assert not any(n["type"] == "ghost" for n in browse_map(conn, skeleton=True)["nodes"])


def test_the_skeleton_is_small_enough_to_read(built):
    from magi.kb import graph_browse

    conn = open_ro_from(built)
    for index in range(graph_browse.SKELETON_LIMIT + 20):
        conn.execute("INSERT INTO nodes VALUES(?, '', ?, 'concept', 'concept', '', '', '')",
                     (f"wiki/concepts/c{index}", f"C{index}"))

    result = graph_browse.browse_map(conn, skeleton=True)
    assert len(result["nodes"]) == graph_browse.SKELETON_LIMIT
    assert result["truncated"]


def test_every_node_carries_a_category_including_ghosts(built):
    """A field present for most rows and absent for some is a field every
    reader has to guard."""
    from magi.kb.graph_browse import browse_map

    conn = open_ro_from(built)
    conn.execute("INSERT INTO edges VALUES('threads/p-gap', 'Nothing Yet', 'wikilink')")

    assert all("category" in node for node in browse_map(conn)["nodes"])


def test_the_skeleton_ranks_on_edges_that_exist(built):
    """A node whose whole degree came from dangling links used to outrank real
    hubs and land in the skeleton as an isolated dot."""
    from magi.kb import graph_browse

    conn = open_ro_from(built)
    conn.execute("INSERT INTO nodes VALUES('wiki/concepts/dangler','','D','concept','concept','','','')")
    for index in range(5):
        conn.execute("INSERT INTO edges VALUES('wiki/concepts/dangler', ?, 'wikilink')",
                     (f"Nothing {index}",))

    # Small enough that the ranking has to choose. Before the fix the dangler
    # ranked first on five links to notes that do not exist, and the skeleton
    # opened with an isolated dot.
    kept = [node["id"] for node in
            graph_browse.browse_map(conn, limit=2, skeleton=True)["nodes"]]

    assert "wiki/concepts/dangler" not in kept
    assert "threads/p-gap" in kept, "a node with a real edge"


def test_a_kind_the_graph_has_no_colour_for_does_not_reach_the_type_column(tmp_path):
    from magi.kb.llmwiki import NODE_TYPES

    assert "banana" not in NODE_TYPES


def test_one_malformed_note_does_not_abort_the_build(tmp_path):
    """`read_note` promises never to raise on malformed content; a list-valued
    `kind:` used to abort the insert instead, leaving no graph.db at all."""
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "threads").mkdir()
    (tmp_path / "wiki" / "concepts" / "c.md").write_text(
        "---\ntitle: C\ntype: concept\n---\nx\n", encoding="utf-8")
    (tmp_path / "threads" / "listy.md").write_text(
        "---\nkind:\n  - proposition\nstatus: open\n---\n\n# Listy\n",
        encoding="utf-8")

    proc = subprocess.run([sys.executable, "-m", "magi", "graph", "build",
                           str(tmp_path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "output" / "graph.db").is_file()


def test_the_printed_count_is_the_count_in_the_table(built, tmp_path):
    nodes = built.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    edges = built.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    assert nodes > 3 and edges > 1, "tags become nodes and edges of their own"
