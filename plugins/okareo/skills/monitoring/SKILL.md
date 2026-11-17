---
name: monitoring
description: >-
  Set up and interpret Okareo production monitoring — checks on live traffic, quality baselines,
  and alerts on regressions or drift. Use for "monitor my agent in production", "watch my voice
  agent's live calls", "alert me when quality drops", "why did responses get worse this week". For
  pre-release testing use agent-simulation or voice-simulation.

---

# Okareo: Monitoring

This skill puts continuous checks on live traffic so quality regressions are
caught in production rather than discovered by users.

It is the production counterpart to `agent-simulation`. When
monitoring flags a real problem, hand off to `scenario-from-traces`
to turn the flagged conversations into a regression test.

## When this skill applies

Use it when the subject is *live* traffic — putting checks on a production
stream, reading the resulting metrics, investigating drift, or tuning the
thresholds that decide what counts as a regression. If the user wants
a one-time judgement on a fixed test set, that is evaluation, not
monitoring — run checks over that set directly instead.

## How the pieces fit

Okareo's MCP server provides the tools; this skill provides the method.
Never call the Okareo HTTP API directly and never fabricate monitoring
metrics — if a needed tool is unavailable, say so and stop.

<!--
  TOOL NAMES: keep this table in exact sync with the Okareo MCP server.
  Rename on both sides in the same release.
-->

| Step                 | MCP tool                       | Purpose                                          |
| -------------------- | ------------------------------ | ------------------------------------------------ |
| Ingest live traffic  | `ingest_conversations`         | Bring production conversations into Okareo       |
| Define the signals   | `create_or_update_check`       | The quality checks evaluated on that traffic     |
| Query metrics        | `query_analytics`              | Read metric values and trends over the traffic   |
| Build a watch view   | `save_dashboard`               | A persistent dashboard of the signals watched    |
| Read a conversation  | `get_conversation_transcript`  | Inspect an individual flagged conversation       |
| Check a pull source  | `test_voice_integration`       | Confirm Okareo can reach an Agentforce org before and after connecting |

Okareo has no single "monitor" object. Monitoring is **checks evaluated on
ingested production traffic, surfaced through a dashboard and read with
analytics queries**. Discover existing pieces with `list_checks`,
`generate_check`, `get_check`, `list_dashboards`, and `get_dashboard`.
Continuous paging is configured in the Okareo product UI — through these
tools, "checking for a regression" means re-running `query_analytics` and
applying the threshold judgement below.

For a **voice agent**, the live stream is wired in differently — see
*Monitoring voice traffic* below. The loop after ingestion is the same.

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

Monitoring needs a sense of "normal" before it can flag "abnormal". With
recent traffic already ingested via `ingest_conversations`, query it with
`query_analytics` and establish baseline values for each signal. Reading a
metric without a baseline produces either constant false alarms or silence.

### 3. Define checks and thresholds

Define the quality signals as checks with `create_or_update_check` (reuse
existing ones found via `list_checks`), and assemble them into a dashboard
with `save_dashboard` so the watched signals live in one place. See
[references/alert-design.md](references/alert-design.md) for how to set
thresholds that catch real regressions without drowning the team in false
positives — the thresholds are judgement you apply when reading
`query_analytics` results, not a field on a tool call.

**Send context with the traffic, and let checks read it.** Each ingested
conversation can carry key/value metadata (a customer tier, a campaign, a
queue) and the name of the provider or dialer that handled the call. The
metadata is shown on the datapoint, can be filtered on, and can be named in
a check's prompt — the whole set, or one key — so a check can judge the
agent against what was true for that caller ("was a gold-tier customer
offered the callback they are entitled to?"). The exact placeholder for
the set and for one key is given in the description of
`create_or_update_check`; copy it from there. Decide the keys before
ingesting: a check can only read what was sent, and a call that arrives
without the key gives the check nothing to judge, so say in the check what
a missing value means. A check prompt that names a variable the platform
does not know is refused when it is saved, with the list of names it does
accept.

Two limits to state rather than hide: saving a check does not attach it to
incoming traffic (that is set up on a monitor in the Okareo app), and a
filter on a metadata key that no datapoint in the project carries is
ignored, returning every row. Confirm one real call shows the key before
relying on either.

### 4. Interpret results, do not just watch the number

- Lead with **status**: are all signals within their normal range?
- For any signal that moved, distinguish a **real regression** from
  **expected variation** or a **traffic-mix shift** — a metric can move
  because the model got worse, or because the kind of requests changed.
- Look at **trend, not just the latest point** — a slow drift over a week is
  as important as a sudden drop, and easier to miss.
- When a signal crosses its threshold, pull the **conversations behind it**
  with `get_conversation_transcript` and characterize what is actually
  failing.

When a metric has moved and you need to say *why*, the distinction that
matters is behavioral drift versus data drift — the model changed, or its
inputs did. See [references/drift.md](references/drift.md) for how to tell
them apart and why the response differs.

### 5. Triage and hand off

When a monitor flags a genuine regression:

- Characterize the failure from the flagged datapoints.
- Hand off to `scenario-from-traces` to turn those datapoints into a
  scenario set, then re-run that set to confirm a fix and guard against
  recurrence.
- Monitoring catches the regression; a durable scenario set prevents it from
  coming back silently.

## Monitoring voice traffic

A voice agent is monitored with the same loop — baseline, checks,
thresholds, interpret — but its live stream reaches Okareo through a
**voice integration** rather than `ingest_conversations`.

Which steps apply depends on the provider. There are three shapes — this
set is distinct from the voice *simulation* target kinds:

| Provider                     | Stored integration? | How its traffic arrives                         |
| ---------------------------- | ------------------- | ----------------------------------------------- |
| `twilio`, `retell`, `livekit` | yes                 | The provider posts to a webhook that carries the integration's public id |
| `vapi`, `elevenlabs`          | no                  | The provider posts to a webhook whose address names the project (`?project_id=`), authenticated with an Okareo API key |
| `agentforce`                  | yes                 | Okareo pulls: it signs in to the Salesforce org and reads session traces itself. No webhook |

1. **Twilio, Retell, LiveKit** — connect with `connect_voice_integration`
   (provider plus that provider's secrets; leave the auth type out and
   Okareo picks it). The reply carries an id and a public id.
2. Get the inbound endpoint with `get_voice_webhook_url` and have the user
   paste it into the provider's console. From then on the provider posts
   completed calls to Okareo. **Vapi and ElevenLabs start here**: they need
   no integration, and `connect_voice_integration` refuses them with this
   pointer. The rest of their setup happens in the provider's own console
   (a credential holding an Okareo API key, and which call events to send);
   fetch those steps with `get_docs` rather than reciting them from memory,
   and tell the user which Okareo environment the returned URL belongs to.
   **Their URL is per project.** It ends in `?project_id=...`, and that is
   what files the calls under the right project. Give the user the URL
   exactly as returned, query string included, and get a fresh one for each
   project. Without the project an ElevenLabs post is refused, and Vapi
   calls land in the Global project instead of the one the user meant.
3. **Agentforce** has no webhook and its own flow — test first, then
   connect. See [references/agentforce.md](references/agentforce.md).
4. Manage integrations with `list_voice_integrations`, `get_voice_integration`,
   `update_voice_integration` (settings, or turn one off and on without
   deleting it), `rotate_voice_integration_secret`, and
   `delete_voice_integration`. Treat integration secrets as secrets — never
   echo them into a report, and never put one in an integration's metadata,
   which is readable.

Once calls are flowing, the loop is unchanged: define checks, baseline,
threshold, interpret. What differs is *which signals matter on a spoken
session* — see [references/voice-signals.md](references/voice-signals.md).

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
  from a `query_analytics` (or `get_dashboard`) call.
- Always interpret a moved metric against a baseline; a number with no
  baseline is not evidence of anything.
- Before calling a change a regression, rule out a traffic-mix shift — the
  inputs may have changed, not the model.
- Resist monitoring every possible signal. A few signals tied to real
  consequences beats a dashboard nobody reads.
