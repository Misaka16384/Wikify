"""magi sync — workspace onboarding: three-core status + sync ratio.

The sync ratio is a deterministic workspace-health score, not vibes:

- MELCHIOR (epistemic state / the wiki):
    0.55 · graph freshness (graph.db mtime >= newest wiki/*.md mtime)
  + 0.25 · backlog health  (max(0, 1 - uncompiled/10))
  + 0.20 · claim health    (verified claims / total claims; 1.0 when no
           claims exist yet — absence of claims is not a defect)
- BALTHASAR (work state / Beads):
    0.6 · beads database reachable
  + 0.4 · bd status summary readable
- CASPER (retrieval state / hybrid index):
    0.7 · index freshness (index.db mtime >= newest wiki/*.md mtime)
  + 0.3 · vector coverage (embedded chunks / total chunks)
  Missing index scores 0 — build it with `magi index`.

Ratio = weighted mean over the cores that are applicable. Agents should
treat a low ratio as "restore the workspace before doing research":
every hint printed is a concrete command.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NamedTuple

from magi.core.workspace import find_workspace_root


def _graph_written_at(graph_db: Path) -> float:
    """When the graph was last built, which is not always its own mtime.

    `graph build` runs in WAL mode, and SQLite folds the write-ahead log back
    into the main file only when the *last* connection closes. Anything else
    holding the database open — the Melchior graph tab, `magi graph query` in
    a second terminal — means the build's own close is not the last one, so
    the write sits in `graph.db-wal` and `graph.db`'s mtime never moves.

    Reading freshness from the main file alone therefore called the graph
    stale directly after a build that had just succeeded, and offered
    `magi graph build` as the remedy for having run `magi graph build`.
    Rebuilding did not help; closing the other window did.

    Checkpointing at the end of the build does not fix it — measured, with a
    reader holding a snapshot: PASSIVE copies 0 of 16 frames, FULL and
    TRUNCATE both come back busy. The data is committed and every reader can
    see it; it is only the file's timestamp that is behind. So read the pair.
    """
    newest = graph_db.stat().st_mtime
    wal = graph_db.with_name(graph_db.name + "-wal")
    try:
        if wal.is_file():
            newest = max(newest, wal.stat().st_mtime)
    except OSError:
        pass
    return newest


def _newest_md_mtime(root: Path) -> float:
    """Newest content mtime under root. Excludes _index.md (regenerated
    AFTER graph build by every standard pipeline — counting it would make
    a just-built graph read as stale) and .backup copies."""
    return _scan_wiki(root).newest


def _newest_threads_mtime(topic: Path) -> float:
    """Newest note under `threads/`, which is on the graph too.

    A proposition is a node with its status as category and its `depends_on`
    as edges (`test_graph_threads.py`), so a new note or a flipped status is a
    graph change. Freshness used to be measured against `wiki/` alone, and a
    project that opened three propositions and compiled nothing read as
    "graph fresh" while the map showed none of them — the WebUI's canvas
    reads `graph.db`, and nothing rebuilt it (2026-09-03).
    """
    newest = 0.0
    directory = topic / "threads"
    if not directory.is_dir():
        return newest
    for note in directory.glob("*.md"):
        try:
            newest = max(newest, note.stat().st_mtime)
        except OSError:
            continue
    return newest


def graph_stale(topic: Path, scan: "_WikiScan | None" = None) -> bool:
    """Whether `output/graph.db` is older than something it is a map of.

    Missing counts as stale when there is anything to map. One answer for
    `magi sync`, the dashboard and the graph endpoints, so they cannot
    disagree about the same file.
    """
    topic = Path(topic)
    graph_db = topic / "output" / "graph.db"
    scan = scan if scan is not None else _scan_wiki(topic / "wiki")
    newest = max(scan.newest, _newest_threads_mtime(topic))
    if not graph_db.is_file():
        return bool(newest)
    try:
        return _graph_written_at(graph_db) < newest
    except OSError:
        return False


class _WikiScan(NamedTuple):
    """One walk of a wiki tree, answering every question the report asks of it."""
    newest: float
    counts: dict[str, int]      # first path segment under root -> card count


def _scan_wiki(root: Path) -> _WikiScan:
    """Walk a wiki tree once.

    The report used to ask this tree four separate questions — newest mtime,
    and a card count for each of concepts/references/topics — and walked it
    once per question. On a large library that is four full rglobs for data a
    single pass already has in hand.
    """
    newest = 0.0
    counts: dict[str, int] = {}
    if not root.is_dir():
        return _WikiScan(0.0, counts)
    for p in root.rglob("*.md"):
        if p.name == "_index.md" or ".backup" in p.parts:
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:      # pragma: no cover - rglob results are under root
            continue
        if len(rel.parts) > 1:
            counts[rel.parts[0]] = counts.get(rel.parts[0], 0) + 1
        try:
            newest = max(newest, p.stat().st_mtime)
        except OSError:
            continue
    return _WikiScan(newest, counts)


def melchior_status(topic: Path, scan: _WikiScan | None = None) -> dict:
    wiki = topic / "wiki"
    graph_db = topic / "output" / "graph.db"
    # `scan` lets a caller that needs several cores walk the tree once and
    # hand the result to each; omitted, this behaves exactly as before.
    scan = scan if scan is not None else _scan_wiki(wiki)
    concepts = scan.counts.get("concepts", 0)
    references = scan.counts.get("references", 0)
    topics_n = scan.counts.get("topics", 0)

    # `threads/` counts too: notes are graph nodes, and a project whose only
    # content so far is three propositions has a graph to be stale about.
    newest = max(scan.newest, _newest_threads_mtime(topic))
    if not graph_db.is_file():
        graph_state = "missing" if newest else "empty-wiki"
        # missing-with-content scores like stale (both mean "run magi graph
        # build") so compiling the first card never drops the sync ratio
        freshness = 0.3 if newest else 1.0
    elif not graph_stale(topic, scan):
        graph_state, freshness = "fresh", 1.0
    else:
        graph_state, freshness = "stale", 0.3

    try:
        from magi.kb.detect_uncompiled import find_uncompiled

        backlog = len(find_uncompiled(topic))
    except Exception:
        backlog = 0
    backlog_health = max(0.0, 1.0 - backlog / 10.0)

    claims_total = claims_verified = 0
    if graph_db.is_file():
        import sqlite3

        # `closing`, not a bare close at the end of the try: the close used to
        # be the last statement inside it, so a query that raised — "database
        # is locked" is the realistic one, since `magi index` holds a write
        # lock and this is polled by a dashboard — jumped straight to the
        # except and left the handle open. (`with sqlite3.connect(...)` would
        # not help: that context manager commits or rolls back a transaction
        # and never closes the connection.)
        from contextlib import closing

        try:
            with closing(sqlite3.connect(graph_db)) as conn:
                row = conn.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN status IN ('verified','web-verified') "
                    "THEN 1 ELSE 0 END) FROM claims").fetchone()
                claims_total, claims_verified = row[0] or 0, row[1] or 0
        except sqlite3.Error:
            pass
    claim_health = (claims_verified / claims_total) if claims_total else 1.0

    return {
        "concepts": concepts,
        "references": references,
        "topics": topics_n,
        "graph": graph_state,
        "backlog": backlog,
        "claims": claims_total,
        "claims_verified": claims_verified,
        "score": round(0.55 * freshness + 0.25 * backlog_health + 0.20 * claim_health, 3),
    }


def casper_status(topic: Path, scan: _WikiScan | None = None) -> dict:
    idx = topic / "output" / "index.db"
    if not idx.is_file():
        return {"state": "missing", "chunks": 0, "vectors": 0, "score": 0.0}
    import sqlite3
    from contextlib import closing

    newest = scan.newest if scan is not None else _newest_md_mtime(topic / "wiki")
    freshness = 1.0 if idx.stat().st_mtime >= newest else 0.3
    chunks = vectors = 0
    readable = True
    try:
        # A read must never wait on a writer: `magi index` holds a write lock
        # for the length of its run, and the dashboard polls this. Without a
        # timeout SQLite raises immediately; with a long one the UI would hang
        # instead. Two seconds is long enough to ride out a commit.
        with closing(sqlite3.connect(idx, timeout=2.0)) as conn:
            chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            # count via vec0's shadow table — readable without the sqlite-vec
            # extension loaded (the virtual table itself is not)
            has_vec = conn.execute(
                "SELECT name FROM sqlite_master WHERE name='chunks_vec_rowids'").fetchone()
            if has_vec:
                vectors = conn.execute("SELECT COUNT(*) FROM chunks_vec_rowids").fetchone()[0]
    except sqlite3.DatabaseError:
        # Freshness is an mtime comparison, so a file that is not a database
        # at all — but was written recently — scored as `fresh · 0 chunks`.
        # The one signal pointing at the broken file was the healthiest in the
        # display, and `magi search` crashed on it a moment later.
        readable = False
    except sqlite3.Error:
        pass
    coverage = (vectors / chunks) if chunks else 0.0
    if not readable:
        return {"state": "unreadable", "chunks": 0, "vectors": 0, "score": 0.0}
    state = "fresh" if freshness == 1.0 else "stale"
    return {"state": state, "chunks": chunks, "vectors": vectors,
            "score": round(0.7 * freshness + 0.3 * coverage, 3)}


class _RadarOff(Exception):
    """Sentinel: the radar is switched off, so its whole hint block is skipped.

    Deliberately not StopIteration — PEP 479 turns that into a RuntimeError
    inside a generator, and this block is one refactor away from being in one.
    """


def balthasar_status(topic: Path | None) -> dict:
    """Intent: what this project is trying to find out, and what it owes.

    v2 moves this core off the task tracker (design-v2 §14). Beads holds
    mechanical work — a compile backlog, a reading queue — and a project can
    have none of it while being in the middle of everything. What Balthasar
    now measures is whether the research state is *legible*: how many lines
    are running, how much is open, what is waiting on a person, and how much
    happened that nobody wrote down.

    The score is bookkeeping cleanliness, not progress. A project with six
    open propositions and no debt is perfectly healthy; one with two and three
    unexplained statuses is not, because every projection over it is wrong.
    Work waiting on a person is not counted against anything — the queue
    existing is the system working.

    A workspace with no `threads/` yet keeps the old beads-derived score, so
    libraries that predate v2 do not suddenly read zero.
    """
    from magi.pm import bd_available, bd_status_summary, find_beads_root

    start = topic or Path.cwd()
    root = find_beads_root(start) if bd_available() else None
    summary = bd_status_summary(root) if root else None
    beads = {
        "bd_installed": bd_available(),
        "beads_root": str(root) if root else None,
        "ready": (summary or {}).get("ready_issues"),
        "in_progress": (summary or {}).get("in_progress_issues"),
        "blocked": (summary or {}).get("blocked_issues"),
        "open": (summary or {}).get("open_issues"),
    }

    research = _research_status(topic)
    if research is None:
        beads["score"] = round((0.6 if root else 0.0) + (0.4 if summary else 0.0), 3)
        beads.update({"lines": None, "open_propositions": None,
                      "waiting": None, "debt": None})
        return beads

    beads.update(research)
    return beads


def _research_status(topic: Path | None):
    """Threads-derived intent numbers, or `None` when there is no `threads/`."""
    if topic is None:
        return None
    if not (Path(topic) / "threads").is_dir():
        return None
    try:
        from magi import state as state_mod

        # `loaded`, not `load`: `load`'s defaults are the library's, and the
        # workspace's own `wip_limit` / `stall_days` / `coaching` live in
        # config.yaml. Reading them here is what stops `magi sync` reporting a
        # smaller `waiting` count than `magi next` for the same line.
        projection = state_mod.loaded(topic)
    except Exception:  # noqa: BLE001 — a broken note must not take sync down
        return None

    notes = len(projection.notes)
    if not notes:
        # A scaffolded but empty `threads/` has nothing to be legible about.
        # Scoring it zero would call a fresh workspace unhealthy for having
        # asked no questions yet; the beads-derived score is the honest
        # fallback until there is research state to measure.
        return None

    debt = len(projection.debt)
    return {
        "lines": len(projection.lines),
        "open_propositions": sum(view.open_count for view in projection.lines),
        "waiting": len(projection.queue),
        "debt": debt,
        "score": round(max(0.0, 1.0 - debt / notes), 3),
    }


def _skills_hint(topic: Path | None, hint) -> None:
    """Are the skills in this workspace the ones this `magi` would write?

    A skill file is documentation of the CLI's own command surface, so a copy
    left behind by an older magi teaches commands that no longer exist. That
    is not hypothetical: a plugin pinned at an old snapshot served v1 skills
    for four months, and nothing ever said so — the drift is silent because
    the stale file is perfectly valid, just wrong.

    `skills_cmd` already computes this exactly, by comparing bytes against what
    the current package would write rather than trusting a version stamp. What
    was missing is that nothing running automatically ever asked. This is that
    question, asked once per `magi sync`.

    Names, not a count. `magi skills where` reports "1 outdated" and a bare
    number is dismissible — it was dismissed, and the file behind it turned out
    to be a v1 skill that had survived two cleanups.

    A file with no `origin: magi` is reported separately: `magi install` treats
    an unmarked file as the person's own and refuses to overwrite it, so
    telling them to re-run install would be advice that cannot work.
    """
    if topic is None:
        return
    try:
        from magi import skills_cmd
    except Exception:
        return
    try:
        skills = skills_cmd.load_skills()
        stale, frozen = [], []
        for host in skills_cmd.detected_hosts():
            for target in host.drops:
                dest = skills_cmd.target_dir(target, "project", topic)
                if dest is None:
                    continue
                for sk in skills:
                    path, text = skills_cmd.files_for(sk, target, dest)[0]
                    if not path.exists():
                        continue
                    current = path.read_text(encoding="utf-8", errors="replace")
                    if current == text:
                        continue
                    (stale if skills_cmd.ORIGIN_MARK in current else frozen).append(
                        path.relative_to(topic).as_posix())
    except Exception:
        # Never let a convenience check take `sync` down: it is what the
        # session-start hook and `--close` both run.
        return

    if stale:
        hint("skills-stale",
             f"magi install   # {len(stale)} skill file(s) were written by an "
             f"older magi: {', '.join(sorted(stale)[:3])}"
             + (" ..." if len(stale) > 3 else ""),
             files=sorted(stale))
    if frozen:
        hint("skills-unmanaged",
             f"{len(frozen)} skill file(s) differ from this magi and carry no "
             f"'{skills_cmd.ORIGIN_MARK}', so install will not replace them: "
             f"{', '.join(sorted(frozen)[:3])}"
             + (" ..." if len(frozen) > 3 else "")
             + " — delete one to have it rewritten",
             files=sorted(frozen))


def build_report(cwd: Path | None = None) -> dict:
    base = cwd or Path.cwd()
    topic = find_workspace_root(base)

    cores: dict[str, dict] = {}
    weights: dict[str, float] = {}
    hints: list[str] = []
    hints_structured: list[dict] = []

    # Defined here rather than inline so the walk is skippable and testable on
    # its own; see `_skills_hint` for why this check exists at all.
    def _hint(code: str, text: str, **params) -> None:
        # Dual-track contract: `hints` (human text, frozen shape) stays exactly
        # as before; `hints_structured` adds a machine-readable code so UI/MCP
        # consumers map actions without parsing prose.
        hints.append(text)
        hints_structured.append({"code": code, "text": text, "params": params})

    # One walk of wiki/, shared by melchior (counts + graph freshness) and
    # casper (index freshness), instead of four.
    scan = _scan_wiki(topic / "wiki") if topic else None

    try:
        from magi.features import feature_enabled

        tasks_on = feature_enabled("tasks")
        radar_on = feature_enabled("radar")
    except Exception:
        # An unreadable settings file must not turn features off — absent has
        # always meant on, and a read error is less information than absent.
        tasks_on = radar_on = True

    if topic:
        m = melchior_status(topic, scan)
        cores["melchior"] = m
        weights["melchior"] = 1.0
        if m["graph"] in ("missing", "stale"):
            _hint("graph-stale", "magi graph build   # refresh the knowledge graph")
        if m["backlog"] > 0:
            # The step this report never named. Once a source lands in raw/,
            # the only thing the dashboard said was "track them as tasks" —
            # so a user who ingested 18 papers through the WebUI was told to
            # file 18 issues about them and never told to compile any, and
            # `wiki/concepts/` stayed empty. Compiling is the work; tracking
            # it is bookkeeping, and it comes second.
            _hint("compile-pending",
                  f"{m['backlog']} source(s) in raw/ are not compiled yet — run the "
                  "compile skill to turn them into reference cards",
                  backlog=m["backlog"])
            # Only worth saying when the task store is something this machine
            # actually uses. With tasks switched off this told people to run
            # `magi pm backlog-sync`, which needs a beads store they had
            # deliberately not set up.
            if tasks_on:
                _hint("backlog-untracked",
                      "magi pm backlog-sync (idempotent) && bd ready   # ensure uncompiled sources are tracked",
                      backlog=m["backlog"])
        if m["concepts"] == 0 and m["references"] == 0 and m["backlog"] == 0:
            _hint("ingest-start",
                  "drop sources in inbox/ and run the ingest skill to start filling this project")
        if m.get("claims") and m["claims_verified"] < m["claims"]:
            n_unv = m["claims"] - m["claims_verified"]
            _hint("claims-unverified",
                  f"claims: {n_unv} unverified — inspect with magi graph query "
                  "\"SELECT text, status FROM claims WHERE status NOT IN ('verified','web-verified')\"",
                  unverified=n_unv)

    if not tasks_on:
        # Not a core that is failing: a core that was switched off. It carries
        # no weight, so the sync ratio is out of the two that are running
        # rather than permanently capped at two thirds.
        cores["balthasar"] = {"state": "disabled", "note": "turned off", "score": None}
    else:
        b = balthasar_status(topic)
        cores["balthasar"] = b
        weights["balthasar"] = 1.0
        if not b["bd_installed"]:
            _hint("beads-missing",
                  "install beads (bd) for work-state tracking: https://github.com/gastownhall/beads")
        elif not b["beads_root"] and topic is not None:
            # Only inside a workspace. Outside one, the missing thing is the
            # workspace, and offering a workspace-scoped command as the first
            # suggestion sends somebody to set up task tracking for a project
            # they have not made yet.
            # Named, not just offered. This one hands the directory to
            # another program that git-inits and commits under the person's
            # own identity, and a one-line nudge that does not say so is how
            # somebody ends up with a commit they did not make.
            _hint("pm-uninit",
                  "magi pm init   # optional task tracking; hands this "
                  "directory to bd, which git-inits and commits")
        elif (b["ready"] or 0) > 0:
            _hint("bd-ready", "bd ready   # there is actionable work", ready=b["ready"])

    if topic:
        c = casper_status(topic, scan)
        cores["casper"] = c
        weights["casper"] = 1.0
        if c["state"] == "missing":
            _hint("index-missing", "magi index   # build the retrieval index")
        elif c["state"] == "unreadable":
            _hint("index-unreadable",
                  "magi index   # output/index.db is not a database; rebuild it")
        elif c["state"] == "stale":
            _hint("index-stale", "magi index   # refresh the retrieval index")

        _skills_hint(topic, _hint)
        # Radar off means no radar hints at all — not a nag about a harvest
        # that is deliberately not happening.
        try:
            if not radar_on:
                raise _RadarOff
            from magi.core.config_loader import get as cfg_get, load_config
            from magi.radar import harvest_age_days, pending_names, scan_reports

            reports = scan_reports(topic)
            # Only nag about staleness once radar is actually in use — a
            # workspace that has never harvested is not overdue, it is unused.
            age = harvest_age_days(topic)
            window = int(cfg_get(load_config(start=topic), "radar.days", 7) or 7)
            if age is not None and age > max(window, 1) * 2:
                _hint("radar-harvest-overdue",
                      f"radar: last harvest was {age}d ago (window is {window}d) — "
                      f"run 'magi radar harvest', or check the scheduled task",
                      days=age, window=window)
        except Exception:
            reports = []
            pending_names = None
        if reports and pending_names:
            pending = len(pending_names(reports, "digest"))
            gap_pending = len(pending_names(reports, "citation-gap"))
            if pending:
                _hint("radar-digests-pending",
                      f"radar: {pending} digest(s) pending — run the radar_review skill",
                      pending=pending)
            if gap_pending:
                _hint("radar-gaps-pending",
                      f"radar: {gap_pending} citation-gap report(s) pending — run the radar_review skill",
                      pending=gap_pending)
    else:
        cores["casper"] = {"state": "offline", "note": "no project", "score": None}
    # No workspace -> no ratio: reporting "100% in sync" from a random
    # directory would invert the metric's meaning.
    if topic:
        scored = [(weights[k], cores[k]["score"]) for k in weights if cores[k].get("score") is not None]
        total_w = sum(w for w, _ in scored)
        ratio = round(100.0 * sum(w * s for w, s in scored) / total_w, 1) if total_w else None
    else:
        ratio = None

    return {
        "workspace": str(topic) if topic else None,
        "sync_ratio": ratio,
        "cores": cores,
        "hints": hints,
        "hints_structured": hints_structured,
    }


def _fmt(v, suffix: str = "") -> str:
    return f"{v}{suffix}" if v is not None else "?"


# `magi sync` already works out what is missing; --fix lets it act on the
# subset that is deterministic and safe to re-run. Everything else (installing
# Beads, ingesting sources, reviewing a digest) stays a human/agent decision
# and is only reported.
FIXABLE = {
    "graph-stale": (["graph", "build"], "refresh the knowledge graph"),
    "index-missing": (["index"], "build the retrieval index"),
    "index-stale": (["index"], "refresh the retrieval index"),
    "backlog-untracked": (["pm", "backlog-sync"], "track uncompiled sources as issues"),
    "pm-uninit": (["pm", "init"], "initialize the task store (creates .beads/)"),
}

#: The order repairs run in. The report emits hints core by core — melchior
#: first, then balthasar — and `run_fixes` used to follow that, so
#: `backlog-untracked` was always attempted before `pm-uninit`. But
#: `magi pm backlog-sync` exits 1 when there is no beads store, which means
#: `magi sync --fix` failed by construction on the one situation it exists to
#: repair: a fresh workspace with `bd` installed and not yet initialised. It
#: reported "1 failed", synced nothing, and worked on the second run.
#:
#: A code missing from this list still runs, after the ones named here — the
#: list is about dependencies, not about being exhaustive.
FIX_ORDER = (
    "pm-uninit",          # creates .beads/ — backlog-sync is useless without it
    "graph-stale",
    "index-missing",
    "index-stale",
    "backlog-untracked",  # needs the store pm-uninit makes
)


def run_fixes(report: dict, dry_run: bool = False, cwd=None) -> tuple[int, int]:
    """Run the deterministic repairs the report asked for. Returns (ran, failed).

    `cwd` is where they run, and it has to be the workspace the *report* was
    about. Every repair here is a `magi` subcommand that finds its workspace by
    walking up from the directory it starts in, so leaving this unset made
    `magi sync --topic-dir X --fix` describe X and then rebuild the graph of
    whatever directory the person happened to be standing in — a read bug in
    the report path, and a write bug here.
    """
    import subprocess  # noqa: F401  (kept: other helpers below use it)

    from .core import trace

    def _rank(hint: dict) -> int:
        code = hint.get("code")
        return FIX_ORDER.index(code) if code in FIX_ORDER else len(FIX_ORDER)

    seen: set[tuple[str, ...]] = set()
    ran = failed = 0
    for hint in sorted(report.get("hints_structured", []), key=_rank):
        entry = FIXABLE.get(hint.get("code"))
        if entry is None:
            continue
        cmd, why = entry
        key = tuple(cmd)
        if key in seen:
            continue
        seen.add(key)
        pretty = "magi " + " ".join(cmd)
        if dry_run:
            print(f"  would run {pretty:<26} # {why}")
            ran += 1
            continue
        print(f"  {pretty:<26} # {why}")
        # An empty pipe for stdin, not DEVNULL: capturing a child's output
        # takes away its ability to ask, so it must not be left believing
        # someone can answer. `magi pm init` confirms on a tty and inherited
        # ours, so its question went to a pipe nobody reads and its `input()`
        # got EOF — it declined itself, and `pm backlog-sync` then failed for
        # want of the store it would have made.
        #
        # DEVNULL does not fix that on Windows: it opens `NUL`, which is a
        # character device, so `isatty()` still answers True. An empty pipe
        # answers False on both platforms, which is the non-tty path
        # `_agreed_to_hand_over` documents — print the notice and continue.
        proc = trace.run([sys.executable, "-m", "magi", *cmd],
                         cwd=str(cwd) if cwd else None)
        ran += 1
        out = (proc.stdout or proc.stderr or "").strip().splitlines()
        for line in out[-2:]:
            print(f"      {line}")
        if proc.returncode != 0:
            failed += 1
            print(f"      exit {proc.returncode}")
    return ran, failed


def _close(args) -> int:
    """`magi sync --close` — the gate between a session and its end.

    Kept out of the report path on purpose: everything else `sync` prints is a
    description of the library, and this is the one thing that can refuse.
    """
    from magi import state as state_mod
    from magi.core.workspace import find_workspace_root

    root = Path(args.topic_dir).resolve() if getattr(args, "topic_dir", None) \
        else find_workspace_root()
    if root is None:
        message = "no project found (run inside one, or pass --project-dir)"
        if args.hook:
            # Nothing to gate, so nothing to say: a stop hook that reports an
            # error for being run outside a workspace blocks every session
            # started anywhere else.
            print(json.dumps({}, ensure_ascii=False))
            return 0
        if args.json:
            print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
            return 1
        print(message, file=sys.stderr)
        return 1

    window = args.window if args.window is not None else state_mod.CLOSE_WINDOW_HOURS
    report = state_mod.close(root, window_hours=window)

    if args.hook:
        print(json.dumps(state_mod.hook_payload(report, args.dialect),
                         ensure_ascii=False))
        # A hook that exits non-zero is a hook that looks broken; the verdict
        # travels in the payload, not in the status code.
        return 0
    if args.json:
        print(json.dumps({
            "ok": report.ok,
            "blocking": [{"slug": item.slug, "why": item.why} for item in report.blocking],
            "older": [{"slug": item.slug, "why": item.why} for item in report.older],
            "conflicts": report.conflicts,
            "unreviewed": report.unreviewed,
            "weakly_reviewed": report.weakly_reviewed,
            "restating": report.restating,
            "outside": [{"slug": slug, "why": why} for slug, why in report.outside],
            "handoff": report.handoff,
            "map": report.map_path,
        }, ensure_ascii=False))
        return 0 if report.ok else 1

    print(state_mod.render_close(report))
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi sync", description="Project onboarding: sync ratio + three-core status")
    parser.add_argument("--project-dir", "--topic-dir", dest="topic_dir",
                        help="Project directory (default: discovered from cwd)")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--fix", action="store_true",
                        help="Run the repairs this report suggests (graph build, index, "
                             "backlog sync, pm init) and report the rest.")
    parser.add_argument("--dry-run", action="store_true",
                        help="With --fix: show what would run, change nothing.")
    parser.add_argument("--close", action="store_true",
                        help="End-of-session gate: refuse while work has happened "
                             "that nobody wrote down. Also settles contended statuses "
                             "and rewrites output/MAP.md.")
    parser.add_argument("--window", type=int, default=None,
                        help="With --close: hours of history that count as this "
                             "session's work (default 12). Older debt is listed, "
                             "not blocking.")
    parser.add_argument("--dialect", default="claude",
                        choices=("claude", "antigravity"),
                        help="With --hook: whose vocabulary the refusal is "
                             "spelled in. Antigravity blocks a stop with "
                             "decision:continue where the others say block.")
    parser.add_argument("--hook", action="store_true",
                        help="With --close: emit the JSON a host's stop hook reads "
                             "instead of a report.")
    args = parser.parse_args(argv)

    if args.close:
        return _close(args)

    # `--topic-dir` has to reach the report as well as the gate. It reached
    # only the gate for one commit, which meant `magi sync --topic-dir X`
    # answered about the directory you were standing in and said "no workspace
    # detected" while pointing at a real one.
    here = Path(args.topic_dir).resolve() if args.topic_dir else None
    report = build_report(here)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    ratio = report["sync_ratio"]
    if ratio is not None:
        header = f"MAGI SYSTEM ONLINE — sync ratio {ratio}%"
    else:
        header = "MAGI SYSTEM — no project detected"
    print(header)
    if report["workspace"]:
        m = report["cores"]["melchior"]
        claims_part = (f" · claims {m['claims_verified']}/{m['claims']} verified"
                       if m.get("claims") else "")
        print(f"|- MELCHIOR  (knowledge)  {m['concepts']} concepts · {m['references']} refs · graph {m['graph']} · backlog {m['backlog']}{claims_part}")
    else:
        print("|- MELCHIOR  (knowledge)  no project here — run 'magi init' in an empty directory")
    b = report["cores"]["balthasar"]
    if b.get("state") == "disabled":
        print("|- BALTHASAR (intent)     disabled (task tracking off — "
              "'magi setup --full' to enable)")
    elif b.get("lines") is not None:
        debt_part = f" · {b['debt']} unrecorded" if b.get("debt") else ""
        lines_word = "line" if b['lines'] == 1 else "lines"
        print(f"|- BALTHASAR (intent)     {b['lines']} {lines_word} · {b['open_propositions']} open "
              f"· {b['waiting']} waiting on you{debt_part}")
    elif b.get("beads_root"):
        print(f"|- BALTHASAR (intent)     {_fmt(b['ready'])} ready · {_fmt(b['in_progress'])} in progress · {_fmt(b['blocked'])} blocked")
    else:
        print("|- BALTHASAR (intent)     beads offline")
    c = report["cores"]["casper"]
    if c.get("score") is not None:
        print(f"`- CASPER    (retrieval)  index {c['state']} · {c['chunks']} chunks · vectors {c['vectors']}/{c['chunks']}")
    else:
        print("`- CASPER    (retrieval)  offline")
    for h in report["hints"]:
        print(f"  -> {h}")

    if not args.fix:
        return 0

    fixable = [h for h in report.get("hints_structured", []) if h.get("code") in FIXABLE]
    manual = [h for h in report.get("hints_structured", []) if h.get("code") not in FIXABLE]
    if not fixable:
        print("\nnothing to fix automatically.")
    else:
        print("\nfixing:" if not args.dry_run else "\nwould fix:")
        ran, failed = run_fixes(report, dry_run=args.dry_run, cwd=here)
        if args.dry_run:
            return 0
        after = build_report(here)
        before_ratio, after_ratio = report["sync_ratio"], after["sync_ratio"]
        arrow = f"{before_ratio}% -> {after_ratio}%" if after_ratio is not None else "—"
        print(f"\nran {ran} step(s)" + (f", {failed} failed" if failed else "") + f"; sync ratio {arrow}")
        report = after
        manual = [h for h in after.get("hints_structured", []) if h.get("code") not in FIXABLE]

    if manual:
        print("\nstill needs you:")
        for h in manual:
            print(f"  -> {h['text']}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())