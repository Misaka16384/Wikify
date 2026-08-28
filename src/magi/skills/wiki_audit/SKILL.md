---
name: wiki_audit
description: "Audit the compiled wiki pages to cross-check statements, highlight scientific contradictions, and output theses using a Map-Reduce architecture."
commands:
  audit: "Audit the wiki contents using Map-Reduce to identify and flag contradictions or inconsistencies."
---

# LLM Wiki — Audit Skill (wiki_audit)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill handles factual auditing, truth-seeking evaluations, and thesis-driven investigations across the compiled knowledge base. To prevent context window limits on large vaults, it strictly uses a Map-Reduce architecture.

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

When the user asks to perform an audit or truth check on their vault:

1.  **Map (Deterministic Inventory — SCRIPT FIRST)**:
    *   Run the wiki inventory command to get a deterministic file listing — do NOT manually browse or rely on grep keywords alone:
        `magi stats <TOPIC_DIR> wiki-summary`
    *   Parse the JSON output to understand the vault structure: total files, per-directory counts, file titles, and which files have sources.
    *   Before graph/regex retrieval, run `magi search "<claim or topic>" -k 8 --json` (hybrid BM25+vector) to locate candidate evidence fast; then ALWAYS read the underlying files before quoting them as evidence.
    *   **Graph Analysis (MANDATORY)**: Run `magi graph build` to ensure the local graph database is strictly up to date. Do NOT skip this, otherwise you will read stale data!
    *   Then query the knowledge graph using `magi graph query "<SQL>"`. Do not use direct `sqlite3` command line execution.
        **Graph DB Schema:**
        - `nodes(id TEXT PRIMARY KEY, path TEXT, title TEXT, type TEXT, category TEXT, summary TEXT, created TEXT, updated TEXT)`
        - `edges(source_id TEXT, target_id TEXT, type TEXT)`
        - `tags(node_id TEXT, tag TEXT)`
        - `aliases(node_id TEXT, alias TEXT)`
        **Example Queries:**
        - `SELECT path FROM nodes WHERE category='reference' AND id IN (SELECT node_id FROM tags WHERE tag='quantum-mechanics')`
        - `SELECT n.path, e.type FROM nodes n JOIN edges e ON n.id = e.target_id WHERE e.source_id = 'some-concept-id'`
    *   Use the inventory and graph results to select the files most relevant to the user's audit query. Then use `magi grep "<regex>" <files...>` for targeted keyword searches within those specific files.
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
        `EVIDENCE` must be a single quoted line — multiline quotes are unsupported by `magi verify`.
    *   If a subagent fails or times out, log the failure and proceed with available results.
    *   **Collect their `NEEDS-DECISION:` lines** as you go: a sub-agent cannot reach the human, so anything it was unsure about is sitting in its report. Ask the user about all of them together, once, at the end — not one interruption per sub-agent.

3.  **Verify Citations (MANDATORY)**:
    *   Save all subagent outputs to `scratch/temp_claims.txt` (`scratch/` is scaffolded by `magi init`, but create it if absent).
    *   Run `magi verify scratch/temp_claims.txt --topic-dir "<TOPIC_DIR>" --json` (blocks opened with either `CLAIM:` or `FINDING:` are accepted)
        (add `--fetch-web` when web sources must be content-verified rather than format-checked)
    *   Discard any finding that is reported as `[UNVERIFIED]`. Log discarded findings separately.
        The `--json` summary reports per-status counts (`verified`, `web-verified`, `url-format-ok`, `unverified`) — read the counts per status, not just a single total. `url-format-ok` web claims are NOT content-verified: either re-verify them with `--fetch-web`, or file them under a clearly marked Unverified/Provisional section — never present them as verified.

4.  **Synthesize**: Merge the verified findings into a structured investigation report (Thesis).

5.  **Produce Theses**:
    *   Save the compiled report under `drafts/YYYY-MM-DD-<slug>.md`. (`wiki/theses/` is
        retired: the write-up is a draft, and the claims in it are propositions. Open one
        per contradiction with `magi thread new --kind proposition` and point its
        `derivation:` at this file.) Frontmatter:
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
    *   **Persist provenance**: after verification, embed the verified claim blocks into the output document as an HTML comment so the knowledge graph ingests them on the next `magi graph build`:

        ```
        <!-- magi:claims
        CLAIM: <claim text>
        EVIDENCE: "<quote>"
        SOURCE_TYPE: local_wiki|web
        SOURCE: <path or URL>
        STATUS: <verified|web-verified|url-format-ok|unverified>
        -->
        ```

        One entry per claim, statuses copied from `magi verify --json` output. Claims become graph nodes (`has_claim` / `supported_by` edges) stored in the `claims(id, doc_id, text, status)` and `evidence(claim_id, source_type, source, quote)` tables, e.g. `magi graph query "SELECT c.text, c.status, e.source FROM claims c JOIN evidence e ON e.claim_id=c.id"` or `magi graph query "SELECT * FROM claims WHERE status != 'verified'"`.
    *   **Post-Write Validation (MANDATORY)**: Run:
        `magi validate "<thesis_file>" --schema thesis --wiki-root "<TOPIC_DIR>"`
        If validation fails, fix the reported issues before proceeding.
    *   Run: `magi stats <TOPIC_DIR> verify-refs "<thesis_file>"`
        to ensure all `[[references]]` in the thesis point to existing files.

6.  **Log**: Update the activity log `log.md` with: audit query, files examined count, findings count, findings discarded count.

## Rules

- **Never fan out without a number.** Say how many sub-agents you are about to start and what each one covers, before the first one starts. Never more than 10 at once. An unstated fan-out is how one 99-page paper spent a user's entire weekly quota.
- **Never let a sub-agent ask the user.** It cannot — the question reaches nobody and the agent hangs or guesses. A sub-agent returns `NEEDS-DECISION: <question>`; you collect them and raise them together, once.
- **Never call something a contradiction on one source.** A contradiction needs both statements, each with its page. One citation is an observation.
- **Never report a partial result as a whole one.** If three of eight sub-agents came back empty or failed, say which and why. A summary that reads as success while part of the work is missing is worse than no summary — it spends the reader's trust instead of their time.

## Task Tracking (Beads)

Beads (`bd`) is the workspace's work-state store; `log.md` stays a one-line human narrative.

- **Start**: claim or create an issue before substantial work:
  `bd create -t review "<short description of this run>"` then `bd update <id> --status in_progress`
  (or claim an existing ready issue from `bd ready`).
- **Finish**: `bd close <id> --reason "<one-line outcome>"`. If follow-up work emerged
  (gaps found, sources to ingest, contradictions to resolve), file it now:
  `bd create -t <appropriate type> "..."` — do not leave TODO prose in markdown.
- If `bd` is unavailable, note it once and proceed; do not block on task tracking.
