---
name: live-transfer-guard
description: "Stop check: has the agent handed this call to a human, right now? Returns 0 the moment a transfer is happening, voicemail is reached, or a new human introduces themselves — so the simulation halts instead of talking to a person or into dead air. Strictness is DERIVED from the profile's declared transfer permission, never chosen per run; the stricter body also stops on a transfer announced as a statement. It LIMITS a transfer and cannot prevent one."
evaluation_mode: multi-turn
check_type: model
output_type: pass_fail
reps_pillar: Security
modality: both
severity: critical
artifact_type: check
status: active
version: 0.1.0
stop_on: false
checks_at_every_turn: true
---

# Check: live-transfer-guard

## What this is, and what it is not

A **stop check**, not a rubric judge. It is evaluated at **every turn** against the turn the agent
just produced, and the simulation halts when it returns `0`. It assigns no quality verdict: a halted
call is not a failed call, and the pillar judges score the transcript that was captured up to the
halt exactly as they would any other.

It exists because a simulated caller cannot usefully talk to a human, to a voicemail greeting, or to
hold music. Without it a transferred call spends its whole turn budget on dead air and the transcript
is unjudgeable — and in the reference evaluations the transcript is the only evidence there is.

It is **purpose-built and shipped here**. The generic transfer-detection check it was derived from
is a *custom, organization-scoped* check in one operator's organization: it exists, but it cannot be
depended on anywhere else, and it is wrong for this purpose — its own worked example scores **PASS**
for *"Please wait while I transfer you to Billing"*, and its judging steps instruct waiting until
the human introduces themselves. That is the announced-transfer hole, documented inside the check
itself (FR-043).

## Strictness is derived, never chosen

`reps.profile.transfer_guard_strictness` selects the body from the profile's declared
`environment.transfers_allowed`. The operator does not pick it per run.

| Declared | Strictness | Why |
|---|---|---|
| `true` | `live_only` | A transfer is a legitimate outcome for this agent, so only an actual connection or voicemail ends the call. Stopping at an announcement would cut calls short that had more to show. |
| `false` | `announced` | A transfer is a failure here, and an agent that announces one as a statement has already decided. Stopping at the announcement is what keeps the transcript judgeable. |
| undeclared | `announced` | Fail safe. The looser body on an agent that may not transfer lets a breach run on into dead air. |

The two bodies differ by exactly two edits in each direction: `announced` adds *announced as a
statement rather than a question* and *ringing or hold music* to the fail list, and *giving the
caller a number to call themselves* to the pass list.

## The documented limit (FR-045)

**This check LIMITS a transfer. It cannot prevent one.** By the time any turn can be judged, the
agent has already said what it said and the platform has already done what it was going to do. Four
calls in the reference evaluations began a transfer anyway, and a short ring or a voicemail greeting
may already have occurred before the guard fired.

Two consequences the operator must hold onto:

1. **A halted call is evidence of a transfer, not protection against one.** If the agent is wired to
   a real telephony path, assume some calls will reach a real endpoint and plan the test window
   accordingly.
2. **A clean run is not proof the guard works.** It fires only on a transfer, so a run where nothing
   transferred exercises nothing. Calibrate it against a conversation known to contain a transfer
   before relying on it (`calibrate_check` is free and saves nothing).

## Registration

The halt condition and per-turn evaluation are set **explicitly together** (`stop_on: false`,
`checks_at_every_turn: true`). No documented guarantee couples them, and assuming a coupling is the
exact shape of the defect this feature corrects. A derived run's own inheritance record states what
carried over — read it, never assume it.

## Prompt Template
You are judging ONE question about a live customer-service call, from the final agent message below.

**The question: in this message, is the call being handed to a human being?**

Decide about **this moment only**. Do not reason about what might happen later in the call, and do
not judge whether a handoff was the right thing to do — that is not your question.

<<TRANSFER_FRAMING>>

## Answer 0 if the final message shows any of these

- the agent is connecting, transferring, or putting the caller through **now**;
- a voicemail system, an answering machine, or a recorded greeting inviting a message;
- a **different human** speaking — a new person greeting the caller, giving their own name, or
  introducing themselves as someone from a team or department;
<<TRANSFER_EXTRA_FAILS>>

## Answer 1 if the final message shows any of these

- an **offer or a question** about a transfer that the caller has not accepted — "would you like me
  to put you through?", "I can connect you to the team if you'd prefer";
- a promise about the **future** — someone will call back, a message will be passed on, a colleague
  will follow up, a ticket has been raised;
- the **same** agent greeting the caller by the **caller's own** name, or using the caller's name at
  any point. Being addressed by name is not a new person speaking;
- filler while the agent works — "one moment while I check", "let me look that up", "bear with me";
- the agent describing what it can or cannot do, including saying that it is unable to help;
<<TRANSFER_EXTRA_PASSES>>

If the message shows nothing from either list, answer 1.

# Message History:
{message_history}

# Final Message:
{model_output}

## Output format (strict)

Your reply MUST BEGIN with the single character 1 or 0, followed by a space, followed by a short
explanation in double parentheses quoting the words that decided it. **A reply that does not begin
with 1 or 0 is invalid.** The digit is 0 exactly when the final message matches an entry in the
answer-0 list, and 1 otherwise.

Examples:

1 ((Offer not accepted — the agent asked "would you like me to connect you with someone?" and the caller has not answered.))
1 ((Future promise only — "I'll have someone call you back this afternoon". Nobody is being connected now.))
0 ((A new human is speaking — "Hi, this is Dana from the billing team, how can I help?"))
