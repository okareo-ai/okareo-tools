# Agentforce session traces

Okareo can pull every Agentforce session's trace from a Salesforce org and
turn it into datapoints: each turn, each router choice, each LLM call. This
is monitoring for an Agentforce agent. It also links a simulation of that
agent to the trace of what the agent did, without any setting on the Target.

It is a **pull** integration. Okareo signs in to the org on a schedule and
reads the traces from Data 360. There is no webhook to configure, and
`get_voice_webhook_url` refuses it.

## What the user must have first

- The org's **My Domain**, like `https://acme.my.salesforce.com`.
- A Salesforce **External Client App** with the client credentials flow
  enabled and a run-as user, and its **client ID** and **client secret**.
- Agentforce session tracing turned on in the org, so there is something to
  read.

Ask for the client ID and secret only when you are about to pass them, pass
them as secrets, and never repeat them back or write them into a report.

## The flow

1. **Test before saving.** Call `test_voice_integration` with the provider,
   the My Domain as metadata, and the two secrets. Nothing is stored. The
   reply says whether each check passed (settings, sign-in, traces readable)
   and lists the org's **agents** with their Agent IDs and how many traced
   sessions each had in the last 30 days.
2. **Read a failure before retrying.** Checks stop at the first failure and
   its detail says what to fix: a wrong client ID or secret, or the client
   credentials flow not enabled on the app. Fix that one thing and test
   again.
3. **Decide which agents to pull.** By default every agent in the org is
   pulled. To limit it, take Agent IDs from the test's agent list (up to
   20). An agent with zero recent sessions has nothing to show yet.
4. **Connect** with `connect_voice_integration` using the same values, plus
   the Agent IDs if you chose any. A project holds one active integration
   per My Domain; a second is refused with the reason — edit the first or
   turn it off.
5. **Confirm** with `test_voice_integration` on the saved integration, and
   again after rotating its secret or pointing it at another org.

## Reading what arrives

Sessions land a few minutes after they end, not instantly. Read them with
`find_datapoints`, open one row with `get_datapoint`, and see the steps
behind it with `get_trace`.

Each datapoint's user metadata has a key named "gen_ai.sf.datapoint" that
says what kind of step it is. Its value is one of:

| Value | What the row is | Use it for |
| --- | --- | --- |
| turn | One exchange between the customer and the agent | What was said, and whether it was right |
| router | The agent choosing a topic or route | Where the request was sent |
| llm_call | One call to the model | Cost and latency |

Filter `find_datapoints` on user metadata with that key and one value. The
other metadata on a row (the session id, the topic, the channel) uses the
same "gen_ai.sf." prefix; open a row to see what is there.

**Check that a metadata filter actually filtered.** A filter on a key that
no datapoint in the project carries is ignored, and every row comes back.
Look at the returned rows' metadata before reporting them as "the turns" or
"the gold-tier calls".

From there the monitoring loop is the usual one: checks on the turns, a
baseline, thresholds, interpretation.

## Changing it later

- `update_voice_integration` takes a partial change for an Agentforce
  integration: pass only the setting that changes. The My Domain and the
  rest are kept.
- To pull every agent again, clear the Agent ID list rather than listing
  them all.
- Polling can be slowed down or sped up. Three settings, all in seconds and
  all described on `update_voice_integration`: how often Okareo checks the
  org (the poll interval), how long it waits after a session ends before
  fetching it (the initial delay), and when it gives up on a session that
  never completes (the timeout). The defaults suit most orgs; change them
  when the user asks or for a stated reason.
- **Note the current value before changing a setting.** Read the
  integration first. Clearing a setting returns it to the platform default,
  not to what it was, so "put it back" means sending the old value.
- Turning an integration off stops the pulling without losing its settings.

## Pitfalls

- **Do not look for a trace setting on the Target.** There is none; the
  integration alone decides what is pulled.
- **The test lists every agent in the org, not only the ones being
  pulled.** Compare the list against the integration's Agent ID filter
  before telling the user which agents are covered.
- **A passing test is not traffic.** It proves the credentials can read
  traces. If nothing arrives, check that the agents actually had sessions
  and that the Agent ID list is not excluding them.
- **A phone simulation's trace is read the same way as a text or WebRTC
  one.** Use `find_datapoints` filtered to the run, or `get_trace` with the
  simulation's context token or the datapoint id of one of its rows. Do not
  tell a phone customer their trace cannot be reached. Traces land a few
  minutes after the call ends, so an empty result right after a run means
  wait and read again.
