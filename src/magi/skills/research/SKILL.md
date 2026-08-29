---
name: research
description: "Investigate a question across the library from several angles at once, verify what comes back, and land it as propositions plus at most one synthesis."
commands:
  research: "Investigate a question from several angles and land the findings."
origin: magi
---

# research

## When to use
A question worth more than one search — including "find what contradicts
what", which is this skill with an adversarial brief, not a separate one.

## Method
1. Decompose the question into 3–6 angles that would disagree with each other.
   Say how many sub-agents that is before starting; 10 concurrent is the
   ceiling.
2. Each sub-agent searches the library only and returns findings in the block
   form `CLAIM: / EVIDENCE: "<quote>" / SOURCE_TYPE: / SOURCE:`, one per
   finding, `SOURCE` pointing into `raw/`.
3. Collect into `scratch/`, then `magi verify --json`. Unverified findings are
   reported as unverified, in their own section — never merged into the rest.
4. Every finding that has a truth value becomes a proposition:
   `magi thread new <slug> --kind proposition --title "<claim>" --purpose "<why>"`.
   A contradiction is one proposition with both sources posted to it, which
   puts it on the decision queue where a person will see it.
5. At most one long-form output: `wiki/topics/<slug>.md` with `type: synthesis`.
   If there is nothing to synthesise, the propositions are the result.
6. `magi validate --schema research`, then `magi lint --fix`.

## Rules
- **Never** report a synthesis as complete when an angle returned nothing.
  Name the angle that came back empty; a **partial** sweep read as whole is
  the failure this whole pipeline is arranged against.
- **Never** let a sub-agent answer from its own knowledge. The library is the
  only source; a finding with no `SOURCE:` in `raw/` is not a finding.
- A sub-agent that needs a decision returns
  `NEEDS-DECISION: <question> | options: <a> / <b> | default if unanswered: <x>`.
  Gather every NEEDS-DECISION and ask the human once, at the end.
