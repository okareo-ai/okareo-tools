# Designing alert thresholds

This file is loaded only when the monitoring setup reaches threshold
configuration. It covers how to set thresholds that catch real regressions
without burying the team in false alarms.

## The two failure modes of alerting

Every threshold trades off two bad outcomes:

- **Too sensitive** — the monitor fires constantly on normal variation. The
  team learns to ignore it, and a real regression slips through unnoticed.
- **Too loose** — the monitor only fires on catastrophic failure, by which
  point users have already been affected for days.

A good threshold sits between these: it fires on a change large enough to
act on, and rarely otherwise.

## Set thresholds relative to the baseline

Absolute thresholds ("alert if groundedness below 0.8") are brittle —
they ignore what normal looks like for this system. Prefer thresholds
defined relative to the established baseline:

- A **drop of more than X** from the baseline value.
- A value outside the **normal range** observed during the baseline window.

This way the same monitor config works even as the system's normal level
shifts over time.

## Account for noise

A single bad datapoint is not a regression. To avoid firing on noise:

- Evaluate over a **window** of recent traffic, not one request.
- Require the signal to stay out of range for a **sustained period** before
  alerting, not just a single sample.
- Size the window to the stream's volume — a low-traffic endpoint needs a
  longer window to gather enough signal.

## Watch for drift, not just drops

A sudden drop is easy to catch. A slow drift — quality eroding a little each
day — is more dangerous because no single day trips a simple threshold. Pair
a sharp-drop alert with a slower trend check that compares the current
window against one further back.

## Tier the alerts

Not every regression deserves a page at 3am. Tier them:

- **Critical** — large, sudden quality or safety regression; page someone.
- **Warning** — smaller or slower degradation; surface in a daily summary.

Tiering keeps the critical channel meaningful, which is what keeps the team
responding to it.

## Tie every alert to an action

Before adding an alert, answer: when this fires, who does what? An alert
with no owner and no response is noise that trains the team to ignore the
whole monitor. If there is no action, do not add the alert.
