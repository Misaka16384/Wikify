---
name: wiki_concept_sync
description: "Master Orchestrator Pipeline: Deduplicates metadata (tags/aliases), discovers semantic collisions, and synthesizes redundant concepts across the entire knowledge vault."
commands:
  refactor_vault: "Run the full 3-Stage Vault Refactoring Pipeline (Tag Sync -> Semantic Link -> Concept Merge)."
  sync_concept: "Synthesize a specific concept across all referencing papers."
---

# LLM Wiki — Master Vault Refactoring Skill (wiki_concept_sync)

This skill is the **Master Orchestrator** for maintaining the semantic integrity and structural purity of the knowledge graph. It unifies metadata cleaning (`wiki_tag_sync`) and semantic collision detection (`wiki_semantic_link`) into a single deterministic pipeline, culminating in the physical merging and synthesis of duplicate concepts.

When the user asks to clean, refactor, deduplicate, or globally sync the vault, you MUST execute the following **3-Stage Pipeline** strictly in order.

---

### Stage 1: Metadata Normalization (Tag Sync)

1.  **Extract**: Run the tag extractor script to gather all unique metadata.
    `python .agents/bin/tag_reducer.py extract <TOPIC_DIR>`
2.  **LLM Map-Reduce**: Read `scratch/raw_tags.json` and `scratch/raw_aliases.json` via `view_file`.
    *   Analyze the tags and aliases to find synonyms, abbreviations, and plural/singular variations.
    *   **Alias Collision Hook (CRITICAL)**: If you notice that two distinct sets of aliases heavily overlap, these are highly likely identical physical concepts. Note their names down in your internal `Merge_Suspects` list.
    *   Create `scratch/tag_mapping.json` and `scratch/alias_mapping.json` with the reduced canonical mappings.
3.  **Apply**: Run the python apply script to normalize the vault's frontmatter.
    `python .agents/bin/tag_reducer.py apply <TOPIC_DIR> <TOPIC_DIR>/scratch/tag_mapping.json <TOPIC_DIR>/scratch/alias_mapping.json`

---

### Stage 2: Discover and Auto-Merge Semantic Collisions (Semantic Linker)

Use the local Ollama embedding engine to scan the entire workspace for semantic overlaps and auto-merge high-confidence identical concepts:
1. Run `python .agents/skills/wiki_semantic_link/semantic_linker.py "<TOPIC_DIR>" --dedup-only --auto-merge`
2. **Analysis**: The script will output a list of `[MERGE_SUGGESTION] A <--> B (Score)`. 
   - **Auto-Merged**: Any pair with a score >= 0.95 will be physically merged by the script automatically. You do not need to do anything for these.
   - **Manual Review**: Any pair with a score between 0.85 and 0.949 will remain unmerged. Note down these remaining high-score suggestions (e.g., >0.90) as your final target list for manual review.

---

### Stage 3: Physics Merging & Synthesis (Concept Merge)

For every pair of duplicate concepts in your final target list (the 0.85-0.949 range that you deem necessary to merge):

1.  **Resolve & Merge (Principle)**: Choose a canonical name. **CRITICAL PRINCIPLE**: Always merge sub-concepts into their parent concepts (e.g., merge `gauge_redundancy` into `gauge_symmetry`). The parent concept becomes the Canonical Name.
2.  **Refactor & Concatenate**: Run the deterministic python script to safely update all `[[Old Concept]]` links to `[[Canonical Name]]`, merge their frontmatter tags, append the old concept's text body to the new concept's body, and handle deletions automatically:
    `python .agents/bin/refactor_concept.py --topic-dir "<TOPIC_DIR>" --old "Old Concept" --new "Canonical Name"`
3.  **No LLM Synthesis Needed**: The script automatically stitches the contents. Do NOT spawn subagents or attempt to manually read/rewrite the files via LLM.
4.  **Post-Write Validation**: Once all merges are complete, run the global linter.
    `python .agents/bin/llm-wiki.py lint <TOPIC_DIR>`

### 4. Final Reporting
Update `log.md` with the number of tags normalized, and list the exact concept merges that were executed. Present a detailed success summary to the user.
