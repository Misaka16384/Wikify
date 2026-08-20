---
name: wiki_graph_index
description: "Extract Obsidian-style relationships (wikilinks, tags, aliases) into a structured AI-friendly SQLite graph database."
commands:
  graph: "Extract a SQLite knowledge graph from the wiki."
---

# LLM Wiki — Graph Index Skill (wiki_graph_index)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill extracts the Markdown-based knowledge graph (comprised of `[[wikilinks]]`, tags, and aliases) into a structured SQLite database (`output/graph.db`) that an AI agent can easily query using standard SQL.

## Usage

When the user asks to extract, index, or query the knowledge graph of their wiki:

### 1. Build the Graph Database
Run the deterministic graph builder to extract the graph from the markdown files:
```bash
magi graph build <TOPIC_DIR>
```
*This will parse all markdown files under `wiki/` (ignoring `_index.md`), extract frontmatter (tags, aliases) and body links, and rebuild the SQLite database located at `output/graph.db`.*

### 2. Query the Graph Database
Once built, use `magi graph query "<SQL>" --db <TOPIC_DIR>/output/graph.db` to query the knowledge graph. Fall back to a temporary Python script using the `sqlite3` module only for complex multi-step traversals that a single SQL statement cannot express. Do not use direct `sqlite3` command line execution.

The database schema is as follows:
- `nodes(id, path, title, type, category, summary, created, updated)`
  - `id`: The topic-relative file path without extension, WITH the `wiki/` prefix (e.g., 'wiki/concepts/concept_name'), or a tag (e.g., 'tag:machine-learning').
- `edges(source_id, target_id, type)`
  - `type` can be 'wikilink' (between files) or 'has_tag' (from file to tag node).
- `tags(node_id, tag)`
- `aliases(node_id, alias)`
- `claims(id, doc_id, text, status)`
  - Provenance claims parsed from `<!-- magi:claims -->` blocks; `doc_id` is the containing document's node id.
- `evidence(claim_id, source_type, source, quote)`
  - Evidence rows backing each claim (`source_type` is 'local_wiki' or 'web').

**Example:**
```bash
magi graph query "SELECT source_id FROM edges WHERE target_id = 'wiki/concepts/transformer';" --db <TOPIC_DIR>/output/graph.db
```

### 3. Report
Present the findings of your graph queries to the user.

## Error Handling

*   If any script exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.
