---
name: wiki_init
description: "Initialize a new topic workspace folder with standard raw/, wiki/, inbox/, and output/ directories."
commands:
  init: "Initialize an empty workspace folder with standard raw/, wiki/, inbox/, and output/ folders."
---

# LLM Wiki — Initialize Skill (wiki_init)

This skill handles the physical bootstrapping of a new academic/personal topic workspace folder. 

When the user asks to initialize, configure, or set up a new wiki in a folder:
1.  **Strict Dispatcher Rule**: Run the local deterministic Python script inside this skill directory using the `lint --fix` action to automatically bootstrap all missing folders (raw/, wiki/, inbox/, output/) and default index files:
    `python $HOME/.gemini\config\bin\llm-wiki.py lint --fix <path_to_initialize>`
2.  **Create Required Config Files**: After running the bootstrap command, create these files at the root level using the exact templates below. Only fill in the `<PLACEHOLDER>` values — do NOT invent additional fields or sections.

    **`config.md`** — use this template verbatim:
    ```markdown
    ---
    title: "<Topic Title>"
    scope: "<1-2 sentence description of what this wiki covers>"
    created: <YYYY-MM-DD>
    ---

    # <Topic Title>

    ## Scope

    <1-2 sentence description of what this wiki covers>

    ## Conventions

    - Source files go in `raw/` under the appropriate subdirectory
    - Compiled articles go in `wiki/references/` (papers) and `wiki/concepts/` (terms)
    - All compiled pages use YAML frontmatter and `[[double-bracket]]` concept links
    ```

    **`log.md`** — use this template verbatim:
    ```markdown
    # Log

    ## [<YYYY-MM-DD>] init | Created new topic wiki
    ```

    **`_index.md`** — use this template verbatim:
    ```markdown
    # <Topic Title>

    > Topic wiki initialized on <YYYY-MM-DD>.

    ## Quick Navigation

    | Directory | Purpose |
    |-----------|---------|
    | [raw/](raw/) | Raw source materials |
    | [wiki/](wiki/) | Compiled knowledge base |
    | [output/](output/) | Generated artifacts |
    | [inbox/](inbox/) | Pending ingestion |

    ## Statistics

    - Raw sources: 0
    - Compiled articles: 0
    - Concepts: 0
    ```

3.  **Approve**: Run `python $HOME/.gemini\config\bin\llm-wiki.py lint <path_to_initialize>` to verify that the initialized workspace achieves a perfect green `Result: PASS`. If it fails, fix the reported issues and re-run until PASS.

