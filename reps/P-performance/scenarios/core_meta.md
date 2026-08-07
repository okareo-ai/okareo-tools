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
version: 0.4.0
---

# Scenario bank: core

The judge-graded Performance probes whose run parameters are compatible (single run, high turn
budget) — merged into one simulation on the `steady-caller` voice and the
`perf-expectation-met` rubric.

## Sub-capabilities covered

degradation · barge-in (run at max_turns 16 — the degradation budget; barge-in ends earlier when
its guidance completes).

## Why the other Performance probes stay separate (FR-002)

Performance is the documented run-parameter exception (Constitution V; research D6):

| Probe | Kept separate because | Check |
|---|---|---|
| output-consistency | needs `repeats: 5` — the consistency measurement IS the repeat | perf-output-equivalence (rubric) |
| turn-latency-budget | latency measured against the profile budget, `repeats: 3` | perf-expectation-met (rubric); latency verdict computed in scoring |
| concurrency-load | error rate under `repeats: 5` load | perf-error-rate.py (code) |

Merging these into core would corrupt the measurement (running degradation at 4 turns, or
consistency without repeats). They remain their own simulations and are counted within the suite
run budget (SC-001).

## Interpreting results

Pass = the row's `result` (pass criterion) held. Turn-taking latency is measured from the run's own
agent-side metrics and compared against the profile's `latency_budget` in scoring, reported with
the budget's provenance. The per-turn *distribution* is not returned by a run, so a percentile is
never claimed — the report states what it compared (see `contracts/performance-signal.md`).
