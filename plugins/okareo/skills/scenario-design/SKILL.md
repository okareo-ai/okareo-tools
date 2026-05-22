---
name: scenario-design
description: >-
  Design a synthetic test scenario set from scratch with Okareo — diverse,
  edge-case inputs covering real workflows, user roles, and stress
  conditions. Use this skill whenever the user wants to create a test set
  from scratch, expand coverage, or generate scenarios — including requests
  like "create a test set for my agent", "generate scenarios to test this",
  "we need more test coverage", "build evals from scratch", or "what cases
  should I test". Use it even when the user does not say "Okareo" but is
  clearly trying to build synthetic test cases for an LLM app or agent. Not
  for converting production traffic into a test set (use
  `scenario-from-traces`) and not for running the set (use `evaluation`).
---

# Okareo: Scenario Design

This skill builds a synthetic scenario set — test cases composed from
scratch — so an LLM app or agent can be exercised against deliberate,
balanced coverage instead of whatever inputs happen to be lying around.

It is the front half of a testing workflow: this skill *builds* the set.
Running it — registering a target, choosing checks, scoring — is the
separate `evaluation` step that follows. For test cases drawn from real
production traffic instead of composed from scratch, use
`scenario-from-traces`.

## When this skill applies

Use it when the raw material is *intent*, not data: the user describes what
the system should do and wants a test set that covers it. If the user
already has production traces, logs, or incidents to turn into tests, that
is `scenario-from-traces`. If the set already exists and they want to score
it, that is `evaluation`.

## How the pieces fit

Okareo's MCP server provides the tools; this skill provides the method.
Never call the Okareo HTTP API directly — if a needed tool is unavailable,
say so and stop.

<!--
  TOOL NAMES: every name below must be a real Okareo MCP tool. The canonical
  list lives in scripts/validate_skills.py; `scripts/build.sh` runs the
  validator and will refuse to package an unknown tool name.
-->

| Step                | MCP tool                   | Purpose                                  |
| ------------------- | -------------------------- | ---------------------------------------- |
| Find existing sets  | `list_scenarios`           | Check for a set to extend rather than fork |
| Inspect a set       | `get_scenario`             | Read an existing set's rows and shape     |
| Create a set        | `save_scenario`            | Persist the composed rows as a set        |
| Extend a set        | `create_scenario_version`  | Append rows as a new version of a set     |

There is no MCP tool that generates scenario rows. Generation is *this
skill's* job: you compose diverse, realistic rows from the user's
description of the system, and `save_scenario` persists them. Treat the
rows as authored test data — design them deliberately, do not pad the set.

## The design loop

Follow these steps in order — scope before coverage, coverage before
composing rows, composing before persisting.

### 1. Scope the system under test

Establish, asking only what you cannot infer from the conversation or repo:

- **What the system does** — its purpose, who uses it, the workflows it
  supports. This decides what "good coverage" even means.
- **What a row looks like** — the shape of one `input` (a question, a task,
  a JSON object) and what the expected `result` should capture (a correct
  answer, a property the output must satisfy, a target end state).
- **What you are testing for** — broad coverage of normal use, or a focused
  probe of one risky area. This sets how wide the set should spread.

### 2. Design the coverage

A scenario set is only as good as its spread. Decide the coverage axes —
workflows, user roles, input difficulty, edge and stress conditions —
before writing any rows, so the set is balanced by design rather than by
accident.

See [references/coverage.md](references/coverage.md) for the axes to cover
and how to keep the set balanced across them.

### 3. Compose the rows

Write each row as an `input` and an expected `result`:

- Make every row a *distinct* case that exercises something the others do
  not — diversity is the point of a synthetic set.
- Write the expected `result` as the **correct** behavior: the right answer,
  or the property the output must satisfy. Be specific enough that a check
  can score against it.
- Include deliberate **edge and stress** rows — ambiguous inputs,
  out-of-scope requests, adversarial phrasings — not just happy-path cases.
- Tag rows by the coverage cell they came from, so evaluation results stay
  diagnosable.

### 4. Create or extend the set

Call `list_scenarios` first. Prefer **extending one coherent set** for a
given system with `create_scenario_version` over scattering near-duplicate
sets — evaluations only compare when they run against a stable set. Persist
a new set with `save_scenario`. Keep the returned scenario ID.

### 5. Hand off to evaluation

The set exists but has not been run. Report what was built — row count,
coverage cells — and hand off to `evaluation`: register a target, choose
checks that target the behaviors this set exercises, and run it.

## Reporting format

```
## Scenario set: <name>  (scenario id: <id>)
Built from: <the system description>
Rows: <count>  across <N> coverage cells

### Coverage
- <axis / cell> — <row count> — <what these rows probe>
- ...

### Next step
Run as an evaluation; suggested checks: <...>
```

## Guardrails

- Never fabricate run results, scores, or transcripts — this skill composes
  test *inputs and expected behavior*, never outcomes of a run that has not
  happened.
- A set of twenty rephrasings of one happy-path case is not coverage. Insist
  on spread across the axes in `references/coverage.md`.
- Write expected results as the *correct* behavior, specific enough to score
  — never as a vague "responds well".
- If the correct behavior for a case is genuinely unclear, ask the user
  rather than guessing — a wrong expected result locks a wrong answer in.
