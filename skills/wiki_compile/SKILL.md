---
name: wiki_compile
description: "Compile raw sources into detailed, Obsidian-compatible, interlinked Markdown pages under wiki/ references/ and concepts/."
commands:
  compile: "Compile raw sources into detailed, high-density, interlinked Markdown wiki pages."
---

# LLM Wiki — Compile Skill (wiki_compile)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill handles the AI-driven "compilation" of high-entropy raw source texts into beautiful, structured, and interconnected literature cards and concept sheets.

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Map each capability to your own agent's tool — *read-file* (`Read` in Claude Code, `view_file` in Antigravity), *sub-agent / parallel task* (`Task`/`Agent` in Claude Code, `invoke_subagent` in Antigravity), *web-search* (`WebSearch` in Claude Code, `search_web`), *shell* (`Bash`/`PowerShell`). Use the closest equivalent your framework provides; if a parallel sub-agent tool is unavailable, perform the steps sequentially yourself.

When the user asks to compile the wiki or process raw files, follow this parallelized workflow:

### Phase 1: Preparation
1.  **Detect Uncompiled Sources**: Scan `raw/` for text documents that do not yet have corresponding compiled notes under `wiki/references/`.

### Phase 2: Parallel Compilation (Subagents)
2.  **Invoke Subagents**: Use your agent's **sub-agent / parallel-task tool** (spawning a fresh self-instance per task) to process one uncompiled raw file per sub-agent, concurrently. If your framework has no sub-agent tool, process the files sequentially yourself.
3.  **Subagent Task Instructions**: Instruct each subagent to process its specifically assigned raw file independently:
    *   **Strict Template Adherence**: Read the raw document and apply the template `<SKILL_DIR>/templates/paper_template.md`.
    *   **Ensure High-Density Output**:
        *   **No vague stubs**: The compiled markdown must have rich sections covering math formulas (LaTeX), experimental metrics, contributions, and critical limits. If critical information is completely missing from the raw text, you MUST ONLY use the exact string `[STUB: Awaiting synthesis]` as the placeholder. Do not generate other variations like "No explicit definition".
        *   **Bidirectional Linking**: Apply standard Obsidian double bracket linking: `[[Concept]]` or `[[Concept|Alias]]`. Do NOT use standard markdown relative links for these.
        *   **Concept Extraction (Thread-Safe)**: To extract novel concepts, do NOT write directly to `wiki/concepts/`. Instead, use the provided script to safely append your perspective. For each extracted concept, run:
            `python <BIN>/add_concept.py --name "Concept Name" --source "Source Paper Name" --content "Your detailed definition and perspective on this concept based on the paper you just read."`
    *   **Write Compiled Files**: Save output ONLY under `wiki/references/`.
    *   **Report Status**: The subagent must report back to the main agent once the reference file is written and all concepts are extracted via the script.

### Phase 3: Coordination and Cleanup (Main Agent)
4.  **Wait for Completion**: The main agent must wait until all spawned subagents have successfully reported completion. If any subagent fails or times out, log the failure and continue.
5.  **Rebuild Navigation Indexes**: Run the index builder script to deterministically rebuild all `_index.md` files:
    `python <BIN>/index_builder.py "<TOPIC_DIR>"`
6.  **Run Final Linting**: Run `python <BIN>/llm-wiki.py lint --fix "<TOPIC_DIR>"` on the full topic workspace as a final structural pass.
7.  **Log Activity**: Log the compile event in `log.md`, including the count of successful vs. failed compilations.

