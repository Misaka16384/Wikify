---
name: wiki_graph_index
description: "Extract Obsidian-style relationships (wikilinks, tags, aliases) into a structured AI-friendly SQLite graph database."
commands:
  graph: "Extract a SQLite knowledge graph from the wiki."
---

# LLM Wiki — Graph Index Skill (wiki_graph_index)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill extracts the Markdown-based knowledge graph (comprised of `[[wikilinks]]`, tags, and aliases) into a structured SQLite database (`output/graph.db`) that an AI agent can easily query using standard SQL.

## Usage

When the user asks to extract, index, or query the knowledge graph of their wiki:

### 1. Build the Graph Database
Run the deterministic python script to extract the graph from the markdown files:
```bash
python <BIN>/llm-wiki.py graph <TOPIC_DIR>
```
*This will parse all markdown files under `wiki/` (ignoring `_index.md`), extract frontmatter (tags, aliases) and body links, and rebuild the SQLite database located at `output/graph.db`.*

### 2. Query the Graph Database
Once built, you (the AI) can query `output/graph.db` using Python's `sqlite3` module to traverse the graph and answer the user's questions.

The database schema is as follows:
- `nodes(id, path, title, type, category, summary, created, updated)`
  - `id`: The file path without extension (e.g., 'concepts/concept_name') or a tag (e.g., 'tag:machine-learning').
- `edges(source_id, target_id, type)`
  - `type` can be 'wikilink' (between files) or 'has_tag' (from file to tag node).
- `tags(node_id, tag)`
- `aliases(node_id, alias)`

Use `python <BIN>/query-graph.py "<SQL>" --db <TOPIC_DIR>/output/graph.db` to query the knowledge graph. Do not use direct `sqlite3` command line execution.

**Example:**
```bash
python <BIN>/query-graph.py "SELECT source_id FROM edges WHERE target_id = 'Transformer';" --db <TOPIC_DIR>/output/graph.db
```
Or via a temporary Python script if you need complex graph traversal.

### 3. Report
Present the findings of your graph queries to the user.

## Error Handling

*   If any script exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.
