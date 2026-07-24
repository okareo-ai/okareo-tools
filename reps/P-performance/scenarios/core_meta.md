---
name: core
description: "Consolidated Performance judge-graded row bank — the judge-scored Performance probes that share run parameters, as standardized rows (contracts/scenario-row.md, feature 002)."
evaluation_mode: multi-turn
reps_pillar: Performance
sub_capabilities: "degradation, barge-in"
importance: Medium
modality: both
severity: medium
artifact_type: scenario
checks: perf-expectation-met
status: active
version: 0.3.0
---

# Scenario bank: core

The judge-graded Performance probes whose run parameters are compatible (single run, high turn
budget) — merged into one simulation on the `steady-caller` voice and the
`perf-expectation-met` rubric.

## Sub-capabilities covered

degradation · barge-in (run at max_turns 16 — the degradation budget; barge-in ends earlier when
its script completes).

## Why the other Performance probes stay separate (FR-002)

Performance is the documented run-parameter exception (Constitution V; research D6):

| Probe | Kept separate because | Check |
|---|---|---|
| output-consistency | needs `repeats: 5` — the consistency measurement IS the repeat | perf-output-equivalence (rubric) |
| turn-latency-budget | deterministic metric, `repeats: 3` | perf-turn-latency.py (code) |
| concurrency-load | deterministic metric under `repeats: 5` load | perf-error-rate.py (code) |

Merging these into core would corrupt the measurement (running degradation at 4 turns, or
consistency without repeats). They remain their own simulations and are counted within the suite
run budget (SC-001).

## Interpreting results

Pass = the row's `result` (pass criterion) held. Per-turn latency / time-to-first-audio remains a
present-but-unverifiable signal unless the target is instrumented (scoring marks it, never
silently passes it).
