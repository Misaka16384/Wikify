---
name: tidy
description: "Repair what the mechanical passes cannot: broken LaTeX from conversion, sprawling tags, and concepts that are secretly the same concept."
commands:
  tidy: "Fix conversion damage, tag sprawl and duplicate concepts."
---

# tidy

## When to use
`magi math check` reports errors, tags have sprawled into near-duplicates, or
two concept cards are about the same thing.

## Method
**Maths.** `magi math format` first — it fixes mechanically what it can, free.
Then `magi math check --json` for what is left. Work one file at a time: fix
the *first* entry, re-check, and watch the rest of that file's errors vanish —
one unclosed `$$` swallows everything after it and reports as many errors.
`likely-macro` is usually a false positive; check the source with
`magi ingest crop` before touching it.

**Tags.** `magi tags extract`, read the counts, and write the mapping that
collapses synonyms, acronyms and plurals into one tag. Show it to the human
before `magi tags apply` — it rewrites every card. Two tags that are aliases of
each other usually mean two cards about one concept.

**Concepts.** `magi link --dedup-only` proposes merges. Confirm each is really
one concept, then `magi wiki refactor-concept --old <a> --new <b>`. A
sub-concept merges into its parent, never the other way. Read the merged
context with `magi wiki context` before rewriting the definition.

Close with `magi lint --fix` and `magi index`.

## Rules
- **Never** apply a tag mapping the human has not seen. It is not reversible
  by hand.
- **Never** rename a concept by editing filenames; `refactor-concept` is the
  only route that fixes the links too.
- The unit of work is the workspace, not the file: re-run `magi math check`
  at the end and report what is still broken as **partial**, not as done.
