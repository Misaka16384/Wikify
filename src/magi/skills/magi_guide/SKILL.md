---
name: magi_guide
description: "Answer MAGI usage and troubleshooting questions from the installed manual: look up the exact error in `magi guide --symptoms/--search`, read the relevant chapter, verify the workspace state, and hand back the exact fix command. Use whenever a magi command errors or the user asks how to install, migrate, ingest, build the graph, search, write, or run the radar."
commands:
  magi_guide: "Diagnose a MAGI problem (or answer a how-do-I question) from the built-in manual."
---

# MAGI — Manual & Troubleshooting Skill (magi_guide)

> **CLI (read first):** This skill drives the `magi` CLI (assumed installed on PATH). Full syntax for any command: `magi <command> --help`. If you are unsure where you are, run `magi sync`.

MAGI ships its own operating manual inside the package — twelve scenario chapters, each written as *what to do → how → what you should see → what to do when you don't*. The same markdown backs the WebUI's Docs tab and the `magi guide` command, so what you read here is exactly what the user reads.

**The rule this skill exists to enforce: never answer a MAGI usage question from memory.** Flags change between versions; the manual on disk describes *this* installation. Look it up, quote it, then act.

> **Tooling (framework-agnostic):** Where this says *file-read tool*, use your agent's equivalent (`Read` in Claude Code, `view_file` in Antigravity). Shell commands run via `Bash`/`PowerShell` or your framework's shell tool.

## The command surface

```bash
magi guide --json                          # chapter list: numbers, anchors, one-line summaries
magi guide <number|anchor|title> --plain   # one chapter, raw markdown (e.g. magi guide ingest)
magi guide --search "<text>" --json        # sections mentioning that text, with their commands
magi guide --symptoms --json               # every symptom -> cause -> fix pair in the manual
magi guide --symptoms --search "<text>"    # that index, filtered
magi guide --lang en                       # the manual defaults to Chinese; English also ships
```

`--json` is the machine contract. Search hits carry `chapter_anchor`, `section`, matched lines, and `commands` — the runnable commands from that section. The symptom index carries `symptom`, `cause`, `fix`, `commands`, and the `anchor` of the chapter it came from.

## Flow A — a command failed

1. **Capture the real error.** Get the exact command the user ran and the exact output. Do not paraphrase it into a guess.
2. **Look it up by symptom first.** Take the most distinctive fragment — the literal error string, not the whole line, and without paths, ids, or numbers that vary per machine:
   `magi guide --symptoms --search "mineru_api_token" --json`
3. **Widen if empty.** Fall back to full-text search: `magi guide --search "no workspace found" --json`. Still empty? Shorten the fragment (three or four distinctive words), or list the index and scan it: `magi guide --symptoms --json`.
4. **Read the chapter around the hit** for the conditions the fix assumes: `magi guide <chapter_anchor> --plain`. The `[!WARN]` and `[!NOTE]` callouts in that chapter are where the traps live.
5. **Check the actual state before prescribing.** Cheap, read-only, and it decides between two candidate fixes:
   - `magi sync` — which core is down, what it suggests next
   - `magi setup --check` — which external tool is missing
   - `magi graph browse overview` / `magi radar status --json` / `magi pm status --json` — subsystem state
6. **Hand back the fix verbatim.** Quote the command from the manual, say which chapter it came from, and state what the user should see afterwards (the manual's `[!EXPECT]` block for that step).
7. **Run it only when it is safe or the user says go.** See *Destructive commands* below.
8. **Confirm the fix worked** by re-running the failed command or the matching diagnostic, and report the result.

## Flow B — "how do I …"

1. `magi guide --json` and pick the chapter whose `title`/`summary` matches the intent.
2. `magi guide <anchor> --plain`, then follow it step by step, respecting the stated prerequisites.
3. For exact syntax of any command in it, run `magi <command> --help` — the manual teaches *when and why*, `--help` is authoritative on flags.
4. Tell the user what to expect at each step, and what the manual says to do if it doesn't happen.

## Quality rules

- **Never invent a flag.** If a flag is not in the manual and not in `magi <command> --help`, it does not exist. Several plausible ones genuinely do not: there is no `magi compile`, no `magi migrate --dry-run`, no `magi index --force`, no `magi tags apply --dry-run`, no `--resume` on `magi ingest ocr`.
- **Prefer the manual's fix to your own improvisation.** If you think you have a better one, say both, and mark yours as untested.
- **Say when it isn't covered.** If two searches return nothing, tell the user the manual doesn't cover this, then fall back to `magi <command> --help` plus `magi sync`/`magi setup --check` and reason from the observed state. Do not fill the gap with a guess dressed up as documentation.
- **Cite the chapter** (`magi guide graph`) so the user can read the context themselves — in the terminal or in `magi ui` → Docs & Help.
- **One fix at a time.** Apply, verify, then move on; a batch of speculative changes makes the next diagnosis harder.

## Destructive commands — confirm first

Ask before running any of these, and say exactly what they will change:

| Command | What it does |
|---|---|
| `magi setup --remove-legacy` | Deletes legacy Wikify skill dirs, and the **whole** `~/.claude/bin` (or `~/.gemini/bin`) if the old script is found inside it |
| `magi tags apply <dir> <map> <map>` | Rewrites frontmatter across every wiki file; no dry-run exists |
| `magi link --auto-merge` | Physically merges concept cards; canonical name is the **shorter** one, not the better one |
| `magi wiki refactor-concept` | Renames/merges a concept across the whole wiki |
| `magi init --force` | Regenerates `CLAUDE.md`/`config.yaml`/`config.md`, discarding manual edits |
| Deleting `output/index.db` or `output/graph.db` | The only way to force a full rebuild — safe, but say so first |

`magi migrate`, `magi lint --fix`, `magi graph build`, and `magi index` are safe to re-run: they only add or fully rebuild derived state.

## Error handling

- `magi: unknown command 'guide'` → this installation predates the manual. Tell the user to upgrade: `uv tool install --force git+https://github.com/Misaka16384/magi`, then retry.
- `guide not found in this installation` → the package data is missing; same upgrade command repairs it.
- `magi guide --search` exits 1 when nothing matched — that is a clean "no hits", not a crash. Widen the query.
- If `magi` itself is not on PATH, stop and point at chapter 2: the manual's install section is also readable on GitHub at `src/magi/docs/guide.zh.md`.

## Report format

State, in this order: what failed, what the manual says the cause is, the exact fix command, which chapter it came from, and what the user should see when it works. Keep it to a few lines — the user wants the fix, not the search trail.
