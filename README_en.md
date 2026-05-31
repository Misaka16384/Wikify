# Agentic Wiki Skills
*[English](README_en.md) | [中文](README.md)*

This project provides a suite of agentic skills for AI coding assistants (like Gemini/Antigravity and Claude Code) to automatically ingest, compile, organize, and query academic papers (PDFs and LaTeX) into an Obsidian-compatible Markdown knowledge base.

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

When loaded into your AI assistant, you can utilize a rich set of deterministic **slash commands** (`/wiki_xxx`) to perform:
- **Ingest**: Convert math-heavy PDFs (via layout-preserving cloud APIs or local OCR) and LaTeX source files into Markdown.
- **Compile**: Extract mathematical definitions, theorems, and concepts into individual, interlinked Obsidian cards.
- **Deduplicate & Link**: Automatically find duplicate concepts, merge them safely, and semantically link related files using local vector embeddings.
- **Interactive Q&A**: Chat with your entire knowledge base where the AI strictly answers using local RAG, Graph SQL queries, and regex search—guaranteeing zero hallucinations and exact citations.
- **Auto-Healing & Math Correction**: The intelligent linter automatically detects dead links and self-heals the knowledge graph using a global concept alias routing system. It also features robust YAML self-healing to automatically repair LLM-hallucinated syntax errors in frontmatter, and pdflatex-backed validation to check LaTeX mathematical formula correctness.

---

## 2. System Dependencies

Before deploying the skills, ensure your system has the following runtime dependencies installed.

### 2.1 Python Dependencies
**Python 3.10+** is required. Install the global packages:
```powershell
pip install -r requirements.txt
```

> **Tip**: Consider using a virtual environment to avoid conflicts:
```powershell
python -m venv .venv
.\.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS
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
3.  **Pandoc** — Required for automated ingestion and conversion of LaTeX (`.tex`) documents to Markdown. *(Note: `pandoc-crossref` is already bundled with this repository for Windows users)*.
    *   *Windows (Scoop)*: `scoop install pandoc`
    *   *Windows (Choco)*: `choco install pandoc`
    *   *macOS (Homebrew)*: `brew install pandoc`
    *   *Linux (APT)*: `sudo apt-get install pandoc`
4.  **TeX / `pdflatex` (Recommended)** — Powers the deep semantic math validation (double subscripts, unbalanced braces, bad delimiters) run during ingestion. *Optional but recommended*: if `pdflatex` is absent, the system automatically falls back to lighter structural checks via `pylatexenc`.
    *   *Windows (Scoop)*: `scoop install miktex`
    *   *Windows (Choco)*: `choco install miktex`
    *   *macOS (Homebrew)*: `brew install --cask mactex-no-gui`
    *   *Linux (APT)*: `sudo apt-get install texlive-latex-extra`

### 2.3 Ollama Local Models
The offline transcription and semantic linking rely on Ollama running as a background service:
```powershell
ollama pull glm-ocr
ollama pull qwen3-embedding:0.6b
```

---

## 3. Deployment

The installer copies `skills/` and `bin/` **side by side** into a target directory, along with `requirements.txt`, `.env.example` and `config.yaml`. Each skill locates its helper scripts relative to itself, so **any** target works — just pick the directory your AI tool scans for skills:

| AI tool | Typical target |
|---|---|
| Claude Code | `~/.claude` (user-global) or `<project>/.claude` |
| Gemini / Antigravity | `<project>/.agents` or `~/.gemini` |

### Windows
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1                    # prompts for the target, or: .\install.ps1 -Target <dir>
```

### Linux / macOS
```bash
bash install.sh                  # prompts for the target
bash install.sh ~/.claude        # or pass it non-interactively
```

---

## 4. Chronological Academic Literature Lifecycle

Once the skills are loaded into your AI assistant, you can manage the entire literature pipeline using explicit **slash commands** (`/wiki_xxx`) directly in your assistant's chat UI. 

Below is the chronological lifecycle of building and maintaining your knowledge base:

### 📥 Phase 1: Setup & Initialization
*   **Central Hub Creation**
    *   *Situation*: You want to establish a central root directory to host and register multiple topic wikis.
    *   *Slash Command*: Run `/wiki_hub_init` under your desired parent folder (e.g. `~/KnowledgeHub`).
    *   *Expected Result*: Bootstraps a global `topics/` directory and a `wikis.json` registry file to track all future topics.
*   **Topic Workspace Creation**
    *   *Situation*: You are starting research on a new scientific subject (e.g. Quantum Computing) and need a dedicated workspace.
    *   *Slash Command*: Create a subfolder under topics (e.g. `~/KnowledgeHub/topics/quantum-computing`), open it, and type `/wiki_init` in the chat UI.
    *   *Expected Result*: Instantly generates the standardized workspace subdirectories (`raw/`, `wiki/`, `inbox/`, `output/`), creates the baseline configuration files (`config.md`, `log.md`, `_index.md`), and registers the new topic vault in the central Hub.

### 📄 Phase 2: Ingestion & Digitalization
*   **Processing Pending Literature**
    *   *Situation*: You have messy raw papers (PDFs/LaTeX preprints) inside the workspace's `inbox/` directory.
    *   *Slash Command & Configuration*:
        *   **Cloud Layout Parser (Highly Recommended)**: Register at [mineru.net](https://mineru.net) to get your MinerU API token. Fill it inside the active `config.yaml` file in the agent directory:
            ```yaml
            ocr:
              mineru_api_token: "YOUR_MINERU_API_TOKEN"
              use_mineru: true
            ```
            Then type `/wiki_ingest` in the chat UI.
        *   **Offline Local Parser (Fallback)**: If you prefer full offline operation, ensure you have pulled Ollama's local OCR model (`ollama pull glm-ocr`) and type `/wiki_ingest_ocr` in the chat UI.
    *   *Expected Result*: Transcribes complex layouts and mathematical formulas into pristine Markdown files inside `raw/articles/` and `raw/papers/`.

### 🔬 Phase 3: Deep Compilation & Concept Extraction
*   **Card Compilation**
    *   *Situation*: Raw markdown articles are generated in `raw/`, and you want to extract structured literature notes and concept cards.
    *   *Slash Command*: Type `/wiki_compile` in the chat UI.
    *   *Expected Result*: Extracts novel physical or mathematical terms, formulas, and definitions into separate cards under `wiki/concepts/`, and creates formal literature index cards under `wiki/references/`.
*   **Semantic Enrichment**
    *   *Situation*: You want to deeply inspect the compiled literature notes to ensure no critical mathematical lemmas, proofs, or theorems were missed.
    *   *Slash Command*: Type `/wiki_enrich` in the chat UI.
    *   *Expected Result*: AI scans the literature note's text, automatically extracts missing equations and definitions, and generates supplementary concept cards under `wiki/concepts/`.

### 🔗 Phase 4: Linking, Validation & Ontology Synchronization
*   **Semantic Embedding Links**
    *   *Situation*: You want to automatically discover hidden mathematical relationships and cross-references between concept cards.
    *   *Slash Command*: Type `/wiki_semantic_link` in the chat UI.
    *   *Expected Result*: Generates vector embeddings for all cards using Ollama's embedding model, calculates cosine similarity, appends a beautifully formatted `[[Related Concepts]]` section to the bottom of matching cards, and automatically merges duplicate concepts with a cosine similarity of $\ge 0.95$.
*   **Tag Normalization**
    *   *Situation*: Overlapping, redundant, or synonymous tags are cluttering your metadata.
    *   *Slash Command*: Type `/wiki_tag_sync` in the chat UI.
    *   *Expected Result*: standardizes tags into a unified, clean ontology whitelist across all cards using a Map-Reduce agent architecture.
*   **Concept Deduplication & Physical Merging**
    *   *Situation*: Duplicate or highly overlapping concepts exist under slightly different names.
    *   *Slash Command*: Type `/wiki_concept_sync` in the chat UI.
    *   *Expected Result*: Triggers a zero-hallucination physical merging engine that safely consolidates card files, appends aliases in the frontmatter, and redirects references globally.
*   **Vault Integrity Check & Auto-Healing**
    *   *Situation*: You want to validate that all mathematical formulas compile correctly and all double-bracket `[[wikilinks]]` are active.
    *   *Slash Command*: Type `/wiki_lint` in the chat UI.
    *   *Expected Result*: Verifies the entire workspace, auto-heals dead/broken links to their new canonical targets using global alias maps, repairs unescaped backslashes in frontmatter YAML, and compiles LaTeX formulas to verify syntax correctness.
*   **Knowledge Graph Database Synchronization**
    *   *Situation*: You want to update the relationship index database for fast semantic queries.
    *   *Slash Command*: Type `/wiki_graph_index` in the chat UI.
    *   *Expected Result*: Rebuilds the SQLite `graph.db` database inside the topic's `output/` directory, mapping all double-bracket linkages for relational SQL graph queries.

### 💬 Phase 5: Q&A, Contradiction Audit & Research Synthesis
*   **Strict Hallucination-Free Q&A**
    *   *Situation*: You want to query your knowledge vault and get exact answers backed by mathematical proofs.
    *   *Slash Command*: Type `/wiki_ask` in the chat UI followed by your question (e.g. `/wiki_ask "What is the relation between theory A and theorem B?"`).
    *   *Expected Result*: Runs a unified Vector RAG + Graph SQL relation search, producing a highly precise answer strictly cited with `[[wikilinks]]` directly to your cards.
*   **Theoretical Inconsistency Audit**
    *   *Situation*: You want to check if different papers or theories in your vault make conflicting claims.
    *   *Slash Command*: Type `/wiki_audit` in the chat UI.
    *   *Expected Result*: Spawns parallel agents to cross-compare literature notes, outputting a structured report listing potential scientific contradictions or mismatched assumptions.
*   **Academic Synthesis & Literature Reviews**
    *   *Situation*: You want a comprehensive, multi-perspective literature review or research synthesis paper on a complex query.
    *   *Slash Command*: Type `/wiki_research` followed by your query in the chat UI.
    *   *Expected Result*: Launches specialized research subagents that compile a complete, publication-grade academic review in the `output/` directory.

### 🧹 Phase 6: Long-term Maintenance & Hub Archiving
*   **Hub Topic Archiving**
    *   *Situation*: A research topic is complete, and you want to clean up your active workspace without losing files.
    *   *Slash Command*: Type `/wiki_hub_manager` in the chat UI to archive the topic.
    *   *Expected Result*: Packages and moves the specific topic directory to `topics/.archive/` and updates the central hub registry `wikis.json`. The topic can be fully restored at any time.

---

## 5. Obsidian Workspace Integration & Configuration

To visualize your knowledge vault beautifully in Obsidian, import the **specific topic directory** (e.g. `~/KnowledgeHub/topics/quantum-computing`), **not** the Hub root directory.

### ⚙️ Hiding System and Index Files from Graph & Search
Because the workspace contains autogenerated indexes, agent action logs, and runtime configs, you must hide them in Obsidian to ensure your **Graph View** and **Global Search** display only pure mathematical concepts and literature cards.

1.  Open Obsidian and navigate to **Settings** -> **Files and links** (设置 -> 档案与链接).
2.  Locate the **Excluded files** (排除档案) setting.
3.  Add the following regular expressions (or click "Add new" and paste them):

*   **Exclude Specific Metadata Markdown Files**:
    ```regex
    ^(?:_index|log|config|uncompiled-source-coverage)\.md$
    ```
    *(This instantly hides all autogenerated directory indices, action logs, configs, and literature backlog tracking files).*

*   **Exclude Dot Directories & System Files**:
    ```regex
    ^\..*
    ```
    *(This explicitly excludes agent runtime directories like `.agents/`, `.git/`, `.backup/`, and related hidden metadata files).*

Once applied, Obsidian's search, backlinks, and graph representation will remain absolutely clean, leaving you with a pristine, beautiful mathematical/physical knowledge graph.
