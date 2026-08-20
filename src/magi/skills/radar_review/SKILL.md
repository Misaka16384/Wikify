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

**Cold start (fresh workspace):** On a fresh workspace run `magi index` before step 3 so `magi search` has an index to query. If `output/graph.db` is missing, treat the wiki as empty and skip the concept query in step 2. On an empty wiki, judge candidates against the scope statement in `config.md` instead of concept cards — do not skip-all.

## Execution Flow

1. **Locate pending work**: `magi radar status --json`. If `pending_digests` is empty, report "radar clean" and stop.
2. **Load context**: read the pending digest file(s) with your file-read tool. For workspace grounding, note the top concepts: `magi graph query "SELECT title FROM nodes WHERE type='concept' ORDER BY id LIMIT 30"` (or `magi stats <TOPIC_DIR> wiki-summary`).
3. **Score each candidate** (work from the digest; consult `output/radar/candidates.jsonl` for full abstracts). When the digest is marked *"Sorted by relevance"*, each candidate carries a `relevance:` cosine score against the library's own embedding centroid. **Read it as a rank, not as a probability.** Every candidate reaching a digest already came from your configured arXiv categories or from recommendations seeded on your own papers, so they are all plausible to begin with and the scores bunch near the top of the scale — measured on a real 67-paper library, all forty candidates fell between 0.55 and 0.70, while genuinely unrelated text scores far lower (a generic condensed-matter paper 0.45, a machine-learning paper 0.37, random characters 0.31). So:

   - The **order** is informative at the extremes and unreliable in the middle. Trust the top of the file; do not treat a 0.02 difference around the median as meaning anything.
   - There is **no absolute cutoff worth applying** — a threshold low enough to be "safe" filters nothing, and one high enough to filter cuts real hits.
   - Judge the middle of the list yourself, from the abstract, against the workspace scope.
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

## Citation-Gap Reports (feature B)

`magi radar citation-gap` produces `inbox/radar/YYYY-MM-DD-citation-gaps.md` — candidates that are semantic neighbors of OUR papers, recent, share references with us, yet do not cite us. **Treat this as a scout report with expected false positives.** For each candidate:

1. Read both abstracts (ours and theirs) and, when available, our claim cards (`magi graph query "SELECT text FROM claims WHERE doc_id LIKE '%<our-paper-slug>%'"`).
2. Judge the actual citation obligation: does their work *use or overlap* a specific result of ours, or is it merely nearby? Citing a survey instead of us, different sub-question, or independent methodology = NOT an obligation.
3. Only for genuine obligations, file: `bd create -t review "Citation gap: arXiv:<their-id> vs our arXiv:<our-id>" -d "<the specific overlapping result + evidence>"`. These are for the human to decide what (if anything) to do — never draft outreach automatically.
4. Mark the report frontmatter `status: reviewed` with a one-line tally.

## Quality Rules

- Judge relevance against the *workspace's* research scope, not general interest — a brilliant paper outside scope is a **skip**.
- Every read-now/relevant verdict must name at least one existing concept card or open bd question it connects to; if you cannot name one, downgrade to skip. Exception: on an empty wiki (no concept cards yet), judge against the scope statement in `config.md` instead — do not skip-all.
- Do not create duplicate bd issues: check `bd list --json` for an existing "Read arXiv:<id>" title first.

## Error Handling

- If `magi radar status` reports no workspace, stop and tell the user to run from a topic directory.
- If `bd` is unavailable, still complete steps 1-3 and 5, and list the would-be issues in your report; note that task tracking was skipped.
- If any script exits non-zero, report the stderr and continue with remaining candidates.
