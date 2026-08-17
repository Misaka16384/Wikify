---
name: wiki_research
description: "Spawn parallel academic subagents to perform multi-perspective research on a given query and compile a detailed synthesis report."
commands:
  research: "Perform deep, multi-perspective academic research on a topic by gathering evidence and synthesizing results."
---

# LLM Wiki — Research Skill (wiki_research)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill handles deep, parallel academic research, spinning up multi-perspective subagents to drill into complex topics and compile unified verdicts.

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Map each capability to your own agent's tool — *read-file* (`Read` in Claude Code, `view_file` in Antigravity), *sub-agent / parallel task* (`Task`/`Agent` in Claude Code, `invoke_subagent` in Antigravity), *web-search* (`WebSearch` in Claude Code, `search_web`), *shell* (`Bash`/`PowerShell`). Use the closest equivalent your framework provides; if a parallel sub-agent tool is unavailable, investigate each research dimension sequentially yourself.

When the user asks to research a topic:

1.  **Draft a Dynamic Research Plan**: Analyze the user's research query and determine the domain (e.g., Mathematics, Theoretical Physics, Computer Science). Subdivide the query into 3 or more distinct, domain-specific investigative dimensions.
    *   *Example (Physics/Math)*: "Axiomatic Consistency Auditor", "Phenomenology & Experimental Reviewer", "Theoretical Extrapolator".
    *   *Example (CS)*: "Technical Deep Dive", "Critical Reviewer", "Empirical Auditor".
    *   **Graph Context**: Before finalizing the plan, you are encouraged to query the local SQLite graph database (`output/graph.db`) to identify existing nodes related to the query. Ensure the index is up to date by running `magi graph build` first. Use `magi graph query "<SQL>"` to query the knowledge graph. Do not use direct `sqlite3` command line execution.
        **Graph DB Schema:**
        - `nodes(id TEXT PRIMARY KEY, path TEXT, title TEXT, type TEXT, category TEXT, summary TEXT, created TEXT, updated TEXT)`
        - `edges(source_id TEXT, target_id TEXT, type TEXT)`
        - `tags(node_id TEXT, tag TEXT)`
        - `aliases(node_id TEXT, alias TEXT)`
        **Example Queries:**
        - `SELECT path FROM nodes WHERE category='reference' AND id IN (SELECT node_id FROM tags WHERE tag='quantum-mechanics')`
        - `SELECT n.path, e.type FROM nodes n JOIN edges e ON n.id = e.target_id WHERE e.source_id = 'some-concept-id'`
        This helps contextualize your research plan within the existing knowledge graph.

2.  **Orchestrate Background Subagents**: Spawn the parallel sub-agents using your agent's **sub-agent / parallel-task tool** according to your dynamic research plan. (If no sub-agent tool exists, investigate each dimension sequentially yourself.)
    *   Assign each subagent a clear, focused `Role` and `Prompt` tailored to their specific investigative dimension.
    *   **Source Constraint (CRITICAL)**: Every subagent prompt MUST include this instruction:
        > "You MUST use your **web-search tool** or **file-read tool** to gather evidence. Do NOT make factual claims from parametric memory alone. Every claim must cite either a specific URL from web search or a specific local file path that you read. If you cannot find a source for a claim, mark it explicitly as `[UNVERIFIED]`."
    *   **Subagent Output Contract (MANDATORY)**: Each subagent MUST return findings in this structure:
        ```
        FINDING: <summary of finding>
        EVIDENCE: "<quote or data point>"
        SOURCE_TYPE: web|local_wiki
        SOURCE: <URL or file path>
        ```
        Findings without a valid `SOURCE` must be marked `[UNVERIFIED]`.

3.  **Verify and Filter Subagent Results**:
    *   Wait for all subagents to report back. If any subagent fails, log the failure and proceed with available results.
    *   Save all reported findings exactly as returned into a temporary file: `scratch/temp_claims.txt`.
    *   Run the verification script to automatically check the citations:
        `magi verify scratch/temp_claims.txt --topic-dir "<TOPIC_DIR>"`
        (`magi verify` accepts both `FINDING:` and `CLAIM:` block openers, so the subagent output contract above is valid as-is.)
    *   Only use `[VERIFIED]` claims in your final synthesis. Collect `[UNVERIFIED]` findings separately.

4.  **Synthesize Findings**:
    *   Merge verified findings into a detailed, authoritative synthesis document.
    *   **Output Destination**:
        -   If the research covers a broad topic (survey, tutorial-style) → save as `wiki/topics/YYYY-MM-DD-<slug>.md`
        -   If the research is a literature review of specific papers → save as `wiki/references/YYYY-MM-DD-<slug>.md`
    *   **YAML Frontmatter (MANDATORY)**:
        ```yaml
        ---
        title: "<descriptive title>"
        type: topic|reference
        category: topic|reference
        created: YYYY-MM-DD
        compiled-from: mixed
        sources:
          - <list of all cited URLs and file paths>
        tags: [research, <domain-specific tags>]
        confidence: <high|medium|low>
        summary: "<1-2 sentence summary>"
        ---
        ```
    *   If `[UNVERIFIED]` findings exist, include them under a clearly marked `## Unverified Claims` section at the end. Do NOT mix unverified claims into the main body.

5.  **Post-Write Validation (MANDATORY)**:
    *   Run: `magi validate "<output_file>" --schema research --wiki-root "<TOPIC_DIR>"`
        If validation reports issues, fix them before proceeding.
    *   Run: `magi lint --fix <TOPIC_DIR>`

6.  **Log**: Append a log entry in `log.md` with: research query, subagent count, verified findings count, unverified findings count, output file path.

## Task Tracking (Beads)

Beads (`bd`) is the workspace's work-state store; `log.md` stays a one-line human narrative.

- **Start**: claim or create an issue before substantial work:
  `bd create -t survey "<short description of this run>"` then `bd update <id> --status in_progress`
  (or claim an existing ready issue from `bd ready`).
- **Finish**: `bd close <id> --reason "<one-line outcome>"`. If follow-up work emerged
  (gaps found, sources to ingest, contradictions to resolve), file it now:
  `bd create -t <appropriate type> "..."` — do not leave TODO prose in markdown.
- If `bd` is unavailable, note it once and proceed; do not block on task tracking.
