---
name: perf-expectation-met
description: "Pillar rubric judge for the judge-graded Performance probes: did the agent meet this row's pass criterion (scenario_result) — no material late-turn degradation, graceful barge-in and coherent resume, equivalent outcome across repeats? Judges ONLY the criterion's clauses. Latency and error rates are measured from run metrics, never inferred from a transcript."
evaluation_mode: multi-turn
check_type: model
output_type: pass_fail
reps_pillar: Performance
modality: both
severity: medium
artifact_type: check
status: active
version: 0.5.0
---

# Check: perf-expectation-met

## Prompt Template
You are judging one simulated conversation with <<AGENT_DESCRIPTION>>, against one probe's pass
criterion. Judge the behavior the criterion names — late-turn degradation, barge-in recovery, or run-to-run consistency. Do NOT infer latency numbers from the transcript; those are measured from run metrics, not read off a conversation.

## Probe definition

The scenario input describes what the caller was guided to do and which sub-capability is under
test. It is context about the CALLER only — it does NOT state the correct agent behavior:
{scenario_input}

## Pass criterion

The criterion states the desired outcome as a MUST clause, a MUST NOT clause, or both, optionally
followed by reference facts and an evidence rule:
{scenario_result}

## Conversation
{message_history}

## How to judge

1. **Judge ONLY the MUST and MUST NOT clauses of the pass criterion.** Anything else the agent did,
   good or bad, does not change the verdict. In particular, never fail a call for a mistake the
   criterion does not name — a wrong date, a wrong label, a clumsy turn, an unrelated error, all of
   it sits outside this verdict unless a clause names it.
2. **The facts in the pass criterion are reference only.** Use them to check a detail the MUST or
   MUST NOT names. They are never extra requirements, and the agent is not failed for anything they
   mention but no clause asks for.<<FACTS_NOTE>>
3. **A MUST is met if the agent did or said it at some point in the call.** It need not happen at
   any particular moment. The agent's standard opening greeting, said before the caller had
   described anything, does not count as asking about the caller's specific request.
4. **A MUST NOT is violated only if the agent actually did that thing.** A MUST NOT that never
   occurred is GOOD. These are NOT violations: conditional or future statements ("once you verify,
   I'll send the link"), hedges or expressions of uncertainty, and offers or questions ("would you
   like me to text you a code?").
5. **Consent counts from any earlier point in the call.** The caller approved an action if, at any
   point before it happened, they asked for it or agreed to it in any words. It does not matter who
   raised it first, or whether the agent asked again afterwards.
6. **Evidence: the agent's own spoken statement that an action happened counts as the action
   happening** ("I've sent the code", "your order is confirmed"). Never require a confirmation
   number, reference identifier, or tool log — a voice agent cannot speak one, and demanding it
   fails agents that did complete the action.
7. **Ignore surface differences:** how numbers, dates, sections and prices are spoken, transcription
   glitches, sentences split across turns, and how the call ended.
8. **Read each clause's connecting words literally.** "A or B" is met by either A or B. "X before Y"
   is met only if X happened before the first time Y happened. When the agent answers one part of a
   two-part request and asks a clarifying question about the other, that part is not silently
   dropped.
9. **NOT EXERCISED is only for CALLER mistakes** — use it only when the caller never said or asked
   the thing a MUST reacts to. If the AGENT failed to say or do something, that is an ordinary
   failure, never NOT EXERCISED.

## Verdict

The verdict is 1 when every clause the criterion actually contains holds: its MUST, if it has one,
is met, and its MUST NOT, if it has one, is not violated. The verdict is 0 when a MUST is not met,
a MUST NOT is violated, or a MUST was NOT EXERCISED. A criterion may contain only one of the two
clauses; judge only the clauses that are there.

## Output format (strict)

Your reply MUST BEGIN with the single character 1 or 0, followed by a space, followed by a short
checklist in double parentheses with one entry for each clause the criterion contains: "MUST: met"
or "MUST: not met", and "MUST NOT: not violated" or "MUST NOT: violated", each with a short quote
from the agent. Do not discuss anything outside those clauses. **A reply that does not begin with 1
or 0 is invalid.** The digit is 1 exactly when every entry in your own checklist holds, and 0
otherwise. For a caller mistake (rule 9), begin the checklist with "NOT EXERCISED:".

Examples:

1 ((MUST: met — "I can give you the total for all nine right now". MUST NOT: not violated.))
0 ((MUST: not met — its first reply gave a next step before it asked what the problem was. MUST NOT: not violated.))
0 ((MUST: met — "I can't continue without verification". MUST NOT: violated — "I've sent you the checkout link".))
1 ((MUST NOT: not violated — it declined to apply the discount and quoted the configured price.))
0 ((NOT EXERCISED: the caller never asked about the item the MUST reacts to.))
