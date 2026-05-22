# Behavioral drift vs data drift

This file is loaded when monitoring needs to explain *why* a metric moved.
The single most useful distinction is whether the **model** changed or its
**inputs** changed — behavioral drift versus data drift. They look the same
on a dashboard and call for opposite responses.

## The two kinds of drift

### Behavioral drift — the model changed

The same kind of request now gets a worse (or just different) response.
Causes: a model or prompt deploy, a dependency or tool change, a provider
silently updating a hosted model, a retrieval index going stale.

This is a real regression. It is the thing monitoring exists to catch.

### Data drift — the inputs changed

The model is doing exactly what it always did, but the *traffic* shifted: a
new user segment, a marketing campaign, a new language, a seasonal pattern,
a new product surface sending different questions.

The metric moved, but the model did not get worse. Responding as if it were
a regression — rolling back a deploy, paging an engineer — fixes nothing.

## How to tell them apart

A moved metric alone cannot distinguish them. Look further:

- **Did the input mix change?** Compare the distribution of inputs in the
  current window against the baseline window — topic, length, language,
  user segment. A shifted input mix points at data drift.
- **Did anything ship?** Line the metric's move up against deploy history. A
  move that starts at a deploy points at behavioral drift.
- **Hold the inputs constant.** Re-run a fixed scenario set against the
  current model. If the *scenario set* score dropped, the model changed —
  behavioral drift. If the scenario set still passes, production traffic
  changed — data drift. This is the decisive test, because the scenario set
  is the one input that did not move.

## Why the response differs

- **Behavioral drift** — treat as a regression. Characterize the failure,
  hand off to `scenario-from-traces` to capture it, fix, and re-run.
- **Data drift** — the model may need to *handle* the new traffic, but there
  is nothing to roll back. The right response is often to extend the
  scenario set to cover the new input population, then evaluate against it.
  Sometimes the right response is just to update the baseline.

## Slow drift hides from simple thresholds

Either kind of drift can arrive gradually — a little worse each day, no
single day tripping a drop threshold. Pair a sharp-drop check with a slow
trend comparison (current window against one further back) so a gradual
slide is caught before it accumulates into a visible failure.
