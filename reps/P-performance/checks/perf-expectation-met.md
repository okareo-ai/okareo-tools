---
name: perf-expectation-met
description: "Pillar rubric judge for the judge-graded Performance probes: did the agent meet this row's pass criterion (scenario_result) — no material late-turn degradation; graceful barge-in and coherent resume; equivalent outcome across repeats? Replaces perf-degradation, perf-barge-in, and perf-output-equivalence. Deterministic latency/error metrics stay in the .py code checks."
evaluation_mode: multi-turn
check_type: model
output_type: pass_fail
reps_pillar: Performance
modality: both
severity: medium
artifact_type: check
status: active
version: 0.4.0
---

# Check: perf-expectation-met

## Prompt Template
You are evaluating a voice agent's performance behavior on one probe, from the conversation.

## Probe definition
The scenario input below describes what the caller was guided to do (`guidance`) and the performance
sub-capability under test (`sub_capability`). It is context about the caller only — it does NOT
state the correct agent behavior:
{scenario_input}

## Pass criterion (the desired agent outcome)
{scenario_result}

## Conversation
{message_history}

Judge ONLY against the pass criterion above:
- **degradation** — compare early vs late turns; fail if answer quality or responsiveness clearly
  deteriorates over the session.
- **barge-in** — fail if the agent ignores the interruption, gets derailed, or cannot resume the
  prior task coherently.
- **consistency** — fail if repeated identical runs produce materially different outcomes.

Do NOT infer raw latency numbers from the transcript — that is measured by the code checks. Return
"true" if the agent's behavior satisfies the pass criterion; "false"
otherwise. Return ONLY "true" or "false".
