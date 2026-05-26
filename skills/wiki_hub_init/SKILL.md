---
name: wiki_hub_init
description: "Initialize a central Hub directory for managing multiple topic wikis."
commands:
  init: "Initialize an empty Hub directory with topics/ and wikis.json registry."
---

# LLM Wiki — Hub Initialize Skill (wiki_hub_init)

This skill bootstraps the root Hub directory that manages multiple individual topic wikis.

When the user asks to initialize or set up a new Hub:
1.  **Strict Dispatcher Rule**: Run the local deterministic Python script inside this skill directory to safely create the required structure.
    `python $HOME/.gemini\config\bin\hub-init.py <path_to_hub>`
2.  **Verify**: Ensure the script executes successfully and confirms the creation of `wikis.json` and `topics/`.
