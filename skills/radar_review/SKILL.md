---
name: radar_review
description: "Triage literature-radar digests: score each candidate paper against the local wiki, file bd survey issues for keepers, and queue selected PDFs for ingestion."
commands:
  radar_review: "Review pending radar digests and turn relevant candidates into tracked reading tasks."
---

# MAGI — Radar Triage Skill (radar_review)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

The deterministic radar (`magi radar harvest`, usually run nightly by the scheduler) collects candidate papers into `inbox/radar/YYYY-MM-DD-digest.md` and `output/radar/candidates.jsonl`. **Your job is the judgment layer**: decide which candidates matter for THIS workspace, and convert decisions into durable state (bd issues, ingestion queue). Never let a digest rot in `pending-review`.

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Where it says *file-read tool*, use your agent's equivalent (`Read` in Claude Code, `view_file` in Antigravity). Shell commands run via `Bash`/`PowerShell` or your framework's shell tool.

## Execution Flow

1. **Locate pending work**: `magi radar status --json`. If `pending_digests` is empty, report "radar clean" and stop.
2. **Load context**: read the pending digest file(s) with your file-read tool. For workspace grounding, note the top concepts: `magi graph query "SELECT title FROM nodes WHERE type='concept' ORDER BY id LIMIT 30"` (or `magi stats <TOPIC_DIR> wiki-summary`).
3. **Score each candidate** (work from the digest; consult `output/radar/candidates.jsonl` for full abstracts):
   - Run `magi search "<candidate title + key abstract phrases>" -k 5 --json` to see how strongly the candidate overlaps existing knowledge.
   - Classify: **read-now** (directly advances an active question — check `bd ready`), **relevant** (extends the wiki's core topics), **skip** (out of scope).
   - Judge from the abstract against the workspace scope (`config.md`); do NOT fetch full PDFs during triage.
4. **Convert decisions to durable state**:
   - For each **read-now** and **relevant** candidate, file a bd issue:
     `bd create -t survey "Read arXiv:<id> — <short title>" -d "<one-line why it matters + which concepts/questions it touches>"`
     Give **read-now** items `-p 1`.
   - For **read-now** items the user will likely ingest: note the arXiv link in the issue description; ingestion happens later via the wiki_ingest skill (PDF into `inbox/`).
   - **skip** items need no action — the ledger already prevents re-surfacing.
5. **Close out the digest**: edit its frontmatter `status: pending-review` → `status: reviewed`, and append a one-line summary at the top of the digest body: how many read-now / relevant / skip.
6. **Report** to the user: counts per class, the read-now titles with one-line justifications, and the created bd issue ids.

## Quality Rules

- Judge relevance against the *workspace's* research scope, not general interest — a brilliant paper outside scope is a **skip**.
- Every read-now/relevant verdict must name at least one existing concept card or open bd question it connects to; if you cannot name one, downgrade to skip.
- Do not create duplicate bd issues: check `bd list --json` for an existing "Read arXiv:<id>" title first.

## Error Handling

- If `magi radar status` reports no workspace, stop and tell the user to run from a topic directory.
- If `bd` is unavailable, still complete steps 1-3 and 5, and list the would-be issues in your report; note that task tracking was skipped.
- If any script exits non-zero, report the stderr and continue with remaining candidates.
