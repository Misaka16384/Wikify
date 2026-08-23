"""A page that comes back repeating gets read another way, once.

Everything here follows from one measurement: **the loop is not random.** The
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


def test_a_failed_page_is_not_repaired(page_png, monkeypatch):
    """A model that errored has nothing to judge; that is what the API-level
    retry is for, and doubling up here would just double the failure."""
    eng, calls = _engine(monkeypatch, [])
    monkeypatch.setattr(eng, "_transcribe",
                        lambda _p: (_ for _ in ()).throw(RuntimeError("ollama down")))
    result, note = eng.ocr_image_repaired(str(page_png), 1, max_retries=0)

    assert not result.success
    assert note == ""
