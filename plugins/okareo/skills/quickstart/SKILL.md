---
name: quickstart
description: >-
  Onboard a developer to Okareo — verify the MCP connection works, explain
  the Target / Driver / Scenario model, and walk through a first simulation
  or evaluation. Use this skill whenever the user is new to Okareo, asks how
  to get started or set up, or asks what Okareo can do — including requests
  like "get me started with Okareo", "how do I set up Okareo", "what can
  Okareo do", "I want to try Okareo", or "help me run my first test". Use it
  even when the user does not say "Okareo" but is clearly new to AI
  evaluation and trying to test an agent or model for the first time. Not for
  a user who already has a configured target and a specific task — route
  straight to the matching skill instead.
---

# Okareo: Quickstart

This skill is the on-ramp to Okareo. It takes someone new and, in one guided
pass, confirms their connection works, teaches the handful of concepts
everything else is built on, and gets them through a first real run —
explaining each piece as it goes. It teaches by doing.

It is deliberately an orientation, not a workshop. Once the user understands
the model and has seen one run, the specialist skills take over: breadth and
tough personas belong to `agent-simulation` and `voice-simulation`, scoring
a fixed set belongs to `evaluation`, and watching production belongs to
`monitoring`.

## When this skill applies

Use it when someone is *new* to Okareo or asks how to get started, set up,
or what Okareo does. If the user already has a configured target and a
specific task ("run my regression suite", "monitor production"), skip the
onboarding and route straight to the skill that matches the task.

## How the pieces fit

Okareo's MCP server provides the tools; this skill provides the method.
Never call the Okareo HTTP API directly and never fabricate a result — if a
needed tool is unavailable, say so and stop.

<!--
  TOOL NAMES: every name below must be a real Okareo MCP tool. The canonical
  list lives in scripts/validate_skills.py; `scripts/build.sh` runs the
  validator and will refuse to package an unknown tool name.
-->

| Step                  | MCP tool         | Purpose                                       |
| --------------------- | ---------------- | --------------------------------------------- |
| Verify the connection | `list_tenants`   | Confirm the MCP is connected and authenticated |
| See what exists       | `list_targets`   | Show targets already in the workspace          |
| See what exists       | `list_scenarios` | Show scenario sets already in the workspace     |
| Read the docs         | `get_docs`       | Pull an Okareo concept doc when the user asks   |

This skill does not run the first test itself — it sets the stage and hands
off. The actual run is owned by `agent-simulation`, `voice-simulation`, or
`evaluation`, so the user learns the skill they will keep using.

## The quickstart loop

Follow these steps in order — connection before concepts, concepts before
the first run.

### 1. Verify the connection

Call `list_tenants`. A successful response means the Okareo MCP server is
connected and the user is authenticated — say so plainly. If it errors,
the connection is not set up: the user needs to sign in (the remote MCP uses
browser OAuth on first use) or, for a headless/CI setup, set an
`OKAREO_API_KEY`. Stop here and walk them through that before going on.

### 2. Teach the model

Before building anything, make sure the user understands the four pieces
every Okareo run is made of — Target, Driver, Scenario, Checks — and how a
simulation differs from an evaluation. Keep it short and concrete.

See [references/concepts.md](references/concepts.md) for the explanations to
draw from, and use `get_docs` if the user wants to read further.

### 3. Find the user's starting point

Establish two things, asking only what you cannot infer:

- **What they want to test** — a text agent or chatbot, a voice/phone agent,
  or an LLM app whose output quality they want to score.
- **What they have** — a running agent to point at (simulation), or a set of
  inputs with expected results (evaluation).

Also call `list_targets` and `list_scenarios`: if the workspace already has
relevant pieces, the first run can reuse them.

### 4. Hand off to the first run

Route to the skill that matches, and frame it as their first run:

- **Text agent / chatbot** → `agent-simulation`.
- **Voice or phone agent** → `voice-simulation`.
- **Scoring outputs against expected results** → `evaluation`.

Tell the user which skill is taking over and why. Stay light — let that
skill run its own loop; do not re-teach its steps here.

### 5. Point the way forward

After the first run, close the loop: name the next things worth doing —
broader persona coverage, more scenario rows, wiring production traffic into
`monitoring` — so the user knows where to go next.

## Reporting format

```
## Quickstart: <what the user is testing>
Connection: <ok / not set up>

### What Okareo is
<two or three sentences grounding Target / Driver / Scenario / Checks>

### First run
Handed off to: <agent-simulation / voice-simulation / evaluation>
<one line on what that run will do>

### Next step
<broader coverage, more rows, or monitor production>
```

## Guardrails

- Never fabricate a result, a transcript, or a connection status — every
  figure comes from a real tool call.
- If `list_tenants` errors, the connection is not set up. Fix that first;
  do not proceed as if it worked.
- Keep onboarding to one run. Breadth and hard cases belong to the
  specialist skills — resist turning the quickstart into a full test suite.
- If a tool errors, report exactly what happened and stop — do not paper
  over it with an estimated result.
