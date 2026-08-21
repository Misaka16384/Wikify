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

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Where it says *file-read tool*, use your agent's equivalent (`Read` in Claude Code, `view_file` in Antigravity). Shell commands run via `Bash`/`PowerShell` (Claude Code) or your framework's shell tool.

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

## Task Tracking (Beads)

Beads (`bd`) is the workspace's work-state store; `log.md` stays a one-line human narrative.

- **Start**: claim or create an issue before substantial work:
  `bd create -t chore "<short description of this run>"` then `bd update <id> --status in_progress`
  (or claim an existing ready issue from `bd ready`).
- **Finish**: `bd close <id> --reason "<one-line outcome>"`. If follow-up work emerged
  (gaps found, sources to ingest, contradictions to resolve), file it now:
  `bd create -t <appropriate type> "..."` — do not leave TODO prose in markdown.
- If `bd` is unavailable, note it once and proceed; do not block on task tracking.

