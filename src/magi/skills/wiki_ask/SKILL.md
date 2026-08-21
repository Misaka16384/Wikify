---
name: wiki_ask
description: "Chat with the knowledge base. Answers user questions by dynamically employing RAG context extraction, graph database queries, and targeted keyword searches to provide cited, hallucination-free answers."
commands:
  ask: "Answer a user question based strictly on the contents of the knowledge base."
---

# LLM Wiki — Knowledge Base Q&A Skill (wiki_ask)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill transforms the agent into a conversational interface for the knowledge base. When the user asks a question, you must intelligently deploy a combination of deterministic search tools to retrieve context and provide a highly rigorous, cited answer.

> **Tooling (framework-agnostic):** This skill is written tool-agnostic. Where it says *file-read tool*, use your agent's equivalent (`Read` in Claude Code, `view_file` in Antigravity, `cat`/open elsewhere). Shell commands run via `Bash`/`PowerShell` (Claude Code) or your framework's shell tool. Where a step says to **ask the user**, use your agent's question tool (`AskUserQuestion` in Claude Code) or simply ask in your reply and wait — never assume an answer and carry on.

## Core Rule: Zero Hallucination
> **CRITICAL INSTRUCTION**: Do NOT answer questions using your parametric memory. Every factual claim or summary you provide MUST be grounded in the local knowledge base and explicitly cited using Obsidian wikilinks (e.g., `[[Concept Name]]` or `[[Paper Title]]`).

## Execution Flow

When tasked with answering a question, follow these strategies depending on the nature of the inquiry:

### Strategy 0: Hybrid Retrieval (start here for most questions)
0.  Scope note: `magi search` federates over the current workspace PLUS any enabled globally-registered KBs (results carry a `kb` field / `[kb:name]` tag). Add `--scope local` to restrict to this workspace; cite cross-KB results with their KB name so the reader can locate the file.
1.  Run `magi search "<query>" -k 8 --json` — hybrid BM25+vector search over the whole corpus. Scope with `--collection references` (papers) or `--collection concepts` when the question type is clear.
2.  **ALWAYS open the top hits with your file-read tool** and read the full section before citing — never cite from a search snippet alone.
3.  If results look empty or stale, run `magi index` first (`magi sync` warns about a stale index).
4.  Fall through to the strategies below when you need graph structure, exact regex, or concept lineage.

### Strategy 1: Concept Extraction (RAG)
If the user asks about the definition, lineage, or application of a specific concept (e.g., "What is Haag Duality?"):
1.  Run the context extractor:
    `magi wiki context --name "Target Concept" --topic-dir "<TOPIC_DIR>"`
2.  Read the resulting `scratch/concept_context_<slug>.md` file with your **file-read tool**.
3.  Synthesize your answer directly from this condensed RAG context, citing the sources listed in the context file.

### Strategy 2: Graph Traversal
If the user asks broad survey questions or inquiries about relationships (e.g., "What papers discuss quantum error correction?"):
1.  Query the local SQLite graph database using:
    `magi graph query "<SQL>"`
2.  **Graph DB Schema (MANDATORY)**: Do not guess table names. Use only this schema:
    - `nodes(id TEXT PRIMARY KEY, path TEXT, title TEXT, type TEXT, category TEXT, summary TEXT, created TEXT, updated TEXT)`
    - `edges(source_id TEXT, target_id TEXT, type TEXT)`
    - `tags(node_id TEXT, tag TEXT)`
    - `aliases(node_id TEXT, alias TEXT)`
    - **NOTE on `type`/`category`**: every node has a non-empty `type` — frontmatter `type` wins when present, otherwise it is derived from the containing folder (`concept`, `reference`, `thesis`, `topic`). `category` IS populated too — the broader bucket (`concept`/`reference`/`topic`/`thesis`). You can filter by either column.
    - **NOTE on node ids**: `id` is the wiki-relative file path WITH the `wiki/` prefix and without the `.md` extension, e.g. `wiki/concepts/anyon`.
    - **NOTE on wikilink edges**: for `type='wikilink'` edges, `target_id` is the resolved node id of the link target (e.g. `wiki/concepts/anyon`); unresolved (dangling) links keep the raw link text as `target_id`.
3.  **Example Queries**:
    - `SELECT title, summary FROM nodes WHERE type='reference' AND id IN (SELECT node_id FROM tags WHERE tag='quantum-error-correction')`
    - `SELECT title, summary FROM nodes WHERE type='concept' AND id IN (SELECT node_id FROM tags WHERE tag='duality')`
    - `SELECT n.title, e.type FROM nodes n JOIN edges e ON n.id = e.target_id WHERE e.source_id = 'wiki/concepts/some_concept'`

### Strategy 3: Targeted Search
If the user asks highly specific, detail-oriented questions requiring deep dives into math or specific mechanisms:
1.  First, use Strategy 2 to narrow down the relevant files.
2.  Run the targeted search:
    `magi grep "<regex>" <files...>`
3.  Read the most promising returned files with your **file-read tool**.

### Strategy 4: Path Finding & Multi-Hop Reasoning
If the user asks about the connection or path between two distinct concepts (e.g., "How is Concept A connected to Concept B?"):
1.  Query the local SQLite graph database using a `WITH RECURSIVE` SQL query to find paths up to 3 hops.
2.  **Example Path-Finding Query**:
    `magi graph query "WITH RECURSIVE undirected_edges(node1, node2) AS (SELECT source_id, target_id FROM edges WHERE source_id NOT LIKE 'tag:%' AND target_id NOT LIKE 'tag:%' AND source_id NOT LIKE 'alias:%' AND target_id NOT LIKE 'alias:%' UNION SELECT target_id, source_id FROM edges WHERE source_id NOT LIKE 'tag:%' AND target_id NOT LIKE 'tag:%' AND source_id NOT LIKE 'alias:%' AND target_id NOT LIKE 'alias:%'), path_search(current_node, path, depth) AS (SELECT 'node-A-id', 'node-A-id', 0 UNION ALL SELECT u.node2, p.path || ' -> ' || u.node2, p.depth + 1 FROM undirected_edges u JOIN path_search p ON u.node1 = p.current_node WHERE p.depth < 3 AND p.path NOT LIKE '%' || u.node2 || '%') SELECT path FROM path_search WHERE current_node = 'node-B-id' LIMIT 5"`
    *(The `NOT LIKE 'tag:%'/'alias:%'` filters matter: paths routed through shared tag nodes are semantically meaningless "shortcuts" and would otherwise dominate the results.)*
3.  Analyze the returned path and read the intermediate concepts if needed to explain *why* they are connected.

## Synthesizing the Final Answer

Once you have gathered sufficient context using the strategies above:
1.  Draft a clear, conversational response.
2.  Ensure every major claim is immediately followed by its source: "As demonstrated in [[2023-06-12-graph_gauge_theory]], the mechanism..."
3.  If you cannot find the answer using these tools, explicitly state: "I could not find information regarding this in the current knowledge base." Do not attempt to fill in the blanks with external knowledge.

## Error Handling

*   If any script exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.

