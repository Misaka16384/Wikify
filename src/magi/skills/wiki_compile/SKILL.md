---
name: wiki_compile
description: "Compile raw sources into detailed, Obsidian-compatible, interlinked Markdown pages under wiki/ references/ and concepts/."
commands:
  compile: "Compile raw sources into detailed, high-density, interlinked Markdown wiki pages."
---

# LLM Wiki — Compile Skill (wiki_compile)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.
> `<SKILL_DIR>` = the directory this SKILL.md lives in (used only for skill-local assets).

This skill handles the AI-driven "compilation" of high-entropy raw source texts into beautiful, structured, and interconnected literature cards and concept sheets.

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Map each capability to your own agent's tool — *read-file* (`Read` in Claude Code, `view_file` in Antigravity), *sub-agent / parallel task* (`Task`/`Agent` in Claude Code, `invoke_subagent` in Antigravity), *web-search* (`WebSearch` in Claude Code, `search_web`), *ask-user* (see the note below — **never assume an answer**), *shell* (`Bash`/`PowerShell`). Use the closest equivalent your framework provides; if a parallel sub-agent tool is unavailable, perform the steps sequentially yourself.

> **Asking the user (read before any step that says to):** stopping and asking in your
> reply, then waiting, is the only mechanism that works on every host — use it by default.
> A dedicated tool exists on some (`AskUserQuestion` in Claude Code, `request_user_input`
> in Codex's Plan mode, `question` in opencode; Antigravity has none) and is fine to use
> when you have one. Two limits matter more than the names:
> **if you are a sub-agent, the tool will not reach the human** — put the question in the
> report you return to whoever spawned you; and **in a headless or scheduled run nobody is
> there**, where every host either denies the tool, errors on it, or hangs. So when there is
> no answer to be had: do not guess and do not wait. Stop, and say plainly what you would
> have asked and what you would need to proceed.

When the user asks to compile the wiki or process raw files, follow this parallelized workflow:

### Phase 1: Preparation
1.  **Detect Uncompiled Sources**: Run the helper command to detect uncompiled files programmatically:
    `magi wiki uncompiled --topic-dir \"<TOPIC_DIR>\"`
    This command output will list the relative paths of uncompiled source files.

### Phase 2: Parallel Compilation (Subagents)
2.  **Invoke Subagents**: Use your agent's **sub-agent / parallel-task tool** (spawning a fresh self-instance per task) to process one uncompiled raw file per sub-agent, concurrently. If your framework has no sub-agent tool, process the files sequentially yourself.
3.  **Subagent Task Instructions**: Instruct each subagent to process its specifically assigned raw file independently:
    *   **Strict Template Adherence**: Read the raw document and apply the template `<SKILL_DIR>/templates/paper_template.md`.
    *   **Ensure High-Density Output**:
        *   **No vague stubs**: The compiled markdown must have rich sections covering math formulas (LaTeX), experimental metrics, contributions, and critical limits. If critical information is completely missing from the raw text, you MUST ONLY use the exact string `[STUB: Awaiting synthesis]` as the placeholder. Do not generate other variations like "No explicit definition".
        *   **Bidirectional Linking**: Apply standard Obsidian double bracket linking: `[[Concept]]` or `[[Concept|Alias]]`. Do NOT use standard markdown relative links for these.
        *   **Concept Extraction (Thread-Safe)**: To extract novel concepts, do NOT write directly to `wiki/concepts/`. Instead, use the provided command to safely append your perspective. For each extracted concept, run:
            `magi wiki add-concept --name "Concept Name" --source "Source Paper Name" --content "Your detailed definition and perspective on this concept based on the paper you just read."`
    *   **Write Compiled Files**: Save output ONLY under `wiki/references/`.
    *   **Report Status**: The subagent must report back to the main agent once the reference file is written and all concepts are extracted via the command.

### Phase 3: Coordination and Cleanup (Main Agent)
4.  **Wait for Completion**: The main agent must wait until all spawned subagents have successfully reported completion. If any subagent fails or times out, log the failure and continue.
5.  **Rebuild Navigation Indexes**: Run the index builder to deterministically rebuild all `_index.md` files:
    `magi wiki reindex "<TOPIC_DIR>"`
6.  **Run Final Linting**: Run `magi lint --fix "<TOPIC_DIR>"` on the full topic workspace as a final structural pass.
7.  **Log Activity**: Log the compile event in `log.md`, including the count of successful vs. failed compilations.

## Task Tracking (Beads)

Beads (`bd`) is the workspace's work-state store; `log.md` stays a one-line human narrative.

- **Start**: claim or create an issue before substantial work:
  `bd create -t task "<short description of this run>"` then `bd update <id> --status in_progress`
  (or claim an existing ready issue from `bd ready`).
- **Finish**: `bd close <id> --reason "<one-line outcome>"`. If follow-up work emerged
  (gaps found, sources to ingest, contradictions to resolve), file it now:
  `bd create -t <appropriate type> "..."` — do not leave TODO prose in markdown.
- If `bd` is unavailable, note it once and proceed; do not block on task tracking.
- Compile backlog issues carry the label `magi-compile` (created by `magi pm backlog-sync`).
  After compiling a source, close its matching issue: find it via `bd list --label magi-compile`.
  When self-creating a compile task (no backlog issue exists yet), add `--label magi-compile` so this lookup finds it:
  `bd create -t task "Compile <source>" --label magi-compile`.
- If the matching backlog issue exists but is closed (e.g. wontfix), reopen it with `bd reopen <id>` (or `bd update <id> --status open`) rather than creating a duplicate — unless the closure was intentional, in which case leave it closed and skip that source.

