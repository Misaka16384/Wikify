---
name: wiki_hub_init
description: "Initialize a central Hub directory for managing multiple topic wikis."
commands:
  init: "Initialize an empty Hub directory with topics/ and wikis.json registry."
---

# LLM Wiki — Hub Initialize Skill (wiki_hub_init)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill bootstraps the root Hub directory that manages multiple individual topic wikis.

When the user asks to initialize or set up a new Hub:
1.  **Strict Dispatcher Rule**: Run the deterministic command to safely create the required structure.
    `magi hub init <path_to_hub>`
2.  **Verify**: Ensure the command executes successfully and confirms the creation of `wikis.json` and `topics/`.

## Error Handling

*   If any command exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.

