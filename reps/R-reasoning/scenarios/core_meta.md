---
name: core
description: "Consolidated Reasoning row bank — every judge-graded multi-turn Reasoning probe as one standardized row (contracts/scenario-row.md, feature 002)."
evaluation_mode: multi-turn
reps_pillar: Reasoning
sub_capabilities: "ambiguous-intent, slot-fill, intent-switch, contradiction, constraint-retention"
importance: High
modality: both
severity: high
artifact_type: scenario
checks: reasoning-expectation-met
status: active
version: 0.4.0
---

# Scenario bank: core

One row per probe. Each row carries its own `sub_capability` (report grouping key), `persona`
(demeanor rendered into the driver shell), `guidance` (the caller's behavioral arc), and
`result` (the pass criterion the `reasoning-expectation-met` rubric judges against).

## Sub-capabilities covered (Constitution I)

| sub_capability | rows | driver (voice/manner) |
|---|---|---|
| ambiguous-intent | 2 | confused-caller (confused) |
| slot-fill | 1 | confused-caller (confused) |
| intent-switch | 2 | assertive-caller (confident) |
| contradiction | 1 | assertive-caller (confident) |
| constraint-retention | 1 | assertive-caller (confident) |

## Separation rationale (FR-002)

This bank runs as **two simulations, one per voice persona** — confused vs. confident audible
demeanor is a driver-level voice property that prompt text cannot set. No other separation
exists: all rows share max_turns 10, `first_turn: target`, and the pillar rubric check. The
runner splits the bank by each row's `input.driver` (registered as `R-core-<driver>`).

## Interpreting results (Constitution II)

Pass = the agent did what the row's `result` describes (judge rationale attached per
probe). Fail severity comes from the row's `severity_on_fail` (default High for Reasoning).
Tuning to a specific agent = editing rows in THIS file only (`reps-profile`); drivers and the
check are agent-agnostic.
