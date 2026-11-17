---
name: voice-simulation
description: >-
  Run voice-first multi-turn simulations against a voice or phone agent in Okareo — spoken
  turn-by-turn calls from a simulated caller. Use for "test my voice agent", "simulate a phone
  call to my bot", "place test calls", "how does my voice assistant handle an angry caller". For
  text agents use agent-simulation; for live calls use monitoring.

---

# Okareo: Voice Simulation

This skill exercises a voice agent the way real callers would — across many
personas, many goals, many turns of spoken conversation — so failures
surface in simulation rather than on a live call with a real user.

It is the voice counterpart to `agent-simulation`: same Target / Driver /
Scenario method, but the driver speaks and the conversation is a call. When
a simulation surfaces failures worth locking in, hand off to
`scenario-from-traces`; to watch live production calls instead of simulating
them, use `monitoring`.

## When this skill applies

Use it when the goal is to *generate* spoken conversations against a voice
agent — probing, coverage testing, or hardening before release. For a
text-only agent or chatbot, use `agent-simulation`. For a brand-new user who
needs orientation first, `quickstart` sets the stage and routes here.

## How the pieces fit

Okareo's MCP server provides the tools; this skill provides the method.
Never call the Okareo HTTP API directly and never fabricate a transcript or
a call outcome — if a needed tool is unavailable, say so and stop.

<!--
  TOOL NAMES: every name below must be a real Okareo MCP tool. The canonical
  list lives in scripts/validate_skills.py; `scripts/build.sh` runs the
  validator and will refuse to package an unknown tool name.
-->

| Step                 | MCP tool                       | Purpose                                          |
| -------------------- | ------------------------------ | ------------------------------------------------ |
| Pick a caller voice  | `list_driver_voices`           | Find a voice, profile, and language for callers   |
| Register the agent   | `create_or_update_target`      | Point Okareo at the voice agent under test         |
| Build the caller     | `create_or_update_driver`      | Define a simulated caller as a voice persona       |
| Define the cases     | `save_scenario`                | Scenario rows — per-call goals and expected outcome |
| Augmentation ref     | `get_templates`                | Fetch `voice_augmentations` field schema for the `augmentation` param |
| Run                  | `run_simulation`               | Place the simulated calls and score them           |
| Read outcomes        | `get_test_run_results`         | Pull success rates and check results               |
| Read a call          | `get_conversation_transcript`  | Inspect an individual call transcript              |
| Deliver a code       | `send_inbox_message`           | Testing aid: hand a live call the message the agent "sent" |
| Agent dials: start   | `start_outbound_simulation`    | Get an Okareo number for the agent to call         |
| Agent dials: stop    | `stop_outbound_simulation`     | Give the number back and score the calls           |

A voice simulation, like a text one, has no single "create" tool — it is a
*target* (the voice agent), a *driver* (the simulated caller, with a voice),
and a *scenario* (per-call goals) run together. Discover existing pieces
with `list_targets`, `list_drivers`, and `list_simulations`; inspect a
check's rubric with `get_check`.

## The voice-simulation loop

Follow these steps in order — persona and voice before running, run before
analysis, and confirm before placing real calls.

### 1. Scope the voice simulation

Establish three things first:

- **What is under test** — a support line, a booking assistant, a triage or
  routing agent. This shapes which callers and goals make sense.
- **What you are probing for** — broad coverage, a specific suspected
  weakness, or how the agent holds up under difficult callers.
- **What "failure" means** — the outcomes the call must achieve and the
  behaviors the agent must not produce (going off-policy, looping, leaving
  the caller's goal unmet). Vague failure criteria produce unscored calls.

Then settle **who places the call**. Most voice agents answer: Okareo
dials them, and the rest of this loop applies. Some agents *place* calls —
a collections agent, an appointment reminder, a sales dialer. Okareo
cannot dial an agent like that; the agent has to call Okareo. That is an
**outbound simulation**, with its own start and stop steps: see
[references/outbound-simulations.md](references/outbound-simulations.md).

### 2. Pick caller voices and design personas

Call `list_driver_voices` and pick voices whose language matches the agent.
Then design the caller personas — see
[references/voice-personas.md](references/voice-personas.md) for caller
personas and objectives specific to voice. In short: vary the *caller*, not
just the words — cooperative and difficult callers, clear and vague goals,
in-scope and out-of-scope requests — and give every caller one concrete
objective so the call has a point.

For a call that must go the same way every time — walking a phone menu,
reading back a fixed set of details, reproducing a reported call — script
the caller instead of describing a persona. See
[references/scripted-callers.md](references/scripted-callers.md).

### 3. Set stopping conditions and turn pacing

Every call needs a max-turn cap. Without one, a stuck agent produces an
endless call — and for a phone-based target that is an endless *billed*
call. Always set a cap high enough to finish a normal call.

`run_simulation` exposes four optional pacing knobs that round out the cap.
Pass them as kwargs alongside `max_turns`; default behaviour is unchanged
when you leave them out:

- `turn_transition_time` — ms of pause between turns. Raise it for
  STT-heavy agents whose "let me check" filler would otherwise get talked
  over by a quick caller.
- `silence_timeout_ms` — ms of silence before the simulator advances. Give
  the agent room during tool calls or holds without letting it stall.
- `checks_at_every_turn` — `True` evaluates checks per turn, not just at
  end-of-call. Use it when the agent might say the right thing at turn 4
  and the wrong thing at turn 12.
- `stop_check` — `{"check_name": str, "stop_on": <value>}` halts the call
  the moment that check returns the configured value. Right for "stop if
  the agent leaks PII" — the run short-circuits before reaching `max_turns`.

### 4. Register the voice agent as a target

Register the agent with `create_or_update_target` as a voice target. The
*kind* depends on how the agent is reached: a phone number Okareo dials for
you, a number dialed through the user's own carrier account, a SIP address,
or a LiveKit room. See
[references/voice-targets.md](references/voice-targets.md) for choosing a
kind and what each one needs. **To change an existing voice target**, save
it again with only the setting that changes: everything left out, stored
credentials included, is kept. See *Changing or copying a voice target*
there.

Two things about the call path are also set on the target. If the agent
**texts or emails the caller a verification code** partway through, the
simulated caller needs an inbox to receive it — see
[references/verification-codes.md](references/verification-codes.md). If
the agent sits **behind a main line and an extension**, the target can dial
the extension once the line answers; the same reference covers it.

### 5. Decide whether to augment the call audio

A voice simulation runs on a clean line by default — no noise, no second
voice, no interruptions. That's the right setting for proving the agent's
*conversation logic*. To prove its **resilience**, layer an augmentation on
top: a caller who interrupts, a noisy room, a second voice nearby, off-mic
stretches, a "stack-two-questions" pattern, or a line that cuts out
entirely. The MCP exposes seven augmentation knobs and a composition rule
(at most one non-noise strategy plus optionally `noise`). See
[references/voice-augmentations.md](references/voice-augmentations.md) for
the judgment call — *should I augment, and which one* — and call
`get_templates(["voice_augmentations"])` for the exact field schema.

Skip augmentation on first scoping runs and on pure-logic failure
investigations; reach for it once the conversation logic is proven and the
user wants production-condition coverage.

### 6. Configure and run the simulation

- Build the simulated callers with `create_or_update_driver` — each a voice
  persona from step 2, with a voice, profile, and language, plus brief voice
  instructions for natural speech.
- Write the per-call goals as scenario rows with `save_scenario`: each row's
  `input` is the caller's situation and goal, and its `result` is the
  outcome a successful call reaches.
- Decide who speaks first: the agent greets first, as it would answering a
  call, or the caller opens. Match production. This is only about the
  first words. **Who places the call** is a separate question, settled in
  step 1: if the agent is the one that dials, this step does not apply —
  follow [references/outbound-simulations.md](references/outbound-simulations.md)
  instead.
- Choose checks at run time. Always include a check that judges whether the
  call reached the scenario's expected result — a call with no completion
  check produces a transcript nobody can score. Add one or two checks for
  the business case.
- If step 5 said yes, pass `augmentation={...}` to `run_simulation` along
  with any of the pacing kwargs from step 3.
- **Check the pieces fit before dialing.** `run_simulation` compares the
  scenario fields the target and driver refer to against the scenario
  itself, and refuses a run that could never dial (a target that dials a
  field the scenario does not have). It can also report without running.
  Fix what it names rather than overriding it.
- **Confirm with the user before running.** A target that dials a phone
  number places real phone calls that incur telephony cost. Then call
  `run_simulation`; it returns immediately with a test-run id and app link.
  Poll `get_test_run_results` rather than assuming failure.

### 7. Analyze transcripts, do not just count

- Lead with the **headline**: across the caller set, what share of calls
  reached the goal without a failure.
- Read the **failing calls** with `get_conversation_transcript` and find the
  pattern — does the agent break with one caller type, at a certain turn
  depth, on out-of-scope requests? Name the failure mode.
- Separate **agent failures** from **caller artifacts** and **transcription
  noise** — a misheard word is the transcriber's error, not the agent's.
  Flag those rather than counting them against the agent.
- Translate findings into concrete fixes, or "ready to ship".

### 8. Hand off

For failures worth preventing permanently, hand off to
`scenario-from-traces` — it turns the failing calls into a durable scenario
set you can re-run on every change.

## Reporting format

```
## Voice simulation: <agent under test>
Augmentation: <strategy + params, or "none — clean line">
Callers: <count> across <N> persona types
Outcome: <success rate> — <ready to ship under these conditions? y/n>

### Failure modes
- <mode> — <which callers / turn depth> — <suggested fix>
- ...

### Next step
Lock failing calls into a scenario set via scenario-from-traces.
```

When an augmentation is active, name it in the report header. "95% success
under barge-in over cafeteria noise" is a different claim than "95% success
on a clean line" — never collapse them.

## Guardrails

- Never fabricate a transcript, a check result, or a call outcome — every
  figure comes from a `get_test_run_results` or `get_conversation_transcript`
  call.
- A voice target that dials a number places real phone calls to real
  numbers. Confirm with the user before running, and never call a number
  they did not give.
- Always set a max-turn cap — a stuck agent on a phone target runs up a
  billed call with no end.
- Always include a completion check. A voice simulation with nothing scoring
  call success produces transcripts and no judgement.
- Distinguish agent failures from unrealistic caller behavior and from
  transcription noise before reporting a failure rate.
