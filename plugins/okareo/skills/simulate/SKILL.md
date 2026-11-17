---
name: simulate
description: >-
  Start an Okareo simulation against an agent — simulated conversations with a text agent, a web
  app used through a browser, or simulated calls to a voice agent. Use for "run a simulation",
  "simulate users against my agent", "test my phone bot", "test the chat on our website", "red-team
  the chatbot". Routes to agent-simulation (text, web) or voice-simulation (voice).
argument-hint: "[voice|text|web]"
---

# simulate

Run a simulation against an agent under test.

## What this does

Exercises an agent with simulated users across personas and goals, then reports where it breaks.

## Route

Decide how the agent is reached, using the argument if it says `voice`, `text` or `web`, otherwise
asking: **is it a voice/phone agent, a text agent you can call through an API, or something a person
uses in a browser?**

- Text agent or chatbot with an API — use the **agent-simulation** skill.
- A web app or site with no API to call (a chat widget, a sign-in flow, a form) — use the
  **agent-simulation** skill and tell it the agent is reached through a browser. It registers a
  vision target and the simulated user works the page as a person would; its web-agents reference
  covers the differences.
- Voice or phone agent — use the **voice-simulation** skill. After routing, also ask whether the run
  should include realistic call-quality conditions (background noise, mid-utterance interruptions,
  off-mic speech, a second voice in the room) — those are *augmentations* the skill can layer on the
  clean default. Skip on a first scoping run; offer them on a "does the agent hold up in
  production?" run.

Hand the task to the chosen skill. It will ask its own scoping questions (what is under test, what to
probe for, who speaks first) as part of its loop — do not pre-empt them here. One thing is worth
passing along if the user has already said it: a voice agent that *places* calls rather than answering
them needs voice-simulation's outbound flow, where the agent dials an Okareo number.
