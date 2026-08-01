---
name: simulate
description: >-
  Start an Okareo simulation against an agent — simulated multi-turn conversations with a text agent,
  or simulated calls to a voice agent. Use for "run a simulation", "simulate users against my agent",
  "test my phone bot", "red-team the chatbot", "how does it handle an angry caller". Routes to
  agent-simulation (text) or voice-simulation (voice).
argument-hint: "[voice|text]"
---

> **Canonical source**: this skill is developed in the private [`okareo-tools-dev`](https://github.com/okareo-ai/okareo-tools-dev) repository and published here by its publish pipeline. To propose a change, open an issue on okareo-tools — direct edits to this copy will be flagged as drift and blocked at the next publish.

# simulate

Run a simulation against an agent under test.

## What this does

Exercises an agent with simulated users across personas and goals, then reports where it breaks.

## Route

Decide text vs voice, using the argument if it says `voice` or `text`, otherwise asking: **is the
agent a voice/phone agent, or a text agent or chatbot?**

- Text agent or chatbot — use the **agent-simulation** skill.
- Voice or phone agent — use the **voice-simulation** skill. After routing, also ask whether the run
  should include realistic call-quality conditions (background noise, mid-utterance interruptions,
  off-mic speech, a second voice in the room) — those are *augmentations* the skill can layer on the
  clean default. Skip on a first scoping run; offer them on a "does the agent hold up in
  production?" run.

Hand the task to the chosen skill. It will ask its own scoping questions (what is under test, what to
probe for, inbound vs outbound) as part of its loop — do not pre-empt them here.
