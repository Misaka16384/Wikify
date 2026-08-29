---
name: ask
description: "Answer a question from this workspace's own knowledge — retrieved, read and cited, never from memory."
commands:
  ask: "Answer a question from the knowledge base, with citations."
origin: magi
---

# ask

## When to use
Any question about what this library knows. Also when you are about to answer
one from memory.

## Method
1. `magi search "<question>"` — hybrid retrieval, the default route. Add
   `--line <line>` when the question comes from inside a research line: it
   ranks what that line is looking at higher without hiding the rest.
2. **Read the files it returns.** A search result is a pointer, not a source;
   citing a snippet you did not open is how a half-sentence becomes a claim.
3. About one concept: `magi wiki context "<name>"` gives every paragraph that
   mentions it, which beats reassembling the card from search hits.
4. Structural questions — what links to what, which sources back a claim,
   what is unlinked: `magi graph query "<SQL>"`, or `magi graph browse` for the
   same without SQL. Exact strings: `magi grep`.
5. Answer with inline `[[wikilinks]]` to the cards you actually read. Where
   the library does not know, say that instead of filling the gap.
6. A question the library cannot answer but should be able to is a gap worth
   keeping: one line in `inbox/notes.md`, or open it as a question with
   `magi thread new <slug> --kind question`.

## Rules
- **Never** answer from parametric memory. If retrieval found nothing, the
  answer is "this library does not have that", which is useful and true.
- **Never** cite a reference card as the source of a claim; cite the `raw/`
  file it was compiled from. A card can be wrong in the way the claim is
  trying to rule out.
- Retrieval that returns nothing usually means the index is stale: `magi sync`
  says so, and `magi index` fixes it.
