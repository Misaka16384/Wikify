---
name: wiki_ingest_ocr
description: "Ingest new academic papers or PDFs into the raw/ folder of your active topic wiki using the local OCR model configured in config.yaml."
commands:
  ingest_ocr: "Ingest new PDFs (from inbox/ or a specific path) using local GLM-OCR into the raw/ directory."
---

# LLM Wiki — Ingest Local OCR Skill (wiki_ingest_ocr)

This skill handles converting external PDF documents (especially academic papers or scanned articles inside `inbox/` or custom local paths) into high-fidelity clean Markdown using the local OCR model configured in `config.yaml` (default: `glm-ocr` at 150 DPI).

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
            python .agents/bin/pdf2md-agent/agent.py "<PDF_PATH>" -o "<TOPIC_DIR>/raw/<type>" -t "<DOC_TITLE>"
            ```
        *   *Note: This script now automatically generates the standard YAML frontmatter and writes the file as `YYYY-MM-DD-slug.md` directly into your output directory. You do NOT need to rename the file or append YAML manually.*
    *   **For `.md` files**: Do not run any conversion. Directly inject standard YAML frontmatter, rename to `YYYY-MM-DD-slug.md`, and copy to `raw/<type>/`.
    *   **For `.tex` files**: You **MUST** use the Pandoc conversion script instead of OCR. Run:
        `python .agents/bin/tex2md.py "<TEX_PATH>" -o "<TOPIC_DIR>\raw\<type>"`
        *Note: This script automatically generates YAML frontmatter and writes the file.*
4.  **Post-Processing Pipeline**: Once the above conversion is done, trigger the automated pipeline script to handle moving, formatting, linting, and logging in one shot:
    ```bash
    python .agents/bin/ingest_pipeline.py "<ORIGINAL_FILE_PATH>" --topic-dir "<TOPIC_DIR>" --log-msg "Ingested <DOC_TITLE> via OCR"
    ```

## Error Handling

*   If any script exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.

