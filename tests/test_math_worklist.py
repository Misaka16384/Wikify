"""`magi math check` as a worklist, not a wall of text.

Ingestion damages formulas in a handful of recognisable ways, and the one that
matters most — a `$$` nobody closed, swallowing the paragraph after it — parses
as valid LaTeX. These tests pin both the detection and the scoping, because a
maintenance pass that rewrote the concept backups would destroy the copy you
keep in case the pass went wrong.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from magi.kb.validate_math_latex import (
    PROSE_RUN_WORDS,
    collect_issues,
    detect_prose_blocks,
    longest_prose_run,
)


@pytest.fixture
def library(tmp_path):
    ws = tmp_path / "topic"
    (ws / "wiki" / "concepts").mkdir(parents=True)
    (ws / "raw" / "papers").mkdir(parents=True)
    (ws / "scratch" / "concept_backups").mkdir(parents=True)
    (ws / "output").mkdir()
    (ws / "config.yaml").write_text("topic: t\n", encoding="utf-8")

    (ws / "wiki" / "concepts" / "brace.md").write_text(
        "---\ntitle: Brace\n---\n\n"
        "Here $\\mathcal{A}_{\\mathrm{SSB}}^{\\mathrm{diag}}} = 11$ appears.\n",
        encoding="utf-8")
    (ws / "wiki" / "concepts" / "swallowed.md").write_text(
        "---\ntitle: Swallowed\n---\n\nBefore.\n\n$$\nE = mc^2\n\n"
        "The closing pair went missing so this whole paragraph reads as one "
        "enormous formula of single letters.\n\n$$\n\nAfter.\n",
        encoding="utf-8")
    (ws / "wiki" / "concepts" / "clean.md").write_text(
        "---\ntitle: Clean\n---\n\nInline $a_1 + b_2$ and a block:\n\n"
        "$$\n\\begin{aligned}\nx &= y \\\\\nz &= w\n\\end{aligned}\n$$\n",
        encoding="utf-8")
    (ws / "raw" / "papers" / "env.md").write_text(
        "# P\n\n$$\n\\begin{aligned}\n1 & 2\n\\end{pmatrix}\n$$\n", encoding="utf-8")
    # Same defect, in a backup. Must never appear in the worklist — in either
    # place a backup has ever lived. `wiki/concepts/.backup/` is where `magi
    # link` and `magi wiki refactor-concept` write now, and it is inside the
    # scanned tree, so it is the one that would actually break this.
    (ws / "scratch" / "concept_backups" / "brace.md").write_text(
        "Here $\\mathcal{A}_{\\mathrm{SSB}}^{\\mathrm{diag}}} = 11$ appears.\n",
        encoding="utf-8")
    (ws / "wiki" / "concepts" / ".backup" / "link-2026-01-01_000000").mkdir(parents=True)
    (ws / "wiki" / "concepts" / ".backup" / "link-2026-01-01_000000" / "brace.md").write_text(
        "Here $\\mathcal{A}_{\\mathrm{SSB}}^{\\mathrm{diag}}} = 11$ appears.\n",
        encoding="utf-8")
    return ws


def _magi(ws, *args):
    return subprocess.run([sys.executable, "-m", "magi", *args], cwd=ws,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


# --------------------------------------------------------------------------
# the detector pylatexenc does not have
# --------------------------------------------------------------------------

def test_prose_swallowed_by_an_unclosed_block_is_found(library):
    """It parses as valid LaTeX, which is exactly why it survived every check
    that existed before and then rendered as a wall of italic letters."""
    entries = collect_issues(library, use_pdflatex=False)
    prose = [e for e in entries if e["detector"] == "prose"]
    assert prose, "the commonest ingest defect went unreported"
    assert prose[0]["path"] == "wiki/concepts/swallowed.md"
    assert "never closed" in prose[0]["error"]


@pytest.mark.parametrize("body,flagged", [
    (r"\begin{aligned} x &= y \\ z &= w \end{aligned}", False),
    (r"E = mc^2", False),
    # Prose that belongs to the formula does not count against it.
    (r"x = y \text{ for every one of the six values considered here } z", False),
    (r"\sum_i a_i \quad \text{where each index runs over the whole lattice}", False),
    # An actual swallowed sentence.
    ("The closing pair went missing so this paragraph reads as a formula", True),
    (r"a = b. Most importantly the dimension of the ring is finite here", True),
])
def test_prose_detector_tells_formulas_from_paragraphs(body, flagged):
    assert bool(detect_prose_blocks(f"$${body}$$")) is flagged


def test_the_threshold_sits_above_a_single_connective_word():
    """A real library has 113 blocks whose longest run is one word ("where");
    the tail that is genuine contamination starts far above that."""
    assert longest_prose_run(r"x = y \quad where \quad z = w") < PROSE_RUN_WORDS
    assert PROSE_RUN_WORDS >= 4, "so low it would flag ordinary annotated formulas"


# --------------------------------------------------------------------------
# scoping — the part that can destroy data if it is wrong
# --------------------------------------------------------------------------

def test_backups_and_generated_output_stay_out_of_the_worklist(library):
    entries = collect_issues(library, use_pdflatex=False)
    paths = {e["path"] for e in entries}
    assert not any(p.startswith("scratch/") for p in paths), paths
    assert not any(p.startswith("output/") for p in paths), paths
    assert not any(".backup" in p.split("/") for p in paths), paths
    assert "wiki/concepts/brace.md" in paths, "the original was missed"


def test_math_format_does_not_rewrite_the_backups(library):
    """It edits in place with no dry-run, so a backup it reformats is a backup
    that no longer says what the wiki said before the run that made it."""
    backups = [library / "scratch" / "concept_backups" / "brace.md",
               library / "wiki" / "concepts" / ".backup"
               / "link-2026-01-01_000000" / "brace.md"]
    before = [b.read_text(encoding="utf-8") for b in backups]
    res = _magi(library, "math", "format")
    assert res.returncode == 0, res.stderr
    assert [b.read_text(encoding="utf-8") for b in backups] == before


def test_a_valid_card_is_never_flagged(library):
    entries = collect_issues(library, use_pdflatex=False)
    assert not any(e["path"].endswith("clean.md") for e in entries)


# --------------------------------------------------------------------------
# worklist shape
# --------------------------------------------------------------------------

def test_every_entry_is_addressable_and_carries_its_source(library):
    for e in collect_issues(library, use_pdflatex=False):
        assert e["id"] == f"{e['path']}:{e['line']}", "ids must be stable to tick off"
        assert e["tex"], "an entry with no source excerpt cannot be triaged"
        assert e["kind"] in ("block", "inline")
        assert e["confidence"] in ("certain", "likely-macro")
        assert e["collection"] in ("wiki", "raw", "drafts")


def test_a_swallowed_page_does_not_swallow_the_worklist(tmp_path):
    """An unclosed `$$` "spans" a page of prose; quoting all of it would bury
    every other entry."""
    from magi.kb.validate_math_latex import TEX_EXCERPT

    ws = tmp_path / "t"
    (ws / "wiki").mkdir(parents=True)
    (ws / "wiki" / "huge.md").write_text(
        "$$\n" + ("word " * 4000) + "\n$$\n", encoding="utf-8")
    entry = collect_issues(ws, use_pdflatex=False)[0]
    assert entry["tex_clipped"] is True
    assert len(entry["tex"]) <= TEX_EXCERPT + 8


# --------------------------------------------------------------------------
# the CLI surface
# --------------------------------------------------------------------------

def test_check_defaults_to_the_surrounding_workspace(library):
    """Global, like `magi lint` — a maintenance pass is not a per-file chore."""
    res = _magi(library, "math", "check", "--fast")
    assert res.returncode == 1, res.stdout
    assert "wiki/concepts/brace.md" in res.stdout
    assert "magi math format" in res.stdout, "the summary must say what to run next"


def test_json_is_a_worklist(library):
    res = _magi(library, "math", "check", "--fast", "--json")
    payload = json.loads(res.stdout)
    assert payload["count"] == len(payload["issues"]) > 0
    assert payload["detector"]
    assert {"id", "path", "line", "kind", "error", "tex", "confidence"} <= set(payload["issues"][0])


def test_wiki_only_narrows_to_the_compiled_cards(library):
    res = _magi(library, "math", "check", "--fast", "--wiki-only", "--json")
    issues = json.loads(res.stdout)["issues"]
    assert issues
    assert {e["collection"] for e in issues} == {"wiki"}


def test_check_outside_a_workspace_says_so(tmp_path):
    res = _magi(tmp_path, "math", "check", "--fast")
    assert res.returncode != 0
    assert "workspace" in (res.stderr + res.stdout).lower()


def test_lint_points_at_the_repair_route_it_cannot_take_itself(library):
    """Math errors are the one class lint reports and cannot --fix."""
    res = _magi(library, "lint", str(library))
    assert "magi math format" in res.stdout or "magi math format" in res.stderr


def test_the_skill_ships_and_names_the_commands_it_drives():
    from magi.skills_cmd import load_skills

    skill = next((s for s in load_skills() if s.name == "tidy"), None)
    assert skill is not None, "the skill is not in the package"
    body = skill.path.read_text(encoding="utf-8")
    for cmd in ("magi math format", "magi math check --json", "magi ingest crop"):
        assert cmd in body, f"the skill never mentions {cmd}"
    # The two judgment calls the skill exists to carry.
    assert "likely-macro" in body, "must warn that a macro is usually not a typo"
    assert "re-run" in body and "first" in body, (
        "must say to fix the first entry in a file and re-check — one unclosed "
        "$$ shifts every pair after it, so 115 entries can be a dozen edits")
