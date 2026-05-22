# How a voice simulation works

This file is loaded when the quickstart reaches the build steps. It explains
the model behind a voice simulation so the walkthrough can teach it, not just
perform it.

## The four pieces

A voice simulation is four objects run together. Onboarding is mostly about
making these four concrete for the user:

- **Target** — the agent under test. For a voice agent it is a phone number
  Okareo dials. The target does not contain the agent's logic; it is just
  Okareo's handle on "the thing that answers this number". Any provider
  (VAPI, LiveKit, Twilio, Telnyx, …) works, because Okareo only places an
  outbound call to the number.
- **Driver** — the simulated caller. A persona prompt that decides what the
  caller wants and how they behave, plus a voice so it can actually speak on
  the phone. The driver is the *user*, never the agent.
- **Scenario** — the test cases. Each row is one call: an `input` (the
  caller's situation and goal) and a `result` (what a successful call
  achieves). The quickstart uses a single row.
- **Checks** — how each call is scored. A check reads the finished call and
  returns a verdict. Without checks a simulation produces a transcript and
  no judgement.

## How a call actually runs

When the simulation runs, Okareo places an outbound phone call from the
driver to the target number. The driver speaks first or the agent does
(the quickstart lets the agent greet first, as a real inbound line would).
They talk turn by turn — the driver pursuing its goal, the agent responding —
until the goal is met, the conversation stalls, or the max-turn cap is hit.
The audio is transcribed, and the checks score that transcript.

This is why a turn cap matters: a stuck agent with no cap produces an endless
call. It is also why the call costs money — it is a real PSTN call, not a
text exchange.

## Designing the caller persona — for onboarding

For a first run the caller should be **cooperative and realistic**:

- One clear goal, drawn straight from the agent's purpose ("check the
  balance on my account", "book a table for two on Friday").
- Natural phone behavior — moderate pace, short utterances, answers the
  agent's questions, stays on task.
- No tricks. Adversarial callers, vague callers, callers who change their
  mind — those reveal failures, but they belong in `okareo-agent-simulation`.
  A quickstart that fails on turn one teaches nothing about the mechanics.

The point of the onboarding call is for the user to *see a simulation work*,
end to end. Make it likely to succeed.

## Writing the expected result

The scenario row's `result` is the single most important field — it is what
the "result_completed" check scores against. Get it right:

- Describe the **outcome**, not the script. "The agent confirms the
  appointment and states the date and time back to the caller" — not a
  verbatim sentence you expect the agent to say.
- Make it **specific enough to judge**. "The call goes well" cannot be
  scored. "The agent identifies the caller, locates the booking, and
  cancels it" can.
- Describe a **successful** call. The expected result is the bar the agent
  should clear, not whatever it happened to do.

## Choosing checks

- **"result_completed"** — always. It answers the core question: did the
  call reach the expected result? Every voice simulation in this skill
  includes it.
- **One or two business-case checks** — pick from what the agent is for:

  | Agent purpose          | A check that fits                                  |
  | ---------------------- | -------------------------------------------------- |
  | Customer support       | The caller's issue was resolved on the call        |
  | Appointment booking    | A booking was made and read back to the caller     |
  | Order status / lookup  | The agent retrieved and stated the correct status  |
  | Triage / routing       | The caller was routed to the right place           |
  | Any voice agent        | The agent stayed on policy and in scope            |

Two or three checks total is plenty for a first run. More checks is
`okareo-agent-simulation` territory.

## Reading a voice transcript

When walking the user through the result:

- Read who spoke each turn and whether the **caller's goal was met**.
- Note where the agent **recovered** (handled a misheard word, re-asked a
  question) and where it **stalled** (looped, went silent, missed the goal).
- Separate an **agent failure** from a **caller artifact** — if the simulated
  caller behaved in a way no real caller would, the failed call is the
  persona's fault, not the agent's. Flag it rather than counting it.
- Tie the check verdicts back to specific turns, so the user sees *why* a
  check passed or failed, not just that it did.
