---
name: okareo-agent-simulation
description: >-
  Stress-test an agent or chatbot before production by running simulated
  multi-turn conversations against it with Okareo. Use this skill whenever
  the user wants to simulate users, run synthetic conversations, red-team an
  agent, probe for failure modes, or check how an agent behaves across many
  personas — including requests like "simulate users talking to my agent",
  "how does the bot handle an angry customer", "find where the agent breaks",
  or "run conversations before we ship". Use it even when the user does not
  say "Okareo" but is clearly trying to exercise an agent with synthetic
  conversations.
---

# Okareo: Agent Simulation

This skill exercises an agent the way real users would — across many
personas, many goals, many turns — so failures surface in simulation rather
than in production.

It is the pre-production counterpart to `okareo-monitoring`. Where
monitoring watches live traffic, simulation generates traffic on purpose.
When a simulation surfaces failures worth locking in as tests, hand off to
`okareo-scenario-from-traces`.

## When this skill applies

Use it when the goal is to *generate* conversations against an agent —
probing, red-teaming, or coverage testing before a release. If the user
already has real transcripts and wants to score them as-is, that is
evaluation — capture them as a scenario set with `okareo-scenario-from-traces`
and run checks over that set, rather than simulating new conversations.

## How the pieces fit

Okareo's MCP server provides the tools; this skill provides the method.
Never call the Okareo HTTP API directly and never invent simulation
transcripts — if a needed tool is unavailable, say so and stop.

<!--
  TOOL NAMES: keep this table in exact sync with the Okareo MCP server.
  Rename on both sides in the same release.
-->

| Step                  | MCP tool                       | Purpose                                        |
| --------------------- | ------------------------------ | ---------------------------------------------- |
| Register the agent    | `create_or_update_target`      | Point Okareo at the agent under test           |
| Design the persona    | `create_or_update_driver`      | Define the simulated user — persona and goal   |
| Define the test cases | `save_scenario`                | Scenario rows — per-conversation goals/seeds   |
| Run                   | `run_simulation`               | Execute simulated multi-turn runs              |
| Read outcomes         | `get_test_run_results`         | Pull success rates and check results           |
| Read transcripts      | `get_conversation_transcript`  | Inspect an individual conversation             |

Okareo has no single "create simulation" tool — a simulation is a *target*
(the agent), a *driver* (the simulated user persona), and a *scenario*
(per-conversation goals) run together. Discover existing pieces with
`list_targets`, `list_drivers`, `list_driver_voices`, and `list_simulations`.

## The simulation loop

Follow these steps in order — persona and goal design before running, run
before analysis.

### 1. Scope the simulation

Establish three things first:

- **What is under test** — a customer-support bot, a tool-using agent, a
  RAG assistant. This shapes which personas and goals make sense.
- **What you are probing for** — general coverage, a specific suspected
  weakness, or adversarial robustness (red-teaming). A focused probe needs
  fewer, sharper personas; coverage needs breadth.
- **What "failure" means** — the behaviors the agent must not produce
  (leaking data, recommending a competitor, looping, going off-policy) and
  the outcomes it must achieve. Vague failure criteria produce unscored runs.

### 2. Design personas and goals

A simulation is only as revealing as its personas. See
[references/persona-design.md](references/persona-design.md) for how to
build a persona set with real coverage.

In short: vary the *user*, not just the words. Cover cooperative and
difficult users, clear and vague requests, in-scope and out-of-scope goals,
and at least one adversarial persona that actively tries to break policy.
Give each persona a concrete goal so the simulated conversation has a point.

### 3. Set stopping conditions

A multi-turn simulation needs to know when a conversation ends — goal
achieved, an explicit max-turn cap, or a failure state. Without a turn cap,
a stuck agent produces an endless transcript. Always set one.

### 4. Register the agent and run

- Register the agent under test with `create_or_update_target`.
- Define the simulated user — persona, goal, and behavior — with
  `create_or_update_driver`, and the per-conversation goals/seeds with
  `save_scenario`. The checks that define failure are attached at run time.
- Start it with `run_simulation`. Simulations run many conversations
  and take time; poll `get_test_run_results` rather than assuming failure.

### 5. Analyze transcripts, do not just count

- Lead with the **headline**: across the persona set, what share of
  conversations reached the goal without a failure.
- Read the **failing transcripts** and find the pattern — does the agent
  break with one persona type, at a certain turn depth, on out-of-scope
  requests? Name the failure mode.
- Separate **agent failures** from **persona artifacts** — sometimes a
  simulated user behaves unrealistically and the "failure" is not the
  agent's fault. Flag those so the persona set can be fixed.
- Translate findings into concrete fixes: a prompt change, a guardrail, a
  tool fix, or "ready to ship".

### 6. Hand off

For failures worth preventing permanently, hand off to
`okareo-scenario-from-traces` — it turns the failing transcripts into a
durable scenario set you can re-run on every change.

## Reporting format

```
## Simulation: <agent under test>
Personas: <count> across <N> persona types
Outcome: <success rate> — <ready to ship? y/n>

### Failure modes
- <mode> — <which personas / turn depth> — <suggested fix>
- ...

### Next step
Lock failing transcripts into a scenario set via okareo-scenario-from-traces.
```

## Guardrails

- Never fabricate simulation transcripts or outcomes — every result comes
  from a `get_test_run_results` or `get_conversation_transcript` call.
- Always set a max-turn cap so a stuck agent cannot produce runaway runs.
- Distinguish agent failures from unrealistic persona behavior before
  reporting a failure rate.
- A simulation that only uses cooperative personas reports a flattering
  number that means little — insist on difficult and adversarial coverage.
