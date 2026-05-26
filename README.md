# Gemini Agentic Wiki Skills — GitHub Release

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Model: GLM-OCR](https://img.shields.io/badge/Model-GLM--OCR-orange.svg)](https://ollama.com/)

An enterprise-grade, agentic markdown-based knowledge management and compilation pipeline for high-entropy **mathematical and physical academic literature**. Designed specifically for autonomous coding assistants (such as `Antigravity`), this repository provides a suite of 14 highly hardened, portable, and script-validated skills that automatically ingest, compile, sync, enrich, and audit dense academic sources.

---

## 1. System Dependencies

Before deploying the skills, ensure the target system has the following runtime dependencies installed.

### 1.1 Python Dependencies
The Python runtime requires **Python 3.10+** (supporting modern pattern matching and advanced type annotations). The third-party dependencies must be installed globally (no virtual environment is needed for global agent execution):

```powershell
pip install -r requirements.txt
```

**Required Packages (`requirements.txt`):**
*   `requests>=2.28.0` — Handles high-performance HTTP requests to the Ollama local model API.
*   `pillow>=9.0.0` — Coordinates localized OCR image resizing, preprocessing, and cropping.
*   `pyyaml>=6.0` — Loads configuration maps and parses Markdown frontmatter securely.
*   `pydantic>=2.0.0` — Enforces structural schemas on thesis and research outputs.
*   `rich>=13.0.0` — Drives beautiful console styling, layout logging, and progress rendering.
*   `pdf2image>=1.16.0` — Converts incoming PDF pages into high-fidelity raster images.

### 1.2 System-Level External Binaries
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

> [!IMPORTANT]
> Verify that the binaries are correctly added to your environment `PATH` by running `pdftoppm -v` and `rg --version` in your terminal.

### 1.3 Ollama Local visual OCR Engine
The local offline PDF-to-Markdown transcription relies on Ollama running as a background service (default: `http://127.0.0.1:11434`). Pull the required visual model:

```powershell
ollama pull glm-ocr
```

---

## 2. Step-by-Step Installation Guide

To deploy this suite of skills, follow these steps:

### Step 1: Download or Clone the Repository
Download this repository folder (`gemini-wiki-skills/`) or extract the `gemini-wiki-skills.zip` asset on your target machine.

### Step 2: Install System and Python Dependencies
1.  Install **Poppler** and **Ripgrep** (see Step 1.2).
2.  Start **Ollama** and run `ollama pull glm-ocr` in the terminal.
3.  Install the required Python modules globally:
    ```powershell
    pip install -r requirements.txt
    ```

### Step 3: Run the Automated PowerShell Installer
Execute the included installer script to automatically copy all skills and helper scripts into the canonical configuration directory (`$HOME/.gemini/config/`):

```powershell
# Set execution policy for the current session to bypass script restrictions
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Run the installer
.\install.ps1
```

### Step 4: Verify the Installation
Validate that the central command-line utility executes successfully:

```powershell
python "$HOME/.gemini/config/bin/llm-wiki.py" --help
```

---

## 3. Comprehensive Skill Directory

The repository contains **14 specialized skills** designed to handle academic ingestion, compilation, and semantic organization. They are deployed to `$HOME/.gemini/config/skills/` and work in tandem with the canonical scripts in `$HOME/.gemini/config/bin/`.

```
  Ingestion Phase (OCR)  →  Compilation Phase  →  Analysis & Sync  →  Auditing & Research
 [wiki_ingest / ocr_ingest]    [wiki_compile]      [wiki_concept_sync]    [wiki_audit / research]
```

### 3.1 Core Ingestion & Compilation Skills

#### 1. `wiki_ingest` (Multimodal Ingestion)
*   **Role**: Converts external files (notes, web articles, PDFs inside `inbox/`) into raw Markdown files under `raw/`.
*   **Math Ingestion Hardening**: Orchestrates PDF transcription by spawning parallel subagents (up to 10 concurrently) to transcribe pages using their native multimodal vision. Incorporates page count validation to prevent silent page truncation.
*   **Commands**: `ingest`

#### 2. `wiki_ingest_ocr` (Offline local OCR Ingestion)
*   **Role**: Performs high-fidelity offline PDF conversion utilizing the local `glm-ocr` model at 150 DPI. Saves API tokens and excels at mathematical equation transcription.
*   **Hardening**: Includes **sequential page-level JSON caching** (`.temp/page_{num}.json`). If the visual model or VRAM crashes midway, restarting skips already-processed pages, enabling instant, zero-token recovery.
*   **Commands**: `ingest_ocr`

#### 3. `wiki_compile` (Literature Compiler & Card Generator)
*   **Role**: Compiles raw ingested markdown into Obsidian-compatible literature cards (`wiki/references/`) and concept sheets (`wiki/concepts/`).
*   **Hardening**: Forces strict template validation. Newly compiled files must automatically pass a `llm-wiki.py lint` check before compilation reports success. Embedded **Convention Blocks** (`## 0. Conventions`) force subagents to document sign metric signatures, unit systems, and coordinate choices to prevent sign convention discrepancies.
*   **Commands**: `compile`

---

### 3.2 Semantic Enrichment & Sync Skills

#### 4. `wiki_enrich` (Concept Miner & Gap Filler)
*   **Role**: Mines secondary theorems, lemmas, and physics corollaries from raw sources to enrich existing literature cards.
*   **Hardening**: Uses a **deterministic density metric script** to skip manual link counting. Implements a strict subagent contract where mined concepts must be accompanied by a `VERBATIM_QUOTE` verified directly in the raw source, preventing mathematical hallucinations.
*   **Commands**: `enrich`

#### 5. `wiki_concept_sync` (Deduplication & Merge)
*   **Role**: Maintains the semantic integrity of the knowledge graph by deduplicating concepts and performing multi-source synthesis.
*   **Hardening**: Enforces mandatory automatic backup of files before executing destructive operations (file deletion or complete rewrites). Uses automated regex-escaping guards to prevent malformed symbolic concept titles (such as group symmetries or operator formulas) from crashing the parser.
*   **Commands**: `sync_concept`, `sync_all_concepts`

---

### 3.3 Auditing, Research & Navigation Skills

#### 6. `wiki_audit` (Vault Auditor & Thesis Generator)
*   **Role**: Executes vault-wide factual audits, cross-checks scientific claims, and synthesizes unified verdicts (Theses) under a Map-Reduce architecture.
*   **Hardening**: Feeds subagents with a deterministic JSON summary seed instead of relying on open-ended keyword guesses. Enforces structured subagent contracts and strict citation verification (asserts supporting quotes actually exist in source files).
*   **Commands**: `audit`

#### 7. `wiki_research` (Academic Researcher)
*   **Role**: Orchestrates background subagents to perform deep, multi-perspective academic research on specialized topics, gathering evidence locally and from the web.
*   **Hardening**: Restricts subagents from making claims from parametric memory alone. Filters out fabricated citations by validating sources against structural schemas via `validate-output.py`.
*   **Commands**: `research`

#### 8. `wiki_lint` (Structural Validator)
*   **Role**: Statically checks and repairs bidirectional linkages, path resolutions, and YAML frontmatter constraints across the entire workspace.
*   **Hardening**: Deploys an idempotent `--fix` engine that repairs broken metadata automatically. Incorporates checks against Windows-illegal filename characters in wikilinks to prevent target terminal execution crashes.
*   **Commands**: `lint`

#### 9. `wiki_router` (Workspace Path Resolver)
*   **Role**: Resolves workspace path slugs dynamically, converting user-provided relative directories or leading tildes to absolute system paths.
*   **Hardening**: Fully synchronized path resolution engine supporting absolute paths, tilde prefixes, and `<HUB>/` path conventions.
*   **Commands**: `route`

#### 10. `wiki_init` (Workspace Initializer)
*   **Role**: Bootstraps a fresh workspace directory with standard `raw/`, `wiki/`, and `inbox/` subfolders.
*   **Hardening**: Replaces free-form file generation with strict verbatim file templates for `config.md`, `log.md`, and `_index.md`.
*   **Commands**: `initialize`

---

### 3.4 Topic & Hub Lifecycle Skills

#### 11. `wiki_hub_init` (Central Registry Bootstrapper)
*   **Role**: Initializes a central registry Hub directory for managing multiple topic vaults.
*   **Hardening**: Validates `wikis.json` schema automatically on every run.

#### 12. `wiki_hub_list` (Registry Auditor)
*   **Role**: Lists all active and archived topics, auditing directories to register untracked workspaces.
*   **Hardening**: Incorporates robust error-handling for registry reading.

#### 13. `wiki_hub_archive` (Vault Archiver)
*   **Role**: Moves active topic workspaces to `.archive/` and updates registries.
*   **Hardening**: Restricts archiver from touching hub roots or running destructive operations on non-empty destinations.

#### 14. `wiki_hub_restore` (Vault Restorer)
*   **Role**: Restores archived topic workspaces back into the active Hub registry.
*   **Hardening**: Cleans up registry files and verifies destination paths safely before moving.

---

## 4. Key Hardened Core Helper Scripts (`bin/`)

These Python scripts provide the core logic invoked by the skills:

*   [llm-wiki.py](./bin/llm-wiki.py) — Enforces structural lint rules, registries, and stats.
    *   **LaTeX-Aware Word Count**: Dynamically strips LaTeX math blocks (inline `$`, block `$$`, and `align`/`equation` environments) before computing word count, preventing math code from distorting concept density metrics.
    *   **Filename & Formula Link Check**: Automatically raises warnings during linting if wikilinks contain Windows-illegal filename characters (`:`, `\`, `/`, etc.) or raw math formulas, blocking malformed nodes before they are written.
*   [validate-output.py](./bin/validate-output.py) — Validates output schemas.
    *   **Citation Exemption**: Exempts logical mathematical derivation and proof paragraphs from the "unsupported claims" warning. Paragraphs containing LaTeX elements or starting with math-proof transition keywords (e.g., *Proof*, *Let*, *Hence*, *Substituting*) are automatically exempted.
*   [format_math.py](./bin/format_math.py) — Spacing normalizer that ensures standard LaTeX math environments (`align`, `equation`, `gather`, `multline`) are cleanly isolated with double newlines, guaranteeing correct rendering in Obsidian.
