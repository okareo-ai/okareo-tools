# What to monitor on live voice sessions

This file is loaded when monitoring is watching a voice agent's production
calls. The monitoring loop is unchanged; what differs is which signals are
worth a check on a *spoken* session.

## Outcome signals — did the call work

These are the signals that matter most. A voice call exists to accomplish
something; monitor whether it did.

- **Task completion** — did the call reach the caller's goal (booking made,
  issue resolved, correctly routed)? The core signal of any voice agent.
- **Containment** — did the agent handle the call, or did it bail to a human
  or dead-end? A rising escalation rate is a quality signal.
- **Policy adherence** — did the agent stay in scope and on policy across
  the call? Spoken agents go off-script in ways a text agent does not.

## Conversation-quality signals

- **Turn count to resolution** — calls drifting longer is an early sign of
  an agent that has gotten worse at understanding callers.
- **Stalls and dead air** — the agent going silent, or looping the same
  prompt. A specific, recognizable voice failure.
- **Interruptions and talk-over** — the agent and caller stepping on each
  other, a sign of broken turn-taking.
- **Recovery** — when a word is misheard, does the agent confirm and
  recover, or does it act on the wrong value?

## Signals to read with care

Voice traffic carries noise that text traffic does not. Do not let it
masquerade as an agent regression:

- **Transcription quality** — a misheard word is the transcriber's error.
  Worsening transcription accuracy is worth its own signal, but it is not
  the agent getting worse — keep the two separate.
- **Latency** — response delay matters far more on a live call than in
  text, where a pause is awkward silence. Worth monitoring as its own
  signal.
- **Audio issues** — dropped audio, cut-offs. Infrastructure, not agent
  behavior — track it, but route it to a different owner.

## Baseline against comparable calls

Voice metrics swing with call type — a balance-check call and a complex
dispute call have different normal turn counts and completion rates.
Baseline within a call type where you can, so a shift in the *mix* of call
types does not read as a quality regression (see
[references/drift.md](references/drift.md)).
