---
name: wiki_semantic_link
description: "Automatically builds semantic links between concept markdown files by calculating vector similarity using a local Ollama embedding model."
commands:
  link_concepts: "Run the semantic linker over all concepts in the wiki to build semantic relationships."
---

# LLM Wiki — Semantic Linker Skill (wiki_semantic_link)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill scans all markdown files within the `wiki/concepts/` directory, extracts their text, and generates embeddings using a local Ollama model (configured in `config.yaml`, default: `qwen3-embedding:0.6b`). It then calculates pairwise cosine similarity between all concepts and automatically injects bi-directional Obsidian-style links (`[[Concept Name]]`) for pairs that exceed a given similarity threshold.

## Execution

This skill is executed via the `magi link` command.

**Crucial Parameter Selection**:
Depending on the objective, you MUST use the correct parameters:
1. **Normal Link Injection**: If the user just wants to inject semantic links (default behavior):
   `magi link <TOPIC_DIR>`
   Model, threshold, and Ollama URL are read from `config.yaml`. Override via CLI flags if needed (e.g. `--threshold 0.80 --model <model>`).
2. **Deduplication Scan (Auto-Merge)**: If the user is running the `wiki_concept_sync` pipeline to merge duplicates:
   `magi link <TOPIC_DIR> --dedup-only --auto-merge`

> **Prerequisites**: Ensure the embedding model is available locally via `ollama pull <model>` (check `config.yaml` for the configured model name). Requires `numpy` and `scikit-learn` Python packages.

## Internal Phases

### Phase 1: Preparation & Backup
1. Identifies the `wiki/concepts/` directory within the given `<TOPIC_DIR>`.
2. **MANDATORY**: Copies all `.md` files to `wiki/concepts/.backup/` before proceeding, ensuring no data loss in case of a bad threshold.

### Phase 2: Embedding Generation
1. Reads all concept markdown files.
2. Strips existing YAML frontmatter and internal links to focus on the pure definition/content for unbiased embeddings.
3. Calls the local Ollama instance (configured in `config.yaml`) to generate vector representations.

### Phase 3: Similarity Calculation & Filtering
1. Uses `scikit-learn` to compute a Cosine Similarity matrix for all generated vectors.
2. Filters out identical pairs (similarity = 1.0, i.e., self-links) and pairs below the defined threshold (e.g., `< 0.85`).

### Phase 4: Idempotent Injection
1. For every highly-related pair `(A, B)` (where `score >= threshold`), checks if `A.md` already contains `[[B]]`.
2. If not, it safely injects it at the bottom under the heading `## 语义关联 (Semantic Links)`.

*Note: This skill no longer handles merge suggestions. Deduplication is strictly handled by the `wiki_concept_sync` skill.*
