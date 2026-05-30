---
name: wiki_ingest
description: "Ingest new academic papers, notes, or web articles into the raw/ folder of your active topic wiki."
commands:
  ingest: "Ingest new papers or sources (from inbox/ or a specific path) into the raw/ directory."
---

# LLM Wiki — Ingest Skill (wiki_ingest)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill handles converting external material (URLs, PDFs, local text files, and items inside `inbox/`) into raw sources.

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Map each capability to your own agent's tool — *read-file* (`Read` in Claude Code, `view_file` in Antigravity), *sub-agent / parallel task* (`Task`/`Agent` in Claude Code, `invoke_subagent` in Antigravity), *shell* (`Bash`/`PowerShell`). Use the closest equivalent your framework provides; if a parallel sub-agent tool is unavailable, transcribe PDF pages sequentially yourself (still verifying the full page count).

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
            `python <BIN>/mineru_cloud_worker.py "<PDF_PATH>" -o "<TOPIC_DIR>\\raw\\<type>"`
            *Note: This script automatically generates YAML frontmatter, writes the file, and extracts referenced figures into `images/` prefixed with the doc slug. Skip Step 4.*
        *   **Native Vision (Fallback/Secondary)**: If MinerU fails or is disabled, you **MUST** enforce strict pagination to prevent laziness and truncation. You **MUST** use your agent's **sub-agent / parallel-task tool** to spawn parallel sub-agents, assigning each sub-agent exactly ONE page of the PDF to transcribe using their native multimodal vision. (If no sub-agent tool exists, transcribe pages one at a time yourself — never skip or summarize pages.) 
    *   **Page Count Verification (MANDATORY)**: If using Native Vision, before spawning subagents, extract the total page count using a deterministic Python script (e.g., `pymupdf` or `PyPDF2`). After all subagents return, verify that the number of returned transcriptions equals the total page count. If any pages are missing, re-invoke subagents for the missing pages. Do NOT proceed with assembly until all pages are accounted for.
    *   **Concurrency Limit**: If using Native Vision, do NOT invoke more than 10 subagents at the same time. If the PDF has more than 10 pages, you must orchestrate them in batches (e.g., launch pages 1-10, wait for them to finish, then launch 11-20). You may write/run a quick Python script (e.g., using `pymupdf` or `PyPDF2`) purely to get the total page count before batching.
    *   Once all subagents return their page transcriptions, assemble them in order into a single standard Markdown document.
    *   **Alternative (Local OCR)**: If the user explicitly requests high-performance local offline OCR or wants to save external API tokens for long documents, you **MUST** use the `wiki_ingest_ocr` skill instead. Do not mix native multimodal with local Python OCR scripts inside this skill.
    *   **For `.md` files**: Do not run any conversion. Directly inject standard YAML frontmatter (see Step 4), rename to `YYYY-MM-DD-slug.md`, and copy to `raw/<type>/`.
    *   **For `.tex` files (and arXiv `.tar.gz` source bundles)**: You **MUST** use the Pandoc conversion script. Run:
        `python <BIN>/tex2md.py "<TEX_OR_TARGZ_PATH>" -o "<TOPIC_DIR>\raw\<type>"`
        *Note: This script automatically generates YAML frontmatter, writes the file, and extracts referenced figures into `images/` (rasterising `.pdf`/`.eps` figures to PNG, prefixed with the doc slug). Skip Step 4. Check the printed `Figures: N embedded, M unresolved` line.*
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
    **Frontmatter Validation (MANDATORY)**: After writing, run `python <BIN>/llm-wiki.py lint <TOPIC_DIR>` and check if the new file has any frontmatter-related critical or warning issues. Fix them before proceeding.
5.  **Post-Processing Pipeline**: Trigger the automated pipeline script to handle moving, formatting, linting, and logging:
    ```bash
    python <BIN>/ingest_pipeline.py "<ORIGINAL_FILE_PATH>" --topic-dir "<TOPIC_DIR>" --log-msg "Ingested <DOC_TITLE>"
    ```

