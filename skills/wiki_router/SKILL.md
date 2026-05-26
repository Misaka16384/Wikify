---
name: wiki_router
description: "Resolve a topic slug to its absolute path by querying the Hub registry."
commands:
  route: "Resolve topic slug to absolute path."
---

# LLM Wiki — Hub Router Skill (wiki_router)

This skill acts as an internal utility for Agents to find the physical path of a topic given its slug.
Since the Hub decoupling, other skills (`wiki_ingest`, `wiki_lint`, etc.) require absolute paths, not slugs.

When you need to operate on a topic by its slug (e.g., the user says "add to holography topic"):
1.  **Strict Dispatcher Rule**: Run the local deterministic Python script inside this skill directory to resolve the slug to an absolute path.
    `python $HOME/.gemini\config\bin\router.py <path_to_hub> <slug>`
2.  The script will output the absolute path to standard output. Use this path as the argument for subsequent skills (e.g., `wiki_ingest`, `wiki_compile`).
3.  If the script errors (e.g., topic not found), report back to the user.
