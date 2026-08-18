---
name: wiki_draft
description: "Write paper drafts inside the workspace: drafts/ convention, evidence-backed writing with magi search, citation export with magi bib, and LaTeX export."
commands:
  draft: "Start or continue a paper draft in drafts/, wired into search, claims, and citation export."
---

# LLM Wiki — Draft Skill (wiki_draft)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill closes the loop from knowledge base to manuscript. Drafts are first-class workspace citizens: they live in `drafts/`, are searchable via `magi search` (collection `drafts`), and reuse the library's citation metadata through `magi bib`.

## Conventions

- Drafts live at `drafts/<slug>.md` (e.g. `drafts/fracton-intro.md`). The directory is recognized by lint and indexed by `magi index`, but drafts do **not** enter the knowledge graph or sync ratio — they are work-in-progress, not knowledge.
- Cite library material with wikilinks to reference cards (`[[pretko-2020-fracton]]`); check them anytime with `magi stats <TOPIC_DIR> verify-refs`.
- Factual assertions you plan to defend belong in a `<!-- magi:claims -->` block inside the draft, same format as cards; verify with `magi verify drafts/<slug>.md --topic-dir <TOPIC_DIR>`.

## Workflow

1. **Ground every section in the library.** Before writing a paragraph, pull evidence:
   - `magi search "<question>" -k 5` (hybrid; add `--collection references` or `--path 'raw/papers/2026-*<slug>*'` to narrow to one paper)
   - `magi wiki context --name "<concept>"` for every paragraph already written about a concept.
2. **Write the draft** in `drafts/<slug>.md`. Quote precisely; wikilink every source card you rely on.
3. **Export citations** when the reference list forms:
   - `magi bib <card-slug>` — one BibTeX entry from a reference card's frontmatter
   - `magi bib --all -o drafts/refs.bib` — the whole library
   - `magi bib <card-slug> --fetch` — prefer arXiv's official BibTeX (network)
   - Ingested papers keep their original `.bib`/`.bbl` next to the raw markdown (`raw/papers/<slug>.bib`) — mine those for entries the cards do not cover.
4. **Validate before sharing**: `magi stats <TOPIC_DIR> verify-refs` (no dangling wikilinks), `magi verify drafts/<slug>.md --topic-dir <TOPIC_DIR>` (claims hold), `magi math check drafts/<slug>.md` (formulas compile).
5. **Export to LaTeX/PDF** when needed (pandoc is already a workspace dependency):
   `pandoc drafts/<slug>.md --bibliography drafts/refs.bib --citeproc -o drafts/<slug>.tex` (or `.pdf` with a LaTeX toolchain).
6. **Track the writing itself** as work: file a `bd` issue (type: thesis/derivation as appropriate) per section so `magi sync` and the Balthasar panel show writing progress alongside reading progress.

## Boundaries

- Do not move drafts into `wiki/` — cards are distilled knowledge, drafts are prose in motion. When a draft stabilizes insights, extract them into concept cards (wiki_compile) instead.
- Drafts are indexed for retrieval, so half-formed text WILL surface in search results; prefix exploratory sections with `> [!draft]` callouts so future searches can tell them apart.
