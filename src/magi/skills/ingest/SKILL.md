---
name: ingest
description: "Turn whatever the human has — a PDF, a link, a DOI, a screenshot of a citation — into raw/ sources this project can compile."
commands:
  ingest: "Ingest papers, articles and notes into raw/."
origin: magi
---

# ingest

## When to use
Anything new is arriving: files in `inbox/`, a link or DOI in the chat, a
citation the human read out.

## Method
1. Files already in `inbox/`, or a path you were given: `magi ingest auto` —
   it routes by type and finalizes. Stop here unless it refuses. (A run that
   skipped cleanup: `magi ingest finalize <the file> --project-dir .`.)
2. A link, DOI, arXiv id or citation: identify it first — that is the step
   that needs you, not the pipeline. Then `magi ingest url "<id or url>"` and
   `magi ingest batch-run`.
3. `magi ingest review` lists what is waiting. Show its findings to the human
   before committing — surface `identity-mismatch`, `figure-count-mismatch`
   and `image-path-not-portable` every time: they mean the file is not what
   its name says.
4. `magi ingest review --item <id> --decision approve` per row, then
   `magi ingest review --commit`.
5. After a batch: `magi math check --json`. Ingestion's signature failure is a
   `$$` that lost its pair and swallowed the paragraph after it — valid LaTeX,
   so nothing catches it. Work that list with the `tidy` skill.

## Rules
- **Never** transcribe pages through vision because a converter failed: it costs
  one sub-agent call per page. Not until a person has said yes; 10 at once.
- **Never** commit a batch the human has not seen the findings for.
- A converter that exits non-zero: report its stderr and stop. An unreadable
  file: name it and carry on. Report **partial** work as partial — "9 of 12".
- Which project a source belongs to is never your guess: when it is
  ambiguous, stop and ask. Collect the questions the work you delegated
  could not ask (Invariant 4) and put them all at once.
