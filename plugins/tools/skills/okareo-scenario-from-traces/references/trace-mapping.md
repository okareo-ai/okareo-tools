# Mapping traces to scenario rows

This file is loaded only when the build reaches the clustering and mapping
steps. It covers how to cluster traces, how many rows to take, and how to
extract an input/expected pair from each trace shape.

## Clustering strategy

Group traces by **root cause**, not by surface symptom. Two traces with
different error messages can share one cause; two with the same message can
have different causes. Read enough of each trace to judge the cause.

Typical clusters for an LLM system:

- Hallucination / unsupported claims
- Wrong format or schema violation
- Refused a request it should have answered (or vice versa)
- Retrieved the wrong context (RAG)
- Wrong tool call or bad arguments (agents)
- Correct behavior worth locking in as a regression guard

## How many rows per cluster

The goal is a set that generalizes, not one that memorizes an incident.

- Take **3–8 representative rows** per cluster — enough that one flaky
  output cannot swing the cluster's result.
- Always include the **worst single case** in the cluster (the adversarial
  edge), even if it is rare.
- Stop adding rows from a cluster once new traces stop teaching you anything
  new. Fifty near-identical rows from one incident is over-fitting.

## Extracting input and expected by trace shape

### Chat / completion trace

A trace of a single prompt-and-response exchange.

- **Input** — the prompt or message list sent to the model. Keep the system
  prompt only if it is part of what is under test.
- **Expected (failure)** — the corrected response, or a description of the
  property the response must satisfy.
- **Expected (good trace)** — the observed response, captured as a
  regression guard.

### RAG trace

A trace that includes a query, retrieved passages, and a generated answer.
Decide first **what you are testing**:

- Testing **generation** — fix the retrieved context as part of the input,
  so the eval isolates whether the model answers faithfully from it.
- Testing **retrieval** — the input is just the query; the expected result
  describes which passages or facts should have been surfaced.

Mixing both into one row makes a failure ambiguous — you will not know
whether retrieval or generation broke.

### Agent trace

A trace of a multi-step, tool-using run.

- **Input** — the task or goal the agent was given, plus any starting state.
- **Expected** — the correct end state, or the correct tool sequence if the
  path matters as much as the outcome.
- Capture intermediate steps only when a specific step is what failed;
  otherwise judge on the final state to keep the row robust.

## Deriving expected behavior from an issue report

When a trace comes from a bug ticket or incident, the report usually states
or implies the correct behavior. Extract it explicitly:

1. Read the report for the expected outcome the reporter described.
2. If the report only says what was wrong, infer the correct behavior from
   domain logic — and confirm it with the user when it is not obvious.
3. Write the expected result as the corrected behavior, never as the
   observed faulty output.

If neither the report nor clear domain logic settles what "correct" means,
do not invent it. Flag the trace for the user and leave it out of the set
until the expected behavior is decided.
