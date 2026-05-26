---
name: wiki_hub_archive
description: "Archive an active topic in the Hub, moving it out of the active working set."
commands:
  archive: "Archive an active topic."
---

# LLM Wiki — Hub Archive Skill (wiki_hub_archive)

This skill safely archives a topic, moving its directory to `.archive/` and updating the registry `wikis.json`.

When the user asks to archive a topic or put a topic on hold:
1.  **Strict Dispatcher Rule**: Run the local deterministic Python script inside this skill directory.
    `python $HOME/.gemini\config\bin\llm-wiki.py archive --hub <path_to_hub> topic <slug>`
2.  If the user provides a reason for archiving, append `--reason "<reason>"`.
