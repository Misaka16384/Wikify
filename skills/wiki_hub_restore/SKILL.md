---
name: wiki_hub_restore
description: "Restore an archived topic back into the active Hub registry."
commands:
  restore: "Restore an archived topic."
---

# LLM Wiki — Hub Restore Skill (wiki_hub_restore)

This skill restores an archived topic, moving its directory back from `.archive/` and updating the registry `wikis.json`.

When the user asks to restore an archived topic or unarchive a topic:
1.  **Strict Dispatcher Rule**: Run the local deterministic Python script inside this skill directory.
    `python .agents/bin/llm-wiki.py archive --hub <path_to_hub> restore <slug>`
