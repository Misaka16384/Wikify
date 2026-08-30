---
name: draft
description: "Write in drafts/ against the project: grounded prose, exported citations, and the derivation a proposition points at."
commands:
  draft: "Write or revise a draft in drafts/, grounded in the wiki."
origin: magi
---

# draft

## When to use
Writing anything longer than a note — a section, an argument, a paper — or
working out the derivation a proposition depends on.

## Method
1. Ground first: `magi search "<what you need>"` and `magi wiki context --name
   <concept>` for what the project
   already says. Write from what you read, not from what you remember.
2. Write to `drafts/<slug>.md`. Drafts are yours to edit freely; they are not
   compiled and they never move into `wiki/`.
3. A draft that supports a proposition is its derivation. Point the
   proposition at it (`derivation:` in the note's frontmatter) so that editing
   one shows up as debt on the other until somebody says what changed.
4. Exploratory prose that is not yet a claim goes in a `> [!draft]` callout,
   so a later reader can tell working-out from conclusion.
5. Citations: `magi bib --all` for what the draft cites, `--fetch` to fill in
   what the cards lack.
6. Before calling it done: `magi verify <claims.json> --project-dir .` for the
   claims, `magi math check` for the formulas, `magi stats verify-refs
   <draft.md>` for the links. verify and verify-refs each take their file.

## Rules
- **Never** cite a reference card as a source. Cite the `raw/` file behind it;
  the card is a compiled view and can be wrong exactly where it matters.
- **Never** move a finished draft into `wiki/`. A conclusion becomes a
  proposition in `threads/` and, if it is worth a long form, a synthesis in
  `wiki/topics/`.
- Say what is still missing. A draft with a section header and no section
  under it reads as finished at a glance and is not.
