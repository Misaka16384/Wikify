---
name: wiki_tag_sync
description: "Deduplicates, normalizes, and reduces sprawling tags and aliases across the knowledge graph using a Map-Reduce architecture."
commands:
  sync_tags: "Normalize all tags and aliases in the current topic workspace."
---

# LLM Wiki — Tag & Alias Sync Skill (wiki_tag_sync)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill resolves the "vocabulary fragmentation" problem. Over time, different agents might invent slightly different tags or aliases for the exact same physical/mathematical concept (e.g., `qca`, `quantum-cellular-automata`, `clifford-qca`). This skill acts as a Map-Reduce pipeline to canonicalize them.

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

When the user asks to sync, reduce, deduplicate, or normalize tags and aliases:

### 1. Map Phase (Extraction)
*   **Action**: Run the deterministic extractor to gather all unique metadata.
    `magi tags extract <TOPIC_DIR>`
*   **Result**: This will silently generate two statistical inverted index files:
    1. `<TOPIC_DIR>/scratch/raw_tags.json`
    2. `<TOPIC_DIR>/scratch/raw_aliases.json`
    *(These JSONs output an inverted index in the format: `{"Tag_Name": {"count": 2, "files": ["wiki/concepts/file.md"]}}`)*

### 2. Reduce Phase (LLM Decision)
*   **Action**: Read the contents of both `raw_tags.json` and `raw_aliases.json` with your **file-read tool**.
*   **Logic (CRITICAL)**: Act as the "Reducer". Use your domain knowledge in physics and mathematics to analyze the raw lists:
    *   **For Tags**: Identify synonyms, acronyms, and plural/singular variations (e.g. mapping `gauge-theory` and `gauge-theories` to `gauge-theory`, or `qca` and `quantum-cellular-automata` to `qca`). Choose the most concise or highest-frequency term as the canonical tag.
    *   **For Aliases**: Identify extremely similar aliases and map them to a clean, canonical format.
    *   **Alias Collision Warning**: If you notice that two distinct sets of aliases are heavily overlapping (which implies two different files might be describing the exact same concept), you MUST print a bold `[MERGE WARNING]` to the user in your final response detailing the suspected duplicate files.
*   **Output generation**: Create two mapping files in the `scratch/` directory.
    1. Write `<TOPIC_DIR>/scratch/tag_mapping.json`:
       ```json
       {
         "tags": {
           "quantum-cellular-automata": "qca",
           "clifford-qca": "qca"
         }
       }
       ```
    2. Write `<TOPIC_DIR>/scratch/alias_mapping.json`:
       ```json
       {
         "aliases": {
           "Z2 QCA": "Z_2 QCA"
         }
       }
       ```
    *Note: You only need to include tags/aliases in the mapping JSON if they are actually being changed. You do not need to map a tag to itself.*

### 3. Apply Phase (Global Replacement)
*   **Action**: Run the apply command to rewrite the frontmatter of all affected Markdown files safely:
    `magi tags apply <TOPIC_DIR> <TOPIC_DIR>/scratch/tag_mapping.json <TOPIC_DIR>/scratch/alias_mapping.json`
*   **Result**: The command will update the YAML frontmatter across the vault, generate a final `wiki/ontology.txt` file containing the canonical whitelisted tags, and **automatically rebuild the SQLite knowledge graph (`output/graph.db`) and Markdown indexes**.

### 4. Semantic Linker Integration (Optional but Recommended)
*   After applying the new tags, ask the user if they want to re-run the `wiki_semantic_link` skill, as the newly normalized tags and aliases will now provide a massive accuracy boost to the semantic similarity engine.

## Task Tracking (Beads)

Beads (`bd`) is the workspace's work-state store; `log.md` stays a one-line human narrative.

- **Start**: claim or create an issue before substantial work:
  `bd create -t chore "<short description of this run>"` then `bd update <id> --status in_progress`
  (or claim an existing ready issue from `bd ready`).
- **Finish**: `bd close <id> --reason "<one-line outcome>"`. If follow-up work emerged
  (gaps found, sources to ingest, contradictions to resolve), file it now:
  `bd create -t <appropriate type> "..."` — do not leave TODO prose in markdown.
- If `bd` is unavailable, note it once and proceed; do not block on task tracking.
