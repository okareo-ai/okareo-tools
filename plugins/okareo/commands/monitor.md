---
description: >-
  Configure or review Okareo production monitoring — checks on live traffic,
  baselines, drift, and alerts, for a text or voice agent.
argument-hint: "[setup|review]"
---

# /okareo:monitor

Set up new production monitoring, or review monitoring already running.

## What this does

Puts continuous checks on live traffic and interprets the result, so quality
regressions are caught in production rather than by users.

## Route

This command routes to one skill — **monitoring** — but frame the task
first so the skill starts in the right place. Using `$ARGUMENTS` where it
says `setup` or `review`, otherwise ask:

- **Setting up new monitoring, or reviewing an existing monitor?**
- **Text traffic, or a voice agent's calls?** — voice traffic is wired in
  through a voice integration; the monitoring skill covers both.

Then hand the task to the **monitoring** skill and let it run its loop.
