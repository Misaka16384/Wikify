"""MAGI: agent-native research workspace.

Three-state architecture:
- Balthasar (work/intent state): Beads issue graph
- Melchior (epistemic state): the wiki knowledge base (concepts, references, claims)
- Casper (retrieval state): hybrid FTS5 + vector index

The CLI is the restraint armor; the LLM host is the pilot's Eva.
"""

__version__ = "1.14.4"
