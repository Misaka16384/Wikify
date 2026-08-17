---
name: wiki_init
description: "Initialize a new topic workspace folder with standard raw/, wiki/, inbox/, and output/ directories."
commands:
  init: "Initialize an empty workspace folder with standard raw/, wiki/, inbox/, and output/ folders."
---

# LLM Wiki — Initialize Skill (wiki_init)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

This skill handles the physical bootstrapping of a new academic/personal topic workspace folder. 

When the user asks to initialize, configure, or set up a new wiki in a folder:
1.  **Strict Dispatcher Rule**: Run the helper command to programmatically initialize folders and files:
    `magi init --topic-dir \"<path_to_initialize>\" --name \"<Topic Title>\" --scope \"<1-2 sentence description of what this wiki covers>\"`
    This command programmatically sets up the folder structures, and generates `config.md`, `log.md`, `_index.md`, and all subdirectory `_index.md` files.
2.  **Approve**: Run `magi lint <path_to_initialize>` to verify that the initialized workspace achieves a perfect green `Result: PASS`. If it fails, fix the reported issues and re-run until PASS.
3.  **Register in Hub (Auto)**: If this topic was created inside an existing hub — i.e., some ancestor directory contains both `wikis.json` and a `topics/` folder — you **MUST** register it so the hub router and `wiki_hub_manager` can resolve it. Run the idempotent registration command:
    `magi hub register --hub <hub_path> <slug> --description "<Topic Title>"`
    where `<slug>` is the topic folder name (e.g. the final path segment) and `<hub_path>` is the hub root. This is safe to re-run. **Skip this step only** for standalone (non-hub) wikis where no ancestor hub exists.

