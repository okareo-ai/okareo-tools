---
reps_pillar: Performance
modality: both
evaluation_mode: multi-turn
checks: "perf-expectation-met"
severity: medium
artifact_type: scenario
status: active
version: 0.4.0
---
Ordinary task run whose latency is measured against the agent profile's `latency_budget`. The
latency verdict is computed in scoring from the run's own agent-side turn-taking latency and is
reported with the budget applied, that budget's provenance, and the basis of the comparison — a
model judge never infers timing from a transcript. The judge scores only what it can observe here:
whether the quick request was handled promptly and coherently.

There is deliberately no code check on this probe. A server-side code check receives one datapoint
and cannot reach the profile or the run-level metrics, so it could never decide a budget question —
it could only return a placeholder verdict.
