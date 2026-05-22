---
name: evaluation
description: >-
  Design, run, and analyze evaluations of an LLM app's generated output with
  Okareo — scoring a model or prompt against a scenario set with checks. Use
  this skill whenever the user wants to test or benchmark output quality,
  catch regressions, or compare prompt or model versions — including requests
  like "evaluate my model", "benchmark output quality", "did this prompt
  change make things worse", "compare GPT-4 and Claude on our test set", or
  "run our evals". Use it even when the user does not say "Okareo" but is
  clearly trying to score an LLM's output against expected results. For
  generating synthetic conversations against an agent use `agent-simulation`;
  to build the scenario set first use `scenario-design` or
  `scenario-from-traces`.
---

# Okareo: Evaluation

This skill scores an LLM app's output against a scenario set, so quality is
a measured number with a per-row breakdown rather than an impression — and
so a regression shows up as a moved number before users feel it.

It is the back half of a testing workflow: the scenario set is *built* by
`scenario-design` (synthetic) or `scenario-from-traces` (from real traffic);
this skill *runs* it. For probing a multi-turn agent with simulated users
rather than scoring fixed inputs, use `agent-simulation`.

## When this skill applies

Use it when the inputs are *fixed* — a scenario set exists (or will) and the
user wants the target's output scored against it: benchmarking quality,
catching a regression, or comparing two prompt or model versions. If the
user wants Okareo to *generate* the conversation turn by turn, that is
simulation, not evaluation.

## How the pieces fit

Okareo's MCP server provides the tools; this skill provides the method.
Never call the Okareo HTTP API directly and never fabricate a score or a
per-row result — if a needed tool is unavailable, say so and stop.

<!--
  TOOL NAMES: every name below must be a real Okareo MCP tool. The canonical
  list lives in scripts/validate_skills.py; `scripts/build.sh` runs the
  validator and will refuse to package an unknown tool name.
-->

| Step                | MCP tool                       | Purpose                                       |
| ------------------- | ------------------------------ | --------------------------------------------- |
| Find the set        | `list_scenarios`               | Locate the scenario set to evaluate against    |
| Discover models     | `list_available_llms`          | See models available to evaluate                |
| Register the target | `register_generation_model`    | Register the model or prompt under test          |
| Choose checks       | `list_checks`                  | Find the checks that will score the output       |
| Run the evaluation  | `run_test`                     | Score the target against the scenario set        |
| Read results        | `get_test_run_results`         | Pull pass rates and per-row verdicts             |

Inspect a check's rubric before adding it with `get_check`, and browse
ready-made check definitions with `get_templates`. Compare against earlier
runs with `list_test_runs`. To re-score an existing run with a different set
of checks — without re-running the model — use `reevaluate_test_run`. Read
an individual flagged row in depth with `get_conversation_transcript`.

## The evaluation loop

Follow these steps in order — set and target before checks, checks before
running, run before interpretation.

### 1. Scope the evaluation

Establish, asking only what you cannot infer:

- **What is under test** — a specific model, a prompt, or a deployed
  endpoint. If the user is comparing versions, both belong in the same
  evaluation so the numbers are comparable.
- **The scenario set** — which set, and whether it already exists. Call
  `list_scenarios`. If no suitable set exists, stop and hand off:
  `scenario-design` to compose one, or `scenario-from-traces` to build one
  from real traffic. An evaluation with no scenario set has nothing to run.
- **What "good" means** — the properties the output must satisfy. This
  decides which checks to choose.

### 2. Register the target

Register the model or prompt under test with `register_generation_model`.
Use `list_available_llms` to pick a hosted model by its real identifier
rather than guessing a name. For a version comparison, register each version
so it can be run against the same set.

### 3. Choose the checks

Checks are what turn an output into a verdict. With `list_checks`, pick the
checks that score the properties from step 1 — correctness, format validity,
groundedness, tone, whatever "good" means here. Inspect any check you are
unsure of with `get_check`; browse `get_templates` for ready-made
definitions. Choose checks that target the failure modes that matter; a pile
of loosely related checks makes the result harder to read, not richer.

### 4. Run the evaluation

Start the run with `run_test` against the registered target, the scenario
set, and the chosen checks. Evaluations take time; poll `get_test_run_results`
rather than assuming failure.

### 5. Interpret the results

`get_test_run_results` returns the pass rates and per-row verdicts. Do not
stop at the headline number. See
[references/interpreting-results.md](references/interpreting-results.md) for
reading pass rates, isolating failure patterns, and comparing against a
prior run for regressions.

In short: lead with the headline pass rate, then find *where* the failures
cluster — one check, one kind of input, one model version — and read the
failing rows with `get_conversation_transcript` to name the failure mode.

### 6. Compare and hand off

- For a regression check or a version comparison, line this run up against
  the baseline with `list_test_runs` and report what moved.
- For failures worth preventing permanently, hand off to
  `scenario-from-traces` to lock the failing rows into the durable set.
- Translate findings into a concrete decision: ship, fix-then-rerun, or
  roll back.

## Reporting format

```
## Evaluation: <target under test>  (test run: <id>)
Scenario set: <name> — <row count> rows
Result: <pass rate> — <ship? / regression? / which version won>

### Where it failed
- <check or input cluster> — <pass rate> — <failure mode>
- ...

### vs baseline
<what moved against the prior run, or "no prior run">

### Next step
<ship, fix and re-run, or lock failing rows via scenario-from-traces>
```

## Guardrails

- Never fabricate a score, a pass rate, or a per-row verdict — every figure
  comes from a `get_test_run_results` call.
- Do not evaluate without a scenario set. If none exists, hand off to build
  one rather than inventing inputs inline.
- A headline pass rate with no failure breakdown is not an analysis. Always
  say where the failures cluster.
- When comparing versions or checking for a regression, compare against a
  run on the *same* scenario set — runs on different sets are not comparable.
- If a run errors or does not complete, report exactly what happened and
  stop — do not present an estimated result.
