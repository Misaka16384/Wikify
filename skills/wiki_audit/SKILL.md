---
name: wiki_audit
description: "Audit the compiled wiki pages to cross-check statements, highlight scientific contradictions, and output theses using a Map-Reduce architecture."
commands:
  audit: "Audit the wiki contents using Map-Reduce to identify and flag contradictions or inconsistencies."
---

# LLM Wiki — Audit Skill (wiki_audit)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill handles factual auditing, truth-seeking evaluations, and thesis-driven investigations across the compiled knowledge base. To prevent context window limits on large vaults, it strictly uses a Map-Reduce architecture.

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Map each capability to your own agent's tool — *read-file* (`Read` in Claude Code, `view_file` in Antigravity), *sub-agent / parallel task* (`Task`/`Agent` in Claude Code, `invoke_subagent` in Antigravity), *shell* (`Bash`/`PowerShell`). Use the closest equivalent your framework provides; if a parallel sub-agent tool is unavailable, audit each file subset sequentially yourself.

When the user asks to perform an audit or truth check on their vault:

1.  **Map (Deterministic Inventory — SCRIPT FIRST)**:
    *   Run the wiki inventory script to get a deterministic file listing — do NOT manually browse or rely on grep keywords alone:
        `python <BIN>/llm-wiki.py stats <TOPIC_DIR> wiki-summary`
    *   Parse the JSON output to understand the vault structure: total files, per-directory counts, file titles, and which files have sources.
    *   **Graph Analysis (MANDATORY)**: Run `python <BIN>/llm-wiki.py graph` to ensure the local graph database is strictly up to date. Do NOT skip this, otherwise you will read stale data!
    *   Then query the knowledge graph using `python <BIN>/query-graph.py "<SQL>"`. Do not use direct `sqlite3` command line execution.
        **Graph DB Schema:**
        - `nodes(id TEXT PRIMARY KEY, path TEXT, title TEXT, type TEXT, category TEXT, summary TEXT, created TEXT, updated TEXT)`
        - `edges(source_id TEXT, target_id TEXT, type TEXT)`
        - `tags(node_id TEXT, tag TEXT)`
        - `aliases(node_id TEXT, alias TEXT)`
        **Example Queries:**
        - `SELECT path FROM nodes WHERE category='reference' AND id IN (SELECT node_id FROM tags WHERE tag='quantum-mechanics')`
        - `SELECT n.path, e.type FROM nodes n JOIN edges e ON n.id = e.target_id WHERE e.source_id = 'some-concept-id'`
    *   Use the inventory and graph results to select the files most relevant to the user's audit query. Then use `python <BIN>/search-wiki.py "<regex>" <files...>` for targeted keyword searches within those specific files.
    *   Do NOT attempt to read all compiled cards manually.

2.  **Reduce (Subagent Phase)**:
    *   Use your agent's **sub-agent / parallel-task tool** to spawn one or more "Audit Subagents". Assign each subagent a specific subset of the relevant files. (If no sub-agent tool exists, audit each subset sequentially yourself.)
    *   **Subagent Output Contract (MANDATORY)**: Each subagent MUST structure findings as:
        ```
        CLAIM: "<exact quote from conflicting file>"
        EVIDENCE: "<exact quote from file>"
        SOURCE_TYPE: local_wiki
        SOURCE: <wiki file path>
        CONTRADICTS_SOURCE: <conflicting wiki file path>
        SEVERITY: high|medium|low
        EXPLANATION: <why these claims conflict>
        ```
    *   If a subagent fails or times out, log the failure and proceed with available results.

3.  **Verify Citations (MANDATORY)**:
    *   Save all subagent outputs to `scratch/temp_claims.txt`.
    *   Run `python <BIN>/verify_claims.py scratch/temp_claims.txt --topic-dir "<TOPIC_DIR>"`
    *   Discard any finding that is reported as `[UNVERIFIED]`. Log discarded findings separately.

4.  **Synthesize**: Merge the verified findings into a structured investigation report (Thesis).

5.  **Produce Theses**:
    *   Save the compiled Thesis report under `wiki/theses/YYYY-MM-DD-<slug>.md` with proper YAML frontmatter:
        ```yaml
        ---
        title: "Thesis: <descriptive title>"
        type: thesis
        category: reference
        created: YYYY-MM-DD
        sources:
          - <list of wiki files examined>
        tags: [audit, thesis]
        confidence: <high|medium|low>
        summary: "<1-2 sentence summary of findings>"
        ---
        ```
    *   **Post-Write Validation (MANDATORY)**: Run:
        `python <BIN>/validate-output.py "<thesis_file>" --schema thesis --wiki-root "<TOPIC_DIR>"`
        If validation fails, fix the reported issues before proceeding.
    *   Run: `python <BIN>/llm-wiki.py stats <TOPIC_DIR> verify-refs "<thesis_file>"`
        to ensure all `[[references]]` in the thesis point to existing files.

6.  **Log**: Update the activity log `log.md` with: audit query, files examined count, findings count, findings discarded count.
