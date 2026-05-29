---
name: wiki_enrich
description: "Act as a Concept Miner to inspect compiled papers, check concept linkage density, and spawn subagents to extract missing mathematical and physical concepts."
commands:
  enrich: "Inspect a compiled paper for concept density and dynamically mine missing concepts from the raw source."
---

# LLM Wiki — Enrich Skill (wiki_enrich)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill handles "gap-filling" for concept extraction. Due to token limits, initial compilations might miss secondary theorems, lemmas, or physics corollaries. This skill ensures high concept density.

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Map each capability to your own agent's tool — *read-file* (`Read` in Claude Code, `view_file` in Antigravity), *sub-agent / parallel task* (`Task`/`Agent` in Claude Code, `invoke_subagent` in Antigravity), *shell* (`Bash`/`PowerShell`). Use the closest equivalent your framework provides; if a parallel sub-agent tool is unavailable, mine the chunks sequentially yourself.

When the user asks to enrich, deep-dive, or查漏补缺 (fill gaps) on a paper:
1.  **Idempotency Check (Main Agent)**:
    *   Read the target compiled paper's YAML frontmatter.
    *   If `enriched: <date>` is present, inform the user the paper was already enriched on that date. Only proceed if the user explicitly forces re-enrichment.

2.  **Density Check (Main Agent — DETERMINISTIC SCRIPT)**:
    *   Run the deterministic density counter — do NOT count links manually:
        `python <BIN>/llm-wiki.py stats <TOPIC_DIR> concept-density "<compiled_file>"`
    *   Read the JSON output. Proceed to enrichment if `total_wikilinks < 5` OR `density_per_1k_words < 2.0`.
    *   Otherwise, inform the user the density is sufficient, unless they force enrichment.

3.  **Chunk & Assign (Main Agent)**:
    *   Locate the corresponding raw source file in `raw/papers/`.
    *   Run the deterministic chunking script to automatically divide the large raw file into smaller pieces in the `scratch/` directory:
        `python <BIN>/chunker.py "path/to/raw/file.md" --topic-dir "<TOPIC_DIR>"`
    *   The script will output the number of chunks created.

4.  **Parallel Mining (Subagents)**:
    *   Use your agent's **sub-agent / parallel-task tool** to spawn one "Concept Miner" sub-agent per chunk (or process chunks sequentially if no sub-agent tool exists).
    *   Assign each subagent a specific chunk from the `scratch/` directory.
    *   Instruct them to deeply extract *only* mathematical axioms, theoretical models, theorems, and boundary conditions that are NOT already present in the initial compilation.
    *   **Subagent Output Contract**: For each discovered concept, the subagent MUST securely register it using the centralized concept addition script:
        `python <BIN>/add_concept.py --name "Concept Name" --source "Source Paper Name" --content "Detailed quote and explanation from the chunk."`
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
    *   Run the concept builder to sequentially generate any missing concept files correctly:
        `python <BIN>/index_builder.py "<TOPIC_DIR>"`
    *   Run the reference verifier to check that all new `[[Concept]]` links point to existing files:
        `python <BIN>/llm-wiki.py stats <TOPIC_DIR> verify-refs "<compiled_file>"`

7.  **Mark Enriched**: Add or update `enriched: YYYY-MM-DD` in the compiled paper's YAML frontmatter.

8.  **Log**: Update the activity log `log.md` with: paper enriched, concepts added count, dangling refs resolved count.
