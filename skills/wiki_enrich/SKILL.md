---
name: wiki_enrich
description: "Act as a Concept Miner to inspect compiled papers, check concept linkage density, and spawn subagents to extract missing mathematical and physical concepts."
commands:
  enrich: "Inspect a compiled paper for concept density and dynamically mine missing concepts from the raw source."
---

# LLM Wiki — Enrich Skill (wiki_enrich)

This skill handles "gap-filling" for concept extraction. Due to token limits, initial compilations might miss secondary theorems, lemmas, or physics corollaries. This skill ensures high concept density.

When the user asks to enrich, deep-dive, or查漏补缺 (fill gaps) on a paper:
1.  **Idempotency Check (Main Agent)**:
    *   Read the target compiled paper's YAML frontmatter.
    *   If `enriched: <date>` is present, inform the user the paper was already enriched on that date. Only proceed if the user explicitly forces re-enrichment.

2.  **Density Check (Main Agent — DETERMINISTIC SCRIPT)**:
    *   Run the deterministic density counter — do NOT count links manually:
        `python $HOME/.gemini\config\bin\llm-wiki.py stats <TOPIC_DIR> concept-density "<compiled_file>"`
    *   Read the JSON output. Proceed to enrichment if `total_wikilinks < 5` OR `density_per_1k_words < 2.0`.
    *   Otherwise, inform the user the density is sufficient, unless they force enrichment.

3.  **Chunk & Assign (Main Agent)**:
    *   Locate the corresponding raw source file in `raw/papers/`.
    *   Logically divide the raw paper into discrete sections (e.g., Section 2: Theoretical Framework, Section 3: Experiments).

4.  **Parallel Mining (Subagents)**:
    *   Use the `invoke_subagent` tool to spawn multiple "Concept Miner" subagents.
    *   Assign each subagent a specific, localized chunk of the raw text.
    *   Instruct them to deeply extract *only* mathematical axioms, theoretical models, theorems, and boundary conditions that are NOT already present in the initial compilation.
    *   **Subagent Output Contract (MANDATORY)**: Each subagent MUST return findings as a structured list:
        ```
        CONCEPT: <concept name>
        SECTION: <section of raw source where found>
        VERBATIM_QUOTE: "<exact quote from raw source proving concept exists>"
        ```
        The main agent MUST verify each `VERBATIM_QUOTE` appears in the raw source file (using `grep_search` or `view_file`). Reject any concept whose quote cannot be found — it is likely hallucinated.

5.  **Synthesize & Append**:
    *   Wait for all subagents to report back. If any subagent fails, log the failure and proceed with available results.
    *   Filter out duplicates and synthesize the newly discovered concepts.
    *   Edit the target compiled paper in `wiki/references/`, appending these new concepts using strict `[[Concept]]` formatting under the appropriate sections.

6.  **Post-Enrichment Verification (MANDATORY)**:
    *   Run the reference verifier to check that all new `[[Concept]]` links point to existing files:
        `python $HOME/.gemini\config\bin\llm-wiki.py stats <TOPIC_DIR> verify-refs "<compiled_file>"`
    *   If `dangling_count > 0`, you MUST create concept files for each dangling reference (at minimum with correct frontmatter and a core definition section). Do NOT leave orphan links.

7.  **Mark Enriched**: Add or update `enriched: YYYY-MM-DD` in the compiled paper's YAML frontmatter.

8.  **Log**: Update the activity log `log.md` with: paper enriched, concepts added count, dangling refs resolved count.
