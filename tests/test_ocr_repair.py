"""A page that comes back wrong gets read another way, once.

Two symptoms, one response. The loud one is a page that repeats itself. The
quiet one is a table that stopped halfway — nothing malformed, nothing
repeated, the page reads as complete, and half the rows are gone.

Everything here follows from one measurement: **the failure is not random.** The
same page through the same pipeline produced byte-identical output twice —
49,561 characters, the body repeated twenty times, both runs. So retrying the
call unchanged reproduces the failure exactly, and a repair has to change a
parameter.

Splitting the page is that parameter, because it is measured to fix it: the
same page at 2x2 came back clean, and a scanned table page went from 10 of 49
rows to all 49. It is also measured to make one page *worse* — a two-column
split turned a 559-character answer into 32,785 characters of loop — which is
why the two attempts are judged rather than the second one assumed better.

The judge is the gate that found the problem. "Better" is not a second opinion
invented for the repair.
"""

import pytest

from magi.ingest.gates import repetition_runs
from magi.ingest.ocr.ocr_engine import OCREngine

pytest.importorskip("PIL.Image", reason="Pillow ships with the OCR rung")


CLEAN = ("# A page\n\n" + "The transfer matrix is constructed from the local "
         "Boltzmann weights, and its largest eigenvalue gives the free energy "
         "density in the thermodynamic limit. ") * 1
LOOP = "# A page\n\n" + ("Anyons are defined as violations of stabilizers, and "
                        "the mapping carries each violation to a coset of the "
                        "lattice group. ") * 8


_HEAD = ("| $[[n,k,d]]$ | $f(x,y)$ | $\\vec{a}_1$ |\n"
         "|---|---|---|\n")


def _rows(lo, hi):
    return "".join("| $[[%d,4,2]]$ | $xy$ | (0,%d) |\n" % (12 + 2 * i, i)
                   for i in range(lo, hi))


def _table(rows):
    """A markdown table of `rows` data rows, as a page would carry it."""
    return "# A page of codes\n\n" + _HEAD + _rows(0, rows)


#: What the model writes from a whole page: it stops around 24 rows.
TRUNCATED_TABLE = _table(24)
#: What the same page returns when it is split.
FULL_TABLE = _table(49)

#: What the two tiles of that page return — different content each, which is
#: the only reason stitching them back together produces the whole table.
#: Handing every tile the same answer produces two copies of one table, and the
#: stitcher is right to call that a repetition loop.
TABLE_TILES = ["# A page of codes\n\n" + _HEAD + _rows(0, 25), _rows(25, 49)]


@pytest.fixture
def page_png(tmp_path):
    from PIL import Image

    path = tmp_path / "page.png"
    Image.new("RGB", (1200, 1600), "white").save(path)
    return path


def _engine(monkeypatch, answers):
    """An engine whose model returns a canned answer per call, in order."""
    eng = OCREngine("glm-ocr:q8_0")
    calls = []

    def fake(image_path):
        calls.append(image_path)
        return answers[min(len(calls) - 1, len(answers) - 1)]

    monkeypatch.setattr(eng, "_transcribe", fake)
    return eng, calls


# --------------------------------------------------------------------------
# The measurement this rests on
# --------------------------------------------------------------------------

def test_the_fixture_really_does_read_as_a_loop():
    """If this stopped being true the rest of the file would pass vacuously."""
    assert repetition_runs(LOOP) > 1
    assert repetition_runs(CLEAN) == 1


# --------------------------------------------------------------------------
# When a repair happens
# --------------------------------------------------------------------------

def test_a_clean_page_is_not_read_twice(page_png, monkeypatch):
    """The repair must cost nothing on the pages that do not need it."""
    eng, calls = _engine(monkeypatch, [CLEAN])
    result, note = eng.ocr_image_repaired(str(page_png), 1)

    assert len(calls) == 1
    assert note == ""


def test_a_repeating_page_is_read_again_a_different_way(page_png, monkeypatch):
    eng, calls = _engine(monkeypatch, [LOOP, CLEAN])
    result, note = eng.ocr_image_repaired(str(page_png), 3)

    assert len(calls) > 1, "the page was not re-read"
    assert result.markdown.strip() == CLEAN.strip()
    assert "page 3" in note


def test_the_retry_changes_the_configuration(page_png, monkeypatch):
    """Retrying unchanged is worthless here — the failure is deterministic, so
    an identical call reproduces it exactly."""
    eng, calls = _engine(monkeypatch, [LOOP, CLEAN])
    eng.ocr_image_repaired(str(page_png), 1, tiles=None)

    # A whole-page first attempt is one call; the repair splits, so more.
    assert len(calls) == 1 + OCREngine.REPAIR_TILES[0] * OCREngine.REPAIR_TILES[1]


def test_a_page_already_split_is_repaired_by_being_read_whole(page_png, monkeypatch):
    """Splitting is what amplified the loop on the one page where the repair
    made things worse, so a split page does not get split further."""
    eng, calls = _engine(monkeypatch, [LOOP, CLEAN])
    eng.ocr_image_repaired(str(page_png), 1, tiles=OCREngine.REPAIR_TILES)

    n_first = OCREngine.REPAIR_TILES[0] * OCREngine.REPAIR_TILES[1]
    assert len(calls) == n_first + 1, "the repair should have read the whole page"


# --------------------------------------------------------------------------
# How to split depends on what is on the page, not on which symptom fired
# --------------------------------------------------------------------------
#
# Measured on the same 49-row table, three sources, both shapes:
#
#     left/right (2x1)   49/49 native, 49/49 clean scan, 45/49 degraded scan
#     2x2                49/49 native, 47/49 clean scan, 32/49 end to end
#
# The 2x2 cut lands inside the table and each half-row is transcribed as a row
# of its own: a hundred rows where forty-nine exist, in a document that reads
# as a clean table. But a two-column split is also what turned a prose page's
# 559-character answer into a 32,785-character loop, so neither shape is right
# everywhere. The page has to say which it is.

def test_a_table_page_is_split_left_and_right():
    assert OCREngine._alternative(None, has_table=True) == OCREngine.TABLE_REPAIR_TILES
    assert OCREngine.TABLE_REPAIR_TILES[1] == 1, "a horizontal cut crosses the rows"


def test_a_page_without_a_table_is_split_both_ways():
    assert OCREngine._alternative(None, has_table=False) == OCREngine.REPAIR_TILES


def test_a_looping_table_page_is_still_split_the_table_way(page_png, monkeypatch):
    """The symptom that fired and the shape to use are different questions. A
    page can loop *and* be a table page, and repairing that one 2x2 fixes the
    loop while cutting the rows in half."""
    looping_table = TRUNCATED_TABLE + "\n\n" + LOOP
    eng, calls = _engine(monkeypatch, [looping_table] + TABLE_TILES)
    _, note = eng.ocr_image_repaired(str(page_png), 1)

    assert "repeated itself" in note
    n_tiles = OCREngine.TABLE_REPAIR_TILES[0] * OCREngine.TABLE_REPAIR_TILES[1]
    assert len(calls) == 1 + n_tiles


def test_at_most_one_repair_per_page(page_png, monkeypatch):
    """A document where every page loops would otherwise cost double forever."""
    eng, calls = _engine(monkeypatch, [LOOP])       # every attempt loops
    result, note = eng.ocr_image_repaired(str(page_png), 1)

    assert len(calls) == 1 + OCREngine.REPAIR_TILES[0] * OCREngine.REPAIR_TILES[1]
    assert result.markdown.strip()                  # something is still returned


# --------------------------------------------------------------------------
# Choosing between the two attempts
# --------------------------------------------------------------------------

def test_a_clean_result_beats_a_repeating_one():
    assert OCREngine._is_better(CLEAN, LOOP)
    assert not OCREngine._is_better(LOOP, CLEAN)


def test_between_two_clean_results_the_fuller_one_wins():
    """Measured: the split read 6,362 characters and every table row where the
    whole page read 4,200 and half of them."""
    more = CLEAN + "\n\nAnd a further paragraph of genuinely new material here."
    assert OCREngine._is_better(more, CLEAN)
    assert not OCREngine._is_better(CLEAN, more)


def test_between_two_repeating_results_the_smaller_mess_wins():
    """The measured bad case: 559 characters of truncation against 32,785 of
    loop. Neither is good; one is much less garbage to read."""
    worse = LOOP * 4
    assert OCREngine._is_better(LOOP, worse)
    assert not OCREngine._is_better(worse, LOOP)


def test_a_repair_that_helps_nothing_keeps_the_original(page_png, monkeypatch):
    eng, _ = _engine(monkeypatch, [LOOP, LOOP * 4])
    result, note = eng.ocr_image_repaired(str(page_png), 1)

    assert result.markdown.strip() == LOOP.strip()
    assert "no better" in note


def test_a_retry_that_returns_nothing_keeps_the_original(page_png, monkeypatch):
    """An empty answer is not an improvement on a bad one."""
    eng, _ = _engine(monkeypatch, [LOOP, ""])
    result, note = eng.ocr_image_repaired(str(page_png), 1)

    assert result.markdown.strip() == LOOP.strip()
    assert "returned nothing" in note


# --------------------------------------------------------------------------
# Saying so
# --------------------------------------------------------------------------

def test_every_outcome_is_reported(page_png, monkeypatch):
    """A repair that leaves no trace is the same silent degradation this
    pipeline exists to stop, pointed the other way. Whichever way it goes, the
    reader is told."""
    for answers, expected in (([LOOP, CLEAN], "kept that"),
                              ([LOOP, LOOP * 4], "no better"),
                              ([LOOP, ""], "returned nothing")):
        eng, _ = _engine(monkeypatch, answers)
        _, note = eng.ocr_image_repaired(str(page_png), 7)
        assert note and expected in note, (answers[1][:20], note)
        assert "page 7" in note


# --------------------------------------------------------------------------
# The quiet symptom: a table that stopped halfway
# --------------------------------------------------------------------------
#
# Repetition is loud. This one is not: nothing is malformed, nothing repeats,
# the page reads as complete, and half the rows are gone. It is the failure the
# whole ladder exists to avoid, and it was going undetected on every scan --
# tiling is aimed by looking for tables in the PDF's text layer, and a scan has
# none. Measured on one 49-row table read three ways:
#
#     native page            whole 24/49    split 49/49
#     clean scan of it       whole 24/49    split 49/49
#     the scan degraded      whole 24/49    split 45/49
#
# Twenty-four rows from three very different images is a budget, not a
# difficulty -- which is why asking the *transcription* works where asking the
# source cannot.

def test_the_table_fixtures_read_as_they_claim():
    """Otherwise the tests below pass without exercising anything."""
    from magi.ingest.ocr.tables import count_rows

    assert count_rows(TRUNCATED_TABLE) >= OCREngine.TABLE_CEILING_ROWS
    assert count_rows(_table(5)) < OCREngine.TABLE_CEILING_ROWS
    assert repetition_runs(TRUNCATED_TABLE) == 1, "it must not be the loud symptom"
    assert repetition_runs(FULL_TABLE) == 1


def test_a_truncated_table_is_read_again_split(page_png, monkeypatch):
    from magi.ingest.ocr.tables import count_rows

    eng, calls = _engine(monkeypatch, [TRUNCATED_TABLE] + TABLE_TILES)
    result, note = eng.ocr_image_repaired(str(page_png), 2)

    assert len(calls) > 1, "the page was not re-read"
    assert count_rows(result.markdown) > count_rows(TRUNCATED_TABLE)
    assert "table" in note and "page 2" in note


def test_a_short_table_is_not_read_twice(page_png, monkeypatch):
    """A table the model finished is a table it finished. Re-reading every
    page that merely *has* a table would double the cost of a table-heavy
    paper to fix pages that were never broken."""
    eng, calls = _engine(monkeypatch, [_table(5)])
    result, note = eng.ocr_image_repaired(str(page_png), 1)

    assert len(calls) == 1
    assert note == ""


def test_a_page_that_was_already_split_is_left_alone(page_png, monkeypatch):
    """It was split because its source holds a table — it has had the
    treatment, and splitting further is measured to cut through rows."""
    eng, calls = _engine(monkeypatch, [TRUNCATED_TABLE])
    result, note = eng.ocr_image_repaired(str(page_png), 1, tiles=(2, 1))

    assert len(calls) == 2, "one call per tile, and no repair"
    assert note == ""


def test_repetition_is_named_over_a_table_when_a_page_has_both(page_png, monkeypatch):
    """Both can be true at once. The loud symptom is the one to report,
    because a repeating page is wrong in a way a truncated table is not."""
    both = LOOP + "\n\n" + TRUNCATED_TABLE
    eng, _ = _engine(monkeypatch, [both, FULL_TABLE])
    _, note = eng.ocr_image_repaired(str(page_png), 1)

    assert "repeated itself" in note


def test_between_two_tables_the_fuller_one_wins():
    assert OCREngine._is_better(FULL_TABLE, TRUNCATED_TABLE, on_tables=True)
    assert not OCREngine._is_better(TRUNCATED_TABLE, FULL_TABLE, on_tables=True)


def test_more_rows_beats_more_characters():
    """The judge counts what the detector counted. On all nine measured pages
    length would have ranked them identically — but only because the fuller
    transcription happened to be the longer one every time, and a tile seam
    that duplicates a paragraph also makes a transcription longer."""
    padded = TRUNCATED_TABLE + "\n\n" + "\n\n".join(
        "Paragraph %d, which the seam between two tiles carried into the "
        "transcription a second time under a different heading." % n
        for n in range(30))
    assert len(padded) > len(FULL_TABLE)
    assert repetition_runs(padded) == 1, "the padding must not be a loop itself"
    assert OCREngine._is_better(FULL_TABLE, padded, on_tables=True)
    # Without the flag, the same pair goes the other way — which is the point.
    assert not OCREngine._is_better(FULL_TABLE, padded)


def test_a_looping_retry_never_wins_a_table_comparison():
    """More rows must not buy its way past the repetition check."""
    looping = LOOP + "\n" + FULL_TABLE
    assert repetition_runs(looping) > 1
    assert not OCREngine._is_better(looping, TRUNCATED_TABLE, on_tables=True)


def test_a_failed_page_is_not_repaired(page_png, monkeypatch):
    """A model that errored has nothing to judge; that is what the API-level
    retry is for, and doubling up here would just double the failure."""
    eng, calls = _engine(monkeypatch, [])
    monkeypatch.setattr(eng, "_transcribe",
                        lambda _p: (_ for _ in ()).throw(RuntimeError("ollama down")))
    result, note = eng.ocr_image_repaired(str(page_png), 1, max_retries=0)

    assert not result.success
    assert note == ""
