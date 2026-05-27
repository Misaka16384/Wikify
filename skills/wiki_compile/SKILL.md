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
    *   **Strict Template Adherence**: Read the raw document and apply the templates stored inside this skill directory:
        *   `<SKILL_DIR>/templates/paper_template.md` (for academic papers)
        *   `<SKILL_DIR>/templates/concept_template.md` (for new theories or terms)
    *   **Ensure High-Density Output**:
        *   **No stubs**: The compiled markdown must have rich sections covering math formulas (LaTeX), experimental metrics, contributions, and critical limits.
        *   **Bidirectional Dual-Linking**: Apply Obsidian-compatible double bracket linking: `[[Concept|Name]] ([Name](../concepts/concept.md))`.
    *   **Write Compiled Files**: Save output under `wiki/references/` and `wiki/concepts/` respectively.
    *   **Post-Write Validation (MANDATORY)**: After writing each file, the subagent MUST run:
        `python .agents/bin/llm-wiki.py lint <TOPIC_DIR>`
        If lint reports critical or warning issues for the file just written, the subagent MUST fix them before reporting success.
    *   **Report Status**: The subagent must report back to the main agent once the markdown file has been successfully written AND lint-validated.

### Phase 3: Coordination and Cleanup (Main Agent)
4.  **Wait for Completion**: The main agent must wait until all spawned subagents have successfully reported completion. If any subagent fails or times out, log the failure and continue with the remaining files — do NOT silently drop failures.
5.  **Rebuild Navigation Indexes**: Refresh the directory `_index.md` navigation files utilizing `<SKILL_DIR>/templates/index_template.md`.
6.  **Run Final Linting**: Run `python .agents/bin/llm-wiki.py lint --fix` on the full topic workspace as a final structural pass.
7.  **Log Activity**: Log the compile event in `log.md`, including the count of successful vs. failed compilations.

