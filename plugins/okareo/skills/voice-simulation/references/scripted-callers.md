# Scripted callers

A caller normally plays a persona. A **scripted** caller plays a fixed list
of steps, with no model choosing the words. Use it when a call must go the
same way every time.

## What it is for

- **Phone menus (IVR).** "Press 1 for billing, then enter your account
  number" is a fixed path. A script walks it reliably; a persona may wander.
- **Reproducing a reported call.** Replay what the caller said, in order.
- **Before-and-after comparison.** The same caller on two versions of the
  agent, so any difference is the agent's.

Use a persona when you want to find out how the agent copes with a caller
you did not predict.

## The four kinds of step

| Step | What the caller does |
| --- | --- |
| Say | Speaks the words exactly as written |
| Press keys | Presses keypad digits and says nothing |
| Stay silent | Says nothing for a turn and listens |
| End the call | Says the closing words and hangs up. Always last, with a short reason |

Pass the steps to `create_or_update_driver` together with a voice, in place
of a prompt. For the exact shape of each kind of step, fetch the
`scripted_driver` template with `get_templates`. Steps can use the scenario row's fields, and a whole script can
come from a row so each row plays its own.

## Getting an IVR right

- **Listen before pressing.** Put a silent step in front of a key press so
  the menu finishes speaking before the digits go in. A menu with several
  prompts in a row may need one silent step per prompt.
- **Keys need a phone line.** Key presses work on phone and SIP targets, not
  on a realtime-audio target. A run that cannot press keys is refused
  before any call is placed.
- **Leave headroom in the turn cap.** If the agent talks over a spoken line,
  that line is said again on the caller's next turn, and the repeated turn
  counts. For a five-step script, a cap of eight to ten is a reasonable
  start.

## With augmentations

A scripted caller has no model, so anything that would need one to invent
words is refused before the run starts:

- Background noise, backchannel and dropout work as usual.
- An interruption or a background remark works only when you give it the
  exact words to say.
- Do not place an augmentation on the turn of a silent, key-press or
  closing step.

## Reading the call

- Spoken steps appear as the caller's lines, word for word.
- A key press appears as the caller sending digits, not as speech.
- A silent step leaves no line at all. `get_conversation_transcript` lists
  the turn it happened on as a dropped caller turn, which is how to tell a
  deliberate silence from a turn that never happened.
- The reason the call ended is reported too. For a script that finished, it
  is the closing step's reason.

## Pitfalls

- **A script does not react.** If the agent asks something unexpected, the
  caller says the next line regardless. Read the transcript before trusting
  a pass.
- **A placed call still costs money.** A scripted run on a phone target
  dials for real; confirm with the user first, as for any voice run.
