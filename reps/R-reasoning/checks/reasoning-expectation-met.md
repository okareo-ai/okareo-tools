---
name: reasoning-expectation-met
description: "Pillar rubric judge for Reasoning: did the agent do what this row's pass criterion (scenario_result) describes? Replaces the per-sub-capability judges (clarifying-question, intent-correct, constraint-retained) — the differentiating expectation lives in each scenario row's result."
evaluation_mode: multi-turn
check_type: model
output_type: pass_fail
reps_pillar: Reasoning
modality: both
severity: high
artifact_type: check
status: active
version: 0.4.0
---

# Check: reasoning-expectation-met

## Prompt Template
You are evaluating one simulated conversation with a voice agent's reasoning on one probe.

## Probe definition
The scenario input below describes what the caller was guided to do (`guidance`) and the reasoning
sub-capability under test (`sub_capability`). It is context about the caller only — it does NOT
state the correct agent behavior:
{scenario_input}

## Pass criterion (the desired agent outcome)
{scenario_result}

## Conversation
{message_history}

Judge ONLY against the pass criterion above — not against generic conversation quality, and not
against anything in the scenario input beyond what the caller did. Return "true" if the agent's
behavior satisfies the pass criterion; "false" if it
guessed, acted on a stale or wrong intent, missed the conflict, or violated the stated
constraint. Return ONLY "true" or "false".
