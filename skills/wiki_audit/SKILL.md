---
name: wiki_audit
description: "Audit the compiled wiki pages to cross-check statements, highlight scientific contradictions, and output theses using a Map-Reduce architecture."
commands:
  audit: "Audit the wiki contents using Map-Reduce to identify and flag contradictions or inconsistencies."
---

# LLM Wiki — Audit Skill (wiki_audit)

This skill handles factual auditing, truth-seeking evaluations, and thesis-driven investigations across the compiled knowledge base. To prevent context window limits on large vaults, it strictly uses a Map-Reduce architecture.

When the user asks to perform an audit or truth check on their vault:

1.  **Map (Deterministic Inventory — SCRIPT FIRST)**:
    *   Run the wiki inventory script to get a deterministic file listing — do NOT manually browse or rely on grep keywords alone:
        `python .agents/bin/llm-wiki.py stats <TOPIC_DIR> wiki-summary`
    *   Parse the JSON output to understand the vault structure: total files, per-directory counts, file titles, and which files have sources.
    *   **Graph Analysis (MANDATORY)**: Run `python .agents/bin/llm-wiki.py graph` to ensure the local graph database is strictly up to date. Do NOT skip this, otherwise you will read stale data!
    *   Then query the knowledge graph using `python .agents/bin/query-graph.py "<SQL>"`. Do not use direct `sqlite3` command line execution to avoid shell escaping issues.
    *   Use the inventory and graph results to select the files most relevant to the user's audit query. Then use `python .agents/bin/search-wiki.py "<regex>" <files...>` for targeted keyword searches within those specific files (do not rely on system `grep` or `grep_search` tool if the environment lacks it).
    *   Do NOT attempt to read all compiled cards manually.

2.  **Reduce (Subagent Phase)**:
    *   Use the `invoke_subagent` tool to spawn one or more "Audit Subagents". Assign each subagent a specific subset of the relevant files.
    *   **Subagent Output Contract (MANDATORY)**: Each subagent MUST structure findings as:
        ```
        CLAIM: "<exact quote from file>"
        SOURCE: <wiki file path>
        CONTRADICTS: "<exact quote from conflicting file>"
        CONTRA_SOURCE: <wiki file path>
        SEVERITY: high|medium|low
        EXPLANATION: <why these claims conflict>
        ```
    *   If a subagent fails or times out, log the failure and proceed with available results.

3.  **Verify Citations (MANDATORY)**:
    *   Before including any finding in the thesis, the main agent MUST verify:
        a. Both `SOURCE` and `CONTRA_SOURCE` file paths exist (use `view_file` or `list_dir`)
        b. The quoted claims actually appear in those files (use `python .agents/bin/search-wiki.py` or `view_file`)
    *   Discard any finding where the file paths don't exist or quotes can't be verified. Log discarded findings separately.

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
        `python .agents/bin/validate-output.py "<thesis_file>" --schema thesis --wiki-root "<TOPIC_DIR>"`
        If validation fails, fix the reported issues before proceeding.
    *   Run: `python .agents/bin/llm-wiki.py stats <TOPIC_DIR> verify-refs "<thesis_file>"`
        to ensure all `[[references]]` in the thesis point to existing files.

6.  **Log**: Update the activity log `log.md` with: audit query, files examined count, findings count, findings discarded count.
