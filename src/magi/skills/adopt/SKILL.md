---
name: adopt
description: "Take a folder that already holds research — papers, notes, code, half-written drafts — into MAGI, without breaking what is already there."
commands:
  adopt: "Bring an existing research folder into MAGI."
origin: magi
---

# adopt

## When to use
A folder with work already in it and no `threads/`. A project MAGI itself made
is `magi migrate`, not this.

## Method
1. `magi adopt survey .` — read the folder first. It also pulls every arXiv id
   and DOI out of the prose, which is where the library already is.
2. Collect what this conversation says about the work: papers named, claims
   made. Nothing there is a normal result — say "0 from the conversation".
3. `magi init` in place. It only adds; it touches nothing already there.
4. Write `{"moves": [{"from": "x", "to": "drafts/x"}]}` — others' material to
   `raw/`, the human's own working out to `drafts/`, code and data left alone.
   Shape it to MAGI: the references between the files are repaired for you.
5. Show the human the plan, then `magi adopt apply plan.json --dry-run`, then
   for real. `magi adopt undo` puts the files *and* the edited text back.
6. `magi ingest url <the ids>`, `magi ingest batch-run`, then `ingest`.
7. The part that matters: open what the material already claims — `magi thread
   new <slug> --kind proposition --title '<claim>' --purpose '<why now>' --bet
   unknown`. A plan index and a status board are lines and propositions already.
8. `magi index`, then `magi next`. Still "no propositions" means the folder was
   tidied, not adopted.

## Rules
- **Never** move anything the human has not seen listed in the plan first.
- **Never** put the human's own writing in `raw/`: it is re-ingested and never
  hand-edited, so a draft filed there can never be worked on again.
- A claim made in conversation is not evidence; it opens at `--bet unknown`.
- Two topics in one folder is ordinary. If the material splits, ask which
  project this is — that one is not yours to decide.
- Say what is **partial**: "3 of 5 placed" beats a summary that looks whole.
