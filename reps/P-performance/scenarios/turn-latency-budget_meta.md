---
reps_pillar: Performance
modality: both
evaluation_mode: multi-turn
checks: "perf-turn-latency"
severity: medium
artifact_type: scenario
status: active
version: 0.3.0
---
Ordinary task run to measure per-turn latency against the profile's budget. Latency is computed from captured timing (scoring), not a model judge; the code check flags any latency hint present.
