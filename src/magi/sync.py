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

from magi.core.workspace import find_hub_root, find_workspace_root


def _newest_md_mtime(root: Path) -> float:
    """Newest content mtime under root. Excludes _index.md (regenerated
    AFTER graph build by every standard pipeline — counting it would make
    a just-built graph read as stale) and .backup copies."""
    return _scan_wiki(root).newest


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


def _hub_topics(hub: Path) -> list[str]:
    """Topic slugs registered at a hub: wikis.json 'wikis' keys, falling
    back to directories under topics/ (excluding .archive)."""
    try:
        data = json.loads((hub / "wikis.json").read_text(encoding="utf-8"))
        slugs = sorted((data.get("wikis") or {}).keys())
        if slugs:
            return slugs
    except (OSError, ValueError):
        pass
    topics_dir = hub / "topics"
    if topics_dir.is_dir():
        return sorted(p.name for p in topics_dir.iterdir()
                      if p.is_dir() and p.name != ".archive")
    return []


def melchior_status(topic: Path, scan: _WikiScan | None = None) -> dict:
    wiki = topic / "wiki"
    graph_db = topic / "output" / "graph.db"
    # `scan` lets a caller that needs several cores walk the tree once and
    # hand the result to each; omitted, this behaves exactly as before.
    scan = scan if scan is not None else _scan_wiki(wiki)
    concepts = scan.counts.get("concepts", 0)
    references = scan.counts.get("references", 0)
    topics_n = scan.counts.get("topics", 0)

    newest = scan.newest
    if not graph_db.is_file():
        graph_state = "missing" if newest else "empty-wiki"
        # missing-with-content scores like stale (both mean "run magi graph
        # build") so compiling the first card never drops the sync ratio
        freshness = 0.3 if newest else 1.0
    elif graph_db.stat().st_mtime >= newest:
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

        try:
            conn = sqlite3.connect(graph_db)
            row = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN status IN ('verified','web-verified') "
                "THEN 1 ELSE 0 END) FROM claims").fetchone()
            claims_total, claims_verified = row[0] or 0, row[1] or 0
            conn.close()
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

    newest = scan.newest if scan is not None else _newest_md_mtime(topic / "wiki")
    freshness = 1.0 if idx.stat().st_mtime >= newest else 0.3
    chunks = vectors = 0
    try:
        # A read must never wait on a writer: `magi index` holds a write lock
        # for the length of its run, and the dashboard polls this. Without a
        # timeout SQLite raises immediately; with a long one the UI would hang
        # instead. Two seconds is long enough to ride out a commit.
        conn = sqlite3.connect(idx, timeout=2.0)
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        # count via vec0's shadow table — readable without the sqlite-vec
        # extension loaded (the virtual table itself is not)
        has_vec = conn.execute(
            "SELECT name FROM sqlite_master WHERE name='chunks_vec_rowids'").fetchone()
        if has_vec:
            vectors = conn.execute("SELECT COUNT(*) FROM chunks_vec_rowids").fetchone()[0]
        conn.close()
    except sqlite3.Error:
        pass
    coverage = (vectors / chunks) if chunks else 0.0
    state = "fresh" if freshness == 1.0 else "stale"
    return {"state": state, "chunks": chunks, "vectors": vectors,
            "score": round(0.7 * freshness + 0.3 * coverage, 3)}


def balthasar_status(topic: Path | None) -> dict:
    from magi.pm import bd_available, bd_status_summary, find_beads_root

    start = topic or Path.cwd()
    root = find_beads_root(start) if bd_available() else None
    summary = bd_status_summary(root) if root else None
    score = (0.6 if root else 0.0) + (0.4 if summary else 0.0)
    return {
        "bd_installed": bd_available(),
        "beads_root": str(root) if root else None,
        "ready": (summary or {}).get("ready_issues"),
        "in_progress": (summary or {}).get("in_progress_issues"),
        "blocked": (summary or {}).get("blocked_issues"),
        "open": (summary or {}).get("open_issues"),
        "score": round(score, 3),
    }


def build_report(cwd: Path | None = None) -> dict:
    base = cwd or Path.cwd()
    topic = find_workspace_root(base)
    hub = find_hub_root(base)

    cores: dict[str, dict] = {}
    weights: dict[str, float] = {}
    hints: list[str] = []
    hints_structured: list[dict] = []

    def _hint(code: str, text: str, **params) -> None:
        # Dual-track contract: `hints` (human text, frozen shape) stays exactly
        # as before; `hints_structured` adds a machine-readable code so UI/MCP
        # consumers map actions without parsing prose.
        hints.append(text)
        hints_structured.append({"code": code, "text": text, "params": params})

    # One walk of wiki/, shared by melchior (counts + graph freshness) and
    # casper (index freshness), instead of four.
    scan = _scan_wiki(topic / "wiki") if topic else None

    if topic:
        m = melchior_status(topic, scan)
        cores["melchior"] = m
        weights["melchior"] = 1.0
        if m["graph"] in ("missing", "stale"):
            _hint("graph-stale", "magi graph build   # refresh the knowledge graph")
        if m["backlog"] > 0:
            _hint("backlog-untracked",
                  "magi pm backlog-sync (idempotent) && bd ready   # ensure uncompiled sources are tracked",
                  backlog=m["backlog"])
        if m["concepts"] == 0 and m["references"] == 0 and m["backlog"] == 0:
            _hint("ingest-start",
                  "drop sources in inbox/ and run the wiki_ingest skill to start building the library")
        if m.get("claims") and m["claims_verified"] < m["claims"]:
            n_unv = m["claims"] - m["claims_verified"]
            _hint("claims-unverified",
                  f"claims: {n_unv} unverified — inspect with magi graph query "
                  "\"SELECT text, status FROM claims WHERE status NOT IN ('verified','web-verified')\"",
                  unverified=n_unv)

    try:
        from magi.kb_registry import load_settings

        kb_only = load_settings().get("profile") == "kb-only"
    except Exception:
        kb_only = False

    if kb_only:
        cores["balthasar"] = {"state": "disabled", "note": "kb-only profile", "score": None}
    else:
        b = balthasar_status(topic)
        cores["balthasar"] = b
        weights["balthasar"] = 1.0
        if not b["bd_installed"]:
            _hint("beads-missing",
                  "install beads (bd) for work-state tracking: https://github.com/gastownhall/beads")
        elif not b["beads_root"]:
            _hint("pm-uninit", "magi pm init   # initialize beads at the hub root")
        elif (b["ready"] or 0) > 0:
            _hint("bd-ready", "bd ready   # there is actionable work", ready=b["ready"])

    if topic:
        c = casper_status(topic, scan)
        cores["casper"] = c
        weights["casper"] = 1.0
        if c["state"] == "missing":
            _hint("index-missing", "magi index   # build the retrieval index")
        elif c["state"] == "stale":
            _hint("index-stale", "magi index   # refresh the retrieval index")
        try:
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
        cores["casper"] = {"state": "offline", "note": "no workspace", "score": None}
        if hub:
            slugs = _hub_topics(hub)
            if slugs:
                _hint("hub-topics",
                      f"topics: {', '.join(slugs)} — cd topics/<slug> && magi sync",
                      topics=slugs)

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
        "hub": str(hub) if hub else None,
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


def run_fixes(report: dict, dry_run: bool = False) -> tuple[int, int]:
    """Run the deterministic repairs the report asked for. Returns (ran, failed)."""
    import subprocess

    seen: set[tuple[str, ...]] = set()
    ran = failed = 0
    for hint in report.get("hints_structured", []):
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
        proc = subprocess.run([sys.executable, "-m", "magi", *cmd],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        ran += 1
        out = (proc.stdout or proc.stderr or "").strip().splitlines()
        for line in out[-2:]:
            print(f"      {line}")
        if proc.returncode != 0:
            failed += 1
            print(f"      exit {proc.returncode}")
    return ran, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi sync", description="Workspace onboarding: sync ratio + three-core status")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--fix", action="store_true",
                        help="Run the repairs this report suggests (graph build, index, "
                             "backlog sync, pm init) and report the rest.")
    parser.add_argument("--dry-run", action="store_true",
                        help="With --fix: show what would run, change nothing.")
    args = parser.parse_args(argv)

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    ratio = report["sync_ratio"]
    if ratio is not None:
        header = f"MAGI SYSTEM ONLINE — sync ratio {ratio}%"
    elif report["hub"]:
        header = "MAGI SYSTEM — hub root (no topic workspace selected)"
    else:
        header = "MAGI SYSTEM — no workspace detected"
    print(header)
    if report["workspace"]:
        m = report["cores"]["melchior"]
        claims_part = (f" · claims {m['claims_verified']}/{m['claims']} verified"
                       if m.get("claims") else "")
        print(f"|- MELCHIOR  (knowledge)  {m['concepts']} concepts · {m['references']} refs · graph {m['graph']} · backlog {m['backlog']}{claims_part}")
    elif report["hub"]:
        print("|- MELCHIOR  (knowledge)  hub root — enter a topic workspace to see knowledge state")
    else:
        print("|- MELCHIOR  (knowledge)  no topic workspace here — run 'magi init' in a topic directory")
    b = report["cores"]["balthasar"]
    if b.get("state") == "disabled":
        print("|- BALTHASAR (intent)     disabled (kb-only profile — 'magi setup --full' to enable)")
    elif b.get("beads_root"):
        print(f"|- BALTHASAR (intent)     {_fmt(b['ready'])} ready · {_fmt(b['in_progress'])} in progress · {_fmt(b['blocked'])} blocked")
    else:
        print("|- BALTHASAR (intent)     beads offline")
    c = report["cores"]["casper"]
    if c.get("score") is not None:
        print(f"`- CASPER    (retrieval)  index {c['state']} · {c['chunks']} chunks · vectors {c['vectors']}/{c['chunks']}")
    else:
        print("`- CASPER    (retrieval)  offline")
    if report["hub"]:
        print(f"hub: {report['hub']}")
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
        ran, failed = run_fixes(report, dry_run=args.dry_run)
        if args.dry_run:
            return 0
        after = build_report()
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
