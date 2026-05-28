---
name: wiki_compile
description: "Compile raw sources into detailed, Obsidian-compatible, interlinked Markdown pages under wiki/ references/ and concepts/."
commands:
  compile: "Compile raw sources into detailed, high-density, interlinked Markdown wiki pages."
---

# LLM Wiki — Compile Skill (wiki_compile)

This skill handles the AI-driven "compilation" of high-entropy raw source texts into beautiful, structured, and interconnected literature cards and concept sheets.

When the user asks to compile the wiki or process raw files, follow this parallelized workflow:

### Phase 1: Preparation
1.  **Detect Uncompiled Sources**: Scan `raw/` for text documents that do not yet have corresponding compiled notes under `wiki/references/`.

### Phase 2: Parallel Compilation (Subagents)
2.  **Invoke Subagents**: Use the `invoke_subagent` tool (using `TypeName: "self"`) to spawn one subagent per uncompiled raw file concurrently.
3.  **Subagent Task Instructions**: Instruct each subagent to process its specifically assigned raw file independently:
    *   **Strict Template Adherence**: Read the raw document and apply the template `<SKILL_DIR>/templates/paper_template.md`.
    *   **Ensure High-Density Output**:
        *   **No stubs**: The compiled markdown must have rich sections covering math formulas (LaTeX), experimental metrics, contributions, and critical limits.
        *   **Bidirectional Linking**: Apply standard Obsidian double bracket linking: `[[Concept]]` or `[[Concept|Alias]]`. Do NOT use standard markdown relative links for these.
        *   **Concept Extraction (Thread-Safe)**: To extract novel concepts, do NOT write directly to `wiki/concepts/`. Instead, use the provided script to safely append your perspective. For each extracted concept, run:
            `python .agents/bin/add_concept.py --name "Concept Name" --source "Source Paper Name" --content "Your detailed definition and perspective on this concept based on the paper you just read."`
            **CRITICAL**: If you cannot find a detailed mathematical or physical definition for a concept in the paper, you MUST use the exact placeholder: `[STUB: Awaiting synthesis]` as the content.
    *   **Write Compiled Files**: Save output ONLY under `wiki/references/`.
    *   **Report Status**: The subagent must report back to the main agent once the reference file is written and all concepts are extracted via the script.

### Phase 3: Coordination and Cleanup (Main Agent)
4.  **Wait for Completion**: The main agent must wait until all spawned subagents have successfully reported completion. If any subagent fails or times out, log the failure and continue.
5.  **Rebuild Navigation Indexes**: Run the index builder script to deterministically rebuild all `_index.md` files:
    `python .agents/bin/index_builder.py "<TOPIC_DIR>"`
6.  **Run Final Linting**: Run `python .agents/bin/llm-wiki.py lint --fix "<TOPIC_DIR>"` on the full topic workspace as a final structural pass.
7.  **Log Activity**: Log the compile event in `log.md`, including the count of successful vs. failed compilations.

