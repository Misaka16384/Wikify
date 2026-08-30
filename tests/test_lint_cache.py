"""What `magi lint` is allowed to keep between runs.

The cache exists to skip the checks, not to hold a second copy of the library.
It used to store `frontmatter` + `body` + `raw_text` for every schema-checked
file, which made `output/.lint_cache.json` about twice the size of the corpus
it described — loaded whole and rewritten whole on every run, a report-only
run included. Measured on 300 files: 1.69MB of cache for 797KB of notes,
bought for roughly four hundredths of a second.

Two things are pinned here. That the file stays small, because the reason it
grew is that nothing said it shouldn't. And that a warm run still agrees with
a cold one, because the text now comes off disk on the fast path and a body
assembled differently from the way `read_document` assembles it would be a
silent difference between the first run and the second.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "p"
    subprocess.run([sys.executable, "-m", "magi", "init", "--project-dir", str(root),
                    "--name", "T"], capture_output=True, text=True, check=True)
    concepts = root / "wiki" / "concepts"
    concepts.mkdir(parents=True, exist_ok=True)
    filler = "Prose about the boundary condition and the transport gap. " * 30
    for i in range(12):
        (concepts / f"c{i:02d}.md").write_text(
            f"---\ntitle: Concept {i}\ntags: [alpha]\n"
            f"created: 2026-01-01\nupdated: 2026-01-01\n---\n\n"
            f"# Concept {i}\n\nSee [[c{(i + 1) % 12:02d}]].\n\n{filler}\n",
            encoding="utf-8")
    return root


def _lint(root):
    return subprocess.run([sys.executable, "-m", "magi", "lint", str(root)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def test_the_cache_does_not_keep_a_second_copy_of_the_library(library):
    """Frontmatter is small and expensive to parse; body and raw_text are the
    bulk and cheap to recover. Keeping the bulk made the cache larger than the
    notes, and every run paid to parse and re-serialise all of it."""
    _lint(library)
    cache_path = library / "output" / ".lint_cache.json"
    assert cache_path.is_file(), "the lint cache was not written"

    entries = json.loads(cache_path.read_text(encoding="utf-8"))["files"]
    assert entries, "nothing was cached, so this test proves nothing"
    for rel, entry in entries.items():
        assert "body" not in entry and "raw_text" not in entry, (
            f"{rel} carries the file's text in the cache; that made "
            "output/.lint_cache.json twice the size of the corpus")

    corpus = sum(f.stat().st_size for f in (library / "wiki").rglob("*.md"))
    assert cache_path.stat().st_size < corpus, (
        f"the cache ({cache_path.stat().st_size}B) is bigger than the notes "
        f"it describes ({corpus}B)")


def test_a_warm_run_says_what_the_cold_run_said(library):
    """The text now comes off disk on the cache-hit path. A body assembled
    differently from the way `read_document` assembles it would show up as a
    second run disagreeing with the first — which is the failure a cache is
    supposed to make impossible."""
    cold = _lint(library)
    warm = _lint(library)

    assert cold.returncode == warm.returncode
    assert cold.stdout == warm.stdout, "the second run reported something else"


def test_a_file_edited_between_runs_is_read_again(library):
    """Cheap insurance that the fast path is keyed on the file and not only on
    its presence in the cache."""
    _lint(library)
    broken = library / "wiki" / "concepts" / "c00.md"
    broken.write_text("no frontmatter at all\n", encoding="utf-8")

    after = _lint(library)

    assert "frontmatter" in (after.stdout + after.stderr).lower(), (
        "an edited file was served from the cache")
