---
name: wiki_hub_manager
description: "Manage topics in the central Hub: route slugs to paths, list topics, and archive or restore topics."
commands:
  manage_hub: "Manage hub topics (route, list, archive, restore)."
---

# LLM Wiki — Hub Manager Skill (wiki_hub_manager)

This skill consolidates all Hub-related operations into a single dispatcher.

## Operations

1. **Resolve a Topic Slug to Absolute Path (Router)**
   If you need to find the absolute path for a topic slug:
   `python .agents/bin/router.py <path_to_hub> <slug>`

2. **List Topics**
   If the user asks to list topics in the hub:
   `python .agents/bin/llm-wiki.py archive --hub <path_to_hub> list`
   *(Append `--archived` to include archived topics).*

3. **Archive a Topic**
   To archive an active topic (move it out of the active working set):
   `python .agents/bin/llm-wiki.py archive --hub <path_to_hub> topic <slug>`
   *(Append `--reason "<reason>"` if the user provided one).*

4. **Restore an Archived Topic**
   To unarchive a topic and move it back into the active working set:
   `python .agents/bin/llm-wiki.py archive --hub <path_to_hub> restore <slug>`

## Error Handling

*   If any script exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.

