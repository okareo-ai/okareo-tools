# Verification codes, messages and extensions

Many voice agents step outside the call: "I've just texted you a code —
can you read it back?" A simulated caller has no phone to look at, so that
call stalls unless the caller is given an **inbox**. This file covers the
inbox, and the related case of an agent behind an extension.

## How the inbox works

1. The target is **armed** for an inbox. Each call then has an inbox for
   as long as the call lasts.
2. While the call is live, a message is **delivered** to that inbox.
3. The simulated caller is told about the message on its next turn and can
   act on it: read the code back, confirm an appointment time, follow a
   link's instruction.

The caller is not given the code in advance and there is no placeholder
for it. It learns the code only when the message arrives, which is the
behaviour being tested.

## Arming the target

Turn the inbox on when saving the target with `create_or_update_target`.
Then decide how a message will find the right call:

| Address a call by | Use when |
| --- | --- |
| The caller's phone number | One call at a time, or each call uses its own caller number |
| A reference of the user's own, set per scenario row (an account id, a booking id) | The agent's system knows the customer by that id. The most reliable choice when several calls run at once |
| The call's own token | A custom integration that already tracks it |

If the target uses a per-row reference, the scenario rows must carry that
field. The pre-flight check on `run_simulation` reports a row that lacks
it.

## Getting the message to the call

There are three ways, in order of how close they are to production:

- **The carrier delivers it.** The target can have the carrier deliver
  texts sent to the caller's number. What it takes depends on whose number
  the call comes from:
  - **Okareo-managed phone target:** the number is Okareo's. Nothing else
    to build.
  - **The user's own Twilio account:** the number is theirs, so its
    messaging webhook in the Twilio console must point at Okareo (the
    Twilio SMS webhook, `/v0/voice/twilio/sms` on the Okareo API address).
    Until it does, no text reaches the caller. Tell the user this before
    the first run, and check it first when a code does not arrive.
  - **The user's own Telnyx account, and every other kind:** not available;
    the save is refused and says so. Use the next option.
- **The user's system posts it.** Whatever sends the code (an SMS
  provider, an email service) is pointed at Okareo's inbox webhook, with an
  Okareo API key. This works on every voice kind and is the usual setup
  for email or in-app codes.
- **You deliver it by hand, for testing.** `send_inbox_message` hands a live
  call a message directly. Use it to prove the caller handles a code
  before the user has wired anything, or in a demo. It is a testing aid:
  it stands in for the agent's system, so a pass with it does not show
  that the real message would arrive.

**Timing a hand delivery.** You cannot watch a live call, so do not try to
time the message to the agent's words. Deliver it as soon as the call is
live — start the run, then send; if the tool says there is no live
conversation yet, wait a few seconds and send again with the same message
id — and rely on the caller's instructions above to hold the code until it
is asked for.

**Addressing a hand delivery.** On an Okareo-managed phone target the
caller's number is not something you can look up, so address by a per-row
reference: arm the target with one, put that field in the scenario row,
and send to its value.

`send_inbox_message` needs exactly one address (the caller number, the
per-row reference, or the call's token) and the message text. It only
works while the call is live: before the call starts or after it ends
there is no inbox, and the tool says so. Sending the same message id twice
delivers once.

## Writing the caller

Tell the persona what to do with a message **whenever** it arrives, in
plain words:

- "You may receive a text with a verification code at any point in the
  call, including before the agent mentions one. Once you have a code,
  keep it: whenever the agent asks for the code, read it back digit by
  digit."
- "Only if no code has arrived at all, say so and ask them to send it
  again."

**Decide what the test is proving, because it changes the caller.**

- *The agent's real code step* (it sends a code and asks for it). The
  caller must do whatever makes the agent start that step. Find out from
  the user what triggers it — a particular request, a known account — and
  put it in the scenario row. A caller with a vague reason for calling may
  never be asked for a code, and the run then proves only delivery.
- *Only that a simulated caller can receive a code and say it* (the user's
  own messaging is not connected yet, or the agent has no code step). The
  agent may never ask. Tell the caller to bring it up: "Once you have
  received a code, tell the agent you have a verification code and read it
  out digit by digit, even if you have not been asked." Add what to do
  next, or the caller may improvise badly once the agent declines the
  code: "After you have read it out, thank the agent and end the call."
  Say in the report that this is what was tested. Expect the completion
  check to fail on a run like this; it is not evidence against delivery.

Do not write "wait for the code after the agent says it was sent". A
message can arrive before the agent mentions it — always, when you deliver
it by hand — and a caller told to wait will then ignore the code it
already has and claim nothing arrived.

Give the caller a reason to stay on the line: a persona that hangs up at
the first pause never sees the code. If the agent's system takes several
seconds to send, the call's silence allowance may need raising; that is
the user's call, so ask rather than change it.

## Reading the result

`get_conversation_transcript` lists each message the call received — who it
was from, what it said, when it was read — and places it in the
conversation: which caller turn read it, how long the caller waited, and
what the caller said next. Use that to judge:

- Did the caller get the code at all? (If not, it is a delivery problem,
  not an agent failure.)
- Did the agent accept the right code and refuse a wrong one?
- How long did the caller wait in silence?

A completion check reads the conversation, not the inbox. Its explanation
may say the caller "never received" a code that the transcript shows
arrived. Judge delivery from the received messages and the read-back from
what the caller said; do not quote the check's reasoning on delivery.

## An agent behind an extension

When the agent is reached through a main number and then an extension, the
target can dial digits once the line answers. Pauses can be written into
the digits so the menu has time to speak. The digits may come from a
scenario field, so each row can reach a different extension; a row
missing that field is refused before the run starts. Available on
Okareo-managed phone targets and the user's own Twilio or Telnyx account.

To remove stored digits or a stored inbox reference later, save the target
with that setting empty. Leaving it out keeps it.

## Pitfalls

- **Do not write the code into the persona or the scenario's caller
  instructions.** The test is whether the caller can use a code it
  receives. If the row needs to record the expected code for a check, put
  it in the row's expected result, and have the driver refer to named
  fields of the row rather than the whole input, so it never sees it.
- **A call where the caller got the code but did not use it has not proven
  the read-back.** Report it as that, with the transcript, rather than as
  a pass or as the agent's failure.
- **A hand-delivered message proves the caller, not the pipeline.** Say
  which delivery was used when reporting.
- **Address by the per-row reference when calls run in parallel.** Two live
  calls from the same caller number cannot be told apart by number, and
  the delivery is refused as ambiguous.
- **These are real calls.** Confirm with the user before running, as for
  any phone target.
