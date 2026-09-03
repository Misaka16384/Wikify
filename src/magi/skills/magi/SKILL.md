---
name: magi
description: "Entry point for a MAGI research project: run magi next, do what it says, and call the skill it names."
commands:
  magi: "Work out what this research project needs next, and do it."
origin: magi
---

# magi — the entry

## When to use
Any turn in a MAGI project where you do not already know what you are doing.

## Method
1. `magi next` — it reads the notes and ranks what is owed. It never acts.
2. Do the first item, unless the human just asked for something else: their
   sentence outranks the list. Everything under **"For the person"** goes to them
   in **one message**; record answers with `magi thread bet <slug>
   <supported|refuted|unknown> --text '<their words>'` or `magi decide --about <slug> --text '<their words>'`.
3. When an item names a skill, call it. When it names a command, run it.
4. A result that came before its note is a finding — `magi thread new <slug>
   --kind proposition --title '<claim>' --purpose '<why>' --found` asks no bet.
   A reviewer's `restate` is yours, not the person's: fix the words as its post
   says, then `magi thread status <slug> supported --text '<what changed>'`.
5. Anything the human says in passing worth keeping goes into `inbox/notes.md`
   as one line, untidied. A later `magi next` files it.
6. Before stopping: `magi sync --close`. It refuses while something happened that
   nobody wrote down — clear each item with `magi thread post <slug> --text '<what
   happened>' --host human` or `magi decide --about <slug> --text '<what they decided>'`, then close again.

## Rules
- **Never** invent a next step while `magi next` has one. That list is derived
  from the notes; a step you made up is derived from nothing.
- **Never** edit a status in `threads/` by hand. `magi thread status <slug>
  <status> --text '<why>'` writes the flip and its reason together, or neither.
- Closing a **line** and leaving `disputed` or `conflict` are a person's call:
  `magi close <line>`, or `magi decide --about <slug> --text '<their words>'`. **Never**
  redo such a flip unsigned to pass the close gate; each unsigned repeat is one more signature owed.
- Read the `magi:begin` block in `AGENTS.md` once per session; those invariants
  are not advice. Stuck: `magi guide --search "<the error>"`, never a guessed flag.
