---
name: okareo-monitoring
description: >-
  Set up and interpret production monitoring of an LLM app or agent with
  Okareo — checks running on live traffic, quality baselines, and alerts on
  regressions or drift. Use this skill whenever the user wants to monitor
  production, watch live quality, catch regressions in the wild, set up
  alerts, or investigate a drift in behavior — including requests like
  "monitor my agent in production", "alert me when quality drops", "why did
  responses get worse this week", or "track our model in the wild". Use it
  even when the user does not say "Okareo" but is clearly trying to observe
  a live LLM system.
---

# Okareo: Monitoring

This skill puts continuous checks on live traffic so quality regressions are
caught in production rather than discovered by users.

It is the production counterpart to `okareo-agent-simulation`. When a
monitor flags a real problem, hand off to `okareo-scenario-from-traces` to
turn the flagged datapoints into a regression test.

## When this skill applies

Use it when the subject is *live* traffic — configuring monitors, reading
monitoring results, investigating drift, or tuning alerts. If the user wants
a one-time judgement on a fixed test set, that is evaluation — use
`okareo-evaluation`.

## How the pieces fit

Okareo's MCP server provides the tools; this skill provides the method.
Never call the Okareo HTTP API directly and never fabricate monitoring
metrics — if a needed tool is unavailable, say so and stop.

<!--
  TOOL NAMES: keep this table in exact sync with the Okareo MCP server.
  Rename on both sides in the same release.
-->

| Step               | MCP tool                    | Purpose                                |
| ------------------ | --------------------------- | -------------------------------------- |
| Inspect live data  | `okareo_list_datapoints`    | Sample logged production traffic       |
| Configure a monitor| `okareo_create_monitor`     | Attach checks + thresholds to a stream |
| Read results       | `okareo_get_monitor_results`| Pull metrics, trends, and triggered alerts|

## The monitoring loop

Follow these steps in order — baseline before thresholds, thresholds before
alerting.

### 1. Scope what to monitor

Establish three things:

- **The stream** — which production endpoint, model, or agent is being
  watched, and roughly how much traffic it sees. Volume affects how fast a
  monitor can detect a change.
- **The quality signals that matter** — the handful of properties whose
  regression would actually hurt: groundedness, format validity, refusal
  rate, latency, cost. Monitor those, not everything.
- **What action an alert triggers** — who gets paged, and what they do.
  A monitor whose alert leads to no action is noise.

### 2. Establish a baseline

A monitor needs a sense of "normal" before it can flag "abnormal". Sample
recent traffic with `okareo_list_datapoints` and establish baseline values
for each signal. Alerting without a baseline produces either constant false
alarms or silence.

### 3. Configure checks and thresholds

Create the monitor with `okareo_create_monitor`, attaching the checks for
your chosen signals. See [references/alert-design.md](references/alert-design.md)
for how to set thresholds that catch real regressions without drowning the
team in false positives.

### 4. Interpret results, do not just watch the number

- Lead with **status**: are all signals within their normal range?
- For any signal that moved, distinguish a **real regression** from
  **expected variation** or a **traffic-mix shift** — a metric can move
  because the model got worse, or because the kind of requests changed.
- Look at **trend, not just the latest point** — a slow drift over a week is
  as important as a sudden drop, and easier to miss.
- For a triggered alert, pull the **datapoints behind it** and characterize
  what is actually failing.

### 5. Triage and hand off

When a monitor flags a genuine regression:

- Characterize the failure from the flagged datapoints.
- Hand off to `okareo-scenario-from-traces` to turn those datapoints into a
  scenario set, then to `okareo-evaluation` to confirm a fix and guard
  against recurrence.
- Monitoring catches the regression; the evaluation skills prevent it from
  coming back silently.

## Reporting format

```
## Monitor: <stream under watch>
Status: <all normal / N signals flagged>

### Signals
- <signal> — <current vs baseline> — <real regression? variation? mix shift?>
- ...

### Triggered alerts
- <alert> — <what the flagged datapoints show> — <recommended action>

### Next step
<turn flagged datapoints into a scenario set, or "no action needed">
```

## Guardrails

- Never fabricate monitoring metrics or alert history — every figure comes
  from an `okareo_get_monitor_results` call.
- Always interpret a moved metric against a baseline; a number with no
  baseline is not evidence of anything.
- Before calling a change a regression, rule out a traffic-mix shift — the
  inputs may have changed, not the model.
- Resist monitoring every possible signal. A few signals tied to real
  consequences beats a dashboard nobody reads.
