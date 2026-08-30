---
name: compile
description: "Compile raw sources into dense, interlinked reference and concept cards, and mine the concepts a compiled card left implicit."
commands:
  compile: "Compile raw sources into wiki cards, and enrich thin ones."
origin: magi
---

# compile

## When to use
`magi next` reports a compile backlog, or `magi wiki uncompiled` lists sources
with no card.

## Method
1. `magi wiki uncompiled` — the backlog. Nothing else decides what is next.
2. One sub-agent per source, at most 10 at once. Each reads the raw file and
   writes one card using `<SKILL_DIR>/templates/paper_template.md`, creating
   concepts with `magi wiki add-concept --name/--source/--content` as it goes.
3. Every claim's `SOURCE:` points at the `raw/` file, never at another card.
4. Thin cards: `magi wiki placeholders <card.md>` and `magi stats concept-density <card.md>`,
one card at a time.
   Under ~5 links or ~2 per 1000 words, mine the source for the concepts it
   actually contains — never invent one it does not.
5. `magi lint --fix` first, then `magi wiki reindex`. That order matters:
   reindex reads what lint has already normalised.
6. `magi graph build` and `magi index` to make it findable.

## Rules
- **Never** start the fan-out without saying how many: "12 sources, so 12
  sub-agent calls" is a sentence a person can stop. Ten concurrent is the
  ceiling.
- **Never** write a card that reads complete while a section is `[STUB:
  Awaiting synthesis]` without saying so in your report. **Partial** work is
  reported as partial.
- Collect the questions your sub-agents could not ask (Invariant 4) and put
  them to the human once, when the batch reports back.
- Cards are compiled, not authored: to change one, change the source and
  recompile.
