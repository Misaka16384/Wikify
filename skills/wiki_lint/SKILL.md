---
name: wiki_lint
description: "Statically check and repair double-bracket linkages and frontmatter within your compiled wiki directory."
commands:
  lint: "Statically analyze the wiki folder to check and repair double-bracket linkages."
---

# LLM Wiki — Lint Skill (wiki_lint)

This skill handles static validation, claim mapping, and link structural checks to keep the personal knowledge base completely healthy and integrated.

When the user asks to lint, repair, or audit the links in their vault:
1.  **Execute Local Python CLI**: Bypass semantic guesswork. Run the complete, 511-line Python validator script bundled inside this skill:
    `python .agents/bin/llm-wiki.py lint --fix <TOPIC_DIR>`
2.  **Report to User**: Present all parsed warnings, dangling double-brackets `[[links]]`, missing metadata frontmatter properties, or directory structure discrepancies.
3.  **Self-Contained Sandbox Verification**: For developer test runs, you can utilize the sandboxed directories in `<SKILL_DIR>/tests/fixtures/` to benchmark and verify the validator's performance:
    *   `golden-wiki/` contains a flawless mock vault.
    *   `defects/` contains defect-injected vaults.
4.  **Log**: Update the activity log `log.md`.

## Error Handling

*   If any script exits with non-zero code, report the full stderr output to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with remaining files.
*   Do NOT silently skip errors or proceed with partial results without reporting.

