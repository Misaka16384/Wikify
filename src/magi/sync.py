"""magi sync — workspace onboarding: three-core status + sync ratio.

The sync ratio is a deterministic workspace-health score, not vibes:

- MELCHIOR (epistemic state / the wiki):
    0.7 · graph freshness (graph.db mtime >= newest wiki/*.md mtime)
  + 0.3 · backlog health  (max(0, 1 - uncompiled/10))
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
from pathlib import Path

from magi.core.workspace import find_hub_root, find_workspace_root


def _newest_md_mtime(root: Path) -> float:
    newest = 0.0
    if root.is_dir():
        for p in root.rglob("*.md"):
            try:
                newest = max(newest, p.stat().st_mtime)
            except OSError:
                continue
    return newest


def _count_cards(d: Path) -> int:
    if not d.is_dir():
        return 0
    return sum(1 for p in d.rglob("*.md") if p.name != "_index.md")


def melchior_status(topic: Path) -> dict:
    wiki = topic / "wiki"
    graph_db = topic / "output" / "graph.db"
    concepts = _count_cards(wiki / "concepts")
    references = _count_cards(wiki / "references")
    topics_n = _count_cards(wiki / "topics")

    newest = _newest_md_mtime(wiki)
    if not graph_db.is_file():
        graph_state = "missing" if newest else "empty-wiki"
        freshness = 0.0 if newest else 1.0
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

    return {
        "concepts": concepts,
        "references": references,
        "topics": topics_n,
        "graph": graph_state,
        "backlog": backlog,
        "score": round(0.7 * freshness + 0.3 * backlog_health, 3),
    }


def casper_status(topic: Path) -> dict:
    idx = topic / "output" / "index.db"
    if not idx.is_file():
        return {"state": "missing", "chunks": 0, "vectors": 0, "score": 0.0}
    import sqlite3

    freshness = 1.0 if idx.stat().st_mtime >= _newest_md_mtime(topic / "wiki") else 0.3
    chunks = vectors = 0
    try:
        conn = sqlite3.connect(idx)
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

    if topic:
        m = melchior_status(topic)
        cores["melchior"] = m
        weights["melchior"] = 1.0
        if m["graph"] in ("missing", "stale"):
            hints.append("magi graph build   # refresh the knowledge graph")
        if m["backlog"] > 0:
            hints.append("magi pm backlog-sync && bd ready   # uncompiled sources -> tracked tasks")

    b = balthasar_status(topic)
    cores["balthasar"] = b
    weights["balthasar"] = 1.0
    if not b["bd_installed"]:
        hints.append("install beads (bd) for work-state tracking: https://github.com/gastownhall/beads")
    elif not b["beads_root"]:
        hints.append("magi pm init   # initialize beads at the hub root")
    elif (b["ready"] or 0) > 0:
        hints.append("bd ready   # there is actionable work")

    if topic:
        c = casper_status(topic)
        cores["casper"] = c
        weights["casper"] = 1.0
        if c["state"] == "missing":
            hints.append("magi index   # build the retrieval index")
        elif c["state"] == "stale":
            hints.append("magi index   # refresh the retrieval index")
        digest_dir = topic / "inbox" / "radar"
        if digest_dir.is_dir():
            pending = sum(
                1 for p in digest_dir.glob("*-digest.md")
                if "status: pending-review" in p.read_text(encoding="utf-8", errors="replace")
            )
            if pending:
                hints.append(f"radar: {pending} digest(s) pending — run the radar_review skill")
    else:
        cores["casper"] = {"state": "offline", "note": "no workspace", "score": None}

    scored = [(weights[k], cores[k]["score"]) for k in weights if cores[k].get("score") is not None]
    total_w = sum(w for w, _ in scored)
    ratio = round(100.0 * sum(w * s for w, s in scored) / total_w, 1) if total_w else None

    return {
        "workspace": str(topic) if topic else None,
        "hub": str(hub) if hub else None,
        "sync_ratio": ratio,
        "cores": cores,
        "hints": hints,
    }


def _fmt(v, suffix: str = "") -> str:
    return f"{v}{suffix}" if v is not None else "?"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="magi sync", description="Workspace onboarding: sync ratio + three-core status")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    ratio = report["sync_ratio"]
    header = f"MAGI SYSTEM ONLINE — sync ratio {ratio}%" if ratio is not None else "MAGI SYSTEM — no workspace detected"
    print(header)
    if report["workspace"]:
        m = report["cores"]["melchior"]
        print(f"|- MELCHIOR  (knowledge)  {m['concepts']} concepts · {m['references']} refs · graph {m['graph']} · backlog {m['backlog']}")
    else:
        print("|- MELCHIOR  (knowledge)  no topic workspace here — run 'magi init' in a topic directory")
    b = report["cores"]["balthasar"]
    if b["beads_root"]:
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
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
