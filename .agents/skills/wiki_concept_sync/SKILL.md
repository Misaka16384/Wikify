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

### Stage 2: Semantic Collision Discovery (Semantic Link)

Now that the YAML metadata is pristine, the semantic linker can utilize the normalized tags and aliases to apply `+0.05` Tag Boosts and `+0.10` Alias Crossmatch Boosts.

1.  **Update Cache & Calculate**: Run the semantic linker in deduplication mode.
    `python .agents/skills/wiki_semantic_link/semantic_linker.py <TOPIC_DIR> --dedup-only --merge-threshold 0.80`
2.  **Semantic Collision Hook**: Read the console output. Extract all `[MERGE_SUGGESTION]` pairs.
3.  **Consolidate Targets**: Combine the suspects from Stage 1 (Alias Collisions) and Stage 2 (Semantic Collisions) into a final deduplication target list.

---

### Stage 3: Physics Merging & Synthesis (Concept Merge)

For every pair of duplicate concepts in your final target list:

1.  **Resolve & Merge (Principle)**: Choose a canonical name. **CRITICAL PRINCIPLE**: Always merge sub-concepts into their parent concepts (e.g., merge `gauge_redundancy` into `gauge_symmetry`). The parent concept becomes the Canonical Name.
2.  **Refactor & Concatenate**: Run the deterministic python script to safely update all `[[Old Concept]]` links to `[[Canonical Name]]`, merge their frontmatter tags, append the old concept's text body to the new concept's body, and handle deletions automatically:
    `python .agents/bin/refactor_concept.py --topic-dir "<TOPIC_DIR>" --old "Old Concept" --new "Canonical Name"`
3.  **No LLM Synthesis Needed**: The script automatically stitches the contents. Do NOT spawn subagents or attempt to manually read/rewrite the files via LLM.
4.  **Post-Write Validation**: Once all merges are complete, run the global linter.
    `python .agents/bin/llm-wiki.py lint <TOPIC_DIR>`

### 4. Final Reporting
Update `log.md` with the number of tags normalized, and list the exact concept merges that were executed. Present a detailed success summary to the user.
