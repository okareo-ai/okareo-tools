---
description: >-
  Guided onboarding to Okareo — verify the connection, explain the model,
  and walk through a first simulation or evaluation. For users new to
  Okareo or asking how to get started.
argument-hint: "[voice|text]"
---

# /okareo:quickstart

Onboard the user to Okareo and get them through a first real run.

## What this does

Confirms the Okareo connection works, teaches the Target / Driver / Scenario
model, and routes the user into their first simulation or evaluation.

## Route

`$ARGUMENTS` may name the kind of agent (`voice` or `text`). If it is empty,
ask one question: **is the agent under test a voice/phone agent, or a
text agent or model?** — then proceed.

Hand the task to the **quickstart** skill. It verifies the connection,
teaches the model, and itself hands off to `voice-simulation`,
`agent-simulation`, or `evaluation` for the first run. Do not run the first
test from this command — let the skill drive its loop.
