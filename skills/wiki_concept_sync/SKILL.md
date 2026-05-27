---
name: wiki_concept_sync
description: "Deduplicates concepts, splits overly broad concepts, and synthesizes multi-source concept definitions by dynamically searching and analyzing all papers that reference them."
commands:
  sync_concept: "Synthesize a specific concept across all referencing papers."
  sync_all_concepts: "Run a global deduplication and refinement pass over all concepts."
---

# LLM Wiki — Concept Synthesizer Skill (wiki_concept_sync)

This skill maintains the semantic integrity and comprehensive depth of the knowledge graph's "Concept" nodes. It resolves duplicate concepts, expands overly broad concepts, and, most importantly, synthesizes multi-source definitions by reading all papers that reference a concept.

## Execution Modes

The user can ask to refine/sync a **single concept** (e.g., `wiki_concept_sync "Quantum Entanglement"`) or run a **global sync** (`wiki_concept_sync_all`). If not specified, default to asking the user or assuming the concept currently being discussed.

### Phase 1: Discovery & Deduplication (Global Only)
1.  **Scan**: List all concept files in `wiki/concepts/`.
2.  **Semantic Merge**: Identify semantically identical concepts (e.g., `Neural_Network.md` and `Artificial_Neural_Networks.md`).
3.  **Resolve**: Choose a canonical name. Merge the content into the canonical file.
4.  **Backup Before Delete (MANDATORY)**: Before deleting any file, copy it to `wiki/concepts/.backup/` with a timestamped suffix (e.g., `Neural_Network_2026-05-26.md`). Create the `.backup/` directory if it does not exist.
5.  **Refactor Links**: Use `grep_search` across `wiki/` to find all `[[Old Concept]]` links. Then use the `replace_file_content` or `multi_replace_file_content` tool to update each file that contains the old link. Only after all references have been updated, delete the duplicate file (after backup per step 4).
6.  **Idempotency Check**: Before merging, check if `wiki/concepts/.backup/` already contains a backup for this concept from a previous run. If so, skip the merge and log that it was already processed.

### Phase 2: Breadth Analysis (Sub-Concept Splitting)
1.  **Evaluate**: Assess if the target concept is too broad (e.g., "Machine Learning") but lacks detailed sub-concept links.
2.  **Split**: If it's a broad umbrella, extract specific subtypes mentioned in the content. Create new concept files for these subtypes and update the origin papers to link to the more precise sub-concepts rather than just the umbrella term.

### Phase 3: Multi-Source Synthesis (Core Function)
This phase builds a comprehensive definition of a concept by reading every paper that mentions it.
1.  **Search References**: Use the `grep_search` tool to find all occurrences of `[[Concept Name]]` within the `wiki/references/` directory.
2.  **Parallel Subagent Mining**:
    *   For *each* paper found, use `invoke_subagent` to spawn a "Context Reader" subagent.
    *   **Prompt for Subagent**: "Read the following paper. Extract exactly how 'Concept Name' is defined, applied, or modified in the specific context of this paper. Return a focused summary of its role here."
3.  **Comprehensive Synthesis**:
    *   Wait for all subagents to report back. If any subagent fails, log the failure and proceed with available results.
    *   **Backup Before Rewrite (MANDATORY)**: Before rewriting any concept file, copy the current version to `wiki/concepts/.backup/<filename>_<YYYY-MM-DD>.md`.
    *   Rewrite the `wiki/concepts/<Concept Name>.md` file.
    *   **Structure**: Ensure the new file adheres to the Concept Template (e.g., `## 1. Core Definition & Physical Intuition`, `## 2. Mathematical Formalism`). 
    *   **Multi-Perspective Citing**: Integrate the subagent findings into a "Cross-Reference Applications" section. Explicitly state how the concept is used differently across the papers (e.g., "In [[Paper A]], it serves as a boundary condition, while [[Paper B]] extends it to...").
    *   **Post-Write Validation**: Run `python .agents/bin/llm-wiki.py lint <TOPIC_DIR>` to verify the rewritten file passes structural checks.
4.  **Log**: Update `log.md` with the synthesis outcome, listing which concepts were merged/rewritten/split.

