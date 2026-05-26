---
name: wiki_research
description: "Spawn parallel academic subagents to perform multi-perspective research on a given query and compile a detailed synthesis report."
commands:
  research: "Perform deep, multi-perspective academic research on a topic by gathering evidence and synthesizing results."
---

# LLM Wiki — Research Skill (wiki_research)

This skill handles deep, parallel academic research, spinning up multi-perspective subagents to drill into complex topics and compile unified verdicts.

When the user asks to research a topic:

1.  **Draft a Dynamic Research Plan**: Analyze the user's research query and determine the domain (e.g., Mathematics, Theoretical Physics, Computer Science). Subdivide the query into 3 or more distinct, domain-specific investigative dimensions.
    *   *Example (Physics/Math)*: "Axiomatic Consistency Auditor", "Phenomenology & Experimental Reviewer", "Theoretical Extrapolator".
    *   *Example (CS)*: "Technical Deep Dive", "Critical Reviewer", "Empirical Auditor".

2.  **Orchestrate Background Subagents**: Spawn the parallel subagents using the `invoke_subagent` tool according to your dynamic research plan.
    *   Assign each subagent a clear, focused `Role` and `Prompt` tailored to their specific investigative dimension.
    *   **Source Constraint (CRITICAL)**: Every subagent prompt MUST include this instruction:
        > "You MUST use `search_web` or `view_file` tools to gather evidence. Do NOT make factual claims from parametric memory alone. Every claim must cite either a specific URL from web search or a specific local file path that you read with `view_file`. If you cannot find a source for a claim, mark it explicitly as `[UNVERIFIED]`."
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
    *   For each finding with `SOURCE_TYPE: local_wiki`, verify the file path exists.
    *   For each finding with `SOURCE_TYPE: web`, verify it includes a real URL (starts with `http://` or `https://`).
    *   Reject any finding with no source or a fabricated source. Collect `[UNVERIFIED]` findings separately.

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
    *   Run: `python $HOME/.gemini\config\bin\validate-output.py "<output_file>" --schema research --wiki-root "<TOPIC_DIR>"`
        If validation reports issues, fix them before proceeding.
    *   Run: `python $HOME/.gemini\config\bin\llm-wiki.py lint --fix <TOPIC_DIR>`

6.  **Log**: Append a log entry in `log.md` with: research query, subagent count, verified findings count, unverified findings count, output file path.
