"""End-to-end smoke test for the magi CLI.

Runs the core deterministic chain in a throwaway sandbox:
hub init -> init -> (seed cards) -> lint -> graph build -> graph query
-> wiki reindex -> stats -> verify -> grep -> sync

Usage: python tests/smoke_test.py            (uses sys.executable -m magi)
Exit code 0 = all green; non-zero = first failing step reported.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAGI = [sys.executable, "-m", "magi"]


def _ollama_up() -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/version", timeout=3):
            return True
    except Exception:
        return False


def run(args: list[str], cwd: Path, expect: tuple[int, ...] = (0,), timeout: int = 120) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        MAGI + args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )
    status = "OK " if proc.returncode in expect else "FAIL"
    print(f"[{status}] magi {' '.join(args)} (exit {proc.returncode}, expected {expect})")
    if proc.returncode not in expect:
        print("--- stdout ---\n" + proc.stdout[-2000:])
        print("--- stderr ---\n" + proc.stderr[-2000:])
        raise SystemExit(1)
    return proc


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="magi_smoke_"))
    print(f"sandbox: {sandbox}")
    try:
        hub = sandbox / "hub"
        # 1. hub + topic workspace scaffolding
        run(["hub", "init", str(hub)], cwd=sandbox)
        topic = hub / "topics" / "smoke-topic"
        topic.mkdir(parents=True)
        run(["init", "--topic-dir", str(topic), "--name", "Smoke Topic", "--scope", "smoke testing"], cwd=topic)
        run(["hub", "register", "smoke-topic", "--hub", str(hub)], cwd=topic)
        run(["hub", "list", "--hub", str(hub), "--json"], cwd=sandbox)
        resolve = run(["hub", "resolve", str(hub), "smoke-topic"], cwd=sandbox)
        assert "smoke-topic" in resolve.stdout, "hub resolve did not return topic path"

        # 2. seed a concept card + a reference card
        concepts = topic / "wiki" / "concepts"
        refs = topic / "wiki" / "references"
        concepts.mkdir(parents=True, exist_ok=True)
        refs.mkdir(parents=True, exist_ok=True)
        (concepts / "test-concept.md").write_text(
            "---\ntitle: Test Concept\ntype: concept\ntags:\n  - smoke\n---\n\n"
            "A test concept about $E=mc^2$ linking to [[Smoke Paper]].\n",
            encoding="utf-8",
        )
        (refs / "smoke-paper.md").write_text(
            "---\ntitle: Smoke Paper\ntype: papers\ntags:\n  - smoke\n---\n\n"
            "A reference card citing [[Test Concept]]. The key result is X.\n",
            encoding="utf-8",
        )

        # regression locks from the friction-fix round:
        assert (topic / "CLAUDE.md").exists() and (topic / "config.yaml").exists(), \
            "init did not scaffold protocol/config files"
        wl = run(["hub", "list", "--json"], cwd=hub)  # hub discovered from cwd, no --hub
        reg = json.loads((hub / "wikis.json").read_text(encoding="utf-8"))
        assert "smoke-topic" in reg.get("wikis", {}), "magi init did not auto-register topic in hub"
        ns = run(["search", "x", "--json"], cwd=sandbox, expect=(1,))  # no workspace -> exit 1 + JSON error
        assert "error" in json.loads(ns.stdout), "search --json error envelope missing"

        # 3. quality chain (lint exits 1 when it finds issues — machinery
        # working on deliberately-minimal seed cards is a pass for smoke)
        run(["wiki", "reindex", str(topic)], cwd=topic)
        run(["lint", str(topic), "--json", "--skip-math", "--fix"], cwd=topic, expect=(0, 1))
        assert (topic / "CLAUDE.md").exists() and (topic / "config.yaml").exists() \
            and not (topic / "inbox" / ".unknown" / "CLAUDE.md").exists(), \
            "lint --fix quarantined init-scaffolded files (regression)"
        run(["graph", "build", str(topic)], cwd=topic)
        q = run(["graph", "query", "SELECT COUNT(*) AS n FROM nodes", "--db", str(topic / "output" / "graph.db")], cwd=topic)
        assert json.loads(q.stdout)["results"][0]["n"] >= 2, f"graph has too few nodes: {q.stdout}"
        # regression lock: wikilink targets resolve to real node ids (joinable)
        jq = run(["graph", "query",
                  "SELECT n.title AS t FROM nodes n JOIN edges e ON n.id = e.target_id "
                  "WHERE e.type='wikilink' AND e.source_id='wiki/concepts/test-concept'",
                  "--db", str(topic / "output" / "graph.db")], cwd=topic)
        assert "Smoke Paper" in jq.stdout, f"wikilink edge not resolved to node id: {jq.stdout}"
        run(["stats", str(topic), "wiki-summary"], cwd=topic)
        run(["map", str(concepts / "test-concept.md")], cwd=topic)
        run(["math", "check", str(concepts / "test-concept.md")], cwd=topic)

        # 4. claim verification (both CLAIM: and FINDING: openers)
        claims = sandbox / "claims.txt"
        claims.write_text(
            "CLAIM: the reference card mentions a key result\n"
            'EVIDENCE: "The key result is X."\n'
            "SOURCE_TYPE: local_wiki\n"
            f"SOURCE: wiki/references/smoke-paper.md\n"
            "\n"
            "FINDING: web sources only get format checks\n"
            'EVIDENCE: "irrelevant"\n'
            "SOURCE_TYPE: web\n"
            "SOURCE: https://example.org/x\n",
            encoding="utf-8",
        )
        run(["verify", str(claims), "--topic-dir", str(topic)], cwd=topic)

        # 5. retrieval + onboarding
        g = run(["grep", "key result", str(refs / "smoke-paper.md")], cwd=topic)
        assert "key result" in g.stdout.lower(), "grep found nothing"
        s = run(["sync", "--json"], cwd=topic)
        payload = json.loads(s.stdout)
        assert payload.get("workspace"), "sync did not detect workspace"

        # 6. writer paths (add-concept WITHOUT --no-rebuild exercises the
        # rewritten 'python -m magi graph build / wiki reindex' subprocess chain)
        run(["wiki", "add-concept", "--name", "Second Concept",
             "--source", "smoke-paper", "--content", "Defined as Y, see [[Test Concept]].",
             "--topic-dir", str(topic)], cwd=topic)
        assert (concepts / "second-concept.md").exists(), "add-concept did not create the card"
        run(["wiki", "context", "--name", "Test Concept", "--topic-dir", str(topic)], cwd=topic)
        run(["wiki", "chunk", str(refs / "smoke-paper.md"), "--topic-dir", str(topic), "--max-lines", "5"], cwd=topic)
        run(["wiki", "placeholders", str(refs / "smoke-paper.md"), "--json"], cwd=topic)
        run(["wiki", "uncompiled", "--topic-dir", str(topic)], cwd=topic)
        run(["tags", "extract", str(topic)], cwd=topic)
        run(["math", "format", str(concepts / "test-concept.md")], cwd=topic)
        run(["wiki", "refactor-concept", "--topic-dir", str(topic),
             "--old", "Second Concept", "--new", "Renamed Concept", "--no-rebuild"], cwd=topic)
        inbox_doc = topic / "inbox" / "note.md"
        inbox_doc.parent.mkdir(exist_ok=True)
        inbox_doc.write_text("---\ntitle: Inbox Note\n---\n\nBody.\n", encoding="utf-8")
        run(["ingest", "add", "--file", str(inbox_doc), "--type", "notes",
             "--topic-dir", str(topic), "--move"], cwd=topic)
        run(["migrate"], cwd=topic)

        # 7. M1: beads bridge + sync ratio (skipped when bd is not on PATH)
        if shutil.which("bd"):
            run(["pm", "init", str(hub), "--prefix", "smoke"], cwd=hub, timeout=300)
            run(["pm", "status", "--json"], cwd=topic)
            run(["pm", "backlog-sync", "--topic-dir", str(topic)], cwd=topic)
            s2 = run(["sync", "--json"], cwd=topic)
            rep = json.loads(s2.stdout)
            assert rep["sync_ratio"] is not None, "sync ratio missing"
            assert rep["cores"]["balthasar"]["beads_root"], "beads not detected by sync"
            assert (rep["cores"]["balthasar"]["open"] or 0) >= 1, "backlog-sync created no issues"
        else:
            print("[SKIP] bd not installed — M1 beads steps skipped")

        # 8. M2: retrieval index + hybrid search (BM25 path is deterministic;
        # vector path exercised only when Ollama is reachable)
        run(["index", "--topic-dir", str(topic), "--no-vectors"], cwd=topic)
        sr = run(["search", "key result", "--topic-dir", str(topic), "--mode", "bm25", "--json"], cwd=topic)
        res = json.loads(sr.stdout)
        assert res["results"], "bm25 search found nothing"
        assert any("smoke-paper" in r["path"] for r in res["results"]), "expected hit missing"
        if _ollama_up():
            run(["index", "--topic-dir", str(topic)], cwd=topic, timeout=300)
            sv = run(["search", "central finding of the paper", "--topic-dir", str(topic), "--json"], cwd=topic)
            resv = json.loads(sv.stdout)
            assert resv["vector_available"], "vectors expected with Ollama up"
        else:
            print("[SKIP] Ollama not reachable — vector search steps skipped")

        # 9. M3: radar status (harvest itself needs network — not in smoke)
        rs = run(["radar", "status", "--topic-dir", str(topic), "--json"], cwd=topic)
        rrep = json.loads(rs.stdout)
        assert rrep["seen_total"] == 0 and rrep["pending_digests"] == [], "fresh workspace radar not clean"

        # 10. M4: claims/provenance — magi:claims block -> graph tables; verify v2
        theses = topic / "wiki" / "theses"
        theses.mkdir(parents=True, exist_ok=True)
        (theses / "smoke-thesis.md").write_text(
            "---\ntitle: Smoke Thesis\ntype: thesis\n---\n\n# Smoke Thesis\n\nBody.\n\n"
            "<!-- magi:claims\n"
            "CLAIM: the paper reports a key result\n"
            'EVIDENCE: "The key   result is X."\n'
            "SOURCE_TYPE: local_wiki\n"
            "SOURCE: wiki/references/smoke-paper.md\n"
            "STATUS: verified\n"
            "-->\n",
            encoding="utf-8",
        )
        run(["graph", "build", str(topic)], cwd=topic)
        cq = run(["graph", "query",
                  "SELECT COUNT(*) AS n FROM claims", "--db", str(topic / "output" / "graph.db")], cwd=topic)
        assert '"n": 1' in cq.stdout, f"claims table expected 1 row: {cq.stdout}"
        eq = run(["graph", "query",
                  "SELECT COUNT(*) AS n FROM edges WHERE type='supported_by'",
                  "--db", str(topic / "output" / "graph.db")], cwd=topic)
        assert '"n": 1' in eq.stdout, "supported_by edge missing"
        claims2 = sandbox / "claims2.txt"
        claims2.write_text(
            "CLAIM: whitespace-normalized quotes verify\n"
            'EVIDENCE: "The key   result   is X."\n'
            "SOURCE_TYPE: local_wiki\n"
            "SOURCE: wiki/references/smoke-paper.md\n",
            encoding="utf-8",
        )
        vr = run(["verify", str(claims2), "--topic-dir", str(topic), "--json"], cwd=topic)
        vrep = json.loads(vr.stdout)
        assert vrep["results"][0]["status"] == "verified", f"normalized match failed: {vrep}"

        print("\nALL SMOKE TESTS PASSED")
        return 0
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
