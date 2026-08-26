---
name: radar_review
description: "Triage literature-radar digests: score each candidate paper against the local wiki, file bd survey issues for keepers, and queue selected PDFs for ingestion."
commands:
  radar_review: "Review pending radar digests and turn relevant candidates into tracked reading tasks."
---

# MAGI — Radar Triage Skill (radar_review)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

The deterministic radar (`magi radar harvest`, usually run nightly by the scheduler) collects candidate papers into `inbox/radar/YYYY-MM-DD-digest.md` and `output/radar/candidates.jsonl`. **Your job is the judgment layer**: decide which candidates matter for THIS workspace, and convert decisions into durable state (bd issues, ingestion queue). Never let a digest rot in `pending-review`.

> **Tools — capabilities, not names.** This skill asks for things like *read a
> file*, *edit a file*, *run a shell command*, *search the web*, *fetch a page*,
> *look at an image*, *spawn a sub-agent*. Every host calls these something
> different and the names change between versions, so use whichever of yours
> fits. If you genuinely lack one, say so and do the sequential equivalent —
> never silently skip the step.

> **Questions go to the main agent.** If you are running as a sub-agent, do not
> try to ask the human: on most hosts the question will not reach them, and on
> some it hangs. Put it in the report you return instead, on its own line:
> `NEEDS-DECISION: <the question> | options: <a> / <b> | default if unanswered: <x>`
> Whoever spawned you collects these and asks once, together — ten sub-agents
> must not become ten interruptions.
> If you **are** the main agent and nobody is there to answer (a scheduled run, a
> piped run, CI), do not guess and do not wait. Stop, and state plainly what you
> would have asked and what you need in order to continue.

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
4. **Record every decision where both surfaces can see it**:

   ```bash
   magi radar triage --report <DIGEST_NAME> --id <CANDIDATE_ID> --decision accept
   magi radar triage --report <DIGEST_NAME> --id <CANDIDATE_ID> --decision dismiss
   magi radar triage --report <DIGEST_NAME>            # list what is recorded so far
   ```

   Use `accept` for **read-now** and **relevant**, `dismiss` for **skip**. Record *every* candidate, not just the keepers — the point of writing "no" down is that triage does not finish in one sitting, and an unrecorded "no" is indistinguishable from an unread candidate.

   **Do not hand-edit the digest's frontmatter to record decisions.** That is what this skill used to do, and it wrote them into a file nothing else reads: the WebUI's radar panel reads `output/radar/triage.jsonl`, so an agent could triage forty candidates and the panel would still show forty undecided. `magi radar triage` writes exactly where the panel reads, and the panel writes there too, so the two agree in both directions.

5. **Turn the keepers into work and into queued papers**:
   - File a bd issue for each **read-now** / **relevant** candidate:
     `bd create -t survey "Read arXiv:<id> — <short title>" -d "<one-line why it matters + which concepts/questions it touches>"`
     Give **read-now** items `-p 1`.
   - Queue the ones the user actually wants in the library. This skill's own description promises it, and it is one command — do not defer it to another skill:
     `magi ingest url "arXiv:<id>" --library "<LIBRARY_NAME>"`
     Queuing fetches nothing. Converting and committing are `magi ingest batch-run` and the approval steps after it (see the `wiki_inbox` skill), and nothing enters the library until a human approves it.
   - **skip** items need no further action — the `dismiss` you recorded plus the seen-ledger keep them from resurfacing.
6. **Close out the digest**: edit its frontmatter `status: pending-review` → `status: reviewed`, and append a one-line summary at the top of the digest body: how many read-now / relevant / skip. This is the one frontmatter edit this skill still makes — it marks the *report* done, and is not where per-candidate decisions go.
7. **Report** to the user: counts per class, the read-now titles with one-line justifications, which papers you queued, and the created bd issue ids.

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

## Rules

- **Never fan out without a number.** Say how many sub-agents you are about to start and what each one covers, before the first one starts. Never more than 10 at once. An unstated fan-out is how one 99-page paper spent a user's entire weekly quota.
- **Never let a sub-agent ask the user.** It cannot — the question reaches nobody and the agent hangs or guesses. A sub-agent returns `NEEDS-DECISION: <question>`; you collect them and raise them together, once.
- **Never decide a candidate on the user's behalf.** The radar proposes; a person accepts. An accepted card becomes a queued ingest, and a queued ingest is work somebody has to review.
- **Never report a partial result as a whole one.** If three of eight sub-agents came back empty or failed, say which and why. A summary that reads as success while part of the work is missing is worse than no summary — it spends the reader's trust instead of their time.

## Error Handling

- If `magi radar status` reports no workspace, stop and tell the user to run from a topic directory.
- If `bd` is unavailable, still complete steps 1-3 and 5, and list the would-be issues in your report; note that task tracking was skipped.
- If any script exits non-zero, report the stderr and continue with remaining candidates.
