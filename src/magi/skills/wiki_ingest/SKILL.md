---
name: wiki_ingest
description: "Ingest new academic papers, notes, or web articles into the raw/ folder of your active topic wiki."
commands:
  ingest: "Ingest new papers or sources (from inbox/ or a specific path) into the raw/ directory."
---

# LLM Wiki — Ingest Skill (wiki_ingest)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill handles converting external material (URLs, PDFs, local text files, and items inside `inbox/`) into raw sources.

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Map each capability to your own agent's tool — *read-file* (`Read` in Claude Code, `view_file` in Antigravity), *sub-agent / parallel task* (`Task`/`Agent` in Claude Code, `invoke_subagent` in Antigravity), *shell* (`Bash`/`PowerShell`). Use the closest equivalent your framework provides; if a parallel sub-agent tool is unavailable, transcribe PDF pages sequentially yourself (still verifying the full page count).

**Fast path (use it when nothing needs judgment):** `magi ingest auto "<PATH>"` — or
`magi ingest auto` with no path to take the whole `inbox/` — picks the converter by file
type (LaTeX source → `tex`, PDF → `mineru` when a token is configured else local `ocr`,
text → `add`), runs `magi ingest finalize` for each file, and does one lint/graph/index
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
    *   **For `.pdf` files**: 
        *   **MinerU Cloud API (Primary)**: You **MUST** first check if `ocr.use_mineru` is `true` and `ocr.mineru_api_token` is set in `config.yaml`. If so, use:
            `magi ingest mineru "<PDF_PATH>" -o "<TOPIC_DIR>\\raw\\<type>"`
            *Note: This script automatically generates YAML frontmatter, writes the file, and extracts referenced figures into `images/` prefixed with the doc slug. Skip Step 4.*
        *   **Native Vision (Fallback/Secondary)**: If MinerU fails or is disabled, you **MUST** enforce strict pagination to prevent laziness and truncation. You **MUST** use your agent's **sub-agent / parallel-task tool** to spawn parallel sub-agents, assigning each sub-agent exactly ONE page of the PDF to transcribe using their native multimodal vision. (If no sub-agent tool exists, transcribe pages one at a time yourself — never skip or summarize pages.) 
    *   **Page Count Verification (MANDATORY)**: If using Native Vision, before spawning subagents, extract the total page count using a deterministic Python script (e.g., `pymupdf` or `PyPDF2`). After all subagents return, verify that the number of returned transcriptions equals the total page count. If any pages are missing, re-invoke subagents for the missing pages. Do NOT proceed with assembly until all pages are accounted for.
    *   **Concurrency Limit**: If using Native Vision, do NOT invoke more than 10 subagents at the same time. If the PDF has more than 10 pages, you must orchestrate them in batches (e.g., launch pages 1-10, wait for them to finish, then launch 11-20). You may write/run a quick Python script (e.g., using `pymupdf` or `PyPDF2`) purely to get the total page count before batching.
    *   Once all subagents return their page transcriptions, assemble them in order using:
        `magi ingest assemble --dir <PAGES_DIR> --out <FILE_PATH> --title <TITLE> [--source <SRC>] [--type papers]`
    *   **Alternative (Local OCR)**: If the user explicitly requests high-performance local offline OCR or wants to save external API tokens for long documents, you **MUST** use the `wiki_ingest_ocr` skill instead. Do not mix native multimodal with local Python OCR scripts inside this skill.
    *   For `.md` files or general inbox files, call the ingest helper script:
        `magi ingest add --file \"<MD_FILE>\" --type \"<TYPE>\" --topic-dir \"<TOPIC_DIR>\" [--move]`
        This script handles parsing/injecting standard YAML frontmatter, slugifying, and moving/copying the file.
        *Note: after `ingest add --move`, the inbox original no longer exists — pass the `raw/` destination path (printed by the command) as `"<ORIGINAL_FILE_PATH>"` to `magi ingest finalize` in Step 5. (If you pass the old inbox path instead, the `source already processed/moved - skipping inbox archival` notice is expected and harmless.)*
    *   **For `.tex` files (and arXiv `.tar.gz` source bundles)**: You **MUST** use the Pandoc conversion script. Run:
        `magi ingest tex "<TEX_OR_TARGZ_PATH>" -o "<TOPIC_DIR>\raw\<type>"`
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
        `magi ingest crop "<PDF_PATH>" --text "<search_text_near_error>" --out "<TOPIC_DIR>\scratch\crop.png"`
    *   View the generated `crop.png`, correct the Markdown from the ground truth, and re-run `magi math check <FILE>` until only annotated possible-macro entries remain.

7.  **Global Lint & Index (End of Batch)**:
    *   **CRITICAL:** Once ALL files in the `inbox/` have been processed through steps 1-6, you MUST run the global lint and index operation ONCE outside the loop:
    ```bash
    magi ingest finalize "none" --topic-dir "<TOPIC_DIR>" --lint-only
    ```
