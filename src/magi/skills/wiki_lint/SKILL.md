---
name: wiki_lint
description: "Statically check and repair double-bracket linkages and frontmatter within your compiled wiki directory."
commands:
  lint: "Statically analyze the wiki folder to check and repair double-bracket linkages."
---

# LLM Wiki — Lint Skill (wiki_lint)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.
> `<SKILL_DIR>` = the directory this SKILL.md lives in (used only for skill-local assets).

This skill handles static validation, claim mapping, and link structural checks to keep the personal knowledge base completely healthy and integrated.

When the user asks to lint, repair, or audit the links in their vault:
1.  **Execute the CLI**: Bypass semantic guesswork. Run the validator:
    `magi lint --fix <TOPIC_DIR>`
    *   **Math Syntax Validation**: Linting automatically runs math syntax checks on all markdown files (validating LaTeX syntax). Math syntax errors in compiled `wiki/` files are `critical` (blocking), while errors in `raw/` files are `warnings` (non-blocking).
    *   **Skip Math Option**: To run fast structural/link-only checks and skip LaTeX validation, add the `--skip-math` flag:
        `magi lint --skip-math <TOPIC_DIR>`
2.  **Report to User**: Present all parsed warnings, dangling double-brackets `[[links]]`, missing metadata frontmatter properties, math syntax errors, or directory structure discrepancies.
3.  **Self-Contained Sandbox Verification**: For developer test runs, you can utilize the sandboxed directories in `<SKILL_DIR>/tests/fixtures/` to benchmark and verify the validator's performance:
    *   `golden-wiki/` contains a flawless mock vault.
    *   `defects/` contains defect-injected vaults.
4.  **Log**: Update the activity log `log.md`.

## Error Handling

*   If any command exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.

