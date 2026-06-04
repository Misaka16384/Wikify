---
name: wiki_lint
description: "Statically check and repair double-bracket linkages and frontmatter within your compiled wiki directory."
commands:
  lint: "Statically analyze the wiki folder to check and repair double-bracket linkages."
---

# LLM Wiki — Lint Skill (wiki_lint)

> **Resolving script paths (read first):** Commands below invoke scripts as `<BIN>/X.py` (and a few as `<SKILLS>/...`). Resolve these to **absolute paths once** before running anything:
>
> - `<SKILL_DIR>` = the directory this `SKILL.md` lives in.
> - `<SKILLS>` = the `skills/` folder containing this skill = `<SKILL_DIR>/..`
> - `<BIN>` = the `bin/` folder beside it = `<SKILL_DIR>/../../bin`
>
> Do **not** hardcode a fixed prefix like `.agents/bin` or `../bin`: shell relative paths resolve against the current working directory (usually the topic root), not this skill's location. Once resolved, `<BIN>` is typically `.agents/bin` when invoked from the hub root, or `.claude/bin` from inside a topic directory.

This skill handles static validation, claim mapping, and link structural checks to keep the personal knowledge base completely healthy and integrated.

When the user asks to lint, repair, or audit the links in their vault:
1.  **Execute Local Python CLI**: Bypass semantic guesswork. Run the Python validator script:
    `python <BIN>/llm-wiki.py lint --fix <TOPIC_DIR>`
    *   **Math Syntax Validation**: Linting automatically runs math syntax checks on all markdown files (validating LaTeX syntax). Math syntax errors in compiled `wiki/` files are `critical` (blocking), while errors in `raw/` files are `warnings` (non-blocking).
    *   **Skip Math Option**: To run fast structural/link-only checks and skip LaTeX validation, add the `--skip-math` flag:
        `python <BIN>/llm-wiki.py lint --skip-math <TOPIC_DIR>`
2.  **Report to User**: Present all parsed warnings, dangling double-brackets `[[links]]`, missing metadata frontmatter properties, math syntax errors, or directory structure discrepancies.
3.  **Self-Contained Sandbox Verification**: For developer test runs, you can utilize the sandboxed directories in `<SKILL_DIR>/tests/fixtures/` to benchmark and verify the validator's performance:
    *   `golden-wiki/` contains a flawless mock vault.
    *   `defects/` contains defect-injected vaults.
4.  **Log**: Update the activity log `log.md`.

## Error Handling

*   If any script exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.

