---
name: wiki_ingest_ocr
description: "Ingest new academic papers or PDFs into the raw/ folder of your active topic wiki using local high-fidelity GLM-OCR model at 150 DPI."
commands:
  ingest_ocr: "Ingest new PDFs (from inbox/ or a specific path) using local GLM-OCR into the raw/ directory."
---

# LLM Wiki — Ingest Local OCR Skill (wiki_ingest_ocr)

This skill handles converting external PDF documents (especially academic papers or scanned articles inside `inbox/` or custom local paths) into high-fidelity clean Markdown using the local offline `glm-ocr` model at **150 DPI**.

When the user asks to ingest PDFs using local OCR (or runs the command without a path):
1.  **Resolve Ingestion Targets**:
    *   If a specific PDF file path is provided, process that target.
    *   If NO target is provided, automatically scan the `inbox/` directory for any `.pdf` files.
    *   If `inbox/` contains multiple PDFs, you **MUST** loop through all of them and process them one by one in a batch.
    *   If `inbox/` is empty of PDFs, only then prompt the user to specify a file path.
2.  **Identify Source Type**: For each PDF file, academic papers go to `raw/papers/`, other articles to `raw/articles/`.
3.  **Execute Local GLM-OCR Conversion**:
    *   Run the upgraded local `pdf2md-agent` script on the PDF:
        ```bash
        python $HOME/.gemini\config\bin\pdf2md-agent\agent.py "<PDF_PATH>" -o "<TOPIC_DIR>\raw\<type>" -t "<DOC_TITLE>"
        ```
    *   *Note: This script now automatically generates the standard YAML frontmatter and writes the file as `YYYY-MM-DD-slug.md` directly into your output directory. You do NOT need to rename the file or append YAML manually.*
4.  **Register Ingest**: If successfully processed from `inbox/`, move the original PDF file to `inbox/.processed/`.
5.  **Format Math Formulas**: Run the math formatting helper script on the active topic workspace directory to automatically clean, isolate, and align LaTeX double-dollar block equations:
    `python $HOME/.gemini\config\bin\format_math.py "<TOPIC_DIR>"`
6.  **Index Update**: Run the local helper to rebuild the topic's raw directory index entries:
    `python $HOME/.gemini\config\bin\llm-wiki.py lint --fix`
7.  **Log**: Append an entry in the topic's `log.md`.
