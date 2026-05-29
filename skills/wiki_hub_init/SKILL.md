---
name: wiki_hub_init
description: "Initialize a central Hub directory for managing multiple topic wikis."
commands:
  init: "Initialize an empty Hub directory with topics/ and wikis.json registry."
---

# LLM Wiki — Hub Initialize Skill (wiki_hub_init)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill bootstraps the root Hub directory that manages multiple individual topic wikis.

When the user asks to initialize or set up a new Hub:
1.  **Strict Dispatcher Rule**: Run the local deterministic Python script inside this skill directory to safely create the required structure.
    `python <BIN>/hub-init.py <path_to_hub>`
2.  **Verify**: Ensure the script executes successfully and confirms the creation of `wikis.json` and `topics/`.

## Error Handling

*   If any script exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.

