---
name: wiki_concept_sync
description: "Deduplicates concepts, splits overly broad concepts, and synthesizes multi-source concept definitions by dynamically searching and analyzing all papers that reference them."
commands:
  sync_concept: "Synthesize a specific concept across all referencing papers."
  sync_all_concepts: "Run a global deduplication and refinement pass over all concepts."
---

# LLM Wiki — Concept Synthesizer Skill (wiki_concept_sync)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill maintains the semantic integrity and comprehensive depth of the knowledge graph's "Concept" nodes. It resolves duplicate concepts, expands overly broad concepts, and, most importantly, synthesizes multi-source definitions by reading all papers that reference a concept.

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

## Execution Modes

The user can ask to refine/sync a **single concept** (e.g., `wiki_concept_sync "Quantum Entanglement"`) or run a **global sync** (`wiki_concept_sync_all`). If not specified, default to asking the user or assuming the concept currently being discussed.

### Phase 1: Deduplication Discovery
1.  **Semantic Duplicates Search**: Run the semantic linker in deduplication-only mode to find highly identical concepts:
    `magi link <TOPIC_DIR> --dedup-only`
    The merge threshold is read from `config.yaml`. Override via `--merge-threshold <value>` if needed.
2.  **Agent Review**: Carefully review the `[MERGE_SUGGESTION]` output logs from the script.
3.  **Resolve & Merge (Principle)**: If you verify that a pair is genuinely the same or strongly overlapping, choose a canonical name. **CRITICAL PRINCIPLE**: Always merge sub-concepts into their parent concepts (e.g., merge `gauge_redundancy` into `gauge_symmetry`). The parent concept becomes the Canonical Name.
4.  **Refactor Links**: Run the deterministic refactor command to safely update all `[[Old Concept]]` links to `[[Canonical Name]]`, handle backups, and delete the old concept automatically:
    `magi wiki refactor-concept --topic-dir \"<TOPIC_DIR>\" --old \"Old Concept\" --new \"Canonical Name\" [--no-rebuild]`
    *(This command will also automatically rebuild the SQLite knowledge graph and markdown indexes upon completion, unless `--no-rebuild` is passed).*
    To speed up bulk refactoring, you can optionally pass the `--no-rebuild` flag to `magi wiki refactor-concept` to skip intermediate index rebuilds.

### Phase 2: Multi-Source Synthesis (Post-Merge RAG)
After resolving duplicates, you must synthesize their definitions to ensure no knowledge is lost.
1.  **Extract RAG Context**: Run the context extractor command to globally search all references for this Canonical Concept and compile the surrounding paragraphs:
    `magi wiki context --name "Canonical Name" --topic-dir "<TOPIC_DIR>"`
    This command will output the path to a `scratch/concept_context_<slug>.md` file.
2.  **Single-Pass Reading**: Use your **file-read tool** to read the generated context file.
3.  **Comprehensive Synthesis**:
    *   **Backup Before Rewrite**: Backup the concept file to `wiki/concepts/.backup/`.
    *   Rewrite `wiki/concepts/<Canonical Name>.md` to fuse the definitions, ensuring no loss of detail from the merged duplicate.
    *   **Post-Write Validation**: Run `magi lint <TOPIC_DIR>`.
4.  **Log**: Update `log.md` with the deduplication and synthesis outcome.

## Rules

- **Never fan out without a number.** Say how many sub-agents you are about to start and what each one covers, before the first one starts. Never more than 10 at once. An unstated fan-out is how one 99-page paper spent a user's entire weekly quota.
- **Never let a sub-agent ask the user.** It cannot — the question reaches nobody and the agent hangs or guesses. A sub-agent returns `NEEDS-DECISION: <question>`; you collect them and raise them together, once.
- **Never rename a concept without `magi wiki refactor-concept`.** It updates every wikilink pointing at the old name. A rename done by hand leaves dangling links that `magi lint` will report as somebody else's problem.
- **Never report a partial result as a whole one.** If three of eight sub-agents came back empty or failed, say which and why. A summary that reads as success while part of the work is missing is worse than no summary — it spends the reader's trust instead of their time.

## Task Tracking (Beads)

Beads (`bd`) is the workspace's work-state store; `log.md` stays a one-line human narrative.

- **Start**: claim or create an issue before substantial work:
  `bd create -t chore "<short description of this run>"` then `bd update <id> --status in_progress`
  (or claim an existing ready issue from `bd ready`).
- **Finish**: `bd close <id> --reason "<one-line outcome>"`. If follow-up work emerged
  (gaps found, sources to ingest, contradictions to resolve), file it now:
  `bd create -t <appropriate type> "..."` — do not leave TODO prose in markdown.
- If `bd` is unavailable, note it once and proceed; do not block on task tracking.

