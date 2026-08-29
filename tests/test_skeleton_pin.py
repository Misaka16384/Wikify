"""`skeleton: true` — overruling the degree ranking on purpose.

The skeleton view keeps the best-connected sixty nodes, which is right most of
the time and systematically wrong about one thing: the newest note has the
fewest edges, and the newest note is usually what somebody is working on. Left
to degree alone, the map hides the live end of the project and shows the part
nobody has touched in months.

So a note may pin itself. The tests here are about the two halves of that: the
pin survives the cut, and it does not quietly eat the map — a pinned set larger
than the budget would otherwise push out every real hub and leave a picture
with the shape gone and nothing saying so.
"""

import sqlite3

import pytest

from magi.kb import graph_browse


def _graph(rows, edges=(), tags=()):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE nodes (id TEXT PRIMARY KEY, title TEXT, type TEXT,
                            category TEXT);
        CREATE TABLE edges (source_id TEXT, target_id TEXT, type TEXT);
        CREATE TABLE tags (node_id TEXT, tag TEXT);
    """)
    conn.executemany("INSERT INTO nodes VALUES (?, ?, ?, ?)", rows)
    conn.executemany("INSERT INTO edges VALUES (?, ?, ?)", edges)
    conn.executemany("INSERT INTO tags VALUES (?, ?)", tags)
    return conn


def _hub_graph(hubs=5, extra=()):
    """`hubs` well-connected nodes, plus whatever else is asked for."""
    rows = [(f"h{i}", f"hub {i}", "concept", "") for i in range(hubs)]
    rows += list(extra)
    edges = [(f"h{i}", f"h{j}", "wikilink")
             for i in range(hubs) for j in range(hubs) if i != j]
    return rows, edges


# --------------------------------------------------------------------------
# the pin
# --------------------------------------------------------------------------

def test_an_unconnected_note_is_dropped_from_the_skeleton():
    """The premise: without a pin, degree decides and a lone note loses."""
    rows, edges = _hub_graph(extra=[("lonely", "Lonely", "proposition", "")])
    conn = _graph(rows, edges)

    kept = {n["id"] for n in graph_browse.browse_map(
        conn, skeleton=True, limit=5)["nodes"]}

    assert "lonely" not in kept


def test_a_pinned_note_survives_however_few_edges_it_has():
    rows, edges = _hub_graph(extra=[("lonely", "Lonely", "proposition", "")])
    conn = _graph(rows, edges, tags=[("lonely", "skeleton")])

    result = graph_browse.browse_map(conn, skeleton=True, limit=5)

    assert "lonely" in {n["id"] for n in result["nodes"]}
    assert len(result["nodes"]) == 5, "the pin takes a slot, it does not add one"


def test_the_pin_costs_a_hub_rather_than_widening_the_map():
    """A pin is a person overruling the ranking, not raising the budget. The
    budget is the whole reason the skeleton is readable."""
    rows, edges = _hub_graph(extra=[("lonely", "Lonely", "proposition", "")])
    conn = _graph(rows, edges, tags=[("lonely", "skeleton")])

    kept = {n["id"] for n in graph_browse.browse_map(
        conn, skeleton=True, limit=3)["nodes"]}

    assert "lonely" in kept and len(kept) == 3


def test_pins_beyond_the_budget_do_not_hide_that_the_map_was_cut():
    rows, edges = _hub_graph(extra=[(f"p{i}", f"pin {i}", "proposition", "")
                                    for i in range(4)])
    conn = _graph(rows, edges, tags=[(f"p{i}", "skeleton") for i in range(4)])

    result = graph_browse.browse_map(conn, skeleton=True, limit=4)

    assert result["truncated"] is True
    assert {n["id"] for n in result["nodes"]} == {"p0", "p1", "p2", "p3"}


def test_a_pin_is_only_a_pin_in_the_skeleton_view():
    """The full map already shows everything; a pin there would mean nothing,
    and a flag that means nothing somewhere is a flag people misread."""
    rows, edges = _hub_graph(extra=[("lonely", "Lonely", "proposition", "")])
    conn = _graph(rows, edges, tags=[("lonely", "skeleton")])

    full = graph_browse.browse_map(conn, skeleton=False, limit=800)

    assert "lonely" in {n["id"] for n in full["nodes"]}
    assert full["truncated"] is False


def test_a_graph_with_no_tag_table_still_renders():
    """An index built by an older version has no such rows, and a map that
    refuses to draw because of a missing pin is worse than an unpinned map."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE nodes (id TEXT PRIMARY KEY, title TEXT, type TEXT,
                            category TEXT);
        CREATE TABLE edges (source_id TEXT, target_id TEXT, type TEXT);
    """)
    conn.execute("INSERT INTO nodes VALUES ('a', 'A', 'concept', '')")

    assert graph_browse.pinned(conn) == set()
    assert graph_browse.browse_map(conn, skeleton=True)["nodes"]


# --------------------------------------------------------------------------
# how the pin gets into the graph
# --------------------------------------------------------------------------

@pytest.mark.parametrize("written,pinned", [
    (True, True), ("true", True), ("yes", True), ("True", True), (1, True),
    (False, False), ("no", False), ("", False), (None, False),
])
def test_however_a_person_spells_it_in_frontmatter(written, pinned):
    """YAML makes `true`, `yes` and `"true"` three different types, and a
    person editing frontmatter by hand writes whichever they think of. A pin
    that silently does nothing because it was quoted is worse than no pin."""
    from magi.kb.llmwiki import _is_pinned

    assert _is_pinned(written) is pinned


def test_the_field_is_declared_so_lint_does_not_call_it_a_stray():
    from magi.core import vocab
    from magi.kb import threads

    for kind in (vocab.PROPOSITION, vocab.QUESTION, vocab.LINE):
        assert threads.PINNED in threads.KIND_OPTIONAL[kind], kind


# --------------------------------------------------------------------------
# one signal, two renderings
# --------------------------------------------------------------------------

def test_the_map_names_what_the_graph_must_keep(tmp_path):
    """design-v2 §12: MAP.md and the map view are two renderings of one
    directory. A pin that reaches only one of them is a third thing pretending
    to be part of the first."""
    from magi import state
    from magi.kb import thread_cmd

    (tmp_path / "threads").mkdir()
    assert thread_cmd.main(["new", "p-key", "--topic-dir", str(tmp_path),
                            "--kind", "proposition", "--title", "The one",
                            "--purpose", "because"]) == 0
    path = tmp_path / "threads" / "p-key.md"
    path.write_text(path.read_text(encoding="utf-8")
                    .replace("purpose:", "skeleton: true\npurpose:", 1),
                    encoding="utf-8")

    loaded = state.load(tmp_path)

    assert state.pinned(loaded) == ["p-key"]
    rendered = state.render_map(loaded)
    assert "## Pinned" in rendered and "[[p-key]]" in rendered


def test_a_library_with_no_pins_has_no_pinned_section(tmp_path):
    """An empty section is a section a reader learns to skip, and then keeps
    skipping when it fills up."""
    from magi import state
    from magi.kb import thread_cmd

    (tmp_path / "threads").mkdir()
    thread_cmd.main(["new", "p-a", "--topic-dir", str(tmp_path), "--kind",
                     "proposition", "--title", "A", "--purpose", "because"])

    assert "## Pinned" not in state.render_map(state.load(tmp_path))
