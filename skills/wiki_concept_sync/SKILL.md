---
name: wiki_concept_sync
description: "Deduplicates concepts, splits overly broad concepts, and synthesizes multi-source concept definitions by dynamically searching and analyzing all papers that reference them."
commands:
  sync_concept: "Synthesize a specific concept across all referencing papers."
  sync_all_concepts: "Run a global deduplication and refinement pass over all concepts."
---

# LLM Wiki — Concept Synthesizer Skill (wiki_concept_sync)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill maintains the semantic integrity and comprehensive depth of the knowledge graph's "Concept" nodes. It resolves duplicate concepts, expands overly broad concepts, and, most importantly, synthesizes multi-source definitions by reading all papers that reference a concept.

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Where it says *file-read tool*, use your agent's equivalent (`Read` in Claude Code, `view_file` in Antigravity). Shell commands run via `Bash`/`PowerShell` (Claude Code) or your framework's shell tool.

## Execution Modes

The user can ask to refine/sync a **single concept** (e.g., `wiki_concept_sync "Quantum Entanglement"`) or run a **global sync** (`wiki_concept_sync_all`). If not specified, default to asking the user or assuming the concept currently being discussed.

### Phase 1: Deduplication Discovery
1.  **Semantic Duplicates Search**: Run the semantic linker in deduplication-only mode to find highly identical concepts:
    `python <SKILLS>/wiki_semantic_link/semantic_linker.py <TOPIC_DIR> --dedup-only`
    The merge threshold is read from `config.yaml`. Override via `--merge-threshold <value>` if needed.
2.  **Agent Review**: Carefully review the `[MERGE_SUGGESTION]` output logs from the script.
3.  **Resolve & Merge (Principle)**: If you verify that a pair is genuinely the same or strongly overlapping, choose a canonical name. **CRITICAL PRINCIPLE**: Always merge sub-concepts into their parent concepts (e.g., merge `gauge_redundancy` into `gauge_symmetry`). The parent concept becomes the Canonical Name.
4.  **Refactor Links**: Run the deterministic python script to safely update all `[[Old Concept]]` links to `[[Canonical Name]]`, handle backups, and delete the old concept automatically:
    `python <BIN>/refactor_concept.py --topic-dir "<TOPIC_DIR>" --old "Old Concept" --new "Canonical Name"`
    *(This script will also automatically rebuild the SQLite knowledge graph and markdown indexes upon completion).*

### Phase 2: Multi-Source Synthesis (Post-Merge RAG)
After resolving duplicates, you must synthesize their definitions to ensure no knowledge is lost.
1.  **Extract RAG Context**: Run the context extractor script to globally search all references for this Canonical Concept and compile the surrounding paragraphs:
    `python <BIN>/extract_concept_context.py --name "Canonical Name" --topic-dir "<TOPIC_DIR>"`
    This script will output the path to a `scratch/concept_context_<slug>.md` file.
2.  **Single-Pass Reading**: Use your **file-read tool** to read the generated context file.
3.  **Comprehensive Synthesis**:
    *   **Backup Before Rewrite**: Backup the concept file to `wiki/concepts/.backup/`.
    *   Rewrite `wiki/concepts/<Canonical Name>.md` to fuse the definitions, ensuring no loss of detail from the merged duplicate.
    *   **Post-Write Validation**: Run `python <BIN>/llm-wiki.py lint <TOPIC_DIR>`.
4.  **Log**: Update `log.md` with the deduplication and synthesis outcome.

