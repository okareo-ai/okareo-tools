---
name: okareo-evaluation
description: >-
  Design, run, and analyze evaluations of LLM apps and agents with Okareo.
  Use this skill whenever the user wants to test, evaluate, benchmark, or
  measure the quality of a model, prompt, RAG pipeline, or agent — including
  requests like "is this prompt good", "did my change regress anything",
  "build a test set", "why is the agent failing", or any mention of evals,
  scenario sets, checks, or Okareo. Use it even when the user does not say
  the word "Okareo" but is clearly trying to judge whether an AI system
  behaves correctly.
---

# Okareo Evaluation

This skill turns Claude into a disciplined evaluation engineer. It does not
score outputs by eyeballing them — it drives the **Okareo MCP server** to run
reproducible evaluations, then interprets the results.

## When this skill applies

Use it for any task where the real question is "is this AI system good
enough?" — comparing prompt versions, catching regressions before a deploy,
building a test set from production traffic, or diagnosing why an agent fails.
If the user just wants to *run* the model once, that is not an evaluation;
answer directly instead.

## How the pieces fit

Okareo's MCP server gives you the *tools*. This skill gives you the *method*.
The server tools (names below) are the only way to touch Okareo — never call
the Okareo HTTP API directly, and never fabricate scores. If a needed tool is
unavailable, say so and stop rather than guessing.

<!--
  TOOL NAMES: the names below are the contract between this skill and the
  Okareo MCP server. Keep them in exact sync with the tools the server
  actually exposes. If you rename a server tool, update this list in the
  same release.
-->

| Step              | MCP tool                  | Purpose                                    |
| ----------------- | ------------------------- | ------------------------------------------ |
| List existing     | `okareo_list_scenarios`   | Find scenario sets already in the project  |
| Build a test set  | `okareo_create_scenario`  | Upload inputs + expected results           |
| Register a target | `okareo_register_model`   | Point Okareo at the model/endpoint to test |
| Run               | `okareo_run_evaluation`   | Execute checks against the target          |
| Read results      | `okareo_get_evaluation`   | Pull scores, pass rates, and per-row detail|
| Inspect a check   | `okareo_list_checks`      | See available checks and their definitions |

## The evaluation loop

Follow these steps in order. Do not skip ahead to running an evaluation
before the scenario set and checks are settled — a run against a vague test
set produces numbers nobody can act on.

### 1. Scope the evaluation

Establish four things before touching any tool. Ask the user only for what
you genuinely cannot infer from the conversation or repo:

- **What is under test** — a single prompt, a RAG pipeline, a tool-using
  agent, or a base model. This determines which checks make sense.
- **What "good" means** — the specific behaviors that must hold (e.g.
  "answers only from retrieved context", "never recommends a competitor",
  "valid JSON every time"). Vague goals produce vague evals.
- **The comparison** — is this an absolute bar, or a regression check
  against a previous version? Regression checks need a baseline run to
  compare against.
- **Where the test data comes from** — an existing scenario set, a file the
  user has, or production traffic that needs to be turned into one.

### 2. Assemble the scenario set

A scenario set is the test data: input rows, each optionally paired with an
expected result. Quality of the eval is capped by quality of this set.

- Call `okareo_list_scenarios` first — reuse an existing set when one fits
  rather than creating a near-duplicate.
- When building a new set, cover the **boring middle, the edges, and the
  adversarial cases**. A set that only contains easy inputs will report a
  high score that means nothing.
- Aim for enough rows that a single flaky output cannot swing the headline
  number — a few dozen is a reasonable floor for most tasks.
- Create it with `okareo_create_scenario` and keep the returned scenario ID.

### 3. Choose checks

Checks are the assertions Okareo evaluates each row against. Call
`okareo_list_checks` to see what is available, then select deliberately.
See [references/checks.md](references/checks.md) for how to pick checks per
system type and how to write a custom check when the built-ins do not fit.

Prefer a small set of checks that map directly to the "what good means"
criteria from step 1. Ten loosely-related checks are worse than three that
each correspond to a real failure the user cares about.

### 4. Register the target and run

- Register what is under test with `okareo_register_model`.
- For a regression check, make sure a baseline evaluation exists first —
  either a prior run or a run of the previous version — so the comparison
  has something to stand on.
- Start the run with `okareo_run_evaluation`. Runs can take time; if the
  tool reports the run is still in progress, wait and poll
  `okareo_get_evaluation` rather than assuming failure.

### 5. Interpret, do not just report

This is where the skill earns its keep. A pass rate alone is not an answer.

- Lead with the **headline result** and whether it clears the bar from
  step 1.
- Pull the **failing rows** and look for a pattern — are failures clustered
  on one input type, one check, one edge case? Name the pattern.
- For a regression check, separate **new failures** from pre-existing ones.
  A change that fixes two rows and breaks five is a regression even if the
  overall number barely moved.
- Translate findings into **concrete next actions**: a prompt change, a
  retrieval fix, a guardrail, or "ship it". Tie each action to the rows
  that motivate it.

### 6. Iterate

After the user applies a fix, re-run the *same* scenario set and checks so
the comparison is honest. Keep the scenario ID and check selection stable
across iterations — changing the test set between runs makes the numbers
incomparable.

## Reporting format

Always structure the final summary like this so results are scannable:

```
## Evaluation: <what was tested>
Result: <pass rate / score> — <clears the bar? regression? y/n>

### What failed
<the pattern, not a row-by-row dump>

### Recommended actions
1. <action> — motivated by <which failures>
2. ...
```

## Guardrails

- Never invent scores, pass rates, or row counts. Every number comes from an
  `okareo_get_evaluation` result.
- If the scenario set is too small or too easy to support a conclusion, say
  so plainly instead of reporting a misleadingly clean result.
- If a tool errors or a run does not complete, report exactly what happened
  and stop — do not paper over it with an estimated result.
