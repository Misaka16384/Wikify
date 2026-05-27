---
name: wiki_hub_list
description: "List all active and archived topics in the Hub registry."
commands:
  list: "List topics in the hub."
---

# LLM Wiki — Hub List Skill (wiki_hub_list)

This skill queries the Hub registry (`wikis.json`) to list topics.

When the user asks to see what topics exist or list topics in a hub:
1.  **Strict Dispatcher Rule**: Run the local deterministic Python script inside this skill directory.
    `python .agents/bin/llm-wiki.py archive --hub <path_to_hub> list`
2.  If the user explicitly asks for archived topics as well, append `--archived`.
