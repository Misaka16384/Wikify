---
name: wiki_graph_index
description: "Extract Obsidian-style relationships (wikilinks, tags, aliases) into a structured AI-friendly SQLite graph database."
commands:
  graph: "Extract a SQLite knowledge graph from the wiki."
---

# LLM Wiki — Graph Index Skill (wiki_graph_index)

This skill extracts the Markdown-based knowledge graph (comprised of `[[wikilinks]]`, tags, and aliases) into a structured SQLite database (`output/graph.db`) that an AI agent can easily query using standard SQL.

## Usage

When the user asks to extract, index, or query the knowledge graph of their wiki:

### 1. Build the Graph Database
Run the deterministic python script to extract the graph from the markdown files:
```bash
python .agents/bin/llm-wiki.py graph
```
*This will parse all markdown files under `wiki/` (ignoring `_index.md`), extract frontmatter (tags, aliases) and body links, and rebuild the SQLite database located at `output/graph.db`.*

### 2. Query the Graph Database
Once built, you (the AI) can query `output/graph.db` using Python's `sqlite3` module to traverse the graph and answer the user's questions.

The database schema is as follows:
- `nodes(id, path, title, type, category, summary, created, updated)`
  - `id`: The file stem (e.g., 'concept_name')
- `edges(source_id, target_id, type)`
  - `type` is currently always 'wikilink'.
- `tags(node_id, tag)`
- `aliases(node_id, alias)`

**Example Query:**
You can query it via command line:
```bash
sqlite3 output/graph.db "SELECT source_id FROM edges WHERE target_id = 'Transformer';"
```
Or via a temporary Python script if you need complex graph traversal.

### 3. Report
Present the findings of your graph queries to the user.
