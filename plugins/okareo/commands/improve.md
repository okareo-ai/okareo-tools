---
description: >-
  Iteratively improve an agent over a set number of cycles with Okareo —
  simulate, analyze, edit, re-verify, and track before/after metrics so you
  can see how much better the agent got.
argument-hint: "[cycles]"
---

# /okareo:improve

Run a diagnose-fix-verify loop against an agent, over several cycles, and
prove the improvement with a before/after trend.

## What this does

Runs the **simulate → analyze → edit → re-verify → compare** lifecycle for a
fixed number of cycles. Each cycle makes one attributable change and re-runs
the *same* eval harness, so progress is legible across runs. The eval is
delegated to the Okareo simulation skills; the agent edit is delegated back to
you via an Edit Target (a local repo, an MCP tool in your environment, or a
diff you apply yourself).

## Route

This command routes to one skill — **agent-improvement-loop** — but frame the
task first so the skill starts in the right place. Using `$ARGUMENTS` for the
cycle count if given, otherwise ask:

- **How many cycles?** — default 3 if the user has no preference.
- **Where and how is this agent edited?** — the Edit Target. This is the one
  thing only the user knows: a local repo and the file/field to change, an MCP
  tool in their environment, or "I'll apply the diff myself."
- **What does success look like, and what counts as a failure?** — a concrete
  definition; the loop refuses to run without one.

Mention that cycles place real, billed calls if the agent is a voice/phone
target, and that the loop starts in **supervised** mode (it pauses for approval
on each proposed change) until the user opts into auto mode.

Then hand the task to the **agent-improvement-loop** skill and let it run its
loop — it will reuse the prior run's harness, track the trend to a ledger and
an Okareo dashboard, and report before/after.
</content>
