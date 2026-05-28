---
name: wiki_ask
description: "Chat with the knowledge base. Answers user questions by dynamically employing RAG context extraction, graph database queries, and targeted keyword searches to provide cited, hallucination-free answers."
commands:
  ask: "Answer a user question based strictly on the contents of the knowledge base."
---

# LLM Wiki — Knowledge Base Q&A Skill (wiki_ask)

This skill transforms the agent into a conversational interface for the knowledge base. When the user asks a question, you must intelligently deploy a combination of deterministic search tools to retrieve context and provide a highly rigorous, cited answer.

## Core Rule: Zero Hallucination
> **CRITICAL INSTRUCTION**: Do NOT answer questions using your parametric memory. Every factual claim or summary you provide MUST be grounded in the local knowledge base and explicitly cited using Obsidian wikilinks (e.g., `[[Concept Name]]` or `[[Paper Title]]`).

## Execution Flow

When tasked with answering a question, follow these strategies depending on the nature of the inquiry:

### Strategy 1: Concept Extraction (RAG)
If the user asks about the definition, lineage, or application of a specific concept (e.g., "What is Haag Duality?"):
1.  Run the context extractor script:
    `python .agents/bin/extract_concept_context.py --name "Target Concept" --topic-dir "<TOPIC_DIR>"`
2.  Read the resulting `scratch/concept_context_<slug>.md` file using the `view_file` tool.
3.  Synthesize your answer directly from this condensed RAG context, citing the sources listed in the context file.

### Strategy 2: Graph Traversal
If the user asks broad survey questions or inquiries about relationships (e.g., "What papers discuss quantum error correction?"):
1.  Query the local SQLite graph database using:
    `python .agents/bin/query-graph.py "<SQL>"`
2.  **Graph DB Schema (MANDATORY)**: Do not guess table names. Use only this schema:
    - `nodes(id TEXT PRIMARY KEY, path TEXT, title TEXT, type TEXT, category TEXT, summary TEXT, created TEXT, updated TEXT)`
    - `edges(source_id TEXT, target_id TEXT, type TEXT)`
    - `tags(node_id TEXT, tag TEXT)`
    - `aliases(node_id TEXT, alias TEXT)`
3.  **Example Queries**:
    - `SELECT title, summary FROM nodes WHERE type='papers' AND id IN (SELECT node_id FROM tags WHERE tag='quantum-error-correction')`
    - `SELECT n.title, e.type FROM nodes n JOIN edges e ON n.id = e.target_id WHERE e.source_id = 'some-concept-id'`

### Strategy 3: Targeted Search
If the user asks highly specific, detail-oriented questions requiring deep dives into math or specific mechanisms:
1.  First, use Strategy 2 to narrow down the relevant files.
2.  Run the targeted search script:
    `python .agents/bin/search-wiki.py "<regex>" <files...>`
3.  Read the most promising returned files using the `view_file` tool.

## Synthesizing the Final Answer

Once you have gathered sufficient context using the strategies above:
1.  Draft a clear, conversational response.
2.  Ensure every major claim is immediately followed by its source: "As demonstrated in [[2023-06-12-graph_gauge_theory]], the mechanism..."
3.  If you cannot find the answer using these tools, explicitly state: "I could not find information regarding this in the current knowledge base." Do not attempt to fill in the blanks with external knowledge.
