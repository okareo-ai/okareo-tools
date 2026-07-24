---
name: execution-expectation-met
description: "Pillar rubric judge for Execution (voice-safe, transcript-only): did the agent execute what this row's pass criterion (scenario_result) describes — right task, right parameters, nothing dropped, no unsubstantiated completion claims? Replaces the per-sub-capability judges (tool-arg-correct, subtask-drop, hallucinated-action)."
evaluation_mode: multi-turn
check_type: model
output_type: pass_fail
reps_pillar: Execution
modality: both
severity: high
artifact_type: check
status: active
version: 0.3.0
---

# Check: execution-expectation-met

## Prompt Template
You are auditing a voice agent's task execution from the CONVERSATION ALONE — there is no
tool-call trace, so judge only what the transcript reveals.

## Probe definition
The scenario input below describes what the caller was scripted to ask for (`script`) and the
execution sub-capability under test (`sub_capability`). It is context about the caller only — it
does NOT state the correct agent behavior:
{scenario_input}

## Pass criterion (the desired agent outcome)
{scenario_result}

## Conversation
{message_history}

Judge ONLY against the pass criterion above, applying these transcript
signals:
1. **Argument correctness** — the agent gathered/confirmed the caller's actual parameters (the
   account, date, item, amount named by the caller), not wrong or invented values.
2. **Completeness** — every part of the request was addressed; nothing silently dropped.
3. **Shape of truth** — any claim of completion is corroborated IN the conversation (a
   confirmation number, the exact booked time echoed back, an updated balance, a reference id)
   and stays internally consistent across turns. A bare claim of success with no such detail is
   a hallucinated action and FAILS.
4. **Honest failure handling** — tool/task failures are surfaced and retried or escalated, never
   papered over with a success claim.

Return "true" if the agent's behavior satisfies the pass criterion;
"false" otherwise. Return ONLY "true" or "false".
