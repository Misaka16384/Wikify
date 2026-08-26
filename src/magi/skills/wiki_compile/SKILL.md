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

> **Tools — capabilities, not names.** This skill asks for things like *read a
> file*, *edit a file*, *run a shell command*, *search the web*, *fetch a page*,
> *look at an image*, *spawn a sub-agent*. Every host calls these something
> different and the names change between versions, so use whichever of yours
> fits. If you genuinely lack one, say so and do the sequential equivalent —
> never silently skip the step.

> **Questions go to the main agent.** If you are running as a sub-agent, do not
> try to ask the human: on most hosts the question will not reach them, and on
> some it hangs. Put it in the report you return instead, on its own line:
> `NEEDS-DECISION: <the question> | options: <a> / <b> | default if unanswered: <x>`
> Whoever spawned you collects these and asks once, together — ten sub-agents
> must not become ten interruptions.
> If you **are** the main agent and nobody is there to answer (a scheduled run, a
> piped run, CI), do not guess and do not wait. Stop, and state plainly what you
> would have asked and what you need in order to continue.

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
4.  **Wait for Completion**: The main agent must wait until all spawned subagents have successfully reported completion. If any subagent fails or times out, log the failure and continue. **Collect their `NEEDS-DECISION:` lines** as you go: a sub-agent cannot reach the human, so anything it was unsure about is sitting in its report. Ask the user about all of them together, once, at the end — not one interruption per sub-agent.
5.  **Run Structural Linting**: Run `magi lint --fix "<TOPIC_DIR>"` on the full topic workspace. This comes *before* the index rebuild, not after: `lint --fix` fills in frontmatter a freshly compiled card is missing, and the index tables are built from that frontmatter. Reindexing first meant every card lint had just repaired was listed with the summary, tags and date it had *before* the repair — until something rebuilt the index again.
6.  **Rebuild Navigation Indexes**: Run the index builder to deterministically rebuild all `_index.md` files:
    `magi wiki reindex "<TOPIC_DIR>"`
7.  **Log Activity**: Log the compile event in `log.md`, including the count of successful vs. failed compilations.

## Rules

- **Never fan out without a number.** Say how many sub-agents you are about to start and what each one covers, before the first one starts. Never more than 10 at once. An unstated fan-out is how one 99-page paper spent a user's entire weekly quota.
- **Never let a sub-agent ask the user.** It cannot — the question reaches nobody and the agent hangs or guesses. A sub-agent returns `NEEDS-DECISION: <question>`; you collect them and raise them together, once.
- **Never edit anything under `raw/`.** It is the source of record and the only thing here that cannot be regenerated. Compilation writes to `wiki/`, always.
- **Never report a partial result as a whole one.** If three of eight sub-agents came back empty or failed, say which and why. A summary that reads as success while part of the work is missing is worse than no summary — it spends the reader's trust instead of their time.

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

