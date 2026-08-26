---
name: wiki_inbox
description: "Put papers into a knowledge base from whatever the user has — an arXiv link, a journal page, a DOI, a citation, or a screenshot. Identifies each one, queues it, runs the deterministic ingest pipeline, and hands the batch back for approval."
commands:
  inbox: "Add papers to a library from links, DOIs, citations, or screenshots."
---

# MAGI — Inbox Skill (wiki_inbox)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

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

**What this is for.** The user has found papers — a browser tab, a list of links, a citation pasted from an email, a screenshot of a reference list — and wants them in a library. Your job is to turn each one into an identifier, hand it to the deterministic pipeline, and report back.

**What you do not do.** You do not download PDFs, convert anything, transcribe pages, or write into the library. Every one of those is a `magi` command, and the pipeline picks the best route available on its own. Your contribution is *identification* — the one part that genuinely needs judgment.

---

## Execution flow

### 1. Work out which library

```bash
magi kb list --json
```

If the user named one, match it. If there is exactly one registered and you are inside it, use it. Otherwise **ask** — do not guess which of someone's libraries a paper belongs in.

Nothing registered? They need `magi kb register <PATH>` first, or to run this from inside a workspace.

### 2. Turn each thing into an identifier

This is the part that needs you. Work down this list per item and stop at the first that succeeds:

| What the user gave you | What to do |
|---|---|
| `arxiv.org/abs/XXXX.XXXXX`, `arXiv:XXXX.XXXXX`, a bare id | Use it as-is. Legacy ids like `cond-mat/0506438` are fine. |
| A DOI, or a `doi.org/...` link | Use the DOI. The pipeline maps it to arXiv itself where one exists. |
| A journal / publisher page URL | *web-fetch* the page and read its `<meta>` tags — `citation_arxiv_id`, then `citation_doi`. Nearly every publisher emits these because Google Scholar requires them. Failing that, look for a DOI in the visible text. |
| A screenshot or PDF page | Read the title and authors off it with your vision tool. Search for the paper to recover an arXiv id or DOI. **Show the user the title you found and confirm it is the right paper before queueing** — a misread title queues the wrong paper under a plausible name. |
| A citation string / BibTeX | Pull the DOI or arXiv id out of it. If neither is present, search on title + first author. |
| A local PDF path | Pass the path straight through; the pipeline handles a file on disk. |

If you genuinely cannot identify something, say which one and why, and leave it out. A queue entry pointing at the wrong paper is worse than a missing one.

### 3. Queue them — one command, all of them

```bash
magi ingest url "<ID_OR_URL>" "<ANOTHER>" "<ANOTHER>" --library "<LIBRARY_NAME>" --json
```

Takes any number of targets. `--library` routes to a registered knowledge base by name, so you do not have to be standing in it.

This writes **one line per paper to a queue and does nothing else** — no network, no conversion, nothing touched in the library. It is safe to run before you are certain, because nothing happens until the next step and nothing is permanent until the one after that.

**If you used `--library`, resolve it to a path now and carry that path through every remaining step.** `--library` is understood by `magi ingest url` and by nothing else: `batch-run`, `batch-list`, `batch-decide` and `batch-commit` take `--topic-dir` and have never taken `--library`. Running them bare after queueing into a named library processes whichever workspace you are standing in — so the queue you just filled sits untouched while a different library's queue gets converted and committed.

```bash
magi kb list --json      # find the path for "<LIBRARY_NAME>"
```

Every command below is written with `--topic-dir "<TOPIC_DIR>"` for that reason. Drop it only when you are certain you are already inside the right workspace.

### 4. Run the pipeline

```bash
magi ingest batch-run --topic-dir "<TOPIC_DIR>"
```

Deterministic and unattended. It tries, in order: arXiv's own LaTeXML HTML (where every formula carries its original LaTeX verbatim), the arXiv source tarball, the PDF text layer, MinerU, then local OCR. It stops at the first that works and never escalates to anything expensive on its own.

**Costs you nothing but the time to read the output.** Do not try to help it. Do not fetch anything yourself.

> Add `--limit N` if the queue is long and you want a first batch to look at.

### 5. Show the user what came out, and let them decide

```bash
magi ingest batch-list --topic-dir "<TOPIC_DIR>" --json
```

Summarise it for them — do not paste the JSON. For each item: the title, which route succeeded, and any findings. Findings are the pipeline telling you what it is unsure about; the ones worth mentioning out loud:

- `figure-count-mismatch` / `broken-image-links` — figures are missing from the output
- `image-path-not-portable` — a figure reference will break once the document is committed. **Always surface this one**: it is a defect in the route, not in the paper, and approving it files a document whose images go dark.
- `leftover-tex` — the converter choked on a macro and left raw TeX inline
- `suspiciously-short` — the document came out far shorter than expected
- `identity-mismatch` — the output is labelled as a different paper than requested. **Always surface this one.**
- `route-arxiv-html` with a formula count — informational, and good news
- `route-textlayer` with a page count — informational, and good news: the PDF was read out of its own text layer, so no model was involved and nothing was recognised

Then **ask** which to keep. For a clean batch, "all of these look fine, approve them?" is a reasonable single question. For anything carrying a finding, name it and let them choose.

```bash
magi ingest batch-decide --topic-dir "<TOPIC_DIR>" --item <ITEM_ID> --decision approve
magi ingest batch-decide --topic-dir "<TOPIC_DIR>" --item <ITEM_ID> --decision reject
```

Rejecting is not discarding: the item is automatically requeued on the **next route down**, and shows up in the next `batch-run`. So "this conversion is bad, try another way" is one word.

### 6. Commit

```bash
magi ingest batch-commit --topic-dir "<TOPIC_DIR>"
```

Moves approved documents into `raw/`, brings their figures, and runs lint + graph build + `wiki reindex` once for the batch.

It does **not** run `magi index`, so the documents are in the library but not yet findable by `magi search`, and it does **not** compile anything into `wiki/references/`. Both are separate steps — finish with them rather than stopping here.

**It refuses to commit a batch that still has undecided items** — that is the human gate, and it is the whole point. If it tells you something is undecided, go back to step 5 rather than working around it.

---

## Rules

- **Never invent an identifier.** If you are not sure a screenshot is `2405.00208`, ask. The pipeline will faithfully fetch whatever you give it.
- **Never bypass the pipeline.** If a route fails, reject the item and let it fall to the next one. Do not download the PDF yourself, and above all do not transcribe pages with your own vision — that costs roughly one sub-agent call per page and has burned a user's entire weekly quota.
- **Never approve on the user's behalf.** Even a batch with no findings is theirs to accept. The gate exists because a pipeline cannot tell whether a paper is the one they meant.
- **Report honestly.** If three of eight papers failed, say so plainly with the reasons. A summary that reads as success while two papers are missing is worse than no summary.

## Error handling

| What you see | What it means |
|---|---|
| `no knowledge base named 'X'` | The name is not registered. Run `magi kb list` and use one of those, or register the path first. |
| `no workspace found` | You are not in a topic directory and gave no `--library`. |
| An item with `error:` in `batch-list` | That route failed. Reject it to fall to the next one; report if it reaches the bottom. |
| `left alone, N item(s) still undecided` | `batch-commit` is refusing on purpose. Decide the rest first. |
| `arXiv served a PDF, not source` | Normal — that submission has no LaTeX. Reject it and it falls through to a PDF route. |
