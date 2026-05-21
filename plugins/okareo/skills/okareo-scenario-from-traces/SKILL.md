---
name: okareo-scenario-from-traces
description: >-
  Turn production traces, logs, incidents, and issue reports into a reusable
  Okareo scenario set for evaluation. Use this skill whenever the user wants
  to build a test set from real traffic — including requests like "turn
  these logs into evals", "we had an incident, make a regression test",
  "convert these traces into a scenario set", "build a test set from
  production", "these support tickets show a bug", or any time real-world
  failures need to become repeatable test cases. Use it even when the user
  does not say "Okareo" but is clearly trying to capture observed behavior
  as a test set.
---

# Okareo: Scenario from Traces

This skill captures what actually happened in production and turns it into a
durable test set, so a bug that bit users once can never come back unnoticed.

It is the front half of an evaluation workflow. This skill *builds* the
scenario set; the `okareo-evaluation` skill *runs* it. When the set is ready,
hand off to that skill rather than scoring outputs here.

## When this skill applies

Use it when the raw material is real-world: production traces, application
logs, error-tracker issues, support tickets, an incident write-up, or the
failing rows from a previous evaluation. If the user wants to invent test
cases from scratch instead, that is ordinary scenario authoring — go
straight to `okareo-evaluation`.

## How the pieces fit

Okareo's MCP server provides the tools; this skill provides the method.
Never call the Okareo HTTP API directly and never fabricate trace data — if
a needed tool is unavailable, say so and stop.

<!--
  TOOL NAMES: keep this table in exact sync with the tools the Okareo MCP
  server actually exposes. Rename on both sides in the same release.
-->

| Step                 | MCP tool                       | Purpose                                    |
| -------------------- | ------------------------------ | ------------------------------------------ |
| Pull production data | `query_analytics`              | Retrieve logged production traffic         |
| Read a transcript    | `get_conversation_transcript`  | Inspect an individual logged conversation  |
| Find existing sets   | `list_scenarios`               | Check for a scenario set to extend         |
| Create a set         | `save_scenario`                | Persist new scenario rows as a set         |
| Extend a set         | `create_scenario_version`      | Append rows as a new version of a set      |

Failing rows from a prior evaluation come from `get_test_run_results`. If the
raw material is a file or pasted text the user provides, you do not need
`query_analytics` — work from what they gave you.

## The build loop

Follow these steps in order. The order matters: scrubbing before selection,
selection before mapping, and mapping before persisting anything.

### 1. Gather the raw material

Identify the source and pull it in:

- **Okareo monitoring** — use `query_analytics`, filtered to the
  time window, model, or error condition the user names, and
  `get_conversation_transcript` to read individual conversations.
- **External logs, error tracker, or tickets** — work from the file or text
  the user provides.
- **A prior evaluation** — the failing rows are already near-scenario shape;
  this is the fastest source.

Find out what the user is trying to protect against: a specific incident, a
recurring class of complaints, or a general "harden our tests" goal. That
framing decides which traces matter.

### 2. Scrub sensitive data — before anything else

Production traces contain real user data: names, emails, payment details,
internal identifiers, secrets. A scenario set is **stored and shared
workspace-wide**, so anything that enters it is no longer ephemeral.

Redact PII and secrets out of every trace before it becomes a scenario row.
Replace real values with realistic placeholders that preserve the shape of
the input — a redacted trace must still exercise the same behavior. If a
trace cannot be scrubbed without destroying what it tests, drop it and note
why rather than persisting raw user data.

### 3. Cluster and select — do not convert everything

A scenario set built by dumping every trace is noisy and slow, and it
over-weights whatever was most common in the window. Instead:

- Group traces by **failure mode or behavior** — same root cause, same
  cluster.
- From each cluster, take a few **representative** cases plus any
  **adversarial edge** that triggered the worst behavior.
- Keep the set balanced across clusters so the eval's headline number is not
  dominated by one noisy category.

See [references/trace-mapping.md](references/trace-mapping.md) for clustering
strategy and how many rows to take per cluster.

### 4. Map each trace to a scenario row — the careful part

A trace records what the system *did*, not what it *should* have done.
Getting the expected result right is the whole game:

- **Failure traces** — the input is the trace's input. The expected result
  is the **corrected** behavior, derived from the issue report, the user, or
  clear domain logic. Never copy a buggy output into the expected field;
  that locks the bug in as "correct" forever.
- **Good traces you want to protect** — the observed output becomes the
  expected result. This builds a regression guard around behavior that is
  currently right.
- **Tag every row** with the failure mode or cluster it came from, so the
  evaluation results stay diagnosable.

`references/trace-mapping.md` covers how to extract the input/expected pair
from chat, RAG, and agent trace shapes specifically.

### 5. Create or extend the scenario set

Call `list_scenarios` first. Prefer **extending one coherent set**
for a given system over scattering many near-duplicate sets — evaluations
are only comparable when they run against a stable set.

Persist a new set with `save_scenario`, or append to an existing one with
`create_scenario_version`. Keep the returned scenario ID — the evaluation
step needs it.

### 6. Hand off to evaluation

The set now exists but has not been run. Tell the user what was built — how
many rows, which clusters, which failure modes — and hand off to the
`okareo-evaluation` skill to register a target, choose checks, and run it.
The checks should target the exact failure modes this skill surfaced.

## Reporting format

Summarize the build like this so the user can sanity-check it before running:

```
## Scenario set: <name>  (scenario id: <id>)
Source: <where the traces came from>
Rows: <count>  across <N> clusters

### Clusters
- <failure mode> — <row count> — expected behavior: <how it was derived>
- ...

### Next step
Run with the okareo-evaluation skill; suggested checks: <...>
```

## Guardrails

- Never persist un-scrubbed PII or secrets into a scenario set.
- Never copy a faulty production output into the expected-result field — the
  expected result is the *corrected* behavior, not the observed one.
- Do not over-fit: one incident should not become fifty near-identical rows.
  A handful of representative cases generalizes better.
- If you cannot confidently determine the correct expected behavior for a
  trace, flag it for the user instead of guessing.
