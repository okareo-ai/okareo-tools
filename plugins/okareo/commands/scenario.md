---
description: >-
  Build an Okareo scenario set — either composed synthetically from scratch
  or captured from production traces, logs, and incidents.
argument-hint: "[synthetic|traces]"
---

# /okareo:scenario

Build a scenario set the user can run as an evaluation.

## What this does

Produces a scenario set, then points at running it. The set is either
designed from scratch or captured from real traffic.

## Route

Decide the source, using `$ARGUMENTS` if it says `synthetic` or `traces`,
otherwise asking one question: **compose the test cases from scratch, or
build them from real production traffic** (traces, logs, incidents,
tickets)?

- Synthetic / from-scratch — use the **scenario-design** skill.
- From real traffic — use the **scenario-from-traces** skill.

Hand the task to the chosen skill and let it run its loop. Both skills stop
once the set exists and hand off to `evaluation`.
