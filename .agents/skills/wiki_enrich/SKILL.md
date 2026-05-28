---
name: wiki_enrich
description: "Act as a Concept Miner to inspect compiled papers, check concept linkage density, and spawn subagents to extract missing mathematical and physical concepts."
commands:
  enrich: "Inspect a compiled paper for concept density and dynamically mine missing concepts from the raw source."
---

# LLM Wiki — Enrich Skill (wiki_enrich)

This skill handles "gap-filling" for concept extraction. Due to token limits, initial compilations might miss secondary theorems, lemmas, or physics corollaries. This skill ensures high concept density.

When the user asks to enrich, deep-dive, or查漏补缺 (fill gaps) on a paper:
0.  **Target Selection (Fallback)**:
    *   If the user does not specify a target paper, run the following command to analyze the wiki structure:
        `python .agents/bin/llm-wiki.py stats <TOPIC_DIR> wiki-summary`
    *   Parse the JSON output and automatically select the paper under `wiki/references/` with the lowest `wikilinks` count as your target.

1.  **Idempotency Check (Main Agent)**:
    *   Read the target compiled paper's YAML frontmatter.
    *   If `enriched: <date>` is present, inform the user the paper was already enriched on that date. Only proceed if the user explicitly forces re-enrichment.

2.  **Density Check (Main Agent — DETERMINISTIC SCRIPT)**:
    *   Run the deterministic density counter — do NOT count links manually:
        `python .agents/bin/llm-wiki.py stats <TOPIC_DIR> concept-density "<compiled_file>"`
    *   Read the JSON output. Proceed to enrichment if `total_wikilinks < 5` OR `density_per_1k_words < 2.0`.
    *   Otherwise, inform the user the density is sufficient, unless they force enrichment.

3.  **Chunk & Assign (Main Agent)**:
    *   Locate the corresponding raw source file in `raw/papers/`.
    *   Run the deterministic chunking script to automatically divide the large raw file into smaller pieces in the `scratch/` directory:
        `python .agents/bin/chunker.py "path/to/raw/file.md" --topic-dir "<TOPIC_DIR>"`
    *   The script will output the number of chunks created.

4.  **Parallel Mining (Subagents)**:
    *   Use the `invoke_subagent` tool to spawn one "Concept Miner" subagent per chunk.
    *   Assign each subagent a specific chunk from the `scratch/` directory.
    *   Instruct them to deeply extract *only* mathematical axioms, theoretical models, theorems, and boundary conditions that are NOT already present in the initial compilation.
    *   **Subagent Output Contract**: For each discovered concept, the subagent MUST securely register it using the centralized concept addition script:
        `python .agents/bin/add_concept.py --name "Concept Name" --source "Source Paper Name" --content "Detailed quote and explanation from the chunk."`
    *   The subagents should also report the names of the concepts they discovered in their response message to the main agent.

5.  **Synthesize & Append**:
    *   Wait for all subagents to report back. If any subagent fails, log the failure and proceed with available results.
    *   Collect the names of the newly discovered concepts from the subagent reports.
    *   Edit the target compiled paper in `wiki/references/`, safely appending a new section at the very bottom (do NOT surgically splice into existing paragraphs):
        ```markdown
        ## 5. Enriched Secondary Concepts
        *   [[New Concept A]]
        *   [[New Concept B]]
        ```

6.  **Post-Enrichment Verification (MANDATORY)**:
    *   Run the reference verifier to check that all new `[[Concept]]` links point to existing files:
        `python .agents/bin/llm-wiki.py stats <TOPIC_DIR> verify-refs "<compiled_file>"`

7.  **Mark Enriched**: Add or update `enriched: YYYY-MM-DD` in the compiled paper's YAML frontmatter.

8.  **Log**: Update the activity log `log.md` with: paper enriched, concepts added count, dangling refs resolved count.
