# Configuring a voice target

This file is loaded when the voice simulation reaches target registration.
It covers the kinds of voice target and how to configure each.

A voice target is Okareo's handle on the voice agent under test. Its *kind*
says how Okareo reaches the agent. Pick the kind that matches how the agent
is actually reached.

## Which kind

| Kind | Use it when | What it needs |
| --- | --- | --- |
| `phone` | The agent answers a phone number and the user has no reason to dial from their own carrier account. **Start here.** | The number to call. Okareo supplies the caller number and bears the telephony cost |
| `twilio` | Calls must come from the user's own Twilio account | The number to call and the number to call from; the account's credentials |
| `telnyx` | Calls must come from the user's own Telnyx account | The same pair of numbers; the account's credentials |
| `vonage` | Calls must come from the user's own Vonage account | The same pair of numbers; the application's credentials |
| `sip` | The agent is reached at a SIP address rather than a phone number | The SIP address; a username and password if the endpoint requires them |
| `livekit` | The agent joins a LiveKit room | The LiveKit URL, the room name, and the API key and secret. All four, always |

The kind is what the user chooses. Which carrier actually serves a `phone`
call is Okareo's business and can change; do not reason about it.

There is no "custom" voice kind. If the agent is a custom HTTP service with
no phone number, SIP address or room, it is a text `custom_endpoint`
target — that belongs to `agent-simulation`.

## What every kind accepts

- **Max parallel requests** — how many calls may run at once. Optional;
  start at 1 for a first run and raise it once the simulation is trusted.
  Each parallel call on a dialed kind is a billed line.

## Credentials

- `phone` takes none.
- On the user's-own-account kinds the **caller number is required** but the
  keys and secrets are optional when the target is created. Two ways to
  supply them: pass them in the call, or create the target with the numbers
  only and have the user add the secret in the Okareo web app. Prefer the
  second: the secret never enters this conversation. The reply to a save
  says whether credentials are stored, but "stored" can mean only part of
  the set (an account id without its token). The pre-flight check is what
  says whether a target can actually dial; trust that, and tell the user
  exactly which value it names as missing.
- A target that has some but not all of what its carrier needs cannot dial.
  `run_simulation` reports that before a run starts, naming what is
  missing.
- `livekit` is the exception: it needs all four values up front.

Every credential is masked when a target is read back. Numbers, addresses
and identifiers stay readable.

## Changing or copying a voice target

Saving a target that already exists is an **update**: every setting left
out keeps its value, and so do the target's tags and stored credentials.
Change one thing by sending that one thing: the target's name, that it is
a voice target, and the one setting. The kind does not need restating; it
is read from what is stored.

The reply to an update can look like a creation — it may say created and
carry a new id. That is a new *version* of the same target, not a second
target. Confirm with `get_target`, which shows the version number and the
changed setting.

- **A masked value means "keep what is stored".** A target read with
  `get_target` can be saved back as read; the masks restore the stored
  secrets. You never need to hold a secret to change something else.
- **Two things cannot change:** whether the target is a voice target, and
  its kind. A save asking for a different kind is refused, naming both. To
  move an agent from `phone` to the user's own carrier, make a new target.
- **A setting that belongs to another kind is refused**, not dropped, and
  the refusal names the kind it belongs to.
- **A copy is a new target**, so it starts with no stored credentials. Read
  the original for its shape, give the copy a new name, and have the user
  supply any secret again (or add it in the web app).
- **The destination number must come from the user.** Never carry a phone
  number across by inference — even if it is visible on the original,
  confirm it before saving a copy.

## Checking a target without dialing

`run_simulation` has a report-only mode (its pre-flight option): it checks
that the scenario has every field the target and driver refer to, and that
a carrier target has what it needs to dial, then stops without starting
anything. Use it to answer "is this ready?" before a billed call.

"Compatible" from that check means the pieces fit. It does not mean the
run is well designed: it does not look for a completion check, a turn cap,
a caller persona or a voice, and it cannot tell whether the agent answers.
Say what it did and did not cover.

## Keypad tones

On `phone` and `telnyx` targets, how keypad presses reach the agent can be
chosen: sent beside the audio (the default) or as tones in the audio.
Leave the default unless the agent's phone menu does not register key
presses; then try the other.

## Common mistakes

- Treating a custom HTTP agent as a voice target. With no phone number, SIP
  address or room, it is a text `custom_endpoint` target.
- Reaching for the user's-own-account kinds when `phone` would do. They
  need a caller number and credentials; `phone` needs only the number to
  call.
- Calling a phone number the user did not explicitly provide.
- Setting max parallel requests high on a first run — start at 1.
- Asking the user to paste a carrier secret into the conversation when it
  could be added in the web app.
- Re-entering every setting to change one. Send only what changes.
- Picking a caller voice whose language does not match the agent's. Match
  the language when picking voices, or the call is unrealistic from turn
  one.
