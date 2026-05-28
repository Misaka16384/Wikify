---
name: wiki_tag_sync
description: "Deduplicates, normalizes, and reduces sprawling tags and aliases across the knowledge graph using a Map-Reduce architecture."
commands:
  sync_tags: "Normalize all tags and aliases in the current topic workspace."
---

# LLM Wiki — Tag & Alias Sync Skill (wiki_tag_sync)

This skill resolves the "vocabulary fragmentation" problem. Over time, different agents might invent slightly different tags or aliases for the exact same physical/mathematical concept (e.g., `qca`, `quantum-cellular-automata`, `clifford-qca`). This skill acts as a Map-Reduce pipeline to canonicalize them.

When the user asks to sync, reduce, deduplicate, or normalize tags and aliases:

### 1. Map Phase (Extraction)
*   **Action**: Run the deterministic python extractor to gather all unique metadata.
    `python .agents/bin/tag_reducer.py extract <TOPIC_DIR>`
*   **Result**: This will silently generate two statistical files:
    1. `<TOPIC_DIR>/scratch/raw_tags.json`
    2. `<TOPIC_DIR>/scratch/raw_aliases.json`

### 2. Reduce Phase (LLM Decision)
*   **Action**: Read the contents of both `raw_tags.json` and `raw_aliases.json` using the `view_file` tool.
*   **Logic (CRITICAL)**: Act as the "Reducer". Use your domain knowledge in physics and mathematics to analyze the raw lists:
    *   **For Tags**: Identify synonyms, acronyms, and plural/singular variations (e.g. mapping `gauge-theory` and `gauge-theories` to `gauge-theory`, or `qca` and `quantum-cellular-automata` to `qca`). Choose the most concise or highest-frequency term as the canonical tag.
    *   **For Aliases**: Identify extremely similar aliases and map them to a clean, canonical format.
    *   **Alias Collision Warning**: If you notice that two distinct sets of aliases are heavily overlapping (which implies two different files might be describing the exact same concept), you MUST print a bold `[MERGE WARNING]` to the user in your final response detailing the suspected duplicate files.
*   **Output generation**: Create two mapping files in the `scratch/` directory.
    1. Write `<TOPIC_DIR>/scratch/tag_mapping.json`:
       ```json
       {
         "tags": {
           "quantum-cellular-automata": "qca",
           "clifford-qca": "qca"
         }
       }
       ```
    2. Write `<TOPIC_DIR>/scratch/alias_mapping.json`:
       ```json
       {
         "aliases": {
           "Z2 QCA": "Z_2 QCA"
         }
       }
       ```
    *Note: You only need to include tags/aliases in the mapping JSON if they are actually being changed. You do not need to map a tag to itself.*

### 3. Apply Phase (Global Replacement)
*   **Action**: Run the python apply script to rewrite the frontmatter of all affected Markdown files safely:
    `python .agents/bin/tag_reducer.py apply <TOPIC_DIR> <TOPIC_DIR>/scratch/tag_mapping.json <TOPIC_DIR>/scratch/alias_mapping.json`
*   **Result**: The script will update the YAML frontmatter across the vault and generate a final `wiki/ontology.txt` file containing the canonical whitelisted tags.

### 4. Semantic Linker Integration (Optional but Recommended)
*   After applying the new tags, ask the user if they want to re-run the `wiki_semantic_link` skill, as the newly normalized tags and aliases will now provide a massive accuracy boost to the semantic similarity engine.
