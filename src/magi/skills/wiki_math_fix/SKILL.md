---
name: wiki_math_fix
description: "Works through every malformed LaTeX formula in the workspace one at a time — the OCR and PDF-conversion damage that `magi math format` cannot fix mechanically."
commands:
  fix_math: "Harvest every broken formula in this workspace and repair them one by one."
---

# LLM Wiki — Math Repair Skill (wiki_math_fix)

> **CLI (read first):** This skill drives the `magi` CLI (MAGI research workspace tool, assumed installed on PATH). If unsure of your surroundings, run `magi sync` first to locate the workspace. For the full syntax of any command: `magi <command> --help`.

> **Tooling (framework-agnostic):** Where this says *file-read tool* / *file-edit tool*, use your agent's equivalent (`Read` / `Edit` in Claude Code, `view_file` / `edit_file` in Antigravity). Shell commands run via your framework's shell tool. Where a step says to **ask the user**, use your agent's question tool (`AskUserQuestion` in Claude Code) or simply ask in your reply and wait — never assume an answer and carry on.

Ingestion turns PDFs into markdown, and the maths does not always survive. A
`$$` loses its closing pair and swallows a page of prose; a subscript brace
never closes; a stray `$` lands inside a display block. `magi math format`
repairs the mechanical half. What is left needs someone who can read the
formula and tell what it was supposed to say — which is why this is a skill
and not another flag.

**The workspace is the unit of work, the same way `magi lint` treats it.**
Do not fix one file and stop.

---

## 1. Free wins first

Never hand-edit what a deterministic pass can fix:

```
magi math format          # delimiter and escaping repairs, whole workspace
```

This rewrites files in place and has no dry-run, so **commit first** if the
workspace is a git repo.

## 2. Harvest the rest

```
magi math check --json > scratch/math-worklist.json
```

One entry per broken formula:

| field | what it is |
|---|---|
| `id` | `path:line` — stable, so you can tick entries off a long list |
| `path`, `line`, `end_line` | where to edit; the range is the whole formula |
| `kind` | `block` (`$$…$$`) or `inline` (`$…$`) |
| `error` | what the parser choked on |
| `tex` | the offending source verbatim (clipped when huge — `tex_clipped`) |
| `confidence` | `certain`, or `likely-macro` — **read the next section** |
| `collection` | `wiki` (compiled cards) or `raw` (ingest output) |

Add `--fast` to skip the per-file `pdflatex` pass when you only want the
structural errors; it is minutes faster on a large library. `--wiki-only`
narrows to compiled cards.

**Triage before you edit.** Read the whole worklist first and group it:
identical errors usually share one cause, and one ingest run usually damaged
one paper in one way.

> [!TIP]
> **A run of consecutive entries in one file is usually one defect, not many.**
> `$$` delimiters pair up in order, so a single unclosed one shifts every pair
> after it and each shifted pair gets reported. Fix the *first* entry in a
> file, re-run `magi math check <that file>`, and watch most of the rest
> disappear. A worklist of 115 entries across 6 files is often a dozen real
> edits. Never work such a file bottom-up.

## 3. Do not "fix" correct mathematics

> [!WARN]
> `confidence: likely-macro` means `pdflatex` met a command it does not know.
> Nine times in ten that is a package the validator does not load — `\bm`,
> `\mathscr`, `\slashed`, something the author defined — **not a typo.**
> Rewriting those silently corrupts formulas that were right.

For anything you are not certain about, check it against the source before
touching it:

```
magi ingest crop <PDF> --text "<words near the formula>" --out scratch/check.png
magi ingest crop <PDF> --page <N> --out scratch/check.png    # no text layer
```

Then look at the PNG with your image-capable read tool. The source paper for
a card is named in its frontmatter, and lives under `raw/papers/`.

If the source is gone or unreadable and the intent is genuinely ambiguous,
**leave the formula alone and report it.** A wrong formula that looks right is
worse than one that visibly fails to render.

## 4. Repair, one entry at a time

For each entry, in worklist order (do `wiki/` before `raw/` — those are the
cards a reader actually opens):

1. **Read** the file around `line`–`end_line` with your *file-read tool*. The
   `tex` field is a preview; the file is the truth.
2. **Diagnose** against the patterns below.
3. **Edit** with your *file-edit tool*. Change only the formula. Do not
   reflow the prose around it, do not renumber equations, do not "improve"
   notation that was already consistent with the rest of the card.
4. **Verify that one file** before moving on:
   `magi math check <path/to/file.md>`
5. Move to the next entry.

### The patterns this actually finds

| Symptom in `error` | What happened | The fix |
|---|---|---|
| `was expecting '$$'` / `was expecting '$'` and `tex` contains paragraphs of prose | A `$$` never got closed, so everything down to the next `$$` reads as one formula | Find where the formula truly ends and close it there. The prose after it goes back to being prose. |
| `Unexpected mismatching closing brace: '}'` | One `}` too many — OCR doubled it | Delete the extra brace. Count the pairs; don't add an opening one. |
| `was expecting '}'` | A brace never closed | Close it where the subscript/superscript/`\text{}` argument ends. |
| `Unexpected closing environment` / `mismatching closing environment` | `\begin{aligned}` vs `\end{pmatrix}` and similar | Make the pair agree; check which one the body actually is. |
| `$` inside a `$$` block | OCR kept the inline delimiters | Delete the inner `$`. |
| `Undefined control sequence` | Usually a package macro (see §3) | Verify against the PDF. Only rewrite a genuine typo. |

## 5. Close the loop

```
magi math check           # expect: "All formulas under … parse cleanly."
magi lint --fix           # math errors in wiki/ are critical and block lint
magi index                # re-index if you edited compiled cards
```

Then open a repaired card in the dashboard (`magi ui`) and look at it. The
preview typesets with KaTeX, which is stricter than `pylatexenc` about some
things and more forgiving about others — a formula that renders is the real
acceptance test.

Finally, append what you changed to `log.md`: how many formulas, which files,
and **which entries you deliberately left alone and why**.

## Error Handling

*   If any command exits non-zero, report the full stderr to the user and stop.
*   If a file cannot be read or parsed, log a warning and continue with the
    remaining entries — one unreadable file must not abandon the worklist.
*   Never silently skip an entry. Every worklist item ends as fixed, or as a
    reported reason it was not.
