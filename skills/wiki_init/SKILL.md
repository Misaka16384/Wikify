---
name: wiki_init
description: "Initialize a new topic workspace folder with standard raw/, wiki/, inbox/, and output/ directories."
commands:
  init: "Initialize an empty workspace folder with standard raw/, wiki/, inbox/, and output/ folders."
---

# LLM Wiki — Initialize Skill (wiki_init)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill handles the physical bootstrapping of a new academic/personal topic workspace folder. 

When the user asks to initialize, configure, or set up a new wiki in a folder:
1.  **Strict Dispatcher Rule**: Run the helper script to programmatically initialize folders and files:
    `python <BIN>/init_workspace.py --topic-dir \"<path_to_initialize>\" --name \"<Topic Title>\" --scope \"<1-2 sentence description of what this wiki covers>\"`
    This script programmatically sets up the folder structures, and generates `config.md`, `log.md`, `_index.md`, and all subdirectory `_index.md` files.
2.  **Approve**: Run `python <BIN>/llm-wiki.py lint <path_to_initialize>` to verify that the initialized workspace achieves a perfect green `Result: PASS`. If it fails, fix the reported issues and re-run until PASS.
3.  **Register in Hub (Auto)**: If this topic was created inside an existing hub — i.e., some ancestor directory contains both `wikis.json` and a `topics/` folder — you **MUST** register it so the hub router and `wiki_hub_manager` can resolve it. Run the idempotent registration command:
    `python <BIN>/llm-wiki.py archive --hub <hub_path> register <slug> --description "<Topic Title>"`
    where `<slug>` is the topic folder name (e.g. the final path segment) and `<hub_path>` is the hub root. This is safe to re-run. **Skip this step only** for standalone (non-hub) wikis where no ancestor hub exists.

