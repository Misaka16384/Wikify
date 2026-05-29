---
name: wiki_hub_manager
description: "Manage topics in the central Hub: route slugs to paths, list topics, and archive or restore topics."
commands:
  manage_hub: "Manage hub topics (route, list, archive, restore)."
---

# LLM Wiki — Hub Manager Skill (wiki_hub_manager)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill consolidates all Hub-related operations into a single dispatcher.

## Operations

1. **Resolve a Topic Slug to Absolute Path (Router)**
   If you need to find the absolute path for a topic slug:
   `python <BIN>/router.py <path_to_hub> <slug>`

2. **List Topics**
   If the user asks to list topics in the hub:
   `python <BIN>/llm-wiki.py archive --hub <path_to_hub> list`
   *(Append `--archived` to include archived topics).*

3. **Archive a Topic**
   To archive an active topic (move it out of the active working set):
   `python <BIN>/llm-wiki.py archive --hub <path_to_hub> topic <slug>`
   *(Append `--reason "<reason>"` if the user provided one).*

4. **Restore an Archived Topic**
   To unarchive a topic and move it back into the active working set:
   `python <BIN>/llm-wiki.py archive --hub <path_to_hub> restore <slug>`

5. **Register an Existing Active Topic**
   If a topic folder exists under `topics/<slug>` but is missing from `wikis.json` (so the router cannot resolve it), register it (idempotent — safe to re-run):
   `python <BIN>/llm-wiki.py archive --hub <path_to_hub> register <slug> --description "<Topic Title>"`
   *(Use `--path <registry-relative-path>` if the topic is not at the default `topics/<slug>`.)* Note: newly initialized topics are auto-registered by `wiki_init`; use this mainly to repair an unregistered topic.

## Error Handling

*   If any script exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.

