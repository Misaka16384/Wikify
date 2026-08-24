---
name: wiki_tag_sync
description: "Deduplicates, normalizes, and reduces sprawling tags and aliases across the knowledge graph using a Map-Reduce architecture."
commands:
  sync_tags: "Normalize all tags and aliases in the current topic workspace."
---

# LLM Wiki — Tag & Alias Sync Skill (wiki_tag_sync)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill resolves the "vocabulary fragmentation" problem. Over time, different agents might invent slightly different tags or aliases for the exact same physical/mathematical concept (e.g., `qca`, `quantum-cellular-automata`, `clifford-qca`). This skill acts as a Map-Reduce pipeline to canonicalize them.

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

## Rules

- **Never fan out without a number.** Say how many sub-agents you are about to start and what each one covers, before the first one starts. Never more than 10 at once. An unstated fan-out is how one 99-page paper spent a user's entire weekly quota.
- **Never let a sub-agent ask the user.** It cannot — the question reaches nobody and the agent hangs or guesses. A sub-agent returns `NEEDS-DECISION: <question>`; you collect them and raise them together, once.
- **Never apply tags you have not shown first.** `magi tags extract` proposes and `magi tags apply` writes. The step between them is a person looking at the list.
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
