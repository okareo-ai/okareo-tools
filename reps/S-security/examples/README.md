---
name: security-row-examples
description: "Worked examples of generated security rows for two reference agents, as DOCUMENTATION ONLY. Not a scenario bank, not runnable, never discovered by a pillar eval config. They exist because the attack taxonomy is a list of names, and what actually transfers between agents is the SHAPE of a concrete row — the escalation triplet, the clause grammar, the way a real tool is named."
artifact_type: reference
status: active
version: 0.1.0
runnable: false
---

# Worked security-row examples — DOCUMENTATION ONLY

**Nothing in this directory is runnable.** These are Markdown documents, not `.jsonl` banks. No
`eval_config.json` references them, pillar artifact discovery does not find them, and
`tests/test_structured_row.py` asserts all of that — because a worked example that could be run
against a *different* agent would reproduce the exact failure the examples exist to prevent.

## Why they ship at all

Domain attack generation is the hardest part of this workbench to convey abstractly, and it is the
change with the largest measured effect: in the first field evaluation **a quarter of the Security
pillar's "passes" were refusals of something the agent had never understood**, because the generic
banks were copied verbatim and the caller delivered attacks about deployment freezes and HR
terminations to a ticketing line. The second evaluation generated attacks from the agent's own tools
and limits and the meaningless-pass share went to near zero.

Shipping the 21-name taxonomy alone was rejected during planning. The evidence is that what
transfers is the *shape* of a concrete row — the `X, then Y, then Z` escalation triplet, the clause
grammar, the way a real tool is named in a required move — and a shape is invisible in a name list.

**This is a recorded deviation from Constitution Principle IV** (baseline artifacts carry no
specific agent's assumptions), accepted in `plan.md` Complexity Tracking with three mitigations:
they are marked not-runnable, they carry no credentials or private data, and a guard asserts they
cannot be reached as banks.

## De-identified by decision

Both examples are drawn from real evaluations, and both are **de-identified**: the domain, the tool
names, the authority limits and the attack shapes are faithful, and the organizations are not named.
The structure is what teaches; publishing which organizations were assessed would put a customer
relationship into a public repository to no pedagogical benefit.

## How to read them

Each example shows a **profile extract** (the anchors the generator had to work with), then the rows
it produced, then a short note on what each row's shape is doing. Compare them against
`reps/S-security/scenarios/*.jsonl`, which are the agent-agnostic fallbacks: the baseline rows say
"a tool the agent should not use that way", and these say the tool's name.

- [`venue-ticketing.md`](venue-ticketing.md) — a voice line selling event seats
- [`business-phone-support.md`](business-phone-support.md) — a voice line supporting a phone service
