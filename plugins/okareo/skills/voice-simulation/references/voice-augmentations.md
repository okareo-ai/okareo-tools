# Voice augmentations — when to use which

This file is loaded when the voice simulation needs to decide whether the
default "clean line, one speaker, no interruptions" run is good enough, or
whether the simulation should add realistic call-quality conditions on top.

Okareo exposes six augmentation knobs that drop into `run_simulation`'s
`augmentation` parameter. They model conditions a real phone or microphone
agent meets every day — and that a clean simulation never surfaces. The MCP
template `get_templates(["voice_augmentations"])` carries the exact field
schema and numeric ranges. This file carries the **judgment**: should you
augment at all, and if so, which one?

## The default is "off"

A voice simulation runs clean by default — no noise, no second voice, no
interruptions, no off-mic stretches. That is correct for proving the agent's
*conversation logic*. Augmentation is for proving its **resilience**:

- The clean run answers "does the agent understand this caller's goal and
  reach it?"
- An augmented run answers "does the agent still reach the goal when the
  caller's audio gets messy in the way real-world audio gets messy?"

Add augmentation when the user is past the basic-conversation milestone and
is asking whether the agent holds up in production-like conditions. Skip it
on a first scoping run, or when the failure mode under investigation is
clearly a *logic* failure (goal not understood, wrong tool called) rather
than an *audio* failure (caller cut off, asked the question twice, talked
over the agent).

## The composition rule (memorize this)

At most **one non-noise strategy** may be active per run, optionally
combined with **noise**. The MCP rejects any other combination with an
error before the run starts. The five non-noise strategies are
mutually-exclusive design choices about what the *caller* is doing; `noise`
is an additive layer about what's happening *around* them.

```text
OK:   {}                                   no augmentation
OK:   {"barge_in": {...}}                  caller interrupts
OK:   {"noise": {...}}                     noise only
OK:   {"barge_in": {...}, "noise": {...}}  caller interrupts in a noisy room
REJECT: {"cap": {...}, "barge_in": {...}}  two non-noise — pick one
```

Augmentations only apply to **voice Targets**. The MCP rejects them pre-network
on a `generation` or `custom_endpoint` Target. If the user asks for an
augmented run on a text agent, point them at the clean `agent-simulation`
flow instead.

## Choosing a strategy — match the failure mode

Pick the augmentation that probes the failure the user is worried about.
Each strategy is a question about how the agent handles one specific kind
of real-world messiness.

### `cap` — Concurrent Ask

> *Does the agent handle a caller who stacks a follow-up before the first
> answer finishes?*

Use when the user is worried about callers who don't wait politely — common
in drive-throughs, urgent service lines, anyone in a hurry. The simulator
fires a second question with a configurable probability and pause. A
well-built agent should either finish the first answer cleanly before
addressing the second, or gracefully merge them.

### `directed_speech` — Off-mic speech

> *Does the agent cope when the caller turns away from the mic mid-sentence?*

The simulator attenuates and reverbs a fraction of the caller's audio,
modeling a caller who turns away to talk to a child, look at something, or
fumble with the phone. Use when the agent will be deployed in real human
contexts — shopping, driving, homes with people in them — where
clean-studio audio is the exception, not the rule.

### `secondary_speaker` — Another voice in the room

> *Does the agent stay focused when a second human voice is audible
> alongside the caller?*

Adds a second speaker (a coworker, a family member, someone in line behind
the caller) at the configured probability. The agent must not respond to
the wrong voice or get confused about who's talking to it. Use this for
agents deployed in shared spaces — call centers, retail, homes — rather
than for solo-caller scenarios.

### `backchannel` — "mm-hmm" while the agent speaks

> *Does the agent get derailed by normal human "I'm listening" cues?*

The simulator drops short utterances ("mm-hmm", "yeah", "uh-huh") during
the agent's turn, with configurable timing offsets. This catches agents
that mistake a backchannel for the caller's real next turn and cut their
answer short. Use it when the agent is verbose enough that a normal
listening caller would naturally backchannel — long-form explainers,
walkthroughs, anything multi-sentence.

### `barge_in` — Mid-utterance interruption

> *Does the agent yield gracefully when the caller cuts in?*

The hardest of the five. The caller, with a configurable probability, fires
a prompt-defined interruption while the agent is mid-sentence. The agent
must stop, listen, and respond — not steamroll through to the end of its
planned utterance. Use this for any agent that gives long answers; the
worst version of "the bot wouldn't shut up" lives here.

### `noise` — Ambient background (composable add-on)

> *Does the agent's transcription hold up when the line isn't quiet?*

Layers cafeteria, classroom, office_babble, or traffic noise at a chosen
SNR onto the call. Less about agent logic and more about whether the upstream
voice stack (STT, VAD) breaks down on a noisy line. Compose it with any
non-noise strategy to stack two failure modes (e.g. barge-in over cafeteria
noise — the drive-through during lunch rush).

The set of profile names (`cafeteria`, `classroom`, `office_babble`,
`traffic`) is server-controlled; if the user names one the server doesn't
know, the run will fail with the current valid list. Don't memorize the
list — pass through what the user says and surface the error if it doesn't
take.

## Companion `simulation_params` knobs

These are tuning knobs on `run_simulation` that often matter alongside
augmentation. They are independent — set them whether or not augmentation
is active.

- **`turn_transition_time`** (ms) — how long the simulator pauses between
  the end of one turn and the start of the next. Increase it for agents
  with heavy STT latency, where a quick caller would talk over the agent's
  "let me check" filler.
- **`silence_timeout_ms`** (ms) — how long the simulator allows silence
  before advancing. Long silences happen during tool calls, lookups, hold
  times — give the agent room without letting it stall.
- **`checks_at_every_turn`** (bool) — evaluate checks per turn instead of
  only at end-of-call. Useful for catching mid-call regressions (the agent
  said the right thing at turn 4 but the wrong thing at turn 7).
- **`stop_check`** (`{check_name, stop_on}`) — halt the call as soon as
  the named check returns the configured value. Useful for "stop if the
  agent leaks PII" — failure short-circuits the run rather than running
  to the configured turn cap.

## What to put in the report

When an augmentation is active, lead the report with it so the user knows
what the success rate is conditional on:

```
## Voice simulation: <agent>
Augmentation: barge_in (p=0.2) + noise (cafeteria, 10 dB SNR)
Callers: <count> across <N> persona types
Outcome: <success rate> — <ready to ship under these conditions? y/n>
```

A success rate without the augmentation conditions named is misleading.
"95% success" under barge-in is a different claim than "95% success" on a
clean line.

## Common mistakes

- Trying to combine two non-noise strategies. Pick one per run; if the
  user wants both, run two simulations and compare.
- Setting augmentation on a `generation` or `custom_endpoint` target —
  the MCP rejects it pre-network. Point the user at `agent-simulation`.
- Treating augmentation as the default for first runs. The clean run
  proves the logic; augmentation proves the resilience. Do the clean run
  first, then add the failure mode the user is worried about.
- Reading a "95% under barge-in" number as comparable to "95% clean".
  They are not the same claim.
- Skipping `checks_at_every_turn` on long calls — without it, an agent
  that says the right thing at turn 4 and the wrong thing at turn 12
  may still pass the end-of-call check.
