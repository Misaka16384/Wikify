---
name: magi
description: "Entry point for a MAGI research workspace: run magi next, do what it says, and call the skill it names."
commands:
  magi: "Work out what this research workspace needs next, and do it."
---

# magi — the entry

## When to use
Any turn in a MAGI workspace where you do not already know what you are doing.

## Method
1. `magi next` — it reads the notes and ranks what is owed. It never acts.
2. Do the first item, unless the human just asked for something else: their
   sentence outranks the list. The menu is computed; the choice is yours.
3. When an item names a skill, call it. When it names a command, run it.
4. Anything the human says in passing that is worth keeping goes into
   `inbox/notes.md` as one line, untidied. A later `magi next` files it.
5. Before stopping: `magi sync --close`. It refuses while something happened
   that nobody wrote down. Fix what it lists, then close again.

## Rules
- **Never** invent a next step while `magi next` has one. That list is derived
  from the notes; a step you made up is derived from nothing.
- **Never** edit a status in `threads/` by hand. `magi thread status <slug>
  <status> --text '<why>'` writes the flip and its reason together, or neither.
- Read the `magi:begin` block in `AGENTS.md` once per session. Those invariants
  are not advice.
- Stuck on a command or an error: `magi guide --search "<the error>"`. Do not
  guess a flag; `magi <command> --help` is one call away.
