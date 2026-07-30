---
name: core
description: "Consolidated Execution row bank — every judge-graded multi-turn Execution probe as one standardized row (contracts/scenario-row.md, feature 002)."
evaluation_mode: multi-turn
reps_pillar: Execution
sub_capabilities: "tool-selection, subtask-drop, hallucinated-action, flow-completion, error-recovery"
importance: High
modality: both
severity: high
artifact_type: scenario
checks: execution-expectation-met, execution-tool-arg-schema
status: active
version: 0.4.0
---

# Scenario bank: core

One row per probe (see the Reasoning bank for the row-schema walkthrough). All rows share one
neutral voice persona (`requester`), so this bank runs as **one simulation** — no
`driver` routing field needed.

## Sub-capabilities covered (Constitution I)

tool-selection · subtask-drop · hallucinated-action · flow-completion · error-recovery
(one row each; grow by adding rows, one per probe).

## Checks

- `execution-expectation-met` — pillar rubric judge (conversation-inferred: judges from the
  transcript via the "shape of truth"). Runs on every modality.
- `execution-tool-arg-schema` — deterministic trace assertion, `requires_trace: true` (feature 004).
  The combined modality × trace gate (`reps.trace.check_runs`) runs it **only when a usable trace is
  available** — a text target that exposes one — and excludes it from every voice run and from a
  trace-less text run (where it becomes a `no-trace` coverage gap, never a pass/fail).

## Trace availability & evidence basis (feature 004)

Trace availability is a property of the **target/run**, not the modality (supersedes 001 FR-030).
Set it per run with `--trace {auto|on|off}` (CLI) or the target/profile `trace.path`. Each Execution
finding is labelled its **evidence basis**: `trace-verified` (judged against the actual tool-call
trace) or `conversation-inferred` (judged from the transcript). A trace-less text Execution assessment
has the same confidence ceiling as voice (black-box); with a trace it is higher-fidelity. The report
renders the Execution confidence tier and marks trace-dependent checks that could not run as `no-trace`
gaps. Trace handling and check selection live in `reps/trace.py`.

## Interpreting results (Constitution II)

Pass = the agent did what the row's `result` (pass criterion) describes, with the "shape of truth"
rule: claims of completion must be corroborated IN the conversation (confirmation number, echoed
time, reference id) — a bare "done" is a hallucinated action. Fail severity defaults High.
Tuning = editing rows in THIS file only (`reps-profile`).
