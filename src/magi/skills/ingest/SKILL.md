---
name: ingest
description: "Turn whatever the human has — a PDF, a link, a DOI, a screenshot of a citation — into raw/ sources this workspace can compile."
commands:
  ingest: "Ingest papers, articles and notes into raw/."
---

# ingest

## When to use
Anything new is arriving: files in `inbox/`, a link or DOI in the chat, a
citation the human read out.

## Method
1. Files already in `inbox/`, or a path you were given: `magi ingest auto` —
   it routes by type and finalizes. Stop here unless it refuses.
2. A link, DOI, arXiv id or citation: identify it first — that is the step
   that needs you, not the pipeline. Then `magi ingest url "<id or url>"`,
   `magi ingest batch-run`, `magi ingest batch-list`.
3. Show `batch-list`'s findings to the human before committing. Surface
   `identity-mismatch`, `figure-count-mismatch` and `image-path-not-portable`
   every time — they mean the file is not what its name says.
4. `magi ingest batch-decide` per item, then `magi ingest batch-commit`.
5. After a batch: `magi math check --json`. Ingestion's signature failure is a
   `$$` that lost its pair and swallowed the paragraph after it — valid LaTeX,
   so nothing else catches it. Work the list with the `tidy` skill.
6. `magi ingest finalize` when a run needs cleanup the auto route skipped.

## Rules
- **Never** fall back to transcribing pages through vision because a converter
  failed. It costs one sub-agent call per page — say the page count and do not
  start until a person has said yes. At most 10 concurrent if they do.
- **Never** commit a batch the human has not seen the findings for.
- A converter that exits non-zero: report its stderr and stop. An unreadable
  file: say which, and carry on with the rest. Report **partial** work as
  partial — "9 of 12, these 3 failed" — never as done.
- When the workspace is ambiguous, say so and stop:
  `NEEDS-DECISION: which library? | options: <a> / <b> | default if unanswered: stop`.
  Collect any NEEDS-DECISION from work you delegate and ask once, together.
