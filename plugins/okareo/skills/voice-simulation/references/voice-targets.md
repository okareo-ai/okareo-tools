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

## Reusing or cloning a voice target

There is no clone-target tool. Duplicating a voice target — for a variant,
or to tweak one setting — means reading the original with `get_target` and
calling `create_or_update_target` again. The shape now round-trips cleanly
(the response keys mirror the create kwargs), but the *values* of any
sensitive fields are masked and must be re-supplied:

- **`create_or_update_target` is a full replace.** Any field you do not
  restate is dropped, whether you reuse the name or pick a new one. Same
  semantics as the text targets.
- **Sensitive values come back redacted.** Fields the backend treats as
  secret — Twilio `account_sid` / `auth_token`, anything else listed under
  the target's `sensitive_fields` — appear in `get_target` output as the
  literal string `"***REDACTED***"`. The *paths* are visible (so you can
  see which fields need values), the *values* are not. `create_or_update_target`
  rejects any payload still containing the sentinel before reaching the
  backend, so you cannot accidentally ship a redacted-as-string credential.
- **`max_parallel_requests` is a top-level field.** It is required for
  Twilio targets (an integer ≥ 1) and `get_target` now returns it at the
  top level, so a field-by-field copy picks it up. Still restate it
  explicitly — don't assume the original value is the right one for the
  clone.
- **The destination number must come from the user.** Never carry a phone
  number across by inference — even if it is visible on the original
  target, confirm it explicitly before saving the new one.

Walk this checklist before calling `create_or_update_target` on a clone:

For **Twilio**:

- [ ] `to_phone_number` — confirm with the user.
- [ ] `max_parallel_requests` — restate explicitly (start at 1 for a first run).
- [ ] `account_sid`, `auth_token`, `from_phone_number` (if the original used
      a user-owned Twilio account) — these come back as `"***REDACTED***"`;
      **re-supply real values from the user**. Submitting the sentinel
      verbatim is rejected by the MCP before any backend call.

For **OpenAI Realtime** or **Deepgram**:

- [ ] `edge_type` — `openai` or `deepgram`.
- [ ] `model`, `output_voice`, `instructions` — restate from the original.

Treat reuse as a *deliberate build*, not a copy: read the original to see
its shape (now mirroring create kwargs), ask the user for anything that came
back as `"***REDACTED***"`, then call `create_or_update_target` with the
substituted envelope.

## Common mistakes

- Treating a custom HTTP agent as a voice target. With no phone number and
  no voice backend, it is a text `custom_endpoint` target.
- Calling a phone number the user did not explicitly provide.
- Omitting max parallel requests on a Twilio target, or setting it high on
  a first run — start at 1.
- Picking a caller voice whose language does not match the agent's. Match
  the language when picking voices, or the call is unrealistic from turn one.
- Cloning a Twilio target by passing the `get_target` output back to
  `create_or_update_target` without substituting the `"***REDACTED***"`
  values. The MCP rejects the call before the backend sees it, naming each
  field that still carries the sentinel — fix those paths, don't try to
  bypass the check.
