# Agentic Wiki Skills
*[English](README.md) | [中文](README_zh.md)*

This project provides a suite of agentic skills for AI coding assistants (like Gemini/Antigravity) to automatically ingest, compile, organize, and query academic papers (PDFs and LaTeX) into an Obsidian-compatible Markdown knowledge base.

## 🌟 Project Showcase

Here are some glimpses of the knowledge base generated and maintained entirely by this AI pipeline:

![Knowledge Graph Visualization](./graph.png)
*A dense, auto-generated semantic graph of mathematical and physical concepts.*

![Knowledge Graph Details](./graph2.png)
*Detailed view of the semantic links injected by the background embedding engine.*

![Compiled Literature Note](./note1.png)
*A pristine literature note compiled directly from a messy PDF using local OCR and Pandoc.*

![Math and Concept Extraction](./note2.png)
*Beautifully formatted mathematical proofs and lemmas extracted flawlessly from LaTeX source.*

---

## 1. What it Does

When loaded into your AI assistant, you can ask the AI to:
- **Ingest**: Convert math-heavy PDFs (via local OCR) and LaTeX source files into Markdown.
- **Compile**: Extract mathematical definitions, theorems, and concepts into individual, interlinked Obsidian cards.
- **Deduplicate & Link**: Automatically find duplicate concepts, merge them safely via RAG, and semantically link related files using local vector embeddings.
- **Interactive Q&A**: Chat with your entire knowledge base (`wiki_ask`) where the AI strictly answers using local RAG, Graph SQL queries, and regex search—guaranteeing zero hallucinations and exact citations.
- **Auto-Healing**: The intelligent linter automatically detects dead links and self-heals the knowledge graph using a global concept alias routing system.

---

## 2. System Dependencies

Before deploying the skills, ensure your system has the following runtime dependencies installed.

### 2.1 Python Dependencies
**Python 3.10+** is required. Install the global packages:
```powershell
pip install -r requirements.txt
```

### 2.2 System-Level External Binaries
The pipeline relies on several external utilities that must be present in your system's `PATH`:

1.  **Poppler-utils (`pdftoppm` & `pdfimages`)** — Required for rendering PDF pages and extracting diagrams.
    *   *Windows (Scoop)*: `scoop install poppler`
    *   *Windows (Choco)*: `choco install poppler`
    *   *macOS (Homebrew)*: `brew install poppler`
    *   *Linux (APT)*: `sudo apt-get install poppler-utils`
2.  **Ripgrep (`rg`)** — Powers fast, multi-file citation mapping and wikilink refactoring.
    *   *Windows (Scoop)*: `scoop install ripgrep`
    *   *Windows (Choco)*: `choco install ripgrep`
    *   *macOS (Homebrew)*: `brew install ripgrep`
    *   *Linux (APT)*: `sudo apt-get install ripgrep`
3.  **Pandoc** — Required for automated ingestion and conversion of LaTeX (`.tex`) documents to Markdown.
    *   *Windows (Scoop)*: `scoop install pandoc`
    *   *Windows (Choco)*: `choco install pandoc`
    *   *macOS (Homebrew)*: `brew install pandoc`
    *   *Linux (APT)*: `sudo apt-get install pandoc`

### 2.3 Ollama Local Models
The offline transcription and semantic linking rely on Ollama running as a background service:
```powershell
ollama pull glm-ocr
ollama pull qwen3-embedding:0.6b
```

---

## 3. Deployment

Run the provided PowerShell installer to copy the skills into your AI's configuration directory (`$HOME\.gemini\config\`):
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

---

## 4. How to Use

Once installed, simply ask your AI assistant to perform the following workflows on your topic directory.

### Ingestion & Compilation
- **`wiki_ingest` / `wiki_ingest_ocr`**: Tell the AI to process a new paper or PDF in your `inbox/`. It will OCR or convert it into the `raw/` directory.
- **`wiki_compile`**: Ask the AI to compile the raw paper. It will generate a structured literature note and extract all novel mathematical/physical concepts into `wiki/concepts/`.

### Knowledge Graph Maintenance
- **`wiki_enrich`**: Tell the AI to scan a paper and extract missing lemmas or theorems into new concept cards.
- **`wiki_concept_sync`**: Ask the AI to deduplicate concepts. It will find duplicates and merge them intelligently.
- **`wiki_semantic_link`**: Runs silently to vector-scan all your concepts and inject `[[Related Links]]` at the bottom of cards. Features blazing-fast incremental MD5 caching for zero API overhead on unchanged concepts.

### Chat & Research
- **`wiki_ask "Your Question"`**: Ask the AI any question about your vault. The AI will use RAG and Graph SQL to answer you with strict `[[Citations]]` and zero hallucinations.
- **`wiki_audit` / `wiki_research`**: Ask the AI to perform a comprehensive literature review or audit the knowledge base for scientific contradictions.

### Utilities & Workspace Lifecycle
- **`wiki_init`**: Tell the AI to bootstrap a fresh, clean topic workspace with all necessary directories and config files.
- **`wiki_lint`**: Runs a structural validation across the vault to fix broken links and metadata. It features an auto-healer that routes dead links to their new canonical files using alias maps.
- **`wiki_graph_index`**: Forces a manual update of the SQLite `graph.db` used by the AI for querying relationships, while simultaneously refreshing the underlying semantic vector cache.
- **`wiki_hub_init` / `wiki_hub_manager`**: Use these to initialize a central Hub and manage (list/archive/restore) multiple topic vaults simultaneously.

---
*Note: All destructive operations (merging, rewriting) automatically create backups in `.backup/` folders.*
