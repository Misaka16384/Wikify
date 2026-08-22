---
name: wiki_ingest
description: "Ingest new academic papers, notes, or web articles into the raw/ folder of your active topic wiki."
commands:
  ingest: "Ingest new papers or sources (from inbox/ or a specific path) into the raw/ directory."
---

# LLM Wiki — Ingest Skill (wiki_ingest)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill handles converting external material (URLs, PDFs, local text files, and items inside `inbox/`) into raw sources.

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

**Fast path (use it when nothing needs judgment):** `magi ingest auto "<PATH>"` — or
`magi ingest auto` with no path to take the whole `inbox/` — picks the converter by what the
file is (LaTeX source → `tex`; PDF → its own text layer when that is enough, else
`mineru` with a token or local `ocr` without one; text → `add`), runs
`magi ingest finalize` for each file, and does one lint/graph/index
pass at the end. Add `--dry-run` to see the routing first. Fall back to the numbered steps
below when a file needs a decision the router cannot make: native-vision transcription,
a page range, math-error triage, or a source type other than the default.

When the user asks to ingest documents (or runs the command without a path):
1.  **Resolve Ingestion Targets**:
    *   If a specific file path or URL is provided, process that target.
    *   If NO target is provided, automatically scan the `inbox/` directory.
    *   If `inbox/` contains multiple files, you **MUST** loop through all of them and process them one by one in a batch.
    *   If `inbox/` is empty, only then prompt the user to specify a file or source URL.
2.  **Identify Source Type**: For each target file, academic papers go to `raw/papers/`, web pages to `raw/articles/`, manually typed notes to `raw/notes/`.
3.  **File Type Handling & Conversion**:
    *   **For a paper you have an arXiv id, DOI, or URL for — including anything the radar accepted**: do NOT convert it by hand. Queue it and let the deterministic pipeline pick the route:
        ```
        magi ingest url "<URL or DOI or arXiv id>"
        magi ingest batch-run
        magi ingest batch-list          # then approve what looks right
        ```
        This tries arXiv's own LaTeXML HTML first, where every formula carries its original LaTeX verbatim, then the source tarball, then the PDF's own text layer where that suffices, then MinerU, then local OCR. It costs you no tokens beyond reading the report. **Everything it produces waits for a human to approve it before entering the library**, so you are not deciding on anyone's behalf.
    *   **For a `.pdf` file already on disk with no identifier**: use the router — it picks the best available converter and never picks anything expensive:
        `magi ingest auto "<PDF_PATH>" --topic-dir "<TOPIC_DIR>"`
        Add `--dry-run` first to see which route it would take. For a born-digital PDF with no mathematics it reads the document's own text layer — free, and faithful because it is the text itself rather than a reading of it. A PDF *with* mathematics goes to a model even though its text reads perfectly: the characters survive and the two-dimensional structure does not. This is not a judgement call you need to make; the gate decides and prints what it decided. If it reports that it cannot route the file, that is a real answer: it means neither a MinerU token nor Ollama is available. **Say so and stop.** Do not work around it.
    *   **Native Vision — last resort, and never by default**: transcribing a PDF page by page with your own multimodal vision costs roughly **one sub-agent call per page**, and a batch of papers can run to hundreds of calls. It has burned a user's entire weekly quota. Use it **only** when the user has explicitly asked for it after being told the page count, or when they say so having seen `magi ingest auto` report no available route.
        Before you spawn anything: count the pages with a deterministic script (`pymupdf` or `PyPDF2`), state the bill plainly — *"this is 34 pages, so about 34 sub-agent calls"* — and **ask the user to confirm**. If a batch, state the total across all files.
        Once confirmed: one sub-agent per page, never more than 10 concurrent, verify the number of returned transcriptions equals the page count and re-invoke for any missing page, then assemble in order:
        **Collect any `NEEDS-DECISION:` lines the page sub-agents return** — an unreadable page or an ambiguous figure is something they cannot ask you about themselves. Raise them together, once, rather than per page.
        `magi ingest assemble --dir <PAGES_DIR> --out <FILE_PATH> --title <TITLE> [--source <SRC>] [--type papers]`
    *   **Local OCR**: `magi ingest auto` already picks this for a PDF that needs a model when Ollama is present and no MinerU token is configured. It is one deterministic command with no fan-out, it supports `--pages`, and it resumes. Reach for the `wiki_ingest_ocr` skill when you need to force it, or need a page range.
    *   For `.md` files or general inbox files, call the ingest helper script:
        `magi ingest add --file \"<MD_FILE>\" --type \"<TYPE>\" --topic-dir \"<TOPIC_DIR>\" [--move]`
        This script handles parsing/injecting standard YAML frontmatter, slugifying, and moving/copying the file.
        *Note: after `ingest add --move`, the inbox original no longer exists — pass the `raw/` destination path (printed by the command) as `"<ORIGINAL_FILE_PATH>"` to `magi ingest finalize` in Step 5. (If you pass the old inbox path instead, the `source already processed/moved - skipping inbox archival` notice is expected and harmless.)*
    *   **For `.tex` files (and arXiv `.tar.gz` source bundles)**: You **MUST** use the Pandoc conversion script. Run:
        `magi ingest tex "<TEX_OR_TARGZ_PATH>" -o "<TOPIC_DIR>/raw/<type>"`
        *Note: This script automatically generates YAML frontmatter (including `arxiv_id:` when the filename carries one), writes the file, and extracts referenced figures into `images/` (rasterising `.pdf`/`.eps` figures to PNG, prefixed with the doc slug). Skip Step 4. Check the printed `Figures: N embedded, M unresolved` line — and take any `figure(s) ... dropped by Pandoc` warning seriously: compare against the source PDF.*
        *Bibliography: if the bundle has a `.bib` it is used with citeproc; if it only ships a compiled `.bbl` (the arXiv norm), the tool inlines it automatically — citations then render as `[@key]` with a full References list. Either asset is preserved next to the markdown as `<slug>.bib`/`.bbl` (used later by `magi bib`). Do not hand-craft empty `.bib` files.*
4.  **Assign Slug & YAML**: Write to `raw/<type>/YYYY-MM-DD-slug.md` with standard frontmatter:
    ```yaml
    ---
    title: "Original Title"
    source: "Original URL or path"
    type: articles|papers|repos|notes
    ingested: YYYY-MM-DD
    tags: [tag1, tag2]
    summary: "2-3 sentence overview of the source"
    ---
    ```
    **Frontmatter Validation (MANDATORY)**: After writing, run `magi lint <TOPIC_DIR>` and check ONLY the issues reported for the newly ingested file — fix its frontmatter-related critical or warning issues before proceeding. Root-level or other-file warnings unrelated to the new file can be ignored at this step (they are handled by the end-of-batch lint in Step 7).
5.  **Post-Processing Pipeline**: Extract the exact path of the generated Markdown file from the conversion script's output. Then, trigger the pipeline to handle moving and formatting (skipping global lint for now):
    ```bash
    magi ingest finalize "<ORIGINAL_FILE_PATH>" --topic-dir "<TOPIC_DIR>" --md-file "<GENERATED_MD_FILE>" --skip-lint --log-msg "Ingested <DOC_TITLE>"
    ```

6.  **Manual Math Error Correction (Agentic Fallback)**:
    *   If `magi ingest finalize` outputs warnings like `[WARNING] Math syntax errors in <FILE>:`, triage them **by kind** before fixing anything:
        *   `Undefined control sequence` entries carrying the validator's *"may be a macro from a package this validator lacks"* note are usually **false positives** (obscure package macros). Spot-check ONE against the PDF; if the markdown matches the paper, leave the rest alone — do NOT rewrite valid macros.
        *   Structural errors (`Double subscript`, `Missing }`, `Unexpected end of stream`) are real. Do NOT guess their fix.
    *   For real errors, read the **original source PDF** at the corresponding location. If you cannot easily infer the formula structure, use the PDF cropping tool:
        `magi ingest crop "<PDF_PATH>" --text "<search_text_near_error>" --out "<TOPIC_DIR>/scratch/crop.png"`
    *   View the generated `crop.png`, correct the Markdown from the ground truth, and re-run `magi math check <FILE>` until only annotated possible-macro entries remain.
    *   **Ingesting a batch?** Do not do this file by file. `magi math check --json` harvests every broken formula in the workspace at once, and the `wiki_math_fix` skill works that list — including the common case where one unclosed `$$` swallowed a page of prose.

7.  **Global Lint & Index (End of Batch)**:
    *   **CRITICAL:** Once ALL files in the `inbox/` have been processed through steps 1-6, you MUST run the global lint and index operation ONCE outside the loop:
    ```bash
    magi ingest finalize "none" --topic-dir "<TOPIC_DIR>" --lint-only
    ```
