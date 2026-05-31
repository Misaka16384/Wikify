---
name: wiki_ingest_ocr
description: "Ingest new academic papers or PDFs into the raw/ folder of your active topic wiki using the local OCR model configured in config.yaml."
commands:
  ingest_ocr: "Ingest new PDFs (from inbox/ or a specific path) using local GLM-OCR into the raw/ directory."
---

# LLM Wiki — Ingest Local OCR Skill (wiki_ingest_ocr)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill handles converting external PDF documents (especially academic papers or scanned articles inside `inbox/` or custom local paths) into high-fidelity clean Markdown using the local OCR model configured in `config.yaml` (default: `glm-ocr` at 130 DPI).

> **Figures are handled automatically.** Both the PDF path (`pdf2md-agent`) and the TeX path (`tex2md.py`) extract figures into an `images/` folder beside the output Markdown and embed them inline (`![caption](images/<slug>-...png)`). Figure files are prefixed with the document slug, so multiple papers can share one `raw/<type>/images/` folder without collisions. Vector figures and `.pdf`/`.eps` sources are rasterised to PNG. You do **not** need to handle figures manually.

When the user asks to ingest PDFs using local OCR (or runs the command without a path):
1.  **Resolve Ingestion Targets**:
    *   If a specific file path is provided, process that target.
    *   If NO target is provided, automatically scan the `inbox/` directory for any `.pdf`, `.md`, or `.tex` files.
    *   If `inbox/` contains multiple target files, you **MUST** loop through all of them and process them one by one in a batch.
    *   If `inbox/` is empty of target files, only then prompt the user to specify a file path.
2.  **Identify Source Type**: For each PDF file, academic papers go to `raw/papers/`, other articles to `raw/articles/`.
3.  **File Type Handling & Conversion**:
    *   **For `.pdf` files (Execute Local GLM-OCR Conversion)**:
        *   Run the upgraded local `pdf2md-agent` script on the PDF:
            ```bash
            python <BIN>/pdf2md-agent/agent.py "<PDF_PATH>" -o "<TOPIC_DIR>/raw/<type>" -t "<DOC_TITLE>"
            ```
        *   *Note: This script now automatically generates the standard YAML frontmatter and writes the file as `YYYY-MM-DD-slug.md` directly into your output directory. You do NOT need to rename the file or append YAML manually.*
    *   **For `.md` files**: Do not run any conversion. Directly inject standard YAML frontmatter, rename to `YYYY-MM-DD-slug.md`, and copy to `raw/<type>/`.
    *   **For `.tex` files (and arXiv `.tar.gz` source bundles)**: You **MUST** use the Pandoc conversion script instead of OCR. Run:
        `python <BIN>/tex2md.py "<TEX_OR_TARGZ_PATH>" -o "<TOPIC_DIR>\raw\<type>"`
        *Note: This script automatically generates YAML frontmatter, writes the file, and extracts/converts referenced figures into `images/` (rasterising `.pdf`/`.eps` figures to PNG). Check the printed `Figures: N embedded, M unresolved` line; if any are unresolved, the source bundle may be missing those figure files.*
4.  **Post-Processing Pipeline**: Extract the exact path of the generated Markdown file from the conversion script's output. Then, trigger the pipeline to handle moving and formatting (skipping global lint for now):
    ```bash
    python <BIN>/ingest_pipeline.py "<ORIGINAL_FILE_PATH>" --topic-dir "<TOPIC_DIR>" --md-file "<GENERATED_MD_FILE>" --skip-lint --log-msg "Ingested <DOC_TITLE> via OCR"
    ```

5.  **Manual Math Error Correction (Agentic Fallback)**:
    *   **CRITICAL:** If `ingest_pipeline.py` outputs any warnings like `[WARNING] Math syntax errors in <FILE>:`, you MUST immediately stop and fix them.
    *   Do NOT guess the fix for semantic errors like `Double subscript` or `Unexpected end of stream`.
    *   You MUST use your file reading, search, or multimodal vision tools to read the **original source PDF** at the corresponding location to see the actual formula.
    *   **CRITICAL TOOL**: If you cannot easily infer the formula structure, you MUST use the provided PDF cropping tool to extract the exact region around the error as an image for your multimodal vision:
        `python <BIN>/pdf_math_crop.py "<PDF_PATH>" --text "<search_text_near_error>" --out "<TOPIC_DIR>\scratch\crop.png"`
    *   View the generated `crop.png`, then manually edit the Markdown file to correct the semantic math errors based on the ground truth in the original paper, and re-run `python <BIN>/validate_math_latex.py <FILE>` to confirm all errors are gone.

6.  **Global Lint & Index (End of Batch)**:
    *   **CRITICAL:** Once ALL files in the `inbox/` have been processed through steps 1-5, you MUST run the global lint and index operation ONCE outside the loop:
    ```bash
    python <BIN>/ingest_pipeline.py "none" --topic-dir "<TOPIC_DIR>" --lint-only
    ```

## Error Handling

*   If any script exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.

