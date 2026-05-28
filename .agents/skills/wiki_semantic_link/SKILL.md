---
name: wiki_semantic_link
description: "Automatically builds semantic links between concept markdown files by calculating vector similarity using a local Ollama embedding model."
commands:
  link_concepts: "Run the semantic linker over all concepts in the wiki to build semantic relationships."
---

# LLM Wiki — Semantic Linker Skill (wiki_semantic_link)

This skill scans all markdown files within the `wiki/concepts/` directory, extracts their text, and generates embeddings using a local Ollama model (default: `qwen3-embedding:0.6b`). It then calculates pairwise cosine similarity between all concepts and automatically injects bi-directional Obsidian-style links (`[[Concept Name]]`) for pairs that exceed a given similarity threshold.

## Execution

This skill is executed via the Python script located within the skill directory:

```bash
python .agents/skills/wiki_semantic_link/semantic_linker.py <TOPIC_DIR> [--threshold 0.85] [--model qwen3-embedding:0.6b]
```

## Internal Phases

### Phase 1: Preparation & Backup
1. Identifies the `wiki/concepts/` directory within the given `<TOPIC_DIR>`.
2. **MANDATORY**: Copies all `.md` files to `wiki/concepts/.backup/` before proceeding, ensuring no data loss in case of a bad threshold.

### Phase 2: Embedding Generation
1. Reads all concept markdown files.
2. Strips existing YAML frontmatter and internal links to focus on the pure definition/content for unbiased embeddings.
3. Calls the local Ollama instance (`http://localhost:11434/api/embeddings`) to generate vector representations.

### Phase 3: Similarity Calculation & Filtering
1. Uses `scikit-learn` to compute a Cosine Similarity matrix for all generated vectors.
2. Filters out identical pairs (similarity = 1.0, i.e., self-links) and pairs below the defined threshold (e.g., `< 0.85`).

### Phase 4: Idempotent Injection
1. For every highly-related pair `(A, B)` (where `score >= threshold`), checks if `A.md` already contains `[[B]]`.
2. If not, it safely injects it at the bottom under the heading `## 语义关联 (Semantic Links)`.

### Phase 5: Global Validation
1.  **Global Validation (MANDATORY)**: Since multiple concept files have been modified, run the global static linter to verify the overall integrity of the wiki:
    `python .agents/bin/llm-wiki.py lint <TOPIC_DIR>`

*Note: This skill no longer handles merge suggestions. Deduplication is strictly handled by the `wiki_concept_sync` skill.*
