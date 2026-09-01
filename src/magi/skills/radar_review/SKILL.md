---
name: radar_review
description: "Triage a literature-radar digest: judge each candidate against what this project is actually doing, and queue only what earns it."
commands:
  radar_review: "Triage the pending radar digest."
origin: magi
---

# radar_review

## When to use
`magi radar status` reports a digest waiting, or `magi next` says so.

## Method
1. `magi radar status --json`, then read the digest.
2. Read the project before judging: `magi stats wiki-summary` and the open
   propositions in `threads/`. Relevance is relevance *to what is being asked
   here*, not to the field.
3. Score each candidate by hand. The digest's own score is a **rank, not a
   measurement** — reliable at the two ends, meaningless in the middle. There
   is no cutoff to apply; read the ones near the top and decide.
4. `magi search "<title>"` before keeping one: a paper the project already
   covers is not new information, it is a duplicate.
5. `magi radar triage --id <id> --decision accept|dismiss`, one call per
   candidate, id from the digest. Never hand-edit the digest's frontmatter to
   record a decision — the triage ledger is what the next run reads.
6. Accepted papers: `magi ingest url "<id>"` to queue them, then hand off to
   the `ingest` skill.

## Rules
- **Never** accept a paper because it scored well. The score orders the
  reading; the judgement is yours and it is the whole point of this step.
- **Each candidate is its own question.** Judge it against the project, not
  against your reasoning about the ones before it: twenty in, that reasoning is
  the loudest thing in context and the least relevant, and the bar drifts.
- **Never** leave a digest half-triaged without saying so. A **partial** pass
  looks identical to a finished one in the ledger — say "18 of 40, stopped at
  the fold" in your report.
- A citation-gap report asks a different question: whether this project *owes*
  a citation, not whether the paper is nearby. Most nearby papers are not owed.
