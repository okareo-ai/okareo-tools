# Configuring a voice target

This file is loaded when the voice simulation reaches target registration.
It covers the three voice edge types and how to configure each.

A voice target is Okareo's handle on the voice agent under test. The *edge
type* says how Okareo reaches the agent and speaks with it. Pick the edge
type that matches how the agent actually runs.

## Which edge type

- **`twilio`** — the agent answers a **phone number**. Okareo places a real
  outbound PSTN call to that number. Use this for any agent reachable by
  phone, regardless of who hosts it (VAPI, LiveKit, Telnyx, Twilio, …) —
  Okareo only needs the number.
- **`openai`** — the agent is built on the **OpenAI Realtime** voice
  backend. Okareo speaks to it through that backend rather than over a
  phone line.
- **`deepgram`** — the agent is built on the **Deepgram** voice backend.

There is no "custom" voice edge type. If the agent is a custom HTTP service
with no voice backend and no phone number, it is a text `custom_endpoint`
target, not a voice target — that belongs to `agent-simulation`.

## Twilio targets (a dialed phone number)

Configure:

- **Destination phone number** — the number the agent answers on. Required.
  Use only a number the user has given you.
- **Max parallel requests** — how many calls Okareo may place at once
  (an integer of at least 1). Required. Keep it low for a first run; raise
  it once the simulation is trusted, mindful that each parallel call is a
  billed line.

A Twilio target places **real phone calls that cost money**. Confirm with
the user before any run. For a Twilio account the user controls directly,
the account SID, auth token, and caller (from) number can also be supplied;
treat all three as secrets and keep them out of transcripts and reports.

## OpenAI Realtime and Deepgram targets

For an `openai` or `deepgram` voice target, configure:

- **Model** — the voice model identifier the agent runs on.
- **Output voice** — the voice identifier the agent speaks with.
- **Instructions** — optional voice-interaction instructions that shape how
  the agent's side of the call behaves.

These targets do not place a phone call, but they still run real,
billed voice sessions against the provider — set a max-turn cap and confirm
before large runs just as you would for Twilio.

## Common mistakes

- Treating a custom HTTP agent as a voice target. With no phone number and
  no voice backend, it is a text `custom_endpoint` target.
- Calling a phone number the user did not explicitly provide.
- Omitting max parallel requests on a Twilio target, or setting it high on
  a first run — start at 1.
- Picking a caller voice whose language does not match the agent's. Match
  the language when picking voices, or the call is unrealistic from turn one.
