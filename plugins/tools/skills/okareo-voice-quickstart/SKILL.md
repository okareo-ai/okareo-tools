---
name: okareo-voice-quickstart
description: >-
  Onboard a voice agent to Okareo and run a first voice simulation end to
  end — a guided, teaching walkthrough for someone new to voice testing. Use
  this skill whenever the user has a phone-based voice agent (hosted on VAPI,
  LiveKit, Twilio, Telnyx, or any service) and wants to try testing it, or
  wants to understand how voice simulations work — including requests like
  "test my voice agent", "simulate a phone call to my bot", "how do voice
  simulations work", "onboard my voice agent", "set up my first voice eval",
  or "place a test call to my agent". It collects a phone number, language,
  and the agent's purpose, then builds the voice target, the simulated
  caller, a one-row scenario, and the checks, and runs one simulation. Use it
  even when the user does not say "Okareo" but is clearly trying to test or
  evaluate a voice or phone agent for the first time.
---

# Okareo: Voice Quickstart

This skill is the on-ramp to Okareo voice testing. It takes someone with a
working voice agent and, in one guided pass, builds everything a voice
simulation needs and places a first test call — explaining each piece as it
goes. It teaches by doing: by the end the user has seen a real simulated
call, scored, and understands the four parts that made it work.

It is deliberately narrow. It runs **one** clean call with **one**
cooperative caller so the mechanics are visible. Once the user is onboarded,
breadth — many personas, adversarial callers, coverage — belongs to
`okareo-agent-simulation`, and watching real production calls belongs to
`okareo-monitoring`.

## When this skill applies

Use it when someone is *new* to voice simulation and wants a working first
run, or asks how voice simulations work. If the user already runs voice
simulations and wants broader or tougher coverage, that is
`okareo-agent-simulation`. If they want to watch live production calls
rather than simulate one, that is `okareo-monitoring`.

## How the pieces fit

Okareo's MCP server provides the tools; this skill provides the method.
Never call the Okareo HTTP API directly and never fabricate a transcript or
a call result — if a needed tool is unavailable, say so and stop.

<!--
  TOOL NAMES: every name below must be a real Okareo MCP tool. The canonical
  list lives in scripts/validate_skills.py; `scripts/build.sh` runs the
  validator and will refuse to package an unknown tool name.
-->

| Step                  | MCP tool                       | Purpose                                              |
| --------------------- | ------------------------------ | ---------------------------------------------------- |
| Pick a caller voice   | `list_driver_voices`           | Find a voice, profile, and language for the caller   |
| Register the agent    | `create_or_update_target`      | Point Okareo at the agent's phone number             |
| Build the caller      | `create_or_update_driver`      | Define the simulated caller as a voice persona       |
| Define the test case  | `save_scenario`                | One scenario row — the call's goal and expected end  |
| Confirm the checks    | `list_checks`                  | Verify the checks to score the call exist            |
| Run                   | `run_simulation`               | Place the simulated call and score it                |
| Read the outcome      | `get_test_run_results`         | Pull the check results for the call                  |
| Read the transcript   | `get_conversation_transcript`  | Inspect what was actually said on the call           |

Use `get_check` to inspect a check's rubric before adding it, and `get_docs`
if the user wants to read more about a concept.

## The quickstart loop

Follow these steps in order — gather inputs before building, build before
running, and confirm before placing a real call.

### 1. Welcome the user and gather three inputs

Set expectations first: explain that you will onboard their voice agent,
build a simulated caller, place **one real test phone call** to their agent,
and walk through the scored result together.

Then ask for exactly these three things — nothing more, this is an
onboarding run, not a configuration interview:

- **A US-based phone number** where their voice agent answers calls. It can
  be hosted on VAPI, LiveKit, Twilio, Telnyx, or any provider — Okareo
  places an *outbound* call to that number, so the hosting provider does not
  matter as long as the number accepts inbound US calls.
- **The language** the agent operates in (for example en-US or es-US).
- **A short description of the agent's purpose** — what it does, who calls
  it, and what a successful call looks like. This one answer drives the
  caller persona, the scenario, and the checks, so draw it out if the user
  is terse.

### 2. Pick a voice for the simulated caller

Call `list_driver_voices` and choose a voice and profile whose language
matches the agent's. Tell the user which voice you picked and why, and offer
to swap it — hearing "your test caller will sound like X" makes the
simulation concrete.

### 3. Register the agent as a voice target

With `create_or_update_target`, create a voice target: target type voice,
edge type twilio, the destination phone number set to the agent's number,
and max parallel requests of 1. Explain what this is — the *target* is
Okareo's handle on the agent under test, and the twilio edge means Okareo
places an ordinary outbound phone call to it. One parallel call keeps the
first run simple and cheap.

### 4. Build the simulated caller

With `create_or_update_driver`, create the *driver* — the simulated caller.
Give it a persona prompt describing a realistic, **cooperative** first-time
caller with one concrete goal taken from the agent's purpose, and set the
voice, voice profile, and language from step 2 plus brief voice
instructions for natural speech (moderate pace, short utterances).

Keep this persona easy. Onboarding shows a clean, successful call; difficult
and adversarial callers are what `okareo-agent-simulation` is for. See
[references/voice-simulation-explained.md](references/voice-simulation-explained.md)
for how the target, driver, scenario, and checks fit together and how to
write a good caller persona and expected result.

### 5. Write the one-row scenario

With `save_scenario`, create a scenario with **exactly one row**:

- **input** — a JSON object giving the caller's situation and goal, with
  keys matching the parameters the driver persona prompt expects.
- **result** — the expected outcome of a *successful* call, in plain
  language: what the agent should have accomplished by the time the call
  ends. Make it specific and outcome-focused (not the agent's exact words) —
  this is the reference the checks score the call against.

### 6. Choose the checks and run

Call `list_checks` to see what is available. Always include the
"result_completed" check — it judges whether the call reached the expected
result recorded in the scenario row, which is the core signal of any voice
simulation; never run this skill without it. Then add one or two checks that
fit the business case (for a support agent, that the issue was resolved; for
a booking agent, that a booking was confirmed). Inspect any check you are
unsure about with `get_check`.

**Confirm with the user before running.** `run_simulation` places a real
outbound phone call to the number they gave and may incur telephony cost.
Then call `run_simulation` with the target, driver, and scenario, the chosen
checks, the first turn set to the target (the agent answers the phone and
greets first), a max-turns cap high enough to finish a short call (around
12), and a single repeat.

### 7. Read the result and teach

`run_simulation` returns immediately with a test-run id and an app link.
Pull the scores with `get_test_run_results` and the call with
`get_conversation_transcript`. This is the teaching payload — walk the user
through it, do not just hand over numbers:

- The **transcript** — what the simulated caller and the agent actually said,
  turn by turn.
- **"result_completed"** — did the call reach the expected result, and the
  reasoning behind the verdict.
- **Each business-case check** — what it measured and what it found.
- The **app link** — where to see and replay the run in the Okareo UI.

Then point the way forward: change the scenario's expected result and re-run
to watch the checks move, add more rows and tougher callers with
`okareo-agent-simulation`, and wire live production calls into
`okareo-monitoring`.

## Reporting format

```
## Voice quickstart: <agent purpose>
Agent number: <number>   Language: <lang>
Simulated caller: <voice> — <persona in a phrase>

### First call
result_completed: <pass / fail> — <one line on why>
<check>: <result> — <one line>
Transcript: <turn count> turns — <app link>

### What this showed
<one or two sentences explaining what a voice simulation is, grounded in
 what just happened on this call>

### Next step
<re-run with a tougher caller via okareo-agent-simulation, add scenario
 rows, or monitor production calls>
```

## Guardrails

- Never fabricate a transcript, a check result, or a call outcome — every
  figure comes from a `get_test_run_results` or `get_conversation_transcript`
  call.
- `run_simulation` places a real phone call to a real number. Confirm with
  the user before running, and never call a number the user did not give you.
- Always include the "result_completed" check. A voice simulation with no
  completion check produces a transcript nobody can score.
- Keep the first run simple — one cooperative caller, one scenario row. This
  skill onboards; `okareo-agent-simulation` is where hard personas and
  coverage belong. Resist turning the quickstart into a full test suite.
- If a tool errors or the call does not connect, report exactly what
  happened and stop — do not present an estimated result.
