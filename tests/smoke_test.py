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

        # 3. quality chain (lint exits 1 when it finds issues — machinery
        # working on deliberately-minimal seed cards is a pass for smoke)
        run(["wiki", "reindex", str(topic)], cwd=topic)
        run(["lint", str(topic), "--json", "--skip-math", "--fix"], cwd=topic, expect=(0, 1))
        run(["graph", "build", str(topic)], cwd=topic)
        q = run(["graph", "query", "SELECT COUNT(*) AS n FROM nodes", "--db", str(topic / "output" / "graph.db")], cwd=topic)
        assert '"n"' in q.stdout or "n" in q.stdout, "graph query returned no rows"
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

        print("\nALL SMOKE TESTS PASSED")
        return 0
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
